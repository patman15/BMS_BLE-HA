"""Constants for the BLE Battery Management System integration."""

import logging

from homeassistant.const import (
    ATTR_BATTERY_CHARGING,
    ATTR_BATTERY_LEVEL,
    ATTR_TEMPERATURE,
    ATTR_VOLTAGE,
)

DOMAIN = "bms_ble"
LOGGER = logging.getLogger(__package__)
UPDATE_INTERVAL = 30  # in seconds

# attributes (do not change)
ATTR_CURRENT = "current"  # [A]
ATTR_CYCLE_CHRG = "cycle_charge"  # [Ah]
ATTR_CYCLE_CAP = "cycle_capacity"  # [Wh]
ATTR_CYCLES = "cycles"  # [#]
ATTR_POWER = "power"  # [W]
ATTR_RUNTIME = "runtime"  # [s]
ATTR_RSSI = "rssi"
