"""Test the Jikong BMS implementation."""

from bleak.backends.characteristic import BleakGATTCharacteristic
from bleak.backends.descriptor import BleakGATTDescriptor
from bleak.backends.service import BleakGATTServiceCollection, BleakGATTService
from bleak.exc import BleakError
from bleak.uuids import normalize_uuid_str, uuidstr_to_str
from custom_components.bms_ble.plugins.jikong_bms import BMS
from typing_extensions import Buffer
from uuid import UUID

from .bluetooth import generate_ble_device
from .conftest import MockBleakClient


class MockJikongBleakClient(MockBleakClient):
    """Emulate a Jikong BMS BleakClient."""

    HEAD_CMD = bytearray(b"\xAA\x55\x90\xEB")
    CMD_INFO = bytearray(b"\x96")

    def _response(
        self, char_specifier: BleakGATTCharacteristic | int | str, data: Buffer
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
                ###
                # b"\x55\xAA\xEB\x90\x02\xE8\xAE\x0C\x9E\x0C\x9A\x0C\x9F\x0C\xA1\x0C\x9F\x0C"
                # b"\xA0\x0C\xA0\x0C\x99\x0C\xA0\x0C\x90\x0C\x99\x0C\xA5\x0C\x9F\x0C\x99\x0C"
                # b"\xAA\x0C\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00"
                # b"\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\xFF\xFF"
                # b"\x00\x00\x9F\x0C\x1F\x00\x00\x0A\x68\x00\x68\x00\x7A\x00\x73\x00\x72\x00"
                # b"\x85\x00\x70\x00\x67\x00\x82\x00\x77\x00\x65\x00\x66\x00\x7E\x00\x78\x00"
                # b"\x74\x00\x9C\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00"
                # b"\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00"
                # b"\xAD\x00\x00\x00\x00\x00\xE9\xC9\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00"
                # b"\xB1\x00\xB1\x00\x00\x00\x00\x00\x00\x00\x00\x34\x13\x04\x00\x00\xD0\x07"
                # b"\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x64\x00\x00\x00\x98\xA3\x01\x00"
                # b"\x01\x01\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\xFF\x00"
                # b"\x01\x00\x00\x00\xE2\x04\x00\x00\x01\x00\xF6\xC7\x40\x40\x00\x00\x00\x00"
                # b"\x30\x14\xFE\x01\x00\x01\x01\x01\x00\x06\x00\x00\x60\x0C\x00\x00\x00\x00"
                # b"\x00\x00\xAD\x00\xB3\x00\xB4\x00\x90\x03\xDA\x26\x9D\x07\x18\x06\x00\x00"
                # b"\x80\x51\x01\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\xFE"
                # b"\xFF\x7F\xDD\x2F\x01\x01\xB0\x07\x00\x00\x00\x16"
            )  # TODO: put reference here!

        return bytearray()

    async def write_gatt_char(
        self,
        char_specifier: BleakGATTCharacteristic | int | str,
        data: Buffer,
        response: bool = None,  # type: ignore[implicit-optional] # same as upstream
    ) -> None:
        """Issue write command to GATT."""
        # await super().write_gatt_char(char_specifier, data, response)
        assert self._notify_callback is not None
        self._notify_callback(
            "MockJikongBleakClient", bytearray(b"\x41\x54\x0d\x0a")
        )  # interleaved AT\r\n command
        resp = self._response(char_specifier, data)
        for notify_data in [resp[i : i + 29] for i in range(0, len(resp), 29)]:
            self._notify_callback("MockJikongBleakClient", notify_data)

    class JKservice(BleakGATTService):

        class CharBase(BleakGATTCharacteristic):
            """Basic characteristic for common properties."""

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

        @property
        def handle(self) -> int:
            """The handle of this service"""
            return 2

        @property
        def uuid(self) -> str:
            """The UUID to this service"""
            return normalize_uuid_str("ffe0")

        @property
        def description(self) -> str:
            """String description for this service"""
            return uuidstr_to_str(self.uuid)

        @property
        def characteristics(self) -> list[BleakGATTCharacteristic]:
            """List of characteristics for this service"""
            return list([self.CharNotify(None, 350), self.CharWrite(None, 350)])

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
    @property
    def services(self) -> BleakGATTServiceCollection:
        """Emulate JiKong BT service setup."""

        ServCol = BleakGATTServiceCollection()

        return ServCol


class MockInvalidBleakClient(MockJikongBleakClient):
    """Emulate a Jikong BMS BleakClient returning wrong data."""

    def _response(
        self, char_specifier: BleakGATTCharacteristic | int | str, data: Buffer
    ) -> bytearray:
        if char_specifier == 3:
            return bytearray(b"\x55\xAA\xEB\x90\x02") + bytearray(295)

        return bytearray()

    async def disconnect(self) -> bool:
        """Mock disconnect to raise BleakError."""
        raise BleakError


class MockOversizedBleakClient(MockJikongBleakClient):
    """Emulate a Jikong BMS BleakClient returning wrong data length."""

    def _response(
        self, char_specifier: BleakGATTCharacteristic | int | str, data: Buffer
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
            )  # TODO: put reference here!

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
        "temperature": 18.4,
        "voltage": 52.234,
        "current": -10.595,
        "battery_level": 42,
        "cycle_charge": 117.575,
        "cycles": 2,
        "cycle_capacity": 6141.41255,
        "power": -553.4192300000001,
        "battery_charging": False,
        "runtime": 39949,
    }

    # query again to check already connected state
    result = await bms.async_update()
    assert bms._connected is not reconnect_fixture

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
        "temperature": 18.4,
        "voltage": 52.234,
        "current": -10.595,
        "battery_level": 42,
        "cycle_charge": 117.575,
        "cycles": 2,
        "cycle_capacity": 6141.41255,
        "power": -553.4192300000001,
        "battery_charging": False,
        "runtime": 39949,        
    }

    await bms.disconnect()


async def test_invalid_device(monkeypatch) -> None:
    """Test data update with BMS returning invalid data."""

    monkeypatch.setattr(
        "custom_components.bms_ble.plugins.jikong_bms.BleakClient",
        MockWrongBleakClient,
    )

    bms = BMS(generate_ble_device("cc:cc:cc:cc:cc:cc", "MockBLEdevice", None, -73))

    result = await bms.async_update()

    assert result == {}

    await bms.disconnect()
