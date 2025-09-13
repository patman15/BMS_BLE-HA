# Contributing

## Issues
In case you have troubles, please [enable the debug protocol](https://www.home-assistant.io/docs/configuration/troubleshooting/#debug-logs-and-diagnostics) for the [integration](https://my.home-assistant.io/redirect/integration/?domain=bms_ble) and [open an issue](https://github.com/patman15/BMS_BLE-HA/issues) with a good description of what happened and attach the log **as a file**.

## Adding a new battery management system

The handling of the BMS types is done by the external library [aiobmsble](https://github.com/patman15/aiobmsble). To add a new type, please see the [CONTRIBUTING](https://github.com/patman15/aiobmsble?tab=contributing-ov-file) guidelines of this repository.
 
### Any contributions you make will be under the Apache-2.0 License

In short, when you submit code changes, your submissions are understood to be under the same [Apache-2.0](LICENSE) that covers the project. Feel free to contact the maintainers if that's a concern.

## Coding Style Guidelines

In general I use guidelines very close to the ones that Home Assistant uses for core integrations. Thus, the code shall pass
- `pytest`
- `ruff check .`
- `mypy .`

> [!NOTE]
> In order to keep maintainability of this integration, pull requests are required to pass standard Home Assistant checks for integrations, [coding style guidelines](#coding-style-guidelines), Python linting, and 100% [branch test coverage](https://coverage.readthedocs.io/en/latest/branch.html#branch).

## Architecture Guidelines
- The integration shall not use persistent information. That means all necessary info shall be determined on connecting the device.

to be extended ...
