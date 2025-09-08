"""Module to support ANT BMS."""

from enum import IntEnum
import math
from typing import Final, override

from bleak.backends.characteristic import BleakGATTCharacteristic
from bleak.backends.device import BLEDevice
from bleak.uuids import normalize_uuid_str

from .basebms import AdvertisementPattern, BaseBMS, BMSdp, BMSsample, BMSvalue, crc_sum


class BMS(BaseBMS):
    """ANT BMS (legacy) implementation."""

    class CMD(IntEnum):
        """Command codes for ANT BMS."""

        GET = 0xDB
        SET = 0xA5

    class ADR(IntEnum):
        """Address codes for ANT BMS."""

        STATUS = 0x00

    _BYTES_ORDER: Final = "big"

    _RX_HEADER: Final[bytes] = b"\xaa\x55\xaa"

    _RSP_STAT: Final[int] = 0xFF
    _RX_HEADER_RSP_STAT: Final[bytes] = b"\xaa\x55\xaa\xff"
    _RSP_STAT_LEN: Final[int] = 140

    _FIELDS: Final[tuple[BMSdp, ...]] = (
        BMSdp("voltage", 4, 2, False, lambda x: x / 10),
        BMSdp("current", 70, 4, True, lambda x: x / -10),
        BMSdp("battery_level", 74, 1, False),
        # actual frame data always report 0 for design_capacity (to be investigated)
        # BMSdp("design_capacity", 75, 4, False, lambda x: x // 1e6),
        BMSdp(
            "cycle_charge", 79, 4, False, lambda x: round(x / 1e6, 1)
        ),  # charge remaining [Ah]
        BMSdp(
            "total_charge", 83, 4, False, lambda x: x // 1000
        ),  # total discharged charge [Ah]
        BMSdp("runtime", 87, 4, False),
        BMSdp("cell_count", 123, 1, False),
    )

    def __init__(self, ble_device: BLEDevice, reconnect: bool = False) -> None:
        """Initialize BMS."""
        super().__init__(ble_device, reconnect)
        self._exp_len = BMS._RSP_STAT_LEN

    @staticmethod
    @override
    def matcher_dict_list() -> list[AdvertisementPattern]:
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
            self._exp_len = BMS._RSP_STAT_LEN
        elif not self._data:
            self._log.debug("invalid Start of Frame")
            return

        self._data += data

        _data_len = len(self._data)
        if _data_len < self._exp_len:
            return

        if _data_len > self._exp_len:
            self._log.debug("invalid length %d > %d", _data_len, self._exp_len)
            self._data.clear()
            return

        if (local_crc := crc_sum(self._data[4:-2], 2)) != (
            remote_crc := int.from_bytes(
                self._data[-2:], byteorder=BMS._BYTES_ORDER, signed=False
            )
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
        _frame += value.to_bytes(2, BMS._BYTES_ORDER)
        _frame += crc_sum(_frame[2:], 1).to_bytes(1, BMS._BYTES_ORDER)
        return bytes(_frame)

    @override
    async def _async_update(self) -> BMSsample:
        """Update battery status information."""
        await self._await_reply(BMS._cmd(BMS.CMD.GET, BMS.ADR.STATUS))

        _data = self._data_final
        result = BMS._decode_data(
            BMS._FIELDS,
            _data,
            byteorder=BMS._BYTES_ORDER,
            offset=0,
        )

        result["cell_voltages"] = BMS._cell_voltages(
            _data,
            cells=result["cell_count"],
            start=6,
            size=2,
            byteorder=BMS._BYTES_ORDER,
            divider=1000,
        )
        # We're not able to actually read the 'design_capacity' so this code
        # is disabled at the moment
        # result["cycles"] = result.get("total_cycled_charge", 0) // (
        #     result.get("design_capacity") or 1
        # )

        # Hack 'design_capacity' until a fix to read the correct value is found
        try:
            result["design_capacity"] = math.ceil(
                (result["cycle_charge"] / result["battery_level"]) * 100
            )
            result["cycles"] = result["total_charge"] // result["design_capacity"]
        except (ZeroDivisionError, KeyError):
            pass

        # ANT-BMS carries 6 slots for temp sensors but only 4 looks like being connected by default
        result["temp_sensors"] = 6
        result["temp_values"] = BMS._temp_values(
            _data, values=6, start=91, size=2, byteorder=BMS._BYTES_ORDER, signed=True
        )

        _data.clear()

        return result
