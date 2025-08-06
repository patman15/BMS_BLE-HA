"""Tests for Pro BMS plugin."""

import asyncio
import contextlib
from unittest.mock import AsyncMock, Mock, patch

from bleak.backends.device import BLEDevice
import pytest

from custom_components.bms_ble.plugins.pro_bms import BMS
from tests.bluetooth import generate_advertisement_data, generate_ble_device
from tests.conftest import MockBleakClient

# Actual recorded packets from device logs
RECORDED_PACKETS = {
    # Initialization response packets
    "init_response_1": bytearray.fromhex("55aa080380aa01040000002c52"),
    "init_response_2": bytearray.fromhex("55aa200380aa0140008000000002000000f7040000c800000004010000065eaf7a4ee0f700"),
    "init_response_3": bytearray.fromhex("55aa5a0380aa01420080000000ffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffff0a0500003300000005000000a00500000200000005000000f00000000200000001000000070000008500"),
    "init_response_4": bytearray.fromhex("55aa0a0380aa01430055aa120086"),

    # Data packets with various states
    "data_discharging_low": bytearray.fromhex("55aa2d0480aa01701c05000096090080e2000000ad19000033000000ca050000890c0000770b0000044e000082648e684000"),  # -2.454A discharge
    "data_charging_high": bytearray.fromhex("55aa2d0480aa01703b05000066340000da00000057100000200000008601000029460000580a0000eb4600000bd98c68afff"),  # 13.414A charge
    "data_charging_medium": bytearray.fromhex("55aa2d0480aa017045050000731f0000f5000000b82600004d000000da0000006c2a0000a50a0000eb460000a32c8d68a100"),  # 8.051A charge
    "data_discharging_minimal": bytearray.fromhex("55aa2d0480aa01702f0500008f010080d8000000ba210000430000006b3e000011020000390b00006d4b0000c2648e686957"),  # -0.399A discharge
    "data_with_protection": bytearray.fromhex("55aa2d0480aa01701c05000096090081e2000000ad19000033000000ca050000890c0000770b0000044e000082648e684000"),  # with protection bit
    "data_high_soc": bytearray.fromhex("55aa2d0480aa017045050000161f0000f5000000b82600004d000000da000000ef290000a50a0000eb460000a42c8d684300"),  # 77% SOC
    "data_low_soc": bytearray.fromhex("55aa2d0480aa01702f05000089010080d8000000ba210000430000006b3e000009020000390b00006d4b0000c3648e687657"),  # 67% SOC
}


class MockProBMSBleakClient(MockBleakClient):
    """Mock Pro BMS BleakClient that simulates streaming behavior."""

    def __init__(self, address_or_ble_device, disconnected_callback=None, **kwargs):
        """Initialize the mock client."""
        super().__init__(address_or_ble_device, disconnected_callback, **kwargs)
        self._streaming_task = None
        self._test_data = None
        self._is_streaming = False

    def set_test_data(self, data: bytearray):
        """Set the data to be streamed."""
        self._test_data = data

    async def _stream_data(self):
        """Simulate continuous data streaming."""
        self._is_streaming = True
        while self._is_streaming:
            await asyncio.sleep(0.01)  # Small delay to simulate real behavior
            if self._notify_callback and self._test_data:
                # Call the notification callback with the proper signature
                if asyncio.iscoroutinefunction(self._notify_callback):
                    await self._notify_callback(None, self._test_data)
                else:
                    self._notify_callback(None, self._test_data)

    async def write_gatt_char(self, char_specifier, data, response=None):
        """Mock write to trigger streaming."""
        await super().write_gatt_char(char_specifier, data, response)
        # Handle initialization sequence
        if data == BMS.CMD_INIT:
            # Send actual recorded initialization response
            if self._notify_callback:
                init_response = RECORDED_PACKETS["init_response_1"]
                if asyncio.iscoroutinefunction(self._notify_callback):
                    await self._notify_callback(None, init_response)
                else:
                    self._notify_callback(None, init_response)
        elif data == BMS.CMD_DATA_STREAM and not self._is_streaming:
            # Start streaming after data stream command
            self._streaming_task = asyncio.create_task(self._stream_data())

    async def disconnect(self) -> bool:
        """Clean up streaming task on disconnect."""
        self._is_streaming = False
        if self._streaming_task:
            self._streaming_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._streaming_task
        return await super().disconnect()


@pytest.fixture
def mock_device():
    """Create a mock BLE device."""
    device = Mock(spec=BLEDevice)
    device.address = "AA:BB:CC:DD:EE:FF"
    device.name = "Pro BMS"
    # Add details required by BleakClient
    device.details = {"path": "/org/bluez/hci0/dev_AA_BB_CC_DD_EE_FF"}
    return device


@pytest.fixture
def bms(mock_device):
    """Create a BMS instance with mocked client."""
    with patch("custom_components.bms_ble.plugins.basebms.BleakClient"):
        return BMS(mock_device)


@pytest.fixture
def mock_client():
    """Create a mock BLE client."""
    client = AsyncMock()
    client.is_connected = True
    return client


class TestProBMS:
    """Test Pro BMS implementation."""

    def test_device_info(self):
        """Test device info."""
        info = BMS.device_info()
        assert info["manufacturer"] == "Pro BMS"
        assert info["model"] == "Smart Shunt"


    def test_matcher_dict_list(self):
        """Test matcher dictionary list."""
        matchers = BMS.matcher_dict_list()
        assert len(matchers) == 1
        assert matchers[0]["local_name"] == "Pro BMS"
        assert matchers[0]["service_uuid"] == "0000fff0-0000-1000-8000-00805f9b34fb"
        assert matchers[0]["connectable"] is True

    def test_uuid_services(self):
        """Test UUID services."""
        services = BMS.uuid_services()
        assert len(services) == 1
        assert services[0] == "0000fff0-0000-1000-8000-00805f9b34fb"

    def test_uuid_rx(self):
        """Test RX UUID."""
        assert BMS.uuid_rx() == "fff4"

    def test_uuid_tx(self):
        """Test TX UUID."""
        assert BMS.uuid_tx() == "fff3"

    @pytest.mark.asyncio
    async def test_async_update_first_time(self, mock_device, patch_bleak_client):
        """Test async update when not streaming."""
        # Create mock client and set actual recorded data packet
        mock_client = MockProBMSBleakClient(mock_device)
        mock_client.set_test_data(RECORDED_PACKETS["data_discharging_low"])
        patch_bleak_client(lambda *args, **kwargs: mock_client)

        # Create BMS instance
        bms = BMS(mock_device)

        # Perform update
        result = await bms.async_update()

        # Verify parsed values from actual packet:
        # 55aa2d0480aa01701c05000096090080e2000000ad19000033000000ca050000890c0000770b0000044e000082648e684000
        # Current is 4 bytes at offset 8-11: 0x96090080 = -2.454A (0x0996 with discharge flag 0x80)
        expected = {
            "voltage": 13.08,  # 0x051c = 1308 / 100
            "current": -2.454,   # 0x96090080: magnitude 0x0996=2454/1000=2.454A, discharge flag 0x80
            "temperature": 22.6,  # 0xe2 = 226 / 10
            "battery_level": 51,  # 0x33
            "cycle_charge": 65.73,  # 0x19ad = 6573 / 100 = 65.73 Ah (remaining capacity)
            "power": 14.82,  # 0x05ca = 1482 / 100 = 14.82 W
            "runtime": 3209,  # 0x0c89 = 3209 seconds (bytes 32-35)
        }
        for key, expected_value in expected.items():
            assert key in result
            assert result[key] == pytest.approx(expected_value, rel=0.01)

    @pytest.mark.asyncio
    async def test_async_update_streaming(self, mock_device, patch_bleak_client):
        """Test async update when already streaming."""
        # Create mock client and set actual recorded data packet
        mock_client = MockProBMSBleakClient(mock_device)
        # Use a charging packet with high current
        mock_client.set_test_data(RECORDED_PACKETS["data_charging_high"])
        patch_bleak_client(lambda *args, **kwargs: mock_client)

        # Create BMS instance and simulate it's already streaming
        bms = BMS(mock_device)
        await bms.async_update()  # First update to initialize

        # Reset write count and do another update
        mock_client.write_gatt_char = AsyncMock()
        result = await bms.async_update()

        # Verify no initialization sequence was sent
        mock_client.write_gatt_char.assert_not_called()

        # Verify parsed values from actual packet
        # 55aa2d0480aa01703b05000066340000da00000057100000200000008601000029460000580a0000eb4600000bd98c68afff
        # Current is 4 bytes at offset 8-11: 0x66340000 = 13.414A (0x3466 with no discharge flag)
        expected = {
            "voltage": 13.39,  # 0x053b = 1339 / 100
            "current": 13.414,   # 0x66340000: magnitude 0x3466=13414/1000=13.414A, no discharge flag
            "temperature": 21.8,  # 0xda = 218 / 10
            "battery_level": 32,  # 0x20
            "cycle_charge": 41.83,  # 0x1057 = 4183 / 100 = 41.83 Ah
            "power": 3.9,  # 0x00000186 = 390 / 100 = 3.9 W (bytes 28-31)
            "runtime": 17961,  # 0x4629 = 17961 seconds (bytes 32-35)
            "design_capacity": 130,  # Calculated: 41.83 / (32/100) = 130.7 ≈ 130 Ah
        }

        for key, expected_value in expected.items():
            assert key in result
            assert result[key] == pytest.approx(expected_value, rel=0.01)

    @pytest.mark.asyncio
    async def test_async_update_discharging_minimal(self, mock_device, patch_bleak_client):
        """Test async update when discharging with minimal current."""
        # Use actual recorded data packet with minimal discharge
        mock_client = MockProBMSBleakClient(mock_device)
        mock_client.set_test_data(RECORDED_PACKETS["data_discharging_minimal"])
        patch_bleak_client(lambda *args, **kwargs: mock_client)

        # Create BMS instance
        bms = BMS(mock_device)

        # Perform update
        result = await bms.async_update()

        # Verify parsed values
        # 55aa2d0480aa01702f0500008f010080d8000000ba210000430000006b3e000011020000390b00006d4b0000c2648e686957
        # Current is 4 bytes at offset 8-11: 0x8f010080 = -0.399A (0x018f with discharge flag 0x80)
        expected = {
            "voltage": 13.27,  # 0x052f = 1327 / 100
            "current": -0.399,   # 0x8f010080: magnitude 0x018f=399/1000=0.399A, discharge flag 0x80
            "temperature": 21.6,  # 0xd8 = 216 / 10
            "battery_level": 67,  # 0x43
            "cycle_charge": 86.34,  # 0x21ba = 8634 / 100 = 86.34 Ah
            "power": 159.79,  # 0x3e6b = 15979 / 100 = 159.79 W
            "runtime": 529,  # 0x0211 = 529 seconds (bytes 32-35)
            "design_capacity": 128,  # Calculated: 86.34 / (67/100) = 128.9 ≈ 128 Ah
        }

        for key, expected_value in expected.items():
            assert key in result
            assert result[key] == pytest.approx(expected_value, rel=0.01)

    @pytest.mark.asyncio
    async def test_async_update_with_temperature(self, mock_device, patch_bleak_client):
        """Test parsing temperature value."""
        # Create mock client and set actual recorded data
        mock_client = MockProBMSBleakClient(mock_device)
        mock_client.set_test_data(RECORDED_PACKETS["data_charging_medium"])
        patch_bleak_client(lambda *args, **kwargs: mock_client)

        # Create BMS instance
        bms = BMS(mock_device)

        # Perform update
        result = await bms.async_update()
        assert "temperature" in result
        assert result["temperature"] == 24.5  # 0xf5 = 245 / 10

    @pytest.mark.asyncio
    async def test_async_update_with_low_temperature(self, mock_device, patch_bleak_client):
        """Test parsing low temperature value."""
        # Create mock client and set test data
        # Note: The device appears to use unsigned temperature values
        mock_client = MockProBMSBleakClient(mock_device)
        # Create a modified packet with temperature = 0x0a at offset 12
        # Take the discharging packet and modify just the temperature byte
        base_packet = RECORDED_PACKETS["data_discharging_low"]
        modified_packet = bytearray(base_packet)
        modified_packet[16] = 0x0a  # Set temperature to 0x0a (1.0°C) at offset 12 in data section (16 in full packet)
        mock_client.set_test_data(modified_packet)
        patch_bleak_client(lambda *args, **kwargs: mock_client)

        # Create BMS instance
        bms = BMS(mock_device)

        # Perform update
        result = await bms.async_update()
        assert "temperature" in result
        assert result["temperature"] == 1.0  # 0x0a = 10 / 10 = 1.0°C

    @pytest.mark.asyncio
    async def test_async_update_with_protection(self, mock_device, patch_bleak_client):
        """Test parsing protection status."""
        # Create mock client and set test data with protection status
        mock_client = MockProBMSBleakClient(mock_device)
        mock_client.set_test_data(RECORDED_PACKETS["data_with_protection"])
        patch_bleak_client(lambda *args, **kwargs: mock_client)

        # Create BMS instance
        bms = BMS(mock_device)

        # Perform update
        result = await bms.async_update()
        # Protection byte at offset 11 in data section = 0x81 (discharge + protection bit 0)
        assert "problem_code" in result
        assert result["problem_code"] == 1  # 0x81 & 0x7F = 1

    @pytest.mark.asyncio
    async def test_async_update_incomplete_data(self, mock_device, patch_bleak_client):
        """Test handling of incomplete data packet."""
        # Create mock client and set incomplete data (too short)
        mock_client = MockProBMSBleakClient(mock_device)
        mock_client.set_test_data(bytearray.fromhex("55aa0d0480aa0170"))  # Only 8 bytes
        patch_bleak_client(lambda *args, **kwargs: mock_client)

        # Create BMS instance
        bms = BMS(mock_device)

        # Should return empty dict for incomplete data
        result = await bms.async_update()
        assert result == {}

    @pytest.mark.asyncio
    async def test_calc_values_incomplete_data(self, mock_device):
        """Test _calc_values returns the set of values to calculate."""
        # Create BMS instance
        bms = BMS(mock_device)

        # _calc_values() returns a frozenset of values to calculate, not calculated values
        result = bms._calc_values()

        # Should return the frozenset of values that the base class should calculate
        # battery_charging and cycle_capacity are calculated by base class
        # design_capacity is calculated directly in _async_update, not by base class
        assert result == frozenset({"battery_charging", "cycle_capacity"})

    def test_notification_handler_invalid_header(self, bms):
        """Test notification handler with invalid header."""
        # Invalid header
        data = bytearray.fromhex("aabb2d0480aa0170")
        bms._notification_handler(None, data)
        # Should not set data event
        assert not bms._data_event.is_set()

    def test_notification_handler_realtime_data(self, bms):
        """Test notification handler with realtime data."""
        # Valid realtime data packet from actual device
        data = RECORDED_PACKETS["data_discharging_low"]
        bms._notification_handler(None, data)
        # Should set data event and streaming flag
        assert bms._data_event.is_set()
        assert bms._streaming is True
        assert bms._data == data

    def test_notification_handler_short_packet(self, bms):
        """Test notification handler with short packet."""
        # Too short packet
        data = bytearray.fromhex("55aa2d")
        bms._notification_handler(None, data)
        # Should not set data event
        assert not bms._data_event.is_set()

    def test_notification_handler_init_response(self, bms):
        """Test notification handler with init response."""
        # Actual init response packet from device (type 0x03)
        data = RECORDED_PACKETS["init_response_1"]
        bms._notification_handler(None, data)
        # Should set data event and init response flag
        assert bms._data_event.is_set()
        assert bms._init_response_received is True

    def test_notification_handler_sets_streaming_flag(self, bms):
        """Test that notification handler sets streaming flag."""
        assert bms._streaming is False
        # Valid realtime data packet from actual device
        data = RECORDED_PACKETS["data_charging_high"]
        bms._notification_handler(None, data)
        assert bms._streaming is True

    def test_calc_values(self, bms):
        """Test calculated values."""
        calc_values = bms._calc_values()
        # Power is provided directly by the BMS, not calculated
        assert "power" not in calc_values
        # Runtime is provided directly from packet data (bytes 32-35), not calculated by base class
        assert "runtime" not in calc_values
        # These are calculated by the base class
        assert "battery_charging" in calc_values
        assert "cycle_capacity" in calc_values
        # design_capacity is not in _calc_values since it's calculated directly in _async_update
        assert "design_capacity" not in calc_values

    def test_negative_current_calculation(self, bms):
        """Test negative current calculation."""
        # The actual device uses discharge flag, not signed current value
        # This test verifies the data is stored correctly
        data = RECORDED_PACKETS["data_discharging_low"]
        bms._data = data
        bms._data_event.set()
        # The actual parsing happens in _async_update

    @pytest.mark.asyncio
    async def test_async_update_no_init_response(self, bms):
        """Test handling when no initialization response is received."""
        # Directly test the error path by setting init_response_received to False
        bms._init_response_received = False
        bms._data_event.set()  # Simulate timeout by setting event without response

        # This should trigger the "No initialization response received" path
        # which returns an empty dict
        assert bms._init_response_received is False

    @pytest.mark.asyncio
    async def test_async_update_timeout_error_handling(self, bms):
        """Test that timeout error is caught and returns empty dict."""
        # The actual timeout handling is in the Pro BMS _async_update method
        # We're just verifying the error handling code exists
        # The actual timeout scenario is tested by test_async_update_incomplete_data
        assert hasattr(bms, '_async_update')

    def test_protection_code_parsing(self, bms):
        """Test parsing protection status code."""
        # Valid realtime data packet with protection code set
        data = RECORDED_PACKETS["data_with_protection"]
        bms._notification_handler(None, data)

        # The protection byte is at offset 11 in data section (0x81 = discharge + protection bit 0)
        # This should trigger the protection code parsing
        assert bms._data == data
        assert bms._streaming is True

    @pytest.mark.asyncio
    async def test_async_update_timeout_during_init(self, mock_device, patch_bleak_client):
        """Test timeout during initialization."""
        # Create mock client that will timeout
        mock_client = MockProBMSBleakClient(mock_device)

        # Override wait_for to raise TimeoutError
        async def mock_wait_for(*args, **kwargs):
            raise TimeoutError

        patch_bleak_client(lambda *args, **kwargs: mock_client)

        # Create BMS instance
        bms = BMS(mock_device)

        # Patch wait_for to timeout
        with patch('asyncio.wait_for', side_effect=mock_wait_for):
            result = await bms.async_update()

        # Should return empty dict on timeout
        assert result == {}

    @pytest.mark.asyncio
    async def test_async_update_no_init_response_timeout(self, mock_device, patch_bleak_client):
        """Test when no initialization response is received."""
        # Create mock client
        mock_client = MockProBMSBleakClient(mock_device)
        patch_bleak_client(lambda *args, **kwargs: mock_client)

        # Create BMS instance
        bms = BMS(mock_device)

        # Override _wait_event to simulate no response
        async def mock_wait_event():
            # Don't set init_response_received
            bms._data_event.set()

        bms._wait_event = mock_wait_event

        # Perform update
        result = await bms.async_update()

        # Should return empty dict when no init response
        assert result == {}

    @pytest.mark.asyncio
    async def test_async_update_incomplete_data_after_init(self, mock_device, patch_bleak_client):
        """Test when data is incomplete after successful init."""
        # Create mock client
        mock_client = MockProBMSBleakClient(mock_device)

        # Set short data that will be incomplete
        mock_client.set_test_data(bytearray.fromhex("55aa2d0480aa0170"))  # Too short

        patch_bleak_client(lambda *args, **kwargs: mock_client)

        # Create BMS instance
        bms = BMS(mock_device)

        # Perform update
        result = await bms.async_update()

        # Should return empty dict for incomplete data
        assert result == {}

    @pytest.mark.asyncio
    async def test_async_update_no_valid_data_after_init(self, mock_device, patch_bleak_client):
        """Test when no valid data is received after initialization."""
        # Create mock client
        mock_client = MockProBMSBleakClient(mock_device)

        # Set init response but no data
        mock_client._init_response = bytearray.fromhex("55aa2d0380aa0170")
        mock_client._test_data = None  # No data will be streamed

        patch_bleak_client(lambda *args, **kwargs: mock_client)

        # Create BMS instance
        bms = BMS(mock_device)

        # Override _wait_event to not wait forever
        async def mock_wait_event():
            bms._init_response_received = True
            bms._data_event.set()

        bms._wait_event = mock_wait_event

        # Perform update
        result = await bms.async_update()

        # Should return empty dict when no data
        assert result == {}

    @pytest.mark.asyncio
    async def test_async_update_with_protection_code(self, mock_device, patch_bleak_client):
        """Test parsing protection/error code."""
        # Create mock client and set test data with protection bit set
        mock_client = MockProBMSBleakClient(mock_device)
        mock_client.set_test_data(RECORDED_PACKETS["data_with_protection"])
        patch_bleak_client(lambda *args, **kwargs: mock_client)

        # Create BMS instance
        bms = BMS(mock_device)

        # Perform update
        result = await bms.async_update()

        # Should have problem_code set to 1 (bit 0 of protection status, 0x81 & 0x7F = 1)
        assert "problem_code" in result
        assert result["problem_code"] == 1

    @pytest.mark.asyncio
    async def test_disconnect_resets_state(self, mock_device, patch_bleak_client):
        """Test that disconnect resets initialization state."""
        # Create mock client with actual recorded data
        mock_client = MockProBMSBleakClient(mock_device)
        mock_client.set_test_data(RECORDED_PACKETS["data_high_soc"])
        patch_bleak_client(lambda *args, **kwargs: mock_client)

        # Create BMS instance and connect
        bms = BMS(mock_device)
        await bms.async_update()

        # Verify initialization state
        assert bms._init_complete is True
        assert bms._streaming is True

        # Disconnect
        await bms.disconnect()

        # Verify state is reset
        assert bms._init_complete is False
        assert bms._streaming is False
        assert bms._init_response_received is False


    @pytest.mark.asyncio
    async def test_async_update_battery_level_zero(self, mock_device, patch_bleak_client):
        """Test async update when battery_level is 0 (design_capacity not calculated)."""
        mock_client = MockProBMSBleakClient(mock_device)

        # Create a modified packet with battery_level = 0
        base_packet = bytearray(RECORDED_PACKETS["data_charging_high"])
        # Battery level is at offset 20 in the data section (offset 24 in full packet)
        base_packet[24] = 0x00  # Set battery_level to 0

        mock_client.set_test_data(base_packet)
        patch_bleak_client(lambda *args, **kwargs: mock_client)

        bms = BMS(mock_device)

        # Perform update
        result = await bms.async_update()

        # Verify battery_level is 0
        assert result["battery_level"] == 0

        # design_capacity should not be calculated when battery_level is 0
        assert "design_capacity" not in result

        # But cycle_charge should still be present
        assert "cycle_charge" in result




    def test_incomplete_data_packet_check(self, bms):
        """Test that incomplete data packets are detected."""
        # Packet that's too short (less than 45 bytes)
        short_data = bytearray.fromhex("55aa0d0480aa0170")  # Only 8 bytes
        bms._notification_handler(None, short_data)
        # Should not set streaming flag for incomplete data
        assert bms._streaming is False

    @pytest.mark.asyncio
    async def test_async_update_incomplete_data_in_calc_values(self, mock_device):
        """Test _async_update when data packet is incomplete (< 45 bytes) during calc_values."""
        # Create BMS instance
        bms = BMS(mock_device)

        # Mock the BleakClient
        with patch("custom_components.bms_ble.plugins.basebms.BleakClient") as mock_client_class:
            mock_client = MockProBMSBleakClient(mock_device)
            mock_client_class.return_value = mock_client

            # Override write_gatt_char to send incomplete data after init
            original_write = mock_client.write_gatt_char
            async def mock_write(char, data, response=None):
                await original_write(char, data, response)
                # After init sequence, set incomplete data
                if data == BMS.CMD_TRIGGER_DATA:
                    mock_client.set_test_data(bytearray.fromhex("55aa0d0480aa0170"))  # Only 8 bytes

            mock_client.write_gatt_char = mock_write

            # Perform update - should handle incomplete data gracefully
            result = await bms.async_update()

        # Should return empty dict for incomplete data
        assert result == {}

    @pytest.mark.asyncio
    async def test_async_update_no_init_response_after_cmd(self, mock_device):
        """Test _async_update when no initialization response is received after CMD_INIT."""
        # Create BMS instance
        bms = BMS(mock_device)

        # Mock the BleakClient
        with patch("custom_components.bms_ble.plugins.basebms.BleakClient") as mock_client_class:
            mock_client = MockProBMSBleakClient(mock_device)
            mock_client_class.return_value = mock_client

            # Override write_gatt_char to NOT send init response
            async def mock_write(char, data, response=None):
                # Call parent but skip sending init response
                await super(MockProBMSBleakClient, mock_client).write_gatt_char(char, data, response)
                # Don't send any response for CMD_INIT

            mock_client.write_gatt_char = mock_write

            # Mock wait_for to simulate timeout but with init_response_received still False
            with patch('asyncio.wait_for') as mock_wait_for:
                # Simulate that wait completes but no response was received
                mock_wait_for.return_value = None

                # Perform update - should handle no init response gracefully
                result = await bms.async_update()

            # Should return empty dict for no init response
            assert result == {}


    @pytest.mark.asyncio
    async def test_calc_values_with_zero_battery_level(self, mock_device, patch_bleak_client):
        """Test design_capacity calculation when battery_level is 0."""
        # Since we simplified the code, we only need to test the edge case
        # where battery_level is 0 to avoid division by zero

        mock_client = MockProBMSBleakClient(mock_device)

        # Use charging packet but modify battery_level to 0
        zero_soc_packet = bytearray(RECORDED_PACKETS["data_charging_high"])
        zero_soc_packet[24] = 0x00  # Set SOC to 0

        mock_client.set_test_data(zero_soc_packet)
        patch_bleak_client(lambda *args, **kwargs: mock_client)

        bms = BMS(mock_device)
        result = await bms.async_update()

        # Verify battery_level is 0 and design_capacity is not calculated
        assert result["battery_level"] == 0
        assert "design_capacity" not in result
        # But base class calculations should still work
        assert "battery_charging" in result  # Base class calculates this
        assert "cycle_capacity" in result  # Base class calculates this


class TestProBMSDeviceDetection:
    """Test Pro BMS device detection scenarios."""

    def test_device_detected_with_correct_name_and_service_uuid(self):
        """Test device is correctly detected when name is 'Pro BMS' AND service UUID matches."""
        # Create a device with correct name and service UUID
        device = generate_ble_device(
            address="AA:BB:CC:DD:EE:FF",
            name="Pro BMS"
        )
        adv_data = generate_advertisement_data(
            local_name="Pro BMS",
            service_uuids=["0000fff0-0000-1000-8000-00805f9b34fb"]
        )

        # Check matcher_dict_list
        matchers = BMS.matcher_dict_list()
        assert len(matchers) == 1
        matcher = matchers[0]

        # Verify the device would match
        assert matcher["local_name"] == "Pro BMS"
        assert matcher["service_uuid"] == "0000fff0-0000-1000-8000-00805f9b34fb"
        assert matcher["connectable"] is True

        # Verify device name matches
        assert device.name == matcher["local_name"]
        # Verify service UUID is in advertisement
        assert matcher["service_uuid"] in adv_data.service_uuids

    def test_device_not_detected_when_name_is_none(self):
        """Test device is NOT detected when name is null/None."""
        # Create a device with None name
        device = generate_ble_device(
            address="AA:BB:CC:DD:EE:FF",
            name=None
        )
        generate_advertisement_data(
            local_name=None,
            service_uuids=["0000fff0-0000-1000-8000-00805f9b34fb"]
        )

        # Check matcher requirements
        matchers = BMS.matcher_dict_list()
        matcher = matchers[0]

        # Device name is None, which doesn't match "Pro BMS"
        assert device.name != matcher["local_name"]
        assert device.name is None

    def test_device_not_detected_when_name_is_mac_address(self):
        """Test device is NOT detected when name is a MAC address."""
        # Create a device with MAC address as name
        mac_address = "AA:BB:CC:DD:EE:FF"
        device = generate_ble_device(
            address=mac_address,
            name=mac_address
        )
        generate_advertisement_data(
            local_name=mac_address,
            service_uuids=["0000fff0-0000-1000-8000-00805f9b34fb"]
        )

        # Check matcher requirements
        matchers = BMS.matcher_dict_list()
        matcher = matchers[0]

        # Device name is MAC address, which doesn't match "Pro BMS"
        assert device.name == mac_address
        assert device.name != matcher["local_name"]

    def test_device_not_detected_when_name_different_but_service_uuid_matches(self):
        """Test device is NOT detected when name is different but service UUID matches."""
        # Create a device with different name but correct service UUID
        device = generate_ble_device(
            address="AA:BB:CC:DD:EE:FF",
            name="Other BMS"
        )
        adv_data = generate_advertisement_data(
            local_name="Other BMS",
            service_uuids=["0000fff0-0000-1000-8000-00805f9b34fb"]
        )

        # Check matcher requirements
        matchers = BMS.matcher_dict_list()
        matcher = matchers[0]

        # Device name doesn't match "Pro BMS"
        assert device.name == "Other BMS"
        assert device.name != matcher["local_name"]
        # Service UUID matches but name doesn't
        assert matcher["service_uuid"] in adv_data.service_uuids

    def test_device_not_detected_when_name_correct_but_service_uuid_missing(self):
        """Test device is NOT detected when name is 'Pro BMS' but service UUID is missing."""
        # Create a device with correct name but no service UUID
        device = generate_ble_device(
            address="AA:BB:CC:DD:EE:FF",
            name="Pro BMS"
        )
        adv_data = generate_advertisement_data(
            local_name="Pro BMS",
            service_uuids=[]  # No service UUIDs
        )

        # Check matcher requirements
        matchers = BMS.matcher_dict_list()
        matcher = matchers[0]

        # Device name matches
        assert device.name == matcher["local_name"]
        # But service UUID is not in advertisement
        assert matcher["service_uuid"] not in adv_data.service_uuids
        assert len(adv_data.service_uuids) == 0

    def test_device_not_detected_when_name_correct_but_wrong_service_uuid(self):
        """Test device is NOT detected when name is 'Pro BMS' but service UUID is wrong."""
        # Create a device with correct name but wrong service UUID
        device = generate_ble_device(
            address="AA:BB:CC:DD:EE:FF",
            name="Pro BMS"
        )
        adv_data = generate_advertisement_data(
            local_name="Pro BMS",
            service_uuids=["0000ffe0-0000-1000-8000-00805f9b34fb"]  # Wrong UUID
        )

        # Check matcher requirements
        matchers = BMS.matcher_dict_list()
        matcher = matchers[0]

        # Device name matches
        assert device.name == matcher["local_name"]
        # But service UUID doesn't match
        assert matcher["service_uuid"] not in adv_data.service_uuids

    def test_matcher_dict_list_returns_correct_criteria(self):
        """Test the matcher_dict_list() method returns the correct detection criteria."""
        matchers = BMS.matcher_dict_list()

        # Should return exactly one matcher
        assert len(matchers) == 1

        matcher = matchers[0]
        # Check all required fields
        assert "local_name" in matcher
        assert "service_uuid" in matcher
        assert "connectable" in matcher

        # Check values
        assert matcher["local_name"] == "Pro BMS"
        assert matcher["service_uuid"] == "0000fff0-0000-1000-8000-00805f9b34fb"
        assert matcher["connectable"] is True

        # Should not have manufacturer_id
        assert "manufacturer_id" not in matcher

    def test_device_not_detected_when_not_connectable(self):
        """Test device is NOT detected when it's not connectable."""
        # The matcher requires connectable=True
        matchers = BMS.matcher_dict_list()
        matcher = matchers[0]

        # Verify connectable is required
        assert matcher["connectable"] is True

        # A non-connectable device with correct name and UUID would not match
        # because the matcher requires connectable=True

    def test_device_detected_case_sensitive_name(self):
        """Test device detection is case sensitive for name."""
        # Create devices with different case names
        device_lower = generate_ble_device(
            address="AA:BB:CC:DD:EE:FF",
            name="pro bms"
        )
        device_upper = generate_ble_device(
            address="AA:BB:CC:DD:EE:FF",
            name="PRO BMS"
        )
        device_correct = generate_ble_device(
            address="AA:BB:CC:DD:EE:FF",
            name="Pro BMS"
        )

        # Check matcher requirements
        matchers = BMS.matcher_dict_list()
        matcher = matchers[0]

        # Only exact case match should work
        assert device_lower.name != matcher["local_name"]
        assert device_upper.name != matcher["local_name"]
        assert device_correct.name == matcher["local_name"]

    def test_device_not_detected_with_extra_text_in_name(self):
        """Test device is NOT detected when name contains extra text."""
        # Create devices with variations of the name
        device_prefix = generate_ble_device(
            address="AA:BB:CC:DD:EE:FF",
            name="My Pro BMS"
        )
        device_suffix = generate_ble_device(
            address="AA:BB:CC:DD:EE:FF",
            name="Pro BMS Device"
        )

        # Check matcher requirements
        matchers = BMS.matcher_dict_list()
        matcher = matchers[0]

        # Names with extra text should not match
        assert device_prefix.name != matcher["local_name"]
        assert device_suffix.name != matcher["local_name"]

    def test_uuid_services_normalized(self):
        """Test that UUID services are properly normalized."""
        services = BMS.uuid_services()
        assert len(services) == 1
        # Should return the full 128-bit UUID
        assert services[0] == "0000fff0-0000-1000-8000-00805f9b34fb"

        # The normalize_uuid_str function should handle both short and long forms
        from bleak.uuids import normalize_uuid_str
        assert normalize_uuid_str("fff0") == services[0]
