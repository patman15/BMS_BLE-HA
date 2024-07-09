"""Module to support Seplos V3 Smart BMS."""

import asyncio
from collections.abc import Callable
import logging
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
    ATTR_DELTA_VOLTAGE,
    ATTR_POWER,
    ATTR_RUNTIME,
    ATTR_TEMPERATURE,
    ATTR_VOLTAGE,
)
from .basebms import BaseBMS

BAT_TIMEOUT = 10
LOGGER = logging.getLogger(__name__)

# setup UUIDs
#    serv 0000fff0-0000-1000-8000-00805f9b34fb
# 	 char 0000fff1-0000-1000-8000-00805f9b34fb (#16): ['read', 'notify']
# 	 char 0000fff2-0000-1000-8000-00805f9b34fb (#20): ['read', 'write-without-response', 'write']
UUID_SERVICE = normalize_uuid_str("fff0")
UUID_RX = normalize_uuid_str("fff1")
UUID_TX = normalize_uuid_str("fff2")


class BMS(BaseBMS):
    """Seplos V3 Smart BMS class implementation."""

    CMD_READ: int = 0x04
    DEV: list[int] = [0x00]  # valid devices
    HEAD_LEN: int = 3
    CRC_LEN: int = 2
    EIA_LEN = 0x1A
    EIB_LEN = 0x16
    QUERY: dict[str, tuple[int, int, int, int]] = {
        "EIA": (0, 0x4, 0x2000, EIA_LEN),
        "EIB": (0, 0x4, 0x2100, EIB_LEN),
    }

    def __init__(self, ble_device: BLEDevice, reconnect: bool = False) -> None:
        """Intialize private BMS members."""
        self._reconnect = reconnect
        self._ble_device = ble_device
        assert self._ble_device.name is not None
        self._client: BleakClient | None = None
        self._data: bytearray | None = None
        self._exp_len: int = 0
        self._data_final: dict[int, bytearray] = {}
        self._data_event = asyncio.Event()
        self._connected = False  # flag to indicate active BLE connection
        self._char_write_handle: int | None = None
        self._FIELDS: list[
            tuple[str, int, int, int, bool, Callable[[int], int | float]]
        ] = [
            (
                ATTR_DELTA_VOLTAGE,
                self.EIB_LEN,
                0,
                4,
                False,
                lambda x: float((((x >> 16) & 0xFFFF) - (x & 0xFFFF)) / 1E3),
            ),
            (ATTR_TEMPERATURE, self.EIB_LEN, 20, 2, False, lambda x: float(x / 10)),
            (
                ATTR_VOLTAGE,
                self.EIA_LEN,
                0,
                4,
                False,
                lambda x: float(self._swap32(x) / 100),
            ),
            (
                ATTR_CURRENT,
                self.EIA_LEN,
                4,
                4,
                False,
                lambda x: float((self._swap32(x, True)) / 10),
            ),
            (
                ATTR_CYCLE_CHRG,
                self.EIA_LEN,
                8,
                4,
                False,
                lambda x: float(self._swap32(x) / 100),
            ),
            (ATTR_BATTERY_LEVEL, self.EIA_LEN, 48, 2, False, lambda x: float(x / 10)),
            (ATTR_CYCLES, self.EIA_LEN, 46, 2, False, lambda x: x),
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

        if (
            len(data) > self.HEAD_LEN + self.CRC_LEN
            and data[1] & 0x7F == self.CMD_READ  # include read errors
            and data[0] in self.DEV
            and data[2] >= self.HEAD_LEN + self.CRC_LEN
        ):
            self._data = data
            self._exp_len = (
                data[2] + self.HEAD_LEN + self.CRC_LEN
            )  # expected packet length
            if data[1] & 0x80:
                LOGGER.debug(
                    "(%s) Rx BLE error: %x", self._ble_device.name, int(data[1])
                )
        elif len(data) and self._data is not None:
            self._data += data

        LOGGER.debug(
            "(%s) Rx BLE data (%s): %s",
            self._ble_device.name,
            "start" if data == self._data else "cnt.",
            data,
        )

        # verify that data long enough
        if self._data is None or len(self._data) < self._exp_len:
            return

        crc = self._crc16(self._data[: self._exp_len - 2])
        if int.from_bytes(self._data[self._exp_len - 2 : self._exp_len]) != crc:
            LOGGER.debug(
                "(%s) Rx data CRC is invalid: %i != %i",
                self._ble_device.name,
                int.from_bytes(self._data[self._exp_len - 2 :]),
                crc,
            )
            self._data_final[int(self._data[0])] = bytearray()  # reset invalid data
        elif not (
            self._data[2] == self.EIA_LEN * 2 or self._data[2] == self.EIB_LEN * 2
        ):
            LOGGER.debug(
                "(%s) unknown message: %s", self._ble_device.name, self._data[0:3]
            )
            return
        else:
            self._data_final[int(self._data[2])] = self._data
            if len(self._data) != self._exp_len:
                LOGGER.debug(
                    "(%s) Wrong data length (%i!=%s): %s",
                    self._ble_device.name,
                    len(self._data_final),
                    self._exp_len,
                    self._data_final,
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

    def _swap32(self, value: int, signed: bool = False) -> int:
        """Swap high and low 16bit in 32bit integer."""

        value = ((value >> 16) & 0xFFFF) | (value & 0xFFFF) << 16
        if signed and value & 0x80000000:
            value = -0x100000000 + value
        return value

    def _crc16(self, data: bytearray) -> int:
        """Calculate CRC-16-CCITT XMODEM (ModBus)."""

        crc: int = 0xFFFF
        for i in data:
            crc ^= i & 0xFF
            for _ in range(8):
                crc = (crc >> 1) ^ 0xA001 if crc % 2 else (crc >> 1)
        return ((0xFF00 & crc) >> 8) | ((crc & 0xFF) << 8)

    def _cmd(self, device: int, cmd: int, start: int, count: int) -> bytearray:
        """Assemble a Seplos BMS command."""
        assert device >= 0x00 and (device <= 0x10 or device == 0xC0 or device == 0xE0)
        assert cmd in (0x01, 0x04)  # allow only read commands
        assert start >= 0 and count > 0 and start + count <= 0xFFFF
        frame = bytearray([device, cmd])
        frame += bytearray(int.to_bytes(start, 2, byteorder="big"))
        frame += bytearray(int.to_bytes(count, 2, byteorder="big"))
        frame += bytearray(int.to_bytes(self._crc16(frame), 2, byteorder="big"))
        return frame

    async def async_update(self) -> dict[str, int | float | bool]:
        """Update battery status information."""

        await self._connect()
        assert self._client is not None
        if not self._connected:
            LOGGER.debug(
                "Update request, but device (%s) not connected", self._ble_device.name
            )
            return {}

        await self._client.write_gatt_char(UUID_TX, data=self._cmd(*self.QUERY["EIA"]))
        await asyncio.wait_for(self._wait_event(), timeout=BAT_TIMEOUT)

        await self._client.write_gatt_char(UUID_TX, data=self._cmd(*self.QUERY["EIB"]))
        await asyncio.wait_for(self._wait_event(), timeout=BAT_TIMEOUT)

        LOGGER.debug(f"{self._data_final=}")

        if not (
            self.EIA_LEN * 2 in self._data_final
            and self.EIB_LEN * 2 in self._data_final
        ):
            return {}

        data = {
            key: func(
                int.from_bytes(
                    self._data_final[msg * 2][
                        self.HEAD_LEN + idx : self.HEAD_LEN + idx + size
                    ],
                    byteorder="big",
                    signed=sign,
                )
            )
            for key, msg, idx, size, sign, func in self._FIELDS
        }

        # get cell voltages
        # if len(self._data_final[self.PART[2]]):
        #     data.update(
        #         {
        #             f"{KEY_CELL_VOLTAGE}{idx}": float(
        #                 int.from_bytes(
        #                     self._data_final[self.PART[2]][
        #                         self.HEAD_LEN + 2 * idx : self.HEAD_LEN + 2 * idx + 2
        #                     ],
        #                     byteorder="big",
        #                     signed=False,
        #                 )
        #                 / 1000
        #             )
        #             for idx in range(16)
        #         }
        #     )

        self.calc_values(
            data, {ATTR_POWER, ATTR_BATTERY_CHARGING, ATTR_CYCLE_CAP, ATTR_RUNTIME}
        )

        self._data_final.clear()

        if self._reconnect:
            # disconnect after data update to force reconnect next time (slow!)
            await self.disconnect()

        return data
