"""Test the ECO-WORTHY implementation."""

import asyncio
from collections.abc import Awaitable, Callable
import contextlib
from typing import Final
from uuid import UUID

from bleak.backends.characteristic import BleakGATTCharacteristic
import pytest

from custom_components.bms_ble.plugins.ecoworthy_bms import BMS, BMSsample

from .bluetooth import generate_ble_device
from .conftest import MockBleakClient


def ref_value() -> BMSsample:
    """Return reference value for mock Seplos BMS."""
    return {
        "cell_count": 4,
        "temp_sensors": 3,
        "voltage": 13.29,
        "current": -1.14,
        "battery_level": 72,
        "cycle_charge": 72.0,
        "design_capacity": 100.0,
        #        "cycles": 8,
        "temperature": 19.567,
        "cycle_capacity": 956.88,
        "power": -15.151,
        "battery_charging": False,
        "cell#0": 3.323,
        "cell#1": 3.325,
        "cell#2": 3.323,
        "cell#3": 3.322,
        "temp#0": 20.5,
        "temp#1": 19.2,
        "temp#2": 19.0,
        "delta_voltage": 0.003,
        "runtime": 227368,
        "problem": False,
        "problem_code": 0,
    }


class MockECOWBleakClient(MockBleakClient):
    """Emulate a ECO-WORTHY BMS BleakClient."""

    CMDS: Final[dict[int, bytearray]] = {
        0xA1: bytearray(b"\x00\x01\x03\x00\x8c\x00\x00\x99\x42"),
        0xA2: bytearray(b"\x00\x01\x03\x00\x8d\x00\x00\x59\x13"),
    }
    RESP: Final[dict[int, bytearray]] = {
        0xA1: bytearray(
            b"\xa1\x00\x00\x00\x65\x00\x00\x00\x00\x00\x18\x01\x03\x44\x00\x18\x00\x48\x00\x64\x05"
            b"\x31\xff\x8e\x00\x00\x27\x10\x00\x01\x00\x01\x00\x00\x00\x00\x00\x00\x00\x00\x00\x01"
            b"\x00\x02\x00\x00\xff\xff\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00"
            b"\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x21\x86"
        ),
        0xA2: bytearray(  # 4 cells, 3 temp sensors
            b"\xa2\x00\x00\x00\x65\x00\x00\x00\x00\x00\x18\x01\x03\x56\x00\x04\x0c\xfb\x0c\xfd\x0c"
            b"\xfb\x0c\xfa\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff"
            b"\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff"
            b"\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\x00\x03\x00\xcd"
            b"\x00\xc0\x00\xbe\xfc\x18\xfc\x18\xfc\x18\xfc\x18\xfc\x18\xfc\x18\x97\x6a"
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
                self._notify_callback("MockECOWBleakClient", msg)
                await asyncio.sleep(0.1)

    async def start_notify(
        self,
        char_specifier: BleakGATTCharacteristic | int | str | UUID,
        callback: Callable[
            [BleakGATTCharacteristic, bytearray], None | Awaitable[None]
        ],
        **kwargs,
    ) -> None:
        """Issue write command to GATT."""
        await super().start_notify(char_specifier, callback, **kwargs)

        self._task = asyncio.create_task(self._notify())

    async def disconnect(self) -> bool:
        """Mock disconnect and wait for send task."""
        self._task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await self._task
        return await super().disconnect()


async def test_update(patch_bleak_client, reconnect_fixture) -> None:
    """Test ECO-WORTHY BMS data update."""

    patch_bleak_client(MockECOWBleakClient)

    bms = BMS(
        generate_ble_device("cc:cc:cc:cc:cc:cc", "MockBLEdevice", None, -73),
        reconnect_fixture,
    )

    result = await bms.async_update()

    assert result == ref_value()

    # query again to check already connected state
    result = await bms.async_update()
    assert bms._client and bms._client.is_connected is not reconnect_fixture

    await bms.disconnect()


@pytest.fixture(
    name="wrong_response",
    params=[
        (
            bytearray(
                b"\xa3\x00\x00\x00\x65\x00\x00\x00\x00\x00\x18\x01\x03\x44\x00\x18\x00\x48\x00\x64"
                b"\x05\x31\xff\x8e\x00\x00\x27\x10\x00\x01\x00\x01\x00\x00\x00\x00\x00\x00\x00\x00"
                b"\x00\x01\x00\x02\x00\x00\xff\xff\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00"
                b"\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00"
                b"\x00\x00\x70\x20"
            ),
            "wrong_type",
        ),
        (
            bytearray(
                b"\xa2\x00\x00\x00\x65\x00\x00\x00\x00\x00\x18\x01\x03\x56\x00\x04\x0c\xfb\x0c\xfd"
                b"\x0c\xfb\x0c\xfa\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff"
                b"\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff"
                b"\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff"
                b"\x00\x03\x00\xcd\x00\xc0\x00\xbe\xfc\x18\xfc\x18\xfc\x18\xfc\x18\xfc\x18\xfc\x18"
                b"\x97\x6a"
            ),
            "single_type_sent",
        ),
        (
            bytearray(  # correct CRC: 0x2186
                b"\xa1\x00\x00\x00\x65\x00\x00\x00\x00\x00\x18\x01\x03\x44\x00\x18\x00\x48\x00\x64"
                b"\x05\x31\xff\x8e\x00\x00\x27\x10\x00\x01\x00\x01\x00\x00\x00\x00\x00\x00\x00\x00"
                b"\x00\x01\x00\x02\x00\x00\xff\xff\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00"
                b"\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00"
                b"\x00\x00\x21\x87"
            ),
            "wrong_CRC",
        ),
        (
            bytearray(b""),
            "empty_response",
        ),
    ],
    ids=lambda param: param[1],
)
def response(request):
    """Return faulty response frame."""
    return request.param[0]


async def test_tx_notimplemented(patch_bleak_client) -> None:
    """Test Ective BMS uuid_tx not implemented for coverage."""

    patch_bleak_client(MockECOWBleakClient)

    bms = BMS(
        generate_ble_device("cc:cc:cc:cc:cc:cc", "MockBLEDevice", None, -73), False
    )

    with pytest.raises(NotImplementedError):
        _ret: str = bms.uuid_tx()


async def test_invalid_response(
    monkeypatch, patch_bleak_client, patch_bms_timeout, wrong_response
) -> None:
    """Test data up date with BMS returning invalid data."""

    patch_bms_timeout("ecoworthy_bms")

    monkeypatch.setattr(
        MockECOWBleakClient,
        "RESP",
        {0xA1: wrong_response, 0xA2: MockECOWBleakClient.RESP[0xA2]},
    )

    patch_bleak_client(MockECOWBleakClient)

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
                b"\xa1\x00\x00\x00\x65\x00\x00\x00\x00\x00\x18\x01\x03\x44\x00\x18\x00\x48\x00\x64"
                b"\x05\x31\xff\x8e\x00\x00\x27\x10\x00\x01\x00\x01\x00\x00\x00\x00\x00\x00\x00\x00"
                b"\x00\x01\x00\x02\x00\x00\xff\xff\x00\x00\x00\x00\x01\x00\x00\x00\x00\x00\x00\x00"
                b"\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00"
                b"\x00\x00\x20\xd6"
            ),
            "first_bit",
        ),
        (
            bytearray(
                b"\xa1\x00\x00\x00\x65\x00\x00\x00\x00\x00\x18\x01\x03\x44\x00\x18\x00\x48\x00\x64"
                b"\x05\x31\xff\x8e\x00\x00\x27\x10\x00\x01\x00\x01\x00\x00\x00\x00\x00\x00\x00\x00"
                b"\x00\x01\x00\x02\x00\x00\xff\xff\x00\x00\x00\x80\x00\x00\x00\x00\x00\x00\x00\x00"
                b"\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00"
                b"\x00\x00\x20\x0e"
            ),
            "last_bit",
        ),
    ],
    ids=lambda param: param[1],
)
def prb_response(request):
    """Return faulty response frame."""
    return request.param


async def test_problem_response(
    monkeypatch, patch_bleak_client, problem_response
) -> None:
    """Test data update with BMS returning error flags."""

    monkeypatch.setattr(
        MockECOWBleakClient,
        "RESP",
        {0xA1: problem_response[0], 0xA2: MockECOWBleakClient.RESP[0xA2]},
    )

    patch_bleak_client(MockECOWBleakClient)

    bms = BMS(generate_ble_device("cc:cc:cc:cc:cc:cc", "MockBLEdevice", None, -73))

    result: BMSsample = await bms.async_update()
    assert result == ref_value() | {
        "problem": True,
        "problem_code": 1 << (0 if problem_response[1] == "first_bit" else 15),
    }

    await bms.disconnect()
