"""Module to support D-powercore Smart BMS."""

import asyncio
from collections.abc import Callable
from enum import Enum
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
)
from custom_components.bms_ble.plugins.basebms import BaseBMS, BMSsample

BAT_TIMEOUT: Final = 10
LOGGER: Final = logging.getLogger(__name__)


class Cmd(Enum):
    """BMS operation codes."""

    UNLOCKACC = 0x32
    UNLOCKREJ = 0x33
    LEGINFO1 = 0x60
    LEGINFO2 = 0x61
    CELLVOLT = 0x62
    UNLOCK = 0x64
    UNLOCKED = 0x65
    GETINFO = 0xA0


class BMS(BaseBMS):
    """D-powercore Smart BMS class implementation."""

    # setup UUIDs, e.g. for receive: '0000fff0-0000-1000-8000-00805f9b34fb'
    _UUID_RX = normalize_uuid_str("fff4")
    _UUID_TX = normalize_uuid_str("fff3")
    _UUID_SERVICE = normalize_uuid_str("fff0")
    PAGE_LEN: Final = 20
    MAX_CELLS: Final = 64  # TODO: remove?

    def __init__(self, ble_device: BLEDevice, reconnect: bool = False) -> None:
        """Intialize private BMS members."""
        super().__init__(LOGGER, self._notification_handler, ble_device, reconnect)
        assert self._ble_device.name is not None  # required for unlock
        self._data: bytearray = bytearray()
        self._data_final: bytearray | None = None
        self._FIELDS: Final[
            list[tuple[str, Cmd, int, int, Callable[[int], int | float]]]
        ] = [
            (ATTR_VOLTAGE, Cmd.LEGINFO1, 6, 2, lambda x: float(x) / 10),
            (ATTR_CURRENT, Cmd.LEGINFO1, 8, 2, lambda x: x),
            (ATTR_BATTERY_LEVEL, Cmd.LEGINFO1, 14, 1, lambda x: x),
            (ATTR_CYCLE_CHRG, Cmd.LEGINFO1, 12, 2, lambda x: float(x) / 1000),
            (
                ATTR_TEMPERATURE,
                Cmd.LEGINFO2,
                12,
                2,
                lambda x: round(float(x) * 0.1 - 273.15, 1),
            ),
            (KEY_CELL_COUNT, Cmd.CELLVOLT, 6, 1, lambda x: min(x, self.MAX_CELLS)),
            (ATTR_CYCLES, Cmd.LEGINFO2, 8, 2, lambda x: x),
        ]

    @staticmethod
    def matcher_dict_list() -> list[dict[str, Any]]:
        """Provide BluetoothMatcher definition."""
        return [
            {"local_name": "DXB-*", "service_uuid": BMS._UUID_SERVICE, "connectable": True},
            {"local_name": "TBA-*", "service_uuid": BMS._UUID_SERVICE, "connectable": True},
        ]

    @staticmethod
    def device_info() -> dict[str, str]:
        """Return device information for the battery management system."""
        return {"manufacturer": "D-powercore", "model": "Smart BMS"}

    async def _notification_handler(self, _sender, data: bytearray) -> None:
        LOGGER.debug("%s: Received BLE data: %s", self.name, data)

        if len(data) != self.PAGE_LEN:
            LOGGER.debug("%s: Invalid page length (%i)", self.name, len(data))
            return

        # ignore ACK responses
        if data[0] & 0x80:
            LOGGER.debug("%s: Ignore acknowledge message", self.name)
            return

        await self._client.write_gatt_char(  # acknowledge received frame
            BMS._UUID_TX, bytearray([data[0] | 0x80]) + data[1:]
        )

        size: Final[int] = int(data[0])
        page: Final[int] = int(data[1] >> 4)
        maxpg: Final[int] = int(data[1] & 0xF)

        if page == 1:
            self._data = bytearray()

        self._data += data[2 : size + 2]

        LOGGER.debug("%s: %s %s", self.name, "start" if page == 1 else "cnt.", data)

        if page == maxpg:
            LOGGER.debug(
                "%s: checksum 0x%X",
                self.name,
                int.from_bytes(self._data[-4:-2], byteorder="big"),
            )
            if int.from_bytes(self._data[-4:-2], byteorder="big") != self._crc(
                self._data[3:-4]
            ):
                LOGGER.debug(
                    "%s: incorrect checksum 0x%X != 0x%X",
                    self.name,
                    int.from_bytes(self._data[-4:-2], byteorder="big"),
                    self._crc(self._data[3:-4]),
                )
                self._data = bytearray()
                self._data_final = None  # reset invalid data
                self._data_event.set()
                return
            self._data_final = self._data
            self._data_event.set()

    def _crc(self, data: bytes) -> int:
        return sum(data) + 8

    def _cmd_frame(self, cmd: Cmd, data: bytes) -> bytes:

        frame = bytes([cmd.value, 0x00, 0x00]) + data
        checksum = self._crc(frame)
        frame = (
            bytes([0x3A, 0x03, 0x05])
            + frame
            + bytes([(checksum >> 8) & 0xFF, checksum & 0xFF, 0x0D, 0x0A])
        )
        frame = bytes([len(frame) + 2, 0x11]) + frame
        frame += bytes(self.PAGE_LEN - len(frame))

        LOGGER.debug("%s: sending cmd: %s", self.name, frame)
        return frame

    async def _init_characteristics(self) -> None:
        """Connect to the BMS and setup notification if not connected."""
        await super()._init_characteristics()

        # unlock BMS if not TBA version
        if not self.name.startswith("TBA-"):
            pwd = int(self.name[-4:], 16)
            await self._client.write_gatt_char(
                BMS._UUID_TX,
                self._cmd_frame(Cmd.UNLOCK, bytes([(pwd >> 8) & 0xFF, pwd & 0xFF])),
            )

    def _cell_voltages(self, data: bytearray, cells: int) -> dict[str, float]:
        """Return cell voltages from status message."""
        return {
            f"{KEY_CELL_VOLTAGE}{idx}": int.from_bytes(
                data[7 + 2 * idx : 7 + 2 * idx + 2], byteorder="big"
            )
            / 1000
            for idx in range(cells)
        }

    async def _async_update(self) -> BMSsample:
        """Update battery status information."""
        await self._connect()

        data = {}
        for request in [Cmd.LEGINFO1, Cmd.LEGINFO2, Cmd.CELLVOLT]:
            await self._client.write_gatt_char(
                BMS._UUID_TX, self._cmd_frame(request, b"")
            )
            await asyncio.wait_for(self._wait_event(), timeout=BAT_TIMEOUT)

            if self._data_final is None:
                continue

            data |= {
                key: func(
                    int.from_bytes(
                        self._data[idx : idx + size], byteorder="big", signed=True
                    )
                )
                for key, cmd, idx, size, func in self._FIELDS
                if cmd == request
            }
            if request == Cmd.CELLVOLT and data.get(KEY_CELL_COUNT):
                data.update(
                    self._cell_voltages(self._data_final, int(data[KEY_CELL_COUNT]))
                )

        self.calc_values(
            data,
            {
                ATTR_BATTERY_CHARGING,
                ATTR_CYCLE_CAP,
                ATTR_DELTA_VOLTAGE,
                ATTR_POWER,
                ATTR_RUNTIME,
            },
        )

        return data
