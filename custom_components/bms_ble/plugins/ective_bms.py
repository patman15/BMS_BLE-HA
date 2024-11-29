"""Module to support Ective BMS."""

import asyncio
import logging
from collections.abc import Callable
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
    KEY_CELL_VOLTAGE,
)

from .basebms import BaseBMS, BMSsample

LOGGER = logging.getLogger(__name__)
BAT_TIMEOUT: Final[int] = 10


class BMS(BaseBMS):
    """Ective battery class implementation."""

    _HEAD_RSP: Final[bytes] = bytes([0x5E])  # header for responses
    _CELLS: Final[int] = 16
    _INFO_LEN: Final[int] = 113
    _CRC_LEN: Final[int] = 4
    _HEX_CHARS: Final[set] = set("0123456789ABCDEF")

    def __init__(self, ble_device: BLEDevice, reconnect: bool = False) -> None:
        """Initialize BMS."""
        LOGGER.debug("%s init(), BT address: %s", self.device_id(), ble_device.address)
        super().__init__(LOGGER, self._notification_handler, ble_device, reconnect)
        self._data: bytearray = bytearray()
        self._data_final: bytearray = bytearray()
        self._FIELDS: Final[
            list[tuple[str, int, int, bool, Callable[[int], int | float]]]
        ] = [
            (ATTR_VOLTAGE, 1, 8, False, lambda x: float(x / 1000)),
            (ATTR_CURRENT, 9, 8, True, lambda x: float(x / 1000)),
            (ATTR_BATTERY_LEVEL, 29, 4, False, lambda x: x),
            (ATTR_CYCLE_CHRG, 17, 8, False, lambda x: float(x / 1000)),
            (ATTR_CYCLES, 25, 4, False, lambda x: x),
            (ATTR_TEMPERATURE, 33, 4, False, lambda x: round(x * 0.1 - 273.15, 1)),
        ]

    @staticmethod
    def matcher_dict_list() -> list[dict[str, Any]]:
        """Provide BluetoothMatcher definition."""
        return [
            {
                "local_name": "$PFLAC*",
                "service_uuid": BMS.uuid_services()[0],
                "manufacturer_id": 65535,
                "connectable": True,
            }
        ]

    @staticmethod
    def device_info() -> dict[str, str]:
        """Return device information for the battery management system."""
        return {"manufacturer": "Ective", "model": "Smart BMS"}

    @staticmethod
    def uuid_services() -> list[str]:
        """Return list of 128-bit UUIDs of services required by BMS."""
        return [normalize_uuid_str("ffe0")]  # change service UUID here!

    @staticmethod
    def uuid_rx() -> str:
        """Return 16-bit UUID of characteristic that provides notification/read property."""
        return "ffe4"

    @staticmethod
    def uuid_tx() -> str:
        """Return 16-bit UUID of characteristic that provides write property."""
        raise NotImplementedError

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

        data = data.strip(b"\x00") # remove leading/trailing string end
        if data.startswith(self._HEAD_RSP):  # check for beginning of frame
            self._data.clear()

        self._data += data
        LOGGER.debug(
            "(%s) Rx BLE data (%s): %s",
            self._ble_device.name,
            "start" if data == self._data else "cnt.",
            data,
        )

        if len(self._data) < self._INFO_LEN:
            return

        if not (
            self._data.startswith(self._HEAD_RSP)
            and set(self._data.decode()[3:]).issubset(self._HEX_CHARS)
        ):
            LOGGER.debug("(%s) incorrect frame coding: %s", self.name, self._data)
            self._data.clear()
            return

        crc: Final[int] = self._crc(self._data[1 : -self._CRC_LEN])
        if crc != int(self._data[-self._CRC_LEN :], 16):
            LOGGER.debug(
                "(%s) incorrect checksum 0x%X != 0x%X",
                self.name,
                int(self._data[-self._CRC_LEN :], 16),
                crc,
            )
            self._data.clear()
            return

        self._data_final = self._data.copy()
        self._data_event.set()

    def _crc(self, data: bytearray) -> int:
        return sum(int(data[idx : idx + 2], 16) for idx in range(0, len(data), 2))

    def _cell_voltages(self, data: bytearray) -> dict[str, float]:
        """Return cell voltages from status message."""
        return {
            f"{KEY_CELL_VOLTAGE}{idx}": self._conv_int(
                data[45 + idx * 4 : 49 + idx * 4], False
            )
            / 1000
            for idx in range(self._CELLS)
            if self._conv_int(data[45 + idx * 4 : 49 + idx * 4], False)
        }

    def _conv_int(self, data: bytearray, sign: bool) -> int:
        return int.from_bytes(
            int(data, 16).to_bytes(len(data) >> 1, byteorder="little", signed=False),
            byteorder="big",
            signed=sign,
        )

    async def _async_update(self) -> BMSsample:
        """Update battery status information."""

        await asyncio.wait_for(self._wait_event(), timeout=BAT_TIMEOUT)
        return {
            key: func(self._conv_int(self._data_final[idx : idx + size], sign))
            for key, idx, size, sign, func in self._FIELDS
        } | self._cell_voltages(self._data_final)
