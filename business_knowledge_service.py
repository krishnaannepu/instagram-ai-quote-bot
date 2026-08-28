from copy import deepcopy
from threading import Lock
from time import monotonic

from sheets_service import spreadsheet


# ------------------------------------------------------------------
# Business Knowledge Cache Configuration
# ------------------------------------------------------------------

CACHE_TTL_SECONDS = 300

SHEET_MAP = {
    "pricing": "Pricing",
    "packages": "Packages",
    "business_info": "Business_Info",
    "faqs": "FAQs",
}

_cache_lock = Lock()

_cache = {
    "loaded_at": 0.0,
    "pricing": [],
    "packages": [],
    "business_info": [],
    "faqs": [],
}


# ------------------------------------------------------------------
# Utility Functions
# ------------------------------------------------------------------

def _is_active(value) -> bool:
    if isinstance(value, bool):
        return value

    return str(value).strip().lower() in {
        "true",
        "1",
        "yes",
    }


def _cache_is_fresh() -> bool:
    loaded_at = _cache.get("loaded_at", 0.0)

    if not loaded_at:
        return False

    return (
        monotonic() - loaded_at
        < CACHE_TTL_SECONDS
    )


def _load_active_rows(sheet_name: str) -> list[dict]:
    worksheet = spreadsheet.worksheet(sheet_name)
    records = worksheet.get_all_records()

    return [
        record
        for record in records
        if _is_active(
            record.get("active", True)
        )
    ]


# ------------------------------------------------------------------
# Cache Refresh
# ------------------------------------------------------------------

def refresh_business_knowledge(
    force: bool = False,
) -> dict:
    if not force and _cache_is_fresh():
        return deepcopy(_cache)

    with _cache_lock:
        if not force and _cache_is_fresh():
            return deepcopy(_cache)

        new_cache = {
            "loaded_at": monotonic(),
        }

        try:
            for cache_key, sheet_name in SHEET_MAP.items():
                new_cache[cache_key] = (
                    _load_active_rows(
                        sheet_name
                    )
                )

        except Exception as error:
            if _cache.get("loaded_at"):
                print(
                    "Business knowledge refresh failed; "
                    "using existing cache:",
                    error,
                )
                return deepcopy(_cache)

            raise

        _cache.clear()
        _cache.update(new_cache)

        print(
            "Business knowledge cache refreshed:",
            {
                key: len(_cache[key])
                for key in SHEET_MAP
            },
        )

        return deepcopy(_cache)


# ------------------------------------------------------------------
# Public Cache Access
# ------------------------------------------------------------------

def get_business_knowledge(
    force_refresh: bool = False,
) -> dict:
    return refresh_business_knowledge(
        force=force_refresh
    )


def get_pricing_knowledge() -> list[dict]:
    return get_business_knowledge()[
        "pricing"
    ]


def get_package_knowledge() -> list[dict]:
    return get_business_knowledge()[
        "packages"
    ]


def get_business_info() -> list[dict]:
    return get_business_knowledge()[
        "business_info"
    ]


def get_faq_knowledge() -> list[dict]:
    return get_business_knowledge()[
        "faqs"
    ]


# ------------------------------------------------------------------
# Exact Business Knowledge Lookups
# ------------------------------------------------------------------

def get_business_info_value(
    key: str,
):
    normalized_key = key.strip().lower()

    for record in get_business_info():
        record_key = str(
            record.get("key", "")
        ).strip().lower()

        if record_key == normalized_key:
            return record.get("value")

    return None


def get_package_info(
    service: str,
    package: str,
):
    normalized_service = (
        service.strip().lower()
    )
    normalized_package = (
        package.strip().lower()
    )

    for record in get_package_knowledge():
        record_service = str(
            record.get("service", "")
        ).strip().lower()

        record_package = str(
            record.get("package", "")
        ).strip().lower()

        if (
            record_service == normalized_service
            and record_package
            == normalized_package
        ):
            return record

    return None


def get_pricing_info(
    service: str,
    package: str,
):
    normalized_service = (
        service.strip().lower()
    )
    normalized_package = (
        package.strip().lower()
    )

    for record in get_pricing_knowledge():
        record_service = str(
            record.get("service", "")
        ).strip().lower()

        record_package = str(
            record.get("package", "")
        ).strip().lower()

        if (
            record_service == normalized_service
            and record_package
            == normalized_package
        ):
            return record

    return None
