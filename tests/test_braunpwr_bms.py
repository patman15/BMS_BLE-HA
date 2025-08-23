"""Test the Braun Power BMS implementation."""

import asyncio
from collections.abc import Buffer
from uuid import UUID

from bleak.backends.characteristic import BleakGATTCharacteristic
from bleak.uuids import normalize_uuid_str
import pytest

from custom_components.bms_ble.plugins.basebms import BMSsample
from custom_components.bms_ble.plugins.braunpwr_bms import BMS

from .bluetooth import generate_ble_device
from .conftest import MockBleakClient


def ref_value() -> BMSsample:
    """Return reference value for mock CBT power BMS."""
    return {
        "voltage": 53.31,
        "current": -11.45,
        "battery_level": 83,
        "cell_count": 16,
        "cycle_charge": 250.26,
        "cycles": 8,
        # "problem_code": 0,
        "cell_voltages": [
            3.327,
            3.334,
            3.333,
            3.335,
            3.333,
            3.335,
            3.333,
            3.338,
            3.332,
            3.335,
            3.334,
            3.336,
            3.333,
            3.334,
            3.336,
            3.337,
        ],
        "design_capacity": 300,
        "power": -610.399,
        "temp_sensors": 4,
        "temp_values": [
            23.0,
            23.0,
            23.0,
            23.0,
        ],
        "delta_voltage": 0.011,
        "cycle_capacity": 13341.361,
        "battery_charging": False,
        "temperature": 23.0,
        "runtime": 78684,
        "problem_code": 0,
        "problem": False,
    }


class MockBraunPWRBleakClient(MockBleakClient):
    """Emulate a Braun Power BMS BleakClient."""

    RESP: dict[int, bytearray] = {
        0x01: bytearray(
            b"\x7b\x01\x20\x00\x53\x14\xd3\x00\xd2\x00\xb4\x00\xbe\xfb\x87\x61"
            b"\xc2\x75\x30\x00\x00\x00\x00\x00\x08\x00\x00\x00\x00\x00\x0e\x00"
            b"\x00\x00\x64\x7d"
        ),
        0x02: bytearray(
            b"\x7b\x02\x21\x10\x0c\xff\x0d\x06\x0d\x05\x0d\x07\x0d\x05\x0d\x07"
            b"\x0d\x05\x0d\x0a\x0d\x04\x0d\x07\x0d\x06\x0d\x08\x0d\x05\x0d\x06"
            b"\x0d\x08\x0d\x09\x7d"
        ),
        0x03: bytearray(b"{\x03\x09\x04\x0b\x91\x0b\x91\x0b\x91\x0b\x91}"),
        0x08: bytearray(
            b"\x7b\x08\x16\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00"
            b"\x00\x00\x00\x00\x00\x00\x00\x00\x00\x7d"
        ),
        0x09: bytearray(b"\x7b\x09\x03\xff\xff\xff\x7d"),
        0x74: bytearray(
            b"\x7b\x74\x1d\x4b\x53\x5f\x42\x4c\x45\x5f\x57\x49\x46\x49\x5f\x56"
            b"\x65\x72\x31\x2e\x30\x2e\x30\x5f\x32\x30\x32\x34\x30\x33\x31\x33\x7d"
        ),
        0x78: bytearray(b"\x7b\x78\x02\x00\x23\x7d"),
        0xF4: bytearray(b"\x7b\xf4\x03\x02\x03\x01\x7d"),
        0xF5: bytearray(b"\x7b\xf5\x02\x02\x39\x7d"),
    }

    def _response(
        self, char_specifier: BleakGATTCharacteristic | int | str | UUID, cmd: int
    ) -> bytearray:
        if isinstance(char_specifier, str) and normalize_uuid_str(
            char_specifier
        ) != normalize_uuid_str("ff02"):
            return bytearray()

        return self.RESP.get(cmd, bytearray())

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
            "MockABCBleakClient", self._response(char_specifier, bytes(data)[1])
        )
        await asyncio.sleep(0)


async def test_update(patch_bleak_client, reconnect_fixture: bool) -> None:
    """Test ABC BMS data update."""

    patch_bleak_client(MockBraunPWRBleakClient)

    bms = BMS(
        generate_ble_device("cc:cc:cc:cc:cc:cc", "MockBLEDevice", None, -73),
        reconnect_fixture,
    )

    assert await bms.async_update() == ref_value()

    # query again to check already connected state
    await bms.async_update()
    assert bms._client.is_connected is not reconnect_fixture

    await bms.disconnect()


@pytest.fixture(
    name="wrong_response",
    params=[
        # (
        #     b"!\x03\x09\x04\x0b\x91\x0b\x91\x0b\x91\x0b\x91}",
        #     "wrong_SOF",
        # ),
        (
            b"!\x03\x09\x04\x0b\x91\x0b\x91\x0b\x91\x0b\x91",
            "wrong_EOF",
        ),
        (
            b"{\x04\x09\x04\x0b\x91\x0b\x91\x0b\x91\x0b\x91}",
            "unknown_CMD",
        ),
        (
            b"{\x02\x09\x04\x0b\x91\x0b\x91\x0b\x91\x0b\x91}",
            "wrong_CMD",
        ),
        (
            b"{\x03\x08\x04\x0b\x91\x0b\x91\x0b\x91\x0b\x91}",
            "wrong_length",
        ),
    ],
    ids=lambda param: param[1],
)
def fix_response(request) -> bytearray:
    """Return faulty response frame."""
    return bytearray(request.param[0])


async def test_invalid_response(
    monkeypatch, patch_bleak_client, patch_bms_timeout, wrong_response: bytearray
) -> None:
    """Test data up date with BMS returning invalid data."""

    patch_bms_timeout()

    monkeypatch.setattr(
        MockBraunPWRBleakClient,
        "RESP",
        MockBraunPWRBleakClient.RESP | {0x03: wrong_response},
    )

    patch_bleak_client(MockBraunPWRBleakClient)

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
            b"\x7b\x01\x20\x00\x53\x14\xd3\x00\xd2\x00\xb4\x00\xbe\xfb\x87\x61\xc2\x75\x30\x00\x00"
            b"\x00\x00\x00\x08\x00\x00\x00\x00\x00\x0e\x80\x00\x00\x64\x7d",
            0x8000,
            "first_bit",
        ),
        (
            b"\x7b\x01\x20\x00\x53\x14\xd3\x00\xd2\x00\xb4\x00\xbe\xfb\x87\x61\xc2\x75\x30\x00\x00"
            b"\x00\x00\x00\x08\x00\x00\x00\x00\x00\x0e\x00\x02\x00\x64\x7d",
            0x02,
            "last_bit",
        ),
        (
            b"\x7b\x01\x20\x00\x53\x14\xd3\x00\xd2\x00\xb4\x00\xbe\xfb\x87\x61\xc2\x75\x30\x00\x00"
            b"\x00\x00\x00\x08\x00\x00\x00\x00\x00\x0e\xFF\xFE\x00\x64\x7d",
            0xFFFE,
            "all_bits_set",
        ),
    ],
    ids=lambda param: param[2],
)
def prb_response(request) -> tuple[bytearray, str]:
    """Return faulty response frame."""
    return request.param


async def test_problem_response(
    monkeypatch, patch_bleak_client, problem_response: tuple[bytearray, int, str]
) -> None:
    """Test data update with BMS returning error flags."""

    monkeypatch.setattr(
        MockBraunPWRBleakClient,
        "RESP",
        MockBraunPWRBleakClient.RESP | {0x1: bytearray(problem_response[0])},
    )

    patch_bleak_client(MockBraunPWRBleakClient)

    bms = BMS(generate_ble_device("cc:cc:cc:cc:cc:cc", "MockBLEdevice", None, -73))

    result: BMSsample = await bms.async_update()
    assert result.get("problem", False)  # expect a problem report
    assert result.get("problem_code", 0) == problem_response[1]

    await bms.disconnect()
