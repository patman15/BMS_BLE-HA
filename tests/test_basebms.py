"""Test the BLE Battery Management System base class functions."""

import pytest

from custom_components.bms_ble.const import (
    ATTR_BATTERY_CHARGING,
    ATTR_BATTERY_LEVEL,
    ATTR_CURRENT,
    ATTR_CYCLE_CAP,
    ATTR_CYCLE_CHRG,
    ATTR_DELTA_VOLTAGE,
    ATTR_POWER,
    ATTR_PROBLEM,
    ATTR_RUNTIME,
    ATTR_TEMPERATURE,
    ATTR_VOLTAGE,
    KEY_CELL_VOLTAGE,
    KEY_DESIGN_CAP,
    KEY_PROBLEM,
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
    ref: BMSsample = ref | {
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
    BaseBMS._add_missing_values(bms_data, {ATTR_VOLTAGE})
    assert bms_data == ref | {ATTR_VOLTAGE: 7.023}


def test_calc_cycle_chrg() -> None:
    """Check if missing data is correctly calculated."""
    bms_data = ref = {ATTR_BATTERY_LEVEL: 73, KEY_DESIGN_CAP: 125.0}
    BaseBMS._add_missing_values(bms_data, {ATTR_CYCLE_CHRG})
    assert bms_data == ref | {ATTR_CYCLE_CHRG: 91.25}


@pytest.fixture(
    name="problem_samples",
    params=[
        ({ATTR_VOLTAGE: -1}, "negative overall voltage"),
        ({f"{KEY_CELL_VOLTAGE}0": 5.907}, "high cell voltage"),
        ({f"{KEY_CELL_VOLTAGE}0": -0.001}, "negative cell voltage"),
        ({ATTR_DELTA_VOLTAGE: 5.907}, "doubtful delta voltage"),
        ({ATTR_CYCLE_CHRG: 0}, "doubtful cycle charge"),
        ({ATTR_BATTERY_LEVEL: 101}, "doubtful SoC"),
        ({KEY_PROBLEM: 0x1}, "BMS problem code"),
        ({ATTR_PROBLEM: True}, "BMS problem report"),
    ],
    ids=lambda param: param[1],
)
def mock_bms_data(request: pytest.FixtureRequest) -> BMSsample:
    """Return BMS data to check error handling function."""
    return request.param[0]


def test_problems(problem_samples: BMSsample) -> None:
    """Check if missing data is correctly calculated."""
    bms_data: BMSsample = problem_samples

    BaseBMS._add_missing_values(bms_data, {ATTR_RUNTIME})

    assert bms_data == problem_samples | {"problem": True}
