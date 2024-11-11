"""Test the BLE Battery Management System base class functions."""

from custom_components.bms_ble.const import (
    ATTR_BATTERY_CHARGING,
    ATTR_CURRENT,
    ATTR_CYCLE_CAP,
    ATTR_DELTA_VOLTAGE,
    ATTR_POWER,
    ATTR_RUNTIME,
    ATTR_TEMPERATURE,
    ATTR_VOLTAGE,
    KEY_CELL_VOLTAGE
)
from custom_components.bms_ble.plugins.basebms import BaseBMS, BMSsample


def test_calc_missing_values(bms_data_fixture: BMSsample) -> None:
    """Check if missing data is correctly calculated."""
    bms_data = ref = bms_data_fixture
    BaseBMS._add_missing_values(
        bms_data,
        {
            ATTR_BATTERY_CHARGING,
            ATTR_CYCLE_CAP,
            ATTR_POWER,
            ATTR_RUNTIME,
            ATTR_DELTA_VOLTAGE,
            ATTR_TEMPERATURE,
            ATTR_VOLTAGE,  # check that not overwritten
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


def test_calc_voltage() -> None:
    """Check if missing data is correctly calculated."""
    bms_data = ref = {f"{KEY_CELL_VOLTAGE}0": 3.456, f"{KEY_CELL_VOLTAGE}1": 3.567}
    BaseBMS._add_missing_values(
        bms_data,
        {ATTR_VOLTAGE},
    )
    ref = ref | {ATTR_VOLTAGE: 7.023}

    assert bms_data == ref
