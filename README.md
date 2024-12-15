# <img src="https://github.com/patman15/BMS_BLE-HA/assets/14628713/0ee84af9-300a-4a26-a098-26954a46ec36" width="32" height="32"> BLE Battery Management Systems for Home Assistant

[![GitHub Release][releases-shield]][releases]
[![License][license-shield]](LICENSE)
[![Analytics][install-shield]]()

This integration allows to monitor Bluetooth Low Energy (BLE) battery management systems (BMS) from within [Home Assistant](https://www.home-assistant.io/). After installation, no configuration is required. You can use the [ESPHome Bluetooth proxy][btproxy-url] to extend the bluetooth coverage range. By using standard dashboard cards, it is easy to visualize the current state of remote batteries.

![Dashboard](https://github.com/user-attachments/assets/f2f68bf6-6bdf-41a7-aa81-17d03b8a6a6e)

## Features
- Zero configuration
- Autodetects compatible batteries
- Supports [ESPHome Bluetooth proxy][btproxy-url]  (limit: 3 devices/proxy)
- Any number of batteries in parallel
- Native Home Assistant integration (works with all [HA installation methods](https://www.home-assistant.io/installation/#advanced-installation-methods))
- Readout of individual cell voltages to be able to judge battery health

### Supported Devices
- CBT Power BMS, Creabest batteries
- D-powercore BMS (show up as `DXB-`&#x2026;), Fliteboard batteries (show up as `TBA-`&#x2026;)
- Daly BMS (show up as `DL-`&#x2026;)
- E&J Technology BMS
    - Supervolt v1 batteries
    - Elektronicx batteries (show up as `LT-`&#x2026;)
- Ective batteries
- JBD BMS, Jiabaida (show up as `SP..S`&#x2026;)
    - accurat batteries (show up as `GJ-`&#x2026;)
    - Supervolt v3 batteries (show up as `SX1*`&#x2026;)
- JK BMS, Jikong, (HW version >=11 required)
- Offgridtec LiFePo4 Smart Pro: type A & B (show up as `SmartBat-A`&#x2026; or `SmartBat-B`&#x2026;)
- LiTime, Power Queen, and Redodo batteries
- Seplos v2 (show up as `BP00`&#x2026;)
- Seplos v3 (show up as `SP0`&#x2026; or `SP1`&#x2026;)
- TDT BMS (show up as `XDZN`&#x2026;)

New device types can be easily added via the plugin architecture of this integration. See the [contribution guidelines](CONTRIBUTING.md) for details.

### Provided Information
> [!CAUTION]
> This integration (including Home Assistant) **shall not be used for safety relevant operations**! The correctness or availability of data cannot be guaranteed (see [warranty section of the license](LICENSE)),
> since the implementation is mostly based on openly available information or non-validated vendor specifications.
> Further, issues with the Bluetooth connection, e.g. disturbances, can lead to unavailable or incorrect values.
> 
> **Do not rely** on the values to control actions that prevent battery damage, overheating (fire), or similar.

Platform | Description | Unit | Details
-- | -- | -- | --
`binary_sensor` | battery charging | `bool` | indicates `True` if battery is charging
`sensor` | charge cycles | `#` | lifetime number of charge cycles
`sensor` | current | `A` | positive for charging, negative for discharging
`sensor` | delta voltage | `V` | maximum difference between any two cells; individual cell voltage are available as attribute to this sensor
`sensor` | power | `W` | positive for charging, negative for discharging
`sensor` | runtime | `s` | remaining discharge time till SoC 0%, `unavailable` during idle/charging
`sensor` | SoC | `%` | state of charge, range 100% (full) to 0% (battery empty)
`sensor` | stored energy | `Wh` | currently stored energy
`sensor` | temperature | `°C` | individual temperature values are available as attribute to this sensor, if the BMS supports multiple sensors
`sensor` | voltage | `V` | overall battery voltage
`sensor`* | link quality  | `%` | successful BMS queries from the last hundred update periods
`sensor`* | RSSI          | `dBm`| received signal strength indicator 

*) In case sensors are reported `unavailable` please enable the diagnostic sensors, i.e. `RSSI` and `link quality` and check your connection quality. The value of `link quality` results from (temporarily) bad `RSSI` values, which are impacted by disturbances of the Bluetooth communication.
 
Quality | link quality [%] | RSSI [dBm]
--  | -- | --
excellent | 98 to 100 | -50 to high
good | 90 to 98 | -60 to -70
fair | 80 to 90 | -70 to -80
weak | 60 to 80 | -80 to -90
bad | 0 to 60  | -90 to low


## Installation
### Automatic
Installation can be done using [HACS](https://hacs.xyz/) by [adding a custom repository](https://hacs.xyz/docs/faq/custom_repositories/).

[![Open your Home Assistant instance and open a repository inside the Home Assistant Community Store.](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=patman15&repository=BMS_BLE-HA&category=Integration)

### Manual
1. Using the tool of choice open the directory (folder) for your HA configuration (where you find `configuration.yaml`).
1. If you do not have a `custom_components` directory (folder) there, you need to create it.
1. In the `custom_components` directory (folder) create a new folder called `bms_ble`.
1. Download _all_ the files from the `custom_components/bms_ble/` directory (folder) in this repository.
1. Place the files you downloaded in the new directory (folder) you created.
1. Restart Home Assistant
1. In the HA UI go to "Configuration" -> "Integrations" click "+" and [search](https://my.home-assistant.io/redirect/config_flow_start/?domain=bms_ble) for "BLE Battery Management"

## FAQ
### My sensors show unknown/unavailable at startup!
The polling interval is 30 seconds. So at startup it takes a few minutes to detect the battery and query the sensors. Then data will be available.

### Can I have the runtime in human readable format (using days)?
Yes, you can use a [template sensor](https://my.home-assistant.io/redirect/config_flow_start?domain=template) or a card to show templates, e.g. [Mushroom template card](https://github.com/piitaya/lovelace-mushroom) with the following template:<br>
`{{ timedelta(seconds=int(states("sensor.smartbat_..._runtime"), 0)) }}` results in e,g, `4 days, 4:20:00`

### How do I get the cell voltages as individual sensor for tracking?
The individual voltages are available as attribute to the `delta voltage` sensor. Click the sensor and at the bottom of the graph expand the `attribute` section. Alternatively, you can also find them in the [developer tools](https://my.home-assistant.io/redirect/developer_states/).
To create individual sensors, go to [Settings > Devices & Services > Helper](https://my.home-assistant.io/redirect/helpers) and [add a template sensor](https://my.home-assistant.io/redirect/config_flow_start?domain=template) for each cell you want to monitor. Fill the configuration for, e.g. the first cell (0), as follows:

Field | Content
-- | --
State template | ```{{ iif(has_value("sensor.smartbat_..._delta_voltage"), state_attr("sensor.smartbat_..._delta_voltage", "cell_voltages")[0], None) }}```<br>The index `[0]` can be in the range from 0 to the number of cells-1, i.e. 0-3 for a 4 cell battery.
Unit of measurement | `V`
Device class | `Voltage`
State class | `Measurement`
Device | `smartbat_...`

or add the following snippet to your `configuration.yaml`:
```yaml
template:
  - sensor:
    - name: cell_voltage_0
      state: >-
        {{ state_attr('sensor.smartbat_..._delta_voltage', 'cell_voltages')[0] }}
      unit_of_measurement: 'V'
      state_class: measurement
      device_class: voltage
      availability: >- 
        {{ has_value('sensor.smartbat_..._delta_voltage') }}
```

### I want to know the maximum cell voltage!
Please follow the explanations in the previous question but use the following:

Field | Content
-- | --
State template | `{%- if has_value("sensor.smartbat_..._delta_voltage") %} {{ state_attr("sensor.smartbat_..._delta_voltage", "cell_voltages") \| max }} {% else %} None {% endif -%}`

There are plenty more functions you can use, e.g. min, and the full power of [templating](https://www.home-assistant.io/docs/configuration/templating/).

### I need a discharge sensor not the charging indicator, can I have that?
Sure, use, e.g. a [threshold sensor](https://my.home-assistant.io/redirect/config_flow_start/?domain=threshold) based on the current to/from the battery. Negative means discharging, positiv is charging.

### My BMS needs a pin, how can I enter it?

Then you need to pair your device first. This is procedure is only required once for each device.
- Open a [terminal to Home Assistant](https://www.home-assistant.io/common-tasks/supervised/#installing-and-using-the-ssh-add-on).
- Use the command `bluetoothctl devices` to check that your devices is detected and
- run `bluetoothctl pair <MAC_of_BMS>` to start pairing the device.

Once pairing is done, the integration should automatically detect the BMS.

## Troubleshooting
### If your device is not recognized

1. Check that your BMS type is listed as [supported device](#supported-devices)
1. Make sure that no other device is connected to the BMS, e.g. app on your phone
1. Check that your are running the [latest release](https://github.com//patman15/BMS_BLE-HA/releases)  of the integration
1. Open a [terminal to Home Assistant](https://www.home-assistant.io/common-tasks/supervised/#installing-and-using-the-ssh-add-on) and verify that your BMS is listed in the ouput of the command `bluetoothctl devices`. Try to connect to the BMS using `bluetoothctl connect <MAC>`.
1. If you use a BT proxy, make sure you have set `active: true` and that you do not exced the [BT proxy limit][btproxy-url] of 3 devices/proxy; check the logs of the proxy if the device is recognized.

### In case you have severe troubles

- please [enable the debug protocol](https://www.home-assistant.io/docs/configuration/troubleshooting/#debug-logs-and-diagnostics) for the [BLE Battery Management integration](https://my.home-assistant.io/redirect/integration/?domain=bms_ble),
- restart Home Assistant and reproduce the issue,
- disable the log (Home Assistant will prompt you to download the log), and finally
- [open an issue](https://github.com/patman15/BMS_BLE-HA/issues/new?assignees=&labels=Bug&projects=&template=bug.yml) with a good description of what happened and attach the log.

## Outlook
- Clean-up of translations
- Implement status report of the BMS, e.g. warnings, errors as (single) binary sensor (ok, not ok)
- Add option to only have temporary connections (lowers reliability, but helps running more devices via [ESPHome Bluetooth proxy][btproxy-url])
- Add further battery types on [request](https://github.com/patman15/BMS_BLE-HA/issues/new?assignees=&labels=enhancement&projects=&template=feature_request.yml)

## Thanks to
> [@gkathan](https://github.com/patman15/BMS_BLE-HA/issues/2), [@downset](https://github.com/patman15/BMS_BLE-HA/issues/19), [@gerritb](https://github.com/patman15/BMS_BLE-HA/issues/22), [@Goaheadz](https://github.com/patman15/BMS_BLE-HA/issues/24), [@alros100, @majonessyltetoy](https://github.com/patman15/BMS_BLE-HA/issues/52), [@snipah, @Gruni22](https://github.com/patman15/BMS_BLE-HA/issues/59), [@azisto](https://github.com/patman15/BMS_BLE-HA/issues/78), [@BikeAtor, @Karatzie](https://github.com/patman15/BMS_BLE-HA/issues/57), [@SkeLLLa,@romanshypovskyi](https://github.com/patman15/BMS_BLE-HA/issues/90), [@riogrande75, @ebagnoli, @andreas-bulling](https://github.com/patman15/BMS_BLE-HA/issues/101), [@hacsler](https://github.com/patman15/BMS_BLE-HA/issues/103)

for helping with making the integration better.

## References
- [Home Assistant Add-on: BatMON](https://github.com/fl4p/batmon-ha)
- Daly BMS: [esp32-smart-bms-simulation](https://github.com/roccotsi2/esp32-smart-bms-simulation)
- Jikong BMS: [esphome-jk-bms](https://github.com/syssi/esphome-jk-bms)
- JBD BMS: [esphome-jbd-bms](https://github.com/syssi/esphome-jbd-bms)
- D-powercore BMS: [Strom BMS monitor](https://github.com/majonessyltetoy/strom)

[license-shield]: https://img.shields.io/github/license/patman15/BMS_BLE-HA.svg?style=for-the-badge
[releases-shield]: https://img.shields.io/github/release/patman15/BMS_BLE-HA.svg?style=for-the-badge
[releases]: https://github.com//patman15/BMS_BLE-HA/releases
[install-shield]: https://img.shields.io/badge/dynamic/json?style=for-the-badge&color=green&label=Analytics&suffix=%20Installs&cacheSeconds=15600&url=https://analytics.home-assistant.io/custom_integrations.json&query=$.bms_ble.total
[btproxy-url]: https://esphome.io/components/bluetooth_proxy
