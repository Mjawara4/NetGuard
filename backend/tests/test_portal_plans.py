import uuid

import pytest

from app.models.core import Device
from app.services.portal_plans import normalise_currency, plan_duration, sellable_plans


@pytest.mark.parametrize("raw,expected", [
    ("GMD", "GMD"), ("D", "GMD"), ("d", "GMD"), ("dalasi", "GMD"),
    (None, "GMD"), ("", "GMD"), (" usd ", "USD"),
])
def test_currency_is_normalised_to_an_iso_code(raw, expected):
    assert normalise_currency(raw) == expected


@pytest.mark.parametrize("name,expected", [
    ("3-Hours", "3h"), ("24-Hours", "24h"), ("7-Days", "7d"), ("30-Days", "30d"),
    # Shapes operators typed by hand on routers NetGuard did not provision.
    ("15-Days", "15d"), ("24hours", "24h"), ("2-hours", "2h"), ("1 Week", "1w"),
    ("30min", "30m"), ("1day", "1d"),
])
def test_duration_is_read_from_the_profile_name(name, expected):
    assert plan_duration(name) == expected


@pytest.mark.parametrize("name", ["default", "Unlimited", "VIP", "", "0-Days", "Days"])
def test_profile_without_a_readable_duration_has_none(name):
    assert plan_duration(name) is None


def _device(pricing):
    device = Device(id=uuid.uuid4(), site_id=uuid.uuid4(), name="r", ip_address="10.0.0.1")
    device.voucher_template = {"profile_pricing": pricing}
    return device


def test_sellable_plans_normalise_currency_and_keep_the_price():
    plans = sellable_plans(_device({"24hours": {"price": 25.0, "currency": "D"}}))
    assert plans == {"24hours": {"price": 25, "currency": "GMD", "duration": "24h"}}


def test_a_plan_that_could_not_be_fulfilled_is_never_sellable():
    plans = sellable_plans(_device({
        "VIP": {"price": 500, "currency": "GMD"},          # no duration in the name
        "3-Hours": {"currency": "GMD"},                    # no price
        "7-Days": {"price": "", "currency": "GMD"},        # blank price
        "30-Days": "350",                                  # legacy scalar shape
        "24-Hours": {"price": 25, "currency": "GMD"},
    }))
    assert list(plans) == ["24-Hours"]


def test_sellable_plans_survive_a_missing_or_malformed_template():
    device = Device(id=uuid.uuid4(), site_id=uuid.uuid4(), name="r", ip_address="10.0.0.1")
    assert sellable_plans(device) == {}
    device.voucher_template = {"profile_pricing": ["not", "a", "dict"]}
    assert sellable_plans(device) == {}
