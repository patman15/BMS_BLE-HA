"""Test the D-powercore BMS implementation."""

import pytest
from collections.abc import Buffer
from uuid import UUID

from bleak.backends.characteristic import BleakGATTCharacteristic
from bleak.exc import BleakError
from bleak.uuids import normalize_uuid_str
from custom_components.bms_ble.plugins.pwrcore_bms import BMS

from .bluetooth import generate_ble_device
from .conftest import MockBleakClient


@pytest.fixture(name="dev_name", params=["TBA-", "DXB-"])
def patch_dev_name(request) -> str:
    """Provide device name variants."""
    return request.param + "MockBLEDevice_C0FE"


class MockPwrcoreBleakClient(MockBleakClient):
    """Emulate a D-powercore BMS BleakClient."""

    PAGE_LEN = 20

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
            )  # TODO: put numbers
        if cmd == 0x61:
            return bytearray(
                b"\x12\x12\x3A\x05\x03\x61\x00\x0C\x00\x12\x00\x12\x6D\x60\x0B\x7E\x8F\xDB\x18\x20"
                b"\x04\x22\x03\x91\x0D\x0A\x00\x0C\x00\x12\x00\x12\x6D\x60\x0B\x7E\x8F\xDB\x18\x20"
            )  # TODO: put numbers
        if cmd == 0x62:
            return bytearray(
                b"\x12\x13\x3A\x05\x03\x62\x00\x1D\x0E\x0E\xD7\x0E\xD6\x0E\xD6\x0E\xD5\x0E\xD5\x0E"
                b"\x12\x23\xD6\x0E\xD1\x0E\xD2\x0E\xD5\x0E\xD6\x0E\xD4\x0E\xD8\x0E\xD7\x0E\xDB\x0D"
                b"\x03\x33\x08\x0D\x0A\x0E\xD2\x0E\xD5\x0E\xD6\x0E\xD4\x0E\xD8\x0E\xD7\x0E\xDB\x0D"
            )  # TODO: put numbers
        if cmd == 0x64:
            assert bytearray(data)[8:10] == bytes.fromhex("C0FE"), "incorrect password"
            assert bytearray(data)[0] == 0xE, "incorrect unlock CMD length"
            resp = bytearray(data)
            return bytearray(resp[0] | 0x80) + resp[1:]
        return bytearray()

    async def write_gatt_char(
        self,
        char_specifier: BleakGATTCharacteristic | int | str | UUID,
        data: Buffer,
        response: bool = None,  # type: ignore[implicit-optional] # noqa: RUF013 # same as upstream
    ) -> None:
        """Issue write command to GATT."""
        data_ba = bytearray(data)
        await super().write_gatt_char(char_specifier, data, response)
        if data_ba[0] & 0x80:  # ignore ACK messages # TODO: verify those?
            return
        assert self._notify_callback is not None
        resp = self._response(char_specifier, data)
        await self._notify_callback(  # send acknowledge
            "MockPwrcoreBleakClient", bytearray([data_ba[0] | 0x80]) + data_ba[1:]
        )
        for pos in range(1 + int((len(resp) - 1) / self.PAGE_LEN)):
            await self._notify_callback(
                "MockPwrcoreBleakClient", resp[pos * 20 :][: self.PAGE_LEN]
            )


class MockWrongCRCBleakClient(MockPwrcoreBleakClient):
    def _response(
        self, char_specifier: BleakGATTCharacteristic | int | str | UUID, data: Buffer
    ) -> bytearray:
        if char_specifier != normalize_uuid_str("fff3"):
            return bytearray()
        cmd: int = int(bytearray(data)[5])
        if cmd == 0x60:
            return bytearray(
                b"\x12\x12\x3A\x05\x03\x60\x00\x0A\x02\x13\x00\x00\x71\xC5\x45\x8E\x3D\x00\x01\xCE"
                b"\x02\x22\x0D\x0A\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00"
            )  # wrong CRC [0x01CE != 0x02CD] in line 1
        if cmd == 0x61:
            return bytearray(
                b"\x12\x12\x3A\x05\x03\x61\x00\x0C\x00\x12\x00\x12\x6D\x60\x0B\x7E\x8F\xDB\x18\x20"
                b"\x04\x22\x02\x91\x0D\x0A\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00"
            )  # wrong CRC [0x02 != 0x03] in line 2
        if cmd == 0x62:
            return bytearray(
                b"\x12\x13\x3A\x05\x03\x62\x00\x1D\x0E\x0E\xD7\x0E\xD6\x0E\xD6\x0E\xD5\x0E\xD5\x0E"
                b"\x12\x23\xD6\x0E\xD1\x0E\xD2\x0E\xD5\x0E\xD6\x0E\xD4\x0E\xD8\x0E\xD7\x0E\xDB\x0E"
                b"\x03\x33\x08\x0D\x0A\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00"
            )  # wrong CRC [0x0E != 0x0D] in line 2
        return bytearray()


class MockInvalidBleakClient(MockPwrcoreBleakClient):
    """Emulate a D-powercore BMS BleakClient."""

    def _response(
        self, char_specifier: BleakGATTCharacteristic | int | str | UUID, data: Buffer
    ) -> bytearray:
        if char_specifier == normalize_uuid_str("fff3"):
            return bytearray(b"invalid_value")

        return bytearray()

    async def disconnect(self) -> bool:
        """Mock disconnect to raise BleakError."""
        raise BleakError


async def test_update(monkeypatch, dev_name, reconnect_fixture) -> None:
    """Test D-pwercore BMS data update."""

    monkeypatch.setattr(
        "custom_components.bms_ble.plugins.basebms.BleakClient",
        MockPwrcoreBleakClient,
    )

    bms = BMS(
        generate_ble_device("cc:cc:cc:cc:cc:cc", dev_name, None, -73),
        reconnect_fixture,
    )

    result = await bms.async_update()

    assert result == {
        "voltage": 53.1,
        "current": 0,
        "battery_level": 61.0,
        "cycles": 18,
        "cycle_charge": 17.806,
        "cell#0": 3.799,
        "cell#1": 3.798,
        "cell#2": 3.798,
        "cell#3": 3.797,
        "cell#4": 3.797,
        "cell#5": 3.798,
        "cell#6": 3.793,
        "cell#7": 3.794,
        "cell#8": 3.797,
        "cell#9": 3.798,
        "cell#10": 3.796,
        "cell#11": 3.800,
        "cell#12": 3.799,
        "cell#13": 3.803,
        "cell_count": 14,
        "delta_voltage": 0.01,
        "temperature": 21.1,
        "cycle_capacity": 945.499,
        "power": 0.0,
        "battery_charging": False,
    }

    # query again to check already connected state
    result = await bms.async_update()
    assert (
        bms._client.is_connected is not reconnect_fixture
    )  # noqa: SLF001

    await bms.disconnect()


async def test_invalid_response(monkeypatch, dev_name) -> None:
    """Test data update with BMS returning invalid data."""

    monkeypatch.setattr(
        "custom_components.bms_ble.plugins.pwrcore_bms.BAT_TIMEOUT",
        1,
    )

    monkeypatch.setattr(
        "custom_components.bms_ble.plugins.basebms.BleakClient",
        MockInvalidBleakClient,
    )

    bms = BMS(generate_ble_device("cc:cc:cc:cc:cc:cc", dev_name, None, -73))

    with pytest.raises(TimeoutError):
        _result = await bms.async_update()

    await bms.disconnect()


async def test_wrong_crc(monkeypatch, dev_name) -> None:
    """Test data update with BMS returning invalid data."""

    monkeypatch.setattr(
        "custom_components.bms_ble.plugins.pwrcore_bms.BAT_TIMEOUT",
        1,
    )

    monkeypatch.setattr(
        "custom_components.bms_ble.plugins.basebms.BleakClient",
        MockWrongCRCBleakClient,
    )

    bms = BMS(generate_ble_device("cc:cc:cc:cc:cc:cc", dev_name, None, -73))

    assert await bms.async_update() == {}

    await bms.disconnect()
