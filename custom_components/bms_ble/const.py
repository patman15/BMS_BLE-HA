"""Constants for the BLE Battery Management System integration."""

import logging
from typing import Final

DOMAIN: Final = "bms_ble"
LOGGER: Final[logging.Logger] = logging.getLogger(__package__)
LOW_RSSI: Final[int] = -75  # dBm considered low signal strength
UPDATE_INTERVAL: Final[int] = 30  # [s]

# attributes (do not change)
ATTR_BALANCER: Final = "balancer"  # [bool]
ATTR_BALANCE_CUR: Final = "balance_current"  # [A]
ATTR_BATTERY_HEALTH: Final = "battery_health"  # [%]
ATTR_BATTERY_MODE: Final = "battery_mode"  # [int]
ATTR_CELL_COUNT: Final = "cell_count"  # [#]
ATTR_CELL_VOLTAGES: Final = "cell_voltages"  # [V]
ATTR_CHRG_MOSFET: Final = "chrg_mosfet"  # [bool]
ATTR_CURRENT: Final = "current"  # [A]
ATTR_CYCLE_CAP: Final = "cycle_capacity"  # [Wh]
ATTR_CYCLE_CHRG: Final = "cycle_charge"  # [Ah]
ATTR_CYCLES: Final = "cycles"  # [#]
ATTR_DELTA_VOLTAGE: Final = "delta_cell_voltage"  # [V]
ATTR_DISCHRG_MOSFET: Final = "dischrg_mosfet"  # [bool]
ATTR_HEATER: Final = "heater"  # [bool]
ATTR_LQ: Final = "link_quality"  # [%]
ATTR_MAX_VOLTAGE: Final = "max_cell_voltage"  # [V]
ATTR_MIN_VOLTAGE: Final = "min_cell_voltage"  # [V]
ATTR_POWER: Final = "power"  # [W]
ATTR_PROBLEM: Final = "problem"  # [bool]
ATTR_PROBLEM_CODE: Final = "problem_code"  # [int]
ATTR_RSSI: Final = "rssi"  # [dBm]
ATTR_RUNTIME: Final = "runtime"  # [s]
ATTR_TEMP_SENSORS: Final = "temperature_sensors"  # [°C]

BINARY_SENSORS: Final[int] = 6  # total number of binary sensors
LINK_SENSORS: Final[int] = 2  # total number of sensors for connection quality
SENSORS: Final[int] = 12  # total number of sensors
