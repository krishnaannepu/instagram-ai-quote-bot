from pathlib import Path
from datetime import datetime, timezone
from uuid import uuid4
from threading import Lock
from time import sleep

import gspread
from gspread.utils import rowcol_to_a1


# ------------------------------------------------------------------
# Google Sheets Configuration
# ------------------------------------------------------------------

BASE_DIR = Path(__file__).resolve().parent

GOOGLE_CREDENTIALS_FILE = (
    BASE_DIR
    / "credentials"
    / "google-service-account.json"
)

SPREADSHEET_NAME = "AI Quote Assistant Database"


# ------------------------------------------------------------------
# Lazy Google Sheets Connection
# ------------------------------------------------------------------
#
# Do not open the workbook at module-import time. A temporary Google Sheets
# 503 should not prevent FastAPI from starting. The first real Sheets call
# connects with a small retry window instead.

_connection_lock = Lock()
_client = None
_spreadsheet = None


def get_spreadsheet():
    global _client, _spreadsheet

    if _spreadsheet is not None:
        return _spreadsheet

    with _connection_lock:
        if _spreadsheet is not None:
            return _spreadsheet

        last_error = None

        for attempt in range(1, 4):
            try:
                if _client is None:
                    _client = gspread.service_account(
                        filename=str(GOOGLE_CREDENTIALS_FILE),
                    )

                _spreadsheet = _client.open(
                    SPREADSHEET_NAME
                )
                return _spreadsheet

            except Exception as error:
                last_error = error
                if attempt < 3:
                    sleep(attempt)

        raise last_error


class _LazySpreadsheet:
    def worksheet(self, name: str):
        return get_spreadsheet().worksheet(name)

    def __getattr__(self, name):
        return getattr(get_spreadsheet(), name)


class _LazyWorksheet:
    def __init__(self, sheet_name: str):
        self.sheet_name = sheet_name

    def _sheet(self):
        return get_spreadsheet().worksheet(
            self.sheet_name
        )

    def __getattr__(self, name):
        return getattr(self._sheet(), name)


# Compatibility objects: existing services can keep importing these names.
spreadsheet = _LazySpreadsheet()
conversation_sheet = _LazyWorksheet("Conversation_State")
pricing_sheet = _LazyWorksheet("Pricing")
leads_sheet = _LazyWorksheet("Leads")


# ------------------------------------------------------------------
# Utility Functions
# ------------------------------------------------------------------

def current_timestamp():
    return datetime.now(
        timezone.utc
    ).isoformat()


def build_row_from_headers(
    headers: list[str],
    data: dict,
):
    return [
        data.get(header, "")
        for header in headers
    ]


# ------------------------------------------------------------------
# Conversation Lookup
# ------------------------------------------------------------------

def get_conversation(
    sender_id: str,
):
    records = (
        conversation_sheet
        .get_all_records()
    )

    for record in records:

        if (
            str(
                record.get(
                    "sender_id"
                )
            )
            == str(sender_id)
        ):
            return record

    return None


# ------------------------------------------------------------------
# Conversation Creation
# ------------------------------------------------------------------

def create_conversation(
    sender_id: str,
    recipient_id: str,
    message_id: str,
):
    existing_conversation = (
        get_conversation(
            sender_id
        )
    )

    if existing_conversation:
        return existing_conversation

    headers = (
        conversation_sheet
        .row_values(1)
    )

    conversation_data = {
        "sender_id":
            sender_id,

        "recipient_id":
            recipient_id,

        "current_stage":
            "WELCOME",

        "selected_action":
            "",

        "service":
            "",

        "package":
            "",

        "coverage_type":
            "",

        "travel_required":
            "",

        "duration_hours":
            "",

        "event_date":
            "",

        "location":
            "",

        "active_lead_id":
            "",

        "status":
            "ACTIVE",

        "last_message_id":
            message_id,

        "updated_at":
            current_timestamp(),
    }

    row_values = (
        build_row_from_headers(
            headers,
            conversation_data,
        )
    )

    conversation_sheet.append_row(
        row_values,
        value_input_option="USER_ENTERED",
    )

    return conversation_data


# ------------------------------------------------------------------
# Conversation Update
# ------------------------------------------------------------------

def update_conversation(
    sender_id: str,
    updates: dict,
):
    records = (
        conversation_sheet
        .get_all_records()
    )

    headers = (
        conversation_sheet
        .row_values(1)
    )

    for row_number, record in enumerate(
        records,
        start=2,
    ):

        if (
            str(
                record.get(
                    "sender_id"
                )
            )
            != str(sender_id)
        ):
            continue

        updated_record = {
            header:
                record.get(
                    header,
                    "",
                )
            for header in headers
        }

        for field, value in updates.items():

            if field not in headers:
                raise ValueError(
                    "Unknown "
                    "Conversation_State "
                    f"field: {field}"
                )

            updated_record[
                field
            ] = value

        updated_record[
            "updated_at"
        ] = current_timestamp()

        row_values = (
            build_row_from_headers(
                headers,
                updated_record,
            )
        )

        end_cell = rowcol_to_a1(
            row_number,
            len(headers),
        )

        conversation_sheet.update(
            values=[
                row_values
            ],
            range_name=(
                f"A{row_number}:"
                f"{end_cell}"
            ),
            value_input_option=(
                "USER_ENTERED"
            ),
        )

        return updated_record

    return None


# ------------------------------------------------------------------
# Synchronise Completed Conversation
# ------------------------------------------------------------------

def sync_conversation_from_session(
    session: dict,
):
    sender_id = str(
        session["sender_id"]
    )

    records = (
        conversation_sheet
        .get_all_records()
    )

    headers = (
        conversation_sheet
        .row_values(1)
    )

    conversation_data = {
        "sender_id":
            session.get(
                "sender_id",
                "",
            ),

        "recipient_id":
            session.get(
                "recipient_id",
                "",
            ),

        "current_stage":
            session.get(
                "current_stage",
                "",
            ),

        "selected_action":
            session.get(
                "selected_action",
                "",
            ),

        "service":
            session.get(
                "service",
                "",
            ),

        "package":
            session.get(
                "package",
                "",
            ),

        "coverage_type":
            session.get(
                "coverage_type",
                "",
            ),

        "travel_required":
            session.get(
                "travel_required",
                "",
            ),

        "duration_hours":
            session.get(
                "duration_hours",
                "",
            ),

        "event_date":
            session.get(
                "event_date",
                "",
            ),

        "location":
            session.get(
                "location",
                "",
            ),

        "active_lead_id":
            session.get(
                "active_lead_id",
                "",
            ),

        "status":
            session.get(
                "status",
                "",
            ),

        "last_message_id":
            session.get(
                "last_message_id",
                "",
            ),

        "updated_at":
            current_timestamp(),
    }

    row_values = (
        build_row_from_headers(
            headers,
            conversation_data,
        )
    )

    for row_number, record in enumerate(
        records,
        start=2,
    ):

        if (
            str(
                record.get(
                    "sender_id"
                )
            )
            != sender_id
        ):
            continue

        end_cell = rowcol_to_a1(
            row_number,
            len(headers),
        )

        conversation_sheet.update(
            values=[
                row_values
            ],
            range_name=(
                f"A{row_number}:"
                f"{end_cell}"
            ),
            value_input_option=(
                "USER_ENTERED"
            ),
        )

        return conversation_data

    conversation_sheet.append_row(
        row_values,
        value_input_option="USER_ENTERED",
    )

    return conversation_data


# ------------------------------------------------------------------
# Lead Lookup
# ------------------------------------------------------------------

def get_lead_by_id(
    lead_id: str,
):
    if not lead_id:
        return None

    records = (
        leads_sheet
        .get_all_records()
    )

    for record in records:

        if (
            str(
                record.get(
                    "lead_id"
                )
            )
            == str(lead_id)
        ):
            return record

    return None


# ------------------------------------------------------------------
# Completed Lead Creation
# ------------------------------------------------------------------

def save_completed_lead(
    session: dict,
    quote_data: dict | None = None,
    ig_handle: str = "",
):
    quote_data = (
        quote_data or {}
    )

    existing_lead_id = (
        session.get(
            "active_lead_id"
        )
    )

    if existing_lead_id:

        existing_lead = (
            get_lead_by_id(
                existing_lead_id
            )
        )

        if existing_lead:
            return existing_lead

    lead_id = (
        "LEAD-"
        + uuid4()
        .hex[:8]
        .upper()
    )

    timestamp = (
        current_timestamp()
    )

    lead_data = {
        "lead_id":
            lead_id,

        "created_at":
            timestamp,

        "sender_id":
            session.get(
                "sender_id",
                "",
            ),

        "ig_handle":
            ig_handle,

        "service":
            session.get(
                "service",
                "",
            ),

        "package":
            session.get(
                "package",
                "",
            ),

        "coverage_type":
            session.get(
                "coverage_type",
                "",
            ),

        "event_date":
            session.get(
                "event_date",
                "",
            ),

        "location":
            session.get(
                "location",
                "",
            ),

        "duration_hours":
            session.get(
                "duration_hours",
                "",
            ),

        "travel_required":
            session.get(
                "travel_required",
                "",
            ),

        "base_price":
            quote_data.get(
                "base_price",
                "",
            ),

        "extra_hours":
            quote_data.get(
                "extra_hours",
                "",
            ),

        "extra_hour_rate":
            quote_data.get(
                "extra_hour_rate",
                "",
            ),

        "travel_fee":
            quote_data.get(
                "travel_fee",
                "",
            ),

        "quote_total":
            quote_data.get(
                "quote_total",
                "",
            ),

        "status":
            quote_data.get(
                "status",
                "QUOTE_INPUT_COMPLETE",
            ),

        "human_handoff":
            quote_data.get(
                "human_handoff",
                False,
            ),

        "updated_at":
            timestamp,
    }

    headers = (
        leads_sheet
        .row_values(1)
    )

    row_values = (
        build_row_from_headers(
            headers,
            lead_data,
        )
    )

    leads_sheet.append_row(
        row_values,
        value_input_option="USER_ENTERED",
    )

    # Keep the lead ID inside the
    # active in-memory conversation.
    session[
        "active_lead_id"
    ] = lead_id

    print(
        "New permanent lead saved:",
        lead_id,
    )

    return lead_data


# ------------------------------------------------------------------
# Persist Completed Quote Input
# ------------------------------------------------------------------

def persist_completed_quote(
    session: dict,
    quote_data: dict | None = None,
    ig_handle: str = "",
):
    lead = save_completed_lead(
        session=session,
        quote_data=quote_data,
        ig_handle=ig_handle,
    )

    conversation = (
        sync_conversation_from_session(
            session
        )
    )

    return {
        "lead": lead,
        "conversation": conversation,
    }


# ------------------------------------------------------------------
# Lead Update
# ------------------------------------------------------------------

def update_lead(
    lead_id: str,
    updates: dict,
):
    records = (
        leads_sheet
        .get_all_records()
    )

    headers = (
        leads_sheet
        .row_values(1)
    )

    for row_number, record in enumerate(
        records,
        start=2,
    ):

        if (
            str(
                record.get(
                    "lead_id"
                )
            )
            != str(lead_id)
        ):
            continue

        updated_record = {
            header:
                record.get(
                    header,
                    "",
                )
            for header in headers
        }

        for field, value in updates.items():

            if field not in headers:
                raise ValueError(
                    f"Unknown Leads field: {field}"
                )

            updated_record[
                field
            ] = value

        updated_record[
            "updated_at"
        ] = current_timestamp()

        row_values = (
            build_row_from_headers(
                headers,
                updated_record,
            )
        )

        end_cell = rowcol_to_a1(
            row_number,
            len(headers),
        )

        leads_sheet.update(
            values=[
                row_values
            ],
            range_name=(
                f"A{row_number}:"
                f"{end_cell}"
            ),
            value_input_option=(
                "USER_ENTERED"
            ),
        )

        return updated_record

    return None


# ------------------------------------------------------------------
# Latest Lead Lookup
# ------------------------------------------------------------------

def get_latest_lead(
    sender_id: str,
):
    records = (
        leads_sheet
        .get_all_records()
    )

    for record in reversed(
        records
    ):

        if (
            str(
                record.get(
                    "sender_id"
                )
            )
            == str(sender_id)
        ):
            return record

    return None


# ------------------------------------------------------------------
# Pricing Lookup
# ------------------------------------------------------------------

def get_pricing_rule(
    service: str,
    package: str,
):
    records = pricing_sheet.get_all_records()

    for record in records:

        record_service = str(
            record.get(
                "service",
                "",
            )
        ).strip()

        record_package = str(
            record.get(
                "package",
                "",
            )
        ).strip()

        active_value = record.get(
            "active",
            True,
        )

        is_active = str(
            active_value
        ).strip().lower() in {
            "true",
            "1",
            "yes",
        }

        if (
            record_service.lower()
            == service.strip().lower()
            and
            record_package.lower()
            == package.strip().lower()
            and
            is_active
        ):
            return record

    return None
