"""Test the Daly BMS implementation."""

from collections.abc import Buffer
from uuid import UUID

from bleak.backends.characteristic import BleakGATTCharacteristic
from bleak.exc import BleakError
from bleak.uuids import normalize_uuid_str
from custom_components.bms_ble.plugins.daly_bms import BMS

from .bluetooth import generate_ble_device
from .conftest import MockBleakClient


class MockDalyBleakClient(MockBleakClient):
    """Emulate a Daly BMS BleakClient."""

    HEAD_READ = bytearray(b"\xD2\x03")
    CMD_INFO = bytearray(b"\x00\x00\x00\x3E\xD7\xB9")
    MOS_INFO = bytearray(b"\x00\x3E\x00\x09\xF7\xA3")    

    def _response(
        self, char_specifier: BleakGATTCharacteristic | int | str | UUID, data: Buffer
    ) -> bytearray:
        if char_specifier == normalize_uuid_str("fff2") and data == (
            self.HEAD_READ + self.CMD_INFO
        ):
            return bytearray(
                b"\xd2\x03|\x10\x1f\x10)\x103\x10=\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00<\x00=\x00>\x00?\x00\x00\x00\x00\x00\x00\x00\x00\x00\x8cuN\x03\x84\x10=\x10\x1f\x00\x00\x00\x00\x00\x00\r\x80\x00\x04\x00\x04\x009\x00\x01\x00\x00\x00\x01\x10.\x01\x41\x00*\x00\x00\x00\x00\x00\x00\x00\x00\xa0\xdf"
            ) # {'voltage': 14.0, 'current': 3.0, 'battery_level': 90.0, 'cycles': 57, 'cycle_charge': 345.6, 'numTemp': 4, 'temperature': 21.5, 'cycle_capacity': 4838.400000000001, 'power': 42.0, 'battery_charging': True, 'runtime': none!, 'delta_voltage': 0.321}

        if char_specifier == normalize_uuid_str("fff2") and data == (
            self.HEAD_READ + self.MOS_INFO
        ):
            return bytearray(b"\xd2\x03\x12\x00\x00\x00\x00\x75\x30\x00\x00\x00\x4e\xff\xff\xff\xff\xff\xff\xff\xff\x0b\x4e")

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
            "MockDalyBleakClient", self._response(char_specifier, data)
        )


class MockInvalidBleakClient(MockDalyBleakClient):
    """Emulate a Daly BMS BleakClient."""

    def _response(
        self, char_specifier: BleakGATTCharacteristic | int | str | UUID, data: Buffer
    ) -> bytearray:
        if char_specifier == normalize_uuid_str("fff2"):
            return bytearray(b"invalid_value")

        return bytearray()

    async def disconnect(self) -> bool:
        """Mock disconnect to raise BleakError."""
        raise BleakError


async def test_update(monkeypatch, reconnect_fixture) -> None:
    """Test Daly BMS data update."""

    monkeypatch.setattr(
        "custom_components.bms_ble.plugins.daly_bms.BleakClient",
        MockDalyBleakClient,
    )

    bms = BMS(
        generate_ble_device("cc:cc:cc:cc:cc:cc", "MockBLEdevice", None, -73),
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
        "temperature": 24.8,
        "cycle_capacity": 4838.4,
        "power": 42.0,
        "temp#0": 38.0,
        "temp#1": 20.0,
        "temp#2": 21.0,
        "temp#3": 22.0,
        "temp#4": 23.0,
        "battery_charging": True,
    }

    # query again to check already connected state
    result = await bms.async_update()
    assert bms._client and bms._client.is_connected is not reconnect_fixture # noqa: SLF001

    await bms.disconnect()


async def test_invalid_response(monkeypatch) -> None:
    """Test data update with BMS returning invalid data."""

    monkeypatch.setattr(
        "custom_components.bms_ble.plugins.daly_bms.BleakClient",
        MockInvalidBleakClient,
    )

    bms = BMS(generate_ble_device("cc:cc:cc:cc:cc:cc", "MockBLEdevice", None, -73))

    result = await bms.async_update()

    assert result == {}

    await bms.disconnect()
