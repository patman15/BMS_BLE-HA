"""Module to support Supervolt BMS"""

import logging
from typing import Any, Dict, Optional, Union
import asyncio

from bleak.backends.device import BLEDevice
from bleak import BleakClient
from bleak.uuids import normalize_uuid_str

from ..const import (
    ATTR_BATTERY_CHARGING,
    ATTR_BATTERY_LEVEL,
    ATTR_CURRENT,
    ATTR_CYCLE_CAP,
    ATTR_CYCLE_CHRG,
    ATTR_CYCLES,
    ATTR_POWER,
    ATTR_TEMPERATURE,
    ATTR_VOLTAGE,
)
from .basebms import BaseBMS

BAT_TIMEOUT = 10
LOGGER = logging.getLogger(__name__)

UUID_SERVICE = normalize_uuid_str("FF00")
UUID_RX = normalize_uuid_str("FF01")
UUID_TX = normalize_uuid_str("FF02")


class BMS(BaseBMS):
    """Supervolt BMS v4 class implementation."""

    CMD_STATUS = bytearray(b"\xDD\xA5\x03\x00\xFF\xFD\x77")

    def __init__(self, ble_device: BLEDevice, reconnect: bool = False) -> None:
        """Initialize BMS."""
        LOGGER.debug("%s init(), BT address: %s", self.device_id(), ble_device.address)
        self._reconnect: bool = reconnect
        self._ble_device: BLEDevice = ble_device
        self._data_event = asyncio.Event()
        assert self._ble_device is not None
        self._client: Optional[BleakClient] = None
        self._connected: bool = False
        self._max_capacity: int = None

    def convert_data(self) -> Dict[str, Union[int, float]]:
        cycle_chrg = int.from_bytes(self._data[8:10], "big") / 100.0
        design_capacity = int.from_bytes(self._data[10:12], "big") / 100.0
        # check if max capacity is already set, if not set it
        if self._max_capacity is None:
            self._max_capacity = design_capacity
        # Supervolts sometimes have more than designed capacity
        # adjust max to get accurate battery level
        if cycle_chrg > self._max_capacity:
            self._max_capacity = cycle_chrg

        temperatures = [
            (int.from_bytes(self._data[idx : idx + 2], "big") - 2731) / 10.0
            for idx in [27 + i * 2 for i in range(self._data[26])]
        ]
        return {
            ATTR_VOLTAGE: int.from_bytes(self._data[4:6], "big") / 100.0,
            ATTR_CURRENT: int.from_bytes(self._data[6:8], "big", signed=True) / 100.0,
            ATTR_CYCLE_CHRG: cycle_chrg,
            ATTR_CYCLE_CAP: cycle_chrg * 12.8,
            ATTR_CYCLES: int.from_bytes(self._data[12:14], "big"),
            ATTR_BATTERY_LEVEL: (cycle_chrg / self._max_capacity) * 100,
            ATTR_TEMPERATURE: sum(temperatures) / len(temperatures),
        }

    @staticmethod
    def matcher_dict_list() -> list[dict[str, Any]]:
        """Provide BluetoothMatcher definition."""
        return [
            {
                "local_name": "SX100P-*",
                "service_uuid": UUID_SERVICE,
                "connectable": True,
            }
        ]

    @staticmethod
    def device_info() -> dict[str, str]:
        """Return device information for the battery management system."""
        return {"manufacturer": "Supervolt", "model": "BMS v4"}

    async def _connect(self) -> None:
        """Connect to the BMS and setup notification if not connected."""

        if not self._connected:
            LOGGER.debug("Connecting BMS (%s)", self._ble_device.name)
            self._client = BleakClient(
                self._ble_device,
                disconnected_callback=self._on_disconnect,
                services=[UUID_SERVICE],
            )
            await self._client.connect()
            await self._client.start_notify(UUID_RX, self._notification_handler)
            self._connected = True
        else:
            LOGGER.debug("BMS %s already connected", self._ble_device.name)

    def _notification_handler(self, sender, data: bytearray) -> None:
        self._data = data
        self._data_event.set()

    def _on_disconnect(self, client: BleakClient) -> None:
        """Disconnect callback function."""

        LOGGER.debug("Disconnected from BMS (%s)", client.address)
        self._connected = False

    async def disconnect(self) -> None:
        """Disconnect connection to BMS if active."""

        if self._client and self._connected:
            LOGGER.debug("Disconnecting BMS (%s)", self._ble_device.name)
            try:
                self._data_event.clear()
                await self._client.disconnect()
            except BleakError:
                LOGGER.warning("Disconnect failed!")

    async def _wait_event(self) -> None:
        await self._data_event.wait()
        self._data_event.clear()

    async def async_update(self) -> dict[str, int | float | bool]:
        """Update battery status information."""
        await self._connect()
        assert self._client is not None
        await self._client.write_gatt_char(char_specifier=UUID_TX, data=self.CMD_STATUS)
        await asyncio.wait_for(self._wait_event(), timeout=BAT_TIMEOUT)
        data = self.convert_data()

        # calculate further values from previously set ones
        self.calc_values(data, {ATTR_POWER, ATTR_BATTERY_CHARGING})
        if self._reconnect:
            await self.disconnect()

        return data
