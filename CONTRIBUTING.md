# Contributing

## Issues
In case you have troubles, please enable the debug protocol for the integration and [open an issue](https://github.com/patman15/BMS_BLE-HA/issues) with a good description of what happened and the relevant snippet from the log.

## Adding a new battery management system

 1. Fork the repository and create a branch with the name of the new BMS to add.
 2. Add a new file to the `plugins` folder called, e.g. `my_bms.py`
 3. Populate the file with class called `BMS` derived from `BaseBMS`(see basebms.py). A dummy implementation without the actual functionality to query the BMS can befound below in section _Dummy BMS Example_
 4. Make sure that the dictionary returned by `async_update()` has (all) keys listed in `SENSOR_TYPES` (see `sensor.py`), __except__ for `ATTR_LQ` and `ATTR_RSSI` which are automatically handled. To make it simple, just follow the `ATTR_*` import in the example code below.
 5. In `const.py` add the filename (without extention), e.g. `my_bms`, to the constant `BMS_TYPES`.
 6. Add an appropriate [bluetooth device matcher](https://developers.home-assistant.io/docs/creating_integration_manifest#bluetooth) to `manifest.json`. Note that this is required to match the implementation of `match_dict_list()` in the new BMS class.
 7. Test and commit the changes to the branch and create a pull request to the main repository.

Note: in order to keep maintainability of this integration, pull requests are required to pass standard Home Assistant checks for integrations, Python linting, and 100% [branch test coverage](https://coverage.readthedocs.io/en/latest/branch.html#branch).

### Any contributions you make will be under the LGPL-2.1 License

In short, when you submit code changes, your submissions are understood to be under the same [LGPL-2.1 license](LICENSE) that covers the project. Feel free to contact the maintainers if that's a concern.

### Dummy BMS Example
Note: In order for the [example](custom_components/bms_ble/plugins/dummy_bms.py) to work, you need to set the UUIDs of the service, the characteristic providing notifications, and the characteristic for sending commands to. While the device must be in Bluetooth range, the actual communication does not matter. Always the fixed values in the code will be shown.

```python
"""Module to support Dummy BMS."""

# import asyncio
import logging
from typing import Any

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
    # ATTR_TEMPERATURE,
    ATTR_VOLTAGE,
)

from .basebms import BaseBMS, BMSsample

LOGGER = logging.getLogger(__name__)
BAT_TIMEOUT = 10


class BMS(BaseBMS):
    """Dummy battery class implementation."""

    def __init__(self, ble_device: BLEDevice, reconnect: bool = False) -> None:
        """Initialize BMS."""
        LOGGER.debug("%s init(), BT address: %s", self.device_id(), ble_device.address)
        super().__init__(LOGGER, self._notification_handler, ble_device, reconnect)

    @staticmethod
    def matcher_dict_list() -> list[dict[str, Any]]:
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
    def _calc_values() -> set[str]:
        return {
            ATTR_POWER,
            ATTR_BATTERY_CHARGING,
        }  # calculate further values from BMS provided set ones

    def _notification_handler(self, _sender, data: bytearray) -> None:
        """Handle the RX characteristics notify event (new data arrives)."""
        # LOGGER.debug("%s: Received BLE data: %s", self.name, data.hex(' '))
        # 
        # # do things like checking correctness of frame here and
        # # store it into a instance variable, e.g. self._data
        #
        # self._data_event.set()

    async def _async_update(self) -> BMSsample:
        """Update battery status information."""
        LOGGER.debug("(%s) replace with command to UUID %s", self.name, BMS.uuid_tx())
        # await self._client.write_gatt_char(BMS.uuid_tx(), data=b"<some_command>")
        # await asyncio.wait_for(self._wait_event(), timeout=BAT_TIMEOUT) # wait for data update
        # #
        # # parse data from self._data here

        return {
            ATTR_VOLTAGE: 12,
            ATTR_CURRENT: 1.5,
        }  # fixed values, replace parsed data
```
