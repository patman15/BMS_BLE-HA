# BLE Battery Management Systems for Home Assistant

This integration allows to monitor Bluetooth Low Energy (BLE) battery management systems (BMS) from within [Home Assistant](https://www.home-assistant.io/). The integration provides information on the battery
- SoC (state of charge) [%]
- stored energy [Wh]
- voltage [V]
- current [A]
- temperature [°C]
- (remaining) runtime [s]

![grafik](https://github.com/patman15/BLE_BMS-HA/assets/14628713/99088715-fa2d-4d3d-90a5-967a8bf08305)

## Supported Devices
- Offgridtec LiFePo4 Smart Pro: type A & B (show up as `SmartBat-Axxxxx` or `SmartBat-Bxxxxx`)

## Outlook
Add further battery types from [Home Assistant Add-on: BatMON](https://github.com/fl4p/batmon-ha)

## Troubleshooting
- Polling interval is 30 seconds. At startup it takes a few minutes to detect the battery and query the sensors.
- In case you have severe troubles, please enable the debug protocol for the integration and open an issue with a good description of what happened and the relevant snippet from the log.
