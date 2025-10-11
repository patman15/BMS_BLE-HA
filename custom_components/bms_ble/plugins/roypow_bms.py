"""Module to support RoyPow BMS."""

from collections.abc import Callable
from typing import Any, Final

from bleak.backends.characteristic import BleakGATTCharacteristic
from bleak.backends.device import BLEDevice
from bleak.uuids import normalize_uuid_str

from .basebms import AdvertisementPattern, BaseBMS, BMSsample, BMSvalue


class BMS(BaseBMS):
    """RoyPow BMS implementation."""

    _HEAD: Final[bytes] = b"\xea\xd1\x01"
    _TAIL: Final[int] = 0xF5
    _BT_MODULE_MSG: Final[bytes] = b"AT+STAT\r\n"  # AT cmd from BLE module
    _MIN_LEN: Final[int] = len(_HEAD) + 1
    _FIELDS: Final[list[tuple[BMSvalue, int, int, int, bool, Callable[[int], Any]]]] = [
        ("battery_level", 0x4, 7, 1, False, lambda x: x),
        ("voltage", 0x4, 47, 2, False, lambda x: float(x / 100)),
        (
            "current",
            0x3,
            6,
            3,
            False,
            lambda x: float((x & 0xFFFF) * (-1 if (x >> 16) & 0x1 else 1) / 100),
        ),
        ("problem_code", 0x3, 9, 3, False, lambda x: x),
        (
            "cycle_charge",
            0x4,
            24,
            4,
            False,
            lambda x: float(
                ((x & 0xFFFF0000) | (x & 0xFF00) >> 8 | (x & 0xFF) << 8) / 1000
            ),
        ),
        ("runtime", 0x4, 30, 2, False, lambda x: x * 60),
        ("temp_sensors", 0x3, 13, 1, False, lambda x: x),
        ("cycles", 0x4, 9, 2, False, lambda x: x),
    ]
    _CMDS: Final[set[int]] = set({field[1] for field in _FIELDS})

    def __init__(self, ble_device: BLEDevice, reconnect: bool = False) -> None:
        """Initialize BMS."""
        super().__init__(__name__, ble_device, reconnect)
        self._data_final: dict[int, bytearray] = {}
        self._exp_len: int = 0

    @staticmethod
    def matcher_dict_list() -> list[AdvertisementPattern]:
        """Provide BluetoothMatcher definition."""
        return [
            {
                "service_uuid": BMS.uuid_services()[0],
                "manufacturer_id": manufacturer_id,
                "connectable": True,
            }
            for manufacturer_id in (0x01A8, 0x0B31, 0x8AFB, 0xC0EA)
        ]

    @staticmethod
    def device_info() -> dict[str, str]:
        """Return device information for the battery management system."""
        return {"manufacturer": "RoyPow", "model": "SmartBMS"}

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
    def _calc_values() -> frozenset[BMSvalue]:
        return frozenset(
            {
                "battery_charging",
                "cycle_capacity",
                "delta_voltage",
                "power",
                "temperature",
            }
        )  # calculate further values from BMS provided set ones

    def _notification_handler(
        self, _sender: BleakGATTCharacteristic, data: bytearray
    ) -> None:
        """Handle the RX characteristics notify event (new data arrives)."""
        if not (data := data.removeprefix(BMS._BT_MODULE_MSG)):
            self._log.debug("filtering AT cmd")
            return

        if (
            data.startswith(BMS._HEAD)
            and not self._data.startswith(BMS._HEAD)
            and len(data) > len(BMS._HEAD)
        ):
            self._exp_len = data[len(BMS._HEAD)]
            self._data.clear()

        self._data += data
        self._log.debug(
            "RX BLE data (%s): %s", "start" if data == self._data else "cnt.", data
        )

        if not self._data.startswith(BMS._HEAD):
            self._data.clear()
            return

        # verify that data is long enough
        if len(self._data) < BMS._MIN_LEN + self._exp_len:
            return

        end_idx: Final[int] = BMS._MIN_LEN + self._exp_len - 1
        if self._data[end_idx] != BMS._TAIL:
            self._log.debug("incorrect EOF: %s", self._data)
            self._data.clear()
            return

        if (crc := BMS._crc(self._data[len(BMS._HEAD) : end_idx - 1])) != self._data[
            end_idx - 1
        ]:
            self._log.debug(
                "invalid checksum 0x%X != 0x%X", self._data[end_idx - 1], crc
            )
            self._data.clear()
            return

        self._data_final[self._data[5]] = self._data.copy()
        self._data.clear()
        self._data_event.set()

    @staticmethod
    def _decode_data(data: dict[int, bytearray]) -> BMSsample:
        result: BMSsample = {}
        for key, cmd, idx, size, sign, func in BMS._FIELDS:
            if cmd in data:
                result[key] = func(
                    int.from_bytes(
                        data[cmd][idx : idx + size], byteorder="big", signed=sign
                    )
                )
        return result

    @staticmethod
    def _cell_voltages(data: bytearray) -> list[float]:
        """Return cell voltages from status message."""
        cells: Final[int] = max(0, (len(data) - 11) // 2)
        return [
            (value / 1000)
            for idx in range(cells)
            if (
                value := int.from_bytes(
                    data[9 + 2 * idx : 11 + 2 * idx],
                    byteorder="big",
                )
            )
        ]

    @staticmethod
    def _temp_sensors(data: bytearray, sensors: int) -> list[int | float]:
        return [data[14 + idx] - 40 for idx in range(sensors)]

    @staticmethod
    def _crc(frame: bytearray) -> int:
        """Calculate XOR of all frame bytes."""
        crc: int = 0
        for b in frame:
            crc ^= b
        return crc

    @staticmethod
    def _cmd(cmd: bytes) -> bytes:
        """Assemble a RoyPow BMS command."""
        data: Final[bytearray] = bytearray([len(cmd) + 2, *cmd])
        return bytes([*BMS._HEAD, *data, BMS._crc(data), BMS._TAIL])

    async def _async_update(self) -> BMSsample:
        """Update battery status information."""

        self._data.clear()
        self._data_final.clear()
        for cmd in range(2, 5):
            await self._await_reply(BMS._cmd(bytes([0xFF, cmd])))

        result: BMSsample = BMS._decode_data(self._data_final)

        # remove remaining runtime if battery is charging
        if result.get("runtime") == 0xFFFF * 60:
            result.pop("runtime", None)

        result["cell_voltages"] = BMS._cell_voltages(
            self._data_final.get(0x2, bytearray())
        )
        result["temp_values"] = BMS._temp_sensors(
            self._data_final.get(0x3, bytearray()),
            int(result.get("temp_sensors", 0)),
        )

        return result
