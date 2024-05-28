"""Test the Daly BMS implementation."""

import asyncio
from typing import Union

from bleak.backends.characteristic import BleakGATTCharacteristic
from bleak.exc import BleakError
from bleak.uuids import normalize_uuid_str
from custom_components.bms_ble.plugins.ogt_bms import BMS
from typing_extensions import Buffer

from .bluetooth import generate_ble_device
from .conftest import MockBleakClient, MockRespChar


class MockOGTBleakClient(MockBleakClient):
    """Emulate an OGT BMS BleakClient."""

    KEY = 0x10  # key used for decoding, constants are encrypted with this key!
    RESP_TYPE_A = {
        0x02: bytearray(b" U  \x1d\x1a"),  # battery_level: 14
        0x04: bytearray(b'"  # Q\x1d\x1a'),  # cycle_charge: 8.0
        0x08: bytearray(b"'!R\"\x1d\x1a"),  # voltage: 45.681
        0x0C: bytearray(b"(% R\x1d\x1a"),  # temperature: 21.8
        0x10: bytearray(b"'R  \x1d\x1a"),  # current: 1.23
        0x18: bytearray(b"'(  \x1d\x1a"),  # runtime: 7200
        0x2C: bytearray(b"&#  \x1d\x1a"),  # cycles: 99
    }
    RESP_TYPE_B: dict[int, bytearray] = {
        0x08: bytearray(b"(% R\x1d\x1a"),  # temperature: 21.8
        0x09: bytearray(b"'!R\"\x1d\x1a"),  # voltage: 45.681
        0x0A: bytearray(b"'R   Q\x1d\x1a"),  # current: 1.23
        0x0D: bytearray(b" U  \x1d\x1a"),  # battery_level: 14
        0x0F: bytearray(b'"  # Q\x1d\x1a'),  # cycle_charge: 8.0
        0x12: bytearray(b"'(  \x1d\x1a"),  # runtime: 7200
        0x17: bytearray(b"&#  \x1d\x1a"),  # cycles: 99
    }

    async def _response(
        self, char_specifier: Union[BleakGATTCharacteristic, int, str], data: Buffer
    ) -> bytearray:
        if char_specifier == normalize_uuid_str("fff6"):
            assert self._ble_device.name is not None
            if self._ble_device.name[9] == "A":
                assert bytearray(data)[0:4] == bytearray(
                    b";BQQ"
                ), "BMS type A command header incorrect."
            else:
                assert bytearray(data)[0:4] == bytearray(
                    b";B!&"
                ), "BMS type B command header incorrect."

            reg = int(
                bytearray((bytearray(data)[x] ^ self.KEY) for x in range(4, 6)).decode(
                    encoding="ascii"
                ),
                16,
            )
            assert self._ble_device.name is not None

            if self._ble_device.name[9] == "A" and reg in self.RESP_TYPE_A:
                return bytearray(b";BT<") + bytearray(data)[4:6] + self.RESP_TYPE_A[reg]

            if self._ble_device.name[9] == "B" and reg in self.RESP_TYPE_B:
                return bytearray(b";BT<") + bytearray(data)[4:6] + self.RESP_TYPE_B[reg]

        return bytearray()

    async def write_gatt_char(
        self,
        char_specifier: Union[BleakGATTCharacteristic, int, str],
        data: Buffer,
        response: bool = None,  # type: ignore # same as upstream
    ) -> None:
        """Issue write command to GATT."""
        # await super().write_gatt_char(char_specifier, data, response)
        assert self._notify_callback is not None
        value = await self._response(char_specifier, data)

        asyncio.get_running_loop().call_soon(
            self._notify_callback, MockRespChar(None, 0), value
        )


class MockInvalidBleakClient(MockOGTBleakClient):
    """Emulate an invalid BleakClient."""

    async def _response(
        self, char_specifier: Union[BleakGATTCharacteristic, int, str], data: Buffer
    ) -> bytearray:
        if char_specifier == normalize_uuid_str("fff6"):
            return bytearray(b"invalid_value")

        return bytearray()

    async def write_gatt_char(
        self,
        char_specifier: Union[BleakGATTCharacteristic, int, str],
        data: Buffer,
        response: bool = None,  # type: ignore # same as upstream
    ) -> None:
        """Issue write command to GATT."""
        # await super().write_gatt_char(char_specifier, data, response)
        assert self._notify_callback is not None
        value = await self._response(char_specifier, data)

        # test read timeout on register 8 (valid for A and B type BMS)
        if bytearray(data)[4:6] != bytearray(b" ("):
            self._notify_callback(MockRespChar(None, 0), value)

    async def disconnect(self) -> bool:
        """Mock disconnect to raise BleakError."""
        raise BleakError


async def test_update(monkeypatch, ogt_bms_fixture, reconnect_fixture) -> None:
    """Test OGT BMS data update."""

    monkeypatch.setattr(
        "custom_components.bms_ble.plugins.ogt_bms.BleakClient",
        MockOGTBleakClient,
    )

    bms = BMS(
        generate_ble_device("cc:cc:cc:cc:cc:cc", ogt_bms_fixture, None, -73),
        reconnect_fixture,
    )

    result = await bms.async_update()

    assert len(result) == 10  # verify number of entries
    assert result == {
        "voltage": 45.681,
        "current": 1.23,
        "battery_level": 14,
        "cycles": 99,
        "cycle_charge": 8.0,
        "temperature": 21.8,
        "cycle_capacity": 365.448,
        "power": 56.18763,
        "battery_charging": True,
        "runtime": 7200,
    }  # verify all sensors are reported

    # query again to check already connected state
    result = await bms.async_update()
    assert bms._connected is not reconnect_fixture

    await bms.disconnect()


async def test_invalid_response(monkeypatch) -> None:
    """Test data update with BMS returning invalid data and read timeout."""

    monkeypatch.setattr(
        "custom_components.bms_ble.plugins.ogt_bms.BleakClient",
        MockInvalidBleakClient,
    )

    bms = BMS(generate_ble_device("cc:cc:cc:cc:cc:cc", "SmartBat-A12345", None, -73))

    result = await bms.async_update()
    assert result == {}
    assert bms._connected

    await bms.disconnect()


async def test_invalid_bms_type(monkeypatch) -> None:
    """Test BMS with invalid type 'C'."""

    monkeypatch.setattr(
        "custom_components.bms_ble.plugins.ogt_bms.BleakClient",
        MockOGTBleakClient,
    )

    bms = BMS(generate_ble_device("cc:cc:cc:cc:cc:cc", "SmartBat-C12294", None, -73))

    result = await bms.async_update()

    assert result == {}
