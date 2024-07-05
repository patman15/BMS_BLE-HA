"""Module to support Seplos V3 Smart BMS."""

import asyncio
from collections.abc import Callable
import logging
from typing import Any

from bleak import BleakClient
from bleak.backends.device import BLEDevice
from bleak.exc import BleakError
from bleak.uuids import normalize_uuid_str

# from ..const import (
#     ATTR_BATTERY_CHARGING,
#     ATTR_BATTERY_LEVEL,
#     ATTR_CURRENT,
#     ATTR_CYCLE_CAP,
#     ATTR_CYCLE_CHRG,
#     ATTR_CYCLES,
#     ATTR_POWER,
#     ATTR_RUNTIME,
#     ATTR_TEMPERATURE,
#     ATTR_VOLTAGE,
# )
from .basebms import BaseBMS

BAT_TIMEOUT = 10
LOGGER = logging.getLogger(__name__)

# setup UUIDs
#    serv 0000fff0-0000-1000-8000-00805f9b34fb
#	 char 0000fff1-0000-1000-8000-00805f9b34fb (#16): ['read', 'notify']
#	 char 0000fff2-0000-1000-8000-00805f9b34fb (#20): ['read', 'write-without-response', 'write']
UUID_CHAR = normalize_uuid_str("FFF1")
UUID_SERVICE = normalize_uuid_str("FFF0")


class BMS(BaseBMS):
    """Seplos V3 Smart BMS class implementation."""

    def __init__(self, ble_device: BLEDevice, reconnect: bool = False) -> None:
        """Intialize private BMS members."""
        self._reconnect = reconnect
        self._ble_device = ble_device
        assert self._ble_device.name is not None
        self._client: BleakClient | None = None
        self._data: bytearray | None = None
        self._data_final: bytearray | None = None
        self._data_event = asyncio.Event()
        self._connected = False  # flag to indicate active BLE connection
        self._char_write_handle: int | None = None
        self._FIELDS: list[tuple[str, int, int, bool, Callable[[int], int | float]]] = [
            # (ATTR_TEMPERATURE, 144, 2, True, lambda x: float(x / 10)),
            # (ATTR_VOLTAGE, 150, 4, False, lambda x: float(x / 1000)),
            # (ATTR_CURRENT, 158, 4, True, lambda x: float(x / 1000)),
            # (ATTR_BATTERY_LEVEL, 173, 1, False, lambda x: x),
            # (ATTR_CYCLE_CHRG, 174, 4, False, lambda x: float(x / 1000)),
            # (ATTR_CYCLES, 182, 4, False, lambda x: x),
        ]  # Protocol Seplos V3

    @staticmethod
    def matcher_dict_list() -> list[dict[str, Any]]:
        """Provide BluetoothMatcher definition."""
        return [
            {
                "local_name": "SP0*",
                "service_uuid": UUID_SERVICE,
                "connectable": True,
            },
        ]

    @staticmethod
    def device_info() -> dict[str, str]:
        """Return device information for the battery management system."""
        return {"manufacturer": "Seplos", "model": "Smart BMS V3"}

    async def _wait_event(self) -> None:
        """Wait for data event and clear it."""
        await self._data_event.wait()
        self._data_event.clear()

    def _on_disconnect(self, client: BleakClient) -> None:
        """Disconnect callback function."""

        LOGGER.debug("Disconnected from BMS (%s)", self._ble_device.name)
        self._connected = False

    def _notification_handler(self, sender, data: bytearray) -> None:
        """Retrieve BMS data update."""

        LOGGER.debug(
            "(%s) Rx BLE data: %s",
            self._ble_device.name,
            data,
        )

        self._data_event.set()

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
            char_notify_handle: int | None = None
            self._char_write_handle = None
            for service in self._client.services:
                for char in service.characteristics:
                    LOGGER.debug(
                        "(%s) Discovered service %s,\n\t char %s (#%i): %s",
                        self._ble_device.name,
                        service.uuid,
                        char.uuid,
                        char.handle,
                        char.properties,
                    )
                    if char.uuid == UUID_CHAR:
                        if "notify" in char.properties or "indicate" in char.properties:
                            char_notify_handle = char.handle
                        if (
                            "write" in char.properties
                            or "write-without-response" in char.properties
                        ):
                            self._char_write_handle = char.handle
            if char_notify_handle is None:
                LOGGER.debug(
                    "(%s) Failed to detect characteristics", self._ble_device.name
                )
                await self._client.disconnect()
                return
            LOGGER.debug(
                "(%s) Using characteristics handle #%i (notify), #%i (write)",
                self._ble_device.name,
                char_notify_handle,
                self._char_write_handle or 0,
            )
            await self._client.start_notify(
                char_notify_handle or 0, self._notification_handler
            )

            self._connected = True
        else:
            LOGGER.debug("BMS %s already connected", self._ble_device.name)

    async def disconnect(self) -> None:
        """Disconnect the BMS and includes stoping notifications."""

        if self._client and self._connected:
            LOGGER.debug("Disconnecting BMS (%s)", self._ble_device.name)
            try:
                self._data_event.clear()
                await self._client.disconnect()
            except BleakError:
                LOGGER.warning("Disconnect failed!")

        self._client = None

    # def _crc(self, frame: bytes):
    #     """Calculate Seplos V3 frame CRC."""
    #     return sum(frame) & 0xFF

    # def _cmd(self, cmd: bytes, value: list[int] | None = None) -> bytes:
    #     """Assemble a Seplos V3 BMS command."""
    #     if value is None:
    #         value = []
    #     assert len(value) <= 13
    #     frame = bytes([*self.HEAD_CMD, cmd[0]])
    #     frame += bytes([len(value), *value])
    #     frame += bytes([0] * (13 - len(value)))
    #     frame += bytes([self._crc(frame)])
    #     return frame

    async def async_update(self) -> dict[str, int | float | bool]:
        """Update battery status information."""
        await self._connect()
        assert self._client is not None
        if not self._connected:
            LOGGER.debug(
                "Update request, but device (%s) not connected", self._ble_device.name
            )
            return {}

        # self.calc_values(
        #     data, {ATTR_POWER, ATTR_BATTERY_CHARGING, ATTR_CYCLE_CAP, ATTR_RUNTIME}
        # )

        if self._reconnect:
            # disconnect after data update to force reconnect next time (slow!)
            await self.disconnect()

        return {}
