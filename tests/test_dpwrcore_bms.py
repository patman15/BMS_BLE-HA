"""Test the D-powercore BMS implementation."""

from collections.abc import Buffer
from uuid import UUID

from bleak.backends.characteristic import BleakGATTCharacteristic
from bleak.exc import BleakError
from bleak.uuids import normalize_uuid_str
import pytest

from custom_components.bms_ble.plugins.basebms import BMSsample
from custom_components.bms_ble.plugins.dpwrcore_bms import BMS

from .bluetooth import generate_ble_device
from .conftest import MockBleakClient


@pytest.fixture(
    name="dev_name",
    params=["TBA-MockBLEDevice_C0FE", "DXB-MockBLEDevice_C0FE", "invalid"],
    ids=["TBA", "DXB", "wrong"],
)
def patch_dev_name(request) -> str:
    """Provide device name variants."""
    return request.param


class MockDPwrcoreBleakClient(MockBleakClient):
    """Emulate a D-powercore BMS BleakClient."""

    PAGE_LEN = 20

    def _response(
        self, char_specifier: BleakGATTCharacteristic | int | str | UUID, data: Buffer
    ) -> bytearray:
        if isinstance(char_specifier, str) and normalize_uuid_str(
            char_specifier
        ) != normalize_uuid_str("fff3"):
            return bytearray()
        cmd: int = int(bytearray(data)[5])
        if cmd == 0x60:
            return bytearray(
                b"\x12\x12\x3a\x05\x03\x60\x00\x0a\x02\x13\x00\x00\x71\xc5\x45\x8e\x3d\x00\x02\xcd"
                b"\x02\x22\x0d\x0a\x03\x60\x00\x0a\x02\x13\x00\x00\x71\xc5\x45\x8e\x3d\x00\x02\xcd"
            )  # 2nd line only 4 bytes valid! TODO: put numbers
        if cmd == 0x61:
            return bytearray(
                b"\x12\x12\x3a\x05\x03\x61\x00\x0c\x00\x12\x00\x12\x6d\x60\x0b\x7e\x8f\xdb\x18\x20"
                b"\x04\x22\x03\x91\x0d\x0a\x00\x0c\x00\x12\x00\x12\x6d\x60\x0b\x7e\x8f\xdb\x18\x20"
            )  # 2nd line only 6 bytes valid! TODO: put numbers
        if cmd == 0x62:
            return bytearray(
                b"\x12\x13\x3a\x05\x03\x62\x00\x1d\x0e\x0e\xd7\x0e\xd6\x0e\xd6\x0e\xd5\x0e\xd5\x0e"
                b"\x12\x23\xd6\x0e\xd1\x0e\xd2\x0e\xd5\x0e\xd6\x0e\xd4\x0e\xd8\x0e\xd7\x0e\xdb\x0d"
                b"\x03\x33\x08\x0d\x0a\x0e\xd2\x0e\xd5\x0e\xd6\x0e\xd4\x0e\xd8\x0e\xd7\x0e\xdb\x0d"
            )  # 2nd line only 5 bytes valid TODO: put numbers
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
        response: bool | None = None,
    ) -> None:
        """Issue write command to GATT."""
        data_ba = bytearray(data)
        await super().write_gatt_char(char_specifier, data, response)
        if data_ba[0] & 0x80:  # ignore ACK messages # TODO: verify those?
            return
        assert self._notify_callback is not None
        resp: bytearray = self._response(char_specifier, data)
        await self._notify_callback(  # send acknowledge
            "MockPwrcoreBleakClient", bytearray([data_ba[0] | 0x80]) + data_ba[1:]
        )
        for pos in range(1 + int((len(resp) - 1) / self.PAGE_LEN)):
            await self._notify_callback(
                "MockPwrcoreBleakClient", resp[pos * 20 :][: self.PAGE_LEN]
            )


class MockWrongCRCBleakClient(MockDPwrcoreBleakClient):
    """Emulate a D-powercore BMS BleakClient that replies with wrong CRC."""

    def _response(
        self, char_specifier: BleakGATTCharacteristic | int | str | UUID, data: Buffer
    ) -> bytearray:
        if isinstance(char_specifier, str) and normalize_uuid_str(
            char_specifier
        ) != normalize_uuid_str("fff3"):
            return bytearray()
        cmd: int = int(bytearray(data)[5])
        if cmd == 0x60:
            return bytearray(
                b"\x12\x12\x3a\x05\x03\x60\x00\x0a\x02\x13\x00\x00\x71\xc5\x45\x8e\x3d\x00\x01\xce"
                b"\x02\x22\x0d\x0a\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00"
            )  # wrong CRC [0x01CE != 0x02CD] in line 1
        if cmd == 0x61:
            return bytearray(
                b"\x12\x12\x3a\x05\x03\x61\x00\x0c\x00\x12\x00\x12\x6d\x60\x0b\x7e\x8f\xdb\x18\x20"
                b"\x04\x22\x02\x91\x0d\x0a\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00"
            )  # wrong CRC [0x02 != 0x03] in line 2
        if cmd == 0x62:
            return bytearray(
                b"\x12\x13\x3a\x05\x03\x62\x00\x1d\x0e\x0e\xd7\x0e\xd6\x0e\xd6\x0e\xd5\x0e\xd5\x0e"
                b"\x12\x23\xd6\x0e\xd1\x0e\xd2\x0e\xd5\x0e\xd6\x0e\xd4\x0e\xd8\x0e\xd7\x0e\xdb\x0e"
                b"\x03\x33\x08\x0d\x0a\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00"
            )  # wrong CRC [0x0E != 0x0D] in line 2
        return bytearray()


class MockInvalidBleakClient(MockDPwrcoreBleakClient):
    """Emulate a D-powercore BMS BleakClient replying garbage."""

    def _response(
        self, char_specifier: BleakGATTCharacteristic | int | str | UUID, data: Buffer
    ) -> bytearray:
        if isinstance(char_specifier, str) and normalize_uuid_str(
            char_specifier
        ) == normalize_uuid_str("fff3"):
            return bytearray(b"invalid_value")

        return bytearray()

    async def disconnect(self) -> bool:
        """Mock disconnect to raise BleakError."""
        raise BleakError


class MockProblemBleakClient(MockDPwrcoreBleakClient):
    """Emulate a D-powercore BMS BleakClient reporting a problem."""

    def _response(
        self, char_specifier: BleakGATTCharacteristic | int | str | UUID, data: Buffer
    ) -> bytearray:
        if isinstance(char_specifier, str) and normalize_uuid_str(
            char_specifier
        ) != normalize_uuid_str("fff3"):
            return bytearray()
        cmd: int = int(bytearray(data)[5])
        if cmd == 0x60:
            return bytearray(
                b"\x12\x12\x3a\x05\x03\x60\x00\x0a\x02\x13\x00\x00\x71\xc5\x45\x8e\x3d\xff\x03\xcc"
                b"\x02\x22\x0d\x0a\x03\x60\x00\x0a\x02\x13\x00\x00\x71\xc5\x45\x8e\x3d\x00\x03\xcc"
            )  # 2nd line only 4 bytes valid!

        return super()._response(char_specifier, data)


async def test_update(patch_bleak_client, dev_name, reconnect_fixture) -> None:
    """Test D-pwercore BMS data update."""

    patch_bleak_client(MockDPwrcoreBleakClient)

    bms = BMS(
        generate_ble_device("cc:cc:cc:cc:cc:cc", dev_name, None, -73),
        reconnect_fixture,
    )

    assert await bms.async_update() == {
        "voltage": 53.1,
        "current": 0,
        "battery_level": 61.0,
        "cycles": 18,
        "cycle_charge": 17.806,
        "cell_voltages": [
            3.799,
            3.798,
            3.798,
            3.797,
            3.797,
            3.798,
            3.793,
            3.794,
            3.797,
            3.798,
            3.796,
            3.800,
            3.799,
            3.803,
        ],
        "cell_count": 14,
        "delta_voltage": 0.01,
        "temperature": 21.1,
        "cycle_capacity": 945.499,
        "power": 0.0,
        "battery_charging": False,
        "problem": False,
        "problem_code": 0,
    }

    # query again to check already connected state
    await bms.async_update()
    assert bms._client.is_connected is not reconnect_fixture

    await bms.disconnect()


async def test_invalid_response(
    patch_bleak_client, patch_bms_timeout, dev_name
) -> None:
    """Test data update with BMS returning invalid data."""

    patch_bms_timeout()
    patch_bleak_client(MockInvalidBleakClient)

    bms = BMS(generate_ble_device("cc:cc:cc:cc:cc:cc", dev_name, None, -73))

    result: BMSsample = {}
    with pytest.raises(TimeoutError):
        result = await bms.async_update()

    assert not result

    await bms.disconnect()


async def test_wrong_crc(patch_bleak_client, patch_bms_timeout, dev_name) -> None:
    """Test data update with BMS returning invalid data."""

    patch_bms_timeout()
    patch_bleak_client(MockWrongCRCBleakClient)

    bms = BMS(generate_ble_device("cc:cc:cc:cc:cc:cc", dev_name, None, -73))

    result: BMSsample = {}
    with pytest.raises(TimeoutError):
        result = await bms.async_update()

    assert not result

    await bms.disconnect()


async def test_problem_response(patch_bleak_client, dev_name) -> None:
    """Test D-pwercore BMS data update."""

    patch_bleak_client(MockProblemBleakClient)

    bms = BMS(generate_ble_device("cc:cc:cc:cc:cc:cc", dev_name, None, -73), False)

    assert await bms.async_update() == {
        "voltage": 53.1,
        "current": 0,
        "battery_level": 61.0,
        "cycles": 18,
        "cycle_charge": 17.806,
        "cell_voltages": [
            3.799,
            3.798,
            3.798,
            3.797,
            3.797,
            3.798,
            3.793,
            3.794,
            3.797,
            3.798,
            3.796,
            3.800,
            3.799,
            3.803,
        ],
        "cell_count": 14,
        "delta_voltage": 0.01,
        "temperature": 21.1,
        "cycle_capacity": 945.499,
        "power": 0.0,
        "battery_charging": False,
        "problem": True,
        "problem_code": 255,
    }

    await bms.disconnect()
