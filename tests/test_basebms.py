"""Test the BLE Battery Management System base class functions."""

from custom_components.bms_ble.const import (
    ATTR_BATTERY_CHARGING,
    ATTR_CURRENT,
    ATTR_CYCLE_CAP,
    ATTR_DELTA_VOLTAGE,
    ATTR_POWER,
    ATTR_RUNTIME,
    ATTR_TEMPERATURE,
)
from custom_components.bms_ble.plugins.basebms import BaseBMS, BMSsample


def test_calc_missing_values(bms_data_fixture: BMSsample) -> None:
    """Check if missing data is correctly calculated."""
    bms_data = ref = bms_data_fixture
    BaseBMS.calc_values(
        bms_data,
        {
            ATTR_BATTERY_CHARGING,
            ATTR_CYCLE_CAP,
            ATTR_POWER,
            ATTR_RUNTIME,
            ATTR_DELTA_VOLTAGE,
            ATTR_TEMPERATURE,
            "invalid",
        },
    )
    ref = ref | {
        ATTR_CYCLE_CAP: 238,
        ATTR_DELTA_VOLTAGE: 0.111,
        ATTR_POWER: (
            -91
            if bms_data[ATTR_CURRENT] < 0
            else 0 if bms_data[ATTR_CURRENT] == 0 else 147
        ),
        ATTR_BATTERY_CHARGING: bms_data[ATTR_CURRENT]
        > 0,  # battery is charging if current is positive
        ATTR_TEMPERATURE: -34.396,
    }
    if bms_data[ATTR_CURRENT] < 0:
        ref |= {ATTR_RUNTIME: 9415}

    assert bms_data == ref
