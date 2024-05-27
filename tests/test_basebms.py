"""Test the BLE Battery Management System base class functions."""

from custom_components.bms_ble.const import (
    ATTR_BATTERY_CHARGING,
    ATTR_CYCLE_CAP,
    ATTR_POWER,
    ATTR_RUNTIME,
)
from custom_components.bms_ble.plugins.basebms import BaseBMS


def test_calc_missing_values(bms_data_fixture) -> None:
    """Check if missing data is correctly calculated."""
    bms_data = reference = bms_data_fixture
    BaseBMS.calc_values(
        bms_data,
        {ATTR_BATTERY_CHARGING, ATTR_CYCLE_CAP, ATTR_POWER, ATTR_RUNTIME, "invalid"},
    )
    assert bms_data == reference | {ATTR_BATTERY_CHARGING: True, ATTR_CYCLE_CAP: 147, ATTR_POWER: 91, ATTR_RUNTIME: 5815}
