"""Module to support ANT BMS."""

import contextlib
from enum import IntEnum
from typing import Final, override

from bleak.backends.characteristic import BleakGATTCharacteristic
from bleak.backends.device import BLEDevice
from bleak.uuids import normalize_uuid_str

from .basebms import BaseBMS, BMSdp, BMSsample, BMSvalue, MatcherPattern, crc_sum


class BMS(BaseBMS):
    """ANT BMS (legacy) implementation."""

    class CMD(IntEnum):
        """Command codes for ANT BMS."""

        GET = 0xDB
        SET = 0xA5

    class ADR(IntEnum):
        """Address codes for ANT BMS."""

        STATUS = 0x00

    _RX_HEADER: Final[bytes] = b"\xaa\x55\xaa"
    _RX_HEADER_RSP_STAT: Final[bytes] = b"\xaa\x55\xaa\xff"

    _RSP_STAT: Final[int] = 0xFF
    _RSP_STAT_LEN: Final[int] = 140

    _FIELDS: Final[tuple[BMSdp, ...]] = (
        BMSdp("voltage", 4, 2, False, lambda x: x / 10),
        BMSdp("current", 70, 4, True, lambda x: x / -10),
        BMSdp("battery_level", 74, 1, False),
        BMSdp("design_capacity", 75, 4, False, lambda x: x // 1e6),
        BMSdp("cycle_charge", 79, 4, False, lambda x: x / 1e6),
        BMSdp("total_charge", 83, 4, False, lambda x: x // 1000),
        BMSdp("runtime", 87, 4, False),
        BMSdp("cell_count", 123, 1, False),
    )

    def __init__(self, ble_device: BLEDevice, keep_alive: bool = True) -> None:
        """Initialize BMS."""
        super().__init__(ble_device, keep_alive)
        self._data_final: bytearray

    @staticmethod
    @override
    def matcher_dict_list() -> list[MatcherPattern]:
        """Provide BluetoothMatcher definition."""
        return [
            {
                "local_name": "ANT-BLE*",
                "service_uuid": BMS.uuid_services()[0],
                "manufacturer_id": 1623,
                "connectable": True,
            }
        ]

    @staticmethod
    @override
    def device_info() -> dict[str, str]:
        """Return device information for the battery management system."""
        return {"manufacturer": "ANT", "model": "Smart BMS"}

    @staticmethod
    @override
    def uuid_services() -> list[str]:
        """Return list of 128-bit UUIDs of services required by BMS."""
        return [normalize_uuid_str("ffe0")]  # change service UUID here!

    @staticmethod
    @override
    def uuid_rx() -> str:
        """Return 16-bit UUID of characteristic that provides notification/read property."""
        return "ffe1"

    @staticmethod
    @override
    def uuid_tx() -> str:
        """Return 16-bit UUID of characteristic that provides write property."""
        return "ffe1"

    @staticmethod
    @override
    def _calc_values() -> frozenset[BMSvalue]:
        return frozenset(
            (
                "battery_charging",
                "cycle_capacity",
                "cycles",
                "delta_voltage",
                "power",
                "temperature",
            )
        )  # calculate further values from BMS provided set ones

    def _notification_handler(
        self, _sender: BleakGATTCharacteristic, data: bytearray
    ) -> None:
        """Handle the RX characteristics notify event (new data arrives)."""

        self._log.debug("RX BLE data: %s", data)

        if data.startswith(BMS._RX_HEADER_RSP_STAT):
            self._data = bytearray()
        elif not self._data:
            self._log.debug("invalid start of frame")
            return

        self._data += data

        _data_len: Final[int] = len(self._data)
        if _data_len < BMS._RSP_STAT_LEN:
            return

        if _data_len > BMS._RSP_STAT_LEN:
            self._log.debug("invalid length %d > %d", _data_len, BMS._RSP_STAT_LEN)
            self._data.clear()
            return

        if (local_crc := crc_sum(self._data[4:-2], 2)) != (
            remote_crc := int.from_bytes(self._data[-2:], byteorder="big", signed=False)
        ):
            self._log.debug("invalid checksum 0x%X != 0x%X", local_crc, remote_crc)
            self._data.clear()
            return

        self._data_final = self._data.copy()
        self._data.clear()
        self._data_event.set()

    @staticmethod
    def _cmd(cmd: CMD, adr: ADR, value: int = 0x0000) -> bytes:
        """Assemble a ANT BMS command."""
        _frame = bytearray((cmd, cmd, adr))
        _frame += value.to_bytes(2, "big")
        _frame += crc_sum(_frame[2:], 1).to_bytes(1, "big")
        return bytes(_frame)

    @override
    async def _async_update(self) -> BMSsample:
        """Update battery status information."""
        await self._await_reply(BMS._cmd(BMS.CMD.GET, BMS.ADR.STATUS))

        _data: bytearray = self._data_final
        result: BMSsample = BMS._decode_data(
            BMS._FIELDS, _data, byteorder="big", offset=0
        )

        result["cell_voltages"] = BMS._cell_voltages(
            _data,
            cells=result["cell_count"],
            start=6,
            size=2,
            byteorder="big",
            divider=1000,
        )

        if not result["design_capacity"]:
            # Workaround for some BMS always reporting 0 for design_capacity
            result.pop("design_capacity")
            with contextlib.suppress(ZeroDivisionError):
                result["design_capacity"] = int(
                    round((result["cycle_charge"] / result["battery_level"]) * 100, -1)
                )  # leads to `cycles` not available when level == 0

        # ANT-BMS carries 6 slots for temp sensors but only 4 looks like being connected by default
        result["temp_values"] = BMS._temp_values(
            _data, values=4, start=91, size=2, byteorder="big", signed=True
        )

        return result
