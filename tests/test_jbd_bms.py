"""Test the JBD BMS implementation."""

import asyncio
from collections.abc import Buffer
from uuid import UUID

from bleak.backends.characteristic import BleakGATTCharacteristic
from bleak.exc import BleakError
from bleak.uuids import normalize_uuid_str
import pytest

from custom_components.bms_ble.plugins.jbd_bms import BMS

from .bluetooth import generate_ble_device
from .conftest import MockBleakClient

BT_FRAME_SIZE = 20


class MockJBDBleakClient(MockBleakClient):
    """Emulate a JBD BMS BleakClient."""

    HEAD_CMD = 0xDD
    CMD_INFO = bytearray(b"\xa5\x03")
    CMD_CELL = bytearray(b"\xa5\x04")

    _tasks: set[asyncio.Task] = set()

    def _response(
        self, char_specifier: BleakGATTCharacteristic | int | str | UUID, data: Buffer
    ) -> bytearray:

        if (
            isinstance(char_specifier, str)
            and normalize_uuid_str(char_specifier) == normalize_uuid_str("ff02")
            and bytearray(data)[0] == self.HEAD_CMD
        ):
            if bytearray(data)[1:3] == self.CMD_INFO:
                return bytearray(
                    b"\xdd\x03\x00\x1d\x06\x18\xfe\xe1\x01\xf2\x01\xf4\x00\x2a\x2c\x7c\x00\x00\x00"
                    b"\x00\x00\x00\x80\x64\x03\x04\x03\x0b\x8b\x0b\x8a\x0b\x84\xf8\x84\x77"
                )  # {'voltage': 15.6, 'current': -2.87, 'battery_level': 100, 'cycle_charge': 4.98, 'cycles': 42, 'temperature': 22.133333333333347}
            if bytearray(data)[1:3] == self.CMD_CELL:
                return bytearray(
                    b"\xdd\x04\x00\x08\x0d\x66\x0d\x61\x0d\x68\x0d\x59\xfe\x3c\x77"
                )  # {'cell#0': 3.43, 'cell#1': 3.425, 'cell#2': 3.432, 'cell#3': 3.417}

        return bytearray()

    async def _send_data(self, char_specifier, data) -> None:
        assert (
            self._notify_callback
        ), "write to characteristics but notification not enabled"

        # always send two responses, to test timeout behaviour
        for resp in (
            self._response(char_specifier, bytearray(b"\xdd\xa5\x03\x00\xff\xfd\x77")),
            self._response(char_specifier, data),
        ):
            for notify_data in [
                resp[i : i + BT_FRAME_SIZE] for i in range(0, len(resp), BT_FRAME_SIZE)
            ]:
                self._notify_callback("MockJBDBleakClient", notify_data)
            await asyncio.sleep(0.01)

    async def write_gatt_char(
        self,
        char_specifier: BleakGATTCharacteristic | int | str | UUID,
        data: Buffer,
        response: bool | None = None,
    ) -> None:
        """Issue write command to GATT."""

        _task: asyncio.Task = asyncio.create_task(self._send_data(char_specifier, data))
        self._tasks.add(_task)
        _task.add_done_callback(self._tasks.discard)

    async def disconnect(self) -> bool:
        """Mock disconnect."""
        await asyncio.gather(*self._tasks)
        return await super().disconnect()


class MockOversizedBleakClient(MockJBDBleakClient):
    """Emulate a JBD BMS BleakClient returning wrong data length."""

    def _response(
        self, char_specifier: BleakGATTCharacteristic | int | str | UUID, data: Buffer
    ) -> bytearray:
        if (
            isinstance(char_specifier, str)
            and normalize_uuid_str(char_specifier) == normalize_uuid_str("ff02")
            and bytearray(data)[0] == self.HEAD_CMD
        ):
            if bytearray(data)[1:3] == self.CMD_INFO:
                return bytearray(
                    b"\xdd\x03\x00\x1d\x06\x18\xfe\xe1\x01\xf2\x01\xf4\x00\x2a\x2c\x7c\x00\x00\x00"
                    b"\x00\x00\x00\x80\x64\x03\x04\x03\x0b\x8b\x0b\x8a\x0b\x84\xf8\x84\x77"
                    b"\00\00\00\00\00\00"  # oversized response
                )  # {'voltage': 15.6, 'current': -2.87, 'battery_level': 100, 'cycle_charge': 4.98, 'cycles': 42, 'temperature': 22.133333333333347}
            if bytearray(data)[1:3] == self.CMD_CELL:
                return bytearray(
                    b"\xdd\x04\x00\x08\x0d\x66\x0d\x61\x0d\x68\x0d\x59\xfe\x3c\x77"
                    b"\00\00\00\00\00\00\00\00\00\00\00\00"  # oversized response
                )  # {'cell#0': 3.43, 'cell#1': 3.425, 'cell#2': 3.432, 'cell#3': 3.417}

        return bytearray()

    async def disconnect(self) -> bool:
        """Mock disconnect to raise BleakError."""
        if self._tasks:
            await asyncio.wait(self._tasks)
        raise BleakError


async def test_update(patch_bleak_client, reconnect_fixture) -> None:
    """Test JBD BMS data update."""

    patch_bleak_client(MockJBDBleakClient)

    bms = BMS(
        generate_ble_device("cc:cc:cc:cc:cc:cc", "MockBLEdevice", None, -73),
        reconnect_fixture,
    )

    assert await bms.async_update() == {
        "temp_sensors": 3,
        "voltage": 15.6,
        "current": -2.87,
        "battery_level": 100,
        "cycle_charge": 4.98,
        "cycles": 42,
        "temperature": 22.133,
        "cycle_capacity": 77.688,
        "power": -44.772,
        "battery_charging": False,
        "runtime": 6246,
        "cell_voltages": [3.43, 3.425, 3.432, 3.417],
        "temp_values": [22.4, 22.3, 21.7],
        "delta_voltage": 0.015,
        "problem": False,
        "problem_code": 0,
    }

    # query again to check already connected state
    await bms.async_update()
    assert bms._client and bms._client.is_connected is not reconnect_fixture

    await bms.disconnect()


@pytest.fixture(
    name="wrong_response",
    params=[
        (
            bytearray(
                b"\xdd\x03\x00\x1d\x06\x18\xfe\xe1\x01\xf2\x01\xf4\x00\x2a\x2c\x7c\x00\x00\x00"
                b"\x00\x00\x00\x80\x64\x03\x04\x03\x0b\x8b\x0b\x8a\x0b\x84\xf8\x84\xdd"
            ),
            "wrong end",
        ),
        (bytearray(b"\xdd\x04\x00\x1d" + b"\x00" * 31 + b"\x77"), "wrong CRC"),
    ],
    ids=lambda param: param[1],
)
def fix_response(request) -> bytearray:
    """Return faulty response frame."""
    return request.param[0]


async def test_invalid_response(
    monkeypatch, patch_bleak_client, patch_bms_timeout, wrong_response
) -> None:
    """Test data update with BMS returning invalid data (wrong CRC)."""

    patch_bms_timeout()

    monkeypatch.setattr(
        MockJBDBleakClient, "_response", lambda _s, _c, _d: wrong_response
    )

    patch_bleak_client(MockJBDBleakClient)

    bms = BMS(generate_ble_device("cc:cc:cc:cc:cc:cc", "MockBLEdevice", None, -73))

    with pytest.raises(TimeoutError):
        _result = await bms.async_update()

    await bms.disconnect()


async def test_oversized_response(patch_bleak_client) -> None:
    """Test data update with BMS returning oversized data, result shall still be ok."""

    patch_bleak_client(MockOversizedBleakClient)

    bms = BMS(generate_ble_device("cc:cc:cc:cc:cc:cc", "MockBLEdevice", None, -73))

    assert await bms.async_update() == {
        "temp_sensors": 3,
        "voltage": 15.6,
        "current": -2.87,
        "battery_level": 100,
        "cycle_charge": 4.98,
        "cycles": 42,
        "temperature": 22.133,
        "cycle_capacity": 77.688,
        "power": -44.772,
        "battery_charging": False,
        "runtime": 6246,
        "cell_voltages": [3.43, 3.425, 3.432, 3.417],
        "temp_values": [22.4, 22.3, 21.7],
        "delta_voltage": 0.015,
        "problem": False,
        "problem_code": 0,
    }

    await bms.disconnect()


@pytest.fixture(
    name="problem_response",
    params=[
        (
            bytearray(
                b"\xdd\x03\x00\x1d\x06\x18\xfe\xe1\x01\xf2\x01\xf4\x00\x2a\x2c\x7c\x00\x00\x00"
                b"\x00\x00\x01\x80\x64\x03\x04\x03\x0b\x8b\x0b\x8a\x0b\x84\xf8\x83\x77"
            ),
            "first_bit",
        ),
        (
            bytearray(
                b"\xdd\x03\x00\x1d\x06\x18\xfe\xe1\x01\xf2\x01\xf4\x00\x2a\x2c\x7c\x00\x00\x00"
                b"\x00\x80\x00\x80\x64\x03\x04\x03\x0b\x8b\x0b\x8a\x0b\x84\xf8\x04\x77"
            ),
            "last_bit",
        ),
    ],
    ids=lambda param: param[1],
)
def prb_response(request) -> bytearray:
    """Return faulty response frame."""
    return request.param


async def test_problem_response(
    monkeypatch, patch_bleak_client, problem_response
) -> None:
    """Test data update with BMS returning invalid data (wrong CRC)."""

    def _response(
        self,
        char_specifier: BleakGATTCharacteristic | int | str | UUID,
        data: Buffer,
        resp: bytearray = problem_response[0],
    ) -> bytearray:
        if (
            isinstance(char_specifier, str)
            and normalize_uuid_str(char_specifier) == normalize_uuid_str("ff02")
            and bytearray(data)[0] == self.HEAD_CMD
        ):
            if bytearray(data)[1:3] == self.CMD_INFO:
                return resp
            if bytearray(data)[1:3] == self.CMD_CELL:
                return bytearray(
                    b"\xdd\x04\x00\x08\x0d\x66\x0d\x61\x0d\x68\x0d\x59\xfe\x3c\x77"
                )  # {'cell#0': 3.43, 'cell#1': 3.425, 'cell#2': 3.432, 'cell#3': 3.417}

        return bytearray()

    monkeypatch.setattr(MockJBDBleakClient, "_response", _response)

    patch_bleak_client(MockJBDBleakClient)

    bms = BMS(generate_ble_device("cc:cc:cc:cc:cc:cc", "MockBLEdevice", None, -73))

    assert await bms.async_update() == {
        "temp_sensors": 3,
        "voltage": 15.6,
        "current": -2.87,
        "battery_level": 100,
        "cycle_charge": 4.98,
        "cycles": 42,
        "temperature": 22.133,
        "cycle_capacity": 77.688,
        "power": -44.772,
        "battery_charging": False,
        "runtime": 6246,
        "cell_voltages": [3.43, 3.425, 3.432, 3.417],
        "temp_values": [22.4, 22.3, 21.7],
        "delta_voltage": 0.015,
        "problem": True,
        "problem_code": 1 << (0 if problem_response[1] == "first_bit" else 15),
    }

    await bms.disconnect()
