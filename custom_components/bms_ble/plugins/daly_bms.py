"""Module to support Daly Smart BMS."""

import asyncio
from collections.abc import Callable
import logging
from statistics import fmean
from typing import Any

from bleak import BleakClient, BleakError, normalize_uuid_str
from bleak.backends.device import BLEDevice

from ..const import (
    ATTR_BATTERY_CHARGING,
    ATTR_BATTERY_LEVEL,
    ATTR_CURRENT,
    ATTR_CYCLE_CAP,
    ATTR_CYCLE_CHRG,
    ATTR_CYCLES,
    ATTR_POWER,
    ATTR_RUNTIME,
    ATTR_TEMPERATURE,
    ATTR_VOLTAGE,
)
from .basebms import BaseBMS

BAT_TIMEOUT = 10
LOGGER = logging.getLogger(__name__)


class BMS(BaseBMS):
    """Daly Smart BMS class implementation."""

    # setup UUIDs, e.g. for receive: '0000fff1-0000-1000-8000-00805f9b34fb'
    UUID_RX = normalize_uuid_str("fff1")
    UUID_TX = normalize_uuid_str("fff2")
    UUID_SERVICE = normalize_uuid_str("FFF0")
    HEAD_READ = bytearray(b"\xD2\x03")
    CMD_INFO = bytearray(b"\x00\x00\x00\x3E\xD7\xB9")
    HEAD_LEN = 3
    CRC_LEN = 2
    INFO_LEN = 124 + HEAD_LEN + CRC_LEN

    def __init__(self, ble_device: BLEDevice, reconnect: bool = False) -> None:
        """Intialize private BMS members."""
        self._reconnect = reconnect
        self._ble_device = ble_device
        assert self._ble_device.name is not None
        self._client: BleakClient | None = None
        self._data: bytearray | None = None
        self._data_event = asyncio.Event()
        self._connected = False  # flag to indicate active BLE connection
        self._FIELDS: list[tuple[str, int, Callable[[int], int | float]]] = [
            (ATTR_VOLTAGE, 80 + self.HEAD_LEN, lambda x: float(x / 10)),
            (ATTR_CURRENT, 82 + self.HEAD_LEN, lambda x: float((x - 30000) / 10)),
            (ATTR_BATTERY_LEVEL, 84 + self.HEAD_LEN, lambda x: float(x / 10)),
            (
                ATTR_CYCLES,
                102 + self.HEAD_LEN,
                lambda x: int(x),  # pylint: disable=unnecessary-lambda
            ),
            (ATTR_CYCLE_CHRG, 96 + self.HEAD_LEN, lambda x: float(x / 10)),
            (
                "numTemp",
                100 + self.HEAD_LEN,
                lambda x: int(x),  # pylint: disable=unnecessary-lambda
            ),
        ]

    @staticmethod
    def matcher_dict_list() -> list[dict[str, Any]]:
        """Provide BluetoothMatcher definition."""
        return [{"local_name": "DL-*", "connectable": True}]

    @staticmethod
    def device_info() -> dict[str, str]:
        """Return device information for the battery management system."""
        return {"manufacturer": "Daly", "model": "Smart BMS"}

    async def _wait_event(self) -> None:
        await self._data_event.wait()
        self._data_event.clear()

    def _on_disconnect(self, client: BleakClient) -> None:
        """Disconnect callback function."""

        LOGGER.debug("Disconnected from BMS (%s)", client.address)
        self._connected = False

    def _notification_handler(self, sender, data: bytearray) -> None:
        LOGGER.debug("Received BLE data: %s", data)
        # note: CRC is not checked
        if (
            len(data) < 3
            or data[0:2] != self.HEAD_READ
            or int(data[2]) + 1 != len(data) - len(self.HEAD_READ) - self.CRC_LEN
        ):
            LOGGER.debug("Response data is invalid")
            self._data = None
            return

        self._data = data
        self._data_event.set()

    async def _connect(self) -> None:
        """Connect to the BMS and setup notification if not connected."""

        if not self._connected:
            LOGGER.debug("Connecting BMS %s", self._ble_device.name)
            self._client = BleakClient(
                self._ble_device.address,
                disconnected_callback=self._on_disconnect,
                services=[self.UUID_SERVICE],
            )
            await self._client.connect()
            await self._client.start_notify(self.UUID_RX, self._notification_handler)
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

    async def async_update(self) -> dict[str, int | float | bool]:
        """Update battery status information."""
        await self._connect()
        assert self._client is not None

        await self._client.write_gatt_char(
            self.UUID_TX, data=self.HEAD_READ + self.CMD_INFO
        )

        await asyncio.wait_for(self._wait_event(), timeout=BAT_TIMEOUT)

        if self._data is None or len(self._data) != self.INFO_LEN:
            return {}

        data = {
            key: func(int.from_bytes(self._data[idx : idx + 2]))
            for key, idx, func in self._FIELDS
        }

        # calculate average temperature
        if data["numTemp"] > 0:
            data[ATTR_TEMPERATURE] = (
                fmean(
                    [
                        int.from_bytes(self._data[idx : idx + 2])
                        for idx in range(
                            64 + self.HEAD_LEN,
                            64 + self.HEAD_LEN + int(data["numTemp"]) * 2,
                            2,
                        )
                    ]
                )
                - 40
            )

        self.calc_values(
            data, {ATTR_CYCLE_CAP, ATTR_POWER, ATTR_BATTERY_CHARGING, ATTR_RUNTIME}
        )

        return data
