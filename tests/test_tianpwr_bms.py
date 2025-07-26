"""Test the TianPwr BMS implementation."""

from collections.abc import Buffer
from typing import Final
from uuid import UUID

from bleak.backends.characteristic import BleakGATTCharacteristic
from bleak.uuids import normalize_uuid_str
import pytest

from custom_components.bms_ble.plugins.basebms import BMSsample, BMSvalue
from custom_components.bms_ble.plugins.tianpwr_bms import BMS

from .bluetooth import generate_ble_device
from .conftest import MockBleakClient


def ref_value() -> BMSsample:
    """Return reference value for mock Seplos BMS."""
    return {
        "temp_sensors": 4,
        "voltage": 54.74,
        "current": 0.0,
        "battery_level": 60,
        "cycle_charge": 138.96,
        "cycles": 0,
        "temperature": 24.167,
        "cycle_capacity": 7606.67,
        "power": 0.0,
        "design_capacity": 230,
        "battery_charging": False,
        "cell_count": 16,
        "cell_voltages": [
            3.415,
            3.419,
            3.419,
            3.422,
            3.421,
            3.422,
            3.425,
            3.424,
            3.421,
            3.425,
            3.421,
            3.421,
            3.422,
            3.42,
            3.422,
            3.429,
        ],
        "temp_values": [28.0, 25.0, 23.0, 23.0, 23.0, 23.0],
        "delta_voltage": 0.014,
        "problem": False,
        "problem_code": 0,
    }


class MockTianPwrBleakClient(MockBleakClient):
    """Emulate a TianPwr BMS BleakClient."""

    RESP: Final[dict[int, bytearray]] = {
        0x81: bytearray(  # Software version frame
            b"\x55\x14\x81\x30\x2e\x31\x2e\x31\x30\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\xaa"
        ),
        0x82: bytearray(  # Hardware version frame
            b"\x55\x14\x82\x54\x50\x2d\x4c\x54\x35\x35\x00\x54\x42\x00\x00\x00\x00\x00\x00\xaa"
        ),
        0x83: bytearray(  # Status frame
            b"\x55\x14\x83\x00\x3c\x15\x62\x01\x18\x00\xe6\x00\xfa\x00\x00\x30\x30\x00\x64\xaa"
        ),  # 60%, 54.74V, 0A, 28° ambient temp, 23°, 25° MOS temp
        0x84: bytearray(  # General info frame
            b"\x55\x14\x84\x10\x04\x59\xd8\x36\x48\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\xaa"
        ),
        0x85: bytearray(  # Mosfet status frame
            b"\x55\x14\x85\x08\x23\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\xaa"
        ),
        0x87: bytearray(  # Temperatures frame
            b"\x55\x14\x87\x00\xe6\x00\xe6\x00\xe6\x00\xe6\x00\x00\x00\x00\x00\x00\x00\x00\xaa"
        ),
        0x88: bytearray(  # Cell voltages frame
            b"\x55\x14\x88\x0d\x57\x0d\x5b\x0d\x5b\x0d\x5e\x0d\x5d\x0d\x5e\x0d\x61\x0d\x60\xaa"
        ),
        0x89: bytearray(  # Cell voltages frame
            b"\x55\x14\x89\x0d\x5d\x0d\x61\x0d\x5d\x0d\x5d\x0d\x5e\x0d\x5c\x0d\x5e\x0d\x65\xaa"
        ),
        0x8A: bytearray(  # Cell voltages frame
            b"\x55\x14\x8a\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\xaa"
        ),
        0x90: bytearray(
            b"\x55\x14\x90\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\xaa"
        ),
        0x91: bytearray(
            b"\x55\x14\x91\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\xaa"
        ),
        0x94: bytearray(
            b"\x55\x14\x91\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\xaa"
        ),
        0x95: bytearray(
            b"\x55\x14\x91\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\xaa"
        ),
    }

    def _response(
        self, char_specifier: BleakGATTCharacteristic | int | str | UUID, data: Buffer
    ) -> bytearray:

        if isinstance(char_specifier, str) and normalize_uuid_str(
            char_specifier
        ) == normalize_uuid_str("ff02"):
            frame: Final[bytes] = bytes(data)
            if frame[0] == 0x55 and frame[-1] == 0xAA and frame[1] == 0x04:
                return self.RESP[frame[2]]

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

        self._notify_callback(
            "MockTianPwrBleakClient", self._response(char_specifier, data)
        )


async def test_update(patch_bleak_client, reconnect_fixture: bool) -> None:
    """Test TianPwr BMS data update."""

    patch_bleak_client(MockTianPwrBleakClient)

    bms = BMS(
        generate_ble_device("cc:cc:cc:cc:cc:cc", "MockBLEdevice", None, -73),
        reconnect_fixture,
    )

    assert await bms.async_update() == ref_value()

    # query again to check already connected state
    await bms.async_update()
    assert bms._client and bms._client.is_connected is not reconnect_fixture

    await bms.disconnect()


@pytest.fixture(
    name="wrong_response",
    params=[
        (bytearray(b"\x51\x14\x83" + bytes(16) + b"\xaa"), "wrong_SOF"),
        (bytearray(b"\x55\x14\x83" + bytes(16) + b"\xa1"), "wrong_EOF"),
        (bytearray(b"\x55\x14\x83" + bytes(17) + b"\xaa"), "wrong_length_max"),
        (bytearray(b"\x55\x14\x83" + bytes(15) + b"\xaa"), "wrong_length_min"),
        (bytearray(), "empty_frame"),
    ],
    ids=lambda param: param[1],
)
def fix_response(request) -> bytearray:
    """Return faulty response frame."""
    return request.param[0]


async def test_invalid_response(
    monkeypatch, patch_bleak_client, patch_bms_timeout, wrong_response: bytearray
) -> None:
    """Test data up date with BMS returning invalid data."""

    patch_bms_timeout()

    monkeypatch.setattr(
        MockTianPwrBleakClient,
        "RESP",
        MockTianPwrBleakClient.RESP | {0x83: wrong_response},
    )

    patch_bleak_client(MockTianPwrBleakClient)

    bms = BMS(generate_ble_device("cc:cc:cc:cc:cc:cc", "MockBLEDevice", None, -73))

    result: BMSsample = {}
    with pytest.raises(TimeoutError):
        result = await bms.async_update()

    assert not result
    await bms.disconnect()


async def test_missing_message(
    monkeypatch, patch_bleak_client, patch_bms_timeout
) -> None:
    """Test data up date with BMS returning no message type 83 but 90."""

    patch_bms_timeout()

    monkeypatch.setattr(
        MockTianPwrBleakClient,
        "RESP",
        MockTianPwrBleakClient.RESP
        | {
            0x83: bytearray(
                b"\x55\x14\x90\x00\x3c\x15\x62\x01\x18\x00\xe6\x00\xfa\x00\x00\x30\x30\x00\x64\xaa"
            )
        },
    )
    patch_bleak_client(MockTianPwrBleakClient)

    bms = BMS(generate_ble_device("cc:cc:cc:cc:cc:cc", "MockBLEDevice", None, -73))

    # remove values from reference that are in 0x84 response (and dependent)
    ref: BMSsample = ref_value()
    key: BMSvalue
    for key in (
        "battery_level",
        "battery_charging",
        "cycle_capacity",
        "power",
        "voltage",
        "current",
        "temp_values",
        "temperature",
    ):
        ref.pop(key)
    assert await bms.async_update() == ref
    await bms.disconnect()


@pytest.fixture(
    name="problem_response",
    params=[
        (
            bytearray(
                b"\x55\x14\x84\x10\x04\x59\xd8\x36\x48\x00\x00\x00\x00\x00\x00\x00\x00\x00\x01\xaa"
            ),
            "first_bit",
        ),
        (
            bytearray(
                b"\x55\x14\x84\x10\x04\x59\xd8\x36\x48\x00\x00\x80\x00\x00\x00\x00\x00\x00\x00\xaa"
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
    monkeypatch, patch_bleak_client, problem_response: tuple[bytearray, str]
) -> None:
    """Test data update with BMS returning error flags."""

    monkeypatch.setattr(
        MockTianPwrBleakClient,
        "RESP",
        MockTianPwrBleakClient.RESP | {0x84: problem_response[0]},
    )

    patch_bleak_client(MockTianPwrBleakClient)

    bms = BMS(generate_ble_device("cc:cc:cc:cc:cc:cc", "MockBLEdevice", None, -73))

    result: BMSsample = await bms.async_update()
    assert result == ref_value() | {
        "problem": True,
        "problem_code": 1 << (0 if problem_response[1] == "first_bit" else 63),
    }

    await bms.disconnect()
