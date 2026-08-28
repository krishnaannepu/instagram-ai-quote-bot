from sheets_service import get_pricing_rule


# ------------------------------------------------------------------
# Numeric Conversion
# ------------------------------------------------------------------

def to_number(
    value,
    default=0,
):
    if value in {
        None,
        "",
    }:
        return default

    if isinstance(
        value,
        (int, float),
    ):
        return float(value)

    cleaned_value = (
        str(value)
        .strip()
        .replace("£", "")
        .replace(",", "")
    )

    try:
        return float(
            cleaned_value
        )

    except (
        TypeError,
        ValueError,
    ):
        return default
# ------------------------------------------------------------------
# Quote Calculation
# ------------------------------------------------------------------

def calculate_quote(
    session: dict,
):
    service = session.get(
        "service",
        "",
    )

    package = session.get(
        "package",
        "",
    )

    coverage_type = session.get(
        "coverage_type",
        "",
    )

    travel_required = session.get(
        "travel_required",
        "No",
    )

    duration_hours = to_number(
        session.get(
            "duration_hours",
            0,
        )
    )

    pricing = get_pricing_rule(
        service=service,
        package=package,
    )

    if pricing is None:
        raise ValueError(
            "No active pricing rule found for "
            f"{service} - {package}"
        )

    included_hours = to_number(
        pricing.get(
            "included_hours"
        )
    )

    extra_hour_rate = to_number(
        pricing.get(
            "extra_hour_rate"
        )
    )

    if coverage_type == "Photography":
        base_price = to_number(
            pricing.get(
                "photography_price"
            )
        )

    elif coverage_type == "Videography":
        base_price = to_number(
            pricing.get(
                "videography_price"
            )
        )

    elif coverage_type == "Both":
        base_price = to_number(
            pricing.get(
                "both_price"
            )
        )

    else:
        raise ValueError(
            "Unsupported coverage type: "
            f"{coverage_type}"
        )

    extra_hours = max(
        0,
        duration_hours
        - included_hours,
    )

    extra_hours_cost = (
        extra_hours
        * extra_hour_rate
    )

    if (
        str(
            travel_required
        ).strip().lower()
        == "yes"
    ):
        travel_fee = to_number(
            pricing.get(
                "travel_fee"
            )
        )

    else:
        travel_fee = 0

    quote_total = (
        base_price
        + extra_hours_cost
        + travel_fee
    )

    return {
        "service":
            service,

        "package":
            package,

        "coverage_type":
            coverage_type,

        "included_hours":
            included_hours,

        "duration_hours":
            duration_hours,

        "base_price":
            base_price,

        "extra_hours":
            extra_hours,

        "extra_hour_rate":
            extra_hour_rate,

        "extra_hours_cost":
            extra_hours_cost,

        "travel_fee":
            travel_fee,

        "quote_total":
            quote_total,

        "status":
            "QUOTE_READY",

        "human_handoff":
            False,
    }


# ------------------------------------------------------------------
# Customer Quote Message
# ------------------------------------------------------------------

def build_quote_message(
    session: dict,
    quote: dict,
):
    total = quote[
        "quote_total"
    ]

    base_price = quote[
        "base_price"
    ]

    extra_hours = quote[
        "extra_hours"
    ]

    extra_hour_rate = quote[
        "extra_hour_rate"
    ]

    travel_fee = quote[
        "travel_fee"
    ]

    message = (
        "Your estimated quote is "
        f"£{total:,.2f}.\n\n"
        f"Service: {session['service']}\n"
        f"Package: {session['package']}\n"
        f"Coverage: {session['coverage_type']}\n"
        f"Duration: {session['duration_hours']} hours\n"
        f"Event Date: {session['event_date']}\n"
        f"Location: {session['location']}\n"
        f"Travel Required: "
        f"{session['travel_required']}\n\n"
        f"Base Price: £{base_price:,.2f}\n"
    )

    if extra_hours > 0:
        message += (
            f"Extra Hours: {extra_hours:g} "
            f"× £{extra_hour_rate:,.2f}\n"
        )

    if travel_fee > 0:
        message += (
            f"Travel Fee: "
            f"£{travel_fee:,.2f}\n"
        )

    message += (
        "\nFinal pricing and availability "
        "may require confirmation."
    )

    return message