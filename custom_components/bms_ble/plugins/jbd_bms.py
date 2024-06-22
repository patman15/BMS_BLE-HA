"""Module to support JBD Smart BMS."""

import asyncio
from collections.abc import Callable
import logging
from statistics import fmean
from typing import Any

from bleak import BleakClient
from bleak.backends.device import BLEDevice
from bleak.exc import BleakError
from bleak.uuids import normalize_uuid_str

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

# setup UUIDs, e.g. for receive: '0000fff1-0000-1000-8000-00805f9b34fb'
UUID_RX = normalize_uuid_str("ff01")
UUID_TX = normalize_uuid_str("ff02")
UUID_SERVICE = normalize_uuid_str("ff00")


class BMS(BaseBMS):
    """JBD Smart BMS class implementation."""

    HEAD_RSP = bytes([0xDD])  # header for responses
    HEAD_CMD = bytes([0xDD, 0xA5])  # read header for commands

    INFO_LEN = 7  # minimum frame size

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
        self._FIELDS: list[tuple[str, int, int, bool, Callable[[int], int | float]]] = [
            ("numTemp", 26, 1, False, lambda x: x),
            (ATTR_VOLTAGE, 4, 2, False, lambda x: float(x / 100)),
            (ATTR_CURRENT, 6, 2, True, lambda x: float(x / 100)),
            (ATTR_BATTERY_LEVEL, 23, 1, False, lambda x: x),
            (ATTR_CYCLE_CHRG, 8, 2, False, lambda x: float(x / 100)),
            (ATTR_CYCLES, 12, 2, False, lambda x: x),
        ]  # general protocol v4

    @staticmethod
    def matcher_dict_list() -> list[dict[str, Any]]:
        """Provide BluetoothMatcher definition."""
        return [
            {
                "service_uuid": UUID_SERVICE,
                "connectable": True,
            },
        ]

    @staticmethod
    def device_info() -> dict[str, str]:
        """Return device information for the battery management system."""
        return {"manufacturer": "Jiabaida", "model": "Smart BMS"}

    async def _wait_event(self) -> None:
        await self._data_event.wait()
        self._data_event.clear()

    def _on_disconnect(self, client: BleakClient) -> None:
        """Disconnect callback function."""

        LOGGER.debug("Disconnected from BMS (%s)", self._ble_device.name)
        self._connected = False

    def _notification_handler(self, sender, data: bytearray) -> None:
        if self._data_event.is_set():
            return

        if (
            data[0 : len(self.HEAD_RSP)] == self.HEAD_RSP
            and (data[1] == 0x03)  # or data[1] == 0x04)
            and data[2] == 0x00
        ):
            self._data = data
        elif len(data) and self._data is not None:
            self._data += data

        LOGGER.debug(
            "(%s) Rx BLE data (%s): %s",
            self._ble_device.name,
            "start" if data == self._data else "cnt.",
            data,
        )

        # verify that data long enough and if answer is basic info (0x3)
        if (
            self._data is None
            or len(self._data) < self.INFO_LEN + self._data[3]
            or self._data[self.INFO_LEN + self._data[3] - 1] != 0x77
        ):
            return

        frame_end: int = self.INFO_LEN + self._data[3] - 1

        crc = self._crc(self._data[2 : frame_end - 2])
        if int.from_bytes(self._data[frame_end - 2 : frame_end], "big") != crc:
            LOGGER.debug(
                "(%s) Rx data CRC is invalid: %i != %i",
                self._ble_device.name,
                int.from_bytes(self._data[frame_end - 2 : frame_end], "big"),
                crc,
            )
            self._data_final = None  # reset invalid data
        else:
            self._data_final = self._data

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
            await self._client.start_notify(UUID_RX, self._notification_handler)
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

    def _crc(self, frame: bytes) -> int:
        """Calculate JBD frame CRC."""
        return 0x10000 - sum(frame)

    def _cmd(self, cmd: bytes) -> bytes:
        """Assemble a JBD BMS command."""
        frame = bytes([*self.HEAD_CMD, cmd[0], 0x00])
        frame += self._crc(frame[2:4]).to_bytes(2, "big")
        frame += bytes([0x77])
        return frame

    async def async_update(self) -> dict[str, int | float | bool]:
        """Update battery status information."""
        await self._connect()
        assert self._client is not None

        # query general info
        await self._client.write_gatt_char(UUID_TX, data=self._cmd(b"\x03"))

        await asyncio.wait_for(self._wait_event(), timeout=BAT_TIMEOUT)

        if self._data_final is None:
            return {}
        if len(self._data_final) != self.INFO_LEN + self._data_final[3]:
            LOGGER.debug(
                "(%s) Wrong data length (%i): %s",
                self._ble_device.name,
                len(self._data_final),
                self._data_final,
            )

        data = {
            key: func(
                int.from_bytes(
                    self._data_final[idx : idx + size], byteorder="big", signed=sign
                )
            )
            for key, idx, size, sign, func in self._FIELDS
        }

        # calculate average temperature
        if data["numTemp"]:
            data[ATTR_TEMPERATURE] = (
                fmean(
                    [
                        int.from_bytes(self._data_final[idx : idx + 2])
                        for idx in range(
                            27,
                            27 + int(data["numTemp"]) * 2,
                            2,
                        )
                    ]
                )
                - 2731
            ) / 10

        self.calc_values(
            data, {ATTR_POWER, ATTR_BATTERY_CHARGING, ATTR_CYCLE_CAP, ATTR_RUNTIME}
        )

        if self._reconnect:
            # disconnect after data update to force reconnect next time (slow!)
            await self.disconnect()

        return data
