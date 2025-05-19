"""Module to support JBD Smart BMS."""

from collections.abc import Callable
from typing import Any, Final

from bleak.backends.characteristic import BleakGATTCharacteristic
from bleak.backends.device import BLEDevice
from bleak.uuids import normalize_uuid_str

from .basebms import AdvertisementPattern, BaseBMS, BMSsample, BMSvalue


class BMS(BaseBMS):
    """JBD Smart BMS class implementation."""

    HEAD_RSP: Final[bytes] = bytes([0xDD])  # header for responses
    HEAD_CMD: Final[bytes] = bytes([0xDD, 0xA5])  # read header for commands
    TAIL: Final[int] = 0x77  # tail for command
    INFO_LEN: Final[int] = 7  # minimum frame size
    BASIC_INFO: Final[int] = 23  # basic info data length
    _FIELDS: Final[list[tuple[BMSvalue, int, int, bool, Callable[[int], Any]]]] = [
        ("temp_sensors", 26, 1, False, lambda x: x),  # count is not limited
        ("voltage", 4, 2, False, lambda x: float(x / 100)),
        ("current", 6, 2, True, lambda x: float(x / 100)),
        ("battery_level", 23, 1, False, lambda x: x),
        ("cycle_charge", 8, 2, False, lambda x: float(x / 100)),
        ("cycles", 12, 2, False, lambda x: x),
        ("problem_code", 20, 2, False, lambda x: x),
    ]  # general protocol v4

    def __init__(self, ble_device: BLEDevice, reconnect: bool = False) -> None:
        """Intialize private BMS members."""
        super().__init__(__name__, ble_device, reconnect)
        self._data_final: bytearray = bytearray()

    @staticmethod
    def matcher_dict_list() -> list[AdvertisementPattern]:
        """Provide BluetoothMatcher definition."""
        return [
            AdvertisementPattern(
                local_name=pattern,
                service_uuid=BMS.uuid_services()[0],
                connectable=True,
            )
            for pattern in (
                "JBD-*",
                "SP0?S*",
                "SP1?S*",
                "SP2?S*",
                "AP2?S*",
                "GJ-*",  # accurat batteries
                "SX1*",  # Supervolt v3
                "DP04S*",  # ECO-WORTHY, DCHOUSE
                "ECO-LFP*",  # ECO-WORTHY rack (use m_id?)
                "121?0*",  # Eleksol, Ultimatron
                "12200*",
                "12300*",
                "LT40AH",  # LionTron
                "PKT*",  # Perfektium
                "gokwh*",
                "OGR-*",  # OGRPHY
            )
        ] + [
            AdvertisementPattern(
                service_uuid=BMS.uuid_services()[0],
                manufacturer_id=m_id,
                connectable=True,
            )
            for m_id in (0x7B, 0x3E70, 0xC1A4)
            # SBL, LISMART1240LX/LISMART1255LX,
            # LionTron XL19110253 / EPOCH batteries 12.8V 460Ah - 12460A-H
        ]

    @staticmethod
    def device_info() -> dict[str, str]:
        """Return device information for the battery management system."""
        return {"manufacturer": "Jiabaida", "model": "Smart BMS"}

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
                "power",
                "battery_charging",
                "cycle_capacity",
                "runtime",
                "delta_voltage",
                "temperature",
            }
        )

    def _notification_handler(
        self, _sender: BleakGATTCharacteristic, data: bytearray
    ) -> None:
        # check if answer is a heading of basic info (0x3) or cell block info (0x4)
        if (
            data.startswith(self.HEAD_RSP)
            and len(self._data) > self.INFO_LEN
            and data[1] in (0x03, 0x04)
            and data[2] == 0x00
            and len(self._data) >= self.INFO_LEN + self._data[3]
        ):
            self._data = bytearray()

        self._data += data
        self._log.debug(
            "RX BLE data (%s): %s", "start" if data == self._data else "cnt.", data
        )

        # verify that data is long enough
        if (
            len(self._data) < BMS.INFO_LEN
            or len(self._data) < BMS.INFO_LEN + self._data[3]
        ):
            return

        # check correct frame ending
        frame_end: Final[int] = BMS.INFO_LEN + self._data[3] - 1
        if self._data[frame_end] != BMS.TAIL:
            self._log.debug("incorrect frame end (length: %i).", len(self._data))
            return

        if (crc := BMS._crc(self._data[2 : frame_end - 2])) != int.from_bytes(
            self._data[frame_end - 2 : frame_end], "big"
        ):
            self._log.debug(
                "invalid checksum 0x%X != 0x%X",
                int.from_bytes(self._data[frame_end - 2 : frame_end], "big"),
                crc,
            )
            return

        if len(self._data) != BMS.INFO_LEN + self._data[3]:
            self._log.debug("wrong data length (%i): %s", len(self._data), self._data)

        self._data_final = self._data
        self._data_event.set()

    @staticmethod
    def _crc(frame: bytearray) -> int:
        """Calculate JBD frame CRC."""
        return 0x10000 - sum(frame)

    @staticmethod
    def _cmd(cmd: bytes) -> bytes:
        """Assemble a JBD BMS command."""
        frame = bytearray([*BMS.HEAD_CMD, cmd[0], 0x00])
        frame.extend([*BMS._crc(frame[2:4]).to_bytes(2, "big"), BMS.TAIL])
        return bytes(frame)

    @staticmethod
    def _decode_data(data: bytearray) -> BMSsample:
        result: BMSsample = {}
        for key, idx, size, sign, func in BMS._FIELDS:
            result[key] = func(
                int.from_bytes(data[idx : idx + size], byteorder="big", signed=sign)
            )
        return result

    @staticmethod
    def _cell_voltages(data: bytearray) -> list[float]:
        return [
            int.from_bytes(
                data[4 + idx * 2 : 4 + idx * 2 + 2], byteorder="big", signed=False
            )
            / 1000
            for idx in range(int(data[3] / 2))
        ]

    @staticmethod
    def _temp_sensors(data: bytearray, sensors: int) -> list[float]:
        return [
            (int.from_bytes(data[idx : idx + 2], byteorder="big") - 2731) / 10
            for idx in range(27, 27 + sensors * 2, 2)
        ]

    async def _async_update(self) -> BMSsample:
        """Update battery status information."""
        data: BMSsample = {}
        await self._await_reply(BMS._cmd(b"\x03"))
        data = BMS._decode_data(self._data_final)
        data["temp_values"] = BMS._temp_sensors(
            self._data_final, int(data.get("temp_sensors", 0))
        )

        await self._await_reply(BMS._cmd(b"\x04"))
        data["cell_voltages"] = BMS._cell_voltages(self._data_final)

        return data
