"""Module to support Seplos V2 BMS."""

import asyncio
import logging
from typing import Any, Callable, Final

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
    KEY_PACK_COUNT,
    KEY_TEMP_SENS,
)

from .basebms import BaseBMS, BMSsample, crc_xmodem

LOGGER = logging.getLogger(__name__)
BAT_TIMEOUT = 10


class BMS(BaseBMS):
    """Dummy battery class implementation."""

    _HEAD: Final[int] = 0x7E
    _TAIL: Final[int] = 0x0D
    _CMD_VER: Final[int] = 0x10
    _RSP_VER: Final[int] = 0x14
    _MIN_LEN: Final[int] = 10
    _MAX_SUBS: Final[int] = 0xF
    _FIELDS: Final[
        list[tuple[str, int, int, int, bool, Callable[[int], int | float]]]
    ] = [
        (ATTR_VOLTAGE, 0x62, 25, 2, False, lambda x: float(x / 100)),
        (ATTR_CURRENT, 0x62, 23, 2, True, lambda x: float(x / 10)),
        (ATTR_CYCLE_CHRG, 0x62, 27, 2, False, lambda x: float(x / 10)),
        (ATTR_CYCLES, 0x62, 36, 2, False, lambda x: x),
        (ATTR_BATTERY_LEVEL, 0x62, 32, 2, False, lambda x: float(x / 10)),
        (ATTR_TEMPERATURE, 0x62, 21, 2, True, lambda x: (x - 2731.5) / 10),
        (KEY_CELL_COUNT, 0x62, 9, 1, False, lambda x: x),
        (KEY_PACK_COUNT, 0x51, 42, 1, False, lambda x: min(x, BMS._MAX_SUBS)),
        (KEY_TEMP_SENS, 0x62, 14, 1, False, lambda x: x),
    ]  # Protocol Seplos V2 (parallel data 0x62, device manufacturer info 0x51)
    _CMDS: Final[list[tuple[int, bytes]]] = [
        *list({(field[1], b"") for field in _FIELDS}),
        (0x61, b"\x00"),
    ]

    def __init__(self, ble_device: BLEDevice, reconnect: bool = False) -> None:
        """Initialize BMS."""
        LOGGER.debug("%s init(), BT address: %s", self.device_id(), ble_device.address)
        super().__init__(LOGGER, self._notification_handler, ble_device, reconnect)
        self._data: bytearray = bytearray()
        self._exp_len: int = 0
        self._data_final: dict[int, bytearray] = {}

    @staticmethod
    def matcher_dict_list() -> list[dict[str, Any]]:
        """Provide BluetoothMatcher definition."""
        return [
            {
                "local_name": "BP0?",
                "service_uuid": BMS.uuid_services()[0],
                "connectable": True,
            }
        ]

    @staticmethod
    def device_info() -> dict[str, str]:
        """Return device information for the battery management system."""
        return {"manufacturer": "Seplos", "model": "Smart BMS V2"}

    @staticmethod
    def uuid_services() -> list[str]:
        """Return list of 128-bit UUIDs of services required by BMS."""
        return [normalize_uuid_str("ff00")]

    @staticmethod
    def uuid_rx() -> str:
        """Return 16-bit UUID of characteristic that provides notification/read property."""
        return "ff01"

    @staticmethod
    def uuid_tx() -> str:
        """Return 16-bit UUID of characteristic that provides write property."""
        return "ff02"

    @staticmethod
    def _calc_values() -> set[str]:
        return {
            ATTR_BATTERY_CHARGING,
            ATTR_CYCLE_CAP,
            ATTR_DELTA_VOLTAGE,
            ATTR_POWER,
            ATTR_RUNTIME,
        }  # calculate further values from BMS provided set ones

    def _notification_handler(self, _sender, data: bytearray) -> None:
        """Handle the RX characteristics notify event (new data arrives)."""
        if (
            data[0] == BMS._HEAD
            and len(data) > BMS._MIN_LEN
            and len(self._data) >= self._exp_len
        ):
            self._exp_len = BMS._MIN_LEN + int.from_bytes(data[5:7])
            self._data = bytearray()

        self._data += data
        LOGGER.debug(
            "%s: RX BLE data (%s): %s",
            self._ble_device.name,
            "start" if data == self._data else "cnt.",
            data,
        )

        # verify that data long enough
        if len(self._data) < self._exp_len:
            return

        if self._data[-1] != BMS._TAIL:
            LOGGER.debug("%s: frame end incorrect: %s", self.name, self._data)
            return

        if self._data[1] != BMS._RSP_VER:
            LOGGER.debug(
                "%s: unknown frame version: V%.1f", self.name, self._data[1] / 10
            )
            return

        if self._data[4]:
            LOGGER.debug("%s: BMS reported error code: 0x%X", self.name, self._data[4])
            return

        crc = crc_xmodem(self._data[1:-3])
        if int.from_bytes(self._data[-3:-1]) != crc:
            LOGGER.debug(
                "%s: RX data CRC is invalid: 0x%X != 0x%X",
                self._ble_device.name,
                int.from_bytes(self._data[-3:-1]),
                crc,
            )
            return

        LOGGER.debug(
            "%s: address: 0x%X, function: 0x%X, return: 0x%X",
            self.name,
            self._data[2],
            self._data[3],
            self._data[4],
        )

        self._data_final[self._data[3]] = self._data
        self._data_event.set()

    @staticmethod
    def _cmd(cmd: int, address: int = 0, data: bytearray = bytearray()) -> bytearray:
        """Assemble a Seplos V2 BMS command."""
        assert cmd in (0x47, 0x51, 0x61, 0x62, 0x04)  # allow only read commands
        frame = bytearray(
            [BMS._HEAD, BMS._CMD_VER, address, 0x46, cmd]
        )  # fixed version
        frame += len(data).to_bytes(2, "big", signed=False) + data
        frame += bytearray(int.to_bytes(crc_xmodem(frame[1:]), 2, byteorder="big"))
        frame += bytearray([BMS._TAIL])
        return frame

    @staticmethod
    def _decode_data(data: dict[int, bytearray]) -> dict[str, int | float]:
        return {
            key: func(
                int.from_bytes(
                    data[cmd][idx : idx + size], byteorder="big", signed=sign
                )
            )
            for key, cmd, idx, size, sign, func in BMS._FIELDS
        }

    @staticmethod
    def _cell_voltages(data: bytearray) -> dict[str, float]:
        return {
            f"{KEY_CELL_VOLTAGE}{idx}": float(
                int.from_bytes(
                    data[10 + idx * 2 : 10 + idx * 2 + 2], byteorder="big", signed=False
                )
            )
            / 1000
            for idx in range(data[9])
        }

    async def _async_update(self) -> BMSsample:
        """Update battery status information."""

        for cmd, data in BMS._CMDS:
            await self._client.write_gatt_char(BMS.uuid_tx(), data=BMS._cmd(cmd, data=bytearray(data)))
            await asyncio.wait_for(self._wait_event(), timeout=BAT_TIMEOUT)

        result: BMSsample = BMS._decode_data(self._data_final)
        result |= BMS._cell_voltages(self._data_final[0x61])

        self._data_final.clear()

        return result
