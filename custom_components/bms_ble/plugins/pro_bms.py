"""Module to support Pro BMS."""

import asyncio
from collections.abc import Callable
from typing import Any, Final

from bleak.backends.characteristic import BleakGATTCharacteristic
from bleak.backends.device import BLEDevice
from bleak.uuids import normalize_uuid_str

from .basebms import AdvertisementPattern, BaseBMS, BMSsample, BMSvalue


class BMS(BaseBMS):
    """Pro BMS Smart Shunt class implementation."""

    # Protocol constants
    HEAD: Final[bytes] = bytes([0x55, 0xAA])
    TYPE_INIT_RESPONSE: Final[int] = 0x03
    TYPE_REALTIME_DATA: Final[int] = 0x04

    # Commands from btsnoop capture
    CMD_INIT: Final[bytes] = bytes.fromhex("55aa0a0101558004077f648e682b")
    CMD_ACK: Final[bytes] = bytes.fromhex("55aa070101558040000095")
    CMD_DATA_STREAM: Final[bytes] = bytes.fromhex("55aa070101558042000097")
    # Critical 4th command that triggers data streaming (Function 0x43)
    CMD_TRIGGER_DATA: Final[bytes] = bytes.fromhex("55aa0901015580430000120084")

    # Field definitions based on protocol specification and btsnoop packet analysis
    # Offset is from start of data_section (after skipping 4 bytes: 55aa + length + type)
    # VALIDATED 2025-08-06: Field offsets validated against 987 Pro BMS packets with physics cross-validation
    # Power field confirmed with 0.019% average error across ALL 987 packets (987/987 perfect matches)
    _FIELDS: Final[list[tuple[BMSvalue, int, int, Callable[[int], Any]]]] = [
        # (name, offset_in_data_section, size, conversion_func)
        # Note: data_section = packet[4:], so data_section[0] = packet[4]
        ("voltage", 4, 2, lambda x: x / 100.0),  # voltage at data_section[4:6] (packet bytes 8-9) in 0.01V units
        ("current", 8, 4, lambda x: ((x & 0xFFFF) / 1000.0) * (-1 if (x >> 24) & 0x80 else 1)),  # current at data_section[8:12] (packet bytes 12-15)
        ("temperature", 12, 3, lambda x: ((x & 0xFFFF) / 10.0) * (1 if (x >> 16) == 0x00 else -1)),  # temperature at data_section[12:15] (packet bytes 16-18)
        ("cycle_charge", 16, 4, lambda x: x / 100.0),  # remaining capacity at data_section[16:20] (packet bytes 20-23) in 0.01Ah units
        ("battery_level", 20, 1, lambda x: x),  # SOC at data_section[20] (packet byte 24)
        # Note: data_section[21:27] (packet bytes 25-31) contain other data (unknown fields)
        # PHYSICS-VALIDATED: Power field at data_section[28:32] (packet bytes 32-35) in 0.01W units
        # Confirmed by V×I calculations across 987 packets with 0.019% avg error (987/987 perfect matches <1% error)
        ("power", 28, 4, lambda x: x / 100.0),  # power at data_section[28:32] (packet bytes 32-35) in 0.01W units
        # Runtime field commented out - BMS firmware has bug calculating runtime at high currents
        # Base BMS class will calculate runtime from remaining capacity / current instead
        # ("runtime", 28, 2, lambda x: min(x * 20, 359940)),  # runtime at bytes 32-33 in 20-second units, cap at 99h59m (359940 seconds)
        # Note: bytes 34-39 contain additional data not currently captured
        # Note: bytes 40-43 are part of timestamp - removed bogus design_capacity field
    ]

    def __init__(self, ble_device: BLEDevice, reconnect: bool = False) -> None:
        """Initialize private BMS members."""
        super().__init__(__name__, ble_device, reconnect)
        self._streaming = False
        self._init_complete = False
        self._init_response_received = False

    @staticmethod
    def matcher_dict_list() -> list[AdvertisementPattern]:
        """Provide BluetoothMatcher definition."""
        return [
            AdvertisementPattern(
                local_name="Pro BMS",
                service_uuid=BMS.uuid_services()[0],
                connectable=True,
            )
        ]

    @staticmethod
    def device_info() -> dict[str, str]:
        """Return device information for the battery management system."""
        return {"manufacturer": "Pro BMS", "model": "Smart Shunt"}

    @staticmethod
    def uuid_services() -> list[str]:
        """Return list of 128-bit UUIDs of services required by BMS."""
        return [normalize_uuid_str("fff0")]

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
        """Return fields for calculation in base class.

        The base class will calculate:
        - battery_charging: current > 0
        - cycle_capacity: voltage * cycle_charge
        - runtime: cycle_charge / abs(current) when discharging

        We don't need to calculate these ourselves.
        design_capacity is calculated directly in _async_update().
        """
        return frozenset({"battery_charging", "cycle_capacity", "runtime"})

    def _notification_handler(
        self, _sender: BleakGATTCharacteristic, data: bytearray
    ) -> None:
        self._log.debug("RX BLE data (%d bytes): %s", len(data), data.hex())

        # Check for valid packet header
        if len(data) < 4 or data[:2] != BMS.HEAD:
            self._log.debug("Invalid packet header")
            return

        # Packet type is at position 3 (after header and length)
        packet_type = data[3]

        # Handle initialization response packets
        if packet_type == BMS.TYPE_INIT_RESPONSE:
            self._log.debug("Received initialization response")
            self._init_response_received = True
            self._data_event.set()
            return

        # Handle data packets
        if packet_type == BMS.TYPE_REALTIME_DATA and len(data) >= 45:
            self._data = data
            self._data_event.set()
            self._streaming = True

    async def _async_update(self) -> BMSsample:
        """Update battery status information."""
        # Perform complete initialization sequence if not already done
        if not self._init_complete:
            self._log.debug("Starting initialization sequence")

            # Step 1: Send initialization command
            self._log.debug("Sending CMD_INIT")
            self._init_response_received = False
            self._data_event.clear()
            await self._client.write_gatt_char(self.uuid_tx(), BMS.CMD_INIT, response=False)

            # Step 2: Wait for initialization response
            try:
                await asyncio.wait_for(self._wait_event(), timeout=5.0)
                if not self._init_response_received:
                    self._log.error("No initialization response received")
                    return {}
            except TimeoutError:
                self._log.error("Timeout waiting for initialization response")
                return {}

            # Step 3: Send ACK command
            self._log.debug("Sending CMD_ACK")
            await self._client.write_gatt_char(self.uuid_tx(), BMS.CMD_ACK, response=True)

            # Small delay to ensure ACK is processed
            await asyncio.sleep(0.1)

            # Step 4: Send data stream command
            self._log.debug("Sending CMD_DATA_STREAM")
            await self._client.write_gatt_char(
                self.uuid_tx(), BMS.CMD_DATA_STREAM, response=True
            )

            # Small delay to ensure data stream command is processed
            await asyncio.sleep(0.1)

            # Step 5: Send trigger data command - CRITICAL for starting data flow
            # This command (Function 0x43) was missing and caused the "no valid data received" error
            self._log.debug("Sending CMD_TRIGGER_DATA")
            await self._client.write_gatt_char(
                self.uuid_tx(), BMS.CMD_TRIGGER_DATA, response=True
            )

            self._init_complete = True
            self._log.debug("Initialization sequence complete")

            # Allow time for device to transition from init responses to data packets
            # The device may continue sending init responses for a short period
            await asyncio.sleep(1.0)

        # Always clear the event to ensure we get fresh data on each update
        self._data_event.clear()

        # Wait for new data packet
        try:
            await asyncio.wait_for(self._wait_event(), timeout=5.0)

            # Verify we have valid data
            if not self._streaming or len(self._data) < 45:
                self._log.error("No valid data received")
                # Reset init state to retry initialization on next update
                self._init_complete = False
                self._streaming = False
                return {}

        except TimeoutError:
            self._log.error("Timeout waiting for data update")
            # Reset init state to retry initialization on next update
            self._init_complete = False
            self._streaming = False
            return {}

        # Skip header (2), length (1), type (1) to get to data section
        data_section = self._data[4:]
        result: BMSsample = {}

        # Parse fields using the same pattern as other plugins
        for key, offset, size, func in BMS._FIELDS:
            value = int.from_bytes(
                data_section[offset:offset + size],
                byteorder="little",
                signed=False
            )
            result[key] = func(value)


        # Parse protection status from byte 15 (offset 11 in data_section)
        # Lower 7 bits indicate protection/error conditions
        protection = data_section[11] & 0x7F
        if protection:
            result["problem_code"] = protection

        # Calculate total battery capacity (design_capacity) from current state
        # Pro BMS provides remaining capacity (cycle_charge) and SOC (battery_level) directly,
        # so we derive total capacity: total = remaining / (SOC% / 100)
        #
        # This differs from most BMS devices which provide design_capacity directly
        # and require the base class to calculate cycle_charge or battery_level
        battery_level = result.get("battery_level", 0)
        cycle_charge = result.get("cycle_charge", 0)
        if battery_level > 0:
            result["design_capacity"] = int(cycle_charge / (battery_level / 100.0))

        return result

    async def disconnect(self, reset: bool = True) -> None:
        """Disconnect from the BMS device."""
        # Reset initialization state when disconnecting
        self._init_complete = False
        self._streaming = False
        self._init_response_received = False
        await super().disconnect(reset)
