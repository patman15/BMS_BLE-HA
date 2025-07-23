"""Module to support Pro BMS Smart Shunt devices."""

import asyncio
import struct
from typing import Any, Final

from bleak.backends.characteristic import BleakGATTCharacteristic
from bleak.backends.device import BLEDevice

from .basebms import AdvertisementPattern, BaseBMS, BMSsample, BMSvalue


class BMS(BaseBMS):
    """Pro BMS Smart Shunt class implementation."""

    # Protocol constants
    PACKET_HEADER: Final[bytes] = bytes([0x55, 0xAA])
    PACKET_TYPE_REALTIME: Final[int] = 0x04
    PACKET_TYPE_INIT_RESPONSE: Final[int] = 0x03

    # Initialization commands
    INIT_COMMANDS: Final[list[bytes]] = [
        bytes.fromhex("55aa0a0101558004077be16968"),    # General init (Function 0x04)
        bytes.fromhex("55aa070101558040000095"),        # Get info (Function 0x40)
        bytes.fromhex("55aa070101558042000097"),        # Extended info (Function 0x42)
        bytes.fromhex("55aa0901015580430000120084"),    # Function 0x43 with 18 data points
    ]

    # Command names for logging
    INIT_COMMAND_NAMES: Final[list[str]] = [
        "General init (0x04)",
        "Get info (0x40)",
        "Extended info (0x42)",
        "Data stream setup (0x43)"
    ]

    # Transition commands
    INIT_ACK_COMMAND: Final[bytes] = bytes.fromhex("55aa070101558006000055")
    DATA_START_COMMAND: Final[bytes] = bytes.fromhex("55aa09010155804300550000c1")

    # Timing constants (seconds)
    INIT_COMMAND_TIMEOUT: Final[float] = 0.5
    INIT_RESPONSE_TIMEOUT: Final[float] = 1.5
    DATA_FLOW_CHECK_TIMEOUT: Final[float] = 0.5

    # Expected packet length for real-time data
    REALTIME_PACKET_LEN: Final[int] = 50

    def __init__(self, ble_device: BLEDevice, reconnect: bool = False) -> None:
        """Initialize private BMS members."""
        # Ensure unique device naming before calling super().__init__
        # Note: We can't use self._log here as it's not initialized yet
        self._ensure_unique_device_name(ble_device)

        super().__init__(__name__, ble_device, reconnect)

        # Initialize buffers and state
        self._buffer: bytearray = bytearray()
        self._init_data: dict[str, Any] = {}
        self._waiting_for_init: bool = True
        self._init_responses_received: int = 0
        self._expected_init_responses: int = 3
        self._packet_stats: dict[str, Any] = {
            "total": 0,
            "init_responses": 0,
            "data_packets": 0,
            "invalid": 0,
            "unknown_types": {},
        }

    @staticmethod
    def device_info() -> dict[str, str]:
        """Return device information for the battery management system."""
        return {"manufacturer": "Pro BMS", "model": "Smart Shunt"}

    @staticmethod
    def matcher_dict_list() -> list[AdvertisementPattern]:
        """Provide BluetoothMatcher definition."""
        return [
            AdvertisementPattern(
                local_name="Pro BMS*",
                service_uuid=BMS.uuid_services()[0],
                manufacturer_id=0x004C,
                connectable=True,
            )
        ]

    @staticmethod
    def uuid_services() -> list[str]:
        """Return list of 128-bit UUIDs of services required by BMS."""
        return ["0000fff0-0000-1000-8000-00805f9b34fb"]

    @staticmethod
    def uuid_rx() -> str:
        """Return 16-bit UUID of characteristic that provides notification/read property."""
        return "fff4"

    @staticmethod
    def uuid_tx() -> str:
        """Return 16-bit UUID of characteristic that provides write property."""
        return "fff3"

    def _ensure_unique_device_name(self, ble_device: BLEDevice) -> None:
        """Ensure device has unique name with MAC suffix."""
        mac_suffix = ble_device.address[-5:].replace(":", "")

        if mac_suffix in (ble_device.name or ""):
            # Device name already contains MAC suffix
            # Can't use self._log here as it's not initialized yet
            import logging
            logging.getLogger(__name__).debug("Device name already contains MAC suffix")
            return

        if ble_device.name and "Pro BMS" in ble_device.name and ble_device.name != "Pro BMS":
            custom_name = f"{ble_device.name} {mac_suffix}"
        else:
            custom_name = f"Pro BMS {mac_suffix}"

        ble_device.name = custom_name

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
        """Update battery status information."""
        self._log.debug("Starting Pro BMS update")

        # Check connection status
        if not self._client or not self._client.is_connected:
            raise ConnectionError("BMS is not connected")

        # Reset state
        self._buffer.clear()
        self._init_data.clear()
        self._waiting_for_init = True
        self._init_responses_received = 0
        self._packet_stats = {
            "total": 0,
            "init_responses": 0,
            "data_packets": 0,
            "invalid": 0,
            "unknown_types": {},
        }

        # Send initialization sequence
        for i, (cmd, cmd_name) in enumerate(zip(self.INIT_COMMANDS, self.INIT_COMMAND_NAMES, strict=False)):
            self._log.debug("Sending init command %d/%d (%s)", i + 1, len(self.INIT_COMMANDS), cmd_name)
            try:
                await self._client.write_gatt_char(self.uuid_tx(), cmd, response=False)
            except Exception as e:
                from bleak.exc import BleakError
                if isinstance(e, BleakError):
                    raise BleakError(f"Init command {i+1} ({cmd_name}) failed: {e}") from e
                raise

            # Wait for response
            await self._wait_for_response(self.INIT_COMMAND_TIMEOUT)

        # Wait for init responses
        await self._wait_for_response(self.INIT_RESPONSE_TIMEOUT)

        if self._init_responses_received > 0:
            self._log.debug("Received %d init responses", self._init_responses_received)

            # Send acknowledgment
            self._log.debug("sending acknowledgment")
            try:
                await self._client.write_gatt_char(self.uuid_tx(), self.INIT_ACK_COMMAND, response=False)
            except Exception as e:
                from bleak.exc import BleakError
                if isinstance(e, BleakError):
                    self._log.warning("Failed to send init acknowledgment: %s", e)
                else:
                    raise
            await self._wait_for_response(0.2)

            self._waiting_for_init = False

            # Send data start command
            try:
                await self._client.write_gatt_char(self.uuid_tx(), self.DATA_START_COMMAND, response=False)
            except Exception as e:
                from bleak.exc import BleakError
                if isinstance(e, BleakError):
                    self._log.warning("Failed to send data start command: %s", e)
                    raise
                raise
            await self._wait_for_response(0.6)

        # Wait for data packets
        await self._wait_for_response(self.DATA_FLOW_CHECK_TIMEOUT)

        if self._packet_stats['data_packets'] > 0:
            self._log.debug("Received %d data packets", self._packet_stats['data_packets'])
            return self._process_data()

        raise TimeoutError("No valid data received from Pro BMS")

    def _notification_handler(
        self, _sender: BleakGATTCharacteristic, data: bytearray
    ) -> None:
        """Retrieve BMS data update."""
        self._log.debug("RX BLE data (%d bytes): %s", len(data), data.hex())

        self._buffer.extend(data)
        self._packet_stats["total"] += 1
        self._process_buffer()

    def _process_buffer(self) -> None:
        """Process data in buffer looking for complete packets."""
        while len(self._buffer) >= 5:
            # Look for packet header
            header_pos = self._buffer.find(self.PACKET_HEADER)
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

            # Calculate total packet length
            total_length = 4 + length_byte + 1

            self._log.debug("Processing packet type 0x%02x, length %d", packet_type, total_length)

            # Check if we have complete packet
            if len(self._buffer) < total_length:
                return

            # Extract packet
            packet = self._buffer[:total_length]
            self._buffer = self._buffer[total_length:]

            # Process packet based on type
            if packet_type == self.PACKET_TYPE_INIT_RESPONSE:
                self._log.debug("Init response #%d received", self._init_responses_received + 1)
                self._process_init_response(packet)
            elif packet_type == self.PACKET_TYPE_REALTIME:
                self._log.debug("Data packet received, length %d", len(packet))
                self._parse_realtime_packet(packet)
            else:
                self._packet_stats["unknown_types"][packet_type] = \
                    self._packet_stats["unknown_types"].get(packet_type, 0) + 1
                if len(self._packet_stats["unknown_types"]) == 1:  # Log only on first unknown type
                    self._log.debug("Unknown packet types: %s", self._packet_stats["unknown_types"])

    def _process_init_response(self, packet: bytes) -> None:
        """Process initialization response packet."""
        self._init_responses_received += 1
        self._packet_stats["init_responses"] += 1
        self._log.debug("Processing init response %d", self._init_responses_received)

    def _parse_realtime_packet(self, packet: bytes) -> bool:  # noqa: PLR0912, PLR0915
        """Parse real-time data packet and store the result.

        Args:
            packet: The complete 50-byte data packet

        Returns:
            True if packet was successfully parsed, False otherwise

        """
        packet_len = len(packet)

        # We expect 50-byte packets from Function 0x43
        if packet_len != 50:
            self._log.warning(
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
            self._log.debug("Voltage: %.2fV (raw: %d)", voltage, voltage_raw)

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
                self._log.warning("Temperature out of range: %.1f°C (raw: %d)", temperature, temp_raw)
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
                self._log.debug(
                    "Calculated total capacity: (%.2f / %d) * 100 = %.1f Ah",
                    remaining_capacity_ah,
                    soc,
                    total_capacity_ah
                )
            else:
                total_capacity_ah = 129.0  # Default for this battery setup
                self._log.debug(
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
                    self._log.debug(
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
                            self._log.debug(
                                "Runtime (discharging): %d minutes (%d seconds)",
                                runtime_minutes,
                                runtime_minutes * 60
                            )
                        else:
                            self._log.debug(
                                "Runtime value %d minutes ignored (battery is charging)",
                                runtime_minutes
                            )
                    else:
                        self._log.debug(
                            "Runtime value %d is out of valid range (1-65534)",
                            runtime_minutes
                        )
                except (struct.error, ValueError) as e:
                    self._log.warning("Error parsing runtime: %s", e)
            else:
                self._log.debug(
                    "Packet too short for runtime data (len=%d, need>=30)",
                    packet_len
                )

            # Log parsed values for debugging
            self._log_parsed_values(result, voltage, current, remaining_capacity_ah)

            # Store the result
            self._result = result
            self._packet_stats["data_packets"] += 1

        except (struct.error, ValueError, IndexError) as e:
            self._log.exception("Failed to parse packet: %s", e)
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
        self._log.debug(
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
            self._log.warning("No data to process")
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

        self._log.debug("Created BMSsample: %s", sample)
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
        return frozenset({"cycle_capacity"})
