# BT630 Pro BMS Smart Shunt Documentation

## Overview

The BT630 "Pro BMS" is actually a smart shunt device, not a full battery management system. It measures system-level battery parameters (voltage, current, temperature, SOC) via Bluetooth Low Energy. The device requires an initialization sequence before streaming data via BLE notifications.

The version used for analysis and developing this plugin was: https://www.amazon.com/dp/B0F8HV7Q8K
"FOXWELL BT630 600A Smart Battery Monitor with Shunt, 10–120V Real-Time Volts, Amps, Watts, Capacity & Runtime Tracking, High and Low Voltage Alarm for RV/Solar Panel/Marine/Off‑Grid/Backup Power"

Which appears to be a specific branding of the white-label: https://leagend.com/products/cm100

Protocol documentation is available here but seems to not always be correct: https://doc.dh5z.com/bt630/UserManual.html

**Important Protocol Note**: While the official BT630 protocol documentation specifies Function 0x56 for real-time data, extensive testing has shown this does not work. The working implementation uses Function 0x43, which the documentation labels as "historical data" but actually provides real-time values.

## Device Identification

- **Local Name**: "Pro BMS"
- **Service UUID**: `0000fff0-0000-1000-8000-00805f9b34fb`
- **Notification Characteristic**: `0000fff4-0000-1000-8000-00805f9b34fb` (read/notify)
- **Write Characteristic**: `0000fff3-0000-1000-8000-00805f9b34fb` (write)

### Device Discovery

The Pro BMS is detected using:
- Exact local name match: "Pro BMS"
- Service UUID: `0000fff0-0000-1000-8000-00805f9b34fb`
- Must be connectable

**Note**: The device no longer uses manufacturer ID matching due to conflicts with other BMS devices. The device exhibits unusual Bluetooth LE advertisement behavior, broadcasting with hundreds of different manufacturer IDs in a single advertisement packet, which caused detection issues.

### Device Name Handling

The plugin includes robust device name handling to address cases where:
- The device name is `None` during initial discovery
- The device advertises its MAC address as the name instead of "Pro BMS"

When these conditions are detected, the plugin automatically creates a new BLEDevice instance with the proper "Pro BMS" name to ensure compatibility with Home Assistant's coordinator requirements.

## BLE Communication Protocol

### Initialization Sequence

The device uses a simplified initialization sequence:

```python
# Extended info command to trigger initialization
CMD_EXTENDED_INFO = "55aa070101558042000097"

# After receiving init responses, send:
CMD_ACK = "55aa070101558006000055"          # Acknowledge init complete
CMD_DATA_STREAM = "55aa0901015580430000120084"  # Start data streaming (Function 0x43)
```

The device may send multiple initialization response packets (type 0x03) before starting data streaming.

### Data Packet Format (50 bytes)

After initialization, the device streams 50-byte packets at ~1Hz via notifications:

| Offset | Size | Field | Description | Formula/Units |
|--------|------|-------|-------------|---------------|
| 0-1 | 2 | Header | Fixed: `0x55 0xAA` | Start marker |
| 2 | 1 | Length | `0x2D` (45 bytes follow) | - |
| 3 | 1 | Type | `0x04` (real-time data) | - |
| 4-7 | 4 | Fixed | `0x80 0xAA 0x01 0x70` | Protocol bytes |
| 8-9 | 2 | Voltage | Battery voltage | Little-endian, `value * 0.01` V |
| 10-11 | 2 | Unknown | - | - |
| 12-13 | 2 | Current | Current magnitude | Little-endian, `value / 1000.0` A |
| 14 | 1 | Unknown | - | - |
| 15 | 1 | Status/Direction | Bit 7: discharge flag (1=discharge, 0=charge) | Bits 0-6: protection status |
| 16 | 1 | Temperature | Primary temperature sensor | `value / 10.0` °C |
| 17-19 | 3 | Unknown | Reserved (always 0x00 0x00 0x00) | - |
| 20-21 | 2 | Remaining Capacity | Current charge in battery | `value * 10` mAh |
| 22-23 | 2 | Unknown | - | - |
| 24 | 1 | **State of Charge** | Battery percentage | 0-100% |
| 25-27 | 3 | Unknown | - | - |
| 28-29 | 2 | Runtime | Remaining time (when discharging) | minutes |
| 30-39 | 10 | Unknown/Reserved | - | - |
| 40-41 | 2 | Design Capacity | Total battery capacity | `value / 100.0` Ah |
| 42-49 | 8 | Unknown/Reserved | - | - |

### Data Conversion Details

1. **Voltage**:
   - Read 16-bit little-endian from bytes 8-9
   - Multiply by 0.01 to get voltage in Volts

2. **Current**:
   - Read 4 bytes starting at offset 12 (bytes 12-15)
   - Bytes 12-13: Current magnitude as 16-bit little-endian unsigned (mA)
   - Byte 15 bit 7: Discharge flag (1 = discharging, 0 = charging)
   - Lambda implementation: `((x & 0xFFFF) / 1000.0) * (-1 if (x >> 24) & 0x80 else 1)`
     - `x & 0xFFFF`: Extract lower 16 bits (magnitude from bytes 12-13)
     - `x >> 24`: Shift to get byte 15
     - `& 0x80`: Check bit 7 for discharge flag
     - Divide by 1000 to convert mA to Amps
     - Apply negative sign if discharging

3. **Temperature**:
   - Read byte 16 (unsigned byte: 0-255)
   - Divide by 10 to get temperature in °C
   - Valid range: 0°C to 25.5°C (limited by unsigned byte encoding)
   - Note: While some protocol documentation suggests temperature should be 3 bytes (value + sign + padding),
     actual device logs show only the first byte is used, with bytes 17-18 always being 0x00 0x00

4. **Protection Status**:
   - Lower 7 bits of byte 15 indicate protection/error conditions
   - Bit meanings:
     - 0x01: Overvoltage
     - 0x02: Undervoltage
     - 0x04: Overcurrent
     - 0x08: Overtemperature
     - 0x10: Undertemperature
     - 0x20: Short circuit
     - 0x40: Cell imbalance

5. **Remaining Capacity**:
   - Read 16-bit little-endian from bytes 20-21
   - Multiply by 10 to get mAh
   - Divide by 1000 to get Ah

6. **State of Charge (SOC)**:
   - Read byte 24 directly as percentage (0-100)

7. **Design Capacity**:
   - Read 16-bit little-endian from bytes 40-41
   - Divide by 100 to get Ah

8. **Runtime**:
   - Read 16-bit little-endian from bytes 28-29 (minutes)
   - Convert to seconds by multiplying by 60
   - Only available when discharging (current < 0)
   - Valid range: 1-65534 minutes

## Calculated Values

The plugin calculates these additional values:

1. **Power**: `voltage × current` (W) - calculated by base class
2. **Battery Charging**: `True` if current > 0, `False` otherwise - calculated by base class
3. **Cycle Charge**: Same as remaining capacity (Ah)
4. **Cycle Capacity**: `voltage × cycle_charge` (Wh) - calculated by base class
5. **Temperature Values Array**: Single-element array with temperature value

## Home Assistant Integration

The plugin exposes these entities:

### Sensors (Read-Only)
- `sensor.pro_bms_voltage` - Battery voltage (V)
- `sensor.pro_bms_current` - Current flow (A, positive = charging, negative = discharging)
- `sensor.pro_bms_battery` - State of charge (%)
- `sensor.pro_bms_temperature` - Temperature (°C)
- `sensor.pro_bms_power` - Power (W)
- `sensor.pro_bms_runtime` - Remaining runtime when discharging (seconds)
- `sensor.pro_bms_stored_energy` - Stored energy / Cycle capacity (Wh)

### Binary Sensors
- `binary_sensor.pro_bms_battery_charging` - Charging status (on = charging)

### Internal Values (not exposed as sensors)
- `remaining_capacity` - Current charge in battery (Ah)
- `design_capacity` - Total battery capacity (Ah)
- `cycle_charge` - Same as remaining capacity (Ah)

### Template Sensor for Charge Time Remaining

Add this to your `configuration.yaml` to calculate estimated charge time:

```yaml
template:
  - sensor:
      - name: "Pro BMS Charge Time Remaining"
        unique_id: pro_bms_charge_time_remaining
        # Use current > 0 to detect charging instead of binary sensor
        availability: >
          {{ states('sensor.pro_bms_current') not in ['unknown', 'unavailable'] 
             and states('sensor.pro_bms_battery') not in ['unknown', 'unavailable']
             and states('sensor.pro_bms_current') | float(0) > 0.1
             and states('sensor.pro_bms_battery') | float(0) < 99.5 }}
        # Calculate time in hours
        state: >
          {% set current_soc = states('sensor.pro_bms_battery') | float(0) %}
          {% set current_amps = states('sensor.pro_bms_current') | float(0) %}
          {% set voltage = states('sensor.pro_bms_voltage') | float(13.2) %}
          {% set stored_energy_wh = states('sensor.pro_bms_stored_energy') | float(1920) %}
          
          {# Estimate total capacity from stored energy and current SoC #}
          {% if current_soc > 0 %}
            {% set total_capacity_wh = (stored_energy_wh / current_soc) * 100 %}
            {% set total_capacity_ah = total_capacity_wh / voltage %}
          {% else %}
            {% set total_capacity_ah = 146 %}
          {% endif %}
          
          {% set remaining_soc = 100 - current_soc %}
          {% set remaining_ah = (remaining_soc / 100) * total_capacity_ah %}
          
          {% if current_amps > 0.1 %}
            {% set hours = remaining_ah / current_amps %}
            {{ [hours, 24] | min | round(2) }}
          {% else %}
            0
          {% endif %}
        attributes:
          # Formatted time string (no self-reference)
          formatted_time: >
            {% set current_soc = states('sensor.pro_bms_battery') | float(0) %}
            {% set current_amps = states('sensor.pro_bms_current') | float(0) %}
            {% if current_amps > 0.1 and current_soc < 99.5 %}
              {% set voltage = states('sensor.pro_bms_voltage') | float(13.2) %}
              {% set stored_energy_wh = states('sensor.pro_bms_stored_energy') | float(1920) %}
              {% if current_soc > 0 %}
                {% set total_capacity_wh = (stored_energy_wh / current_soc) * 100 %}
                {% set total_capacity_ah = total_capacity_wh / voltage %}
              {% else %}
                {% set total_capacity_ah = 146 %}
              {% endif %}
              {% set remaining_soc = 100 - current_soc %}
              {% set remaining_ah = (remaining_soc / 100) * total_capacity_ah %}
              {% set total_hours = remaining_ah / current_amps %}
              {% set hours = total_hours | int %}
              {% set minutes = ((total_hours % 1) * 60) | int %}
              {% if hours > 0 %}
                {{ hours }}h {{ minutes }}m
              {% else %}
                {{ minutes }} minutes
              {% endif %}
            {% else %}
              Not charging
            {% endif %}
          # Estimated completion time (no self-reference)
          estimated_completion: >
            {% set current_soc = states('sensor.pro_bms_battery') | float(0) %}
            {% set current_amps = states('sensor.pro_bms_current') | float(0) %}
            {% if current_amps > 0.1 and current_soc < 99.5 %}
              {% set voltage = states('sensor.pro_bms_voltage') | float(13.2) %}
              {% set stored_energy_wh = states('sensor.pro_bms_stored_energy') | float(1920) %}
              {% if current_soc > 0 %}
                {% set total_capacity_wh = (stored_energy_wh / current_soc) * 100 %}
                {% set total_capacity_ah = total_capacity_wh / voltage %}
              {% else %}
                {% set total_capacity_ah = 146 %}
              {% endif %}
              {% set remaining_soc = 100 - current_soc %}
              {% set remaining_ah = (remaining_soc / 100) * total_capacity_ah %}
              {% set hours_remaining = remaining_ah / current_amps %}
              {{ (now() + timedelta(hours=hours_remaining)) | as_timestamp | timestamp_custom('%I:%M %p') }}
            {% else %}
              --:--
            {% endif %}
          # Other attributes
          charging_power_kw: >
            {{ states('sensor.pro_bms_power') | float(0) / 1000 | round(2) }}
          charge_rate_per_hour: >
            {% set current_amps = states('sensor.pro_bms_current') | float(0) %}
            {% set voltage = states('sensor.pro_bms_voltage') | float(13.2) %}
            {% set current_soc = states('sensor.pro_bms_battery') | float(0) %}
            {% set stored_energy_wh = states('sensor.pro_bms_stored_energy') | float(1920) %}
            {% if current_soc > 0 %}
              {% set total_capacity_wh = (stored_energy_wh / current_soc) * 100 %}
              {% set total_capacity_ah = total_capacity_wh / voltage %}
              {% if total_capacity_ah > 0 %}
                {{ ((current_amps / total_capacity_ah) * 100) | round(1) }}
              {% else %}
                0
              {% endif %}
            {% else %}
              0
            {% endif %}
          battery_level: "{{ states('sensor.pro_bms_battery') }}%"
          charging_current: "{{ states('sensor.pro_bms_current') }}A"
          battery_voltage: "{{ states('sensor.pro_bms_voltage') }}V"
          battery_power: "{{ states('sensor.pro_bms_power') }}W"
          stored_energy: "{{ states('sensor.pro_bms_stored_energy') }}Wh"
        unit_of_measurement: "h"
        device_class: duration
        state_class: measurement
        icon: >
          {% if states('sensor.pro_bms_current') | float(0) > 0.1 %}
            {% set soc = states('sensor.pro_bms_battery') | float(0) %}
            {% if soc < 10 %}
              mdi:battery-charging-10
            {% elif soc < 20 %}
              mdi:battery-charging-20
            {% elif soc < 30 %}
              mdi:battery-charging-30
            {% elif soc < 40 %}
              mdi:battery-charging-40
            {% elif soc < 50 %}
              mdi:battery-charging-50
            {% elif soc < 60 %}
              mdi:battery-charging-60
            {% elif soc < 70 %}
              mdi:battery-charging-70
            {% elif soc < 80 %}
              mdi:battery-charging-80
            {% elif soc < 90 %}
              mdi:battery-charging-90
            {% else %}
              mdi:battery-charging-100
            {% endif %}
          {% else %}
            mdi:battery
          {% endif %}
```

## Implementation Notes

1. **Function 0x43 vs 0x56**: Despite documentation, Function 0x43 provides real-time data
2. **Simplified Initialization**: Only one init command is sent, device handles the rest
3. **Multiple Init Responses**: Device may send 2-3 init response packets before data
4. **Checksum**: Currently bypassed as the algorithm differs from documentation
5. **Buffer Management**: Robust handling of fragmented packets and buffer alignment
6. **Device Name Handling**: Automatic correction when device name is None or MAC address
7. **Protection Status**: Monitored via byte 15 (lower 7 bits) for safety alerts
8. **Temperature Validation**: Removed - trust the device and Home Assistant to handle values
9. **Current Reading**: Uses a 4-byte read to get both magnitude and sign in one operation

## Testing

Run the test suite:
```bash
pytest tests/test_pro_bms.py -v
```

Test coverage includes:
- Packet parsing and validation
- Current direction handling
- Temperature range validation
- Buffer management and alignment
- Multiple init response handling
- Device name correction
- Protection status detection
- Edge cases and error conditions

## Troubleshooting

### Common Issues

| Problem | Cause | Solution |
|---------|-------|----------|
| Device not discovered | Name is None or MAC address | Plugin auto-corrects to "Pro BMS" |
| No data after init | Device needs time to respond | Wait for multiple init responses |
| Wrong current direction | Incorrect byte/bit check | Use byte 15 bit 7 for direction |
| Temperature shows unexpected value | Check device readings | Verify with actual device data |
| SOC shows 0% | Device calibrating | Wait 10-30 seconds after connection |
| No runtime value | Battery charging | Runtime only available when discharging |
| Slow initialization | Multiple init packets | Normal behavior, wait for data packets |
| Buffer alignment issues | Fragmented packets | Fixed with proper header search |

### Debug Logging

Enable debug logging in Home Assistant to troubleshoot connection issues:

```yaml
logger:
  default: info
  logs:
    custom_components.bms_ble: debug
    custom_components.bms_ble.plugins.pro_bms: debug
```

## References

- **Plugin Source**: [`custom_components/bms_ble/plugins/pro_bms.py`](../custom_components/bms_ble/plugins/pro_bms.py)
- **Test Suite**: [`tests/test_pro_bms.py`](../tests/test_pro_bms.py)
- **Protocol Documentation**: https://doc.dh5z.com/bt630/UserManual.html
- **Product Page**: https://www.amazon.com/dp/B0F8HV7Q8K
- **White-label Version**: https://leagend.com/products/cm100