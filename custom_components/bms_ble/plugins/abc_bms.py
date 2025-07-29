"""Module to support ABC BMS."""

from collections.abc import Callable
import contextlib
from typing import Any, Final

from bleak.backends.characteristic import BleakGATTCharacteristic
from bleak.backends.device import BLEDevice
from bleak.uuids import normalize_uuid_str

from .basebms import AdvertisementPattern, BaseBMS, BMSsample, BMSvalue, crc8


class BMS(BaseBMS):
    """ABC BMS implementation."""

    _HEAD_CMD: Final[int] = 0xEE
    _HEAD_RESP: Final[bytes] = b"\xcc"
    _INFO_LEN: Final[int] = 0x14
    _EXP_REPLY: Final[dict[int, set[int]]] = {  # wait for these replies
        0xC0: {0xF1},
        0xC1: {0xF0, 0xF2},
        0xC2: {0xF0, 0xF3, 0xF4},  # 4 cells per F4 message
        0xC3: {0xF5, 0xF6, 0xF7, 0xF8, 0xFA},
        0xC4: {0xF9},
    }
    _FIELDS: Final[list[tuple[BMSvalue, int, int, int, bool, Callable[[int], Any]]]] = [
        ("temp_sensors", 0xF2, 4, 1, False, lambda x: x),
        ("voltage", 0xF0, 2, 3, False, lambda x: x / 1000),
        ("current", 0xF0, 5, 3, True, lambda x: x / 1000),
        # ("design_capacity", 0xF0, 8, 3, False, lambda x: x / 1000),
        ("battery_level", 0xF0, 16, 1, False, lambda x: x),
        ("cycle_charge", 0xF0, 11, 3, False, lambda x: x / 1000),
        ("cycles", 0xF0, 14, 2, False, lambda x: x),
        (  # only first bit per byte is used
            "problem_code",
            0xF9,
            2,
            16,
            False,
            lambda x: sum(((x >> (i * 8)) & 1) << i for i in range(16)),
        ),
    ]
    _RESPS: Final[set[int]] = {field[1] for field in _FIELDS} | {0xF4}  # cell voltages

    def __init__(self, ble_device: BLEDevice, reconnect: bool = False) -> None:
        """Initialize BMS."""
        super().__init__(__name__, ble_device, reconnect)
        self._data_final: dict[int, bytearray] = {}
        self._exp_reply: set[int] = set()

    @staticmethod
    def matcher_dict_list() -> list[AdvertisementPattern]:
        """Provide BluetoothMatcher definition."""
        return [
            {
                "local_name": pattern,
                "service_uuid": normalize_uuid_str("fff0"),
                "connectable": True,
            }
            for pattern in ("ABC-*", "SOK-*")  # "NB-*", "Hoover",
        ]

    @staticmethod
    def device_info() -> dict[str, str]:
        """Return device information for the battery management system."""
        return {"manufacturer": "Chunguang Song", "model": "ABC BMS"}

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

        if not data.startswith(BMS._HEAD_RESP):
            self._log.debug("Incorrect frame start")
            return

        if len(data) != BMS._INFO_LEN:
            self._log.debug("Incorrect frame length")
            return

        if (crc := crc8(data[:-1])) != data[-1]:
            self._log.debug("invalid checksum 0x%X != 0x%X", data[-1], crc)
            return

        if data[1] == 0xF4 and 0xF4 in self._data_final:
            # expand cell voltage frame with all parts
            self._data_final[0xF4] = bytearray(self._data_final[0xF4][:-2] + data[2:])
        else:
            self._data_final[data[1]] = data.copy()

        self._exp_reply.discard(data[1])

        if not self._exp_reply:  # check if all expected replies are received
            self._data_event.set()

    @staticmethod
    def _cmd(cmd: bytes) -> bytes:
        """Assemble a ABC BMS command."""
        frame = bytearray([BMS._HEAD_CMD, cmd[0], 0x00, 0x00, 0x00])
        frame.append(crc8(frame))
        return bytes(frame)

    @staticmethod
    def _temp_sensors(data: bytearray, sensors: int) -> list[int | float]:
        return [
            int.from_bytes(data[5 + idx : 6 + idx], byteorder="little", signed=True)
            for idx in range(sensors)
        ]

    @staticmethod
    def _decode_data(data: dict[int, bytearray]) -> BMSsample:
        result: BMSsample = {}
        for key, cmd, idx, size, sign, func in BMS._FIELDS:
            result[key] = func(
                int.from_bytes(
                    data[cmd][idx : idx + size], byteorder="little", signed=sign
                )
            )
        return result

    async def _async_update(self) -> BMSsample:
        """Update battery status information."""
        self._data_final.clear()
        for cmd in (0xC1, 0xC2, 0xC4):
            self._exp_reply.update(BMS._EXP_REPLY[cmd])
            with contextlib.suppress(TimeoutError):
                await self._await_reply(BMS._cmd(bytes([cmd])))

        # check all repsonses are here, 0xF9 is not mandatory (not all BMS report it)
        self._data_final.setdefault(0xF9, bytearray())
        if not BMS._RESPS.issubset(set(self._data_final.keys())):
            self._log.debug("Incomplete data set %s", self._data_final.keys())
            raise TimeoutError("BMS data incomplete.")

        result: BMSsample = BMS._decode_data(self._data_final)
        return result | {
            "cell_voltages": BMS._cell_voltages(
                self._data_final[0xF4],
                cells=(len(self._data_final[0xF4]) - 4) // 4,
                start=3,
                byteorder="little",
                size=3,
                step=4,
            ),
            "temp_values": BMS._temp_sensors(
                self._data_final[0xF2], int(result.get("temp_sensors", 0))
            ),
        }
