"""Test the CBT power BMS implementation."""

from collections.abc import Buffer
from uuid import UUID

from bleak.backends.characteristic import BleakGATTCharacteristic
from bleak.exc import BleakError
from bleak.uuids import normalize_uuid_str
import pytest

from custom_components.bms_ble.plugins.cbtpwr_bms import BMS

from .bluetooth import generate_ble_device
from .conftest import MockBleakClient


class MockCBTpwrBleakClient(MockBleakClient):
    """Emulate a CBT power BMS BleakClient."""

    def _response(
        self, char_specifier: BleakGATTCharacteristic | int | str | UUID, data: Buffer
    ) -> bytearray:
        if isinstance(char_specifier, str) and normalize_uuid_str(
            char_specifier
        ) != normalize_uuid_str("ffe9"):
            return bytearray()
        cmd: int = int(bytearray(data)[2])
        assert bytearray(data)[4] == cmd, "incorrect CRC"
        if cmd in (0x07, 0x08):
            pytest.fail("only 5 cells available, do not query.")
        resp: dict[int, bytearray] = {
            0x05: bytearray(
                b"\xAA\x55\x05\x0A\x0B\x0D\x0B\x0D\x0A\x0D\x0A\x0D\x0D\x09\x83\x0D\x0A"
            ),  # cell voltage info (5 cells)
            0x06: bytearray(
                b"\xAA\x55\x06\x0A\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x10\x0D\x0A"
            ),  # cell voltage info (no additional cells)
            0x09: bytearray(
                b"\xAA\x55\x09\x0C\xFE\xFF\xFE\xFF\x00\x00\x00\x00\x00\x00\x00\x00\x0F\x0D\x0A"
            ),  # temperature frame
            0x0B: bytearray(
                b"\xAA\x55\x0B\x08\x58\x34\x00\x00\xBC\xF3\xFF\xFF\x4C\x0D\x0A"
            ),  # voltage/current frame
            0x0A: bytearray(
                b"\xAA\x55\x0A\x06\x64\x13\x0D\x00\x00\x00\x94\x0D\x0A"
            ),  # capacity frame
            0x0C: bytearray(
                b"\xAA\x55\x0C\x0C\x00\x00\x00\x00\x5B\x06\x00\x00\x03\x00\x74\x02\xF2\x0D\x0A"
            ),  # runtime info frame, 6.28h*100
            0x15: bytearray(
                b"\xAA\x55\x15\x04\x28\x00\x03\x00\x44\x0D\x0A"
            ),  # cycle info frame
            0x21: bytearray(
                b"\xAA\x55\x21\x04\x00\x00\x00\x00\x25\x0D\x0A"
            ),  # warnings frame
        }
        return resp.get(cmd, bytearray())

    async def write_gatt_char(
        self,
        char_specifier: BleakGATTCharacteristic | int | str | UUID,
        data: Buffer,
        response: bool = None,  # type: ignore[implicit-optional] # noqa: RUF013 # same as upstream
    ) -> None:
        """Issue write command to GATT."""
        await super().write_gatt_char(char_specifier, data, response)

        assert self._notify_callback is not None

        self._notify_callback(
            "MockCBTpwrBleakClient", self._response(char_specifier, data)
        )


class MockInvalidBleakClient(MockCBTpwrBleakClient):
    """Emulate a CBT power BMS BleakClient."""

    def _response(
        self, char_specifier: BleakGATTCharacteristic | int | str | UUID, data: Buffer
    ) -> bytearray:
        if isinstance(char_specifier, str) and normalize_uuid_str(
            char_specifier
        ) != normalize_uuid_str("ffe9"):
            return bytearray()
        cmd: int = int(bytearray(data)[2])
        resp: dict[int, bytearray] = {
            0x09: bytearray(b"\x12\x34\x00\x00\x00\x56\x78"),  # invalid start/end
            0x0A: bytearray(
                b"\xAA\x55\x0B\x08\x58\x34\x00\x00\xBC\xF3\xFF\xFF\x4C\x0D\x0A"
            ),  # wrong answer to capacity req (0xA) with 0xB: voltage, cur -> pwr, charging
            0x0B: bytearray(b"invalid_len"),  # invalid length
            0x15: bytearray(
                b"\xAA\x55\x15\x04\x00\x00\x00\x00\x00\x0D\x0A"
            ),  # wrong CRC
        }
        return resp.get(cmd, bytearray())

    async def disconnect(self) -> bool:
        """Mock disconnect to raise BleakError."""
        raise BleakError


class MockPartBaseDatBleakClient(MockCBTpwrBleakClient):
    """Emulate a CBT power BMS BleakClient."""

    def _response(
        self, char_specifier: BleakGATTCharacteristic | int | str | UUID, data: Buffer
    ) -> bytearray:
        if isinstance(char_specifier, str) and normalize_uuid_str(
            char_specifier
        ) != normalize_uuid_str("ffe9"):
            return bytearray()
        cmd: int = int(bytearray(data)[2])
        if cmd == 0x0B:
            return bytearray(
                b"\xAA\x55\x0B\x08\x58\x34\x00\x00\x00\x00\x00\x00\x9F\x0D\x0A"
            )  # voltage/current frame, positive current

        return bytearray()


class MockAllCellsBleakClient(MockCBTpwrBleakClient):
    """Emulate a CBT power BMS BleakClient."""

    def _response(
        self, char_specifier: BleakGATTCharacteristic | int | str | UUID, data: Buffer
    ) -> bytearray:
        if isinstance(char_specifier, str) and normalize_uuid_str(
            char_specifier
        ) != normalize_uuid_str("ffe9"):
            return bytearray()
        cmd: int = int(bytearray(data)[2])
        resp: dict[int, bytearray] = {
            0x05: bytearray(
                b"\xAA\x55\x05\x0A\x0B\x0D\x0A\x0D\x09\x0D\x08\x0D\x07\x0D\x7D\x0D\x0A"
            ),
            0x06: bytearray(
                b"\xAA\x55\x06\x0A\x06\x0D\x05\x0D\x04\x0D\x03\x0D\x02\x0D\x65\x0D\x0A"
            ),
            0x07: bytearray(
                b"\xAA\x55\x07\x0A\x01\x0D\x00\x0D\xFF\x0C\xFE\x0C\xFD\x0C\x4A\x0D\x0A"
            ),
            0x08: bytearray(
                b"\xAA\x55\x08\x0A\xFC\x0C\xFB\x0C\xFA\x0C\xF9\x0C\xF8\x0C\x30\x0D\x0A"
            ),
            0x09: bytearray(
                b"\xAA\x55\x09\x0C\x15\x00\x15\x00\x00\x00\x00\x00\x00\x00\x00\x00\x3F\x0D\x0A"
            ),  # temperature frame
            0x0B: bytearray(
                b"\xAA\x55\x0B\x08\x58\x34\x00\x00\xBC\xF3\xFF\xFF\x4C\x0D\x0A"
            ),  # voltage/current frame
            0x15: bytearray(
                b"\xAA\x55\x15\x04\x28\x00\x03\x00\x44\x0D\x0A"
            ),  # cycle info frame
            0x0A: bytearray(
                b"\xAA\x55\x0A\x06\x64\x13\x0D\x00\x00\x00\x94\x0D\x0A"
            ),  # capacity frame
            0x0C: bytearray(
                b"\xAA\x55\x0C\x0C\x00\x00\x00\x00\x5B\x06\x00\x00\x03\x00\x74\x02\xF2\x0D\x0A"
            ),  # runtime info frame, 6.28h*100
        }
        return resp.get(cmd, bytearray())


async def test_update(monkeypatch, reconnect_fixture) -> None:
    """Test CBT power BMS data update."""

    monkeypatch.setattr(
        "custom_components.bms_ble.plugins.basebms.BleakClient",
        MockCBTpwrBleakClient,
    )

    bms = BMS(
        generate_ble_device("cc:cc:cc:cc:cc:cc", "MockBLEDevice", None, -73),
        reconnect_fixture,
    )

    result = await bms.async_update()

    assert result == {
        "voltage": 13.4,
        "current": -3.14,
        "battery_level": 100,
        "cycles": 3,
        "cycle_charge": 40.0,
        "cell#0": 3.339,
        "cell#1": 3.339,
        "cell#2": 3.338,
        "cell#3": 3.338,
        "cell#4": 2.317,
        "delta_voltage": 1.022,
        "temperature": -2,
        "cycle_capacity": 536.0,
        "design_capacity": 40,
        "power": -42.076,
        "runtime": 22608,
        "battery_charging": False,
    }

    # query again to check already connected state
    result = await bms.async_update()
    assert bms._client.is_connected is not reconnect_fixture  # noqa: SLF001

    await bms.disconnect()


async def test_invalid_response(monkeypatch) -> None:
    """Test data update with BMS returning invalid data."""

    monkeypatch.setattr(
        "custom_components.bms_ble.plugins.cbtpwr_bms.BMS.BAT_TIMEOUT",
        0.1,
    )

    monkeypatch.setattr(
        "custom_components.bms_ble.plugins.basebms.BleakClient",
        MockInvalidBleakClient,
    )

    bms = BMS(generate_ble_device("cc:cc:cc:cc:cc:cc", "MockBLEDevice", None, -73))

    result = await bms.async_update()
    assert result == {
        "battery_charging": False,
        "current": -3.14,
        "power": -42.076,
        "voltage": 13.4,
    }

    await bms.disconnect()


async def test_partly_base_data(monkeypatch) -> None:
    """Test data update with BMS returning invalid data."""

    monkeypatch.setattr(
        "custom_components.bms_ble.plugins.cbtpwr_bms.BMS.BAT_TIMEOUT",
        0.1,
    )

    monkeypatch.setattr(
        "custom_components.bms_ble.plugins.basebms.BleakClient",
        MockPartBaseDatBleakClient,
    )

    bms = BMS(generate_ble_device("cc:cc:cc:cc:cc:cc", "MockBLEDevice", None, -73))

    result = await bms.async_update()
    assert result == {
        "battery_charging": False,
        "current": 0.0,
        "power": 0.0,
        "voltage": 13.4,
    }

    await bms.disconnect()


async def test_all_cell_voltages(monkeypatch) -> None:
    """Test data update with BMS returning invalid data."""

    monkeypatch.setattr(
        "custom_components.bms_ble.plugins.cbtpwr_bms.BMS.BAT_TIMEOUT",
        0.1,
    )

    monkeypatch.setattr(
        "custom_components.bms_ble.plugins.basebms.BleakClient",
        MockAllCellsBleakClient,
    )

    bms = BMS(generate_ble_device("cc:cc:cc:cc:cc:cc", "MockBLEDevice", None, -73))

    result = await bms.async_update()
    assert result == {
        "voltage": 13.4,
        "current": -3.14,
        "battery_level": 100,
        "cycles": 3,
        "cycle_charge": 40.0,
        "cell#0": 3.339,
        "cell#1": 3.338,
        "cell#2": 3.337,
        "cell#3": 3.336,
        "cell#4": 3.335,
        "cell#5": 3.334,
        "cell#6": 3.333,
        "cell#7": 3.332,
        "cell#8": 3.331,
        "cell#9": 3.330,
        "cell#10": 3.329,
        "cell#11": 3.328,
        "cell#12": 3.327,
        "cell#13": 3.326,
        "cell#14": 3.325,
        "cell#15": 3.324,
        "cell#16": 3.323,
        "cell#17": 3.322,
        "cell#18": 3.321,
        "cell#19": 3.320,
        "delta_voltage": 0.019,
        "temperature": 21,
        "cycle_capacity": 536.0,
        "design_capacity": 40,
        "power": -42.076,
        "runtime": 22608,
        "battery_charging": False,
    }

    await bms.disconnect()
