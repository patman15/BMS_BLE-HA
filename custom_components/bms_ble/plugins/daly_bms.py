"""Module to support Daly Smart BMS."""

from collections.abc import Callable
from typing import Any, Final

from bleak.backends.characteristic import BleakGATTCharacteristic
from bleak.backends.device import BLEDevice
from bleak.uuids import normalize_uuid_str

from .basebms import AdvertisementPattern, BaseBMS, BMSsample, BMSvalue, crc_modbus


class BMS(BaseBMS):
    """Daly Smart BMS class implementation."""

    HEAD_READ: Final[bytes] = b"\xd2\x03"
    CMD_INFO: Final[bytes] = b"\x00\x00\x00\x3e\xd7\xb9"
    MOS_INFO: Final[bytes] = b"\x00\x3e\x00\x09\xf7\xa3"
    HEAD_LEN: Final[int] = 3
    CRC_LEN: Final[int] = 2
    MAX_CELLS: Final[int] = 32
    MAX_TEMP: Final[int] = 8
    INFO_LEN: Final[int] = 84 + HEAD_LEN + CRC_LEN + MAX_CELLS + MAX_TEMP
    MOS_TEMP_POS: Final[int] = HEAD_LEN + 8
    _FIELDS: Final[list[tuple[BMSvalue, int, int, Callable[[int], Any]]]] = [
        ("voltage", 80 + HEAD_LEN, 2, lambda x: float(x / 10)),
        ("current", 82 + HEAD_LEN, 2, lambda x: float((x - 30000) / 10)),
        ("battery_level", 84 + HEAD_LEN, 2, lambda x: float(x / 10)),
        ("cycle_charge", 96 + HEAD_LEN, 2, lambda x: float(x / 10)),
        ("cell_count", 98 + HEAD_LEN, 2, lambda x: min(x, BMS.MAX_CELLS)),
        ("temp_sensors", 100 + HEAD_LEN, 2, lambda x: min(x, BMS.MAX_TEMP)),
        ("cycles", 102 + HEAD_LEN, 2, lambda x: x),
        ("delta_voltage", 112 + HEAD_LEN, 2, lambda x: float(x / 1000)),
        ("problem_code", 116 + HEAD_LEN, 8, lambda x: x % 2**64),
    ]

    def __init__(self, ble_device: BLEDevice, reconnect: bool = False) -> None:
        """Intialize private BMS members."""
        super().__init__(__name__, ble_device, reconnect)

    @staticmethod
    def matcher_dict_list() -> list[AdvertisementPattern]:
        """Provide BluetoothMatcher definition."""
        return [
            AdvertisementPattern(
                local_name="DL-*",
                service_uuid=BMS.uuid_services()[0],
                connectable=True,
            )
        ] + [
            AdvertisementPattern(
                manufacturer_id=m_id,
                connectable=True,
            )
            for m_id in (0x102, 0x104, 0x0302)
        ]

    @staticmethod
    def device_info() -> dict[str, str]:
        """Return device information for the battery management system."""
        return {"manufacturer": "Daly", "model": "Smart BMS"}

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
                "cycle_capacity",
                "power",
                "battery_charging",
                "runtime",
                "temperature",
            }
        )

    def _notification_handler(
        self, _sender: BleakGATTCharacteristic, data: bytearray
    ) -> None:
        self._log.debug("RX BLE data: %s", data)

        if (
            len(data) < BMS.HEAD_LEN
            or data[0:2] != BMS.HEAD_READ
            or int(data[2]) + 1 != len(data) - len(BMS.HEAD_READ) - BMS.CRC_LEN
        ):
            self._log.debug("response data is invalid")
            return

        if (crc := crc_modbus(data[:-2])) != int.from_bytes(
            data[-2:], byteorder="little"
        ):
            self._log.debug(
                "invalid checksum 0x%X != 0x%X",
                int.from_bytes(data[-2:], byteorder="little"),
                crc,
            )
            self._data.clear()
            return

        self._data = data
        self._data_event.set()

    @staticmethod
    def _cell_voltages(data: bytearray, cells: int) -> list[float]:
        return [
            int.from_bytes(
                data[BMS.HEAD_LEN + 2 * idx : BMS.HEAD_LEN + 2 * idx + 2],
                byteorder="big",
                signed=True,
            )
            / 1000
            for idx in range(cells)
        ]

    @staticmethod
    def _temp_sensors(data: bytearray, sensors: int, offs: int) -> list[float]:
        return [
            float(
                int.from_bytes(data[idx : idx + 2], byteorder="big", signed=True) - 40
            )
            for idx in range(offs, offs + sensors * 2, 2)
        ]

    async def _async_update(self) -> BMSsample:
        """Update battery status information."""
        data: BMSsample = {}
        try:
            # request MOS temperature (possible outcome: response, empty response, no response)
            await self._await_reply(BMS.HEAD_READ + BMS.MOS_INFO)

            if sum(self._data[BMS.MOS_TEMP_POS :][:2]):
                self._log.debug("MOS info: %s", self._data)
                data["temp_values"] = [
                    float(
                        int.from_bytes(
                            self._data[BMS.MOS_TEMP_POS :][:2],
                            byteorder="big",
                            signed=True,
                        )
                        - 40
                    )
                ]
        except TimeoutError:
            self._log.debug("no MOS temperature available.")

        await self._await_reply(BMS.HEAD_READ + BMS.CMD_INFO)

        if len(self._data) != BMS.INFO_LEN:
            self._log.debug("incorrect frame length: %i", len(self._data))
            return {}

        for key, idx, size, func in BMS._FIELDS:
            data[key] = func(
                int.from_bytes(
                    self._data[idx : idx + size], byteorder="big", signed=True
                )
            )

        # get temperatures
        data.setdefault("temp_values", []).extend(
            self._temp_sensors(
                self._data, data.get("temp_sensors", 0), 64 + BMS.HEAD_LEN
            )
        )

        # get cell voltages
        data["cell_voltages"] = self._cell_voltages(
            self._data, int(data.get("cell_count", 0))
        )

        return data
