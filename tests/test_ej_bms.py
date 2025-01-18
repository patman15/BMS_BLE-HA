"""Test the E&J technology BMS implementation."""

from collections.abc import Buffer
from uuid import UUID

from bleak.backends.characteristic import BleakGATTCharacteristic
from bleak.uuids import normalize_uuid_str
import pytest

from custom_components.bms_ble.plugins.ej_bms import BMS

from .bluetooth import generate_ble_device
from .conftest import MockBleakClient

BT_FRAME_SIZE = 20


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
                b":0082310080000101C00000880F540F3C0F510FD70F310F2C0F340F3A0FED0FED0000000000000000"
                b"000000000000000248424242F0000000000000000001AB~"
            )  # TODO: put numbers
        if cmd == 0x10:
            return bytearray(b":009031001E00000002000A000AD8~")  # TODO: put numbers
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
        self._notify_callback("MockEctiveBleakClient", bytearray(b"AT\r\n"))
        self._notify_callback("MockEctiveBleakClient", bytearray(b"AT\r\nillegal"))
        for notify_data in [
            self._response(char_specifier, data)[i : i + BT_FRAME_SIZE]
            for i in range(0, len(self._response(char_specifier, data)), BT_FRAME_SIZE)
        ]:
            self._notify_callback("MockEctiveBleakClient", notify_data)


class MockEJsfBleakClient(MockEJBleakClient):
    """Emulate a E&J technology BMS BleakClient with single frame protocol."""

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
                b":008231008C000000000000000CBF0CC00CEA0CD50000000000000000000000000000000000000000"
                b"00000000008C000041282828F000000000000100004B044C05DC05DCB2~"
            )  # TODO: put numbers
        return bytearray()


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
        "cycle_charge": 0.2,
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
        "cycle_capacity": 7.903,
        "power": -0.79,
        "runtime": 36000,
        "battery_charging": False,
    }

    # query again to check already connected state
    result = await bms.async_update()
    assert bms._client.is_connected is not reconnect_fixture  # noqa: SLF001

    await bms.disconnect()


async def test_update_single_frame(monkeypatch, reconnect_fixture) -> None:
    """Test E&J technology BMS data update."""

    monkeypatch.setattr(
        "custom_components.bms_ble.plugins.basebms.BleakClient",
        MockEJsfBleakClient,
    )

    bms = BMS(
        generate_ble_device("cc:cc:cc:cc:cc:cc", "MockBLEDevice", None, -73),
        reconnect_fixture,
    )

    result = await bms.async_update()

    assert result == {
        "voltage": 13.118,
        "current": 1.4,
        "battery_level": 75,
        "cycles": 1,
        "cycle_charge": 110.0,
        "cell#0": 3.263,
        "cell#1": 3.264,
        "cell#2": 3.306,
        "cell#3": 3.285,
        "delta_voltage": 0.043,
        "temperature": 25,
        "cycle_capacity": 1442.98,
        "power": 18.365,
        "battery_charging": True,
    }

    # query again to check already connected state
    result = await bms.async_update()
    assert bms._client.is_connected is not reconnect_fixture  # noqa: SLF001

    await bms.disconnect()


@pytest.fixture(
    name="wrong_response",
    params=[
        (b"x009031001E0000001400080016F4~", "wrong SOI"),
        (b":009031001E0000001400080016F4x", "wrong EOI"),
        (b":009031001D0000001400080016F4~", "wrong length"),
        (b":009031001E00000002000A000AD9~", "wrong CRC"),
    ],
    ids=lambda param: param[1],
)
def response(request):
    """Return faulty response frame."""
    return request.param[0]


async def test_invalid_response(monkeypatch, wrong_response) -> None:
    """Test data up date with BMS returning invalid data."""

    monkeypatch.setattr(
        "custom_components.bms_ble.plugins.ej_bms.BMS.BAT_TIMEOUT",
        0.1,
    )

    monkeypatch.setattr(
        "tests.test_ej_bms.MockEJBleakClient._response",
        lambda _s, _c, _d: wrong_response,
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
