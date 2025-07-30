"""Module to support ANT BMS."""

from collections.abc import Callable
from typing import Any, Final

from bleak.backends.characteristic import BleakGATTCharacteristic
from bleak.backends.device import BLEDevice
from bleak.uuids import normalize_uuid_str

from .basebms import AdvertisementPattern, BaseBMS, BMSsample, BMSvalue, crc_modbus


class BMS(BaseBMS):
    """ANT BMS implementation."""

    _HEAD: Final[bytes] = b"\x7e\xa1"
    _TAIL: Final[bytes] = b"\xaa\x55"
    _MIN_LEN: Final[int] = 10  # frame length without data
    _CMD_STAT: Final[int] = 0x01
    _CMD_DEV: Final[int] = 0x02
    _TEMP_POS: Final[int] = 8
    _MAX_TEMPS: Final[int] = 6
    _CELL_COUNT: Final[int] = 9
    _CELL_POS: Final[int] = 34
    _MAX_CELLS: Final[int] = 32
    _FIELDS: Final[list[tuple[BMSvalue, int, int, bool, Callable[[int], Any]]]] = [
        ("battery_charging", 7, 1, False, lambda x: x == 0x2),
        ("voltage", 38, 2, False, lambda x: x / 100),
        ("current", 40, 2, True, lambda x: x / 10),
        ("design_capacity", 50, 4, False, lambda x: x // 100000),
        ("battery_level", 42, 2, False, lambda x: x),
        ("cycle_charge", 54, 4, False, lambda x: x // 100000),
        # ("cycles", 14, 2, False, lambda x: x),
        ("delta_voltage", 82, 2, False, lambda x: x / 1000),
        ("power", 62, 4, True, lambda x: x / 1),
    ]

    def __init__(self, ble_device: BLEDevice, reconnect: bool = False) -> None:
        """Initialize BMS."""
        super().__init__(__name__, ble_device, reconnect)
        self._data_final: bytearray = bytearray()
        self._valid_reply: int = BMS._CMD_STAT | 0x10  # valid reply mask
        self._exp_len: int = 0

    @staticmethod
    def matcher_dict_list() -> list[AdvertisementPattern]:
        """Provide BluetoothMatcher definition."""
        return [
            {
                "local_name": "ANT-BLE*",
                "service_uuid": BMS.uuid_services()[0],
                "manufacturer_id": 0x2313,
                "connectable": True,
            }
        ]

    @staticmethod
    def device_info() -> dict[str, str]:
        """Return device information for the battery management system."""
        return {"manufacturer": "ANT", "model": "Smart BMS"}

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
        return "ffe1"

    @staticmethod
    def _calc_values() -> frozenset[BMSvalue]:
        return frozenset(
            {"cycle_capacity", "temperature"}
        )  # calculate further values from BMS provided set ones

    async def _init_connection(
        self, char_notify: BleakGATTCharacteristic | int | str | None = None
    ) -> None:
        """Initialize RX/TX characteristics and protocol state."""
        await super()._init_connection(char_notify)
        self._exp_len = 0
        self._valid_reply = BMS._CMD_DEV | 0x10
        await self._await_reply(BMS._cmd(BMS._CMD_DEV, 0x026C, 0x20))  # TODO: parse
        self._valid_reply = BMS._CMD_STAT | 0x10

    def _notification_handler(
        self, _sender: BleakGATTCharacteristic, data: bytearray
    ) -> None:
        """Handle the RX characteristics notify event (new data arrives)."""

        if data.startswith(BMS._HEAD) and (
            len(self._data) >= self._exp_len or self._exp_len == 0
        ):
            self._data = bytearray()
            self._exp_len = data[5] + BMS._MIN_LEN

        self._data += data
        self._log.debug(
            "RX BLE data (%s): %s", "start" if data == self._data else "cnt.", data
        )

        # verify that data is long enough
        if len(self._data) < self._exp_len:
            return

        if (self._data[2] >> 4) != 0x1:
            self._log.debug("invalid response (0x%X)", self._data[2])
            return

        if not self._data.endswith(BMS._TAIL):
            self._log.debug("invalid frame end")
            return

        if len(self._data) != self._exp_len:
            self._log.debug(
                "invalid frame length %d != %d", len(self._data), self._exp_len
            )
            # return

        if self._data[2] != self._valid_reply:
            self._log.debug("unexpected response (type 0x%X)", self._data[2])
            return

        if (crc := crc_modbus(self._data[1:-5])) != int.from_bytes(
            self._data[-4:-2], "little"
        ):
            self._log.debug(
                "invalid checksum 0x%X != 0x%X",
                int.from_bytes(self._data[-4:-2], "little"),
                crc,
            )
            # return

        self._data_final = self._data.copy()
        self._data_event.set()

    @staticmethod
    def _cmd(cmd: int, adr: int, value: int) -> bytes:
        """Assemble a ANT BMS command."""
        frame: bytearray = (
            bytearray([*BMS._HEAD, cmd & 0xFF])
            + adr.to_bytes(2, "little")
            + int.to_bytes(value & 0xFF, 1)
        )
        frame.extend(int.to_bytes(crc_modbus(frame[1:]), 2, "little"))
        return bytes(frame) + BMS._TAIL

    @staticmethod
    def _decode_data(data: bytearray, offs: int = 0) -> BMSsample:
        result: BMSsample = {}
        for key, idx, size, sign, func in BMS._FIELDS:
            result[key] = func(
                int.from_bytes(
                    data[idx + offs : idx + offs + size],
                    byteorder="little",
                    signed=sign,
                )
            )
        return result

    @staticmethod
    def _temp_sensors(data: bytearray, sensors: int, offs: int) -> list[float]:
        return [
            float(int.from_bytes(data[idx : idx + 2], byteorder="little", signed=True))
            for idx in range(offs, offs + sensors * 2, 2)
        ]

    async def _async_update(self) -> BMSsample:
        """Update battery status information."""
        await self._await_reply(BMS._cmd(BMS._CMD_STAT, 0, 0xBE))

        result: BMSsample = {}
        protection: Final[int] = int.from_bytes(
            self._data_final[10:18], byteorder="little", signed=False
        )
        warning: Final[int] = int.from_bytes(
            self._data_final[18:26], byteorder="little", signed=False
        )
        result["problem_code"] = protection | warning
        result["cell_count"] = int(self._data_final[BMS._CELL_COUNT])
        result["cell_voltages"] = BMS._cell_voltages(
            self._data_final,
            cells=result.get("cell_count", 0),
            start=BMS._CELL_POS,
            byteorder="little",
        )
        result["temp_sensors"] = int(self._data_final[BMS._TEMP_POS])
        result["temp_values"] = BMS._temp_sensors(
            self._data_final,
            result.get("temp_sensors", 0) + 2,  # + MOSFET, balancer temperature
            BMS._CELL_POS + result.get("cell_count", 0) * 2,
        )
        result.update(
            BMS._decode_data(
                self._data_final,
                (result.get("temp_sensors", 0) + result.get("cell_count", 0)) * 2,
            )
        )

        return result
