"""Module to support Seplos v2 BMS."""

from collections.abc import Callable
from typing import Any, Final

from bleak.backends.characteristic import BleakGATTCharacteristic
from bleak.backends.device import BLEDevice
from bleak.uuids import normalize_uuid_str

from .basebms import AdvertisementPattern, BaseBMS, BMSsample, BMSvalue, crc_xmodem


class BMS(BaseBMS):
    """Seplos v2 BMS implementation."""

    _HEAD: Final[bytes] = b"\x7e"
    _TAIL: Final[bytes] = b"\x0d"
    _CMD_VER: Final[int] = 0x10  # TX protocol version
    _RSP_VER: Final[int] = 0x14  # RX protocol version
    _MIN_LEN: Final[int] = 10
    _MAX_SUBS: Final[int] = 0xF
    _CELL_POS: Final[int] = 9
    _PRB_MAX: Final[int] = 8  # max number of alarm event bytes
    _PRB_MASK: Final[int] = ~0x82FFFF  # ignore byte 7-8 + byte 6 (bit 7,2)
    _PFIELDS: Final[  # Seplos V2: single machine data
        list[tuple[BMSvalue, int, int, int, bool, Callable[[int], Any]]]
    ] = [
        ("voltage", 0x61, 2, 2, False, lambda x: x / 100),
        ("current", 0x61, 0, 2, True, lambda x: x / 100),  # /10 for 0x62
        ("cycle_charge", 0x61, 4, 2, False, lambda x: x / 100),  # /10 for 0x62
        ("cycles", 0x61, 13, 2, False, lambda x: x),
        ("battery_level", 0x61, 9, 2, False, lambda x: x / 10),
    ]
    _CMDS: Final[list[tuple[int, bytes]]] = [(0x51, b""), (0x61, b"\x00"), (0x62, b"")]

    def __init__(self, ble_device: BLEDevice, reconnect: bool = False) -> None:
        """Initialize BMS."""
        super().__init__(__name__, ble_device, reconnect)
        self._data_final: dict[int, bytearray] = {}
        self._exp_len: int = BMS._MIN_LEN
        self._exp_reply: set[int] = set()

    @staticmethod
    def matcher_dict_list() -> list[AdvertisementPattern]:
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
        if (
            len(data) > BMS._MIN_LEN
            and data.startswith(BMS._HEAD)
            and len(self._data) >= self._exp_len
        ):
            self._exp_len = BMS._MIN_LEN + int.from_bytes(data[5:7])
            self._data = bytearray()

        self._data += data
        self._log.debug(
            "RX BLE data (%s): %s", "start" if data == self._data else "cnt.", data
        )

        # verify that data is long enough
        if len(self._data) < self._exp_len:
            return

        if not self._data.endswith(BMS._TAIL):
            self._log.debug("incorrect frame end: %s", self._data)
            return

        if self._data[1] != BMS._RSP_VER:
            self._log.debug("unknown frame version: V%.1f", self._data[1] / 10)
            return

        if self._data[4]:
            self._log.debug("BMS reported error code: 0x%X", self._data[4])
            return

        if (crc := crc_xmodem(self._data[1:-3])) != int.from_bytes(self._data[-3:-1]):
            self._log.debug(
                "invalid checksum 0x%X != 0x%X",
                crc,
                int.from_bytes(self._data[-3:-1]),
            )
            return

        self._log.debug(
            "address: 0x%X, function: 0x%X, return: 0x%X",
            self._data[2],
            self._data[3],
            self._data[4],
        )

        self._data_final[self._data[3]] = self._data
        try:
            self._exp_reply.remove(self._data[3])
            self._data_event.set()
        except KeyError:
            self._log.debug("unexpected reply: 0x%X", self._data[3])

    async def _init_connection(
        self, char_notify: BleakGATTCharacteristic | int | str | None = None
    ) -> None:
        """Initialize protocol state."""
        await super()._init_connection()
        self._exp_len = BMS._MIN_LEN

    @staticmethod
    def _cmd(cmd: int, address: int = 0, data: bytearray = bytearray()) -> bytes:
        """Assemble a Seplos V2 BMS command."""
        assert cmd in (0x47, 0x51, 0x61, 0x62, 0x04)  # allow only read commands
        frame = bytearray([*BMS._HEAD, BMS._CMD_VER, address, 0x46, cmd])
        frame += len(data).to_bytes(2, "big", signed=False) + data
        frame += int.to_bytes(crc_xmodem(frame[1:]), 2, byteorder="big") + BMS._TAIL
        return bytes(frame)

    @staticmethod
    def _decode_data(data: dict[int, bytearray], offs: int) -> BMSsample:
        result: BMSsample = {}
        for key, cmd, idx, size, sign, func in BMS._PFIELDS:
            if idx + offs + size <= len(data[cmd]) - 3:
                result[key] = func(
                    int.from_bytes(
                        data[cmd][idx + offs : idx + offs + size],
                        byteorder="big",
                        signed=sign,
                    )
                )
        return result

    @staticmethod
    def _temp_sensors(data: bytearray, sensors: int, offs: int) -> list[int | float]:
        return [
            (value - 2731.5) / 10
            for idx in range(sensors)
            if (
                value := int.from_bytes(
                    data[offs + idx * 2 : offs + (idx + 1) * 2],
                    byteorder="big",
                    signed=False,
                )
            )
        ]

    @staticmethod
    def _cell_voltages(data: bytearray) -> list[float]:
        return [
            int.from_bytes(
                data[10 + idx * 2 : 10 + idx * 2 + 2], byteorder="big", signed=False
            )
            / 1000
            for idx in range(data[BMS._CELL_POS])
        ]

    async def _async_update(self) -> BMSsample:
        """Update battery status information."""

        for cmd, data in BMS._CMDS:
            self._exp_reply.add(cmd)
            await self._await_reply(BMS._cmd(cmd, data=bytearray(data)))

        result: BMSsample = {}
        result["cell_count"] = int(self._data_final[0x61][BMS._CELL_POS])
        result["temp_sensors"] = int(
            self._data_final[0x61][BMS._CELL_POS + int(result["cell_count"]) * 2 + 1]
        )
        result |= BMS._decode_data(
            self._data_final,
            BMS._CELL_POS
            + (result.get("cell_count", 0) + result.get("temp_sensors", 0)) * 2
            + 2,
        )

        # get extention pack count from parallel data (main pack)
        result["pack_count"] = int.from_bytes(
            self._data_final[0x51][42:43], byteorder="big"
        )

        # get alarms from parallel data (main pack)
        alarm_events: Final[int] = min(
            int.from_bytes(self._data_final[0x62][46:47]), BMS._PRB_MAX
        )
        result["problem_code"] = (
            int.from_bytes(
                self._data_final[0x62][47 : 47 + alarm_events], byteorder="big"
            )
            & BMS._PRB_MASK
        )

        result["cell_voltages"] = BMS._cell_voltages(self._data_final[0x61])
        result["temp_values"] = BMS._temp_sensors(
            self._data_final[0x61],
            result["temp_sensors"],
            BMS._CELL_POS + result.get("cell_count", 0) * 2 + 2,
        )

        self._data_final.clear()

        return result
