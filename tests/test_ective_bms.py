"""Test the Ective BMS implementation."""

from collections.abc import Awaitable, Callable
from uuid import UUID

from bleak.backends.characteristic import BleakGATTCharacteristic
import pytest

from custom_components.bms_ble.plugins.ective_bms import BMS

from .bluetooth import generate_ble_device
from .conftest import MockBleakClient

BT_FRAME_SIZE = 32


class MockEctiveBleakClient(MockBleakClient):
    """Emulate a Ective BMS BleakClient."""

    def _response(self) -> bytearray:
        return bytearray(
            b"\x00\x5E\x38\x34\x33\x35\x30\x30\x30\x30\x33\x38\x43\x44\x46\x46\x46\x46"
            b"\x32\x43\x46\x39\x30\x32\x30\x30\x39\x37\x30\x31\x36\x32\x30\x30"
            b"\x45\x31\x30\x42\x30\x30\x30\x30\x30\x30\x30\x30"
            b"\x35\x45\x30\x44\x37\x31\x30\x44\x36\x35\x30\x44\x35\x45\x30\x44"
            b"\x30\x30\x30\x30\x30\x30\x30\x30\x30\x30\x30\x30\x30\x30\x30\x30"
            b"\x30\x30\x30\x30\x30\x30\x30\x30\x30\x30\x30\x30\x30\x30\x30\x30"
            b"\x30\x30\x30\x30\x30\x30\x30\x30\x30\x30\x30\x30\x30\x30\x30\x30"
            b"\x30\x38\x38\x46\x00\x00\x00\x00\x00\x00\x00\x00"
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


async def test_update(monkeypatch, reconnect_fixture) -> None:
    """Test Ective BMS data update."""

    monkeypatch.setattr(
        "custom_components.bms_ble.plugins.basebms.BleakClient",
        MockEctiveBleakClient,
    )

    bms = BMS(
        generate_ble_device("cc:cc:cc:cc:cc:cc", "MockBLEDevice", None, -73),
        reconnect_fixture,
    )

    result = await bms.async_update()

    assert result == {
        "voltage": 13.7,
        "current": -13.0,
        "battery_level": 98,
        "cycles": 407,
        "cycle_charge": 194.86,
        "cell#0": 3.422,
        "cell#1": 3.441,
        "cell#2": 3.429,
        "cell#3": 3.422,
        "delta_voltage": 0.019,
        "temperature": 31.0,
        "cycle_capacity": 2669.582,
        "power": -178.1,
        "runtime": 53961,
        "battery_charging": False,
    }

    # query again to check already connected state
    result = await bms.async_update()
    assert bms._client.is_connected is not reconnect_fixture  # noqa: SLF001

    await bms.disconnect()


async def test_tx_notimplemented(monkeypatch) -> None:
    """Test Ective BMS uuid_tx not implemented for coverage."""

    monkeypatch.setattr(
        "custom_components.bms_ble.plugins.basebms.BleakClient", MockEctiveBleakClient
    )

    bms = BMS(
        generate_ble_device("cc:cc:cc:cc:cc:cc", "MockBLEDevice", None, -73), False
    )

    with pytest.raises(NotImplementedError):
        _ret = bms.uuid_tx()


@pytest.fixture(
    name="wrong_response",
    params=[
        (
            b"\x5E\x38\x34\x33\x35\x30\x30\x30\x30\x33\x38\x43\x44\x46\x46\x46\x46"
            b"\x32\x43\x46\x39\x30\x32\x30\x30\x39\x37\x30\x31\x36\x32\x30\x30"
            b"\x45\x31\x30\x42\x30\x30\x30\x30\x30\x30\x30\x30"
            b"\x35\x45\x30\x44\x37\x31\x30\x44\x36\x35\x30\x44\x35\x45\x30\x44"
            b"\x30\x30\x30\x30\x30\x30\x30\x30\x30\x30\x30\x30\x30\x30\x30\x30"
            b"\x30\x30\x30\x30\x30\x30\x30\x30\x30\x30\x30\x30\x30\x30\x30\x30"
            b"\x30\x30\x30\x30\x30\x30\x30\x30\x30\x30\x30\x30\x30\x30\x30\x30"
            b"\x30\x38\x38\x45\x00\x00\x00\x00\x00\x00\x00\x00",
            "wrong CRC",
        ),
        (
            b"\x5A\x38\x34\x33\x35\x30\x30\x30\x30\x33\x38\x43\x44\x46\x46\x46\x46"
            b"\x32\x43\x46\x39\x30\x32\x30\x30\x39\x37\x30\x31\x36\x32\x30\x30"
            b"\x45\x31\x30\x42\x30\x30\x30\x30\x30\x30\x30\x30"
            b"\x35\x45\x30\x44\x37\x31\x30\x44\x36\x35\x30\x44\x35\x45\x30\x44"
            b"\x30\x30\x30\x30\x30\x30\x30\x30\x30\x30\x30\x30\x30\x30\x30\x30"
            b"\x30\x30\x30\x30\x30\x30\x30\x30\x30\x30\x30\x30\x30\x30\x30\x30"
            b"\x30\x30\x30\x30\x30\x30\x30\x30\x30\x30\x30\x30\x30\x30\x30\x30"
            b"\x30\x38\x38\x46\x00\x00\x00\x00\x00\x00\x00\x00",
            "wrong SOF",
        ),
        (
            b"\x5E\x34\x33\x35\x30\x30\x30\x30\x33\x38\x43\x44\x46\x46\x46\x46"
            b"\x32\x43\x46\x39\x30\x32\x30\x30\x39\x37\x30\x31\x36\x32\x30\x30"
            b"\x45\x31\x30\x42\x30\x30\x30\x30\x30\x30\x30\x30"
            b"\x35\x45\x30\x44\x37\x31\x30\x44\x36\x35\x30\x44\x35\x45\x30\x44"
            b"\x30\x30\x30\x30\x30\x30\x30\x30\x30\x30\x30\x30\x30\x30\x30\x30"
            b"\x30\x30\x30\x30\x30\x30\x30\x30\x30\x30\x30\x30\x30\x30\x30\x30"
            b"\x30\x30\x30\x30\x30\x30\x30\x30\x30\x30\x30\x30\x30\x30\x30\x30"
            b"\x30\x38\x38\x46",
            "wrong length",  # 1st byte missing
        ),
    ],
    ids=lambda param: param[1],
)
def response(request) -> bytearray:
    """Return faulty response frame."""
    return request.param[0]


async def test_invalid_response(monkeypatch, wrong_response) -> None:
    """Test data up date with BMS returning invalid data."""

    monkeypatch.setattr(
        "custom_components.bms_ble.plugins.ective_bms.BMS.BAT_TIMEOUT",
        0.1,
    )

    monkeypatch.setattr(
        "tests.test_ective_bms.MockEctiveBleakClient._response",
        lambda _s: wrong_response,
    )

    monkeypatch.setattr(
        "custom_components.bms_ble.plugins.basebms.BleakClient",
        MockEctiveBleakClient,
    )

    bms = BMS(generate_ble_device("cc:cc:cc:cc:cc:cc", "MockBLEDevice", None, -73))

    result = {}
    with pytest.raises(TimeoutError):
        result = await bms.async_update()

    assert not result
    await bms.disconnect()
