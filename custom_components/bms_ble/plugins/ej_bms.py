"""Module to support Dummy BMS."""

import asyncio
from enum import Enum
import logging
from typing import Any, Callable, Final

from bleak.backends.device import BLEDevice

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
    KEY_CELL_VOLTAGE,
)

from .basebms import BaseBMS, BMSsample

LOGGER = logging.getLogger(__name__)
BAT_TIMEOUT = 10


class Cmd(Enum):
    """BMS operation codes."""

    RT = 0x2
    CAP = 0x10


class BMS(BaseBMS):
    """Dummy battery class implementation."""

    _MAX_CELLS: Final[int] = 16
    _FIELDS: Final[list[tuple[str, Cmd, int, int, Callable[[int], int | float]]]] = [
        (ATTR_CURRENT, Cmd.RT, 89, 8, lambda x: float((x >> 16) - (x & 0xFFFF)) / 100),
        (ATTR_BATTERY_LEVEL, Cmd.RT, 123, 2, lambda x: x),
        (ATTR_CYCLE_CHRG, Cmd.CAP, 15, 4, lambda x: float(x) / 10),
        (ATTR_TEMPERATURE, Cmd.RT, 97, 2, lambda x: x - 40),  # only 1st sensor relevant
        (ATTR_CYCLES, Cmd.RT, 115, 4, lambda x: x),
    ]

    def __init__(self, ble_device: BLEDevice, reconnect: bool = False) -> None:
        """Initialize BMS."""
        LOGGER.debug("%s init(), BT address: %s", self.device_id(), ble_device.address)
        super().__init__(LOGGER, self._notification_handler, ble_device, reconnect)
        self._data = bytearray()

    @staticmethod
    def matcher_dict_list() -> list[dict[str, Any]]:
        """Provide BluetoothMatcher definition."""
        return [ # Fliteboard, Electronix battery
            {"local_name": "libatt*", "manufacturer_id": 21320, "connectable": True},
            {"local_name": "LT-*", "manufacturer_id": 33384, "connectable": True},
        ]

    @staticmethod
    def device_info() -> dict[str, str]:
        """Return device information for the battery management system."""
        return {"manufacturer": "E&J Technology", "model": "Smart BMS"}

    @staticmethod
    def uuid_services() -> list[str]:
        """Return list of 128-bit UUIDs of services required by BMS."""
        return ["6e400001-b5a3-f393-e0a9-e50e24dcca9e"]

    @staticmethod
    def uuid_rx() -> str:
        """Return 128-bit UUID of characteristic that provides notification/read property."""
        return "6e400003-b5a3-f393-e0a9-e50e24dcca9e"

    @staticmethod
    def uuid_tx() -> str:
        """Return 127-bit UUID of characteristic that provides write property."""
        return "6e400002-b5a3-f393-e0a9-e50e24dcca9e"

    @staticmethod
    def _calc_values() -> set[str]:
        return {
            ATTR_BATTERY_CHARGING,
            ATTR_CYCLE_CAP,
            ATTR_DELTA_VOLTAGE,
            ATTR_POWER,
            ATTR_RUNTIME,
            ATTR_VOLTAGE,
        }  # calculate further values from BMS provided set ones

    def _notification_handler(self, _sender, data: bytearray) -> None:
        """Handle the RX characteristics notify event (new data arrives)."""
        LOGGER.debug("%s: Received BLE data: %s", self.name, data)

        if data[0] != 0x3A or data[-1] != 0x7E:
            LOGGER.debug("%s: Incorrect SOI or EOI: %s", self.name, data)
            return

        if len(data) != int(data[7:11], 16):
            LOGGER.debug(
                "%s: Incorrect frame length %i != %i",
                self.name,
                len(data),
                int(data[7:11], 16),
            )
            return

        crc: Final = BMS._crc(data[1:-3])
        if crc != int(data[-3:-1], 16):
            LOGGER.debug(
                "%s: incorrect checksum 0x%X != 0x%X",
                self.name,
                int(data[-3:-1], 16),
                crc,
            )
            return

        LOGGER.debug(
            "%s: address: 0x%X, commnad 0x%X, version: 0x%X",
            self.name,
            int(data[1:3], 16),
            int(data[3:5], 16) & 0x7F,
            int(data[5:7], 16),
        )
        self._data = data
        self._data_event.set()

    @staticmethod
    def _crc(data: bytes) -> int:
        return (sum(data) ^ 0xFF) & 0xFF

    @staticmethod
    def _cell_voltages(data: bytearray) -> dict[str, float]:
        """Return cell voltages from status message."""
        return {
            f"{KEY_CELL_VOLTAGE}{idx}": int(data[25 + 4 * idx : 25 + 4 * idx + 4], 16)
            / 1000
            for idx in range(BMS._MAX_CELLS)
            if int(data[25 + 4 * idx : 25 + 4 * idx + 4], 16)
        }

    async def _async_update(self) -> BMSsample:
        """Update battery status information."""
        raw_data: dict[int, bytearray] = {}

        # query real-time information and capacity
        for cmd in [b":000250000E03~", b":001031000E05~"]:
            await self._client.write_gatt_char(BMS.uuid_tx(), data=cmd)
            await asyncio.wait_for(self._wait_event(), timeout=BAT_TIMEOUT)
            raw_data[int(cmd[3:5], 16) & 0x7F] = self._data.copy()

        return {
            key: func(int(raw_data[cmd.value][idx : idx + size], 16))
            for key, cmd, idx, size, func in BMS._FIELDS
        } | self._cell_voltages(raw_data[Cmd.RT.value])
