"""Module to support Jikong Smart BMS."""

import asyncio
from collections.abc import Callable
import logging
from typing import Any, Final

from bleak.backends.device import BLEDevice
from bleak.uuids import normalize_uuid_str
from custom_components.bms_ble.const import (
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
    KEY_CELL_COUNT,
    KEY_CELL_VOLTAGE,
    KEY_TEMP_VALUE,
)

from custom_components.bms_ble.plugins.basebms import BaseBMS, BMSsample

BAT_TIMEOUT: Final = 10
LOGGER: Final = logging.getLogger(__name__)


class BMS(BaseBMS):
    """Jikong Smart BMS class implementation."""

    HEAD_RSP: Final = bytes([0x55, 0xAA, 0xEB, 0x90])  # header for responses
    HEAD_CMD: Final = bytes([0xAA, 0x55, 0x90, 0xEB])  # header for commands (endiness!)
    BT_MODULE_MSG: Final = bytes([0x41, 0x54, 0x0D, 0x0A])  # AT\r\n from BLE module
    INFO_LEN: Final = 300

    def __init__(self, ble_device: BLEDevice, reconnect: bool = False) -> None:
        """Intialize private BMS members."""
        super().__init__(LOGGER, self._notification_handler, ble_device, reconnect)
        self._data: bytearray = bytearray()
        self._data_final: bytearray | None = None
        self._char_write_handle: int | None = None
        self._FIELDS: Final[
            list[tuple[str, int, int, bool, Callable[[int], int | float]]]
        ] = [  # Protocol: JK02_32S; JK02_24S has offset -32
            (KEY_CELL_COUNT, 70, 4, False, lambda x: x.bit_count()),
            (ATTR_DELTA_VOLTAGE, 76, 2, False, lambda x: float(x / 1000)),
            (ATTR_VOLTAGE, 150, 4, False, lambda x: float(x / 1000)),
            (ATTR_CURRENT, 158, 4, True, lambda x: float(x / 1000)),
            (ATTR_BATTERY_LEVEL, 173, 1, False, lambda x: x),
            (ATTR_CYCLE_CHRG, 174, 4, False, lambda x: float(x / 1000)),
            (ATTR_CYCLES, 182, 4, False, lambda x: x),
        ] + [  # add temperature sensors
            (f"{KEY_TEMP_VALUE}{i}", addr, 2, True, lambda x: float(x / 10))
            for i, addr in [(0, 144), (1, 162), (2, 164), (3, 256), (4, 258)]
        ]

    @staticmethod
    def matcher_dict_list() -> list[dict[str, Any]]:
        """Provide BluetoothMatcher definition."""
        return [
            {
                "service_uuid": BMS.uuid_services()[0],
                "connectable": True,
                "manufacturer_id": 0x0B65,
            },
        ]

    @staticmethod
    def device_info() -> dict[str, str]:
        """Return device information for the battery management system."""
        return {"manufacturer": "Jikong", "model": "Smart BMS"}

    @staticmethod
    def uuid_services() -> list[str]:
        """Return list of 128-bit UUIDs of services required by BMS"""
        return [normalize_uuid_str("ffe0")]

    @staticmethod
    def uuid_rx() -> str:
        """Return 16-bit UUID of characteristic that provides notification/read property."""
        return "ffe1"

    @staticmethod
    def uuid_tx() -> str:
        """Return 16-bit UUID of characteristic that provides write property."""
        return "ffe1"

    @staticmethod
    def _calc_values() -> set[str]:
        return {
            ATTR_POWER,
            ATTR_BATTERY_CHARGING,
            ATTR_CYCLE_CAP,
            ATTR_RUNTIME,
            ATTR_TEMPERATURE,
        }

    def _notification_handler(self, _sender, data: bytearray) -> None:
        """Retrieve BMS data update."""

        if data[0 : len(self.BT_MODULE_MSG)] == self.BT_MODULE_MSG:
            LOGGER.debug("(%s) filtering AT cmd", self._ble_device.name)
            if len(data) == len(self.BT_MODULE_MSG):
                return
            data = data[len(self.BT_MODULE_MSG) :]

        if data[0 : len(self.HEAD_RSP)] == self.HEAD_RSP:
            self._data = bytearray()

        self._data += data

        LOGGER.debug(
            "(%s) Rx BLE data (%s): %s",
            self._ble_device.name,
            "start" if data == self._data else "cnt.",
            data,
        )

        # verify that data long enough and if answer is cell info (0x2)
        if len(self._data) < self.INFO_LEN or self._data[4] != 0x2:
            return

        crc = self._crc(self._data[0 : self.INFO_LEN - 1])
        if self._data[self.INFO_LEN - 1] != crc:
            LOGGER.debug(
                "(%s) Rx data CRC is invalid: %i != %i",
                self._ble_device.name,
                self._data[self.INFO_LEN - 1],
                self._crc(self._data[0 : self.INFO_LEN - 1]),
            )
            self._data_final = None  # reset invalid data
        else:
            self._data_final = self._data

        self._data_event.set()

    async def _init_characteristics(self) -> None:
        """initialize RX/TX characteristics"""
        char_notify_handle: int | None = None
        self._char_write_handle = None
        for service in self._client.services:
            for char in service.characteristics:
                LOGGER.debug(
                    "(%s) Discovered %s (#%i): %s",
                    self._ble_device.name,
                    char.uuid,
                    char.handle,
                    char.properties,
                )
                if char.uuid == normalize_uuid_str(
                    BMS.uuid_rx()
                ) or char.uuid == normalize_uuid_str(BMS.uuid_tx()):
                    if "notify" in char.properties:
                        char_notify_handle = char.handle
                    if (
                        "write" in char.properties
                        or "write-without-response" in char.properties
                    ):
                        self._char_write_handle = char.handle
        if char_notify_handle is None or self._char_write_handle is None:
            LOGGER.debug("(%s) Failed to detect characteristics", self._ble_device.name)
            await self._client.disconnect()
            raise ConnectionError(
                f"Failed to detect characteristics from {self._ble_device.name}."
            )
        LOGGER.debug(
            "(%s) Using characteristics handle #%i (notify), #%i (write)",
            self._ble_device.name,
            char_notify_handle,
            self._char_write_handle,
        )
        await self._client.start_notify(
            char_notify_handle or 0, self._notification_handler
        )

        # query device info
        await self._client.write_gatt_char(
            self._char_write_handle or 0, data=self._cmd(b"\x97")
        )

    def _crc(self, frame: bytes) -> int:
        """Calculate Jikong frame CRC."""
        return sum(frame) & 0xFF

    def _cmd(self, cmd: bytes, value: list[int] | None = None) -> bytes:
        """Assemble a Jikong BMS command."""
        value = [] if value is None else value
        assert len(value) <= 13
        frame = bytes([*self.HEAD_CMD, cmd[0]])
        frame += bytes([len(value), *value])
        frame += bytes([0] * (13 - len(value)))
        frame += bytes([self._crc(frame)])
        return frame

    def _cell_voltages(self, data: bytearray, cells: int) -> dict[str, float]:
        """Return cell voltages from status message."""
        return {
            f"{KEY_CELL_VOLTAGE}{idx}": int.from_bytes(
                data[6 + 2 * idx : 6 + 2 * idx + 2],
                byteorder="little",
                signed=True,
            )
            / 1000
            for idx in range(cells)
        }

    def _decode_data(self, data: bytearray) -> BMSsample:
        """Return BMS data from status message."""
        return {
            key: func(
                int.from_bytes(data[idx : idx + size], byteorder="little", signed=sign)
            )
            for key, idx, size, sign, func in self._FIELDS
        }

    async def _async_update(self) -> BMSsample:
        """Update battery status information."""
        if not self._data_event.is_set():
            # request cell info (only if data is not constantly published)
            LOGGER.debug("(%s) request cell info", self._ble_device.name)
            await self._client.write_gatt_char(
                self._char_write_handle or 0, data=self._cmd(b"\x96")
            )

        await asyncio.wait_for(self._wait_event(), timeout=BAT_TIMEOUT)

        if self._data_final is None:
            return {}
        if len(self._data_final) != self.INFO_LEN:
            LOGGER.debug(
                "(%s) Wrong data length (%i): %s",
                self._ble_device.name,
                len(self._data_final),
                self._data_final,
            )

        data = self._decode_data(self._data_final)
        data.update(self._cell_voltages(self._data_final, int(data[KEY_CELL_COUNT])))

        return data
