# Contributing

## Issues
In case you have troubles, please [enable the debug protocol](https://www.home-assistant.io/docs/configuration/troubleshooting/#debug-logs-and-diagnostics) for the [integration](https://my.home-assistant.io/redirect/integration/?domain=bms_ble) and [open an issue](https://github.com/patman15/BMS_BLE-HA/issues) with a good description of what happened and attach the log **as a file**.

## Architecture Guidelines
- The integration shall not use persistent information. That means all necessary info shall be determined on connecting the device.
- The BT pattern matcher shall be unique to allow auto-detecting devices.
- Frame parsing shall check the validity of a frame according to the protocol type, e.g. CRC, length, allowed type
- All plugin classes shall inherit from `BaseBMS` and use the functions from there before overriding or replacing.
- If available the data shall be read from the device, the `BaseBMS._add_missing_values()` functionality is only to have consistent data over all BMS types.

to be extended ...

## Coding Style Guidelines

In general I use guidelines very close to the ones that Home Assistant uses for core integrations. Thus, the code shall pass
- `pytest`
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
