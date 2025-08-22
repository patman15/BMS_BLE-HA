"""Test the Ective BMS implementation."""

from collections.abc import Awaitable, Callable
from typing import Final
from uuid import UUID

from bleak.backends.characteristic import BleakGATTCharacteristic
import pytest

from custom_components.bms_ble.plugins.basebms import BMSsample
from custom_components.bms_ble.plugins.ective_bms import BMS

from .bluetooth import generate_ble_device
from .conftest import MockBleakClient

BT_FRAME_SIZE = 32

_PROTO_DEFS: Final[dict[int, bytearray]] = {
    0x5E: bytearray(
        b"\x36\x46\x32\x00\x5e\x38\x34\x33\x35\x30\x30\x30\x30\x46\x38\x43\x44\x46\x46\x46\x46"
        b"\x32\x43\x46\x39\x30\x32\x30\x30\x39\x37\x30\x31\x36\x32\x30\x30"
        b"\x45\x31\x30\x42\x30\x30\x30\x30\x30\x30\x30\x30"
        b"\x35\x45\x30\x44\x37\x31\x30\x44\x36\x35\x30\x44\x35\x45\x30\x44"
        b"\x30\x30\x30\x30\x30\x30\x30\x30\x30\x30\x30\x30\x30\x30\x30\x30"
        b"\x30\x30\x30\x30\x30\x30\x30\x30\x30\x30\x30\x30\x30\x30\x30\x30"
        b"\x30\x30\x30\x30\x30\x30\x30\x30\x30\x30\x30\x30\x30\x30\x30\x30"
        b"\x30\x39\x34\x46\xaf\x46\x38\x33\x33\x30\x30\x30\x30\x30\x30\x30"  # \xaf garbage
        b"\x30\x30\x30\x30\x30\x00\x00\x00\x00\x00\x00\x00\x00"  # garbage
    ),
    0x83: bytearray(
        b"\x836234000076FEFFFF888A010016006200530B008007B4160D170D190D1C0D00000000000000000000000000000000000000000000000007C2\x11\x11\x11\x11\x11\x11\x11\x11"
    ),
}

_RESULT_DEFS: Final[dict[int, BMSsample]] = {
    0x5E: {
        "voltage": 13.7,
        "current": -12.808,
        "battery_level": 98,
        "cycles": 407,
        "cycle_charge": 194.86,
        "cell_voltages": [3.422, 3.441, 3.429, 3.422],
        "delta_voltage": 0.019,
        "temperature": 31.0,
        "cycle_capacity": 2669.582,
        "power": -175.47,
        "runtime": 54770,
        "battery_charging": False,
        "problem": False,
        "problem_code": 0,
    },
    0x83: {
        "voltage": 13.41,
        "current": -0.394,
        "battery_level": 98,
        "cycles": 22,
        "cycle_charge": 101,
        "cell_voltages": [3.35, 3.351, 3.353, 3.356],
        "delta_voltage": 0.006,
        "temperature": 16.8,
        "cycle_capacity": 1354.41,
        "power": -5.284,
        "runtime": 922842,
        "battery_charging": False,
        "problem": False,
        "problem_code": 0,
    },
}


@pytest.fixture(
    name="protocol_type",
    params=[0x5E, 0x83],
)
def proto(request: pytest.FixtureRequest) -> str:
    """Protocol fixture."""
    return request.param


class MockEctiveBleakClient(MockBleakClient):
    """Emulate a Ective BMS BleakClient."""

    _RESP: bytearray = _PROTO_DEFS[0x5E]

    def _send_info(self) -> None:
        assert self._notify_callback is not None
        for notify_data in [
            self._RESP[i : i + BT_FRAME_SIZE]
            for i in range(0, len(self._RESP), BT_FRAME_SIZE)
        ]:
            self._notify_callback("MockEctiveBleakClient", notify_data)

    @property
    def is_connected(self) -> bool:
        """Mock connected."""
        if self._connected:
            self._send_info()  # patch to provide data when not reconnecting
        return self._connected

    async def start_notify(
        self,
        char_specifier: BleakGATTCharacteristic | int | str | UUID,
        callback: Callable[
            [BleakGATTCharacteristic, bytearray], None | Awaitable[None]
        ],
        **kwargs,
    ) -> None:
        """Mock start_notify."""
        await super().start_notify(char_specifier, callback)
        self._send_info()


async def test_update(
    monkeypatch, patch_bleak_client, protocol_type, reconnect_fixture
) -> None:
    """Test Ective BMS data update."""

    monkeypatch.setattr(MockEctiveBleakClient, "_RESP", _PROTO_DEFS[protocol_type])
    patch_bleak_client(MockEctiveBleakClient)

    bms = BMS(
        generate_ble_device("cc:cc:cc:cc:cc:cc", "MockBLEDevice", None, -73),
        reconnect_fixture,
    )

    assert await bms.async_update() == _RESULT_DEFS[protocol_type]

    # query again to check already connected state
    await bms.async_update()
    assert bms._client.is_connected is not reconnect_fixture

    await bms.disconnect()


async def test_tx_notimplemented(patch_bleak_client) -> None:
    """Test Ective BMS uuid_tx not implemented for coverage."""

    patch_bleak_client(MockEctiveBleakClient)

    bms = BMS(
        generate_ble_device("cc:cc:cc:cc:cc:cc", "MockBLEDevice", None, -73), False
    )

    with pytest.raises(NotImplementedError):
        _ret = bms.uuid_tx()


@pytest.fixture(
    name="wrong_response",
    params=[
        (
            b"\x5e\x38\x34\x33\x35\x30\x30\x30\x30\x33\x38\x43\x44\x46\x46\x46\x46"
            b"\x32\x43\x46\x39\x30\x32\x30\x30\x39\x37\x30\x31\x36\x32\x30\x30"
            b"\x45\x31\x30\x42\x30\x30\x30\x30\x30\x30\x30\x30"
            b"\x35\x45\x30\x44\x37\x31\x30\x44\x36\x35\x30\x44\x35\x45\x30\x44"
            b"\x30\x30\x30\x30\x30\x30\x30\x30\x30\x30\x30\x30\x30\x30\x30\x30"
            b"\x30\x30\x30\x30\x30\x30\x30\x30\x30\x30\x30\x30\x30\x30\x30\x30"
            b"\x30\x30\x30\x30\x30\x30\x30\x30\x30\x30\x30\x30\x30\x30\x30\x30"
            b"\x30\x38\x38\x45\x00\x00\x00\x00\x00\x00\x00\x00",
            "wrong_CRC",
        ),
        (
            b"\x5a\x38\x34\x33\x35\x30\x30\x30\x30\x33\x38\x43\x44\x46\x46\x46\x46"
            b"\x32\x43\x46\x39\x30\x32\x30\x30\x39\x37\x30\x31\x36\x32\x30\x30"
            b"\x45\x31\x30\x42\x30\x30\x30\x30\x30\x30\x30\x30"
            b"\x35\x45\x30\x44\x37\x31\x30\x44\x36\x35\x30\x44\x35\x45\x30\x44"
            b"\x30\x30\x30\x30\x30\x30\x30\x30\x30\x30\x30\x30\x30\x30\x30\x30"
            b"\x30\x30\x30\x30\x30\x30\x30\x30\x30\x30\x30\x30\x30\x30\x30\x30"
            b"\x30\x30\x30\x30\x30\x30\x30\x30\x30\x30\x30\x30\x30\x30\x30\x30"
            b"\x30\x38\x38\x46\x00\x00\x00\x00\x00\x00\x00\x00",
            "wrong_SOF",
        ),
        (
            b"\x5e\x34\x33\x35\x30\x30\x30\x30\x33\x38\x43\x44\x46\x46\x46\x46"
            b"\x32\x43\x46\x39\x30\x32\x30\x30\x39\x37\x30\x31\x36\x32\x30\x30"
            b"\x45\x31\x30\x42\x30\x30\x30\x30\x30\x30\x30\x30"
            b"\x35\x45\x30\x44\x37\x31\x30\x44\x36\x35\x30\x44\x35\x45\x30\x44"
            b"\x30\x30\x30\x30\x30\x30\x30\x30\x30\x30\x30\x30\x30\x30\x30\x30"
            b"\x30\x30\x30\x30\x30\x30\x30\x30\x30\x30\x30\x30\x30\x30\x30\x30"
            b"\x30\x30\x30\x30\x30\x30\x30\x30\x30\x30\x30\x30\x30\x30\x30\x30"
            b"\x30\x38\x38\x46",
            "wrong_length",  # 1st byte missing
        ),
        (
            b"\x5e\x5e\x34\x33\x35\x30\x30\x30\x30\x33\x38\x43\x44\x46\x46\x46\x46"
            b"\x32\x43\x46\x39\x30\x32\x30\x30\x39\x37\x30\x31\x36\x32\x30\x30"
            b"\x45\x31\x30\x42\x30\x30\x30\x30\x30\x30\x30\x30"
            b"\x35\x45\x30\x44\x37\x31\x30\x44\x36\x35\x30\x44\x35\x45\x30\x44"
            b"\x30\x30\x30\x30\x30\x30\x30\x30\x30\x30\x30\x30\x30\x30\x30\x30"
            b"\x30\x30\x30\x30\x30\x30\x30\x30\x30\x30\x30\x30\x30\x30\x30\x30"
            b"\x30\x30\x30\x30\x30\x30\x30\x30\x30\x30\x30\x30\x30\x30\x30\x30"
            b"\x30\x38\x38\x46",
            "wrong_character",
        ),
    ],
    ids=lambda param: param[1],
)
def response(request) -> bytearray:
    """Return faulty response frame."""
    return request.param[0]


async def test_invalid_response(
    monkeypatch, patch_bleak_client, patch_bms_timeout, wrong_response
) -> None:
    """Test data up date with BMS returning invalid data."""

    patch_bms_timeout("ective_bms")
    monkeypatch.setattr(MockEctiveBleakClient, "_RESP", bytearray(wrong_response))
    patch_bleak_client(MockEctiveBleakClient)

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
                b"\x5e\x38\x34\x33\x35\x30\x30\x30\x30\x33\x38\x43\x44\x46\x46\x46\x46"
                b"\x32\x43\x46\x39\x30\x32\x30\x30\x39\x37\x30\x31\x36\x32\x30\x30"
                b"\x45\x31\x30\x42\x30\x31\x30\x30\x30\x30\x30\x30"
                b"\x35\x45\x30\x44\x37\x31\x30\x44\x36\x35\x30\x44\x35\x45\x30\x44"
                b"\x30\x30\x30\x30\x30\x30\x30\x30\x30\x30\x30\x30\x30\x30\x30\x30"
                b"\x30\x30\x30\x30\x30\x30\x30\x30\x30\x30\x30\x30\x30\x30\x30\x30"
                b"\x30\x30\x30\x30\x30\x30\x30\x30\x30\x30\x30\x30\x30\x30\x30\x30"
                b"\x30\x38\x39\x30"
            ),
            "first_bit",
        ),
        (
            bytearray(
                b"\x5e\x38\x34\x33\x35\x30\x30\x30\x30\x33\x38\x43\x44\x46\x46\x46\x46"
                b"\x32\x43\x46\x39\x30\x32\x30\x30\x39\x37\x30\x31\x36\x32\x30\x30"
                b"\x45\x31\x30\x42\x38\x30\x30\x30\x30\x30\x30\x30"
                b"\x35\x45\x30\x44\x37\x31\x30\x44\x36\x35\x30\x44\x35\x45\x30\x44"
                b"\x30\x30\x30\x30\x30\x30\x30\x30\x30\x30\x30\x30\x30\x30\x30\x30"
                b"\x30\x30\x30\x30\x30\x30\x30\x30\x30\x30\x30\x30\x30\x30\x30\x30"
                b"\x30\x30\x30\x30\x30\x30\x30\x30\x30\x30\x30\x30\x30\x30\x30\x30"
                b"\x30\x39\x30\x46"
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

    monkeypatch.setattr(MockEctiveBleakClient, "_RESP", bytearray(problem_response[0]))

    patch_bleak_client(MockEctiveBleakClient)

    bms = BMS(generate_ble_device("cc:cc:cc:cc:cc:cc", "MockBLEdevice", None, -73))

    result: BMSsample = await bms.async_update()
    assert result == {
        "voltage": 13.7,
        "current": -13.0,
        "battery_level": 98,
        "cycles": 407,
        "cycle_charge": 194.86,
        "cell_voltages": [
            3.422,
            3.441,
            3.429,
            3.422,
        ],
        "delta_voltage": 0.019,
        "temperature": 31.0,
        "cycle_capacity": 2669.582,
        "power": -178.1,
        "runtime": 53961,
        "battery_charging": False,
        "problem": True,
        "problem_code": (1 if problem_response[1] == "first_bit" else 128),
    }

    await bms.disconnect()
