"""Test the Jikong BMS implementation."""

import asyncio
from collections.abc import Buffer
from typing import Final
from uuid import UUID

from bleak.backends.characteristic import BleakGATTCharacteristic
from bleak.backends.descriptor import BleakGATTDescriptor
from bleak.backends.service import BleakGATTService, BleakGATTServiceCollection
from bleak.exc import BleakError
from bleak.uuids import normalize_uuid_str, uuidstr_to_str
import pytest

from custom_components.bms_ble.plugins.jikong_bms import BMS

from .bluetooth import generate_ble_device
from .conftest import MockBleakClient

BT_FRAME_SIZE = 29


class MockJikongBleakClient(MockBleakClient):
    """Emulate a Jikong BMS BleakClient."""

    HEAD_CMD: Final = bytearray(b"\xAA\x55\x90\xEB")
    CMD_INFO: Final = bytearray(b"\x96")
    DEV_INFO: Final = bytearray(b"\x97")

    CEL_FRAME: Final = bytearray(  # JK02_24S (SW: 10.08)
        b"\x55\xaa\xeb\x90\x02\xc8\xee\x0c\xf2\x0c\xf1\x0c\xf0\x0c\xf0\x0c\xec\x0c\xf0\x0c\xed\x0c"
        b"\xed\x0c\xed\x0c\xed\x0c\xf0\x0c\xf1\x0c\xed\x0c\xee\x0c\xed\x0c\x00\x00\x00\x00\x00\x00"
        b"\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\xff\xff\x00\x00\xef\x0c\x05\x00\x01\x09\x36\x00"
        b"\x37\x00\x39\x00\x38\x00\x37\x00\x37\x00\x35\x00\x41\x00\x42\x00\x36\x00\x37\x00\x3a\x00"
        b"\x38\x00\x34\x00\x36\x00\x37\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00"
        b"\x00\x00\x00\x00\x00\x00\x00\x00\xeb\xce\x00\x00\xc7\x0d\x02\x00\x19\x09\x00\x00\xb5\x00"
        b"\xba\x00\xe4\x00\x00\x00\x00\x00\x00\x38\x5d\xba\x01\x00\x10\x15\x03\x00\x3c\x00\x00\x00"
        b"\xa4\x65\xb9\x00\x64\x00\xd9\x02\x8b\xe8\x6c\x03\x01\x01\xb3\x06\x00\x00\x00\x00\x00\x00"
        b"\x00\x00\x00\x00\x00\x00\x07\x00\x01\x00\x00\x00\x23\x04\x0b\x00\x00\x00\x9f\x19\x40\x40"
        b"\x00\x00\x00\x00\xe2\x04\x00\x00\x00\x00\x00\x01\x00\x03\x00\x00\x83\xd5\x37\x00\x00\x00"
        b"\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00"
        b"\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00"
        b"\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00"
        b"\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\xbb"
    )

    DEV_FRAME: Final = bytearray(  # JK02_24S (SW: 10.08)
        b"\x55\xaa\xeb\x90\x03\x79\x4a\x4b\x2d\x42\x32\x41\x32\x30\x53\x32\x30\x50\x00\x00\x00\x00"
        b"\x31\x30\x2e\x58\x47\x00\x00\x00\x31\x30\x2e\x30\x38\x00\x00\x00\xe4\xe7\x6c\x03\x11\x00"
        b"\x00\x00\x4a\x4b\x2d\x42\x4d\x53\x2d\x41\x00\x00\x00\x00\x00\x00\x00\x00\x31\x32\x33\x34"
        b"\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x32\x32\x30\x37\x30\x31\x00\x00\x32\x30"
        b"\x33\x32\x38\x31\x36\x30\x31\x32\x00\x30\x30\x30\x30\x00\x4d\x61\x72\x69\x6f\x00\x00\x00"
        b"\x00\x00\x00\x00\x00\x61\x00\x00\x31\x32\x33\x34\x35\x36\x00\x00\x00\x00\x00\x00\x00\x00"
        b"\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00"
        b"\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00"
        b"\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00"
        b"\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00"
        b"\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00"
        b"\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00"
        b"\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00"
        b"\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x93"
    )

    # CEL_FRAME: Final = bytearray( # JK02_32 (SW: V11.48)
    #     b"\x55\xaa\xeb\x90\x02\xc6\xc1\x0c\xc1\x0c\xc1\x0c\xc1\x0c\xc1\x0c\xc1\x0c\xc1\x0c\xc1\x0c"
    #     b"\xc1\x0c\xc1\x0c\xc1\x0c\xc1\x0c\xc1\x0c\xc1\x0c\xc1\x0c\xc1\x0c\x00\x00\x00\x00\x00\x00"
    #     b"\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00"
    #     b"\x00\x00\x00\x00\xff\xff\x00\x00\xc1\x0c\x02\x00\x00\x07\x3a\x00\x3c\x00\x46\x00\x48\x00"
    #     b"\x54\x00\x5c\x00\x69\x00\x76\x00\x7d\x00\x76\x00\x6c\x00\x69\x00\x61\x00\x4b\x00\x47\x00"
    #     b"\x3c\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00"
    #     b"\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\xb8\x00\x00\x00\x00\x00\x0a\xcc\x00\x00"
    #     b"\xcd\x71\x08\x00\x9d\xd6\xff\xff\xb5\x00\xb6\x00\x00\x00\x00\x00\x00\x00\x00\x2a\x47\xcb"
    #     b"\x01\x00\xc0\x45\x04\x00\x02\x00\x00\x00\x15\xb7\x08\x00\x64\x00\x00\x00\x6b\xc7\x06\x00"
    #     b"\x01\x01\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\xff\x00\x01\x00\x00\x00"
    #     b"\xb2\x03\x00\x00\x1c\x00\x54\x29\x40\x40\x00\x00\x00\x00\x67\x14\x00\x00\x00\x01\x01\x01"
    #     b"\x00\x06\x00\x00\xf3\x48\x2e\x00\x00\x00\x00\x00\xb8\x00\xb4\x00\xb7\x00\xb2\x03\xde\xe4"
    #     b"\x5b\x08\x2c\x00\x00\x00\x80\x51\x01\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00"
    #     b"\x00\xfe\xff\x7f\xdc\x2f\x01\x01\xb0\x07\x00\x00\x00\xd0"
    # )  # {"temperature": 18.4, "voltage": 52.234, "current": -10.595, "battery_level": 42, "cycle_charge": 117.575, "cycles": 2}

    # DEV_FRAME: Final = bytearray(
    #     b"\x55\xaa\xeb\x90\x03\xa3\x4a\x4b\x5f\x42\x32\x41\x38\x53\x32\x30\x50\x00\x00\x00\x00\x00"
    #     b"\x31\x31\x2e\x58\x41\x00\x00\x00\x31\x31\x2e\x34\x38\x00\x00\x00\xe4\xa7\x46\x00\x07\x00"
    #     b"\x00\x00\x31\x32\x76\x34\x32\x30\x61\x00\x00\x00\x00\x00\x00\x00\x00\x00\x31\x32\x33\x34"
    #     b"\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x32\x34\x30\x37\x30\x34\x00\x00\x34\x30"
    #     b"\x34\x30\x39\x32\x43\x32\x32\x36\x32\x00\x30\x30\x30\x00\x49\x6e\x70\x75\x74\x20\x55\x73"
    #     b"\x65\x72\x64\x61\x74\x61\x00\x00\x31\x34\x30\x37\x30\x33\x00\x00\x00\x00\x00\x00\x00\x00"
    #     b"\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\xfe\xf9\xff\xff"
    #     b"\x1f\x2d\x00\x02\x00\x00\x00\x00\x90\x1f\x00\x00\x00\x00\xc0\xd8\xe7\x32\x00\x00\x00\x01"
    #     b"\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x07\x04\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00"
    #     b"\x00\x00\x00\x00\x41\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00"
    #     b"\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x09\x00\x00\x00\x64\x00\x00\x00"
    #     b"\x5f\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00"
    #     b"\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00"
    #     b"\x00\xfe\xbf\x21\x06\x00\x00\x00\x00\x00\x00\x00\x00\xd8"
    # )  # Vendor_ID: JK_B2A8S20P, SN: 404092C2262, HW: V11.XA, SW: V11.48, power-on: 7, Version: 4.28.0
    ACK_FRAME: Final = bytearray(
        b"\xaa\x55\x90\xeb\xc8\x01\x01\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x44"
    )
    _task: asyncio.Task

    def _response(
        self, char_specifier: BleakGATTCharacteristic | int | str | UUID, data: Buffer
    ) -> bytearray:
        if char_specifier != 3:
            return bytearray()
        if bytearray(data)[0:5] == self.HEAD_CMD + self.CMD_INFO:
            return (
                bytearray(b"\x41\x54\x0d\x0a") + self.CEL_FRAME  # added AT\r\n command
            )
        if bytearray(data)[0:5] == self.HEAD_CMD + self.DEV_INFO:
            return self.DEV_FRAME

        return bytearray()

    async def _send_confirm(self):
        assert self._notify_callback, "send confirm called but notification not enabled"
        await asyncio.sleep(0.1)
        self._notify_callback(
            "MockJikongBleakClient",
            b"\xaa\x55\x90\xeb\xc8\x01\x01\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x44",
        )

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
        if (
            bytearray(data)[0:5] == self.HEAD_CMD + self.DEV_INFO
        ):  # JK BMS confirms commands with a command in reply
            self._task = asyncio.create_task(self._send_confirm())

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
                self.CharFaulty(None, lambda: 350),  # leave last!
            ]

        def add_characteristic(self, characteristic: BleakGATTCharacteristic) -> None:
            """Add a :py:class:`~BleakGATTCharacteristic` to the service.

            Should not be used by end user, but rather by `bleak` itself.
            """
            raise NotImplementedError

    @property
    def services(self) -> BleakGATTServiceCollection:
        """Emulate JiKong BT service setup."""

        serv_col = BleakGATTServiceCollection()
        serv_col.add_service(self.JKservice(None))

        return serv_col


class MockStreamBleakClient(MockJikongBleakClient):
    """Mock JiKong BMS that already sends battery data (no request required)."""

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
        if bytearray(data).startswith(
            self.HEAD_CMD + self.DEV_INFO
        ):  # send all responses as a series
            for resp in [self.DEV_FRAME, self.ACK_FRAME, self.CEL_FRAME]:
                self._notify_callback("MockJikongBleakClient", resp)


class MockWrongBleakClient(MockBleakClient):
    """Mock invalid service for JiKong BMS."""

    @property
    def services(self) -> BleakGATTServiceCollection:
        """Emulate JiKong BT service setup."""

        return BleakGATTServiceCollection()


class MockInvalidBleakClient(MockJikongBleakClient):
    """Emulate a Jikong BMS BleakClient with disconnect error."""

    async def disconnect(self) -> bool:
        """Mock disconnect to raise BleakError."""
        raise BleakError


class MockOversizedBleakClient(MockJikongBleakClient):
    """Emulate a Jikong BMS BleakClient returning wrong data length."""

    def _response(
        self, char_specifier: BleakGATTCharacteristic | int | str | UUID, data: Buffer
    ) -> bytearray:
        if char_specifier == 3:
            return self.CEL_FRAME + bytearray(
                b"\00\00\00\00\00\00"
            )  # oversized response

        return bytearray()

    async def disconnect(self) -> bool:
        """Mock disconnect to raise BleakError."""
        raise BleakError


@pytest.mark.asyncio
async def test_update(monkeypatch, reconnect_fixture) -> None:
    """Test Jikong BMS data update."""

    monkeypatch.setattr(
        "custom_components.bms_ble.plugins.basebms.BleakClient",
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
        "temperature": 18.2,
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
        "temp#3": 18.0,
        "temp#4": 18.3,
    }

    # query again to check already connected state
    result = await bms.async_update()
    assert (
        bms._client and bms._client.is_connected is not reconnect_fixture
    )  # noqa: SLF001

    await bms.disconnect()


async def test_stream_update(monkeypatch, reconnect_fixture) -> None:
    """Test Jikong BMS data update."""

    monkeypatch.setattr(
        "custom_components.bms_ble.plugins.basebms.BleakClient",
        MockStreamBleakClient,
    )

    monkeypatch.setattr(  # mock that response has already been received
        "custom_components.bms_ble.plugins.basebms.asyncio.Event.is_set",
        lambda _: True,
    )

    bms = BMS(
        generate_ble_device("cc:cc:cc:cc:cc:cc", "MockBLEdevice", None, -73),
        reconnect_fixture,
    )

    result = await bms.async_update()

    assert result == {
        "cell_count": 16,
        "delta_voltage": 0.002,
        "temperature": 18.2,
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
        "temp#3": 18.0,
        "temp#4": 18.3,
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
        "tests.test_jikong_bms.MockInvalidBleakClient._response",
        lambda _s, _c_, d: bytearray(b"\x55\xaa\xeb\x90\x02")
        + bytearray(295),  # incorrect CRC,
    )

    monkeypatch.setattr(
        "custom_components.bms_ble.plugins.basebms.BleakClient",
        MockInvalidBleakClient,
    )

    bms = BMS(generate_ble_device("cc:cc:cc:cc:cc:cc", "MockBLEdevice", None, -73))

    result = await bms.async_update()

    assert result == {}

    await bms.disconnect()


async def test_invalid_frame_type(monkeypatch) -> None:
    """Test data update with BMS returning invalid data."""

    monkeypatch.setattr(
        "custom_components.bms_ble.plugins.jikong_bms.BAT_TIMEOUT",
        0.1,
    )

    monkeypatch.setattr(
        "tests.test_jikong_bms.MockInvalidBleakClient._response",
        lambda _s, _c_, d: bytearray(b"\x55\xaa\xeb\x90\x05")
        + bytearray(295),  # invalid frame type (0x5)
    )

    monkeypatch.setattr(
        "custom_components.bms_ble.plugins.basebms.BleakClient",
        MockInvalidBleakClient,
    )

    bms = BMS(generate_ble_device("cc:cc:cc:cc:cc:cc", "MockBLEdevice", None, -73))

    result = {}
    with pytest.raises(TimeoutError):
        result = await bms.async_update()
    assert result == {}

    await bms.disconnect()


async def test_oversized_response(monkeypatch) -> None:
    """Test data update with BMS returning oversized data, result shall still be ok."""

    monkeypatch.setattr(
        "custom_components.bms_ble.plugins.basebms.BleakClient",
        MockOversizedBleakClient,
    )

    bms = BMS(generate_ble_device("cc:cc:cc:cc:cc:cc", "MockBLEdevice", None, -73))

    result = await bms.async_update()

    assert result == {
        "cell_count": 16,
        "delta_voltage": 0.002,
        "temperature": 18.2,
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
        "temp#3": 18.0,
        "temp#4": 18.3,
    }

    await bms.disconnect()


async def test_invalid_device(monkeypatch) -> None:
    """Test data update with BMS returning invalid data."""

    monkeypatch.setattr(
        "custom_components.bms_ble.plugins.basebms.BleakClient",
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
