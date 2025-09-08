"""Test the Neey BMS implementation."""

import asyncio
from collections.abc import Buffer
from copy import deepcopy
from typing import Final
from uuid import UUID

from bleak.backends.characteristic import BleakGATTCharacteristic

# from bleak.uuids import normalize_uuid_str, uuidstr_to_str
import pytest

from custom_components.bms_ble.plugins.basebms import BMSsample
from custom_components.bms_ble.plugins.neey_bms import BMS

from .bluetooth import generate_ble_device
from .conftest import MockBleakClient

BT_FRAME_SIZE = 29

_PROTO_DEFS: Final[dict[str, bytearray]] = {
    "dev": bytearray(
        b"\x55\xaa\x11\x01\x01\x00\x64\x00\x47\x57\x2d\x32\x34\x53\x34\x45\x42\x00\x00\x00"
        b"\x00\x00\x00\x00\x48\x57\x2d\x32\x2e\x38\x2e\x30\x5a\x48\x2d\x31\x2e\x32\x2e\x33"
        b"\x56\x31\x2e\x30\x2e\x30\x00\x00\x32\x30\x32\x32\x30\x35\x33\x31\x05\x00\x00\x00"
        b"\x01\x91\x0a\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00"
        b"\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\xab\xff"
    ),
    "ack": bytearray(
        # b"\xaa\x55\x90\xeb\xc8\x01\x01\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x44\x41"
        # b"\x54\x0d\x0a"
    ),  # ACKnowledge message with attached AT\r\n message (needs to be filtered)
    "cell": bytearray(
        b"\x55\xaa\x11\x01\x02\x00\x2c\x01\x38\xe7\xfa\x50\x40\xb6\x04\x51\x40\x85\x0e\x51"
        b"\x40\xf0\x05\x51\x40\xb6\x04\x51\x40\x75\x1e\x51\x40\x7f\x4f\x51\x40\x43\x02\x51"
        b"\x40\x1c\x3d\x51\x40\x78\x6a\x51\x40\xfe\x82\x51\x40\x16\x7e\x51\x40\xbc\x76\x51"
        b"\x40\x16\x7e\x51\x40\x8b\x80\x51\x40\xca\x66\x51\x40\x00\x00\x00\x00\x00\x00\x00"
        b"\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00"
        b"\x00\x00\x00\x00\x00\x35\x93\x24\x3e\x68\x94\x26\x3e\x3d\x25\x1b\x3e\x90\x8e\x1b"
        b"\x3e\xb3\xf3\x23\x3e\x2e\x91\x25\x3e\xc6\x1b\x1a\x3e\x4a\x7c\x1c\x3e\x6f\x1b\x1a"
        b"\x3e\xc2\x43\x1b\x3e\x85\x1e\x18\x3e\x4b\x27\x19\x3e\x5e\xdf\x18\x3e\xd0\xeb\x1a"
        b"\x3e\xe6\xd4\x18\x3e\x0c\xfe\x18\x3e\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00"
        b"\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00"
        b"\x00\xde\x40\x51\x42\xde\x40\x51\x40\x00\x17\x08\x3c\x0a\x00\x0f\x05\x19\xa1\x82"
        b"\xc0\xc3\xf5\x48\x42\xc3\xf5\x48\x42\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00"
        b"\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x76\x2e\x09\x00\x00\x00"
        b"\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00"
        b"\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\xb6\xff"
    ),
}

_RESULT_DEFS: Final[BMSsample] = {
    "delta_voltage": 0.008,
    "temperature": 50.24,
    "voltage": 52.313,
    "balance_current": -4.082,
    "cell_voltages": [
        3.265,
        3.266,
        3.267,
        3.266,
        3.266,
        3.267,
        3.27,
        3.266,
        3.269,
        3.272,
        3.274,
        3.273,
        3.273,
        3.273,
        3.273,
        3.272,
    ],
    "temp_values": [50.24, 50.24],
    "problem": False,
    "problem_code": 0,
}


class MockNeeyBleakClient(MockBleakClient):
    """Emulate a Neey BMS BleakClient."""

    HEAD_CMD: Final = bytearray(b"\xaa\x55\x11\x01")
    DEV_INFO: Final = bytearray(b"\x01")
    CELL_INFO: Final = bytearray(b"\x02")
    TAIL: Final = 0xFF
    _FRAME: dict[str, bytearray] = {}

    _task: asyncio.Task | None = None

    def _response(
        self, char_specifier: BleakGATTCharacteristic | int | str | UUID, data: Buffer
    ) -> bytearray:
        frame: Final[bytearray] = bytearray(data)
        if (
            char_specifier != "ffe1"
            or frame[19] != self.TAIL
            or not frame.startswith(self.HEAD_CMD)
        ):
            return bytearray()
        if frame[4:5] == self.CELL_INFO:
            return self._FRAME["cell"]
        if frame[4:5] == self.DEV_INFO:
            return self._FRAME["dev"]

        return bytearray()

    async def _send_confirm(self) -> None:
        assert self._notify_callback, "send confirm called but notification not enabled"
        await asyncio.sleep(0)
        self._notify_callback(
            "MockNeeyBleakClient",
            b"\xaa\x55\x90\xeb\xc8\x01\x01\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x44",
        )

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

        resp: Final[bytearray] = self._response(char_specifier, data)
        for notify_data in [
            resp[i : i + BT_FRAME_SIZE] for i in range(0, len(resp), BT_FRAME_SIZE)
        ]:
            self._notify_callback("MockNeeyBleakClient", notify_data)


class MockStreamBleakClient(MockNeeyBleakClient):
    """Mock Neey BMS that already sends battery data (no request required)."""

    async def _send_all(self) -> None:
        assert (
            self._notify_callback
        ), "send_all frames called but notification not enabled"
        for resp in self._FRAME.values():
            self._notify_callback("MockNeeyBleakClient", resp)
            await asyncio.sleep(0)

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
        if bytearray(data).startswith(
            self.HEAD_CMD + self.DEV_INFO
        ):  # send all responses as a series
            self._task = asyncio.create_task(self._send_all())

    async def disconnect(self) -> bool:
        """Mock disconnect and wait for send task."""
        if self._task and not self._task.done():
            await asyncio.wait_for(self._task, 0.1)
            assert self._task.done(), "send task still running!"
        return await super().disconnect()


class MockOversizedBleakClient(MockNeeyBleakClient):
    """Emulate a Neey BMS BleakClient returning wrong data length."""

    def _response(
        self, char_specifier: BleakGATTCharacteristic | int | str | UUID, data: Buffer
    ) -> bytearray:

        return super()._response(char_specifier, data) + bytearray(6)


@pytest.mark.asyncio
async def test_update(monkeypatch, patch_bleak_client, keep_alive_fixture) -> None:
    """Test Neey BMS data update."""

    monkeypatch.setattr(MockNeeyBleakClient, "_FRAME", _PROTO_DEFS)

    patch_bleak_client(MockNeeyBleakClient)

    bms = BMS(
        generate_ble_device("cc:cc:cc:cc:cc:cc", "MockBLEdevice", None, -73),
        keep_alive_fixture,
    )

    assert await bms.async_update() == _RESULT_DEFS

    # query again to check already connected state
    assert await bms.async_update() == _RESULT_DEFS
    assert bms._client and bms._client.is_connected is keep_alive_fixture

    await bms.disconnect()


async def test_stream_update(
    monkeypatch, patch_bleak_client, keep_alive_fixture
) -> None:
    """Test Neey BMS data update."""

    monkeypatch.setattr(MockStreamBleakClient, "_FRAME", _PROTO_DEFS)
    patch_bleak_client(MockStreamBleakClient)
    monkeypatch.setattr(  # mock that response has already been received
        "custom_components.bms_ble.plugins.basebms.asyncio.Event.is_set", lambda _: True
    )

    bms = BMS(
        generate_ble_device("cc:cc:cc:cc:cc:cc", "MockBLEdevice", None, -73),
        keep_alive_fixture,
    )

    assert await bms.async_update() == _RESULT_DEFS

    # query again to check already connected state
    assert await bms.async_update() == _RESULT_DEFS
    assert bms._client and bms._client.is_connected is keep_alive_fixture

    await bms.disconnect()


@pytest.fixture(
    name="wrong_response",
    params=[
        (_PROTO_DEFS["dev"][:-2] + b"\x00\xff", "wrong_CRC"),
        (b"\x55\xaa\xeb\x90\x05" + bytes(295), "wrong_frame_type"),
        (_PROTO_DEFS["dev"][:-1] + b"\x00", "wrong_EOF"),
    ],
    ids=lambda param: param[1],
)
def faulty_response(request) -> bytearray:
    """Return faulty response frame."""
    return request.param[0]


async def test_invalid_response(
    monkeypatch, patch_bleak_client, patch_bms_timeout, wrong_response
) -> None:
    """Test data up date with BMS returning invalid data."""

    patch_bms_timeout()
    monkeypatch.setattr(
        MockNeeyBleakClient, "_response", lambda _s, _c, _d: wrong_response
    )
    patch_bleak_client(MockNeeyBleakClient)

    bms = BMS(generate_ble_device("cc:cc:cc:cc:cc:cc", "MockBLEDevice", None, -73))

    result: BMSsample = {}
    with pytest.raises(TimeoutError):
        result = await bms.async_update()

    assert not result
    await bms.disconnect()


async def test_oversized_response(monkeypatch, patch_bleak_client) -> None:
    """Test data update with BMS returning oversized data, result shall still be ok."""

    monkeypatch.setattr(MockOversizedBleakClient, "_FRAME", _PROTO_DEFS)

    patch_bleak_client(MockOversizedBleakClient)

    bms = BMS(generate_ble_device("cc:cc:cc:cc:cc:cc", "MockBLEdevice", None, -73))

    assert await bms.async_update() == _RESULT_DEFS

    await bms.disconnect()


async def test_non_stale_data(
    monkeypatch, patch_bleak_client, patch_bms_timeout
) -> None:
    """Test if BMS class is reset if connection is reset."""

    patch_bms_timeout()

    monkeypatch.setattr(MockNeeyBleakClient, "_FRAME", _PROTO_DEFS)

    orig_response = MockNeeyBleakClient._response
    monkeypatch.setattr(
        MockNeeyBleakClient,
        "_response",
        lambda _s, _c, _d: bytearray(b"\x55\xaa\xeb\x90\x05")
        + bytearray(10),  # invalid frame type (0x5)
    )

    patch_bleak_client(MockNeeyBleakClient)

    bms = BMS(generate_ble_device("cc:cc:cc:cc:cc:cc", "MockBLEdevice", None, -73))

    # run an update which provides half a valid message and then disconnects
    result: BMSsample = {}
    with pytest.raises(TimeoutError):
        result = await bms.async_update()
    assert not result
    await bms.disconnect()

    # restore working BMS responses and run a test again to see if stale data is kept
    monkeypatch.setattr(MockNeeyBleakClient, "_response", orig_response)

    assert await bms.async_update() == _RESULT_DEFS


@pytest.fixture(
    name="problem_response",
    params=[
        (0x01, "Wrong cell count"),
        # (0x02, "AcqLine Res test"),
        (0x03, "AcqLine Res exceed"),
        # (0x04, "Systest Completed"),
        # (0x05, "Balancing"),
        # (0x06, "Balancing finished"),
        (0x07, "Low voltage"),
        (0x08, "System Overtemp"),
        (0x09, "Host fails"),
        (0x0A, "Low battery voltage - balancing stopped"),
        (0x0B, "Temperature too high - balancing stopped"),
        # (0x0C, "Self-test completed"),
    ],
    ids=lambda param: param[1],
)
def prb_response(request) -> bytearray:
    """Return faulty response frame."""
    return request.param


async def test_problem_response(
    monkeypatch, patch_bleak_client, problem_response
) -> None:
    """Test data update with BMS returning system problem flags."""

    def frame_update(data: bytearray, update: int) -> None:
        data[-2] = (data[-2] + update - data[216]) & 0xFF
        data[216] = update

    protocol_def: dict[str, bytearray] = deepcopy(_PROTO_DEFS)
    # set error flags in the copy

    frame_update(
        protocol_def["cell"],
        problem_response[0],
    )

    monkeypatch.setattr(MockNeeyBleakClient, "_FRAME", protocol_def)

    patch_bleak_client(MockNeeyBleakClient)

    bms = BMS(
        generate_ble_device("cc:cc:cc:cc:cc:cc", "MockBLEdevice", None, -73), False
    )

    assert await bms.async_update() == _RESULT_DEFS | {
        "problem": True,
        "problem_code": problem_response[0],
    }

    await bms.disconnect()
