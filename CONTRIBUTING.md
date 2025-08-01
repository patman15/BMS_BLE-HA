# Contributing

## Issues
In case you have troubles, please enable the debug protocol for the integration and [open an issue](https://github.com/patman15/BMS_BLE-HA/issues) with a good description of what happened and the relevant snippet from the log.

## Architecture Guidelines
- The integration shall not use persistent information. That means all necessary info shall be determined on connecting the device.
- The BT pattern matcher shall be unique to allow auto-detecting devices.
- Frame parsing shall check the validity of a frame according to the protocol type, e.g. CRC, length, allowed type
- All plugin classes shall inherit from `BaseBMS` and use the functions from there before overriding or replacing.
- If available the data shall be read from the device, the `BaseBMS._add_missing_values()` functionality is only to have consistent data over all BMS types.

to be extended ...

## Coding Style Guidelines

In general I use guidelines very close to the ones that Home Assistant uses for core integrations. Thus, the code shall pass
- `ruff check .`
- `mypy .`

## Adding a new battery management system

 1. Fork the repository and create a branch with the name of the new BMS to add.
 2. Add a new file to the `plugins` folder called, e.g. `my_bms.py`
 3. Populate the file with class called `BMS` derived from `BaseBMS`(see basebms.py). A dummy implementation without the actual functionality to query the BMS can befound below in section _Dummy BMS Example_
 4. Make sure that the dictionary returned by `async_update()` has (all) keys listed in `SENSOR_TYPES` (see `sensor.py`), __except__ for `ATTR_LQ` and `ATTR_RSSI` which are automatically handled. To make it simple, just follow the `ATTR_*` import in the example code below.
 5. In `const.py` add the filename (without extention), e.g. `my_bms`, to the constant `BMS_TYPES`.
 6. Add an appropriate [bluetooth device matcher](https://developers.home-assistant.io/docs/creating_integration_manifest#bluetooth) to `manifest.json`. Note that this is required to match the implementation of `match_dict_list()` in the new BMS class.
 7. Test and commit the changes to the branch and create a pull request to the main repository.

> [!NOTE]
> In order to keep maintainability of this integration, pull requests are required to pass standard Home Assistant checks for integrations, [coding style guidelines](#coding-style-guidelines), Python linting, and 100% [branch test coverage](https://coverage.readthedocs.io/en/latest/branch.html#branch).

### Any contributions you make will be under the Apache-2.0 License

In short, when you submit code changes, your submissions are understood to be under the same [Apache-2.0](LICENSE) that covers the project. Feel free to contact the maintainers if that's a concern.

### Dummy BMS Example
Note: In order for the [example](custom_components/bms_ble/plugins/dummy_bms.py) to work, you need to set the UUIDs of the service, the characteristic providing notifications, and the characteristic for sending commands to. While the device must be in Bluetooth range, the actual communication does not matter. Always the fixed values in the code will be shown.

```python
"""Module to support Dummy BMS."""

from bleak.backends.characteristic import BleakGATTCharacteristic
from bleak.backends.device import BLEDevice
from bleak.uuids import normalize_uuid_str

from .basebms import AdvertisementPattern, BaseBMS, BMSsample, BMSvalue


class BMS(BaseBMS):
    """Dummy BMS implementation."""

    # _HEAD: Final[bytes] = b"\x55"  # beginning of frame
    # _TAIL: Final[bytes] = b"\xAA"  # end of frame
    # _FRAME_LEN: Final[int] = 10  # length of frame, including SOF and checksum

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
        self._log.debug("RX BLE data: %s", data)

        # *******************************************************
        # # Do things like checking correctness of frame here and
        # # store it into a instance variable, e.g. self._data
        # # Below are some examples of how to do it
        # # Have a look at the BMS base class for function to use,
        # # take a look at other implementations for more  details
        # *******************************************************

        # if not data.startswith(BMS._HEAD):
        #     self._log.debug("incorrect SOF")
        #     return

        # if (crc := crc_sum(self._data[:-1])) != self._data[-1]:
        #     self._log.debug("invalid checksum 0x%X != 0x%X", self._data[-1], crc)
        #     return

        self._data = data.copy()
        self._data_event.set()

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
```
