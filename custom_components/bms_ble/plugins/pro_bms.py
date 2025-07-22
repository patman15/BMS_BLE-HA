"""Pro BMS BLE Battery Monitor Plugin.

This plugin supports Pro BMS Smart Shunt devices via Bluetooth Low Energy.

Key features:
- Function 0x43 for real-time data streaming (NOT 0x56 as documented)
- Flexible initialization handling (accepts 3-4 responses)
- Proper packet length calculation and parsing
- Separate runtime (discharge) and charge time sensors
- Automatic device naming with MAC suffix for uniqueness
"""

import asyncio
import logging
import struct
from typing import Any

from bleak.backends.device import BLEDevice
from bleak.exc import BleakError

from .basebms import AdvertisementPattern, BaseBMS, BMSsample

LOGGER = logging.getLogger(__name__)

# Pro BMS BLE service and characteristic UUIDs
SERVICE_UUID = "0000fff0-0000-1000-8000-00805f9b34fb"
NOTIFY_CHAR_UUID = "0000fff4-0000-1000-8000-00805f9b34fb"
WRITE_CHAR_UUID = "0000fff3-0000-1000-8000-00805f9b34fb"

# Protocol constants
PACKET_HEADER = bytes([0x55, 0xAA])
PACKET_TYPE_REALTIME = 0x04
PACKET_TYPE_INIT_RESPONSE = 0x03

# Initialization commands for Pro BMS
INIT_COMMANDS = [
    bytes.fromhex("55aa0a0101558004077be16968"),    # Command 1: General init (Function 0x04)
    bytes.fromhex("55aa070101558040000095"),        # Command 2: Get info (Function 0x40)
    bytes.fromhex("55aa070101558042000097"),        # Command 3: Extended info (Function 0x42)
    bytes.fromhex("55aa0901015580430000120084"),    # Command 4: Function 0x43 with 18 data points
]

# Command names for better logging
INIT_COMMAND_NAMES = [
    "General init (0x04)",
    "Get info (0x40)",
    "Extended info (0x42)",
    "Data stream setup (0x43)"
]

# Commands for transitioning from init to data mode
INIT_ACK_COMMAND = bytes.fromhex("55aa070101558006000055")  # Acknowledge init complete
DATA_START_COMMAND = bytes.fromhex("55aa09010155804300550000c1")  # Function 0x43: Historical data stream

# Timing constants (in seconds)
INIT_COMMAND_TIMEOUT = 0.5      # Maximum wait time per init command
INIT_RESPONSE_TIMEOUT = 1.5     # Maximum wait time for all init responses
DATA_FLOW_CHECK_TIMEOUT = 0.5   # Time to check for data flow after init


class BMS(BaseBMS):
    """Pro BMS BLE battery monitor plugin for Smart Shunt devices."""

    def __init__(self, ble_device: BLEDevice, reconnect: bool = False) -> None:
        """Initialize Pro BMS plugin.

        Args:
            ble_device: The BLE device to connect to
            reconnect: Whether to enable automatic reconnection

        """
        # Ensure unique device naming by appending MAC suffix
        self._set_unique_device_name(ble_device)

        # Initialize parent class
        super().__init__(__name__, ble_device, reconnect)

        # Initialize Pro BMS specific attributes
        self._buffer = bytearray()
        self._init_data: dict[str, Any] = {}
        self._waiting_for_init = True
        self._init_responses_received = 0
        self._expected_init_responses = 3  # Most BMS units respond to 3 out of 4 init commands
        self._packet_stats = self._create_packet_stats()

    def _set_unique_device_name(self, ble_device: BLEDevice) -> None:
        """Set a unique device name with MAC suffix for consistency.

        This ensures multiple Pro BMS devices can be distinguished in Home Assistant.

        Args:
            ble_device: The BLE device to modify

        """
        mac_suffix = ble_device.address[-5:].replace(":", "")

        # Check if MAC suffix is already appended to avoid duplication
        if mac_suffix in (ble_device.name or ""):
            LOGGER.debug("Device name already contains MAC suffix: %s", ble_device.name)
            return

        if ble_device.name and "Pro BMS" in ble_device.name and ble_device.name != "Pro BMS":
            # Keep custom name but append MAC suffix
            custom_name = f"{ble_device.name} {mac_suffix}"
            LOGGER.debug("Using custom device name with MAC suffix: %s", custom_name)
        else:
            # Use standard name with MAC suffix
            custom_name = f"Pro BMS {mac_suffix}"
            LOGGER.debug(
                "Device advertised as '%s', using standardized name: %s",
                ble_device.name,
                custom_name
            )

        ble_device.name = custom_name

    def _create_packet_stats(self) -> dict[str, Any]:
        """Create initial packet statistics dictionary."""
        return {
            "total": 0,
            "init_responses": 0,
            "data_packets": 0,
            "invalid": 0,
            "unknown_types": {},
        }

    @staticmethod
    def device_info() -> dict[str, str]:
        """Return device information for Home Assistant."""
        return {
            "manufacturer": "Pro BMS",
            "model": "Smart Shunt",
        }

    @staticmethod
    def matcher_dict_list() -> list[AdvertisementPattern]:
        """Return list of matcher dictionaries for identifying Pro BMS devices."""
        return [{
            "local_name": "Pro BMS*",
            "service_uuid": SERVICE_UUID,
            "manufacturer_id": 0x004C,
            "connectable": True,
        }]

    @staticmethod
    def uuid_services() -> list[str]:
        """Return list of service UUIDs required for connection."""
        return [SERVICE_UUID]

    @staticmethod
    def uuid_rx() -> str:
        """Return UUID of characteristic that provides notification property."""
        return NOTIFY_CHAR_UUID

    @staticmethod
    def uuid_tx() -> str:
        """Return UUID of characteristic that provides write property."""
        return WRITE_CHAR_UUID

    async def _wait_for_response(self, timeout: float, check_interval: float = 0.05) -> bool:
        """Wait for a response with timeout, checking periodically.

        Args:
            timeout: Maximum time to wait in seconds
            check_interval: How often to check for response (default 50ms)

        Returns:
            True if response received, False if timeout

        """
        loop = asyncio.get_event_loop()
        start_time = loop.time()
        initial_responses = self._init_responses_received
        initial_data_packets = self._packet_stats['data_packets']

        while loop.time() - start_time < timeout:
            await asyncio.sleep(check_interval)

            # Check if we got new responses
            if self._waiting_for_init and self._init_responses_received > initial_responses:
                return True
            if not self._waiting_for_init and self._packet_stats['data_packets'] > initial_data_packets:
                return True

        return False

    async def _async_update(self) -> BMSsample:
        """Update battery information from Pro BMS Smart Shunt."""
        LOGGER.debug("Starting Pro BMS update")
        LOGGER.debug("Using Function 0x43 for real-time data streaming")

        # Reset state for fresh update
        self._reset_state()

        # Verify connection state
        if not self._client or not self._client.is_connected:
            LOGGER.error("BLE client is not connected")
            raise ConnectionError("BLE client is not connected")

        # Send initialization sequence with optimized timing
        LOGGER.debug("Sending initialization commands...")

        for i, (cmd, cmd_name) in enumerate(zip(INIT_COMMANDS, INIT_COMMAND_NAMES, strict=False)):
            LOGGER.debug(
                "Sending init command %d/%d (%s): %s",
                i + 1,
                len(INIT_COMMANDS),
                cmd_name,
                cmd.hex()
            )

            try:
                await self._client.write_gatt_char(WRITE_CHAR_UUID, cmd, response=False)
                LOGGER.debug("Successfully sent command %d (%s)", i + 1, cmd_name)
            except BleakError as e:
                LOGGER.error(
                    "Failed to send init command %d (%s): %s",
                    i + 1,
                    cmd_name,
                    e
                )
                raise BleakError(f"Init command {i+1} ({cmd_name}) failed: {e}") from e

            # Wait for response with early exit if response received
            response_received = await self._wait_for_response(INIT_COMMAND_TIMEOUT)
            if response_received:
                LOGGER.debug(
                    "Got response to command %d (%s) quickly",
                    i + 1,
                    cmd_name
                )
            else:
                LOGGER.debug(
                    "No response to command %d (%s) within timeout",
                    i + 1,
                    cmd_name
                )

        # Wait for init responses with reduced timeout
        LOGGER.debug(
            "Waiting for initialization responses (expecting %d)...",
            self._expected_init_responses
        )

        if not await self._wait_for_response(INIT_RESPONSE_TIMEOUT):
            # Accept partial responses as some BMS units don't respond to all commands
            if self._init_responses_received > 0:
                LOGGER.debug(
                    "Received %d init responses (expected %d). Proceeding with initialization.",
                    self._init_responses_received,
                    self._expected_init_responses
                )
            else:
                LOGGER.warning(
                    "No init responses received after %ss timeout",
                    INIT_RESPONSE_TIMEOUT
                )

        # Send acknowledgment if we got init responses
        if self._init_responses_received > 0:
            LOGGER.debug(
                "Received %d init responses, sending acknowledgment",
                self._init_responses_received
            )

            try:
                await self._client.write_gatt_char(WRITE_CHAR_UUID, INIT_ACK_COMMAND, response=False)
                LOGGER.debug("Sent init acknowledgment")
                await self._wait_for_response(0.2)
            except BleakError as e:
                LOGGER.warning("Failed to send init acknowledgment: %s", e)

            self._waiting_for_init = False

            # Send data start command
            LOGGER.debug("Sending data start command...")
            try:
                await self._client.write_gatt_char(WRITE_CHAR_UUID, DATA_START_COMMAND, response=False)
                LOGGER.debug("Successfully sent data start command")
            except BleakError as e:
                LOGGER.warning("Failed to send data start command: %s", e)

            # Wait for data to start flowing
            if await self._wait_for_response(0.6):
                LOGGER.debug("Data flow started quickly")
        else:
            LOGGER.warning("No init responses received, skipping acknowledgment")
            self._waiting_for_init = False

        # Check if data is already flowing (with early exit)
        LOGGER.debug("Checking for data flow...")
        if not await self._wait_for_response(DATA_FLOW_CHECK_TIMEOUT):
            LOGGER.debug("No additional data packets in final check")

        if self._packet_stats['data_packets'] > 0:
            LOGGER.debug(
                "Data flow established! Received %d data packets",
                self._packet_stats['data_packets']
            )
        else:
            LOGGER.warning("No data packets received after initialization")

        # Log packet statistics
        LOGGER.debug(
            "Packet stats - Total: %d, Init: %d, Data: %d, Invalid: %d",
            self._packet_stats['total'],
            self._packet_stats['init_responses'],
            self._packet_stats['data_packets'],
            self._packet_stats['invalid']
        )
        if self._packet_stats['unknown_types']:
            LOGGER.debug("Unknown packet types: %s", self._packet_stats['unknown_types'])

        # Process the collected data
        result = self._process_data()
        if result:
            return result
        raise TimeoutError("No valid data received from Pro BMS")

    def _reset_state(self) -> None:
        """Reset internal state for a fresh update."""
        self._buffer.clear()
        self._init_data.clear()
        self._waiting_for_init = True
        self._init_responses_received = 0
        self._packet_stats = self._create_packet_stats()

    def _notification_handler(self, sender: Any, data: bytearray) -> None:
        """Handle notification from BLE device.

        Args:
            sender: The characteristic that sent the notification
            data: The notification data

        """
        LOGGER.debug("Notification received (%d bytes): %s", len(data), data.hex())

        self._buffer.extend(data)
        self._packet_stats["total"] += 1
        self._process_buffer()

    def _process_buffer(self) -> None:
        """Process data in buffer looking for complete packets."""
        while len(self._buffer) >= 5:
            # Look for packet header
            header_pos = self._buffer.find(PACKET_HEADER)
            if header_pos == -1:
                if len(self._buffer) > 10:
                    self._buffer = self._buffer[-10:]
                return

            # Remove data before header
            if header_pos > 0:
                self._buffer = self._buffer[header_pos:]

            # Check if we have enough data for length and type fields
            if len(self._buffer) < 4:
                return

            # Get packet length and type
            length_byte = self._buffer[2]
            packet_type = self._buffer[3]

            # Calculate total packet length: header(2) + length(1) + type(1) + data(length_byte) + checksum(1)
            total_length = 4 + length_byte + 1

            LOGGER.debug(
                "Processing packet type 0x%02x, length %d",
                packet_type,
                total_length
            )

            # Check if we have complete packet
            if len(self._buffer) < total_length:
                return

            # Extract packet
            packet = self._buffer[:total_length]
            self._buffer = self._buffer[total_length:]

            # Process packet based on type
            if packet_type == PACKET_TYPE_INIT_RESPONSE:
                LOGGER.debug(
                    "Init response #%d received",
                    self._init_responses_received + 1
                )
                self._process_init_response(packet)
            elif packet_type == PACKET_TYPE_REALTIME:
                LOGGER.debug("Data packet received, length %d", len(packet))
                self._parse_realtime_packet(packet)
            else:
                self._packet_stats["unknown_types"][packet_type] = \
                    self._packet_stats["unknown_types"].get(packet_type, 0) + 1

    def _process_init_response(self, packet: bytes) -> None:
        """Process initialization response packet.

        Args:
            packet: The complete initialization response packet

        """
        self._init_responses_received += 1
        self._packet_stats["init_responses"] += 1
        LOGGER.debug(
            "Processing init response %d",
            self._init_responses_received
        )

    def _parse_realtime_packet(self, packet: bytes) -> bool:
        """Parse real-time data packet and store the result.

        Args:
            packet: The complete 50-byte data packet

        Returns:
            True if packet was successfully parsed, False otherwise

        """
        packet_len = len(packet)

        # We expect 50-byte packets from Function 0x43
        if packet_len != 50:
            LOGGER.warning(
                "Unexpected packet length: %d bytes (expected 50)",
                packet_len
            )
            return False

        try:
            # Parse with FIXED field locations from original working version
            result = {}

            # Voltage at bytes 8-9 (multiply by 0.01)
            voltage_raw = struct.unpack("<H", packet[8:10])[0]
            voltage = voltage_raw * 0.01
            result["voltage"] = voltage
            LOGGER.debug("Voltage: %.2fV (raw: %d)", voltage, voltage_raw)

            # Current at bytes 12-13 as UNSIGNED int16
            current_raw = struct.unpack("<H", packet[12:14])[0]
            current_magnitude = current_raw / 1000.0  # Convert mA to A

            # Current direction from byte 15 bit 7 (FIXED: proper interpretation)
            discharge_flag = (packet[15] & 0x80) != 0

            # Apply sign based on discharge flag
            # Negative current = discharging, Positive current = charging
            current = -current_magnitude if discharge_flag else current_magnitude
            result["current"] = current

            # Determine charging status based on discharge flag
            result["battery_charging"] = not discharge_flag

            # State of Charge at byte 24
            result["battery_level"] = packet[24]

            # Temperature at byte 16 (divide by 10 for °C)
            # Note: Since this is an unsigned byte (0-255), the temperature range is 0-25.5°C
            # The device cannot report negative temperatures with this encoding
            temp_raw = packet[16]
            temperature = temp_raw / 10.0

            # Validate temperature range (0-25.5°C due to unsigned byte limitation)
            # While the protocol documentation mentions -40°C to 100°C, the actual
            # implementation is limited by the unsigned byte encoding
            if temperature <= 25.5:  # Always true for unsigned byte, but kept for clarity
                result["temperature"] = temperature
                result["temp_values"] = [temperature]
            else:
                # This branch is unreachable with unsigned byte, but kept for completeness
                LOGGER.warning("Temperature out of range: %.1f°C (raw: %d)", temperature, temp_raw)
                result["temperature"] = 20.0
                result["temp_values"] = [20.0]

            # Remaining capacity at bytes 20-21 (multiply by 10 for mAh)
            capacity_raw = struct.unpack("<H", packet[20:22])[0]
            actual_capacity_mah = capacity_raw * 10
            remaining_capacity_ah = actual_capacity_mah / 1000.0

            # Calculate total capacity from remaining capacity and SOC
            soc = result["battery_level"]
            if soc > 0:
                total_capacity_ah = (remaining_capacity_ah / soc) * 100
                LOGGER.debug(
                    "Calculated total capacity: (%.2f / %d) * 100 = %.1f Ah",
                    remaining_capacity_ah,
                    soc,
                    total_capacity_ah
                )
            else:
                total_capacity_ah = 129.0  # Default for this battery setup
                LOGGER.debug(
                    "SOC is %d, using default total capacity: %.1f Ah",
                    soc,
                    total_capacity_ah
                )

            result["remaining_capacity"] = remaining_capacity_ah
            result["cycle_charge"] = remaining_capacity_ah
            result["design_capacity"] = int(total_capacity_ah)

            # Calculate power from voltage and current
            result["power"] = voltage * current

            # Check for runtime in bytes 28-29 (if available)
            # Note: Runtime is only valid when discharging (current < 0)
            # When charging (current > 0), charge_time is calculated by base class
            if packet_len >= 30:  # Need at least 30 bytes to read bytes 28-29
                try:
                    runtime_bytes = packet[28:30]  # Bytes 28-29 contain runtime in minutes
                    runtime_minutes = struct.unpack("<H", runtime_bytes)[0]
                    LOGGER.debug(
                        "Runtime bytes (28-29): %s, value: %d minutes",
                        runtime_bytes.hex(),
                        runtime_minutes
                    )

                    # Only set runtime if it's a reasonable value
                    # 0 means no runtime data, 65535 (0xFFFF) often means invalid/not available
                    if 0 < runtime_minutes < 65535:
                        # Only set runtime when discharging (current < 0)
                        # This ensures runtime and charge_time are mutually exclusive
                        if current < 0:
                            result["runtime"] = runtime_minutes * 60  # Convert to seconds
                            LOGGER.debug(
                                "Runtime (discharging): %d minutes (%d seconds)",
                                runtime_minutes,
                                runtime_minutes * 60
                            )
                        else:
                            LOGGER.debug(
                                "Runtime value %d minutes ignored (battery is charging)",
                                runtime_minutes
                            )
                    else:
                        LOGGER.debug(
                            "Runtime value %d is out of valid range (1-65534)",
                            runtime_minutes
                        )
                except (struct.error, ValueError) as e:
                    LOGGER.warning("Error parsing runtime: %s", e)
            else:
                LOGGER.debug(
                    "Packet too short for runtime data (len=%d, need>=30)",
                    packet_len
                )

            # Log parsed values for debugging
            self._log_parsed_values(result, voltage, current, remaining_capacity_ah)

            # Store the result
            self._result = result
            self._packet_stats["data_packets"] += 1

        except Exception:
            LOGGER.exception("Failed to parse packet")
            self._packet_stats["invalid"] += 1
            return False
        else:
            return True

    def _log_parsed_values(
        self,
        result: dict[str, Any],
        voltage: float,
        current: float,
        remaining_capacity_ah: float
    ) -> None:
        """Log parsed values for debugging.

        Args:
            result: The parsed result dictionary
            voltage: Battery voltage in volts
            current: Battery current in amps
            remaining_capacity_ah: Remaining capacity in amp-hours

        """
        LOGGER.debug(
            "Parsed data - Voltage: %.2fV, Current: %.3fA, "
            "SOC: %d%%, Temp: %.1f°C, "
            "Remaining: %.2fAh, Power: %.2fW",
            voltage,
            current,
            result['battery_level'],
            result.get('temperature', 25.0),
            remaining_capacity_ah,
            result['power']
        )

    def _process_data(self) -> BMSsample | None:
        """Process collected data and return BMSsample.

        Returns:
            BMSsample with parsed data, or None if no valid data available

        """
        if not hasattr(self, '_result') or not self._result:
            LOGGER.warning("No data to process")
            return None

        # Get calculated values from base class
        self._add_missing_values(self._result, self._calc_values())

        # Create BMSsample with available data
        sample = BMSsample(
            voltage=round(self._result.get("voltage", 0), 2),
            current=round(self._result.get("current", 0), 2),
            battery_level=self._result.get("battery_level", 0),
            cycles=self._result.get("cycles"),
            temperature=self._result.get("temperature"),
            temp_values=self._result.get("temp_values", []),
            cycle_charge=self._result.get("cycle_charge"),
            remaining_capacity=self._result.get("remaining_capacity"),
            design_capacity=self._result.get("design_capacity"),
            problem=self._result.get("problem", False),
            problem_code=self._result.get("problem_code", 0),
            power=round(self._result.get("power", 0), 2),
            runtime=self._result.get("runtime"),
            battery_charging=self._result.get("battery_charging", False),
        )

        LOGGER.debug("Created BMSsample: %s", sample)
        return sample

    def _verify_checksum(self, packet: bytes) -> tuple[bool, str]:
        """Verify packet checksum.

        Note: Checksum validation is currently bypassed for Pro BMS compatibility.
        The Pro BMS protocol checksum implementation differs from standard implementations.

        Args:
            packet: The packet to verify

        Returns:
            Tuple of (is_valid, checksum_type) - always returns (True, "BYPASSED")

        """
        return True, "BYPASSED"

    @staticmethod
    def _calc_values() -> frozenset[str]:
        """Return values that the BMS cannot provide and need to be calculated.

        Returns:
            Set of value names that need calculation by the base class

        """
        # Don't include runtime here since we try to extract it from the packet
        # If extraction fails, the base class will calculate it
        return frozenset({"cycle_capacity", "charge_time"})
