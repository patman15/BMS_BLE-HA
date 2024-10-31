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
```python
"""Module to support Dummy BMS."""

import logging
from typing import Any

from bleak.backends.device import BLEDevice

from ..const import (
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


class BMS(BaseBMS):
    """Dummy battery class implementation."""

    def __init__(self, ble_device: BLEDevice, reconnect: bool = False) -> None:
        """Initialize BMS."""
        LOGGER.debug("%s init(), BT address: %s", self.device_id(), ble_device.address)

    @staticmethod
    def matcher_dict_list() -> list[dict[str, Any]]:
        """Provide BluetoothMatcher definition."""
        return [{"local_name": "dummy", "connectable": True}]

    @staticmethod
    def device_info() -> dict[str, str]:
        """Return device information for the battery management system."""
        return {"manufacturer": "Dummy Manufacturer", "model": "dummy model"}

    async def disconnect(self) -> None:
        """Disconnect connection to BMS if active."""

    async def async_update(self) -> BMSsample:
        """Update battery status information."""
        data = {
            ATTR_VOLTAGE: 12,
            ATTR_CURRENT: 1.5,
        }  # set fixed values for dummy battery
        self.calc_values(
            data, {ATTR_POWER, ATTR_BATTERY_CHARGING}
        )  # calculate further values from previously set ones
        return data
```
