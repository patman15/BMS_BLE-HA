"""Test the E&J technology BMS implementation."""

from collections.abc import Buffer
from uuid import UUID

from bleak.backends.characteristic import BleakGATTCharacteristic
from bleak.uuids import normalize_uuid_str
import pytest

from custom_components.bms_ble.plugins.redodo_bms import BMS

from .bluetooth import generate_ble_device
from .conftest import MockBleakClient


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
        response: bool = None,  # type: ignore[implicit-optional] # noqa: RUF013 # same as upstream
    ) -> None:
        """Issue write command to GATT."""
        await super().write_gatt_char(char_specifier, data, response)
        assert self._notify_callback is not None
        self._notify_callback(
            "MockRedodoBleakClient", self._response(char_specifier, data)
        )


async def test_update(monkeypatch, reconnect_fixture) -> None:
    """Test Redodo technology BMS data update."""

    monkeypatch.setattr(
        "custom_components.bms_ble.plugins.basebms.BleakClient",
        MockRedodoBleakClient,
    )

    bms = BMS(
        generate_ble_device("cc:cc:cc:cc:cc:cc", "MockBLEDevice", None, -73),
        reconnect_fixture,
    )

    result = await bms.async_update()

    assert result == {
        "voltage": 26.556,
        "current": -1.435,
        "cell#0": 3.317,
        "cell#1": 3.319,
        "cell#2": 3.324,
        "cell#3": 3.323,
        "cell#4": 3.320,
        "cell#5": 3.314,
        "cell#6": 3.322,
        "cell#7": 3.317,
        "delta_voltage": 0.01,
        "power": -38.108,
        "battery_charging": False,
        "battery_level": 65,
        "cycle_charge": 68.89,
        "cycle_capacity": 1829.443,
        "runtime": 172825,
        "temp#0": 23,
        "temp#1": 22,
        "temp#2": -2,
        "temperature": 14.333,
        "cycles": 3,
    }

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
def response(request):
    """Return faulty response frame."""
    return request.param[0]


async def test_invalid_response(monkeypatch, wrong_response) -> None:
    """Test data up date with BMS returning invalid data."""

    monkeypatch.setattr(
        "custom_components.bms_ble.plugins.redodo_bms.BMS.BAT_TIMEOUT",
        0.1,
    )

    monkeypatch.setattr(
        "tests.test_redodo_bms.MockRedodoBleakClient._response",
        lambda _s, _c_, d: wrong_response,
    )

    monkeypatch.setattr(
        "custom_components.bms_ble.plugins.basebms.BleakClient",
        MockRedodoBleakClient,
    )

    bms = BMS(generate_ble_device("cc:cc:cc:cc:cc:cc", "MockBLEDevice", None, -73))

    result = {}
    with pytest.raises(TimeoutError):
        result = await bms.async_update()

    assert not result
    await bms.disconnect()
