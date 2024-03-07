# <img src="https://github.com/patman15/BLE_BMS-HA/assets/14628713/0ee84af9-300a-4a26-a098-26954a46ec36" width="32" height="32"> BLE Battery Management Systems for Home Assistant

This integration allows to monitor Bluetooth Low Energy (BLE) battery management systems (BMS) from within [Home Assistant](https://www.home-assistant.io/). The integration provides the following information about the battery
- SoC (state of charge) [%]
- stored energy [Wh]
- voltage [V]
- current [A]
- power [W]
- temperature [°C]
- (remaining) runtime [s]
- charge cycles [#]

![grafik](https://github.com/patman15/BLE_BMS-HA/assets/14628713/99088715-fa2d-4d3d-90a5-967a8bf08305)

## Supported Devices
- Offgridtec LiFePo4 Smart Pro: type A & B (show up as `SmartBat-Axxxxx` or `SmartBat-Bxxxxx`)

## Installation
Installation can be done using [HACS](https://hacs.xyz/) by [adding a custom repository](https://hacs.xyz/docs/faq/custom_repositories/). Alternatively, download a zip of this repository and place the folder `custom_components/bms_ble` in the `config/custom_components` directory of your Home Assistant installation.

[![Open your Home Assistant instance and open a repository inside the Home Assistant Community Store.](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=patman15&repository=BLE_BMS-HA&category=Integration)

## Outlook
Add further battery types from [Home Assistant Add-on: BatMON](https://github.com/fl4p/batmon-ha)

## Troubleshooting
- Polling interval is 30 seconds. At startup it takes a few minutes to detect the battery and query the sensors.
- In case you have severe troubles, please enable the debug protocol for the integration and open an issue with a good description of what happened and the relevant snippet from the log.
