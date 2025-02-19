"""Test the ECOW implementation."""

from collections.abc import Awaitable, Callable
from typing import Final
from uuid import UUID

from bleak.backends.characteristic import BleakGATTCharacteristic

# from bleak.exc import BleakDeviceNotFoundError
# from bleak.uuids import normalize_uuid_str
# import pytest
from custom_components.bms_ble.plugins.ecoworthy_bms import BMS

from .bluetooth import generate_ble_device
from .conftest import MockBleakClient


def ref_value() -> dict:
    """Return reference value for mock Seplos BMS."""
    return {
        "cell_count": 4,
        "temp_sensors": 3,
        "voltage": 13.29,
        "current": -1.14,
        "battery_level": 72,
        "cycle_charge": 72,
        "design_capacity": 100,
        "cycles": 8,
        "temperature": 19.567,
        "cycle_capacity": 956.88,
        "power": -15.151,
        "battery_charging": False,
        "cell#0": 3.323,
        "cell#1": 3.325,
        "cell#2": 3.323,
        "cell#3": 3.322,
        "temp#0": 20.5,
        "temp#1": 19.2,
        "temp#2": 19.0,
        "delta_voltage": 0.003,
        "runtime": 227368,
    }


class MockECOWBleakClient(MockBleakClient):
    """Emulate a ECOW BMS BleakClient."""

    CMDS: Final[dict[int, bytearray]] = {
        0xA1: bytearray(b"\x00\x01\x03\x00\x8c\x00\x00\x99\x42"),
        0xA2: bytearray(b"\x00\x01\x03\x00\x8d\x00\x00\x59\x13"),
    }
    RESP: Final[dict[int, bytearray]] = {
        0xA1: bytearray(  # 16 celll message
            b"\xa1\x00\x00\x00\x65\x00\x00\x00\x00\x00\x18\x01\x03\x44\x00\x18\x00\x48\x00\x64\x05"  # 21
            b"\x31\xff\x8e\x00\x00\x27\x10\x00\x01\x00\x01\x00\x00\x00\x00\x00\x00\x00\x00\x00\x01"
            b"\x00\x02\x00\x00\xff\xff\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00"
            b"\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x21\x86"
        ),
        0xA2: bytearray(
            b"\xa2\x00\x00\x00\x65\x00\x00\x00\x00\x00\x18\x01\x03\x56\x00\x04\x0c\xfb\x0c\xfd\x0c"
            b"\xfb\x0c\xfa\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff"
            b"\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff"
            b"\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\x00\x03\x00\xcd"
            b"\x00\xc0\x00\xbe\xfc\x18\xfc\x18\xfc\x18\xfc\x18\xfc\x18\xfc\x18\x97\x6a"
        ),
    }

    async def start_notify(
        self,
        char_specifier: BleakGATTCharacteristic | int | str | UUID,
        callback: Callable[
            [BleakGATTCharacteristic, bytearray], None | Awaitable[None]
        ],
        **kwargs,
    ) -> None:
        """Issue write command to GATT."""
        await super().start_notify(char_specifier, callback, **kwargs)

        assert (
            self._notify_callback
        ), "write to characteristics but notification not enabled"

        self._notify_callback("MockECOWBleakClient", self.RESP[0xA1])
        self._notify_callback("MockECOWBleakClient", self.RESP[0xA2])


async def test_update(monkeypatch, reconnect_fixture) -> None:
    """Test ECOW BMS data update."""

    monkeypatch.setattr(
        "custom_components.bms_ble.plugins.basebms.BleakClient",
        MockECOWBleakClient,
    )

    bms = BMS(
        generate_ble_device("cc:cc:cc:cc:cc:cc", "MockBLEdevice", None, -73),
        reconnect_fixture,
    )

    result = await bms.async_update()

    assert result == ref_value()

    # query again to check already connected state
    result = await bms.async_update()
    assert (
        bms._client and bms._client.is_connected is not reconnect_fixture
    )  # noqa: SLF001

    await bms.disconnect()


# @pytest.fixture(
#     name="wrong_response",
#     params=[
#         (b"\x7e\x00\x01\x03\x00\x8c\x00\x01\x00\xA1\x18\x00", "invalid frame end"),
#         (b"\x7e\x10\x01\x03\x00\x8c\x00\x01\x00\xAD\x19\x0D", "invalid version"),
#         (b"\x7e\x00\x01\x03\x00\x8c\x00\x01\x00\xA1\x00\x0D", "invalid CRC"),
#         (b"\x7e\x00\x01\x03\x00\x8c\x00\x01\x00\xA1\x18\x0D\x00", "oversized frame"),
#         (b"\x7e\x00\x01\x03\x00\x8c\x00\x01\x00\xA1\x0D", "undersized frame"),
#         (b"\x7e\x00\x01\x03\x01\x8c\x00\x01\x00\x61\x25\x0D", "error response"),
#     ],
#     ids=lambda param: param[1],
# )
# def response(request):
#     """Return faulty response frame."""
#     return request.param[0]


# async def test_invalid_response(monkeypatch, wrong_response) -> None:
#     """Test data up date with BMS returning invalid data."""

#     monkeypatch.setattr(
#         "custom_components.bms_ble.plugins.ECOW_bms.BMS.BAT_TIMEOUT",
#         0.1,
#     )

#     monkeypatch.setattr(
#         "tests.test_ECOW_bms.MockECOWBleakClient._response",
#         lambda _s, _c_, d: wrong_response,
#     )

#     monkeypatch.setattr(
#         "custom_components.bms_ble.plugins.basebms.BleakClient",
#         MockECOWBleakClient,
#     )

#     bms = BMS(generate_ble_device("cc:cc:cc:cc:cc:cc", "MockBLEDevice", None, -73))

#     result = {}
#     with pytest.raises(TimeoutError):
#         result = await bms.async_update()

#     assert not result
#     await bms.disconnect()


# async def test_init_fail(monkeypatch, bool_fixture) -> None:
#     """Test that failing to initialize simply continues and tries to read data."""

#     throw_exception: bool = bool_fixture

#     async def error_repsonse(*_args, **_kwargs) -> bytearray:
#         return bytearray(b"\x00")

#     async def throw_response(*_args, **_kwargs) -> bytearray:
#         raise BleakDeviceNotFoundError("MockECOWBleakClient")

#     monkeypatch.setattr(
#         "tests.test_ECOW_bms.MockECOWBleakClient.read_gatt_char",
#         throw_response if throw_exception else error_repsonse,
#     )

#     monkeypatch.setattr(
#         "custom_components.bms_ble.plugins.basebms.BleakClient",
#         MockECOWBleakClient,
#     )

#     bms = BMS(generate_ble_device("cc:cc:cc:cc:cc:cc", "MockBLEDevice", None, -73))

#     if bool_fixture:
#         with pytest.raises(BleakDeviceNotFoundError):
#             assert not await bms.async_update()
#     else:
#         assert await bms.async_update() == ref_value()["16S6T"]

#     await bms.disconnect()
