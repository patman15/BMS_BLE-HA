"""Constants for the BLE Battery Management System integration."""

import logging
from typing import Final

from homeassistant.const import (  # noqa: F401
    ATTR_BATTERY_CHARGING,
    ATTR_BATTERY_LEVEL,
    ATTR_TEMPERATURE,
    ATTR_VOLTAGE,
)

BMS_TYPES: Final = [
    "cbtpwr_bms",
    "daly_bms",
    "dpwrcore_bms",
    "jbd_bms",
    "jikong_bms",
    "ogt_bms",
    "seplos_bms",
]  # available BMS types
DOMAIN: Final = "bms_ble"
LOGGER: Final = logging.getLogger(__package__)
UPDATE_INTERVAL: Final = 30  # [s]
MAX_CONNECT_RETRIES: Final = 4  # [#]

# attributes (do not change)
ATTR_CELL_VOLTAGES: Final = "cell_voltages"  # [V]
ATTR_CURRENT: Final = "current"  # [A]
ATTR_CYCLE_CAP: Final = "cycle_capacity"  # [Wh]
ATTR_CYCLE_CHRG: Final = "cycle_charge"  # [Ah]
ATTR_CYCLES: Final = "cycles"  # [#]
ATTR_DELTA_VOLTAGE: Final = "delta_voltage"  # [V]
ATTR_LQ: Final = "link_quality"  # [%]
ATTR_POWER: Final = "power"  # [W]
ATTR_RSSI: Final = "rssi"  # [dBm]
ATTR_RUNTIME: Final = "runtime"  # [s]
ATTR_TEMP_SENSORS: Final = "temperature_sensors"  # [°C]

# temporary dictionary keys (do not change)
KEY_CELL_COUNT: Final = "cell_count"  # [#]
KEY_CELL_VOLTAGE: Final = "cell#"  # [V]
KEY_DESIGN_CAP: Final = "design_capacity"  # [Ah]
KEY_PACK_COUNT: Final = "pack_count"  # [#]
KEY_TEMP_SENS: Final = "temp_sensors"  # [#]
KEY_TEMP_VALUE: Final = "temp#"  # [°C]
