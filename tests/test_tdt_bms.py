"""Test the TDT implementation."""

from collections.abc import Buffer
from typing import Final
from uuid import UUID

from bleak.backends.characteristic import BleakGATTCharacteristic
from bleak.exc import BleakDeviceNotFoundError
from bleak.uuids import normalize_uuid_str
import pytest

from custom_components.bms_ble.plugins.tdt_bms import BMS

from .bluetooth import generate_ble_device
from .conftest import MockBleakClient

BT_FRAME_SIZE = 27


def ref_value() -> dict:
    """Return reference value for mock Seplos BMS."""
    return {
        "16S6T": {
            "cell_count": 16,
            "temp_sensors": 6,
            "voltage": 52.7,
            "current": -5.7,
            "battery_level": 91,
            "cycle_charge": 99.1,
            "cycles": 8,
            "temperature": 18.267,
            "cycle_capacity": 5222.57,
            "power": -300.39,
            "battery_charging": False,
            "cell#0": 3.299,
            "cell#1": 3.302,
            "cell#2": 3.294,
            "cell#3": 3.294,
            "cell#4": 3.293,
            "cell#5": 3.294,
            "cell#6": 3.293,
            "cell#7": 3.292,
            "cell#8": 3.292,
            "cell#9": 3.290,
            "cell#10": 3.294,
            "cell#11": 3.294,
            "cell#12": 3.294,
            "cell#13": 3.293,
            "cell#14": 3.295,
            "cell#15": 3.294,
            "temp#0": 17.85,
            "temp#1": 19.55,
            "temp#2": 17.85,
            "temp#3": 17.85,
            "temp#4": 17.85,
            "temp#5": 18.65,
            "delta_voltage": 0.012,
            "runtime": 62589,
        },
        "4S4T": {
            "cell_count": 4,
            "temp_sensors": 4,
            "voltage": 13.18,
            "current": 0.0,
            "battery_level": 55,
            "cycle_charge": 57.5,
            "cycles": 8,
            "temperature": 23.025,
            "cycle_capacity": 757.85,
            "power": 0.0,
            "battery_charging": False,
            "cell#0": 3.297,
            "cell#1": 3.295,
            "cell#2": 3.297,
            "cell#3": 3.292,
            "temp#0": 23.15,
            "temp#1": 23.95,
            "temp#2": 22.55,
            "temp#3": 22.45,
            "delta_voltage": 0.005,
        },
    }


class MockTDTBleakClient(MockBleakClient):
    """Emulate a TDT BMS BleakClient."""

    HEAD_CMD: Final[int] = 0x7E
    TAIL_CMD: Final[int] = 0x0D
    CMDS: Final[dict[int, bytearray]] = {
        0x8C: bytearray(b"\x00\x01\x03\x00\x8c\x00\x00\x99\x42"),
        0x8D: bytearray(b"\x00\x01\x03\x00\x8d\x00\x00\x59\x13"),
        0x92: bytearray(b"\x00\x01\x03\x00\x92\x00\x00\x9f\x22"),
    }
    RESP: Final[dict[int, bytearray]] = {
        0x8C: bytearray(  # 16 celll message
            b"\x7e\x00\x01\x03\x00\x8c\x00\x3c\x10\x0c\xe3\x0c\xe6\x0c\xde\x0c\xde\x0c\xdd\x0c\xde"
            b"\x0c\xdd\x0c\xdc\x0c\xdc\x0c\xda\x0c\xde\x0c\xde\x0c\xde\x0c\xdd\x0c\xdf\x0c\xde\x06"
            b"\x0b\x5e\x0b\x6f\x0b\x5e\x0b\x5e\x0b\x5e\x0b\x66\xc0\x39\x14\x96\x03\xdf\x04\x3b\x00"
            b"\x08\x03\xe8\x00\x5b\x2b\x9c\x0d"
        ),
        0x8D: bytearray(
            b"\x7e\x00\x01\x03\x00\x8d\x00\x27\x10\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00"
            b"\x00\x00\x00\x00\x06\x00\x00\x00\x00\x00\x00\x00\x00\x00\x02\x00\x00\x0e\x01\x00\x00"
            b"\x18\x00\x00\x00\x00\x0b\x7b\x0d"
        ),
        0x92: bytearray(
            b"\x7e\x00\x01\x03\x00\x92\x00\x3c\x36\x30\x33\x32\x5f\x31\x30\x30\x31\x36\x53\x30\x30"
            b"\x30\x5f\x4c\x5f\x34\x31\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00"
            b"\x00\x00\x00\x00\x00\x00\x36\x30\x33\x32\x36\x30\x31\x36\x32\x30\x37\x32\x37\x30\x30"
            b"\x30\x31\x00\x00\x00\x50\x01\x0d"
        ),
    }
    _char_fffa: int = 0x0  # return value for UUID "fffa"

    def _response(
        self, char_specifier: BleakGATTCharacteristic | int | str | UUID, data: Buffer
    ) -> bytearray:

        if (
            isinstance(char_specifier, str)
            and normalize_uuid_str(char_specifier) == normalize_uuid_str("fff2")
            and bytearray(data)[0] == self.HEAD_CMD
            and bytearray(data)[-1] == self.TAIL_CMD
        ):
            for k, v in self.CMDS.items():
                if bytearray(data)[1:].startswith(v):
                    return self.RESP[k]

        return bytearray()

    async def write_gatt_char(
        self,
        char_specifier: BleakGATTCharacteristic | int | str | UUID,
        data: Buffer,
        response: bool | None = None,
    ) -> None:
        """Issue write command to GATT."""
        await super().write_gatt_char(char_specifier, data)

        if isinstance(char_specifier, str) and normalize_uuid_str(
            char_specifier
        ) == normalize_uuid_str("fffa"):
            if data == b"HiLink":
                self._char_fffa = 0x1
            return

        assert (
            self._notify_callback
        ), "write to characteristics but notification not enabled"

        resp = self._response(char_specifier, data)
        for notify_data in [
            resp[i : i + BT_FRAME_SIZE] for i in range(0, len(resp), BT_FRAME_SIZE)
        ]:
            self._notify_callback("MockTDTBleakClient", notify_data)

    async def read_gatt_char(
        self,
        char_specifier: BleakGATTCharacteristic | int | str | UUID,
        **kwargs,
    ) -> bytearray:
        """Mock write GATT characteristics."""
        await super().read_gatt_char(char_specifier, kwargs=kwargs)
        return bytearray(int.to_bytes(self._char_fffa, 1, "big"))


async def test_update_16S_6T(monkeypatch, reconnect_fixture) -> None:
    """Test TDT BMS data update."""

    monkeypatch.setattr(
        "custom_components.bms_ble.plugins.basebms.BleakClient",
        MockTDTBleakClient,
    )

    bms = BMS(
        generate_ble_device("cc:cc:cc:cc:cc:cc", "MockBLEdevice", None, -73),
        reconnect_fixture,
    )

    result = await bms.async_update()

    assert result == ref_value()["16S6T"]

    # query again to check already connected state
    result = await bms.async_update()
    assert (
        bms._client and bms._client.is_connected is not reconnect_fixture
    )  # noqa: SLF001

    await bms.disconnect()


async def test_update_4s_4t(monkeypatch, reconnect_fixture) -> None:
    """Test TDT BMS data update."""

    resp_4s4t: Final[dict[int, bytearray]] = {
        0x8C: bytearray(  # 4 cell message
            b"\x7e\x00\x01\x03\x00\x8c\x00\x20\x04\x0c\xe1\x0c\xdf\x0c\xe1\x0c"
            b"\xdc\x04\x0b\x93\x0b\x9b\x0b\x8d\x0b\x8c\x40\x00\x05\x26\x02\x3f"
            b"\x04\x1c\x00\x08\x03\xe8\x00\x37\x91\x91\x0d"
        ),
        0x8D: bytearray(
            b"\x7e\x00\x01\x03\x00\x8d\x00\x18\x04\x00\x00\x00\x00\x04\xc0\x00"
            b"\x00\x00\x00\x00\x00\x00\x00\x00\x06\x09\x00\x00\x18\x00\x00\x00"
            b"\xdf\x18\x0d"
        ),
    }

    monkeypatch.setattr(
        "tests.test_tdt_bms.MockTDTBleakClient.RESP",
        resp_4s4t,
    )

    monkeypatch.setattr(
        "custom_components.bms_ble.plugins.basebms.BleakClient",
        MockTDTBleakClient,
    )

    bms = BMS(
        generate_ble_device("cc:cc:cc:cc:cc:cc", "MockBLEdevice", None, -73),
        reconnect_fixture,
    )

    result = await bms.async_update()
    assert result == ref_value()["4S4T"]

    # query again to check already connected state
    _ = await bms.async_update()
    assert (
        bms._client and bms._client.is_connected is not reconnect_fixture
    )  # noqa: SLF001

    await bms.disconnect()


@pytest.fixture(
    name="wrong_response",
    params=[
        (b"\x7e\x00\x01\x03\x00\x8c\x00\x01\x00\xA1\x18\x00", "invalid frame end"),
        (b"\x7e\x10\x01\x03\x00\x8c\x00\x01\x00\xAD\x19\x0D", "invalid version"),
        (b"\x7e\x00\x01\x03\x00\x8c\x00\x01\x00\xA1\x00\x0D", "invalid CRC"),
        (b"\x7e\x00\x01\x03\x00\x8c\x00\x01\x00\xA1\x18\x0D\x00", "oversized frame"),
        (b"\x7e\x00\x01\x03\x00\x8c\x00\x01\x00\xA1\x0D", "undersized frame"),
        (b"\x7e\x00\x01\x03\x01\x8c\x00\x01\x00\x61\x25\x0D", "error response"),
    ],
    ids=lambda param: param[1],
)
def response(request):
    """Return faulty response frame."""
    return request.param[0]


async def test_invalid_response(monkeypatch, wrong_response) -> None:
    """Test data up date with BMS returning invalid data."""

    monkeypatch.setattr(
        "custom_components.bms_ble.plugins.tdt_bms.BMS.BAT_TIMEOUT",
        0.1,
    )

    monkeypatch.setattr(
        "tests.test_tdt_bms.MockTDTBleakClient._response",
        lambda _s, _c, _d: wrong_response,
    )

    monkeypatch.setattr(
        "custom_components.bms_ble.plugins.basebms.BleakClient",
        MockTDTBleakClient,
    )

    bms = BMS(generate_ble_device("cc:cc:cc:cc:cc:cc", "MockBLEDevice", None, -73))

    result = {}
    with pytest.raises(TimeoutError):
        result = await bms.async_update()

    assert not result
    await bms.disconnect()


async def test_init_fail(monkeypatch, bool_fixture) -> None:
    """Test that failing to initialize simply continues and tries to read data."""

    throw_exception: bool = bool_fixture

    async def error_repsonse(*_args, **_kwargs) -> bytearray:
        return bytearray(b"\x00")

    async def throw_response(*_args, **_kwargs) -> bytearray:
        raise BleakDeviceNotFoundError("MockTDTBleakClient")

    monkeypatch.setattr(
        "tests.test_tdt_bms.MockTDTBleakClient.read_gatt_char",
        throw_response if throw_exception else error_repsonse,
    )

    monkeypatch.setattr(
        "custom_components.bms_ble.plugins.basebms.BleakClient",
        MockTDTBleakClient,
    )

    bms = BMS(generate_ble_device("cc:cc:cc:cc:cc:cc", "MockBLEDevice", None, -73))

    if bool_fixture:
        with pytest.raises(BleakDeviceNotFoundError):
            assert not await bms.async_update()
    else:
        assert await bms.async_update() == ref_value()["16S6T"]

    await bms.disconnect()
