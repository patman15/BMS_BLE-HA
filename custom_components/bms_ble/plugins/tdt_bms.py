"""Module to support TDT BMS."""

from collections.abc import Callable
from typing import Any, Final

from bleak.backends.characteristic import BleakGATTCharacteristic
from bleak.backends.device import BLEDevice
from bleak.uuids import normalize_uuid_str

from .basebms import AdvertisementPattern, BaseBMS, BMSsample, BMSvalue, crc_modbus


class BMS(BaseBMS):
    """TDT BMS implementation."""

    _UUID_CFG: Final[str] = "fffa"
    _HEAD: Final[int] = 0x7E
    _CMD_HEADS: list[int] = [0x7E, 0x1E]  # alternative command head
    _TAIL: Final[int] = 0x0D
    _CMD_VER: Final[int] = 0x00
    _RSP_VER: Final[int] = 0x00
    _CELL_POS: Final[int] = 0x8
    _INFO_LEN: Final[int] = 10  # minimal frame length
    _FIELDS: Final[list[tuple[BMSvalue, int, int, int, bool, Callable[[int], Any]]]] = [
        ("voltage", 0x8C, 2, 2, False, lambda x: float(x / 100)),
        (
            "current",
            0x8C,
            0,
            2,
            False,
            lambda x: float((x & 0x3FFF) / 10 * (-1 if x >> 15 else 1)),
        ),
        ("cycle_charge", 0x8C, 4, 2, False, lambda x: float(x / 10)),
        ("battery_level", 0x8C, 13, 1, False, lambda x: x),
        ("cycles", 0x8C, 8, 2, False, lambda x: x),
    ]  # problem code is not included in the list, but extra
    _CMDS: Final[list[int]] = [*list({field[1] for field in _FIELDS}), 0x8D]

    def __init__(self, ble_device: BLEDevice, reconnect: bool = False) -> None:
        """Initialize BMS."""
        super().__init__(__name__, ble_device, reconnect)
        self._data_final: dict[int, bytearray] = {}
        self._cmd_heads: list[int] = BMS._CMD_HEADS
        self._exp_len: int = 0

    @staticmethod
    def matcher_dict_list() -> list[AdvertisementPattern]:
        """Provide BluetoothMatcher definition."""
        return [{"manufacturer_id": 54976, "connectable": True}]

    @staticmethod
    def device_info() -> dict[str, str]:
        """Return device information for the battery management system."""
        return {"manufacturer": "TDT", "model": "Smart BMS"}

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
        return "fff2"

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

    async def _init_connection(self) -> None:
        await self._await_reply(
            data=b"HiLink", char=BMS._UUID_CFG, wait_for_notify=False
        )
        if (
            ret := int.from_bytes(await self._client.read_gatt_char(BMS._UUID_CFG))
        ) != 0x1:
            self._log.debug("error unlocking BMS: %X", ret)

        await super()._init_connection()

    def _notification_handler(
        self, _sender: BleakGATTCharacteristic, data: bytearray
    ) -> None:
        """Handle the RX characteristics notify event (new data arrives)."""
        self._log.debug("RX BLE data: %s", data)

        if (
            len(data) > BMS._INFO_LEN
            and data[0] in self._cmd_heads
            and len(self._data) >= self._exp_len
        ):
            self._exp_len = BMS._INFO_LEN + int.from_bytes(data[6:8])
            self._data = bytearray()

        self._data += data
        self._log.debug(
            "RX BLE data (%s): %s", "start" if data == self._data else "cnt.", data
        )

        # verify that data is long enough
        if len(self._data) < max(BMS._INFO_LEN, self._exp_len):
            return

        if self._data[-1] != BMS._TAIL:
            self._log.debug("frame end incorrect: %s", self._data)
            return

        if self._data[1] != BMS._RSP_VER:
            self._log.debug("unknown frame version: V%.1f", self._data[1] / 10)
            return

        if self._data[4]:
            self._log.debug("BMS reported error code: 0x%X", self._data[4])
            return

        if (crc := crc_modbus(self._data[:-3])) != int.from_bytes(
            self._data[-3:-1], "big"
        ):
            self._log.debug(
                "invalid checksum 0x%X != 0x%X",
                int.from_bytes(self._data[-3:-1], "big"),
                crc,
            )
            return
        self._data_final[self._data[5]] = self._data
        self._data_event.set()

    @staticmethod
    def _cmd(cmd: int, data: bytearray = bytearray(), cmd_head: int = _HEAD) -> bytes:
        """Assemble a TDT BMS command."""
        assert cmd in (0x8C, 0x8D, 0x92)  # allow only read commands

        frame = bytearray([cmd_head, BMS._CMD_VER, 0x1, 0x3, 0x0, cmd])
        frame += len(data).to_bytes(2, "big", signed=False) + data
        frame += crc_modbus(frame).to_bytes(2, "big") + bytes([BMS._TAIL])

        return bytes(frame)

    @staticmethod
    def _decode_data(data: dict[int, bytearray], offs: int) -> BMSsample:
        result: BMSsample = {}
        for key, cmd, idx, size, sign, func in BMS._FIELDS:
            result[key] = func(
                int.from_bytes(
                    data[cmd][idx + offs : idx + offs + size],
                    byteorder="big",
                    signed=sign,
                )
            )
        return result

    @staticmethod
    def _cell_voltages(data: bytearray) -> list[float]:
        return [
            int.from_bytes(
                data[BMS._CELL_POS + 1 + idx * 2 : BMS._CELL_POS + 1 + idx * 2 + 2],
                byteorder="big",
                signed=False,
            )
            / 1000
            for idx in range(data[BMS._CELL_POS])
        ]

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

    async def _async_update(self) -> BMSsample:
        """Update battery status information."""

        for head in self._cmd_heads:
            try:
                for cmd in BMS._CMDS:
                    await self._await_reply(BMS._cmd(cmd, cmd_head=head))
                self._cmd_heads = [head]  # set to single head for further commands
                break
            except TimeoutError:
                ...  # try next command head
        else:
            raise TimeoutError

        result: BMSsample = {"cell_count": int(self._data_final[0x8C][BMS._CELL_POS])}
        result["temp_sensors"] = int(
            self._data_final[0x8C][BMS._CELL_POS + int(result["cell_count"]) * 2 + 1]
        )

        result["cell_voltages"] = BMS._cell_voltages(self._data_final[0x8C])
        result["temp_values"] = BMS._temp_sensors(
            self._data_final[0x8C],
            result["temp_sensors"],
            BMS._CELL_POS + result.get("cell_count", 0) * 2 + 2,
        )
        idx: Final[int] = int(
            result.get("cell_count", 0) + result.get("temp_sensors", 0)
        )
        result |= BMS._decode_data(
            self._data_final,
            BMS._CELL_POS + idx * 2 + 2,
        )
        result["problem_code"] = int.from_bytes(
            self._data_final[0x8D][BMS._CELL_POS + idx + 6 : BMS._CELL_POS + idx + 8]
        )

        self._data_final.clear()

        return result
