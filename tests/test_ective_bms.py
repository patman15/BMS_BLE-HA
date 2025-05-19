"""Test the Ective BMS implementation."""

from collections.abc import Awaitable, Callable
from uuid import UUID

from bleak.backends.characteristic import BleakGATTCharacteristic
import pytest

from custom_components.bms_ble.plugins.basebms import BMSsample
from custom_components.bms_ble.plugins.ective_bms import BMS

from .bluetooth import generate_ble_device
from .conftest import MockBleakClient

BT_FRAME_SIZE = 32


class MockEctiveBleakClient(MockBleakClient):
    """Emulate a Ective BMS BleakClient."""

    def _response(self) -> bytearray:
        return bytearray(
            b"\x36\x46\x32\x00\x5e\x38\x34\x33\x35\x30\x30\x30\x30\x33\x38\x43\x44\x46\x46\x46\x46"
            b"\x32\x43\x46\x39\x30\x32\x30\x30\x39\x37\x30\x31\x36\x32\x30\x30"
            b"\x45\x31\x30\x42\x30\x30\x30\x30\x30\x30\x30\x30"
            b"\x35\x45\x30\x44\x37\x31\x30\x44\x36\x35\x30\x44\x35\x45\x30\x44"
            b"\x30\x30\x30\x30\x30\x30\x30\x30\x30\x30\x30\x30\x30\x30\x30\x30"
            b"\x30\x30\x30\x30\x30\x30\x30\x30\x30\x30\x30\x30\x30\x30\x30\x30"
            b"\x30\x30\x30\x30\x30\x30\x30\x30\x30\x30\x30\x30\x30\x30\x30\x30"
            b"\x30\x38\x38\x46\xaf\x46\x38\x33\x33\x30\x30\x30\x30\x30\x30\x30"  # \xaf garbage
            b"\x30\x30\x30\x30\x30\x00\x00\x00\x00\x00\x00\x00\x00"  # garbage
        )

    def _send_info(self) -> None:
        assert self._notify_callback is not None
        for notify_data in [
            self._response()[i : i + BT_FRAME_SIZE]
            for i in range(0, len(self._response()), BT_FRAME_SIZE)
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


async def test_update(patch_bleak_client, reconnect_fixture) -> None:
    """Test Ective BMS data update."""

    patch_bleak_client(MockEctiveBleakClient)

    bms = BMS(
        generate_ble_device("cc:cc:cc:cc:cc:cc", "MockBLEDevice", None, -73),
        reconnect_fixture,
    )

    assert await bms.async_update() == {
        "voltage": 13.7,
        "current": -13.0,
        "battery_level": 98,
        "cycles": 407,
        "cycle_charge": 194.86,
        "cell_voltages": [3.422, 3.441, 3.429, 3.422],
        "delta_voltage": 0.019,
        "temperature": 31.0,
        "cycle_capacity": 2669.582,
        "power": -178.1,
        "runtime": 53961,
        "battery_charging": False,
        "problem": False,
        "problem_code": 0,
    }

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
    monkeypatch.setattr(MockEctiveBleakClient, "_response", lambda _s: wrong_response)
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

    monkeypatch.setattr(
        MockEctiveBleakClient, "_response", lambda _s: problem_response[0]
    )

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
