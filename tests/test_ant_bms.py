"""Test the ANT implementation."""

import asyncio
from collections.abc import Buffer
from typing import Final
from uuid import UUID

from bleak.backends.characteristic import BleakGATTCharacteristic
import pytest

from custom_components.bms_ble.plugins.ant_bms import BMS
from custom_components.bms_ble.plugins.basebms import BMSsample

from .bluetooth import generate_ble_device
from .conftest import MockBleakClient

BT_FRAME_SIZE: Final[int] = 20  # ANT BMS frame size

_RESULT_DEFS: Final[BMSsample] = {
    "cell_count": 22,
    "temp_sensors": 4,
    "voltage": 50.88,
    "current": 2.1,
    "battery_level": 10,
    "cycle_charge": 9.957766,
    "design_capacity": 80,
    "temperature": 29.333,
    "cycle_capacity": 506.651,
    "power": 106.0,
    "battery_charging": False,
    "cell_voltages": [
        2.334,
        2.331,
        2.334,
        2.333,
        2.333,
        2.334,
        2.336,
        2.334,
        2.191,
        2.19,
        2.192,
        2.338,
        2.283,
        2.336,
        2.336,
        2.335,
        2.334,
        2.335,
        2.334,
        2.335,
        2.337,
        2.335,
    ],
    "temp_values": [29.0, 29.0, 29.0, 29.0, 30.0, 30.0],
    "delta_voltage": 0.148,
    "problem": False,
    "problem_code": 0,
}


class MockANTBleakClient(MockBleakClient):
    """Emulate a ANT BMS BleakClient."""

    CMDS: Final[dict[int, bytearray]] = {
        0x01: bytearray(b"\x7e\xa1\x01\x00\x00\xbe\x18\x55\xaa\x55"),
        0x02: bytearray(b"\x7e\xa1\x02\x6c\x02\x20\x58\xc4\xaa\x55"),
    }
    RESP: Final[dict[int, bytearray]] = {
        0x1: bytearray(
            b"\x7e\xa1\x11\x00\x00\x9e\x05\x04\x04\x16\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00"
            b"\x88\x01\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x1e\x09\x1b\x09\x1e\x09"
            b"\x1d\x09\x1d\x09\x1e\x09\x20\x09\x1e\x09\x8f\x08\x8e\x08\x90\x08\x22\x09\xeb\x08"
            b"\x20\x09\x20\x09\x1f\x09\x1e\x09\x1f\x09\x1e\x09\x1f\x09\x21\x09\x1f\x09\x1d\x00"
            b"\x1d\x00\x1d\x00\x1d\x00\x1e\x00\x1e\x00\xe0\x13\x15\x00\x0a\x00\x64\x00\x01\x01"
            b"\x00\x00\x00\xb4\xc4\x04\x86\xf1\x97\x00\x3a\xed\xe8\x00\x6a\x00\x00\x00\xa1\xf2"
            b"\xc0\x03\x00\x00\x00\x00\x22\x09\x0c\x00\x8e\x08\x0a\x00\x94\x00\x08\x09\x00\x00"
            b"\x6d\x00\x6a\x00\xaf\x02\xf3\xfa\x4c\x74\xe5\x00\x28\x66\xec\x00\xc3\x5d\x62\x00"
            b"\xcc\xb3\x92\x00\xed\xc8\xaa\x55"
        ),
        0x2: bytearray(
            b"\x7e\xa1\x12\x6c\x02\x20\x32\x34\x42\x48\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00"
            b"\x00\x00\x32\x34\x42\x48\x55\x42\x30\x30\x2d\x32\x31\x31\x30\x32\x36\x41\x57\x96"
            b"\xff\x0b\x00\x00\x41\xf2\xaa\x55"
        ),
    }

    _task: asyncio.Task

    async def _notify(self) -> None:
        """Notify function."""

        assert (
            self._notify_callback
        ), "write to characteristics but notification not enabled"

        while True:
            for msg in self.RESP.values():
                self._notify_callback("MockANTBleakClient", msg)
                await asyncio.sleep(0.1)

    async def write_gatt_char(
        self,
        char_specifier: BleakGATTCharacteristic | int | str | UUID,
        data: Buffer,
        response: bool | None = None,
    ) -> None:
        """Issue write command to GATT."""

        assert (
            self._notify_callback
        ), "write to characteristics but notification not enabled"

        resp: Final[bytearray] = self.RESP.get(int(bytes(data)[2]), bytearray())
        for notify_data in [
            resp[i : i + BT_FRAME_SIZE] for i in range(0, len(resp), BT_FRAME_SIZE)
        ]:
            self._notify_callback("MockANTBleakClient", notify_data)


async def test_update(patch_bms_timeout, patch_bleak_client, reconnect_fixture) -> None:
    """Test ANT BMS data update."""

    patch_bms_timeout()
    patch_bleak_client(MockANTBleakClient)

    bms = BMS(
        generate_ble_device("cc:cc:cc:cc:cc:cc", "MockBLEdevice", None, -73),
        reconnect_fixture,
    )

    assert await bms.async_update() == _RESULT_DEFS

    # query again to check already connected state
    await bms.async_update()
    assert bms._client and bms._client.is_connected is not reconnect_fixture

    await bms.disconnect()


@pytest.fixture(
    name="wrong_response",
    params=[
        (b"\x6e" + MockANTBleakClient.RESP[0x1][1:], "wrong_SOF"),
        (b"\x7e\xa1\x12" + MockANTBleakClient.RESP[0x1][3:], "wrong_type"),
        (b"\x7e\xa1\x1f" + MockANTBleakClient.RESP[0x1][3:], "unknown_type"),
        (
            b"\x7e\xa1\x11\x00\x00\x01" + MockANTBleakClient.RESP[0x1][6:],
            "wrong_length",
        ),
        (MockANTBleakClient.RESP[0x1][:-2] + b"\xa1\x55", "wrong_EOF"),
        (b"\x7e\xa1\x11", "too_short"),
        (MockANTBleakClient.RESP[0x1][:-4] + b"\xff\xff\xaa\x55", "wrong_CRC"),
        (bytearray(1), "empty_response"),
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
        MockANTBleakClient,
        "RESP",
        MockANTBleakClient.RESP | {0x1: wrong_response},
    )

    patch_bleak_client(MockANTBleakClient)

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
                b"\x7e\xa1\x11\x00\x00\x9e\x05\x04\x04\x16\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00"
                b"\x88\x01\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x1e\x09\x1b\x09\x1e\x09"
                b"\x1d\x09\x1d\x09\x1e\x09\x20\x09\x1e\x09\x8f\x08\x8e\x08\x90\x08\x22\x09\xeb\x08"
                b"\x20\x09\x20\x09\x1f\x09\x1e\x09\x1f\x09\x1e\x09\x1f\x09\x21\x09\x1f\x09\x1d\x00"
                b"\x1d\x00\x1d\x00\x1d\x00\x1e\x00\x1e\x00\xe0\x13\x15\x00\x0a\x00\x64\x00\x02\x02"  # \x02
                b"\x00\x00\x00\xb4\xc4\x04\x86\xf1\x97\x00\x3a\xed\xe8\x00\x6a\x00\x00\x00\xa1\xf2"
                b"\xc0\x03\x00\x00\x00\x00\x22\x09\x0c\x00\x8e\x08\x0a\x00\x94\x00\x08\x09\x00\x00"
                b"\x6d\x00\x6a\x00\xaf\x02\xf3\xfa\x4c\x74\xe5\x00\x28\x66\xec\x00\xc3\x5d\x62\x00"
                b"\xcc\xb3\x92\x00\x4d\x04\xaa\x55"
            ),
            "low_value",
        ),
        (
            bytearray(
                b"\x7e\xa1\x11\x00\x00\x9e\x05\x04\x04\x16\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00"
                b"\x88\x01\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x1e\x09\x1b\x09\x1e\x09"
                b"\x1d\x09\x1d\x09\x1e\x09\x20\x09\x1e\x09\x8f\x08\x8e\x08\x90\x08\x22\x09\xeb\x08"
                b"\x20\x09\x20\x09\x1f\x09\x1e\x09\x1f\x09\x1e\x09\x1f\x09\x21\x09\x1f\x09\x1d\x00"
                b"\x1d\x00\x1d\x00\x1d\x00\x1e\x00\x1e\x00\xe0\x13\x15\x00\x0a\x00\x64\x00\x0e\x0e"  # \x0e
                b"\x00\x00\x00\xb4\xc4\x04\x86\xf1\x97\x00\x3a\xed\xe8\x00\x6a\x00\x00\x00\xa1\xf2"
                b"\xc0\x03\x00\x00\x00\x00\x22\x09\x0c\x00\x8e\x08\x0a\x00\x94\x00\x08\x09\x00\x00"
                b"\x6d\x00\x6a\x00\xaf\x02\xf3\xfa\x4c\x74\xe5\x00\x28\x66\xec\x00\xc3\x5d\x62\x00"
                b"\xcc\xb3\x92\x00\xc8\xf6\xaa\x55"
            ),
            "high_value",
        ),
    ],
    ids=lambda param: param[1],
)
def prb_response(request) -> tuple[bytearray, str]:
    """Return faulty response frame."""
    return request.param


async def test_problem_response(
    monkeypatch, patch_bms_timeout, patch_bleak_client, problem_response
) -> None:
    """Test data update with BMS returning error flags."""

    patch_bms_timeout()
    monkeypatch.setattr(
        MockANTBleakClient,
        "RESP",
        MockANTBleakClient.RESP | {0x1: problem_response[0]},
    )

    patch_bleak_client(MockANTBleakClient)

    bms = BMS(generate_ble_device("cc:cc:cc:cc:cc:cc", "MockBLEdevice", None, -73))

    result: BMSsample = await bms.async_update()
    assert result == _RESULT_DEFS | {
        "problem": True,
        "problem_code": (0x202 if problem_response[1] == "low_value" else 0xE0E),
    }

    await bms.disconnect()
