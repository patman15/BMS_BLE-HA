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

    # Field definitions based on btsnoop packet analysis
    # Offset is from start of data section (after 4-byte header)
    _FIELDS: Final[list[tuple[BMSvalue, int, int, Callable[[int], Any]]]] = [
        # (name, offset_in_data, size, conversion_func)
        ("voltage", 4, 2, lambda x: x / 100.0),  # voltage in 0.01V
        ("current", 8, 2, lambda x: (x if x < 0x8000 else x - 0x10000) / 100.0),  # current in 0.01A (signed 16-bit)
        ("temperature", 12, 1, lambda x: x / 10.0),  # temperature in 0.1°C (unsigned for this device)
        ("battery_level", 16, 1, lambda x: x),  # remaining percentage
        ("runtime", 28, 2, lambda x: x * 60),  # runtime in minutes, convert to seconds
        ("cycle_charge", 32, 2, lambda x: x / 100.0),  # cumulative charge in 0.01 kWh
        ("design_capacity", 36, 2, lambda x: x / 100.0),  # design capacity in 0.01 Ah
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
        return frozenset(
            {
                "power",
                "battery_charging",
                "cycle_capacity",
            }
        )

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

        # Wait for data packet
        self._data_event.clear()  # clear event to ensure new data is acquired
        await asyncio.wait_for(self._wait_event(), timeout=BaseBMS.TIMEOUT)

        if len(self._data) < 45:
            self._log.debug("Incomplete data packet")
            return {}

        # Skip header (2), length (1), type (1) to get to data section
        data_section = self._data[4:]
        result: BMSsample = {}

        # Parse fields using the same pattern as other plugins
        # We already checked that len(self._data) >= 45, so we have at least 41 bytes in data_section
        for key, offset, size, func in BMS._FIELDS:
            value = int.from_bytes(
                data_section[offset:offset + size],
                byteorder="little",
                signed=False
            )
            result[key] = func(value)

        # Parse protection status at offset 11 from start of packet (offset 7 in data_section)
        protection = data_section[7] & 0x7F
        if protection:
            result["problem_code"] = protection

        return result

    async def disconnect(self, reset: bool = True) -> None:
        """Disconnect from the BMS device."""
        # Reset initialization state when disconnecting
        self._init_complete = False
        self._streaming = False
        self._init_response_received = False
        await super().disconnect(reset)
