"""Module to support Dummy BMS."""

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
    KEY_CELL_VOLTAGE,
)

from .basebms import BaseBMS, BMSsample

LOGGER = logging.getLogger(__name__)
BAT_TIMEOUT = 10


class BMS(BaseBMS):
    """Dummy battery class implementation."""

    CRC_POS: Final = -1  # last byte
    HEAD_LEN: Final = 3
    MAX_CELLS: Final = 16

    def __init__(self, ble_device: BLEDevice, reconnect: bool = False) -> None:
        """Initialize BMS."""
        LOGGER.debug("%s init(), BT address: %s", self.device_id(), ble_device.address)
        super().__init__(LOGGER, self._notification_handler, ble_device, reconnect)

        self._data: bytearray = bytearray()
        self._FIELDS: Final[
            list[tuple[str, int, int, bool, Callable[[int], int | float]]]
        ] = [
            (ATTR_VOLTAGE, 12, 2, False, lambda x: float(x / 1000)),
            (ATTR_CURRENT, 48, 4, True, lambda x: float(x / 1000)),
            (ATTR_TEMPERATURE, 56, 2, False, lambda x: x),
            (ATTR_BATTERY_LEVEL, 90, 2, False, lambda x: x),
            (ATTR_CYCLE_CHRG, 62, 2, False, lambda x: float(x / 100)),
            (ATTR_CYCLES, 96, 4, False, lambda x: x),
        ]

    @staticmethod
    def matcher_dict_list() -> list[dict[str, Any]]:
        """Provide BluetoothMatcher definition."""
        return [
            {
                "service_uuid": BMS.uuid_services()[0],
                "manufacturer_id": 0x585A,
                "connectable": True,
            }
        ]

    @staticmethod
    def device_info() -> dict[str, str]:
        """Return device information for the battery management system."""
        return {"manufacturer": "Redodo", "model": "Bluetooth battery"}

    @staticmethod
    def uuid_services() -> list[str]:
        """Return list of 128-bit UUIDs of services required by BMS."""
        return [normalize_uuid_str("ffe0")]  # change service UUID here!

    @staticmethod
    def uuid_rx() -> str:
        """Return 16-bit UUID of characteristic that provides notification/read property."""
        return "ffe1"

    @staticmethod
    def uuid_tx() -> str:
        """Return 16-bit UUID of characteristic that provides write property."""
        return "ffe2"

    @staticmethod
    def _calc_values() -> set[str]:
        return {
            ATTR_BATTERY_CHARGING,
            ATTR_DELTA_VOLTAGE,
            ATTR_CYCLE_CAP,
            ATTR_POWER,
            ATTR_RUNTIME,
        }  # calculate further values from BMS provided set ones

    def _notification_handler(self, _sender, data: bytearray) -> None:
        """Handle the RX characteristics notify event (new data arrives)."""
        LOGGER.debug("%s: Received BLE data: %s", self.name, data.hex(" "))

        if len(data) < 3 or not data.startswith(b"\x00\x00"):
            LOGGER.debug("%s: incorrect SOF.")
            return

        if len(data) != data[2] + self.HEAD_LEN + 1:  # add header length and CRC
            LOGGER.debug("(%s) incorrect frame length (%i)", self.name, len(data))
            return

        crc = self._crc(data[: self.CRC_POS])
        if crc != data[self.CRC_POS]:
            LOGGER.debug(
                "(%s) Rx data CRC is invalid: 0x%x != 0x%x",
                self.name,
                data[len(data) + self.CRC_POS],
                crc,
            )
            return

        self._data = data
        self._data_event.set()

    def _crc(self, frame: bytes) -> int:
        """Calculate frame CRC."""
        return sum(frame) & 0xFF

    def _cell_voltages(self, data: bytearray, cells: int) -> dict[str, float]:
        """Return cell voltages from status message."""
        return {
            f"{KEY_CELL_VOLTAGE}{idx}": int.from_bytes(
                data[16 + 2 * idx : 16 + 2 * idx + 2],
                byteorder="little",
                signed=False,
            )
            / 1000
            for idx in range(cells)
            if int.from_bytes(data[16 + 2 * idx : 16 + 2 * idx + 2], byteorder="little")
        }

    async def _async_update(self) -> BMSsample:
        """Update battery status information."""
        await self._client.write_gatt_char(
            BMS.uuid_tx(), data=b"\x00\x00\x04\x01\x13\x55\xaa\x17"
        )
        await asyncio.wait_for(self._wait_event(), timeout=BAT_TIMEOUT)

        return {
            key: func(
                int.from_bytes(
                    self._data[idx : idx + size], byteorder="little", signed=sign
                )
            )
            for key, idx, size, sign, func in self._FIELDS
        } | self._cell_voltages(self._data, self.MAX_CELLS)
