"""Test the CBT power BMS implementation."""

from collections.abc import Buffer
from uuid import UUID

from bleak.backends.characteristic import BleakGATTCharacteristic
from bleak.exc import BleakError
from bleak.uuids import normalize_uuid_str
import pytest

from custom_components.bms_ble.const import BMSsample
from custom_components.bms_ble.plugins.cbtpwr_bms import BMS

from .bluetooth import generate_ble_device
from .conftest import MockBleakClient


def ref_value() -> BMSsample:
    """Return reference value for mock CBT power BMS."""
    return {
        "voltage": 13.4,
        "current": -3.14,
        "battery_level": 100,
        "cycles": 3,
        "cycle_charge": 40.0,
        "cell#0": 3.339,
        "cell#1": 3.339,
        "cell#2": 3.338,
        "cell#3": 3.338,
        "cell#4": 2.317,
        "delta_voltage": 1.022,
        "temperature": -2,
        "cycle_capacity": 536.0,
        "design_capacity": 40,
        "power": -42.076,
        "runtime": 22608,
        "battery_charging": False,
        "problem": False,
        "problem_code": 0,
    }


class MockCBTpwrBleakClient(MockBleakClient):
    """Emulate a CBT power BMS BleakClient."""

    RESP: dict[int, bytearray] = {
        0x05: bytearray(
            b"\xaa\x55\x05\x0a\x0b\x0d\x0b\x0d\x0a\x0d\x0a\x0d\x0d\x09\x83\x0d\x0a"
        ),  # cell voltage info (5 cells)
        0x06: bytearray(
            b"\xaa\x55\x06\x0a\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x10\x0d\x0a"
        ),  # cell voltage info (no additional cells)
        0x09: bytearray(
            b"\xaa\x55\x09\x0c\xfe\xff\xfe\xff\x00\x00\x00\x00\x00\x00\x00\x00\x0f\x0d\x0a"
        ),  # temperature frame
        0x0B: bytearray(
            b"\xaa\x55\x0b\x08\x58\x34\x00\x00\xbc\xf3\xff\xff\x4c\x0d\x0a"
        ),  # voltage/current frame
        0x0A: bytearray(
            b"\xaa\x55\x0a\x06\x64\x13\x0d\x00\x00\x00\x94\x0d\x0a"
        ),  # capacity frame
        0x0C: bytearray(
            b"\xaa\x55\x0c\x0c\x00\x00\x00\x00\x5b\x06\x00\x00\x03\x00\x74\x02\xf2\x0d\x0a"
        ),  # runtime info frame, 6.28h*100
        0x15: bytearray(
            b"\xaa\x55\x15\x04\x28\x00\x03\x00\x44\x0d\x0a"
        ),  # cycle info frame
        0x21: bytearray(
            b"\xaa\x55\x21\x04\x00\x00\x00\x00\x25\x0d\x0a"
        ),  # warnings frame
    }

    def _response(
        self, char_specifier: BleakGATTCharacteristic | int | str | UUID, data: Buffer
    ) -> bytearray:
        if isinstance(char_specifier, str) and normalize_uuid_str(
            char_specifier
        ) != normalize_uuid_str("ffe9"):
            return bytearray()
        cmd: int = int(bytearray(data)[2])
        assert bytearray(data)[4] == cmd, "incorrect CRC"
        if cmd in (0x07, 0x08):
            pytest.fail("only 5 cells available, do not query.")

        return self.RESP.get(cmd, bytearray())

    async def write_gatt_char(
        self,
        char_specifier: BleakGATTCharacteristic | int | str | UUID,
        data: Buffer,
        response: bool = None,  # noqa: RUF013 # same as upstream
    ) -> None:
        """Issue write command to GATT."""
        await super().write_gatt_char(char_specifier, data, response)

        assert self._notify_callback is not None

        self._notify_callback(
            "MockCBTpwrBleakClient", self._response(char_specifier, data)
        )


class MockInvalidBleakClient(MockCBTpwrBleakClient):
    """Emulate a CBT power BMS BleakClient."""

    RESP: dict[int, bytearray] = {
        0x09: bytearray(b"\x12\x34\x00\x00\x00\x56\x78"),  # invalid start/end
        0x0A: bytearray(
            b"\xaa\x55\x0b\x08\x58\x34\x00\x00\xbc\xf3\xff\xff\x4c\x0d\x0a"
        ),  # wrong answer to capacity req (0xA) with 0xB: voltage, cur -> pwr, charging
        0x0B: bytearray(b"invalid_len"),  # invalid length
        0x15: bytearray(b"\xaa\x55\x15\x04\x00\x00\x00\x00\x00\x0d\x0a"),  # wrong CRC
        0x21: bytearray(0),  # empty frame
    }

    async def disconnect(self) -> bool:
        """Mock disconnect to raise BleakError."""
        raise BleakError


class MockPartBaseDatBleakClient(MockCBTpwrBleakClient):
    """Emulate a CBT power BMS BleakClient."""

    RESP: dict[int, bytearray] = {
        0x0B: bytearray(
            b"\xaa\x55\x0b\x08\x58\x34\x00\x00\x00\x00\x00\x00\x9f\x0d\x0a"
        )  # voltage/current frame, positive current
    }


class MockAllCellsBleakClient(MockCBTpwrBleakClient):
    """Emulate a CBT power BMS BleakClient."""

    RESP: dict[int, bytearray] = {
        0x05: bytearray(
            b"\xaa\x55\x05\x0a\x0b\x0d\x0a\x0d\x09\x0d\x08\x0d\x07\x0d\x7d\x0d\x0a"
        ),
        0x06: bytearray(
            b"\xaa\x55\x06\x0a\x06\x0d\x05\x0d\x04\x0d\x03\x0d\x02\x0d\x65\x0d\x0a"
        ),
        0x07: bytearray(
            b"\xaa\x55\x07\x0a\x01\x0d\x00\x0d\xff\x0c\xfe\x0c\xfd\x0c\x4a\x0d\x0a"
        ),
        0x08: bytearray(
            b"\xaa\x55\x08\x0a\xfc\x0c\xfb\x0c\xfa\x0c\xf9\x0c\xf8\x0c\x30\x0d\x0a"
        ),
        0x09: bytearray(
            b"\xaa\x55\x09\x0c\x15\x00\x15\x00\x00\x00\x00\x00\x00\x00\x00\x00\x3f\x0d\x0a"
        ),  # temperature frame
        0x0B: bytearray(
            b"\xaa\x55\x0b\x08\x58\x34\x00\x00\xbc\xf3\xff\xff\x4c\x0d\x0a"
        ),  # voltage/current frame
        0x15: bytearray(
            b"\xaa\x55\x15\x04\x28\x00\x03\x00\x44\x0d\x0a"
        ),  # cycle info frame
        0x0A: bytearray(
            b"\xaa\x55\x0a\x06\x64\x13\x0d\x00\x00\x00\x94\x0d\x0a"
        ),  # capacity frame
        0x0C: bytearray(
            b"\xaa\x55\x0c\x0c\x00\x00\x00\x00\x5b\x06\x00\x00\x03\x00\x74\x02\xf2\x0d\x0a"
        ),  # runtime info frame, 6.28h*100
        0x21: bytearray(
            b"\xaa\x55\x21\x04\x00\x00\x00\x00\x25\x0d\x0a"
        ),  # warnings frame
    }

    def _response(
        self, char_specifier: BleakGATTCharacteristic | int | str | UUID, data: Buffer
    ) -> bytearray:
        if isinstance(char_specifier, str) and normalize_uuid_str(
            char_specifier
        ) != normalize_uuid_str("ffe9"):
            return bytearray()
        cmd: int = int(bytearray(data)[2])

        return self.RESP.get(cmd, bytearray())


async def test_update(patch_bleak_client, reconnect_fixture: bool) -> None:
    """Test CBT power BMS data update."""

    patch_bleak_client(MockCBTpwrBleakClient)

    bms = BMS(
        generate_ble_device("cc:cc:cc:cc:cc:cc", "MockBLEDevice", None, -73),
        reconnect_fixture,
    )

    result = await bms.async_update()

    assert result == ref_value()

    # query again to check already connected state
    result = await bms.async_update()
    assert bms._client.is_connected is not reconnect_fixture

    await bms.disconnect()


async def test_invalid_response(patch_bleak_client, patch_bms_timeout) -> None:
    """Test data update with BMS returning invalid data."""

    patch_bms_timeout("cbtpwr_bms")
    patch_bleak_client(MockInvalidBleakClient)

    bms = BMS(generate_ble_device("cc:cc:cc:cc:cc:cc", "MockBLEDevice", None, -73))

    result = await bms.async_update()
    assert result == {
        "battery_charging": False,
        "current": -3.14,
        "power": -42.076,
        "voltage": 13.4,
        "problem": False,
    }

    await bms.disconnect()


async def test_partly_base_data(patch_bleak_client, patch_bms_timeout) -> None:
    """Test data update with BMS returning invalid data."""

    patch_bms_timeout("cbtpwr_bms")
    patch_bleak_client(MockPartBaseDatBleakClient)

    bms = BMS(generate_ble_device("cc:cc:cc:cc:cc:cc", "MockBLEDevice", None, -73))

    result = await bms.async_update()
    assert result == {
        "battery_charging": False,
        "current": 0.0,
        "power": 0.0,
        "voltage": 13.4,
        "problem": False,
    }

    await bms.disconnect()


async def test_all_cell_voltages(patch_bleak_client, patch_bms_timeout) -> None:
    """Test data update with BMS returning invalid data."""

    patch_bms_timeout("cbtpwr_bms")
    patch_bleak_client(MockAllCellsBleakClient)

    bms = BMS(generate_ble_device("cc:cc:cc:cc:cc:cc", "MockBLEDevice", None, -73))

    result = await bms.async_update()
    assert result == {
        "voltage": 13.4,
        "current": -3.14,
        "battery_level": 100,
        "cycles": 3,
        "cycle_charge": 40.0,
        "cell#0": 3.339,
        "cell#1": 3.338,
        "cell#2": 3.337,
        "cell#3": 3.336,
        "cell#4": 3.335,
        "cell#5": 3.334,
        "cell#6": 3.333,
        "cell#7": 3.332,
        "cell#8": 3.331,
        "cell#9": 3.330,
        "cell#10": 3.329,
        "cell#11": 3.328,
        "cell#12": 3.327,
        "cell#13": 3.326,
        "cell#14": 3.325,
        "cell#15": 3.324,
        "cell#16": 3.323,
        "cell#17": 3.322,
        "cell#18": 3.321,
        "cell#19": 3.320,
        "delta_voltage": 0.019,
        "temperature": 21,
        "cycle_capacity": 536.0,
        "design_capacity": 40,
        "power": -42.076,
        "runtime": 22608,
        "battery_charging": False,
        "problem": False,
        "problem_code": 0,
    }

    await bms.disconnect()


@pytest.fixture(
    name="problem_response",
    params=[
        (
            {0x21: bytearray(b"\xaa\x55\x21\x04\x01\x00\x00\x00\x26\x0d\x0a")},
            "first_bit",
        ),
        (
            {0x21: bytearray(b"\xaa\x55\x21\x04\x00\x00\x00\x80\xa5\x0d\x0a")},
            "last_bit",
        ),
    ],
    ids=lambda param: param[1],
)
def prb_response(request) -> tuple[dict[int, bytearray], str]:
    """Return faulty response frame."""
    return request.param


async def test_problem_response(
    monkeypatch, patch_bleak_client, problem_response: tuple[dict[int, bytearray], str]
) -> None:
    """Test data update with BMS returning error flags."""

    monkeypatch.setattr(  # patch response dictionary to only problem reports (no other data)
        MockCBTpwrBleakClient, "RESP", MockCBTpwrBleakClient.RESP | problem_response[0]
    )

    patch_bleak_client(MockCBTpwrBleakClient)

    bms = BMS(generate_ble_device("cc:cc:cc:cc:cc:cc", "MockBLEdevice", None, -73))

    result: BMSsample = await bms.async_update()
    assert result == ref_value() | {
        "problem": True,
        "problem_code": 1 << (0 if problem_response[1] == "first_bit" else 31),
    }

    await bms.disconnect()
