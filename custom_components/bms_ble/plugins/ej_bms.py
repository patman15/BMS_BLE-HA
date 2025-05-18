"""Module to support E&J Technology BMS."""

from collections.abc import Callable
from enum import IntEnum
from string import hexdigits
from typing import Any, Final

from bleak.backends.characteristic import BleakGATTCharacteristic
from bleak.backends.device import BLEDevice

from .basebms import AdvertisementPattern, BaseBMS, BMSsample, BMSvalue


class Cmd(IntEnum):
    """BMS operation codes."""

    RT = 0x2
    CAP = 0x10


class BMS(BaseBMS):
    """E&J Technology BMS implementation."""

    _BT_MODULE_MSG: Final[bytes] = bytes([0x41, 0x54, 0x0D, 0x0A])  # BLE module message
    _HEAD: Final[bytes] = b"\x3a"
    _TAIL: Final[bytes] = b"\x7e"
    _MAX_CELLS: Final[int] = 16
    _FIELDS: Final[list[tuple[BMSvalue, Cmd, int, int, Callable[[int], Any]]]] = [
        ("current", Cmd.RT, 89, 8, lambda x: float((x >> 16) - (x & 0xFFFF)) / 100),
        ("battery_level", Cmd.RT, 123, 2, lambda x: x),
        ("cycle_charge", Cmd.CAP, 15, 4, lambda x: float(x) / 10),
        ("temperature", Cmd.RT, 97, 2, lambda x: x - 40),  # only 1st sensor relevant
        ("cycles", Cmd.RT, 115, 4, lambda x: x),
        ("problem_code", Cmd.RT, 105, 4, lambda x: x & 0x0FFC),  # mask status bits
    ]

    def __init__(self, ble_device: BLEDevice, reconnect: bool = False) -> None:
        """Initialize BMS."""
        super().__init__(__name__, ble_device, reconnect)
        self._data_final: bytearray = bytearray()

    @staticmethod
    def matcher_dict_list() -> list[AdvertisementPattern]:
        """Provide BluetoothMatcher definition."""
        return [  # Lithtech Energy (2x), Volthium
            AdvertisementPattern(local_name=pattern, connectable=True)
            for pattern in ("L-12V???AH-*", "LT-12V-*", "V-12V???Ah-*")
        ] + [  # Fliteboard, Electronix battery
            {"local_name": "libatt*", "manufacturer_id": 21320, "connectable": True},
            {"local_name": "LT-*", "manufacturer_id": 33384, "connectable": True},
            {"local_name": "SV12V*", "manufacturer_id": 33384, "connectable": True},
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
        """Return 128-bit UUID of characteristic that provides write property."""
        return "6e400002-b5a3-f393-e0a9-e50e24dcca9e"

    @staticmethod
    def _calc_values() -> frozenset[BMSvalue]:
        return frozenset(
            {
                "battery_charging",
                "cycle_capacity",
                "delta_voltage",
                "power",
                "runtime",
                "voltage",
            }
        )  # calculate further values from BMS provided set ones

    def _notification_handler(
        self, _sender: BleakGATTCharacteristic, data: bytearray
    ) -> None:
        """Handle the RX characteristics notify event (new data arrives)."""

        if data.startswith(BMS._BT_MODULE_MSG):
            self._log.debug("filtering AT cmd")
            if not (data := data.removeprefix(BMS._BT_MODULE_MSG)):
                return

        if data.startswith(BMS._HEAD):  # check for beginning of frame
            self._data.clear()

        self._data += data

        self._log.debug(
            "RX BLE data (%s): %s", "start" if data == self._data else "cnt.", data
        )

        exp_frame_len: Final[int] = (
            int(self._data[7:11], 16)
            if len(self._data) > 10
            and all(chr(c) in hexdigits for c in self._data[7:11])
            else 0xFFFF
        )

        if not self._data.startswith(BMS._HEAD) or (
            not self._data.endswith(BMS._TAIL) and len(self._data) < exp_frame_len
        ):
            return

        if not self._data.endswith(BMS._TAIL):
            self._log.debug("incorrect EOF: %s", data)
            self._data.clear()
            return

        if not all(chr(c) in hexdigits for c in self._data[1:-1]):
            self._log.debug("incorrect frame encoding.")
            self._data.clear()
            return

        if len(self._data) != exp_frame_len:
            self._log.debug(
                "incorrect frame length %i != %i",
                len(self._data),
                exp_frame_len,
            )
            self._data.clear()
            return

        if (crc := BMS._crc(self._data[1:-3])) != int(self._data[-3:-1], 16):
            self._log.debug(
                "invalid checksum 0x%X != 0x%X", int(self._data[-3:-1], 16), crc
            )
            self._data.clear()
            return

        self._log.debug(
            "address: 0x%X, command 0x%X, version: 0x%X, length: 0x%X",
            int(self._data[1:3], 16),
            int(self._data[3:5], 16) & 0x7F,
            int(self._data[5:7], 16),
            len(self._data),
        )
        self._data_final = self._data.copy()
        self._data_event.set()

    @staticmethod
    def _crc(data: bytearray) -> int:
        return (sum(data) ^ 0xFF) & 0xFF

    @staticmethod
    def _cell_voltages(data: bytearray) -> list[float]:
        """Return cell voltages from status message."""
        return [
            (value / 1000)
            for idx in range(BMS._MAX_CELLS)
            if (value := int(data[25 + 4 * idx : 25 + 4 * idx + 4], 16))
        ]

    @staticmethod
    def _decode_data(data: dict[int, bytearray]) -> BMSsample:
        result: BMSsample = {}
        for key, cmd, idx, size, func in BMS._FIELDS:
            result[key] = func(int(data[cmd.value][idx : idx + size], 16))
        return result

    async def _async_update(self) -> BMSsample:
        """Update battery status information."""
        raw_data: dict[int, bytearray] = {}

        # query real-time information and capacity
        for cmd in (b":000250000E03~", b":001031000E05~"):
            await self._await_reply(cmd)
            rsp: int = int(self._data_final[3:5], 16) & 0x7F
            raw_data[rsp] = self._data_final
            if rsp == Cmd.RT and len(self._data_final) == 0x8C:
                # handle metrisun version
                self._log.debug("single frame protocol detected")
                raw_data[Cmd.CAP] = bytearray(15) + self._data_final[125:]
                break

        if len(raw_data) != len(list(Cmd)) or not all(
            len(value) > 0 for value in raw_data.values()
        ):
            return {}

        return self._decode_data(raw_data) | {
            "cell_voltages": self._cell_voltages(raw_data[Cmd.RT])
        }
