"""Module to support Pro BMS Smart Shunt devices."""

import asyncio
from collections.abc import Callable
import contextlib
import logging
from typing import Any, Final

from bleak.backends.characteristic import BleakGATTCharacteristic
from bleak.backends.device import BLEDevice

from .basebms import AdvertisementPattern, BaseBMS, BMSsample, BMSvalue

# Debug logger
_LOGGER = logging.getLogger(__name__)


class BMS(BaseBMS):
    """Pro BMS Smart Shunt class implementation."""

    # Protocol constants
    _HEAD: Final[bytes] = bytes([0x55, 0xAA])
    _TYPE_INIT_RESPONSE: Final[int] = 0x03
    _TYPE_REALTIME_DATA: Final[int] = 0x04

    # Commands (original hardcoded values that work with the device)
    _CMD_EXTENDED_INFO: Final[bytes] = bytes.fromhex("55aa070101558042000097")
    _CMD_ACK: Final[bytes] = bytes.fromhex("55aa070101558006000055")
    _CMD_DATA_STREAM: Final[bytes] = bytes.fromhex("55aa0901015580430000120084")

    # Timing constants (seconds)
    _INIT_TIMEOUT: Final[float] = 0.5  # Short timeout for init
    _DATA_TIMEOUT: Final[float] = 2.0  # Longer timeout for data

    # Expected packet length
    _REALTIME_PACKET_LEN: Final[int] = 50

    # Data field definitions with offsets relative to data section (not full packet)
    _FIELDS: Final[list[tuple[BMSvalue, int, int, bool, Callable[[int], Any]]]] = [
        # (name, offset_in_data, size, signed, conversion_func)
        ("voltage", 4, 2, False, lambda x: x * 0.01),
        ("current", 8, 2, False, lambda x: x / 1000.0),  # Magnitude only
        ("battery_level", 20, 1, False, lambda x: x),
        ("temperature", 12, 1, False, lambda x: x / 10.0),
        ("remaining_capacity", 16, 2, False, lambda x: x * 10 / 1000.0),  # mAh to Ah
        ("runtime", 24, 2, False, lambda x: x * 60 if 0 < x < 65535 else None),  # minutes to seconds
        # Design capacity at offset 36-37 in data section
        ("design_capacity_raw", 36, 2, False, lambda x: x / 100.0),
    ]

    # Protection/error status bit definitions (if available in byte 15 of data section)
    _PROTECTION_BITS: Final[dict[int, str]] = {
        0x01: "overvoltage",
        0x02: "undervoltage",
        0x04: "overcurrent",
        0x08: "overtemperature",
        0x10: "undertemperature",
        0x20: "short_circuit",
        0x40: "cell_imbalance",
        # 0x80 is used for discharge flag
    }

    def __init__(self, ble_device: BLEDevice, reconnect: bool = False) -> None:
        """Initialize private BMS members."""
        # Debug logging for device name issues
        _LOGGER.debug(
            "Pro BMS init - device name: %s, address: %s",
            ble_device.name,
            ble_device.address
        )
        
        # If device name is None or just MAC address, set it to "Pro BMS"
        if not ble_device.name or ble_device.name == ble_device.address:
            _LOGGER.warning(
                "Pro BMS device %s has no name or MAC as name, setting to 'Pro BMS'",
                ble_device.address
            )
            # Create a new BLEDevice with the proper name
            from bleak.backends.device import BLEDevice as BLEDeviceClass
            ble_device = BLEDeviceClass(
                address=ble_device.address,
                name="Pro BMS",
                details=ble_device.details,
                rssi=ble_device.rssi,
            )
            _LOGGER.debug("Created new BLEDevice with name: %s", ble_device.name)

        super().__init__(__name__, ble_device, reconnect)

        # Initialize buffers and state
        self._buffer: bytearray = bytearray()
        self._result: dict[str, Any] = {}
        self._data_received: bool = False
        self._ack_sent: bool = False  # Prevent multiple ACK/Data Stream sequences
        self._ack_task: asyncio.Task | None = None  # Track the ACK task
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
            # Exact match for "Pro BMS" with service UUID only
            AdvertisementPattern(
                local_name="Pro BMS",
                service_uuid=BMS.uuid_services()[0],
                connectable=True,
            ),
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

    @staticmethod
    def _calc_values() -> frozenset[BMSvalue]:
        """Return values that the BMS cannot provide and need to be calculated."""
        return frozenset({"cycle_capacity"})

    async def _wait_for_data(self, timeout: float, wait_for_any_packet: bool = False) -> bool:
        """Wait for data packets with timeout.

        Args:
            timeout: Maximum time to wait
            wait_for_any_packet: If True, return when any packet is received (not just data)
        """
        loop = asyncio.get_event_loop()
        start_time = loop.time()
        last_packet_count = self._packet_stats["total"]

        while loop.time() - start_time < timeout:
            # Check if we received data packets
            if self._data_received:
                return True

            # If waiting for any packet, check if we received anything
            if wait_for_any_packet and self._packet_stats["total"] > last_packet_count:
                return True

            await asyncio.sleep(0.05)

        return False

    async def _send_ack_and_data_stream(self) -> None:
        """Send ACK and Data Stream commands after init response."""
        # Check if already sent
        if self._ack_sent:
            return

        # Send ACK command
        try:
            self._log.debug("Sending ACK command")
            await self._client.write_gatt_char(self.uuid_tx(), self._CMD_ACK, response=False)
        except OSError as e:
            self._log.error("Failed to send ACK command: %s", e)
            return

        # Small delay between commands
        await asyncio.sleep(0.1)

        # Send Data Stream request
        try:
            self._log.debug("Sending Data Stream request")
            await self._client.write_gatt_char(self.uuid_tx(), self._CMD_DATA_STREAM, response=False)
            # Mark as sent only after successful completion
            self._ack_sent = True
        except OSError as e:
            self._log.error("Failed to send Data Stream command: %s", e)

    def _notification_handler(self, _sender: BleakGATTCharacteristic, data: bytearray) -> None:
        """Handle BMS data notifications."""
        self._log.debug("RX BLE data (%d bytes): %s", len(data), data.hex())

        # Log buffer state before adding new data
        if self._buffer:
            self._log.debug("Buffer before: %d bytes, first 10: %s",
                          len(self._buffer),
                          self._buffer[:min(10, len(self._buffer))].hex())

        self._buffer.extend(data)
        self._packet_stats["total"] += 1
        self._process_buffer()

    def _process_buffer(self) -> None:
        """Process data in buffer looking for complete packets."""
        while len(self._buffer) >= 5:
            # Look for packet header
            header_pos = self._buffer.find(self._HEAD)
            if header_pos == -1:
                # No header found - clear buffer if it's just garbage
                if len(self._buffer) > 10:
                    self._buffer = self._buffer[-10:]
                else:
                    # Small buffer with no header - clear it
                    self._buffer.clear()
                return

            # Remove data before header
            if header_pos > 0:
                self._log.debug("Removing %d bytes before header", header_pos)
                self._buffer = self._buffer[header_pos:]

            # Check if we have enough data for length and type fields
            if len(self._buffer) < 4:
                return

            # Get packet length and type - ensure we're reading from the correct position
            length_byte = self._buffer[2]
            packet_type = self._buffer[3]

            # Calculate total packet length
            total_length = 4 + length_byte + 1

            # Validate packet type before processing
            if packet_type not in [self._TYPE_INIT_RESPONSE, self._TYPE_REALTIME_DATA]:
                self._log.warning(
                    "Invalid packet type 0x%02x at position 3, buffer: %s",
                    packet_type,
                    self._buffer[:min(20, len(self._buffer))].hex()
                )
                # Track unknown packet types
                self._packet_stats["unknown_types"][packet_type] = self._packet_stats["unknown_types"].get(packet_type, 0) + 1
                # Skip this byte and try again
                self._buffer = self._buffer[1:]
                continue

            self._log.debug("Processing packet type 0x%02x, length %d", packet_type, total_length)

            # Check if we have complete packet
            if len(self._buffer) < total_length:
                return

            # Extract packet
            packet = self._buffer[:total_length]
            self._buffer = self._buffer[total_length:]

            # Skip checksum validation for Pro BMS compatibility
            self._log.debug("Skipping checksum validation for Pro BMS compatibility")

            # Process packet based on type using handler mapping
            handler = self._get_packet_handler(packet_type)
            handler(packet, packet_type)

    def _get_packet_handler(self, packet_type: int):
        """Get the appropriate handler for a packet type."""
        handlers = {
            self._TYPE_INIT_RESPONSE: self._handle_init_response,
            self._TYPE_REALTIME_DATA: self._handle_realtime_data,
        }
        return handlers.get(packet_type, lambda p, t: self._packet_stats["unknown_types"].__setitem__(t, self._packet_stats["unknown_types"].get(t, 0) + 1))

    def _handle_init_response(self, packet: bytearray, packet_type: int) -> None:
        """Handle init response packet."""
        self._log.debug("Received init response")
        self._packet_stats["init_responses"] += 1
        # Send ACK and Data Stream commands after init response (only once)
        if not self._ack_sent and not self._ack_task:
            self._ack_task = asyncio.create_task(self._send_ack_and_data_stream())

    def _handle_realtime_data(self, packet: bytearray, packet_type: int) -> None:
        """Handle realtime data packet."""
        self._log.debug("Received realtime data packet, length: %d", len(packet))
        if self._parse_realtime_packet(packet):
            self._data_received = True


    def _parse_current_sign(self, current_bytes: bytearray) -> float:
        """Parse current value with sign bit handling."""
        # Extract the raw value (lower 15 bits)
        raw_value = int.from_bytes(current_bytes, byteorder="little") & 0x7FFF

        # Check sign bit (bit 15)
        if current_bytes[1] & 0x80:
            # Negative current (discharging)
            return -raw_value / 100.0
        # Positive current (charging)
        return raw_value / 100.0

    def _parse_realtime_packet(self, packet: bytes) -> bool:
        """Parse real-time data packet and store the result."""
        packet_len = len(packet)

        # We expect 50-byte packets from Function 0x43
        if packet_len != self._REALTIME_PACKET_LEN:
            self._log.warning(
                "Unexpected packet length: %d bytes (expected %d)",
                packet_len,
                self._REALTIME_PACKET_LEN
            )
            return False

        # Extract data section (skip header, length, type, and checksum)
        data_section = packet[4:-1]

        # Parse fields according to _FIELDS
        result: BMSsample = {}
        for key, offset, size, signed, func in self._FIELDS:
            if offset + size <= len(data_section):
                value = int.from_bytes(
                    data_section[offset:offset + size],
                    byteorder="little",
                    signed=signed
                )
                converted = func(value)
                if converted is not None:
                    result[key] = converted

        # Handle current sign based on discharge flag (bit 7 of byte 15 in data section)
        if "current" in result and len(data_section) > 11:
            byte15 = data_section[11]  # Byte 15 in full packet = offset 11 in data section
            discharge_flag = (byte15 & 0x80) != 0
            # Negative current = discharging, Positive current = charging
            if discharge_flag:
                result["current"] = -result["current"]
            result["battery_charging"] = not discharge_flag

            # Check for protection/error status in lower bits of byte 15
            protection_byte = byte15 & 0x7F  # Mask out discharge flag
            if protection_byte:
                result["problem_code"] = protection_byte
                result["problem"] = True
                # Log protection status
                problems = []
                for bit, problem in self._PROTECTION_BITS.items():
                    if protection_byte & bit:
                        problems.append(problem)
                # Always log if we have a protection byte
                self._log.debug("Protection status detected: %s", ", ".join(problems) if problems else "Unknown protection code")
            else:
                result["problem"] = False

        # Use design capacity from packet if available
        if "design_capacity_raw" in result:
            result["design_capacity"] = int(result["design_capacity_raw"])
            del result["design_capacity_raw"]  # Remove raw field
        # Fallback to calculation if design capacity not in packet
        elif "remaining_capacity" in result and "battery_level" in result:
            soc = result["battery_level"]
            if soc > 0:
                total_capacity_ah = (result["remaining_capacity"] / soc) * 100
                result["design_capacity"] = int(total_capacity_ah)
                self._log.debug(
                    "Calculated total capacity: (%.2f / %d) * 100 = %d Ah",
                    result["remaining_capacity"],
                    soc,
                    int(total_capacity_ah)
                )
            else:
                self._log.debug("Cannot calculate design capacity with SOC=%d", soc)

        # Set cycle charge
        if "remaining_capacity" in result:
            result["cycle_charge"] = result["remaining_capacity"]

        # Calculate power
        if "voltage" in result and "current" in result:
            result["power"] = round(result["voltage"] * result["current"], 2)

        # Calculate temperature values array
        if "temperature" in result:
            result["temp_values"] = [result["temperature"]]
            # Validate temperature range (0-25.5°C due to unsigned byte limitation)
            if result["temperature"] > 25.5:
                self._log.warning("Temperature out of range: %.1f°C", result["temperature"])
                result["temperature"] = 20.0
                result["temp_values"] = [20.0]

        # Only include runtime when discharging
        if "runtime" in result and result.get("current", 0) >= 0:
            del result["runtime"]  # Remove runtime when charging

        # Log parsed values for debugging
        self._log.debug(
            "Parsed data - Voltage: %.2fV, Current: %.3fA, "
            "SOC: %d%%, Temp: %.1f°C, "
            "Remaining: %.2fAh, Power: %.2fW",
            result.get("voltage", 0),
            result.get("current", 0),
            result.get("battery_level", 0),
            result.get("temperature", 0),
            result.get("remaining_capacity", 0),
            result.get("power", 0)
        )

        # Store the result
        self._result = result
        self._packet_stats["data_packets"] += 1

        return True

    async def _async_update(self) -> BMSsample:
        """Update battery status information."""
        self._log.debug("Starting Pro BMS update")

        # Reset state
        self._buffer.clear()
        self._result.clear()
        self._data_received = False
        self._ack_sent = False  # Reset ACK flag for new update cycle
        # Cancel any pending ACK task
        if self._ack_task and not self._ack_task.done():
            self._ack_task.cancel()
        self._ack_task = None
        self._packet_stats = {
            "total": 0,
            "init_responses": 0,
            "data_packets": 0,
            "invalid": 0,
            "unknown_types": {},
        }

        # First, wait a bit to see if device is already streaming
        self._log.debug("Checking if device is already streaming data...")
        if await self._wait_for_data(self._INIT_TIMEOUT):
            self._log.debug("Device is already streaming data!")
            return self._process_data()

        # If not streaming, send init command
        self._log.debug("Device not streaming, sending Extended info command for initialization")
        try:
            await self._client.write_gatt_char(self.uuid_tx(), self._CMD_EXTENDED_INFO, response=False)
            self._log.debug("Extended info command sent successfully")
        except Exception as e:
            self._log.error("Failed to send Extended info command: %s", e)
            raise

        # Wait for any response (init responses or data)
        if not await self._wait_for_data(self._DATA_TIMEOUT, wait_for_any_packet=True):
            self._log.warning(
                "No packets received after %s seconds. Stats: %s",
                self._DATA_TIMEOUT,
                self._packet_stats
            )
            raise TimeoutError("No response from Pro BMS")

        # Now wait for actual data packets (device may send multiple init responses first)
        # Use a longer timeout since we know the device is responding
        extended_timeout = self._DATA_TIMEOUT * 2
        self._log.debug(
            "Waiting for data packets (received %d init responses so far)",
            self._packet_stats["init_responses"]
        )

        if await self._wait_for_data(extended_timeout):
            self._log.debug("Received data after init command. Stats: %s", self._packet_stats)
            return self._process_data()

        # Log appropriate warning based on what we received
        warning_msg = (
            f"Received {self._packet_stats['init_responses']} init responses but no data packets after {extended_timeout} seconds. Stats: {self._packet_stats}"
            if self._packet_stats["init_responses"] > 0
            else f"No valid packets received after {extended_timeout} seconds. Stats: {self._packet_stats}"
        )
        self._log.warning(warning_msg)
        raise TimeoutError("No valid data received from Pro BMS")

    def _process_data(self) -> BMSsample | None:
        """Process collected data and return BMSsample."""
        if not self._result:
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
            power=round(self._result.get("power", 0), 2),
            runtime=self._result.get("runtime"),
            battery_charging=self._result.get("battery_charging", False),
        )

        self._log.debug("Returning sample: %s", sample)
        return sample

    async def disconnect(self) -> None:
        """Disconnect from the BMS."""
        self._log.debug("disconnecting BMS (%s)", self._reconnect)
        self._log.debug("Packet stats: %s", self._packet_stats)

        # Cancel any pending ACK task
        if self._ack_task and not self._ack_task.done():
            self._ack_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._ack_task
            self._ack_task = None

        # Clear buffer and reset state for clean reconnection
        self._buffer.clear()
        self._ack_sent = False
        self._data_received = False

        await super().disconnect()
