"""Module to support Dummy BMS."""

# import asyncio
import logging
from typing import Any

from bleak.backends.device import BLEDevice
from bleak.uuids import normalize_uuid_str

from custom_components.bms_ble.const import (
    ATTR_BATTERY_CHARGING,
    # ATTR_BATTERY_LEVEL,
    ATTR_CURRENT,
    # ATTR_CYCLE_CAP,
    # ATTR_CYCLE_CHRG,
    # ATTR_CYCLES,
    # ATTR_DELTA_VOLTAGE,
    ATTR_POWER,
    # ATTR_RUNTIME,
    # ATTR_TEMPERATURE,
    ATTR_VOLTAGE,
)

from .basebms import BaseBMS, BMSsample

LOGGER = logging.getLogger(__name__)


class BMS(BaseBMS):
    """Dummy battery class implementation."""

    def __init__(self, ble_device: BLEDevice, reconnect: bool = False) -> None:
        """Initialize BMS."""
        LOGGER.debug("%s init(), BT address: %s", self.device_id(), ble_device.address)
        super().__init__(LOGGER, self._notification_handler, ble_device, reconnect)

    @staticmethod
    def matcher_dict_list() -> list[dict[str, Any]]:
        """Provide BluetoothMatcher definition."""
        return [{"local_name": "dummy", "connectable": True}]

    @staticmethod
    def device_info() -> dict[str, str]:
        """Return device information for the battery management system."""
        return {"manufacturer": "Dummy Manufacturer", "model": "dummy model"}

    @staticmethod
    def uuid_services() -> list[str]:
        """Return list of 128-bit UUIDs of services required by BMS."""
        return [normalize_uuid_str("0000")]  # change service UUID here!

    @staticmethod
    def uuid_rx() -> str:
        """Return 16-bit UUID of characteristic that provides notification/read property."""
        return "#changeme"

    @staticmethod
    def uuid_tx() -> str:
        """Return 16-bit UUID of characteristic that provides write property."""
        return "#changeme"

    @staticmethod
    def _calc_values() -> set[str]:
        return {
            ATTR_POWER,
            ATTR_BATTERY_CHARGING,
        }  # calculate further values from BMS provided set ones

    def _notification_handler(self, _sender, data: bytearray) -> None:
        """Handle the RX characteristics notify event (new data arrives)."""

    async def _async_update(self) -> BMSsample:
        """Update battery status information."""
        LOGGER.debug("(%s) replace with command to UUID %s", self.name, BMS.uuid_tx())
        # await self._client.write_gatt_char(BMS.uuid_tx(), data=b"<some_command>"")
        # await asyncio.wait_for(self._wait_event(), timeout=BAT_TIMEOUT)

        return {
            ATTR_VOLTAGE: 12,
            ATTR_CURRENT: 1.5,
        }  # set fixed values, replace with implementation in _notification_handler
