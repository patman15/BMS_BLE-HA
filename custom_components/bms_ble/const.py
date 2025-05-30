"""Constants for the BLE Battery Management System integration."""

import logging
from typing import Final

from homeassistant.const import (  # noqa: F401  # pylint: disable=unused-import
    ATTR_BATTERY_CHARGING,
    ATTR_BATTERY_LEVEL,
    ATTR_TEMPERATURE,
    ATTR_VOLTAGE,
)

BMS_TYPES: Final[list[str]] = [
    "abc_bms",
    "cbtpwr_bms",
    "cbtpwr_vb_bms",
    "daly_bms",
    "ecoworthy_bms",
    "ective_bms",
    "ej_bms",
    "jbd_bms",
    "jikong_bms",
    "ogt_bms",
    "redodo_bms",
    "renogy_bms",
    "seplos_bms",
    "seplos_v2_bms",
    "roypow_bms",
    "tdt_bms",
    "dpwrcore_bms",  # only name filter
    "felicity_bms",
]  # available BMS types
DOMAIN: Final[str] = "bms_ble"
LOGGER: Final[logging.Logger] = logging.getLogger(__package__)
UPDATE_INTERVAL: Final[int] = 30  # [s]

# attributes (do not change)
ATTR_BALANCE_CUR: Final[str] = "balance_current"  # [A]
ATTR_CELL_VOLTAGES: Final[str] = "cell_voltages"  # [V]
ATTR_CURRENT: Final[str] = "current"  # [A]
ATTR_CYCLE_CAP: Final[str] = "cycle_capacity"  # [Wh]
ATTR_CYCLE_CHRG: Final[str] = "cycle_charge"  # [Ah]
ATTR_CYCLES: Final[str] = "cycles"  # [#]
ATTR_DELTA_VOLTAGE: Final[str] = "delta_voltage"  # [V]
ATTR_LQ: Final[str] = "link_quality"  # [%]
ATTR_POWER: Final[str] = "power"  # [W]
ATTR_PROBLEM: Final[str] = "problem"  # [bool]
ATTR_PROBLEM_CODE: Final[str] = "problem_code"  # [int]
ATTR_RSSI: Final[str] = "rssi"  # [dBm]
ATTR_RUNTIME: Final[str] = "runtime"  # [s]
ATTR_TEMP_SENSORS: Final[str] = "temperature_sensors"  # [°C]
