"""Module to support Ective BMS."""

import asyncio
from collections.abc import Callable
from string import hexdigits
from typing import Any, Final

from bleak.backends.characteristic import BleakGATTCharacteristic
from bleak.backends.device import BLEDevice
from bleak.uuids import normalize_uuid_str

from .basebms import AdvertisementPattern, BaseBMS, BMSsample, BMSvalue


class BMS(BaseBMS):
    """Ective BMS implementation."""

    _HEAD_RSP: Final[bytes] = bytes([0x5E])  # header for responses
    _MAX_CELLS: Final[int] = 16
    _INFO_LEN: Final[int] = 113
    _CRC_LEN: Final[int] = 4
    _FIELDS: Final[list[tuple[BMSvalue, int, int, bool, Callable[[int], Any]]]] = [
        ("voltage", 1, 8, False, lambda x: x / 1000),
        ("current", 9, 8, True, lambda x: x / 1000),
        ("battery_level", 29, 4, False, lambda x: x),
        ("cycle_charge", 17, 8, False, lambda x: x / 1000),
        ("cycles", 25, 4, False, lambda x: x),
        ("temperature", 33, 4, False, lambda x: round(x * 0.1 - 273.15, 1)),
        ("problem_code", 37, 2, False, lambda x: x),
    ]

    def __init__(self, ble_device: BLEDevice, reconnect: bool = False) -> None:
        """Initialize BMS."""
        super().__init__(__name__, ble_device, reconnect)
        self._data_final: bytearray = bytearray()

    @staticmethod
    def matcher_dict_list() -> list[AdvertisementPattern]:
        """Provide BluetoothMatcher definition."""
        return [
            {
                "local_name": pattern,
                "service_uuid": BMS.uuid_services()[0],
                "connectable": True,
            }
            for pattern in ("$PFLAC*", "NWJ20*", "ZM20*")
        ]

    @staticmethod
    def device_info() -> dict[str, str]:
        """Return device information for the battery management system."""
        return {"manufacturer": "Ective", "model": "Smart BMS"}

    @staticmethod
    def uuid_services() -> list[str]:
        """Return list of 128-bit UUIDs of services required by BMS."""
        return [normalize_uuid_str("ffe0")]

    @staticmethod
    def uuid_rx() -> str:
        """Return 16-bit UUID of characteristic that provides notification/read property."""
        return "ffe4"

    @staticmethod
    def uuid_tx() -> str:
        """Return 16-bit UUID of characteristic that provides write property."""
        raise NotImplementedError

    @staticmethod
    def _calc_values() -> frozenset[BMSvalue]:
        return frozenset(
            {
                "battery_charging",
                "cycle_capacity",
                "cycle_charge",
                "delta_voltage",
                "power",
                "runtime",
            }
        )  # calculate further values from BMS provided set ones

    def _notification_handler(
        self, _sender: BleakGATTCharacteristic, data: bytearray
    ) -> None:
        """Handle the RX characteristics notify event (new data arrives)."""

        if (start := data.find(BMS._HEAD_RSP)) != -1:  # check for beginning of frame
            data = data[start:]
            self._data.clear()

        self._data += data
        self._log.debug(
            "RX BLE data (%s): %s", "start" if data == self._data else "cnt.", data
        )

        if len(self._data) < BMS._INFO_LEN:
            return

        self._data = self._data[: BMS._INFO_LEN]  # cut off exceeding data

        if not (
            self._data.startswith(BMS._HEAD_RSP)
            and set(self._data.decode(errors="replace")[1:]).issubset(hexdigits)
        ):
            self._log.debug("incorrect frame coding: %s", self._data)
            self._data.clear()
            return

        if (crc := BMS._crc(self._data[1 : -BMS._CRC_LEN])) != int(
            self._data[-BMS._CRC_LEN :], 16
        ):
            self._log.debug(
                "invalid checksum 0x%X != 0x%X",
                int(self._data[-BMS._CRC_LEN :], 16),
                crc,
            )
            self._data.clear()
            return

        self._data_final = self._data.copy()
        self._data_event.set()

    @staticmethod
    def _crc(data: bytearray) -> int:
        return sum(int(data[idx : idx + 2], 16) for idx in range(0, len(data), 2))

    @staticmethod
    def _cell_voltages(data: bytearray) -> list[float]:
        """Return cell voltages from status message."""
        return [
            (value / 1000)
            for idx in range(BMS._MAX_CELLS)
            if (value := BMS._conv_int(data[45 + idx * 4 : 49 + idx * 4], False))
        ]

    @staticmethod
    def _conv_int(data: bytearray, sign: bool) -> int:
        return int.from_bytes(
            int(data, 16).to_bytes(len(data) >> 1, byteorder="little", signed=False),
            byteorder="big",
            signed=sign,
        )

    @staticmethod
    def _decode_data(data: bytearray) -> BMSsample:
        result: BMSsample = {}
        for key, idx, size, sign, func in BMS._FIELDS:
            result[key] = func(BMS._conv_int(data[idx : idx + size], sign))
        return result

    async def _async_update(self) -> BMSsample:
        """Update battery status information."""

        await asyncio.wait_for(self._wait_event(), timeout=BMS.TIMEOUT)
        return self._decode_data(self._data_final) | {
            "cell_voltages": BMS._cell_voltages(self._data_final)
        }
