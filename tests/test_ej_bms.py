"""Test the E&J technology BMS implementation."""

import pytest
from collections.abc import Buffer
from uuid import UUID

from bleak.backends.characteristic import BleakGATTCharacteristic
from bleak.exc import BleakError
from bleak.uuids import normalize_uuid_str
from custom_components.bms_ble.plugins.ej_bms import BMS

from .bluetooth import generate_ble_device
from .conftest import MockBleakClient


class MockEJBleakClient(MockBleakClient):
    """Emulate a E&J technology BMS BleakClient."""

    def _response(
        self, char_specifier: BleakGATTCharacteristic | int | str | UUID, data: Buffer
    ) -> bytearray:
        if isinstance(char_specifier, str) and normalize_uuid_str(
            char_specifier
        ) != normalize_uuid_str("6e400002-b5a3-f393-e0a9-e50e24dcca9e"):
            return bytearray()
        cmd: int = int(bytearray(data)[3:5], 16)
        if cmd == 0x02:
            return bytearray(
                b":0082310080000101C00000880F540F3C0F510FD70F310F2C0F340F3A0FED0FED0000000000000000000000000000000248424242F0000000000000000001AB~"
            )  # TODO: put numbers
        if cmd == 0x10:
            return bytearray(b":009031001E0000001400080016F4~")  # TODO: put numbers
        return bytearray()

    async def write_gatt_char(
        self,
        char_specifier: BleakGATTCharacteristic | int | str | UUID,
        data: Buffer,
        response: bool = None,  # type: ignore[implicit-optional] # noqa: RUF013 # same as upstream
    ) -> None:
        """Issue write command to GATT."""
        await super().write_gatt_char(char_specifier, data, response)
        assert self._notify_callback is not None
        self._notify_callback(
            "MockPwrcoreBleakClient", self._response(char_specifier, data)
        )


# class MockWrongCRCBleakClient(MockEJBleakClient):
#     """Emulate a E&J technology BMS BleakClient that replies with wrong CRC"""

#     def _response(
#         self, char_specifier: BleakGATTCharacteristic | int | str | UUID, data: Buffer
#     ) -> bytearray:
#         if isinstance(char_specifier, str) and normalize_uuid_str(
#             char_specifier
#         ) != normalize_uuid_str("fff3"):
#             return bytearray()
#         cmd: int = int(bytearray(data)[5])
#         if cmd == 0x60:
#             return bytearray(
#                 b"\x12\x12\x3A\x05\x03\x60\x00\x0A\x02\x13\x00\x00\x71\xC5\x45\x8E\x3D\x00\x01\xCE"
#                 b"\x02\x22\x0D\x0A\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00"
#             )  # wrong CRC [0x01CE != 0x02CD] in line 1
#         if cmd == 0x61:
#             return bytearray(
#                 b"\x12\x12\x3A\x05\x03\x61\x00\x0C\x00\x12\x00\x12\x6D\x60\x0B\x7E\x8F\xDB\x18\x20"
#                 b"\x04\x22\x02\x91\x0D\x0A\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00"
#             )  # wrong CRC [0x02 != 0x03] in line 2
#         if cmd == 0x62:
#             return bytearray(
#                 b"\x12\x13\x3A\x05\x03\x62\x00\x1D\x0E\x0E\xD7\x0E\xD6\x0E\xD6\x0E\xD5\x0E\xD5\x0E"
#                 b"\x12\x23\xD6\x0E\xD1\x0E\xD2\x0E\xD5\x0E\xD6\x0E\xD4\x0E\xD8\x0E\xD7\x0E\xDB\x0E"
#                 b"\x03\x33\x08\x0D\x0A\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00"
#             )  # wrong CRC [0x0E != 0x0D] in line 2
#         return bytearray()


class MockInvalidBleakClient(MockEJBleakClient):
    """Emulate a E&J technology BMS BleakClient replying garbage."""

    def _response(
        self, char_specifier: BleakGATTCharacteristic | int | str | UUID, data: Buffer
    ) -> bytearray:
        if isinstance(char_specifier, str) and normalize_uuid_str(
            char_specifier
        ) != normalize_uuid_str("6e400002-b5a3-f393-e0a9-e50e24dcca9e"):
            return bytearray()
        cmd: int = int(bytearray(data)[3:5], 16)
        if cmd == 0x02:
            return bytearray(
                b"X0082310080000101C00000880F540F3C0F510FD70F310F2C0F340F3A0FED0FED0000000000000000000000000000000248424242F0000000000000000001ABX"
            )  # correct message, wrong SOI
        if cmd == 0x10:
            return bytearray(
                b":009031001D0000001400080016F4~"
            )  # incorrect message, wrong length (1E != 1D)
        return bytearray()

    async def disconnect(self) -> bool:
        """Mock disconnect to raise BleakError."""
        raise BleakError


async def test_update(monkeypatch, reconnect_fixture) -> None:
    """Test E&J technology BMS data update."""

    monkeypatch.setattr(
        "custom_components.bms_ble.plugins.basebms.BleakClient",
        MockEJBleakClient,
    )

    bms = BMS(
        generate_ble_device("cc:cc:cc:cc:cc:cc", "MockBLEDevice", None, -73),
        reconnect_fixture,
    )

    result = await bms.async_update()

    assert result == {
        "voltage": 39.517,
        "current": -0.02,
        "battery_level": 1,
        "cycles": 0,
        "cycle_charge": 2.0,
        "cell#0": 3.924,
        "cell#1": 3.900,
        "cell#2": 3.921,
        "cell#3": 4.055,
        "cell#4": 3.889,
        "cell#5": 3.884,
        "cell#6": 3.892,
        "cell#7": 3.898,
        "cell#8": 4.077,
        "cell#9": 4.077,
        "delta_voltage": 0.193,
        "temperature": 32,
        "cycle_capacity": 79.034,
        "power": -0.79,
        "runtime": 360000,
        "battery_charging": False,
    }

    # query again to check already connected state
    result = await bms.async_update()
    assert bms._client.is_connected is not reconnect_fixture  # noqa: SLF001

    await bms.disconnect()


@pytest.fixture(name="wrong_response", params=[
        b"x009031001E0000001400080016F4~", # wrong SOI
        b":009031001E0000001400080016F4x", # wrong EOI
        b":009031001D0000001400080016F4~", # wrong length
    ])
def response(request):
    """Return all possible BMS variants."""
    return request.param

async def test_invalid_response(monkeypatch, wrong_response) -> None:
    """Test data up date with BMS returning invalid data."""

    monkeypatch.setattr(
        "custom_components.bms_ble.plugins.ej_bms.BAT_TIMEOUT",
        0.1,
    )

    monkeypatch.setattr(
        "tests.test_ej_bms.MockEJBleakClient._response",
        lambda _s,_c_,d: wrong_response,
    )

    monkeypatch.setattr(
        "custom_components.bms_ble.plugins.basebms.BleakClient",
        MockEJBleakClient,
    )

    bms = BMS(generate_ble_device("cc:cc:cc:cc:cc:cc", "MockBLEDevice", None, -73))

    result = {}
    with pytest.raises(TimeoutError):
        result = await bms.async_update()

    assert not result
    await bms.disconnect()


# async def test_wrong_crc(monkeypatch, dev_name) -> None:
#     """Test data update with BMS returning invalid data."""

#     monkeypatch.setattr(
#         "custom_components.bms_ble.plugins.dpwrcore_bms.BAT_TIMEOUT",
#         0.1,
#     )

#     monkeypatch.setattr(
#         "custom_components.bms_ble.plugins.basebms.BleakClient",
#         MockWrongCRCBleakClient,
#     )

#     bms = BMS(generate_ble_device("cc:cc:cc:cc:cc:cc", dev_name, None, -73))

#     assert await bms.async_update() == {}

#     await bms.disconnect()
