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

from .basebms import BaseBMS, BMSsample, crc_sum

LOGGER: Final = logging.getLogger(__name__)


class BMS(BaseBMS):
    """Jikong Smart BMS class implementation."""

    HEAD_RSP: Final = bytes([0x55, 0xAA, 0xEB, 0x90])  # header for responses
    HEAD_CMD: Final = bytes([0xAA, 0x55, 0x90, 0xEB])  # header for commands (endiness!)
    BT_MODULE_MSG: Final = bytes([0x41, 0x54, 0x0D, 0x0A])  # AT\r\n from BLE module
    TYPE_POS: Final[int] = 4  # frame type is right after the header
    INFO_LEN: Final[int] = 300
    _FIELDS: Final[list[tuple[str, int, int, bool, Callable[[int], int | float]]]] = (
        [  # Protocol: JK02_32S; JK02_24S has offset -32
            (ATTR_VOLTAGE, 150, 4, False, lambda x: float(x / 1000)),
            (ATTR_CURRENT, 158, 4, True, lambda x: float(x / 1000)),
            (ATTR_BATTERY_LEVEL, 173, 1, False, lambda x: x),
            (ATTR_CYCLE_CHRG, 174, 4, False, lambda x: float(x / 1000)),
            (ATTR_CYCLES, 182, 4, False, lambda x: x),
        ]
    )

    def __init__(self, ble_device: BLEDevice, reconnect: bool = False) -> None:
        """Intialize private BMS members."""
        super().__init__(LOGGER, self._notification_handler, ble_device, reconnect)
        self._data: bytearray = bytearray()
        self._data_final: bytearray = bytearray()
        self._char_write_handle: int = -1
        self._bms_info: dict[str, str] = {}
        self._prot_offset: int = 0
        self._valid_reply: int = 0x02

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
        """Return list of 128-bit UUIDs of services required by BMS."""
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

        if data.startswith(BMS.BT_MODULE_MSG):
            LOGGER.debug("%s: filtering AT cmd", self.name)
            if len(data) == len(BMS.BT_MODULE_MSG):
                return
            data = data[len(BMS.BT_MODULE_MSG) :]

        if (
            len(self._data) >= self.INFO_LEN
            and (data.startswith((BMS.HEAD_RSP, self.HEAD_CMD)))
        ) or not self._data.startswith(BMS.HEAD_RSP):
            self._data = bytearray()

        self._data += data

        LOGGER.debug(
            "%s: RX BLE data (%s): %s",
            self.name,
            "start" if data == self._data else "cnt.",
            data,
        )

        # verify that data long enough
        if (
            len(self._data) < BMS.INFO_LEN and self._data.startswith(BMS.HEAD_RSP)
        ) or len(self._data) < BMS.TYPE_POS:
            return

        # check that message type is expected
        if self._data[BMS.TYPE_POS] != self._valid_reply:
            LOGGER.debug(
                "%s: unexpected message type 0x%X (length %i): %s",
                self.name,
                self._data[BMS.TYPE_POS],
                len(self._data),
                self._data,
            )
            return

        # trim message in case oversized
        if len(self._data) > BMS.INFO_LEN:
            LOGGER.debug(
                "%s: wrong data length (%i): %s",
                self.name,
                len(self._data),
                self._data,
            )
            self._data = self._data[: BMS.INFO_LEN]

        crc = crc_sum(self._data[:-1])
        if self._data[-1] != crc:
            LOGGER.debug(
                "%s: RX data CRC is invalid: 0x%X != 0x%X",
                self.name,
                self._data[-1],
                crc,
            )
            return

        self._data_final = self._data
        self._data_event.set()

    async def _init_characteristics(self) -> None:
        """Initialize RX/TX characteristics."""
        char_notify_handle: int = -1
        self._char_write_handle = -1

        for service in self._client.services:
            for char in service.characteristics:
                LOGGER.debug(
                    "%s: discovered %s (#%i): %s",
                    self.name,
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
        if char_notify_handle == -1 or self._char_write_handle == -1:
            LOGGER.debug("%s: Failed to detect characteristics.", self.name)
            await self._client.disconnect()
            raise ConnectionError(f"Failed to detect characteristics from {self.name}.")
        LOGGER.debug(
            "%s: Using characteristics handle #%i (notify), #%i (write).",
            self.name,
            char_notify_handle,
            self._char_write_handle,
        )
        await self._client.start_notify(char_notify_handle, self._notification_handler)

        # query device info frame (0x03) and wait for BMS ready (0xC8)
        self._valid_reply = 0x03
        await self._send(self._cmd(b"\x97"), char=self._char_write_handle)
        self._bms_info = BMS._dec_devinfo(self._data_final or bytearray())
        LOGGER.debug("%s: device information: %s", self.name, self._bms_info)
        self._prot_offset = (
            -32 if int(self._bms_info.get("sw_version", "")[:2]) < 11 else 0
        )
        self._valid_reply = 0xC8  # BMS ready confirmation
        await asyncio.wait_for(self._wait_event(), timeout=self.BAT_TIMEOUT)
        self._valid_reply = 0x02  # cell information

    @staticmethod
    def _cmd(cmd: bytes, value: list[int] | None = None) -> bytes:
        """Assemble a Jikong BMS command."""
        value = [] if value is None else value
        assert len(value) <= 13
        frame = bytes([*BMS.HEAD_CMD, cmd[0]])
        frame += bytes([len(value), *value])
        frame += bytes([0] * (13 - len(value)))
        frame += bytes([crc_sum(frame)])
        return frame

    @staticmethod
    def _dec_devinfo(data: bytearray) -> dict[str, str]:
        return {"hw_version": data[22:27].decode(), "sw_version": data[30:35].decode()}

    @staticmethod
    def _cell_voltages(data: bytearray, cells: int) -> dict[str, float]:
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

    @staticmethod
    def _temp_sensors(data: bytearray, offs: int) -> dict[str, float]:
        temp_pos: Final[list[tuple[int, int]]] = (
            [(0, 130), (1, 132), (2, 134)]
            if offs
            else [(0, 144), (1, 162), (2, 164), (3, 256), (4, 258)]
        )
        return {
            f"{KEY_TEMP_VALUE}{idx}": int.from_bytes(
                data[pos : pos + 2], byteorder="little", signed=False
            )
            / 10
            for idx, pos in temp_pos
            if int.from_bytes(data[pos : pos + 2], byteorder="little", signed=False)
        }

    @staticmethod
    def _decode_data(data: bytearray, offs: int) -> BMSsample:
        """Return BMS data from status message."""
        return (
            {
                KEY_CELL_COUNT: int.from_bytes(
                    data[70 + (offs >> 1) : 74 + (offs >> 1)],
                    byteorder="little",
                ).bit_count()
            }
            | {
                ATTR_DELTA_VOLTAGE: int.from_bytes(
                    data[76 + (offs >> 1) : 78 + (offs >> 1)],
                    byteorder="little",
                )
                / 1000
            }
            | {
                key: func(
                    int.from_bytes(
                        data[idx + offs : idx + offs + size],
                        byteorder="little",
                        signed=sign,
                    )
                )
                for key, idx, size, sign, func in BMS._FIELDS
            }
        )

    async def _async_update(self) -> BMSsample:
        """Update battery status information."""
        if not self._data_event.is_set() or self._data_final[4] != 0x02:
            # request cell info (only if data is not constantly published)
            LOGGER.debug("%s: request cell info", self.name)
            await self._send(data=BMS._cmd(b"\x96"), char=self._char_write_handle)

        data: BMSsample = self._decode_data(self._data_final, self._prot_offset)
        data.update(BMS._temp_sensors(self._data_final, self._prot_offset))
        data.update(BMS._cell_voltages(self._data_final, int(data[KEY_CELL_COUNT])))

        return data
