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
    "daly_bms",
    "jbd_bms",
    "jikong_bms",
    "ogt_bms",
    "seplos_bms",
]  # available BMS types
DOMAIN: Final = "bms_ble"
LOGGER: Final = logging.getLogger(__package__)
UPDATE_INTERVAL: Final = 30  # in seconds
SCAN_INTERVAL = UPDATE_INTERVAL * 0.9  # diagnosis interval [s]

# attributes (do not change)
ATTR_CELL_VOLTAGES: Final = "cell_voltages"  # [V]
ATTR_CURRENT: Final = "current"  # [A]
ATTR_CYCLE_CHRG: Final = "cycle_charge"  # [Ah]
ATTR_CYCLE_CAP: Final = "cycle_capacity"  # [Wh]
ATTR_CYCLES: Final = "cycles"  # [#]
ATTR_DELTA_VOLTAGE: Final = "delta_voltage"  # [V]
ATTR_LQ: Final = "link_quality"  # [%]
ATTR_POWER: Final = "power"  # [W]
ATTR_RSSI: Final = "rssi"  # [dBm]
ATTR_RUNTIME: Final = "runtime"  # [s]

# temporary dictionary keys (do not change)
KEY_TEMP_SENS: Final = "temp_sensors"  # [#]
KEY_PACK_COUNT: Final = "pack_count"  # [#]
KEY_CELL_VOLTAGE: Final = "cell#"  # [V]
KEY_CELL_COUNT: Final = "cell_count"  # [#]
