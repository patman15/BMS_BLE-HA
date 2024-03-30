# Contributing

## Issues
In case you have troubles, please enable the debug protocol for the integration and open an issue with a good description of what happened and the relevant snippet from the log.

## Adding a new battery management system

 1. Fork the repository and create a branch with the name of the new BMS to add.
 2. Add a new file to the `plugins` folder called, e.g. `dummy_bms.py`
 3. Populate the file with class derived from `BaseBMS`(see basebms.py). A dummy implementation without the actual functionality to query the BMS can befound below in section _Dummy BMS Example_
 4. Make sure that the dictionary returned by `async_update()` has (all) keys listed in `SENSOR_TYPES` (see `sensor.py`), __except__ for the RSSI value which is automatically added by the data update coordinator.
 5. In `plugins/__init__.py` add line to import the new class, e.g. `from .dummy_bms import DummyBms` and add it to the valid enum `BmsTypes`, e.g. `DummyBms = auto()`.
 6. Add an appropriate [bluetooth device matcher](https://developers.home-assistant.io/docs/creating_integration_manifest#bluetooth) to `manifest.json`. Note that this is required to match the implementation of `match_dict_list()` in the new BMS class.
 7. Test and commit the changes to the branch and create a pull request to the main repository.

### Dummy BMS Example
```python
import logging
from typing import Any

from bleak.backends.device import BLEDevice

from .basebms import BaseBMS

LOGGER = logging.getLogger(__name__)


class DummyBms(BaseBMS):
    """Dummy battery class implementation"""

    def __init__(self, ble_device: BLEDevice, reconnect=False) -> None:
        LOGGER.debug(f"{self.device_id()} init()")

    @staticmethod
    def matcher_dict_list() -> list[dict[str, Any]]:
        """Provide BluetoothMatcher definition"""
        return [{"local_name": "dummy", "connectable": True}]

    @staticmethod
    def device_info() -> dict[str, str]:
        """Return device information for the battery management system"""
        return {"manufacturer": "Dummy Manufacturer", "model": "dummy model"}

    async def async_update(self) -> dict[str, float]:
        """Update battery status information"""
        return {}
```