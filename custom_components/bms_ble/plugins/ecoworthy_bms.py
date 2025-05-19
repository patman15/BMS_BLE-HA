"""Module to support ECO-WORTHY BMS."""

import asyncio
from collections.abc import Callable
from typing import Any, Final

from bleak.backends.characteristic import BleakGATTCharacteristic
from bleak.backends.device import BLEDevice
from bleak.uuids import normalize_uuid_str

from .basebms import AdvertisementPattern, BaseBMS, BMSsample, BMSvalue, crc_modbus


class BMS(BaseBMS):
    """ECO-WORTHY BMS implementation."""

    _HEAD: Final[tuple] = (b"\xa1", b"\xa2")
    _CELL_POS: Final[int] = 14
    _TEMP_POS: Final[int] = 80
    _FIELDS: Final[list[tuple[BMSvalue, int, int, int, bool, Callable[[int], Any]]]] = [
        ("battery_level", 0xA1, 16, 2, False, lambda x: x),
        ("voltage", 0xA1, 20, 2, False, lambda x: float(x / 100)),
        ("current", 0xA1, 22, 2, True, lambda x: float(x / 100)),
        ("problem_code", 0xA1, 51, 2, False, lambda x: x),
        ("design_capacity", 0xA1, 26, 2, False, lambda x: float(x / 100)),
        ("cell_count", 0xA2, _CELL_POS, 2, False, lambda x: x),
        ("temp_sensors", 0xA2, _TEMP_POS, 2, False, lambda x: x),
        # ("cycles", 0xA1, 8, 2, False, lambda x: x),
    ]
    _CMDS: Final[set[int]] = set({field[1] for field in _FIELDS})

    def __init__(self, ble_device: BLEDevice, reconnect: bool = False) -> None:
        """Initialize BMS."""
        super().__init__(__name__, ble_device, reconnect)
        self._mac_head: Final[tuple] = tuple(
            int(self._ble_device.address.replace(":", ""), 16).to_bytes(6) + head
            for head in BMS._HEAD
        )
        self._data_final: dict[int, bytearray] = {}

    @staticmethod
    def matcher_dict_list() -> list[AdvertisementPattern]:
        """Provide BluetoothMatcher definition."""
        return [
            {
                "local_name": "ECO-WORTHY*",
                "manufacturer_id": m_id,
                "connectable": True,
            }
            for m_id in (0x3E7C, 0xBB28, 0xC2B4, 0xE0E2)
        ]

    @staticmethod
    def device_info() -> dict[str, str]:
        """Return device information for the battery management system."""
        return {"manufacturer": "ECO-WORTHY", "model": "BW02"}

    @staticmethod
    def uuid_services() -> list[str]:
        """Return list of 128-bit UUIDs of services required by BMS."""
        return [normalize_uuid_str("fff0")]

    @staticmethod
    def uuid_rx() -> str:
        """Return 16-bit UUID of characteristic that provides notification/read property."""
        return "fff1"

    @staticmethod
    def uuid_tx() -> str:
        """Return 16-bit UUID of characteristic that provides write property."""
        raise NotImplementedError

    @staticmethod
    def _calc_values() -> frozenset[BMSvalue]:
        return frozenset(
            {
                "battery_charging",
                "cycle_charge",
                "cycle_capacity",
                "delta_voltage",
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

        if not data.startswith(BMS._HEAD + self._mac_head):
            self._log.debug("invalid frame type: '%s'", data[0:1].hex())
            return

        if (crc := crc_modbus(data[:-2])) != int.from_bytes(data[-2:], "little"):
            self._log.debug(
                "invalid checksum 0x%X != 0x%X",
                int.from_bytes(data[-2:], "little"),
                crc,
            )
            self._data = bytearray()
            return

        # copy final data without message type and adapt to protocol type
        shift: Final[bool] = data.startswith(self._mac_head)
        self._data_final[data[6 if shift else 0]] = (
            bytearray(2 if shift else 0) + data.copy()
        )
        if BMS._CMDS.issubset(self._data_final.keys()):
            self._data_event.set()

    @staticmethod
    def _decode_data(data: dict[int, bytearray]) -> BMSsample:
        result: BMSsample = {}
        for key, cmd, idx, size, sign, func in BMS._FIELDS:
            result[key] = func(
                int.from_bytes(
                    data[cmd][idx : idx + size], byteorder="big", signed=sign
                )
            )
        return result

    @staticmethod
    def _cell_voltages(data: bytearray, cells: int, offs: int) -> list[float]:
        return [
            int.from_bytes(
                data[offs + idx * 2 : offs + idx * 2 + 2],
                byteorder="big",
                signed=False,
            )
            / 1000
            for idx in range(cells)
        ]

    @staticmethod
    def _temp_sensors(data: bytearray, sensors: int, offs: int) -> list[float]:
        return [
            int.from_bytes(
                data[offs + idx * 2 : offs + (idx + 1) * 2],
                byteorder="big",
                signed=True,
            )
            / 10
            for idx in range(sensors)
        ]

    async def _async_update(self) -> BMSsample:
        """Update battery status information."""

        self._data_final.clear()
        self._data_event.clear()  # clear event to ensure new data is acquired
        await asyncio.wait_for(self._wait_event(), timeout=BMS.TIMEOUT)

        result: BMSsample = BMS._decode_data(self._data_final)

        result["cell_voltages"] = BMS._cell_voltages(
            self._data_final[0xA2],
            int(result.get("cell_count", 0)),
            BMS._CELL_POS + 2,
        )
        result["temp_values"] = BMS._temp_sensors(
            self._data_final[0xA2],
            int(result.get("temp_sensors", 0)),
            BMS._TEMP_POS + 2,
        )

        return result
