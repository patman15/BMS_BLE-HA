"""Test the E&J technology BMS implementation."""

from collections.abc import Buffer
from typing import Final
from uuid import UUID

from bleak.backends.characteristic import BleakGATTCharacteristic
from bleak.uuids import normalize_uuid_str
import pytest

from custom_components.bms_ble.plugins.basebms import BMSsample
from custom_components.bms_ble.plugins.redodo_bms import BMS

from .bluetooth import generate_ble_device
from .conftest import MockBleakClient

_RESULT_DEFS: Final[BMSsample] = {
    "voltage": 26.556,
    "current": -1.435,
    "cell_voltages": [3.317, 3.319, 3.324, 3.323, 3.320, 3.314, 3.322, 3.317],
    "delta_voltage": 0.01,
    "power": -38.108,
    "battery_charging": False,
    "battery_level": 65,
    "cycle_charge": 68.89,
    "cycle_capacity": 1829.443,
    "runtime": 172825,
    "temp_values": [23, 22, -2],
    "temperature": 14.333,
    "cycles": 3,
    "problem": False,
    "problem_code": 0,
}


class MockRedodoBleakClient(MockBleakClient):
    """Emulate a Redodo BMS BleakClient."""

    def _response(
        self, char_specifier: BleakGATTCharacteristic | int | str | UUID, data: Buffer
    ) -> bytearray:
        if isinstance(char_specifier, str) and normalize_uuid_str(
            char_specifier
        ) != normalize_uuid_str("ffe2"):
            return bytearray()
        cmd: int = bytearray(data)[4]
        if cmd == 0x13:
            return bytearray(
                b"\x00\x00\x65\x01\x93\x55\xaa\x00\x46\x66\x00\x00\xbc\x67\x00\x00\xf5\x0c\xf7\x0c"
                b"\xfc\x0c\xfb\x0c\xf8\x0c\xf2\x0c\xfa\x0c\xf5\x0c\x00\x00\x00\x00\x00\x00\x00\x00"
                b"\x00\x00\x00\x00\x00\x00\x00\x00\x65\xfa\xff\xff\x17\x00\x16\x00\xfe\xff\x00\x00"
                b"\x00\x00\xe9\x1a\x04\x29\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00"
                b"\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x41\x00\x64\x00\x00\x00\x03\x00\x00\x00"
                b"\x5f\x01\x00\x00\xa2"
            )  # TODO: put numbers
        return bytearray()

    async def write_gatt_char(
        self,
        char_specifier: BleakGATTCharacteristic | int | str | UUID,
        data: Buffer,
        response: bool | None = None,
    ) -> None:
        """Issue write command to GATT."""
        await super().write_gatt_char(char_specifier, data, response)
        assert self._notify_callback is not None
        self._notify_callback(
            "MockRedodoBleakClient", self._response(char_specifier, data)
        )


async def test_update(patch_bleak_client, reconnect_fixture) -> None:
    """Test Redodo technology BMS data update."""

    patch_bleak_client(MockRedodoBleakClient)

    bms = BMS(
        generate_ble_device("cc:cc:cc:cc:cc:cc", "MockBLEDevice", None, -73),
        reconnect_fixture,
    )

    result = await bms.async_update()

    assert result == _RESULT_DEFS

    # query again to check already connected state
    result = await bms.async_update()
    assert bms._client.is_connected is not reconnect_fixture

    await bms.disconnect()


@pytest.fixture(
    name="wrong_response",
    params=[
        (
            bytearray(
                b"\x00\x00\x65\x01\x93\x55\xaa\x00\x46\x66\x00\x00\xbc\x67\x00\x00\xf5\x0c\xf7\x0c"
                b"\xfc\x0c\xfb\x0c\xf8\x0c\xf2\x0c\xfa\x0c\xf5\x0c\x00\x00\x00\x00\x00\x00\x00\x00"
                b"\x00\x00\x00\x00\x00\x00\x00\x00\x65\xfa\xff\xff\x17\x00\x16\x00\x17\x00\x00\x00"
                b"\x00\x00\xe9\x1a\x04\x29\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00"
                b"\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x41\x00\x64\x00\x00\x00\x03\x00\x00\x00"
                b"\x5f\x01\x00\x00\xff"
            ),
            "wrong CRC",
        ),
        (
            bytearray(
                b"\x00\x01\x65\x01\x93\x55\xaa\x00\x46\x66\x00\x00\xbc\x67\x00\x00\xf5\x0c\xf7\x0c"
                b"\xfc\x0c\xfb\x0c\xf8\x0c\xf2\x0c\xfa\x0c\xf5\x0c\x00\x00\x00\x00\x00\x00\x00\x00"
                b"\x00\x00\x00\x00\x00\x00\x00\x00\x65\xfa\xff\xff\x17\x00\x16\x00\x17\x00\x00\x00"
                b"\x00\x00\xe9\x1a\x04\x29\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00"
                b"\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x41\x00\x64\x00\x00\x00\x03\x00\x00\x00"
                b"\x5f\x01\x00\x00\xbc"
            ),
            "wrong SOF",
        ),
        (
            bytearray(
                b"\x00\x00\x65\x01\x93\x55\xaa\x00\x46\x66\x00\x00\xbc\x67\x00\x00\xf5\x0c\xf7\x0c"
                b"\xfc\x0c\xfb\x0c\xf8\x0c\xf2\x0c\xfa\x0c\xf5\x0c\x00\x00\x00\x00\x00\x00\x00\x00"
                b"\x00\x00\x00\x00\x00\x00\x00\x00\x65\xfa\xff\xff\x17\x00\x16\x00\x17\x00\x00\x00"
                b"\x00\x00\xe9\x1a\x04\x29\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00"
                b"\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x41\x00\x64\x00\x00\x00\x03\x00\x00\x00"
                b"\x5f\x01\x00\xbc"
            ),
            "wrong length",
        ),
        (bytearray(b"\x00"), "too short"),
    ],
    ids=lambda param: param[1],
)
def fix_response(request):
    """Return faulty response frame."""
    return request.param[0]


async def test_invalid_response(
    monkeypatch, patch_bleak_client, patch_bms_timeout, wrong_response
) -> None:
    """Test data up date with BMS returning invalid data."""

    patch_bms_timeout()

    monkeypatch.setattr(
        MockRedodoBleakClient, "_response", lambda _s, _c, _d: wrong_response
    )

    patch_bleak_client(MockRedodoBleakClient)

    bms = BMS(generate_ble_device("cc:cc:cc:cc:cc:cc", "MockBLEDevice", None, -73))

    result: BMSsample = {}
    with pytest.raises(TimeoutError):
        result = await bms.async_update()

    assert not result
    await bms.disconnect()


@pytest.fixture(
    name="problem_response",
    params=[
        (
            bytearray(
                b"\x00\x00\x65\x01\x93\x55\xaa\x00\x46\x66\x00\x00\xbc\x67\x00\x00\xf5\x0c\xf7\x0c"
                b"\xfc\x0c\xfb\x0c\xf8\x0c\xf2\x0c\xfa\x0c\xf5\x0c\x00\x00\x00\x00\x00\x00\x00\x00"
                b"\x00\x00\x00\x00\x00\x00\x00\x00\x65\xfa\xff\xff\x17\x00\x16\x00\xfe\xff\x00\x00"
                b"\x00\x00\xe9\x1a\x04\x29\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x01\x00\x00\x00"
                b"\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x41\x00\x64\x00\x00\x00\x03\x00\x00\x00"
                b"\x5f\x01\x00\x00\xa3"
            ),
            "first_bit",
        ),
        (
            bytearray(
                b"\x00\x00\x65\x01\x93\x55\xaa\x00\x46\x66\x00\x00\xbc\x67\x00\x00\xf5\x0c\xf7\x0c"
                b"\xfc\x0c\xfb\x0c\xf8\x0c\xf2\x0c\xfa\x0c\xf5\x0c\x00\x00\x00\x00\x00\x00\x00\x00"
                b"\x00\x00\x00\x00\x00\x00\x00\x00\x65\xfa\xff\xff\x17\x00\x16\x00\xfe\xff\x00\x00"
                b"\x00\x00\xe9\x1a\x04\x29\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x80"
                b"\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x41\x00\x64\x00\x00\x00\x03\x00\x00\x00"
                b"\x5f\x01\x00\x00\x22"
            ),
            "last_bit",
        ),
    ],
    ids=lambda param: param[1],
)
def prb_response(request):
    """Return faulty response frame."""
    return request.param


async def test_problem_response(
    monkeypatch, patch_bleak_client, problem_response
) -> None:
    """Test data up date with BMS returning protection flags."""

    monkeypatch.setattr(
        MockRedodoBleakClient, "_response", lambda _s, _c, _d: problem_response[0]
    )

    patch_bleak_client(MockRedodoBleakClient)

    bms = BMS(generate_ble_device("cc:cc:cc:cc:cc:cc", "MockBLEDevice", None, -73))

    assert await bms.async_update() == _RESULT_DEFS | {
        "problem": True,
        "problem_code": 1 << (0 if problem_response[1] == "first_bit" else 31),
    }

    await bms.disconnect()
