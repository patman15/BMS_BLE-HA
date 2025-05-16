"""Module to support Dummy BMS."""

from bleak.backends.characteristic import BleakGATTCharacteristic
from bleak.backends.device import BLEDevice
from bleak.uuids import normalize_uuid_str

from .basebms import AdvertisementPattern, BaseBMS, BMSsample, BMSvalue


class BMS(BaseBMS):
    """Dummy BMS implementation."""

    def __init__(self, ble_device: BLEDevice, reconnect: bool = False) -> None:
        """Initialize BMS."""
        super().__init__(__name__, ble_device, reconnect)

    @staticmethod
    def matcher_dict_list() -> list[AdvertisementPattern]:
        """Provide BluetoothMatcher definition."""
        return [{"local_name": "dummy", "connectable": True}]

    @staticmethod
    def device_info() -> dict[str, str]:
        """Return device information for the battery management system."""
        return {"manufacturer": "Dummy Manufacturer", "model": "dummy model"}

    @staticmethod
    def uuid_services() -> list[str]:
        """Return list of 128-bit UUIDs of services required by BMS."""
        return [normalize_uuid_str("0000")]  # change service UUID here!

    @staticmethod
    def uuid_rx() -> str:
        """Return 16-bit UUID of characteristic that provides notification/read property."""
        return "#changeme"

    @staticmethod
    def uuid_tx() -> str:
        """Return 16-bit UUID of characteristic that provides write property."""
        return "#changeme"

    @staticmethod
    def _calc_values() -> frozenset[BMSvalue]:
        return frozenset(
            {"power", "battery_charging"}
        )  # calculate further values from BMS provided set ones

    def _notification_handler(
        self, _sender: BleakGATTCharacteristic, data: bytearray
    ) -> None:
        """Handle the RX characteristics notify event (new data arrives)."""
        # self._log.debug("RX BLE data: %s", data)
        #
        # # do things like checking correctness of frame here and
        # # store it into a instance variable, e.g. self._data
        #
        # self._data_event.set()

    async def _async_update(self) -> BMSsample:
        """Update battery status information."""
        self._log.debug("replace with command to UUID %s", BMS.uuid_tx())
        # await self._await_reply(b"<some_command>")
        # #
        # # parse data from self._data here

        return {
            "voltage": 12,
            "current": 1.5,
            "temperature": 27.182,
        }  # fixed values, replace parsed data
