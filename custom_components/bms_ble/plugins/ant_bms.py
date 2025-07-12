"""Module to support ANT BMS."""

from typing import Final

from bleak.backends.characteristic import BleakGATTCharacteristic
from bleak.backends.device import BLEDevice
from bleak.uuids import normalize_uuid_str

from .basebms import AdvertisementPattern, BaseBMS, BMSsample, BMSvalue, crc_modbus


class BMS(BaseBMS):
    """ANT BMS implementation."""

    _HEAD: Final[bytes] = b"\x7e\xa1"
    _TAIL: Final[bytes] = b"\xaa\x55"
    _CMD_STAT: Final[int] = 0x01
    _CMD_DEV: Final[int] = 0x02

    def __init__(self, ble_device: BLEDevice, reconnect: bool = False) -> None:
        """Initialize BMS."""
        super().__init__(__name__, ble_device, reconnect)

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
            {"power", "battery_charging"}
        )  # calculate further values from BMS provided set ones

    async def _init_connection(self) -> None:
        """Initialize RX/TX characteristics and protocol state."""
        await super()._init_connection()
        await self._await_reply(BMS._cmd(BMS._CMD_DEV, 0x026C, 0x20))

    def _notification_handler(
        self, _sender: BleakGATTCharacteristic, data: bytearray
    ) -> None:
        """Handle the RX characteristics notify event (new data arrives)."""
        self._log.debug("RX BLE data: %s", data)
        #
        # # do things like checking correctness of frame here and
        # # store it into a instance variable, e.g. self._data
        #
        # self._data_event.set()

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

    async def _async_update(self) -> BMSsample:
        """Update battery status information."""
        await self._await_reply(BMS._cmd(BMS._CMD_STAT, 0, 0xBE))

        return {
            "voltage": 12,
            "current": 1.5,
            "temperature": 27.182,
        }  # fixed values, replace parsed data
