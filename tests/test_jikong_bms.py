"""Test the Jikong BMS implementation."""

from collections.abc import Buffer
from uuid import UUID

from bleak.backends.characteristic import BleakGATTCharacteristic
from bleak.backends.descriptor import BleakGATTDescriptor
from bleak.backends.service import BleakGATTService, BleakGATTServiceCollection
from bleak.exc import BleakError
from bleak.uuids import normalize_uuid_str, uuidstr_to_str
from custom_components.bms_ble.plugins.jikong_bms import BMS
import pytest

from .bluetooth import generate_ble_device
from .conftest import MockBleakClient

BT_FRAME_SIZE = 29


class MockJikongBleakClient(MockBleakClient):
    """Emulate a Jikong BMS BleakClient."""

    HEAD_CMD = bytearray(b"\xAA\x55\x90\xEB")
    CMD_INFO = bytearray(b"\x96")

    def _response(
        self, char_specifier: BleakGATTCharacteristic | int | str | UUID, data: Buffer
    ) -> bytearray:
        if (
            char_specifier == 3
            and bytearray(data)[0:5] == self.HEAD_CMD + self.CMD_INFO
        ):
            return bytearray(
                b"\x41\x54\x0d\x0a"  # added AT\r\n command
                b"\x55\xaa\xeb\x90\x02\xc6\xc1\x0c\xc1\x0c\xc1\x0c\xc1\x0c\xc1\x0c\xc1\x0c"
                b"\xc1\x0c\xc1\x0c\xc1\x0c\xc1\x0c\xc1\x0c\xc1\x0c\xc1\x0c\xc1\x0c\xc1\x0c"
                b"\xc1\x0c\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00"
                b"\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\xff\xff"
                b"\x00\x00\xc1\x0c\x02\x00\x00\x07\x3a\x00\x3c\x00\x46\x00\x48\x00\x54\x00"
                b"\x5c\x00\x69\x00\x76\x00\x7d\x00\x76\x00\x6c\x00\x69\x00\x61\x00\x4b\x00"
                b"\x47\x00\x3c\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00"
                b"\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00"
                b"\xb8\x00\x00\x00\x00\x00\x0a\xcc\x00\x00\xcd\x71\x08\x00\x9d\xd6\xff\xff"
                b"\xb5\x00\xb6\x00\x00\x00\x00\x00\x00\x00\x00\x2a\x47\xcb\x01\x00\xc0\x45"
                b"\x04\x00\x02\x00\x00\x00\x15\xb7\x08\x00\x64\x00\x00\x00\x6b\xc7\x06\x00"
                b"\x01\x01\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\xff\x00"
                b"\x01\x00\x00\x00\xb2\x03\x00\x00\x1c\x00\x54\x29\x40\x40\x00\x00\x00\x00"
                b"\x67\x14\x00\x00\x00\x01\x01\x01\x00\x06\x00\x00\xf3\x48\x2e\x00\x00\x00"
                b"\x00\x00\xb8\x00\xb4\x00\xb7\x00\xb2\x03\xde\xe4\x5b\x08\x2c\x00\x00\x00"
                b"\x80\x51\x01\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\xfe"
                b"\xff\x7f\xdc\x2f\x01\x01\xb0\x07\x00\x00\x00\xd0"
            )  # {"temperature": 18.4, "voltage": 52.234, "current": -10.595, "battery_level": 42, "cycle_charge": 117.575, "cycles": 2}

        return bytearray()

    async def write_gatt_char(
        self,
        char_specifier: BleakGATTCharacteristic | int | str | UUID,
        data: Buffer,
        response: bool = None,  # type: ignore[implicit-optional] # noqa: RUF013 # same as upstream
    ) -> None:
        """Issue write command to GATT."""

        assert (
            self._notify_callback
        ), "write to characteristics but notification not enabled"
        self._notify_callback(
            "MockJikongBleakClient", bytearray(b"\x41\x54\x0d\x0a")
        )  # interleaved AT\r\n command
        resp = self._response(char_specifier, data)
        for notify_data in [
            resp[i : i + BT_FRAME_SIZE] for i in range(0, len(resp), BT_FRAME_SIZE)
        ]:
            self._notify_callback("MockJikongBleakClient", notify_data)

    class JKservice(BleakGATTService):
        """Mock the main battery info service from JiKong BMS."""

        class CharBase(BleakGATTCharacteristic):
            """Basic characteristic for common properties.

            Note that Jikong BMS has two characteristics with same UUID!
            """

            @property
            def service_handle(self) -> int:
                """The integer handle of the Service containing this characteristic."""
                return 0

            @property
            def handle(self) -> int:
                """The handle for this characteristic."""
                return 3

            @property
            def service_uuid(self) -> str:
                """The UUID of the Service containing this characteristic."""
                return normalize_uuid_str("ffe0")

            @property
            def uuid(self) -> str:
                """The UUID for this characteristic."""
                return normalize_uuid_str("ffe1")

            @property
            def descriptors(self) -> list[BleakGATTDescriptor]:
                """List of descriptors for this service."""
                return []

            def get_descriptor(
                self, specifier: int | str | UUID
            ) -> BleakGATTDescriptor | None:
                """Get a descriptor by handle (int) or UUID (str or uuid.UUID)."""
                raise NotImplementedError

            def add_descriptor(self, descriptor: BleakGATTDescriptor) -> None:
                """Add a :py:class:`~BleakGATTDescriptor` to the characteristic.

                Should not be used by end user, but rather by `bleak` itself.
                """
                raise NotImplementedError

        class CharNotify(CharBase):
            """Characteristic for notifications."""

            @property
            def properties(self) -> list[str]:
                """Properties of this characteristic."""
                return ["notify"]

        class CharWrite(CharBase):
            """Characteristic for writing."""

            @property
            def properties(self) -> list[str]:
                """Properties of this characteristic."""
                return ["write", "write-without-response"]

        class CharFaulty(CharBase):
            """Characteristic for writing."""

            @property
            def uuid(self) -> str:
                """The UUID for this characteristic."""
                return normalize_uuid_str("0000")

            @property
            def properties(self) -> list[str]:
                """Properties of this characteristic."""
                return ["write", "write-without-response"]

        @property
        def handle(self) -> int:
            """The handle of this service."""

            return 2

        @property
        def uuid(self) -> str:
            """The UUID to this service."""

            return normalize_uuid_str("ffe0")

        @property
        def description(self) -> str:
            """String description for this service."""

            return uuidstr_to_str(self.uuid)

        @property
        def characteristics(self) -> list[BleakGATTCharacteristic]:
            """List of characteristics for this service."""

            return [
                self.CharNotify(None, lambda: 350),
                self.CharWrite(None, lambda: 350),
                self.CharFaulty(None, lambda: 350), # leave last!
            ]

        def add_characteristic(self, characteristic: BleakGATTCharacteristic) -> None:
            """Add a :py:class:`~BleakGATTCharacteristic` to the service.

            Should not be used by end user, but rather by `bleak` itself.
            """
            raise NotImplementedError

    @property
    def services(self) -> BleakGATTServiceCollection:
        """Emulate JiKong BT service setup."""

        ServCol = BleakGATTServiceCollection()
        ServCol.add_service(self.JKservice(None))

        return ServCol


class MockWrongBleakClient(MockBleakClient):
    """Mock invalid service for JiKong BMS."""

    @property
    def services(self) -> BleakGATTServiceCollection:
        """Emulate JiKong BT service setup."""

        return BleakGATTServiceCollection()


class MockInvalidBleakClient(MockJikongBleakClient):
    """Emulate a Jikong BMS BleakClient returning wrong data."""

    def _response(
        self, char_specifier: BleakGATTCharacteristic | int | str | UUID, data: Buffer
    ) -> bytearray:
        if char_specifier == 3:
            return bytearray(b"\x55\xaa\xeb\x90\x02") + bytearray(295)

        return bytearray()

    async def disconnect(self) -> bool:
        """Mock disconnect to raise BleakError."""
        raise BleakError


class MockOversizedBleakClient(MockJikongBleakClient):
    """Emulate a Jikong BMS BleakClient returning wrong data length."""

    def _response(
        self, char_specifier: BleakGATTCharacteristic | int | str | UUID, data: Buffer
    ) -> bytearray:
        if char_specifier == 3:
            return bytearray(
                b"\x55\xaa\xeb\x90\x02\xc6\xc1\x0c\xc1\x0c\xc1\x0c\xc1\x0c\xc1\x0c\xc1\x0c"
                b"\xc1\x0c\xc1\x0c\xc1\x0c\xc1\x0c\xc1\x0c\xc1\x0c\xc1\x0c\xc1\x0c\xc1\x0c"
                b"\xc1\x0c\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00"
                b"\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\xff\xff"
                b"\x00\x00\xc1\x0c\x02\x00\x00\x07\x3a\x00\x3c\x00\x46\x00\x48\x00\x54\x00"
                b"\x5c\x00\x69\x00\x76\x00\x7d\x00\x76\x00\x6c\x00\x69\x00\x61\x00\x4b\x00"
                b"\x47\x00\x3c\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00"
                b"\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00"
                b"\xb8\x00\x00\x00\x00\x00\x0a\xcc\x00\x00\xcd\x71\x08\x00\x9d\xd6\xff\xff"
                b"\xb5\x00\xb6\x00\x00\x00\x00\x00\x00\x00\x00\x2a\x47\xcb\x01\x00\xc0\x45"
                b"\x04\x00\x02\x00\x00\x00\x15\xb7\x08\x00\x64\x00\x00\x00\x6b\xc7\x06\x00"
                b"\x01\x01\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\xff\x00"
                b"\x01\x00\x00\x00\xb2\x03\x00\x00\x1c\x00\x54\x29\x40\x40\x00\x00\x00\x00"
                b"\x67\x14\x00\x00\x00\x01\x01\x01\x00\x06\x00\x00\xf3\x48\x2e\x00\x00\x00"
                b"\x00\x00\xb8\x00\xb4\x00\xb7\x00\xb2\x03\xde\xe4\x5b\x08\x2c\x00\x00\x00"
                b"\x80\x51\x01\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\xfe"
                b"\xff\x7f\xdc\x2f\x01\x01\xb0\x07\x00\x00\x00\xd0"
                b"\00\00\00\00\00\00"  # oversized response
            )  # {"temperature": 18.4, "voltage": 52.234, "current": -10.595, "battery_level": 42, "cycle_charge": 117.575, "cycles": 2}

        return bytearray()

    async def disconnect(self) -> bool:
        """Mock disconnect to raise BleakError."""
        raise BleakError


async def test_update(monkeypatch, reconnect_fixture) -> None:
    """Test Jikong BMS data update."""

    monkeypatch.setattr(
        "custom_components.bms_ble.plugins.jikong_bms.BleakClient",
        MockJikongBleakClient,
    )

    bms = BMS(
        generate_ble_device("cc:cc:cc:cc:cc:cc", "MockBLEdevice", None, -73),
        reconnect_fixture,
    )

    result = await bms.async_update()

    assert result == {
        "cell_count": 16,
        "delta_voltage": 0.002,
        "temperature": 18.233,
        "voltage": 52.234,
        "current": -10.595,
        "battery_level": 42,
        "cycle_charge": 117.575,
        "cycles": 2,
        "cell#0": 3.265,
        "cell#1": 3.265,
        "cell#2": 3.265,
        "cell#3": 3.265,
        "cell#4": 3.265,
        "cell#5": 3.265,
        "cell#6": 3.265,
        "cell#7": 3.265,
        "cell#8": 3.265,
        "cell#9": 3.265,
        "cell#10": 3.265,
        "cell#11": 3.265,
        "cell#12": 3.265,
        "cell#13": 3.265,
        "cell#14": 3.265,
        "cell#15": 3.265,
        "cycle_capacity": 6141.413,
        "power": -553.419,
        "battery_charging": False,
        "runtime": 39949,
        "temp#0": 18.4,
        "temp#1": 18.1,
        "temp#2": 18.2,
        "temp#3": 18.4,
        "temp#4": 18.0,
        "temp#5": 18.3,
    }

    # query again to check already connected state
    result = await bms.async_update()
    assert (
        bms._client and bms._client.is_connected is not reconnect_fixture
    )  # noqa: SLF001

    await bms.disconnect()


async def test_invalid_response(monkeypatch) -> None:
    """Test data update with BMS returning invalid data."""

    monkeypatch.setattr(
        "custom_components.bms_ble.plugins.jikong_bms.BleakClient",
        MockInvalidBleakClient,
    )

    bms = BMS(generate_ble_device("cc:cc:cc:cc:cc:cc", "MockBLEdevice", None, -73))

    result = await bms.async_update()

    assert result == {}

    await bms.disconnect()


async def test_oversized_response(monkeypatch) -> None:
    """Test data update with BMS returning oversized data, result shall still be ok."""

    monkeypatch.setattr(
        "custom_components.bms_ble.plugins.jikong_bms.BleakClient",
        MockOversizedBleakClient,
    )

    bms = BMS(generate_ble_device("cc:cc:cc:cc:cc:cc", "MockBLEdevice", None, -73))

    result = await bms.async_update()

    assert result == {
        "cell_count": 16,
        "delta_voltage": 0.002,
        "temperature": 18.233,
        "voltage": 52.234,
        "current": -10.595,
        "battery_level": 42,
        "cycle_charge": 117.575,
        "cycles": 2,
        "cell#0": 3.265,
        "cell#1": 3.265,
        "cell#2": 3.265,
        "cell#3": 3.265,
        "cell#4": 3.265,
        "cell#5": 3.265,
        "cell#6": 3.265,
        "cell#7": 3.265,
        "cell#8": 3.265,
        "cell#9": 3.265,
        "cell#10": 3.265,
        "cell#11": 3.265,
        "cell#12": 3.265,
        "cell#13": 3.265,
        "cell#14": 3.265,
        "cell#15": 3.265,
        "cycle_capacity": 6141.413,
        "power": -553.419,
        "battery_charging": False,
        "runtime": 39949,
        "temp#0": 18.4,
        "temp#1": 18.1,
        "temp#2": 18.2,
        "temp#3": 18.4,
        "temp#4": 18.0,
        "temp#5": 18.3,        
    }

    await bms.disconnect()


async def test_invalid_device(monkeypatch) -> None:
    """Test data update with BMS returning invalid data."""

    monkeypatch.setattr(
        "custom_components.bms_ble.plugins.jikong_bms.BleakClient",
        MockWrongBleakClient,
    )

    bms = BMS(generate_ble_device("cc:cc:cc:cc:cc:cc", "MockBLEdevice", None, -73))

    result = {}

    with pytest.raises(
        ConnectionError, match=r"^Failed to detect characteristics from.*"
    ):
        result = await bms.async_update()

    assert result == {}

    await bms.disconnect()
