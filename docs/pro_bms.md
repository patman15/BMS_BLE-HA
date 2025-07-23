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
- **Manufacturer ID**: `0x004C` (NB: Apple's manufacturer ID?)
- **Notification Characteristic**: `0000fff4-0000-1000-8000-00805f9b34fb` (read/notify)
- **Write Characteristic**: `0000fff3-0000-1000-8000-00805f9b34fb` (write)

## BLE Communication Protocol

### Initialization Sequence

The device requires 4 initialization commands sent to the write characteristic:

```python
INIT_COMMANDS = [
    "55aa0a0101558004077be16968",  # Command 1: General init (Function 0x04)
    "55aa070101558040000095",      # Command 2: Get info (Function 0x40)
    "55aa070101558042000097",      # Command 3: Extended info (Function 0x42)
    "55aa0901015580430000120084",  # Command 4: Function 0x43 with 18 data points
]

# After init responses, send acknowledgment and start data streaming
INIT_ACK_COMMAND = "55aa070101558006000055"     # Acknowledge init complete
DATA_START_COMMAND = "55aa09010155804300550000c1"  # Function 0x43: Start data stream
```

### Data Packet Format (50 bytes)

After initialization, the device streams 50-byte packets at ~1Hz via notifications:

| Offset | Size | Field | Description | Formula/Units |
|--------|------|-------|-------------|---------------|
| 0-1 | 2 | Header | Fixed: `0x55 0xAA` | Start marker |
| 2 | 1 | Length | `0x2E` (46 bytes follow) | - |
| 3 | 1 | Type | `0x04` (real-time data) | - |
| 4-7 | 4 | Fixed | `0x80 0xAA 0x01 0x43` | Protocol bytes |
| 8-9 | 2 | Voltage | Battery voltage | `value * 0.01` V |
| 10-11 | 2 | Unknown | - | - |
| 12-13 | 2 | Current | Unsigned current magnitude | `value / 1000.0` A |
| 14 | 1 | Unknown | - | - |
| 15 | 1 | Current Direction | Bit 7: 1=discharge, 0=charge | - |
| 16 | 1 | Temperature | Primary temperature sensor (unsigned) | `value / 10.0` °C |
| 17-19 | 3 | Unknown | - | - |
| 20-21 | 2 | Remaining Capacity | Current charge in battery | `value * 10` mAh |
| 22-23 | 2 | Unknown | - | - |
| 24 | 1 | **State of Charge** | Battery percentage | 0-100% |
| 25-27 | 3 | Unknown | - | - |
| 28-29 | 2 | Runtime (if available) | Remaining time | minutes |
| 30-49 | 20 | Unknown/Reserved | - | - |

### Data Conversion Details

1. **Voltage**: 
   - Read 16-bit little-endian from bytes 8-9
   - Multiply by 0.01 to get voltage in Volts

2. **Current**:
   - Read 16-bit little-endian unsigned from bytes 12-13 (magnitude only)
   - Check bit 7 of byte 15 for direction (1 = discharging, 0 = charging)
   - Apply sign: negative for discharge, positive for charge
   - Divide by 1000 to convert mA to Amps

3. **Temperature**:
   - Read byte 16 (unsigned byte: 0-255)
   - Divide by 10 to get temperature in °C
   - Actual range: 0°C to 25.5°C (limited by unsigned byte encoding)
   - Note: While protocol documentation mentions -40°C to 100°C, the single unsigned byte implementation cannot represent negative temperatures

4. **Remaining Capacity**:
   - Read 16-bit little-endian from bytes 20-21
   - Multiply by 10 to get mAh
   - Divide by 1000 to get Ah

5. **State of Charge (SOC)**:
   - Read byte 24 directly as percentage (0-100)

6. **Total Capacity**:
   - Calculated from remaining capacity and SOC
   - Formula: `(remaining_capacity_ah / soc) * 100`
   - Default: 129.0 Ah if SOC is 0

7. **Power**:
   - Calculated: `voltage * current`

8. **Runtime** (experimental):
   - Bytes 28-29 may contain runtime in minutes
   - Only valid when discharging (current < 0)
   - Valid range: 1-65534 minutes
   - When charging, runtime is not available

## Protocol Frame Structure

### Request Frame (from host)

| Field | Header | Length | Frame Type | Source | Direction | Target | Function | Parameters | Checksum |
|-------|--------|--------|------------|--------|-----------|--------|----------|------------|----------|
| Bytes | 2 | 1 | 1 | 1 | 1 | 1 | 1 | n | 1 |
| Value | 0x55AA | n | 0x01 | 0x01 | 0xAA | 0x80 | 0xXX | ... | sum |

### Response Frame (from BMS)

| Field | Header | Length | Frame Type | Source | Direction | Target | Function+Status | Parameters | Checksum |
|-------|--------|--------|------------|--------|-----------|--------|-----------------|------------|----------|
| Bytes | 2 | 1 | 1 | 1 | 1 | 1 | 2 | n | 1 |
| Value | 0x55AA | n | 0x03/0x04 | 0x80 | 0xAA | 0x01 | 0xXX 0x00 | ... | sum |

**Notes**:
- Frame Type: 0x01 = command, 0x03 = init response, 0x04 = data
- Checksum: Sum of all bytes between length (exclusive) and checksum (exclusive)
- All multi-byte values use little-endian byte order

## Available Functions (from Protocol Documentation)

While these functions are documented, only the initialization and data streaming commands have been tested:

- **0x02**: Current zero calibration
- **0x04**: General initialization (used)
- **0x05**: Current/shunt calibration
- **0x10**: Total capacity setting
- **0x13**: Overvoltage threshold
- **0x14**: Undervoltage threshold
- **0x18**: Over-temperature threshold
- **0x1A**: SOC setup
- **0x20**: Temperature calibration
- **0x24**: Under-temperature threshold
- **0x27**: Full voltage function
- **0x40**: Get device info (used)
- **0x42**: Get extended info (used)
- **0x43**: Read data/history (used for real-time streaming)
- **0x56**: Real-time data (documented but non-functional)
- **0x71**: Protection status

## Implementation Notes

1. **Critical**: Use Function 0x43 for data streaming, NOT 0x56
2. **Initialization**: Device requires all 4 init commands before streaming
3. **Checksum**: Currently bypassed as the algorithm is unknown
4. **Timeouts**: 10-second timeout for data after initialization
5. **Packet Validation**: Always verify header and packet length
6. **Buffer Management**: Handle fragmented packets properly

## Home Assistant Integration

The plugin exposes these entities:

### Sensors (Read-Only)
- `sensor.bms_voltage` - Battery voltage (V)
- `sensor.bms_current` - Current flow (A, negative = discharge)
- `sensor.bms_battery_level` - State of charge (%)
- `sensor.bms_temperature` - Temperature (°C)
- `sensor.bms_remaining_capacity` - Remaining charge (Ah)
- `sensor.bms_cycle_charge` - Current charge in battery (Ah)
- `sensor.bms_design_capacity` - Total battery capacity (Ah)
- `sensor.bms_power` - Power (W)
- `sensor.bms_runtime` - Remaining runtime when discharging (seconds)
- `binary_sensor.bms_battery_charging` - Charging status

### Calculated Values
- **cycle_capacity**: Stored energy (Wh) = voltage × cycle_charge

## Testing

Run the test suite:
```bash
pytest tests/test_pro_bms.py -v
```

Test coverage includes:
- Packet parsing and validation
- Current direction handling
- Temperature range validation
- Buffer management
- Edge cases and error conditions

## Future Enhancements

1. **Protection Status Monitoring** - Implement function 0x71 for safety alerts
2. **Configuration Commands** - Add capacity setting, temperature calibration
3. **Historical Data** - Implement historical data reading for trends
4. **Runtime Extraction** - Confirm byte location for runtime data
5. **Checksum Algorithm** - Reverse engineer the checksum calculation

## Troubleshooting

### Common Issues

| Problem | Cause | Solution |
|---------|-------|----------|
| No data after init | Incomplete initialization | Ensure all 4 init commands sent |
| Wrong current direction | Incorrect byte/bit check | Use byte 15 bit 7 for direction |
| Temperature always 0°C | Sensor disconnected | Check physical sensor connection |
| SOC shows 0% | Device calibrating | Wait 10-30 seconds after connection |
| Multiple devices conflict | Same name in HA | MAC suffix ensures uniqueness |
| No runtime value | Battery charging | Runtime only available when discharging |
| Checksum errors | Different algorithm | Checksum validation is bypassed |

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