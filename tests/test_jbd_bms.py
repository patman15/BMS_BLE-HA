"""Test the JBD BMS implementation."""

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
    CMD_INFO = bytearray(b"\xA5\x03")
    CMD_CELL = bytearray(b"\xA5\x04")

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
                    b"\xdd\x03\x00\x1D\x06\x18\xFE\xE1\x01\xF2\x01\xF4\x00\x2A\x2C\x7C\x00\x00\x00"
                    b"\x00\x00\x00\x80\x64\x03\x04\x03\x0B\x8B\x0B\x8A\x0B\x84\xf8\x84\x77"
                )  # {'voltage': 15.6, 'current': -2.87, 'battery_level': 100, 'cycle_charge': 4.98, 'cycles': 42, 'temperature': 22.133333333333347}
            if bytearray(data)[1:3] == self.CMD_CELL:
                return bytearray(
                    b"\xdd\x04\x00\x08\x0d\x66\x0d\x61\x0d\x68\x0d\x59\xfe\x3c\x77"
                )  # {'cell#0': 3.43, 'cell#1': 3.425, 'cell#2': 3.432, 'cell#3': 3.417}

        return bytearray()

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

        resp = self._response(char_specifier, data)
        for notify_data in [
            resp[i : i + BT_FRAME_SIZE] for i in range(0, len(resp), BT_FRAME_SIZE)
        ]:
            self._notify_callback("MockJBDBleakClient", notify_data)


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
                    b"\xdd\x03\x00\x1D\x06\x18\xFE\xE1\x01\xF2\x01\xF4\x00\x2A\x2C\x7C\x00\x00\x00"
                    b"\x00\x00\x00\x80\x64\x03\x04\x03\x0B\x8B\x0B\x8A\x0B\x84\xf8\x84\x77"
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
        raise BleakError


async def test_update(monkeypatch, reconnect_fixture) -> None:
    """Test JBD BMS data update."""

    monkeypatch.setattr(
        "custom_components.bms_ble.plugins.basebms.BleakClient",
        MockJBDBleakClient,
    )

    bms = BMS(
        generate_ble_device("cc:cc:cc:cc:cc:cc", "MockBLEdevice", None, -73),
        reconnect_fixture,
    )

    result = await bms.async_update()

    assert result == {
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
        "cell#0": 3.43,
        "cell#1": 3.425,
        "cell#2": 3.432,
        "cell#3": 3.417,
        "temp#0": 22.4,
        "temp#1": 22.3,
        "temp#2": 21.7,
        "delta_voltage": 0.015,
    }

    # query again to check already connected state
    result = await bms.async_update()
    assert bms._client and bms._client.is_connected is not reconnect_fixture

    await bms.disconnect()


@pytest.fixture(
    name="wrong_response",
    params=[
        (
            bytearray(
                b"\xdd\x03\x00\x1D\x06\x18\xFE\xE1\x01\xF2\x01\xF4\x00\x2A\x2C\x7C\x00\x00\x00"
                b"\x00\x00\x00\x80\x64\x03\x04\x03\x0B\x8B\x0B\x8A\x0B\x84\xf8\x84\xdd"
            ),
            "wrong end",
        ),
        (bytearray(b"\xdd\x04\x00\x1d" + b"\x00" * 31 + b"\x77"), "wrong CRC"),
    ],
    ids=lambda param: param[1],
)
def response(request) -> bytearray:
    """Return faulty response frame."""
    return request.param[0]


async def test_invalid_response(monkeypatch, wrong_response) -> None:
    """Test data update with BMS returning invalid data (wrong CRC)."""

    monkeypatch.setattr(
        "custom_components.bms_ble.plugins.jbd_bms.BMS.BAT_TIMEOUT",
        0.1,
    )

    monkeypatch.setattr(
        "tests.test_jbd_bms.MockJBDBleakClient._response",
        lambda _s, _c_, d: wrong_response,
    )

    monkeypatch.setattr(
        "custom_components.bms_ble.plugins.basebms.BleakClient",
        MockJBDBleakClient,
    )

    bms = BMS(generate_ble_device("cc:cc:cc:cc:cc:cc", "MockBLEdevice", None, -73))

    with pytest.raises(TimeoutError):
        _result = await bms.async_update()

    await bms.disconnect()


async def test_oversized_response(monkeypatch) -> None:
    """Test data update with BMS returning oversized data, result shall still be ok."""

    monkeypatch.setattr(
        "custom_components.bms_ble.plugins.basebms.BleakClient",
        MockOversizedBleakClient,
    )

    bms = BMS(generate_ble_device("cc:cc:cc:cc:cc:cc", "MockBLEdevice", None, -73))

    result = await bms.async_update()

    assert result == {
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
        "cell#0": 3.43,
        "cell#1": 3.425,
        "cell#2": 3.432,
        "cell#3": 3.417,
        "temp#0": 22.4,
        "temp#1": 22.3,
        "temp#2": 21.7,
        "delta_voltage": 0.015,
    }

    await bms.disconnect()
