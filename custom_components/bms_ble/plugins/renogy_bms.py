"""Module to support Dummy BMS."""

import contextlib

from bleak.backends.characteristic import BleakGATTCharacteristic
from bleak.backends.device import BLEDevice
from bleak.uuids import normalize_uuid_str

from custom_components.bms_ble.const import (
    ATTR_BATTERY_CHARGING,
    # ATTR_BATTERY_LEVEL,
    ATTR_CURRENT,
    # ATTR_CYCLE_CAP,
    # ATTR_CYCLE_CHRG,
    # ATTR_CYCLES,
    # ATTR_DELTA_VOLTAGE,
    ATTR_POWER,
    # ATTR_RUNTIME,
    ATTR_TEMPERATURE,
    ATTR_VOLTAGE,
)

from .basebms import BaseBMS, BMSsample


class BMS(BaseBMS):
    """Dummy battery class implementation."""

    def __init__(self, ble_device: BLEDevice, reconnect: bool = False) -> None:
        """Initialize BMS."""
        super().__init__(__name__, ble_device, reconnect)

    @staticmethod
    def matcher_dict_list() -> list[dict]:
        """Provide BluetoothMatcher definition."""
        return [
            {
                "service_uuid": BMS.uuid_services()[0],
                "manufacturer_id": 0x9860,
                "connectable": True,
            }
        ]

    @staticmethod
    def device_info() -> dict[str, str]:
        """Return device information for the battery management system."""
        return {"manufacturer": "Renogy", "model": "Bluetooth battery"}

    @staticmethod
    def uuid_services() -> list[str]:
        """Return list of 128-bit UUIDs of services required by BMS."""
        return [normalize_uuid_str("ffd0"), normalize_uuid_str("fff0")]

    @staticmethod
    def uuid_rx() -> str:
        """Return 16-bit UUID of characteristic that provides notification/read property."""
        return "fff1"

    @staticmethod
    def uuid_tx() -> str:
        """Return 16-bit UUID of characteristic that provides write property."""
        return "ffd1"

    @staticmethod
    def _calc_values() -> frozenset[str]:
        return frozenset(
            {ATTR_POWER, ATTR_BATTERY_CHARGING}
        )  # calculate further values from BMS provided set ones

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

    async def _async_update(self) -> BMSsample:
        """Update battery status information."""
        for cmd in (
            b"\x30\x03\x13\x88\x00\x22\x45\x5c",
            b"\x30\x03\x13\xf0\x00\x1c\x44\x95",
            b"\x30\x03\x13\xb2\x00\x06\x65\x4a",
            b"\x30\x03\x14\x02\x00\x08\xe4\x1d",
        ):
            with contextlib.suppress(TimeoutError):
                await self._await_reply(cmd)

        return {
            ATTR_VOLTAGE: 12,
            ATTR_CURRENT: 1.5,
            ATTR_TEMPERATURE: 27.182,
        }  # fixed values, replace parsed data
