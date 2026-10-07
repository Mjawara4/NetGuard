"""Which hotspot profiles can be sold online, and what a purchase grants.

One definition shared by the plan listing, checkout creation, the fulfilment
webhook and the generated portal page: a plan may only be offered if
fulfilment can deliver it, otherwise a customer pays and gets nothing.
"""

import re
from typing import Optional

# Operators type the dalasi as "D" in the pricing form; Modem Pay wants ISO 4217.
_CURRENCY_ALIASES = {"D": "GMD", "DALASI": "GMD", "DALASIS": "GMD"}
DEFAULT_CURRENCY = "GMD"

_DURATION_RE = re.compile(r"^\s*(\d+)[\s_-]*([a-z]+)\s*$", re.IGNORECASE)
_UNIT_SUFFIX = {
    "m": "m", "min": "m", "mins": "m", "minute": "m", "minutes": "m",
    "h": "h", "hr": "h", "hrs": "h", "hour": "h", "hours": "h",
    "d": "d", "day": "d", "days": "d",
    "w": "w", "wk": "w", "week": "w", "weeks": "w",
}


def normalise_currency(value) -> str:
    code = str(value or "").strip().upper()
    if not code:
        return DEFAULT_CURRENCY
    return _CURRENCY_ALIASES.get(code, code)


def plan_duration(profile_name) -> Optional[str]:
    """RouterOS limit-uptime for a profile named like "3-Hours" or "24hours"."""
    match = _DURATION_RE.match(str(profile_name or ""))
    if not match:
        return None
    count, suffix = int(match.group(1)), _UNIT_SUFFIX.get(match.group(2).lower())
    if not count or not suffix:
        return None
    return f"{count}{suffix}"


def _price(raw):
    try:
        price = float(raw)
    except (TypeError, ValueError):
        return None
    if price <= 0:
        return None
    return int(price) if price.is_integer() else price


def sellable_plans(device) -> dict:
    """{profile: {price, currency, duration}} for every plan fulfilment can deliver."""
    pricing = (device.voucher_template or {}).get("profile_pricing", {})
    if not isinstance(pricing, dict):
        return {}
    plans = {}
    for profile, details in pricing.items():
        if not isinstance(details, dict):
            continue
        price = _price(details.get("price"))
        duration = plan_duration(profile)
        if price is None or duration is None:
            continue
        plans[profile] = {
            "price": price,
            "currency": normalise_currency(details.get("currency")),
            "duration": duration,
        }
    return plans
