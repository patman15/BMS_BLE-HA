"""Test the BLE Battery Management System base class functions."""

import pytest

from custom_components.bms_ble.plugins.basebms import BaseBMS, BMSsample


def test_calc_missing_values(bms_data_fixture: BMSsample) -> None:
    """Check if missing data is correctly calculated."""
    bms_data: BMSsample = bms_data_fixture
    ref: BMSsample = bms_data_fixture.copy()

    BaseBMS._add_missing_values(
        bms_data,
        frozenset(
            {
                "battery_charging",
                "cycle_capacity",
                "power",
                "runtime",
                "delta_voltage",
                "temperature",
                "voltage",  # check that not overwritten
            }
        ),
    )
    ref = ref | {
        "cycle_capacity": 238,
        "delta_voltage": 0.111,
        "power": (
            -91
            if bms_data.get("current", 0) < 0
            else 0 if bms_data.get("current") == 0 else 147
        ),
        # battery is charging if current is positive
        "battery_charging": bms_data.get("current", 0) > 0,
        "temperature": -34.396,
        "problem": False
    }
    if bms_data.get("current", 0) < 0:
        ref |= {"runtime": 9415}

    assert bms_data == ref


def test_calc_voltage() -> None:
    """Check if missing data is correctly calculated."""
    bms_data: BMSsample = {"cell_voltages": [3.456, 3.567]}
    ref: BMSsample = bms_data.copy()
    BaseBMS._add_missing_values(bms_data, frozenset({"voltage"}))
    assert bms_data == ref | {"voltage": 7.023, "problem": False}


def test_calc_cycle_chrg() -> None:
    """Check if missing data is correctly calculated."""
    bms_data: BMSsample = {"battery_level": 73, "design_capacity": 125}
    ref: BMSsample = bms_data.copy()
    BaseBMS._add_missing_values(bms_data, frozenset({"cycle_charge"}))
    assert bms_data == ref | {"cycle_charge": 91.25, "problem": False}


@pytest.fixture(
    name="problem_samples",
    params=[
        ({"voltage": -1}, "negative overall voltage"),
        ({"cell_voltages": [5.907]}, "high cell voltage"),
        ({"cell_voltages": [-0.001]}, "negative cell voltage"),
        ({"delta_voltage": 5.907}, "doubtful delta voltage"),
        ({"cycle_charge": 0}, "doubtful cycle charge"),
        ({"battery_level": 101}, "doubtful SoC"),
        ({"problem_code": 0x1}, "BMS problem code"),
        ({"problem": True}, "BMS problem report"),
    ],
    ids=lambda param: param[1],
)
def mock_bms_data(request: pytest.FixtureRequest) -> BMSsample:
    """Return BMS data to check error handling function."""
    return request.param[0]


def test_problems(problem_samples: BMSsample) -> None:
    """Check if missing data is correctly calculated."""
    bms_data: BMSsample = problem_samples.copy()

    BaseBMS._add_missing_values(bms_data, frozenset({"runtime"}))

    assert bms_data == problem_samples | {"problem": True}
