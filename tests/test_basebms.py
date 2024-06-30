"""Test the BLE Battery Management System base class functions."""

import pytest
from custom_components.bms_ble.const import (
    ATTR_BATTERY_CHARGING,
    ATTR_CURRENT,
    ATTR_CYCLE_CAP,
    ATTR_POWER,
    ATTR_RUNTIME,
    ATTR_CYCLE_CHRG,
    ATTR_VOLTAGE,
    ATTR_DELTA_VOLTAGE,
    KEY_CELL_VOLTAGE,
)
from custom_components.bms_ble.plugins.basebms import BaseBMS


@pytest.fixture(params=[-13, 0, 21])
def bms_data_fixture(request):
    """Return a fake BMS data dictionary."""

    return {
        ATTR_VOLTAGE: 7.0,
        ATTR_CURRENT: request.param,
        ATTR_CYCLE_CHRG: 34,
        f"{KEY_CELL_VOLTAGE}0": 3.456,
        f"{KEY_CELL_VOLTAGE}1": 3.567,
    }


def test_calc_missing_values(bms_data_fixture) -> None:
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
    }
    if bms_data[ATTR_CURRENT] < 0:
        ref |= {ATTR_RUNTIME: 9415}

    assert bms_data == ref
