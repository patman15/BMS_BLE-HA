"""Test the D-powercore BMS implementation."""

from collections.abc import Buffer
from uuid import UUID

from bleak.backends.characteristic import BleakGATTCharacteristic
from bleak.exc import BleakError
from bleak.uuids import normalize_uuid_str
from custom_components.bms_ble.plugins.pwrcore_bms import BMS

from .bluetooth import generate_ble_device
from .conftest import MockBleakClient


class MockPwrcoreBleakClient(MockBleakClient):
    """Emulate a D-powercore BMS BleakClient."""

    def _response(
        self, char_specifier: BleakGATTCharacteristic | int | str | UUID, data: Buffer
    ) -> bytearray:
        if char_specifier != normalize_uuid_str("fff3"):
            return bytearray()
        cmd: int = int(bytearray(data)[5])
        if cmd == 0x60:
            return bytearray(
                b"\x12\x12\x3A\x05\x03\x60\x00\x0A\x02\x13\x00\x00\x71\xC5\x45\x8E\x3D\x00\x02\xCD"
                b"\x02\x22\x0D\x0A\x03\x60\x00\x0A\x02\x13\x00\x00\x71\xC5\x45\x8E\x3D\x00\x02\xCD"
            ) # TODO: put numbers

        return bytearray()

    async def write_gatt_char(
        self,
        char_specifier: BleakGATTCharacteristic | int | str | UUID,
        data: Buffer,
        response: bool = None,  # type: ignore[implicit-optional] # noqa: RUF013 # same as upstream
    ) -> None:
        """Issue write command to GATT."""
        await super().write_gatt_char(char_specifier, data, response)       
        if bytearray(data)[0] & 0x80: # ignore ACK messages # TODO: verify those?
            return
        assert self._notify_callback is not None
        self._notify_callback(
            "MockPwrcoreBleakClient", self._response(char_specifier, data)
        )


class MockInvalidBleakClient(MockPwrcoreBleakClient):
    """Emulate a D-powercore BMS BleakClient."""

    def _response(
        self, char_specifier: BleakGATTCharacteristic | int | str | UUID, data: Buffer
    ) -> bytearray:
        if char_specifier != normalize_uuid_str("fff3"):
            return bytearray(b"invalid_value")

        return bytearray()

    async def disconnect(self) -> bool:
        """Mock disconnect to raise BleakError."""
        raise BleakError


async def test_update(monkeypatch, reconnect_fixture) -> None:
    """Test D-pwercore BMS data update."""

    monkeypatch.setattr(
        "custom_components.bms_ble.plugins.pwrcore_bms.BleakClient",
        MockPwrcoreBleakClient,
    )

    bms = BMS(
        generate_ble_device("cc:cc:cc:cc:cc:cc", "TBA-MockBLEdevice", None, -73),
        reconnect_fixture,
    )

    result = await bms.async_update()

    assert result == {
        "voltage": 14.0,
        "current": 3.0,
        "battery_level": 90.0,
        "cycles": 57,
        "cycle_charge": 345.6,
        "cell#0": 4.127,
        "cell#1": 4.137,
        "cell#2": 4.147,
        "cell#3": 4.157,
        "cell_count": 4,
        "delta_voltage": 0.321,
        "temp_sensors": 4,
        "temperature": 21.5,
        "cycle_capacity": 4838.4,
        "power": 42.0,
        "temp#0": 20.0,
        "temp#1": 21.0,
        "temp#2": 22.0,
        "temp#3": 23.0,
        "battery_charging": True,
    }

    # query again to check already connected state
    result = await bms.async_update()
    assert bms._client and bms._client.is_connected is not reconnect_fixture # noqa: SLF001

    await bms.disconnect()


async def test_invalid_response(monkeypatch) -> None:
    """Test data update with BMS returning invalid data."""

    monkeypatch.setattr(
        "custom_components.bms_ble.plugins.pwrcore_bms.BleakClient",
        MockInvalidBleakClient,
    )

    bms = BMS(generate_ble_device("cc:cc:cc:cc:cc:cc", "TBA-MockBLEdevice", None, -73))

    result = await bms.async_update()

    assert result == {}

    await bms.disconnect()
