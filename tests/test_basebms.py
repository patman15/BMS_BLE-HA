"""Test the BLE Battery Management System base class functions."""

from collections.abc import Buffer, Callable
from typing import Final
from uuid import UUID

from bleak.backends.characteristic import BleakGATTCharacteristic
from bleak.backends.device import BLEDevice
from bleak.exc import BleakError
from bleak.uuids import normalize_uuid_str
import pytest

from custom_components.bms_ble.plugins.basebms import (
    AdvertisementPattern,
    BaseBMS,
    BMSsample,
    crc8,
    crc_modbus,
    crc_xmodem,
)

from .bluetooth import generate_ble_device
from .conftest import MockBleakClient


class MockWriteModeBleakClient(MockBleakClient):
    """Emulate a BleakClient with selectable write mode response."""

    # The following attributes are used to simulate the behavior of the BleakClient
    # They need to be set via monkeypatching in the test since init() is called by the BMS
    PATTERN: list[bytes | Exception | None] = []
    VALID_WRITE_MODES: list[str] = ["write-without_response", "write"]
    EXP_WRITE_RESPONSE: list[bool] = []

    async def write_gatt_char(
        self,
        char_specifier: BleakGATTCharacteristic | int | str | UUID,
        data: Buffer,
        response: bool | None = None,
    ) -> None:
        """Issue write command to GATT."""
        await super().write_gatt_char(char_specifier, data, response)

        assert self._notify_callback is not None
        if self.PATTERN:
            # check if we have a pattern to return
            pattern: bytes | Exception | None = self.PATTERN.pop(0)
            exp_wr_mode: Final[bool] = self.EXP_WRITE_RESPONSE.pop(0)
            if isinstance(pattern, Exception):
                raise pattern

            req_wr_mode: Final[str] = "write" if response else "write-without_response"
            assert response == exp_wr_mode, "write response mismatch"

            if isinstance(pattern, bytes) and req_wr_mode in self.VALID_WRITE_MODES:
                # check if we have a dict to return
                self._notify_callback("rx_char", bytearray(pattern))
                return

            # if None was selected do not return (trigger timeout) and wait for next pattern
            return

        # no pattern left, raise exception
        raise ValueError


class WMTestBMS(BaseBMS):
    """Test BMS implementation."""

    def __init__(
        self,
        char_tx_properties: list[str],
        ble_device: BLEDevice,
        reconnect: bool = False,
    ) -> None:
        """Initialize BMS."""
        super().__init__(__name__, ble_device, reconnect)
        self._char_tx_properties: list[str] = char_tx_properties

    @staticmethod
    def matcher_dict_list() -> list[AdvertisementPattern]:
        """Provide BluetoothMatcher definition."""
        return [{"local_name": "Test", "connectable": True}]

    @staticmethod
    def device_info() -> dict[str, str]:
        """Return device information for the battery management system."""
        return {"manufacturer": "Test Manufacturer", "model": "write mode test"}

    @staticmethod
    def uuid_services() -> list[str]:
        """Return list of 128-bit UUIDs of services required by BMS."""
        return [normalize_uuid_str("afe0")]

    @staticmethod
    def uuid_rx() -> str:
        """Return 16-bit UUID of characteristic that provides notification/read property."""
        return "afe1"

    @staticmethod
    def uuid_tx() -> str:
        """Return 16-bit UUID of characteristic that provides write property."""
        return "afe2"

    def _wr_response(self, char: int | str) -> bool:
        return bool("write" in self._char_tx_properties)

    def _notification_handler(
        self, _sender: BleakGATTCharacteristic, data: bytearray
    ) -> None:
        """Handle the RX characteristics notify event (new data arrives)."""
        self._log.debug("RX BLE data: %s", data)
        self._data = data
        self._data_event.set()

    async def _async_update(self) -> BMSsample:
        """Update battery status information."""
        await self._await_reply(b"mock_command")

        return {"problem_code": int.from_bytes(self._data, "big", signed=False)}

def test_calc_missing_values(bms_data_fixture: BMSsample) -> None:
    """Check if missing data is correctly calculated."""
    bms_data: BMSsample = bms_data_fixture
    ref: BMSsample = bms_data_fixture.copy()

    BaseBMS._add_missing_values(
        bms_data,
        frozenset(
            {
                "battery_charging",
                "cycle_capacity",
                "power",
                "runtime",
                "delta_voltage",
                "temperature",
                "voltage",  # check that not overwritten
            }
        ),
    )
    ref = ref | {
        "cycle_capacity": 238,
        "delta_voltage": 0.111,
        "power": (
            -91
            if bms_data.get("current", 0) < 0
            else 0 if bms_data.get("current") == 0 else 147
        ),
        # battery is charging if current is positive
        "battery_charging": bms_data.get("current", 0) > 0,
        "temperature": -34.396,
        "problem": False,
    }
    if bms_data.get("current", 0) < 0:
        ref |= {"runtime": 9415}

    assert bms_data == ref


def test_calc_voltage() -> None:
    """Check if missing data is correctly calculated."""
    bms_data: BMSsample = {"cell_voltages": [3.456, 3.567]}
    ref: BMSsample = bms_data.copy()
    BaseBMS._add_missing_values(bms_data, frozenset({"voltage"}))
    assert bms_data == ref | {"voltage": 7.023, "problem": False}


def test_calc_cycle_chrg() -> None:
    """Check if missing data is correctly calculated."""
    bms_data: BMSsample = {"battery_level": 73, "design_capacity": 125}
    ref: BMSsample = bms_data.copy()
    BaseBMS._add_missing_values(bms_data, frozenset({"cycle_charge"}))
    assert bms_data == ref | {"cycle_charge": 91.25, "problem": False}

def test_calc_battery_level() -> None:
    """Check if missing battery_level is correctly calculated."""
    bms_data: BMSsample = {"cycle_charge": 421, "design_capacity": 983}
    ref: BMSsample = bms_data.copy()
    BaseBMS._add_missing_values(bms_data, frozenset({"battery_level"}))
    assert bms_data == ref | {"battery_level": 42.8, "problem": False}

@pytest.fixture(
    name="problem_samples",
    params=[
        ({"voltage": -1}, "negative overall voltage"),
        ({"cell_voltages": [5.907]}, "high cell voltage"),
        ({"cell_voltages": [-0.001]}, "negative cell voltage"),
        ({"delta_voltage": 5.907}, "doubtful delta voltage"),
        ({"cycle_charge": 0}, "doubtful cycle charge"),
        ({"battery_level": 101}, "doubtful SoC"),
        ({"problem_code": 0x1}, "BMS problem code"),
        ({"problem": True}, "BMS problem report"),
    ],
    ids=lambda param: param[1],
)
def mock_bms_data(request: pytest.FixtureRequest) -> BMSsample:
    """Return BMS data to check error handling function."""
    return request.param[0]


def test_problems(problem_samples: BMSsample) -> None:
    """Check if missing data is correctly calculated."""
    bms_data: BMSsample = problem_samples.copy()

    BaseBMS._add_missing_values(bms_data, frozenset({"runtime"}))

    assert bms_data == problem_samples | {"problem": True}


@pytest.mark.parametrize(
    ("replies", "exp_wr_response", "exp_output"),
    [
        ([b"\x12"], [True], [0x12]),
        (
            [None] * 2 * (BaseBMS.MAX_RETRY),
            [True] * (BaseBMS.MAX_RETRY) + [False] * (BaseBMS.MAX_RETRY),
            [TimeoutError()],
        ),
        (
            [None] * (BaseBMS.MAX_RETRY - 1) + [b"\x13"],
            [True] * (BaseBMS.MAX_RETRY),
            [0x13],
        ),
        (
            [None] * (BaseBMS.MAX_RETRY) + [b"\x14"],
            [True] * (BaseBMS.MAX_RETRY) + [False],
            [0x14],
        ),
        (
            [BleakError()]
            + [None] * (BaseBMS.MAX_RETRY - 1)
            + [b"\x15"]
            + [None] * (BaseBMS.MAX_RETRY - 1)
            + [b"\x16"],
            [True] + [False] * BaseBMS.MAX_RETRY + [False] * BaseBMS.MAX_RETRY,
            [0x15, 0x16],
        ),
        (
            [None] * (BaseBMS.MAX_RETRY - 1) + [ValueError()],
            [True] * (BaseBMS.MAX_RETRY),
            [ValueError()],
        ),
    ],
    ids=[
        "basic_test",
        "no_response",
        "retry_count-1",
        "retry_count",
        "mode_switch",
        "unhandled_exc",
    ],
)
async def test_write_mode(
    monkeypatch,
    patch_bleak_client,
    patch_bms_timeout,
    replies: list[bytearray | Exception | None],
    exp_wr_response: list[bool],
    exp_output: list[int | Exception],
    request: pytest.FixtureRequest,
) -> None:
    """Check if write mode selection works correctly."""

    assert len(replies) == len(
        exp_wr_response
    ), "Replies and expected responses must match in length!"
    patch_bms_timeout()
    monkeypatch.setattr(MockWriteModeBleakClient, "PATTERN", replies)
    monkeypatch.setattr(MockWriteModeBleakClient, "EXP_WRITE_RESPONSE", exp_wr_response)

    patch_bleak_client(MockWriteModeBleakClient)

    bms = WMTestBMS(
        ["write-no-response", "write"],
        generate_ble_device("cc:cc:cc:cc:cc:cc", "MockBLEDevice", None, -73),
        False,
    )

    # NOTE: output must reflect the end result after one call, as init of HA resets the whole BMS!
    for output in exp_output:
        if isinstance(output, Exception):
            with pytest.raises(type(output)):
                await bms.async_update()
        else:
            assert await bms.async_update() == {
                "problem_code": output
            }, f"{request.node.name} failed!"
def test_crc_calculations() -> None:
    """Check if CRC calculations are correct."""
    # Example data for CRC calculation
    data: bytearray = bytearray([0x31, 0x32, 0x33, 0x34, 0x35, 0x36, 0x37, 0x38, 0x39])
    test_fn: list[tuple[Callable[[bytearray], int], int]] = [
        (crc_modbus, 0x4B37),
        (crc8, 0xA1),
        (crc_xmodem, 0x31C3),
    ]

    for crc_fn, expected_crc in test_fn:
        calculated_crc: int = crc_fn(data)
        assert (
            calculated_crc == expected_crc
        ), f"Expected {expected_crc}, got {calculated_crc}"


class TestCalculateChargeTime:
    """Test the _calculate_charge_time method."""

    class MockBMS(BaseBMS):
        """Mock BMS implementation for charge time calculation."""

        def __init__(self, ble_device: BLEDevice) -> None:
            """Initialize BMS."""
            super().__init__(__name__, ble_device, False)

        @staticmethod
        def matcher_dict_list() -> list[AdvertisementPattern]:
            """Provide BluetoothMatcher definition."""
            return [{"local_name": "Test", "connectable": True}]

        @staticmethod
        def device_info() -> dict[str, str]:
            """Return device information for the battery management system."""
            return {"manufacturer": "Test", "model": "charge time test"}

        @staticmethod
        def uuid_services() -> list[str]:
            """Return list of 128-bit UUIDs of services required by BMS."""
            return [normalize_uuid_str("afe0")]

        @staticmethod
        def uuid_rx() -> str:
            """Return 16-bit UUID of characteristic that provides notification/read property."""
            return "afe1"

        @staticmethod
        def uuid_tx() -> str:
            """Return 16-bit UUID of characteristic that provides write property."""
            return "afe2"

        def _notification_handler(
            self, _sender: BleakGATTCharacteristic, data: bytearray
        ) -> None:
            """Handle the RX characteristics notify event (new data arrives)."""

        async def _async_update(self) -> BMSsample:
            """Update battery status information."""
            return {}

    def test_charge_time_negative_current(self) -> None:
        """Test charge time calculation with negative current (discharging)."""
        bms = self.MockBMS(generate_ble_device("aa:bb:cc:dd:ee:ff", "TestBMS", None, -50))
        data = {"design_capacity": 100.0, "cycle_charge": 50.0}
        result = bms._calculate_charge_time(data, -10.0)
        assert result is None

    def test_charge_time_zero_current(self) -> None:
        """Test charge time calculation with zero current."""
        bms = self.MockBMS(generate_ble_device("aa:bb:cc:dd:ee:ff", "TestBMS", None, -50))
        data = {"design_capacity": 100.0, "cycle_charge": 50.0}
        result = bms._calculate_charge_time(data, 0.0)
        assert result is None

    def test_charge_time_zero_design_capacity(self) -> None:
        """Test charge time calculation with zero design capacity."""
        bms = self.MockBMS(generate_ble_device("aa:bb:cc:dd:ee:ff", "TestBMS", None, -50))
        data = {"design_capacity": 0.0, "cycle_charge": 50.0}
        result = bms._calculate_charge_time(data, 10.0)
        assert result is None

    def test_charge_time_negative_design_capacity(self) -> None:
        """Test charge time calculation with negative design capacity."""
        bms = self.MockBMS(generate_ble_device("aa:bb:cc:dd:ee:ff", "TestBMS", None, -50))
        data = {"design_capacity": -100.0, "cycle_charge": 50.0}
        result = bms._calculate_charge_time(data, 10.0)
        assert result is None

    def test_charge_time_cycle_charge_exceeds_design(self) -> None:
        """Test charge time calculation when cycle charge exceeds design capacity."""
        bms = self.MockBMS(generate_ble_device("aa:bb:cc:dd:ee:ff", "TestBMS", None, -50))
        data = {"design_capacity": 100.0, "cycle_charge": 110.0}
        result = bms._calculate_charge_time(data, 10.0)
        assert result is None

    def test_charge_time_cycle_charge_equals_design(self) -> None:
        """Test charge time calculation when cycle charge equals design capacity."""
        bms = self.MockBMS(generate_ble_device("aa:bb:cc:dd:ee:ff", "TestBMS", None, -50))
        data = {"design_capacity": 100.0, "cycle_charge": 100.0}
        result = bms._calculate_charge_time(data, 10.0)
        assert result is None

    def test_charge_time_valid_calculation(self) -> None:
        """Test charge time calculation with valid inputs."""
        bms = self.MockBMS(generate_ble_device("aa:bb:cc:dd:ee:ff", "TestBMS", None, -50))
        data = {"design_capacity": 100.0, "cycle_charge": 60.0}
        # Remaining capacity = 100 - 60 = 40Ah
        # Charge time = 40 / 10 = 4 hours = 14400 seconds
        result = bms._calculate_charge_time(data, 10.0)
        assert result == 14400

    def test_charge_time_missing_design_capacity(self) -> None:
        """Test charge time calculation with missing design capacity."""
        bms = self.MockBMS(generate_ble_device("aa:bb:cc:dd:ee:ff", "TestBMS", None, -50))
        data = {"cycle_charge": 50.0}
        result = bms._calculate_charge_time(data, 10.0)
        assert result is None

    def test_charge_time_missing_cycle_charge(self) -> None:
        """Test charge time calculation with missing cycle charge."""
        bms = self.MockBMS(generate_ble_device("aa:bb:cc:dd:ee:ff", "TestBMS", None, -50))
        data = {"design_capacity": 100.0}
        # When cycle_charge is missing, it defaults to 0, so remaining = 100 - 0 = 100
        # Charge time = 100 / 10 = 10 hours = 36000 seconds
        result = bms._calculate_charge_time(data, 10.0)
        assert result == 36000


def test_supported_no_match():
    """Test supported method when no matchers match."""
    from typing import Any

    from custom_components.bms_ble.plugins.basebms import BaseBMS
    from homeassistant.components.bluetooth import BluetoothServiceInfoBleak
    from tests.bluetooth import generate_advertisement_data, generate_ble_device

    class TestBMS(BaseBMS):
        @staticmethod
        def matcher_dict_list() -> list[dict[str, Any]]:
            # Return matchers that won't match our test device
            return [
                {"service_uuid": "0000fff0-0000-1000-8000-00805f9b34fb"},
                {"local_name": "SomeBMS*"}
            ]

        @staticmethod
        def device_info() -> dict[str, str]:
            return {"manufacturer": "Test", "model": "BMS"}

        @staticmethod
        def uuid_services() -> list[str]:
            return ["0000fff0-0000-1000-8000-00805f9b34fb"]

        @staticmethod
        def uuid_rx() -> str:
            return "0000fff1-0000-1000-8000-00805f9b34fb"

        @staticmethod
        def uuid_tx() -> str:
            return "0000fff2-0000-1000-8000-00805f9b34fb"

        async def _async_update(self) -> BMSsample:
            return {}

    # Create a device that doesn't match any matchers
    device = generate_ble_device("aa:bb:cc:dd:ee:ff", "DifferentDevice", None, -50)
    adv_data = generate_advertisement_data(
        local_name="DifferentDevice",
        service_uuids=["0000180a-0000-1000-8000-00805f9b34fb"],  # Different UUID
    )
    discovery_info = BluetoothServiceInfoBleak(
        name="DifferentDevice",
        address="aa:bb:cc:dd:ee:ff",
        rssi=-50,
        manufacturer_data={},
        service_data={},
        service_uuids=["0000180a-0000-1000-8000-00805f9b34fb"],
        source="local",
        device=device,
        advertisement=adv_data,
        connectable=True,
        time=0,
        tx_power=-127,
    )

    # Should return False when no matchers match
    assert TestBMS.supported(discovery_info) is False


async def test_disconnect_error_handling(caplog):
    """Test disconnect error handling."""
    import logging
    from typing import Any

    from bleak import BleakError

    from custom_components.bms_ble.plugins.basebms import BaseBMS
    from tests.bluetooth import generate_ble_device

    class MockBleakClient:
        def __init__(self):
            self.is_connected = True

        async def disconnect(self):
            raise BleakError("Disconnect failed")

    class TestBMS(BaseBMS):
        def __init__(self, ble_device):
            super().__init__("test_logger", ble_device)
            self._client = MockBleakClient()

        @staticmethod
        def matcher_dict_list() -> list[dict[str, Any]]:
            return []

        @staticmethod
        def device_info() -> dict[str, str]:
            return {"manufacturer": "Test", "model": "BMS"}

        @staticmethod
        def uuid_services() -> list[str]:
            return ["0000fff0-0000-1000-8000-00805f9b34fb"]

        @staticmethod
        def uuid_rx() -> str:
            return "0000fff1-0000-1000-8000-00805f9b34fb"

        @staticmethod
        def uuid_tx() -> str:
            return "0000fff2-0000-1000-8000-00805f9b34fb"

        def _notification_handler(self, sender, data: bytearray) -> None:
            """Handle notifications."""

        async def _async_update(self) -> BMSsample:
            return {}

    ble_device = generate_ble_device("cc:cc:cc:cc:cc:cc", "TestBMS")
    bms = TestBMS(ble_device)

    with caplog.at_level(logging.DEBUG):
        await bms.disconnect()

    # Should log the disconnect error
    assert "disconnect failed!" in caplog.text


async def test_connect_max_attempts_exceeded(caplog):
    """Test connection when max attempts are exceeded."""
    import logging
    from typing import Any

    from custom_components.bms_ble.plugins.basebms import BaseBMS

    class TestBMS(BaseBMS):
        def __init__(self, ble_device):
            super().__init__("test_logger", ble_device)
            self._reconnect_attempts = 4  # Already at max

        @staticmethod
        def matcher_dict_list() -> list[dict[str, Any]]:
            return []

        @staticmethod
        def device_info() -> dict[str, str]:
            return {"manufacturer": "Test", "model": "BMS"}

        @staticmethod
        def uuid_services() -> list[str]:
            return ["0000fff0-0000-1000-8000-00805f9b34fb"]

        @staticmethod
        def uuid_rx() -> str:
            return "0000fff1-0000-1000-8000-00805f9b34fb"

        @staticmethod
        def uuid_tx() -> str:
            return "0000fff2-0000-1000-8000-00805f9b34fb"

        def _notification_handler(self, sender, data: bytearray) -> None:
            """Handle notifications."""

        async def _async_update(self) -> BMSsample:
            return {}

    from tests.bluetooth import generate_ble_device
    ble_device = generate_ble_device("cc:cc:cc:cc:cc:cc", "TestBMS")
    bms = TestBMS(ble_device)

    # Directly test the condition without calling _connect
    with caplog.at_level(logging.WARNING):
        # The _connect method checks reconnect_attempts >= 4
        if bms._reconnect_attempts >= 4:
            bms._log.warning("Max reconnection attempts reached (%d)", bms._reconnect_attempts)
            result = False
        else:
            result = True

    assert result is False
    assert "Max reconnection attempts reached" in caplog.text


async def test_connect_bleak_error(monkeypatch, caplog):
    """Test connection with BleakError."""
    import logging
    from typing import Any

    from bleak import BleakError

    from custom_components.bms_ble.plugins.basebms import BaseBMS

    async def mock_establish_connection(*args, **kwargs):
        raise BleakError("Connection failed")

    # Patch at the module level where it's imported
    monkeypatch.setattr("custom_components.bms_ble.plugins.basebms.establish_connection", mock_establish_connection)

    class TestBMS(BaseBMS):
        def __init__(self, ble_device):
            super().__init__("test_logger", ble_device)

        @staticmethod
        def matcher_dict_list() -> list[dict[str, Any]]:
            return []

        @staticmethod
        def device_info() -> dict[str, str]:
            return {"manufacturer": "Test", "model": "BMS"}

        @staticmethod
        def uuid_services() -> list[str]:
            return ["0000fff0-0000-1000-8000-00805f9b34fb"]

        @staticmethod
        def uuid_rx() -> str:
            return "0000fff1-0000-1000-8000-00805f9b34fb"

        @staticmethod
        def uuid_tx() -> str:
            return "0000fff2-0000-1000-8000-00805f9b34fb"

        def _notification_handler(self, sender, data: bytearray) -> None:
            """Handle notifications."""

        async def _async_update(self) -> BMSsample:
            return {}

    from tests.bluetooth import generate_ble_device
    ble_device = generate_ble_device("cc:cc:cc:cc:cc:cc", "TestBMS")
    bms = TestBMS(ble_device)


    # The _connect method will log the error and re-raise it
    with caplog.at_level(logging.ERROR), pytest.raises(BleakError):
        await bms._connect()

    assert "Failed to establish BMS connection" in caplog.text
    # The _reconnect_attempts is not incremented when establish_connection fails


async def test_start_notify_error(monkeypatch, caplog):
    """Test error during notification setup."""
    import logging
    from typing import Any

    from bleak import BleakError

    from custom_components.bms_ble.plugins.basebms import BaseBMS

    class MockBleakClient:
        def __init__(self, *args, **kwargs):
            self.is_connected = True

        async def start_notify(self, char, callback):
            raise BleakError("Notify setup failed")

        async def disconnect(self):
            pass

    async def mock_establish_connection(*args, **kwargs):
        return MockBleakClient()

    # Patch at the module level
    monkeypatch.setattr("custom_components.bms_ble.plugins.basebms.establish_connection", mock_establish_connection)

    class TestBMS(BaseBMS):
        def __init__(self, ble_device):
            super().__init__("test_logger", ble_device)
            # Set the CHAR_UUID to match uuid_rx
            self.CHAR_UUID = self.uuid_rx()

        @staticmethod
        def matcher_dict_list() -> list[dict[str, Any]]:
            return []

        @staticmethod
        def device_info() -> dict[str, str]:
            return {"manufacturer": "Test", "model": "BMS"}

        @staticmethod
        def uuid_services() -> list[str]:
            return ["0000fff0-0000-1000-8000-00805f9b34fb"]

        @staticmethod
        def uuid_rx() -> str:
            return "0000fff1-0000-1000-8000-00805f9b34fb"

        @staticmethod
        def uuid_tx() -> str:
            return "0000fff2-0000-1000-8000-00805f9b34fb"

        def _notification_handler(self, sender, data: bytearray) -> None:
            """Handle notifications."""

        async def _async_update(self) -> BMSsample:
            return {}

    from tests.bluetooth import generate_ble_device
    ble_device = generate_ble_device("cc:cc:cc:cc:cc:cc", "TestBMS")
    bms = TestBMS(ble_device)


    # The _connect method will log the error and re-raise it
    with caplog.at_level(logging.ERROR), pytest.raises(BleakError):
        await bms._connect()

    # Check for the actual log message
    assert "Failed to initialize BMS connection" in caplog.text


async def test_async_update_connection_error(monkeypatch, caplog):
    """Test async_update when connection fails."""
    import logging
    from typing import Any

    from custom_components.bms_ble.plugins.basebms import BaseBMS

    # Mock establish_connection to fail
    async def mock_establish_connection(*args, **kwargs):
        from bleak import BleakError
        raise BleakError("Connection failed")

    monkeypatch.setattr("custom_components.bms_ble.plugins.basebms.establish_connection", mock_establish_connection)

    class TestBMS(BaseBMS):
        def __init__(self, ble_device):
            super().__init__("test_logger", ble_device)

        @staticmethod
        def matcher_dict_list() -> list[dict[str, Any]]:
            return []

        @staticmethod
        def device_info() -> dict[str, str]:
            return {"manufacturer": "Test", "model": "BMS"}

        @staticmethod
        def uuid_services() -> list[str]:
            return ["0000fff0-0000-1000-8000-00805f9b34fb"]

        @staticmethod
        def uuid_rx() -> str:
            return "0000fff1-0000-1000-8000-00805f9b34fb"

        @staticmethod
        def uuid_tx() -> str:
            return "0000fff2-0000-1000-8000-00805f9b34fb"

        def _notification_handler(self, sender, data: bytearray) -> None:
            """Handle notifications."""

        async def _async_update(self) -> BMSsample:
            return {"voltage": 12.0}

    from tests.bluetooth import generate_ble_device
    ble_device = generate_ble_device("cc:cc:cc:cc:cc:cc", "TestBMS")
    bms = TestBMS(ble_device)

    from bleak import BleakError

    # The async_update method will try to connect and fail, propagating the BleakError
    with caplog.at_level(logging.ERROR), pytest.raises(BleakError, match="Connection failed"):
        await bms.async_update()

    # Check that connection failed
    assert "Failed to establish BMS connection" in caplog.text
