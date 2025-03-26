"""Test the ABC BMS implementation."""

import asyncio
from collections.abc import Buffer
from uuid import UUID

from bleak.backends.characteristic import BleakGATTCharacteristic
from bleak.uuids import normalize_uuid_str
import pytest

from custom_components.bms_ble.plugins.abc_bms import BMS, BMSsample

from .bluetooth import generate_ble_device
from .conftest import MockBleakClient


class MockABCBleakClient(MockBleakClient):
    """Emulate a ABC BMS BleakClient."""

    RESP: dict[int, bytearray] = {
        0xF0: bytearray(
            b"\xcc\xf0\xa2\x6b\x00\x00\x00\x00\xa0\x86\x01\x40\x9e\x01\x07\x00\x63\x00\x00\x21"
        ),
        0xF1: bytearray(
            b"\xcc\xf1\x53\x4f\x4b\x2d\x42\x4d\x53\x0d\x00\x00\x00\x00\x00\x00\x00\x00\x00\x40"
        ),
        0xF2: bytearray(
            b"\xcc\xf2\x01\x01\x01\x14\x00\x00\x00\x00\x00\x00\x00\x02\x00\x00\x00\x00\x00\x7f"
        ),
        0xF3: bytearray(
            b"\xcc\xf3\x17\x03\x12\x00\x64\x00\x00\x01\x00\x00\x00\x00\x00\x00\x00\x00\x00\x36"
        ),
        0xF41: bytearray(
            b"\xcc\xf4\x01\x72\x0d\x00\x02\xa8\x0d\x00\x03\x2f\x0d\x00\x04\x88\x0d\x00\x00\x8b"
        ),  #           ^^ 1B idx, 3B voltage
        0xF45: bytearray(
            b"\xcc\xf4\x05\x81\x0d\x00\x06\x65\x0d\x00\x07\x1f\x0d\x00\x08\x5c\x0d\x00\x00\x33"
        ),
        0xF5: bytearray(
            b"\xcc\xf5\x42\x0e\x10\x0e\xc4\x09\xf6\x09\xa0\x86\x01\xa0\x86\x01\x00\x00\x00\x55"
        ),
        0xF6: bytearray(
            b"\xcc\xf6\x10\x72\x00\x80\x70\x00\x37\x00\x32\x00\x00\x00\x05\x00\x00\x00\x00\x23"
        ),
        0xF7: bytearray(
            b"\xcc\xf7\x20\x4e\x00\x40\x51\x00\x4b\x00\x46\x00\xec\xff\xf1\xff\x00\x00\x00\x8f"
        ),
        0xF8: bytearray(
            b"\xcc\xf8\x00\x64\x00\x80\x57\x00\x80\x70\x00\x10\x27\x00\x00\x00\x00\x00\x00\x3e"
        ),
        0xF9: bytearray(
            b"\xcc\xf9\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\xed"
        ),
        0xFA: bytearray(
            b"\xcc\xfa\x48\x0d\x14\x00\x0f\x27\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\xd6"
        ),
    }

    def _response(
        self, char_specifier: BleakGATTCharacteristic | int | str | UUID, cmd: int
    ) -> bytearray:
        if isinstance(char_specifier, str) and normalize_uuid_str(
            char_specifier
        ) != normalize_uuid_str("ffe2"):
            return bytearray()

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

        for cmd in {  # determine which responses to command
            0xC0: [0xF1],
            0xC1: [0xF0, 0xF2],
            0xC2: [0xF0, 0xF3, 0xF41, 0xF45],
            0xC3: [0xF5, 0xF6, 0xF7, 0xF8, 0xFA],
            0xC4: [0xF9],
        }.get(bytearray(data)[1], []):
            self._notify_callback(
                "MockABCBleakClient", self._response(char_specifier, cmd)
            )
            await asyncio.sleep(0)


async def test_update(patch_bleak_client, reconnect_fixture: bool) -> None:
    """Test ABC BMS data update."""

    patch_bleak_client(MockABCBleakClient)

    bms = BMS(
        generate_ble_device("cc:cc:cc:cc:cc:cc", "MockBLEDevice", None, -73),
        reconnect_fixture,
    )

    result = await bms.async_update()

    assert result == {
        "temp_sensors": 1,
        "voltage": 27.554,
        "current": 0.0,
        "battery_level": 99,
        "cycle_charge": 106.048,
        "cycles": 7,
        "problem_code": 0,
        "cell#0": 3.442,
        "cell#1": 3.496,
        "cell#2": 3.375,
        "cell#3": 3.464,
        "cell#4": 3.457,
        "cell#5": 3.429,
        "cell#6": 3.359,
        "cell#7": 3.42,
        "temp#0": 20,
        "delta_voltage": 0.137,
        "cycle_capacity": 2922.047,
        "power": 0.0,
        "battery_charging": False,
        "temperature": 20.0,
        "problem": False,
    }

    # query again to check already connected state
    result = await bms.async_update()
    assert bms._client.is_connected is not reconnect_fixture

    await bms.disconnect()


@pytest.fixture(
    name="wrong_response",
    params=[
        (
            b"\xcc\xf0\xa2\x6b\x00\x00\x00\x00\xa0\x86\x01\x40\x9e\x01\x07\x00\x63\x00\x00\x20",
            "wrong_CRC",
        ),
        (
            b"\xc0\xf0\xa2\x6b\x00\x00\x00\x00\xa0\x86\x01\x40\x9e\x01\x07\x00\x63\x00\x00\x21",
            "wrong_SOF",
        ),
        (
            b"\xcc\xfe\xa2\x6b\x00\x00\x00\x00\xa0\x86\x01\x40\x9e\x01\x07\x00\x63\x00\x00\x4f",
            "wrong_CMD",
        ),
        (
            b"\xcc\xf0\xa2\x6b\x00\x00\x00\x00\xa0\x86\x01\x40\x9e\x01\x07\x00\x63\x00\x21",
            "wrong_length",
        ),
    ],
    ids=lambda param: param[1],
)
def response(request) -> bytearray:
    """Return faulty response frame."""
    return bytearray(request.param[0])


async def test_invalid_response(
    monkeypatch, patch_bleak_client, patch_bms_timeout, wrong_response: bytearray
) -> None:
    """Test data up date with BMS returning invalid data."""

    patch_bms_timeout("abc_bms")

    monkeypatch.setattr(
        MockABCBleakClient,
        "RESP",
        MockABCBleakClient.RESP | {0xF0: wrong_response},
    )

    patch_bleak_client(MockABCBleakClient)

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
            b"\xcc\xf9\x69\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x1d",
            "first_bit",
        ),
        (
            b"\xcc\xf9\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x69\x00\x05",
            "last_bit",
        ),
    ],
    ids=lambda param: param[1],
)
def prb_response(request) -> tuple[bytearray, str]:
    """Return faulty response frame."""
    return request.param


async def test_problem_response(
    monkeypatch, patch_bleak_client, problem_response: tuple[bytearray, str]
) -> None:
    """Test data update with BMS returning error flags."""

    monkeypatch.setattr(
        MockABCBleakClient,
        "RESP",
        MockABCBleakClient.RESP | {0xF9: bytearray(problem_response[0])},
    )

    patch_bleak_client(MockABCBleakClient)

    bms = BMS(generate_ble_device("cc:cc:cc:cc:cc:cc", "MockBLEdevice", None, -73))

    result: BMSsample = await bms.async_update()
    assert result.get("problem", False)  # expect a problem report
    assert result.get("problem_code", 0) == (
        0x1 if problem_response[1] == "first_bit" else 0x8000
    )

    await bms.disconnect()
