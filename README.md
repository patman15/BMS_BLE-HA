# <img src="https://github.com/patman15/BMS_BLE-HA/assets/14628713/0ee84af9-300a-4a26-a098-26954a46ec36" width="32" height="32"> BLE Battery Management Systems for Home Assistant

[![GitHub Release][releases-shield]][releases]
[![License][license-shield]](LICENSE)
[![Effort][effort-shield]](https://buymeacoffee.com/patman15)
[![HACS][install-shield]](https://hacs.xyz/docs/use/)

This integration allows to monitor Bluetooth Low Energy (BLE) battery management systems (BMS) from within [Home Assistant](https://www.home-assistant.io/). After installation, no configuration is required. You can use the [ESPHome Bluetooth proxy][btproxy-url] to extend the Bluetooth coverage range. By using standard dashboard cards, it is easy to visualize the current state of remote batteries.

![dashboard](https://github.com/user-attachments/assets/56136072-db44-4ffa-94e5-dc165d0fc1b4)


* [Features](#features)
* [Installation](#installation)
* [Removing the Integration](#removing-the-integration)
* [Troubleshooting](#troubleshooting)
    * [Known Issues](#known-issues)
    * [Device is not Recognized](#if-your-device-is-not-recognized)
    * [Support Issues](#in-case-you-have-troubles-youd-like-to-have-help-with)
* [Energy Dashboard Integration](#energy-dashboard-integration)
* [FAQ](#faq)
* [Outlook](#outlook)
* [Thanks to](#thanks-to)
* [References](#references)

## Features
- Zero configuration
- Auto detects compatible batteries
- Supports [ESPHome Bluetooth proxy][btproxy-url]  (limit: 3 devices/proxy)
- Any number of batteries in parallel
- Native Home Assistant integration (works with all [HA installation methods](https://www.home-assistant.io/installation/#advanced-installation-methods))
- Readout of individual cell voltages to be able to judge battery health
- 100% test coverage

### Supported Devices
- ABC/SOK BMS (show up as `ABC-`&#x2026;, `SOK-`&#x2026;)
- Braun Power BMS (show up as `BL-`&#x2026; or `HSKS-`&#x2026;)
- ANT BMS (show up as `ANT-BLE`&#x2026;)
- CBT Power BMS, Creabest batteries
- D-powercore BMS (show up as `DXB-`&#x2026;), Fliteboard batteries (show up as `TBA-`&#x2026;)
- Daly BMS (show up as `DL-`&#x2026;)
    - 100Balance BMS
    - Bulltron batteries
- E&J Technology BMS (show ups as `libatt`&#x2026;)
    - Elektronicx batteries (show up as `LT-`&#x2026;)
    - Lithtech batteries (show up as `LT-12V-`&#x2026; or `L-12V`&#x2026;)
    - Meritsun, Supervolt v1 (show up as `SV12V`&#x2026;), and Volthium (show up as `V-12V`&#x2026;) batteries
- ECO-WORTHY + BW02 adapter (show up as `ECO-WORTHY`&#x2026;)
    - DCHOUSE batteries (show up as `DCHOUSE`&#x2026;)
- Ective, Startcraft, Topband batteries (show up as `$PFLAC`&#x2026;, `NWJ20`&#x2026;, `ZM20`&#x2026;)
- Felicity ESS (show up as `F10`&#x2026;) and FLB batteries (show up as `F07`&#x2026;)
- JBD BMS, Jiabaida (show up as `JBD-`&#x2026;)
    - accurat batteries, Aolithium batteries
    - BasenGreen, Bulltron, DCHOUSE, ECO-WORTHY, Epoch batteries
    - Eleksol, Fritz Berger, Liontron, LANPWR, OGRPHY, Perfektium, Ultimatron batteries
    - SBL batteries (show up as `SBL-`&#x2026;), Supervolt v3 batteries (show up as `SX1`&#x2026;), Vatrer batteries
- JK BMS, Jikong, (HW version &ge; 6 required)
- LiTime, Power Queen, and Redodo batteries
- LiPower BMS
- NEEY balancer (4th gen) (show up as `GW-24S`&#x2026;)
- Offgridtec LiFePo4 Smart Pro: type A & B (show up as `SmartBat-A`&#x2026; or `SmartBat-B`&#x2026;)
- PaceEX BMS (show up as `PC-`&#x2026;)
- Pro BMS Smart Shunt
    - Foxwell BT630
    - Leagend CM100
- Renogy BMS, Renogy Pro BMS
- RoyPow batteries
- Seplos v2 (show up as `BP[0-2]?`)
- Seplos v3 (show up as `SP[0,1,4-6]`&#x2026;)
- Super-B Epsilon BMS (show up as `Epsilon-`&#x2026;)
- TDT BMS
    - Wattcycle batteries
- TianPower BMS (show up as `TP_`&#x2026;)
- Vatrer BMS (show up as `YYMMDDVVVAAAAxx` (date, V, Ah))

If you would like to get your battery/BMS supported please consider raising a pull request for [aiobmsble](https://github.com/patman15/aiobmsble) following the [contribution guidelines](https://github.com/patman15/aiobmsble?tab=contributing-ov-file) or raise [a new issue](https://github.com/patman15/BMS_BLE-HA/issues/new?assignees=&labels=question&projects=&template=feature_request.yml) giving your BMS/battery type in the title. Please provide the information requested by the template (see *additional context*).

### Provided Information
> [!CAUTION]
> This integration (including Home Assistant) **shall not be used for safety relevant operations**! The correctness or availability of data cannot be guaranteed (see [warranty section of the license](LICENSE)),
> since the implementation is mostly based on openly available information or non-validated vendor specifications.
> Further, issues with the Bluetooth connection, e.g. disturbances, can lead to unavailable or incorrect values.
> 
> **Do not rely** on the values to control actions that prevent battery damage, overheating (fire), or similar.

Platform | Name | Unit | Description | Optional Attributes
-- | -- | -- | -- | --
`binary_sensor` | battery charging | `bool` | indicates `True` if battery is charging | battery mode
`sensor` | charge cycles | `#` | lifetime number of charge cycles | package charge cycles
`sensor` | current | `A` | positive for charging, negative for discharging | balance current, package current
`sensor` | power | `W` | positive for charging, negative for discharging
`sensor` | runtime | `s` | remaining discharge time till SoC 0%, `unavailable` during idle/charging
`sensor` | SoC | `%` | state of charge, range 100% (full) to 0% (battery empty) | package SoC
`sensor` | stored energy | `Wh` | currently stored energy
`sensor` | temperature | `°C` | (average) battery temperature | individual temperature values
`sensor` | voltage | `V` | overall battery voltage | package voltage
||||
|||| **Diagnosis Sensors**
`binary_sensor` | problem | `bool` | indicates `True` if the battery reports an issue or plausibility checks on values fail | problem code
`sensor` | delta cell voltage | `V` | maximum difference between any two cells in a pack | cell voltages
`sensor`* | max cell voltage | `V` | overall maximum cell voltage in the system | cell number
`sensor`* | min cell voltage | `V` | overall minimum cell voltage in the system | cell number
`sensor`* | link quality  | `%` | successful BMS queries from the last hundred update periods
`sensor`* | RSSI          | `dBm`| received signal strength indicator

*) sensors are disabled by default

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

## Troubleshooting

> [!NOTE]
> A lot of transient issues are due to problems with Bluetooth adapters. Most prominent example is the performance limitation of the [internal Raspberry Pi BT adapter](https://www.home-assistant.io/integrations/bluetooth/#cypress-based-adapters), resulting in, e.g., sometimes wrong data, when you have multiple devices. Please check the Home Assistant [Bluetooth integration](https://www.home-assistant.io/integrations/bluetooth/) page for known issues and consider using a [recommended high-performance adapter](https://www.home-assistant.io/integrations/bluetooth/#known-working-high-performance-adapters).

### Known Issues

<details><summary>ECO-WORTHY batteries "<code>ECOxxxx</code>"</summary>
ECO-WORTHY batteries that show up as <code>ECOxxxx</code> use classic Bluetooth and do not support Bluetooth Low Energy (BLE). Thus, they unfortunately cannot be integrated.
The advertisement contains <code>{"name":"ECOxxxx","service_uuids":["0000ff00-0000-1000-8000-00805f9b34fb","00000001-0000-1000-8000-00805f9b34fb"]</code>
</details>
<details><summary>Elektronicx, Lithtech batteries</summary>
Bluetooth is turned off, when there is no current. Thus, device will get unavailable / cannot be added.
</details>
<details><summary>Batteries with JBD BMS</summary>
JBD BMS detection unfortunately needs to rely on name patterns. If you renamed your battery it most likely will not be detected. I do appreciate issues being raised for new vendor naming schemes to ease the life of other users. To help, please follow the instructions in the last list item for <a href="#if-your-device-is-not-recognized">non-detected devices</a>.
</details>
<details><summary>Liontron batteries</summary>
These batteries need a shorter interval between queries. Be a bit patient to get them added and set a <a href="[custint-url]">custom interval</a> of about 9s to keep a stable connection.
</details>
<details><summary>Seplos v2</summary>
The internal Bluetooth adapter issues <code>AT</code> commands in regular intervals which can interfere with BMS messages causing them to be corrupted. This impacts data availability (<code>link quality</code>).
</details>

### If your device is not recognized

1. Check that your BMS type is listed as [supported device](#supported-devices)
1. If a name detection pattern is listed ("show up as"), make sure your device matches it.
1. Check the [known issues](#known-issues) for an entry for your BMS.
1. Make sure that no other device is connected to the BMS, e.g. app on your phone
1. Check that your are running the [latest release](https://github.com//patman15/BMS_BLE-HA/releases) of the integration
1. Go to the [advertisement monitor](https://my.home-assistant.io/redirect/bluetooth_advertisement_monitor/) and verify that your device shows up there. Also, please ensure that your `RSSI` value is `>= -75 dBm`. If your device is missing or the `RSSI` value is `-80 dBm`or worse, please check your BT setup (is the device in range?).
1. If you use a BT proxy, make sure you have set `active: true` and that you do not exceed the [BT proxy limit][btproxy-url] of 3 devices/proxy; check the logs of the proxy if the device is recognized. Note: The [Bluetooth proxy of Shelly devices](https://www.home-assistant.io/integrations/shelly/#bluetooth-support) does not support active connections and thus cannot be used.
1. If above points did not help, please go to the [Bluetooth integration](https://my.home-assistant.io/redirect/integration/?domain=bluetooth). On your BT adapter select `configure`.
    1.  Verify that you have connection slots available.
    1.  Go to the [advertisement monitor](https://my.home-assistant.io/redirect/bluetooth_advertisement_monitor/) and click the device in question. Please provide the information via **`copy to clipboard`** to [a new issue](https://github.com/patman15/BMS_BLE-HA/issues/new?assignees=&labels=question&projects=&template=feature_request.yml) giving your BMS/battery type in the title.

### Some/all sensors go `unavailable` temporarily or permanently
In case sensors are reported `unavailable` please enable the diagnostic sensors, i.e. `RSSI` and `link quality` and check your connection quality. The value of `link quality` results from (temporarily) bad `RSSI` values, which are impacted by disturbances of the Bluetooth communication. Your quality should be at least *fair* according to the following table:
 
Quality | link quality [%] | RSSI [dBm]
--  | -- | --
excellent | 98 to 100 | -60 to high
good | 90 to 98 | -60 to -75
fair | 80 to 90 | -75 to -80
weak | 60 to 80 | -80 to -90
bad | 0 to 60  | -90 to low

Verify that you have a proper Bluetooth setup according to the recommendations for the Home Assistant Bluetooth Integrations, see [this note](#troubleshooting).
In case your `RSSI` level is *fair* or better, but still the sensors show `unknown`, please follow the [instructions for opening an issue](#in-case-you-have-troubles-youd-like-to-have-help-with). Please attach
- a debug log  as a file,
- diagnosis data as a file, and
- a 24hrs diagram of `RSSI` and `link quality` sensor.

### In case you have troubles you'd like to have help with

- please [enable the debug protocol](https://www.home-assistant.io/docs/configuration/troubleshooting/#debug-logs-and-diagnostics) for the [BLE Battery Management integration](https://my.home-assistant.io/redirect/integration/?domain=bms_ble),
- restart Home Assistant, wait till it is fully started up,
- reproduce the issue,
- disable the log (Home Assistant will prompt you to download the log), and finally
- [open an issue](https://github.com/patman15/BMS_BLE-HA/issues/new?assignees=&labels=question&projects=&template=support.yml) with a good description of what your question/issue is and attach the log, or
- [open a bug](https://github.com/patman15/BMS_BLE-HA/issues/new?assignees=&labels=Bug&projects=&template=bug.yml) if you think the behaviour you see is caused by the integration, including a good description of what happened, your expectations, and attach the log.

## Energy Dashboard Integration

If you want your battery to be integrated with the Home Assistant [energy dashboard](https://my.home-assistant.io/redirect/energy/) you need to integrate the reported power value separately for charge and discharge power to two energy values. Here are the detailed steps for energy dashboard configuration in your `configuration.yaml` (you achieve the same result by configuring equivalent [helpers](https://my.home-assistant.io/redirect/helpers/)):
### Add two template sensors
```yaml
template:
  - sensor:
    - unique_id: charge_power
      state: "{{ [states('sensor.smartbat_..._power') | float, 0] | max}}"
      unit_of_measurement: 'W'
      state_class: measurement
      device_class: power
      availability: "{{ has_value('sensor.smartbat_..._power') }}"
    - unique_id: discharge_power
      state: "{{ [states('sensor.smartbat_..._power') | float, 0] | min | abs}}"
      unit_of_measurement: 'W'
      state_class: measurement
      device_class: power
      availability: "{{ has_value('sensor.smartbat_..._power') }}"
```
### Add two integration sensors
```yaml
sensor:
  - platform: integration
    name: energy_in
    source: sensor.template_charge_power
  - platform: integration
    name: energy_out
    source: sensor.template_discharge_power
```

Then go to the [energy dashboard configuration](https://my.home-assistant.io/redirect/config_energy/), add a battery system and set the two sensors `energy_in` and `energy_out`.

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
State template | ```{{ iif(has_value("sensor.smartbat_..._delta_cell_voltage"), state_attr("sensor.smartbat_..._delta_cell_voltage", "cell_voltages")[0], None) }}```<br>The index `[0]` can be in the range from 0 to the number of cells-1, i.e. 0-3 for a 4 cell battery.
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
        {{ state_attr('sensor.smartbat_..._delta_cell_voltage', 'cell_voltages')[0] }}
      unit_of_measurement: 'V'
      state_class: measurement
      device_class: voltage
      availability: >- 
        {{ has_value('sensor.smartbat_..._delta_cell_voltage') }}
```
There are plenty more functions you can use, please see [templating](https://www.home-assistant.io/docs/configuration/templating/).

### I want to know the cell with the lowest voltage!
Please follow the explanations in the previous question but use the following:

Field | Content
-- | --
State template | `{%- if has_value("sensor.smartbat_..._minimal_cell_voltage") %} {{ state_attr("sensor.smartbat_..._minimal_cell_voltage", "cell_number") }} {% else %} None {% endif -%}`

### I need a discharge sensor not the charging indicator, can I have that?
Sure, use, e.g. a [threshold sensor](https://my.home-assistant.io/redirect/config_flow_start/?domain=threshold) based on the current to/from the battery. Negative means discharging, positive is charging.

### My BMS needs a pin, how can I enter it?

Then you need to pair your device first. This is procedure is only required once for each device.
- Open a [terminal to Home Assistant](https://www.home-assistant.io/common-tasks/supervised/#installing-and-using-the-ssh-add-on).
- Use the command `bluetoothctl devices` to check that your devices is detected and
- run `bluetoothctl pair <MAC_of_BMS>` to start pairing the device.

Once pairing is done, the integration should automatically detect the BMS.

## Outlook
- Develop towards a [Home Assistant core integration](https://www.home-assistant.io/integrations/)
- Improvements to fulfill the [Home Assistant quality scale](https://www.home-assistant.io/docs/quality_scale/)
- Add option to only have temporary connections (lowers reliability, but helps running more devices via [ESPHome Bluetooth proxy][btproxy-url])

## Thanks to
all [contributors of aiobmsble](https://github.com/patman15/aiobmsble?tab=readme-ov-file#thanks-to) (the BMS library) for helping with making the integration better.

## References
- [Home Assistant Add-on: BatMON](https://github.com/fl4p/batmon-ha)
- [ESPHome BMS components](https://github.com/syssi)

[license-shield]: https://img.shields.io/github/license/patman15/BMS_BLE-HA?style=for-the-badge&color=orange&cacheSeconds=86400
[releases-shield]: https://img.shields.io/github/release/patman15/BMS_BLE-HA.svg?style=for-the-badge&cacheSeconds=14400
[releases]: https://github.com//patman15/BMS_BLE-HA/releases
[effort-shield]: https://img.shields.io/badge/Effort%20spent-743_hours-gold?style=for-the-badge&cacheSeconds=86400
[install-shield]: https://img.shields.io/badge/dynamic/json?style=for-the-badge&color=green&label=HACS&suffix=%20Installs&cacheSeconds=15600&url=https://analytics.home-assistant.io/custom_integrations.json&query=$.bms_ble.total&cacheSeconds=14400
[btproxy-url]: https://esphome.io/components/bluetooth_proxy
[custint-url]: https://www.home-assistant.io/common-tasks/general/#defining-a-custom-polling-interval
