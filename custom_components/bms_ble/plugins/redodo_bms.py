"""Module to support Redodo BMS."""

from collections.abc import Callable
from typing import Any, Final

from bleak.backends.characteristic import BleakGATTCharacteristic
from bleak.backends.device import BLEDevice
from bleak.uuids import normalize_uuid_str

from .basebms import AdvertisementPattern, BaseBMS, BMSsample, BMSvalue, crc_sum


class BMS(BaseBMS):
    """Redodo BMS implementation."""

    CRC_POS: Final[int] = -1  # last byte
    HEAD_LEN: Final[int] = 3
    MAX_CELLS: Final[int] = 16
    MAX_TEMP: Final[int] = 5
    _FIELDS: Final[list[tuple[BMSvalue, int, int, bool, Callable[[int], Any]]]] = [
        ("voltage", 12, 2, False, lambda x: float(x / 1000)),
        ("current", 48, 4, True, lambda x: float(x / 1000)),
        ("battery_level", 90, 2, False, lambda x: x),
        ("cycle_charge", 62, 2, False, lambda x: float(x / 100)),
        ("cycles", 96, 4, False, lambda x: x),
        ("problem_code", 76, 4, False, lambda x: x),
    ]

    def __init__(self, ble_device: BLEDevice, reconnect: bool = False) -> None:
        """Initialize BMS."""
        super().__init__(__name__, ble_device, reconnect)

    @staticmethod
    def matcher_dict_list() -> list[AdvertisementPattern]:
        """Provide BluetoothMatcher definition."""
        return [
            {  # patterns required to exclude "BT-ROCC2440"
                "local_name": pattern,
                "service_uuid": BMS.uuid_services()[0],
                "manufacturer_id": 0x585A,
                "connectable": True,
            }
            for pattern in ("R-12*", "R-24*", "P-12*", "P-24*", "PQ-12*", "PQ-24*", "L-12*")
        ]

    @staticmethod
    def device_info() -> dict[str, str]:
        """Return device information for the battery management system."""
        return {"manufacturer": "Redodo", "model": "Bluetooth battery"}

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
        return "ffe2"

    @staticmethod
    def _calc_values() -> frozenset[BMSvalue]:
        return frozenset(
            {
                "battery_charging",
                "delta_voltage",
                "cycle_capacity",
                "power",
                "runtime",
                "temperature",
            }
        )  # calculate further values from BMS provided set ones

    def _notification_handler(
        self, _sender: BleakGATTCharacteristic, data: bytearray
    ) -> None:
        """Handle the RX characteristics notify event (new data arrives)."""
        self._log.debug("RX BLE data: %s", data)

        if len(data) < 3 or not data.startswith(b"\x00\x00"):
            self._log.debug("incorrect SOF.")
            return

        if len(data) != data[2] + BMS.HEAD_LEN + 1:  # add header length and CRC
            self._log.debug("incorrect frame length (%i)", len(data))
            return

        if (crc := crc_sum(data[: BMS.CRC_POS])) != data[BMS.CRC_POS]:
            self._log.debug(
                "invalid checksum 0x%X != 0x%X", data[len(data) + BMS.CRC_POS], crc
            )
            return

        self._data = data
        self._data_event.set()

    @staticmethod
    def _decode_data(data: bytearray) -> BMSsample:
        result: BMSsample = {}
        for key, idx, size, sign, func in BMS._FIELDS:
            result[key] = func(
                int.from_bytes(data[idx : idx + size], byteorder="little", signed=sign)
            )
        return result

    @staticmethod
    def _cell_voltages(data: bytearray, cells: int) -> list[float]:
        """Return cell voltages from status message."""
        return [
            (value / 1000)
            for idx in range(cells)
            if (
                value := int.from_bytes(
                    data[16 + 2 * idx : 16 + 2 * idx + 2], byteorder="little"
                )
            )
        ]

    @staticmethod
    def _temp_sensors(data: bytearray, sensors: int) -> list[int | float]:
        return [
            value
            for idx in range(sensors)
            if (
                value := int.from_bytes(
                    data[52 + idx * 2 : 54 + idx * 2], byteorder="little", signed=True
                )
            )
        ]

    async def _async_update(self) -> BMSsample:
        """Update battery status information."""
        await self._await_reply(b"\x00\x00\x04\x01\x13\x55\xaa\x17")

        return BMS._decode_data(self._data) | BMSsample(
            {
                "cell_voltages": BMS._cell_voltages(self._data, BMS.MAX_CELLS),
                "temp_values": BMS._temp_sensors(self._data, BMS.MAX_TEMP),
            }
        )
