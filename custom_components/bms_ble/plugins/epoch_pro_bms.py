"""Module to support Epoch Pro BMS."""

from collections.abc import Callable
from typing import Any, Final

from bleak.backends.characteristic import BleakGATTCharacteristic
from bleak.backends.device import BLEDevice
from bleak.uuids import normalize_uuid_str

from .basebms import (
    AdvertisementPattern,
    BaseBMS,
    BMSpackvalue,
    BMSsample,
    BMSvalue,
    crc_modbus,
)


class BMS(BaseBMS):
    """Epoch Pro BMS implementation."""

    _HEAD: Final[bytes] = b"\xfa"
    _CMDS: Final[set[int]] = {0xF3}
    _VER: Final[bytes] = b"\x16"  # version 1.6?
    _CELLNUM_POS: Final[int] = 55  # number of cells in pack
    _CELL_POS: Final[int] = 77  # position of first cell voltage in pack
    _TEMPNUM_POS: Final[int] = 56  # number of temperature sensors in pack
    _TEMP_POS: Final[int] = 109  # position of first temperature sensor in pack
    _HEAD_LEN: Final[int] = 5
    _MIN_LEN: Final[int] = 7  # HEAD, CMD, VER, DEV, LEN, CRC (2 bytes)

    _FIELDS: Final[list[tuple[BMSvalue, int, int, bool, Callable[[int], Any]]]] = [
        ("temperature", 18, 2, True, lambda x: x / 10),
        ("voltage", 14, 2, False, lambda x: x / 100),
        ("current", 16, 2, True, lambda x: x),
        ("pack_count", 42, 2, False, lambda x: x),
        # ("cycle_charge", 8, 4, False, lambda x: float(BMS._swap32(x) / 100)),
        # ("cycles", 46, 2, False, lambda x: x),
        #("design_capacity", 4, 4, False, lambda x: float(x / 100)),
        ("battery_level", 8, 2, False, lambda x: x),
        # ("problem_code", 100, 8, False, lambda x: x),
    ]

    _PFIELDS: Final[list[tuple[BMSpackvalue, int, bool, Callable[[int], Any]]]] = [
        ("pack_voltages", 46, False, lambda x: x / 100),
        ("pack_currents", 48, True, lambda x: x / 100),
        ("pack_battery_levels", 66, False, lambda x: x / 10),
        ("pack_cycles", 16, False, lambda x: x),
    ]

    def __init__(self, ble_device: BLEDevice, reconnect: bool = False) -> None:
        """Initialize BMS."""
        super().__init__(__name__, ble_device, reconnect)
        self._pkglen: int = 0
        self._data_final: dict[int, bytearray] = {}

    @staticmethod
    def matcher_dict_list() -> list[AdvertisementPattern]:
        """Provide BluetoothMatcher definition."""
        return [
            {
                "local_name": "EpochGC2-*",
                "service_uuid": BMS.uuid_services()[0],
                "connectable": True,
            }
        ]

    @staticmethod
    def device_info() -> dict[str, str]:
        """Return device information for the battery management system."""
        return {"manufacturer": "Epoch", "model": "Pro"}

    @staticmethod
    def uuid_services() -> list[str]:
        """Return list of 128-bit UUIDs of services required by BMS."""
        return [normalize_uuid_str("ffe0")]

    @staticmethod
    def uuid_rx() -> str:
        """Return 16-bit UUID of characteristic that provides notification/read property."""
        return "ffe4"

    @staticmethod
    def uuid_tx() -> str:
        """Return 16-bit UUID of characteristic that provides write property."""
        return "ffe1"

    @staticmethod
    def _calc_values() -> frozenset[BMSvalue]:
        return frozenset(
            {"power", "battery_charging"}
        )  # calculate further values from BMS provided set ones

    def _notification_handler(
        self, _sender: BleakGATTCharacteristic, data: bytearray
    ) -> None:
        """Handle the RX characteristics notify event (new data arrives)."""

        # Check for a valid new packet header
        if (
            len(data) >= BMS._MIN_LEN
            and data[0:1] == BMS._HEAD
            and data[1] in BMS._CMDS
            and data[2:3] == BMS._VER
        ):
            self._data = bytearray()
            self._pkglen = data[4] + BMS._MIN_LEN

        self._data += data
        self._log.debug(
            "RX BLE data (%s): %s", "start" if data == self._data else "cnt.", data
        )

        # verify that data is long enough
        if self._pkglen and len(self._data) < self._pkglen:
            return

        if (crc := crc_modbus(self._data[: self._pkglen - 2])) != int.from_bytes(
            self._data[self._pkglen - 2 : self._pkglen], "little"
        ):
            self._log.debug(
                "invalid checksum 0x%X != 0x%X",
                int.from_bytes(self._data[self._pkglen - 2 : self._pkglen], "little"),
                crc,
            )
            self._data = bytearray()
            return

        if len(self._data) != self._pkglen:
            self._log.debug(
                "wrong data length (%i!=%s): %s",
                len(self._data),
                self._pkglen,
                self._data,
            )

        self._data_final[int(self._data[3]) << 8 | int(self._data[4])] = (
            self._data.copy()
        )
        self._data_event.set()

    @staticmethod
    def _cmd(device: int, cmd: int, start: int, count: int) -> bytes:
        """Assemble a Seplos BMS command."""
        assert start >= 0 and count > 0 and start + count <= 0xFFFF
        frame: bytearray = (
            bytearray(BMS._HEAD)
            + int.to_bytes(cmd, 1, byteorder="big")
            + BMS._VER
            + int.to_bytes(start, 2, byteorder="big")
            + int.to_bytes(device, 1)
            + int.to_bytes(count, 2, byteorder="big")
        )
        frame += int.to_bytes(crc_modbus(frame), 2, byteorder="little")
        return bytes(frame)

    @staticmethod
    def _decode_data(data: bytearray) -> BMSsample:
        result: BMSsample = {}
        for key, idx, size, sign, func in BMS._FIELDS:
            result[key] = func(
                int.from_bytes(
                    data[BMS._HEAD_LEN + idx : BMS._HEAD_LEN + idx + size],
                    byteorder="big",
                    signed=sign,
                )
            )
        return result

    async def _async_update(self) -> BMSsample:
        """Update battery status information."""
        # await self._await_reply(BMS._cmd(0, 0xf3, 0xea64, 0x1))
        await self._await_reply(BMS._cmd(1, 0xF3, 0x7654, 0x37))
        # #
        # # parse data from self._data here

        data: BMSsample = BMS._decode_data(self._data_final[0x016E])

        for pack in range(1, 1 + data.get("pack_count", 0)):
            await self._await_reply(BMS._cmd(pack, 0xF3, 0x75F8, 0x52))
            pack_response: bytearray = self._data_final[pack << 8 | 0xA4]

            for key, idx, sign, func in BMS._PFIELDS:
                data.setdefault(key, []).append(
                    func(
                        int.from_bytes(
                            pack_response[
                                BMS._HEAD_LEN + idx : BMS._HEAD_LEN + idx + 2
                            ],
                            byteorder="big",
                            signed=sign,
                        )
                    )
                )
            # get cell voltages
            pack_cells: list[float] = [
                float(
                    int.from_bytes(
                        pack_response[
                            BMS._CELL_POS + idx * 2 : BMS._CELL_POS + idx * 2 + 2
                        ],
                        byteorder="big",
                    )
                    / 1000
                )
                for idx in range(pack_response[BMS._CELLNUM_POS])
            ]
            # update per pack delta voltage
            data["delta_voltage"] = max(
                data.get("delta_voltage", 0),
                round(max(pack_cells) - min(pack_cells), 3),
            )
            # add individual cell voltages
            data.setdefault("cell_voltages", []).extend(pack_cells)
            # add temperature sensors (4x cell temperature + 4 reserved)
            data.setdefault("temp_values", []).extend(
                (
                    int.from_bytes(
                        pack_response[
                            BMS._TEMP_POS + idx * 2 : BMS._TEMP_POS + idx * 2 + 2
                        ],
                        byteorder="big",
                        signed=True,
                    )
                )
                for idx in range(pack_response[BMS._TEMPNUM_POS])
            )

        self._data_final.clear()

        return data
