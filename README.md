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
- battery charging indicator [bool]

![grafik](https://github.com/patman15/BLE_BMS-HA/assets/14628713/99088715-fa2d-4d3d-90a5-967a8bf08305)

## Supported Devices
- Offgridtec LiFePo4 Smart Pro: type A & B (show up as `SmartBat-Axxxxx` or `SmartBat-Bxxxxx`)

New device types can be easily added via the plugin architecture of this integration. See [CONTRIBUTING.md](./CONTRIBUTING.md) for details.

## Installation
Installation can be done using [HACS](https://hacs.xyz/) by [adding a custom repository](https://hacs.xyz/docs/faq/custom_repositories/). Alternatively, download a zip of this repository and place the folder `custom_components/bms_ble` in the `config/custom_components` directory of your Home Assistant installation.

[![Open your Home Assistant instance and open a repository inside the Home Assistant Community Store.](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=patman15&repository=BLE_BMS-HA&category=Integration)

## Outlook
Add further battery types from [Home Assistant Add-on: BatMON](https://github.com/fl4p/batmon-ha)

## Troubleshooting
In case you have severe troubles,

- please enable the debug protocol for the integration,
- reproduce the issue,
- disable the log (Home Assistant will prompt you to download the log), and finally
- open an issue with a good description of what happened and attach the log.

## FAQ
### My sensors show unknown/unavailable at startup!
The polling interval is 30 seconds. So at startup it takes a few minutes to detect the battery and query the sensors. Then data will be available.

### Can I have the runtime in human readable format (using days)?
Yes, you can use a [template sensor](https://my.home-assistant.io/redirect/config_flow_start?domain=template) or a card to show templates, e.g. [Mushroom template card](https://github.com/piitaya/lovelace-mushroom) with the following template:
`{{ timedelta(seconds=int(states("sensor.smartbat_..._runtime"), 0)) }}` results in e,g, `4 days, 4:20:00`

### I need a discharge sensor not the charging indicator, can I have that?
Sure, use, e.g. a [threshold sensor](https://my.home-assistant.io/redirect/config_flow_start/?domain=threshold) based on the current to/from the battery. Negative means discharging, positiv is charging.