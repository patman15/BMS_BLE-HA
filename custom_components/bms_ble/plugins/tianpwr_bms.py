"""Module to support TianPwr BMS."""

from collections.abc import Callable
from typing import Any, Final

from bleak.backends.characteristic import BleakGATTCharacteristic
from bleak.backends.device import BLEDevice
from bleak.uuids import normalize_uuid_str

from .basebms import AdvertisementPattern, BaseBMS, BMSsample, BMSvalue


class BMS(BaseBMS):
    """TianPwr BMS implementation."""

    _HEAD: Final[bytes] = b"\x55"
    _TAIL: Final[bytes] = b"\xaa"
    _RDCMD: Final[bytes] = b"\x04"
    _MAX_CELLS: Final[int] = 16
    _MIN_LEN: Final[int] = 4
    _DEF_LEN: Final[int] = 20
    _FIELDS: Final[list[tuple[BMSvalue, int, int, int, bool, Callable[[int], Any]]]] = [
        ("battery_level", 0x83, 3, 2, False, lambda x: x),
        ("voltage", 0x83, 5, 2, False, lambda x: x / 100),
        ("current", 0x83, 13, 2, True, lambda x: x / 100),
        ("problem_code", 0x84, 11, 8, False, lambda x: x),
        # ("runtime", 0x4, 30, 2, False, lambda x: x * 60),
        ("cell_count", 0x84, 3, 1, False, lambda x: x),
        ("temp_sensors", 0x84, 4, 1, False, lambda x: x),
        ("design_capacity", 0x84, 5, 2, False, lambda x: x // 100),
        ("cycle_charge", 0x84, 7, 2, False, lambda x: x / 100),
        ("cycles", 0x84, 9, 2, False, lambda x: x),
    ]
    _CMDS: Final[set[int]] = set({field[1] for field in _FIELDS}) | set({0x87})

    def __init__(self, ble_device: BLEDevice, reconnect: bool = False) -> None:
        """Initialize BMS."""
        super().__init__(__name__, ble_device, reconnect)
        self._data_final: dict[int, bytearray] = {}

    @staticmethod
    def matcher_dict_list() -> list[AdvertisementPattern]:
        """Provide BluetoothMatcher definition."""
        return [{"local_name": "TP_*", "connectable": True}]

    @staticmethod
    def device_info() -> dict[str, str]:
        """Return device information for the battery management system."""
        return {"manufacturer": "TianPwr", "model": "SmartBMS"}

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
        self._log.debug("RX BLE data: %s", data)

        # verify that data is long enough
        if len(data) != BMS._DEF_LEN:
            self._log.debug("incorrect frame length")
            return

        if not data.startswith(BMS._HEAD):
            self._log.debug("incorrect SOF.")
            return

        if not data.endswith(BMS._TAIL):
            self._log.debug("incorrect EOF.")
            return

        self._data_final[data[2]] = data.copy()
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
        return [
            (value / 1000)
            for idx in range(8)
            if (
                value := int.from_bytes(
                    data[3 + 2 * idx : 5 + 2 * idx],
                    byteorder="big",
                )
            )
        ]

    @staticmethod
    def _temp_sensors(data: bytearray, sensors: int) -> list[int | float]:
        return [
            int.from_bytes(
                data[3 + idx * 2 : 5 + idx * 2], byteorder="big", signed=True
            )
            / 10
            for idx in range(min(sensors, 6))
        ]

    @staticmethod
    def _cmd(addr: int) -> bytes:
        """Assemble a TianPwr BMS command."""
        return BMS._HEAD + BMS._RDCMD + addr.to_bytes(1) + BMS._TAIL

    async def _async_update(self) -> BMSsample:
        """Update battery status information."""

        self._data_final.clear()
        for cmd in BMS._CMDS:
            await self._await_reply(BMS._cmd(cmd))

        result: BMSsample = BMS._decode_data(self._data_final)

        for cmd in range(
            0x88, 0x89 + min(result.get("cell_count", 0), BMS._MAX_CELLS) // 8
        ):
            await self._await_reply(BMS._cmd(cmd))
            result["cell_voltages"] = result.setdefault(
                "cell_voltages", []
            ) + BMS._cell_voltages(self._data_final.get(cmd, bytearray()))

        if {0x83, 0x87}.issubset(self._data_final):
            result["temp_values"] = [
                int.from_bytes(
                    self._data_final[0x83][idx : idx + 2], byteorder="big", signed=True
                )
                / 10
                for idx in (7, 11)  # take ambient and mosfet temperature
            ] + BMS._temp_sensors(
                self._data_final.get(0x87, bytearray()),
                int(result.get("temp_sensors", 0)),
            )

        return result
