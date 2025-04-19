# <img src="https://github.com/patman15/BMS_BLE-HA/assets/14628713/0ee84af9-300a-4a26-a098-26954a46ec36" width="32" height="32"> BLE Battery Management Systems for Home Assistant

[![GitHub Release][releases-shield]][releases]
[![License][license-shield]](LICENSE)
[![Effort][effort-shield]](https://buymeacoffee.com/patman15)
[![Analytics][install-shield]]()

This integration allows to monitor Bluetooth Low Energy (BLE) battery management systems (BMS) from within [Home Assistant](https://www.home-assistant.io/). After installation, no configuration is required. You can use the [ESPHome Bluetooth proxy][btproxy-url] to extend the bluetooth coverage range. By using standard dashboard cards, it is easy to visualize the current state of remote batteries.

![dashboard](https://github.com/user-attachments/assets/45fbba89-6e80-4f5a-a6a2-f589c4eedaf2)

## Features
- Zero configuration
- Autodetects compatible batteries
- Supports [ESPHome Bluetooth proxy][btproxy-url]  (limit: 3 devices/proxy)
- Any number of batteries in parallel
- Native Home Assistant integration (works with all [HA installation methods](https://www.home-assistant.io/installation/#advanced-installation-methods))
- Readout of individual cell voltages to be able to judge battery health
- 100% test coverage plus fuzz tests for BLE data

### Supported Devices
- ABC/SOK BMS (show up as `ABC-`&#x2026;, `SOK-`&#x2026;)
- CBT Power BMS, Creabest batteries
- D-powercore BMS (show up as `DXB-`&#x2026;), Fliteboard batteries (show up as `TBA-`&#x2026;)
- Daly BMS (show up as `DL-`&#x2026;)
    - 100Balance BMS
    - Bulltron batteries
- E&J Technology BMS (show ups as `libatt`&#x2026;)
    - Elektronicx batteries (show up as `LT-`&#x2026;)
    - Lithtech batteries (show up as `LT-12V-`&#x2026; or `L-12V`&#x2026;)
    - Meritsun, Supervolt v1, and Volthium (show up as `V-12V`&#x2026;) batteries
- ECO-WORTHY + BW02 adapter (show up as `ECO-WORTHY`&#x2026;)
- Ective, Topband batteries (show up as `$PFLAC`&#x2026;, `NWJ20`&#x2026;, `ZM20`&#x2026;)
- Felicity ESS batteries (show up as `F10`&#x2026;)
- JBD BMS, Jiabaida (show up as `AP2.S`&#x2026;, `SP..S`&#x2026;)
    - accurat batteries (show up as `GJ-`&#x2026;)
    - DCHOUSE, ECO-WORTHY (show up as `DP04S`&#x2026;), Epoch batteries
    - Eleksol, Liontron, Perfektium (show up as `PKT`&#x2026;), Ultimatron batteries (show up as `12??0`&#x2026;)
    - SBL batteries, Supervolt v3 batteries (show up as `SX1`&#x2026;)
- JK BMS, Jikong, (HW version &ge; 6 required)
- Offgridtec LiFePo4 Smart Pro: type A & B (show up as `SmartBat-A`&#x2026; or `SmartBat-B`&#x2026;)
- LiTime, Power Queen, and Redodo batteries
- Seplos v2 (show up as `BP0?`)
- Seplos v3 (show up as `SP[0,1,4-6]`&#x2026;)
- RoyPow batteries
- TDT BMS

> [!TIP]
> New device types can be easily added via the plugin architecture of this integration. See the [contribution guidelines](CONTRIBUTING.md) for details.

### Provided Information
> [!CAUTION]
> This integration (including Home Assistant) **shall not be used for safety relevant operations**! The correctness or availability of data cannot be guaranteed (see [warranty section of the license](LICENSE)),
> since the implementation is mostly based on openly available information or non-validated vendor specifications.
> Further, issues with the Bluetooth connection, e.g. disturbances, can lead to unavailable or incorrect values.
> 
> **Do not rely** on the values to control actions that prevent battery damage, overheating (fire), or similar.

Platform | Description | Unit | Decription | optional Attributes
-- | -- | -- | -- | --
`binary_sensor` | battery charging | `bool` | indicates `True` if battery is charging
`binary_sensor` | problem | `bool` | indicates `True` if the battery reports an issue or plausibility checks on values fail
`sensor` | charge cycles | `#` | lifetime number of charge cycles | package charge cycles
`sensor` | current | `A` | positive for charging, negative for discharging | balance current, package current
`sensor` | delta voltage | `V` | maximum difference between any two cells | cell voltages
`sensor` | power | `W` | positive for charging, negative for discharging
`sensor` | runtime | `s` | remaining discharge time till SoC 0%, `unavailable` during idle/charging
`sensor` | SoC | `%` | state of charge, range 100% (full) to 0% (battery empty) | package SoC
`sensor` | stored energy | `Wh` | currently stored energy
`sensor` | temperature | `°C` | (average) battery temperature | individual temperature values
`sensor` | voltage | `V` | overall battery voltage | package voltage
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
BMS_BLE is a default repository in [HACS](https://hacs.xyz/). Please follow the [guidelines on how to use HACS](https://hacs.xyz/docs/use/) if you haven't installed it yet. To add the integration to your Home Assistant instance, use this My button:

[![Open your Home Assistant instance and open a repository inside the Home Assistant Community Store.](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=patman15&repository=BMS_BLE-HA&category=Integration)

<details><summary>Manual installation steps</summary>

1. Using the tool of choice open the directory (folder) for your HA configuration (where you find `configuration.yaml`).
1. If you do not have a `custom_components` directory (folder) there, you need to create it.
1. In the `custom_components` directory (folder) create a new folder called `bms_ble`.
1. Download _all_ the files from the `custom_components/bms_ble/` directory (folder) in this repository.
1. Place the files you downloaded in the new directory (folder) you created.
1. Restart Home Assistant
1. In the HA UI go to <a href="https://my.home-assistant.io/redirect/integrations">Configuration > Integrations</a> click <a href="https://my.home-assistant.io/redirect/config_flow_start?domain=bms_ble">+ Add Integration</a> and [search](https://my.home-assistant.io/redirect/config_flow_start/?domain=bms_ble) for "BLE Battery Management"
</details>

## Removing the Integration
This integration follows standard integration removal. No extra steps are required.
<details><summary>To remove an integration instance from Home Assistant</summary>

1. Go to <a href="https://my.home-assistant.io/redirect/integrations">Settings > Devices & services</a> and select the integration card.
1. From the list of devices, select the integration instance you want to remove.
1. Next to the entry, select the three-dot menu. Then, select Delete.
</details>

## Known Issues

<details><summary>Daly BMS with WiFi, e.g. Bulltron</summary>
The connection cannot be established. The reason is most likely a <a href="https://github.com/hbldh/bleak/issues/972#issuecomment-1235867382">violation of the Bluetooth specification</a>, that is rejected by the Linux BlueZ daemon. Please raise a <a href="https://github.com/patman15/BMS_BLE-HA/issues/new?template=support.yml">new issue</a> if you have further information or observations.
</details>
<details><summary>Elektronicx, Lithtech batteries</summary>
Bluetooth is turned off, when there is no current. Thus, device will get unavailble / cannot be added.
</details>
<details><summary>Liontron batteries</summary>
These batteries need a shorter interval between queries. Be a bit patient to get them added and set a <a href="[custint-url]">custom interval</a> of about 9s to keep a stable connection.
</details>
<details><summary>Redodo MPPT</summary>
Currently there is no way to distinguish Redodo batteries from their MPPT chargers. Thus, the latter are also detected but cannot be read out. Please set these devices to `ignore`.
</details>
<details><summary>Seplos v2</summary>
The internal Bluetooth adapter issues <code>AT</code> commands in regular intervals which can interfer with BMS messages causing them to be corrupted. This impacts data availability (<code>link quality</code>).
</details>

## Troubleshooting

> [!NOTE]
> A lot of transient issues are due to problems with Bluetooth adapters. Most prominent example is the performance limitation of the [internal Raspberry Pi BT adapter](https://www.home-assistant.io/integrations/bluetooth/#cypress-based-adapters), resulting in, e.g., sometimes wrong data, when you have multiple devices. Please check the Home Assistant [Bluetooth integration](https://www.home-assistant.io/integrations/bluetooth/) page for known issues and consider using a [recommended high-performance adapter](https://www.home-assistant.io/integrations/bluetooth/#known-working-high-performance-adapters).

### If your device is not recognized

1. Check that your BMS type is listed as [supported device](#supported-devices)
1. If a name detection pattern is listed ("show up as"), make sure your device matches it.
1. Make sure that no other device is connected to the BMS, e.g. app on your phone
1. Check that your are running the [latest release](https://github.com//patman15/BMS_BLE-HA/releases) of the integration
1. Open a [terminal to Home Assistant](https://www.home-assistant.io/common-tasks/supervised/#installing-and-using-the-ssh-add-on) and verify that your BMS is listed in the ouput of the command `bluetoothctl devices`.
1. If you use a BT proxy, make sure you have set `active: true` and that you do not exced the [BT proxy limit][btproxy-url] of 3 devices/proxy; check the logs of the proxy if the device is recognized. Note: The [Bluetooth proxy of Shelly devices](https://www.home-assistant.io/integrations/shelly/#bluetooth-support) does not support active connections and thus cannot be used.
1. If above points did not help, please [open an issue](https://github.com/patman15/BMS_BLE-HA/issues/new?assignees=&labels=question&projects=&template=feature_request.yml) providing the advertisement data of the device. To get the data, please go to the [bluetooth integration](https://my.home-assistant.io/redirect/integration/?domain=bluetooth). On your BT adapter select `configure -> advertisement monitor`, click the device in question and provide the information via **`copy to clipboard`**.

### In case you have troubles you'd like to have help with

- please [enable the debug protocol](https://www.home-assistant.io/docs/configuration/troubleshooting/#debug-logs-and-diagnostics) for the [BLE Battery Management integration](https://my.home-assistant.io/redirect/integration/?domain=bms_ble),
- restart Home Assistant, wait till it is fully started up,
- reproduce the issue,
- disable the log (Home Assistant will prompt you to download the log), and finally
- [open an issue](https://github.com/patman15/BMS_BLE-HA/issues/new?assignees=&labels=question&projects=&template=support.yml) with a good description of what your question/issue is and attach the log, or
- [open a bug](https://github.com/patman15/BMS_BLE-HA/issues/new?assignees=&labels=Bug&projects=&template=bug.yml) if you think the behaviour you see is caused by the integration, including a good description of what happened, your expectations, and attach the log.

## FAQ
### My sensors show unknown/unavailable at startup!
The polling interval is 30 seconds. So at startup it takes a few minutes to detect the battery and query the sensors. Then data will be available.

### Can I set a custom polling interval?
Yes, but I strongly discourage that for stability reasons. If you still want to do so, please see the default way to define a [custom interval][custint-url] by Home Assistant. Note that Bluetooth discoveries can take up to a minute in worst case. Thus, please expect side effects, when changing the default of 30 seconds!

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

## Outlook
- Improvements to fulfill the [Home Assistant quality scale](https://www.home-assistant.io/docs/quality_scale/)
- Add option to only have temporary connections (lowers reliability, but helps running more devices via [ESPHome Bluetooth proxy][btproxy-url])
- Add further battery types on [request](https://github.com/patman15/BMS_BLE-HA/issues/new?assignees=&labels=enhancement&projects=&template=feature_request.yml)

## Thanks to
> [@gkathan](https://github.com/patman15/BMS_BLE-HA/issues/2), [@downset](https://github.com/patman15/BMS_BLE-HA/issues/19), [@gerritb](https://github.com/patman15/BMS_BLE-HA/issues/22), [@Goaheadz](https://github.com/patman15/BMS_BLE-HA/issues/24), [@alros100, @majonessyltetoy](https://github.com/patman15/BMS_BLE-HA/issues/52), [@snipah, @Gruni22](https://github.com/patman15/BMS_BLE-HA/issues/59), [@azisto](https://github.com/patman15/BMS_BLE-HA/issues/78), [@BikeAtor, @Karatzie](https://github.com/patman15/BMS_BLE-HA/issues/57), [@SkeLLLa,@romanshypovskyi](https://github.com/patman15/BMS_BLE-HA/issues/90), [@riogrande75, @ebagnoli, @andreas-bulling](https://github.com/patman15/BMS_BLE-HA/issues/101), [@goblinmaks, @andreitoma-github](https://github.com/patman15/BMS_BLE-HA/issues/102), [@hacsler](https://github.com/patman15/BMS_BLE-HA/issues/103), [@ViPeR5000](https://github.com/patman15/BMS_BLE-HA/pull/182), [@edelstahlratte](https://github.com/patman15/BMS_BLE-HA/issues/161), [@nezra](https://github.com/patman15/BMS_BLE-HA/issues/164), [@Fandu21](https://github.com/patman15/BMS_BLE-HA/issues/194), [@rubenclark74](https://github.com/patman15/BMS_BLE-HA/issues/186), [@gavrilov](https://github.com/patman15/BMS_BLE-HA/issues/247)

for helping with making the integration better.

## References
- [Home Assistant Add-on: BatMON](https://github.com/fl4p/batmon-ha)
- Daly BMS: [esp32-smart-bms-simulation](https://github.com/roccotsi2/esp32-smart-bms-simulation)
- Jikong BMS: [esphome-jk-bms](https://github.com/syssi/esphome-jk-bms)
- JBD BMS: [esphome-jbd-bms](https://github.com/syssi/esphome-jbd-bms)
- D-powercore BMS: [Strom BMS monitor](https://github.com/majonessyltetoy/strom)
- Redodo BMS: [LiTime BMS bluetooth](https://github.com/calledit/LiTime_BMS_bluetooth)

[license-shield]: https://img.shields.io/github/license/patman15/BMS_BLE-HA.svg?style=for-the-badge&cacheSeconds=86400
[releases-shield]: https://img.shields.io/github/release/patman15/BMS_BLE-HA.svg?style=for-the-badge&cacheSeconds=14400
[releases]: https://github.com//patman15/BMS_BLE-HA/releases
[effort-shield]: https://img.shields.io/badge/Effort%20spent-444_hours-gold?style=for-the-badge&cacheSeconds=86400
[install-shield]: https://img.shields.io/badge/dynamic/json?style=for-the-badge&color=green&label=Analytics&suffix=%20Installs&cacheSeconds=15600&url=https://analytics.home-assistant.io/custom_integrations.json&query=$.bms_ble.total&cacheSeconds=14400
[btproxy-url]: https://esphome.io/components/bluetooth_proxy
[custint-url]: https://www.home-assistant.io/common-tasks/general/#defining-a-custom-polling-interval
