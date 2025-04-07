"""Test the CBT power VB series BMS implementation."""

from collections.abc import Buffer
from uuid import UUID

from bleak.backends.characteristic import BleakGATTCharacteristic

# from bleak.exc import BleakError
from bleak.uuids import normalize_uuid_str
import pytest

from custom_components.bms_ble.plugins.cbtpwr_vb_bms import BMS, BMSsample

from .bluetooth import generate_ble_device
from .conftest import MockBleakClient


def ref_value() -> BMSsample:
    """Return reference value for mock CBT power VB series BMS."""
    return {
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
        "problem": False,
        "problem_code": 0,
    }


class MockCBTpwrVBBleakClient(MockBleakClient):
    """Emulate a CBT power VB series BMS BleakClient."""

    RESP: dict[int, bytearray] = {
        0x0006: bytearray(
            b"\xaa\x55\x4d\x00\x01\x00\x00\x00\x02\x01\xd0\x0c\xe8\x0c\xf4\x0c\x28\x0c\x1e\x00\x23"
            b"\x00\x64\x00\x00\x00\x10\x27\x00\x00\xc8\x00\x00\x00\xa0\x00\x00\x00\x14\x00\x00\x00"
            b"\x0a\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\xdc\x05\xb4\x04\xa0\x03"
            b"\x02\x03\x1a\x00\x14\x00\x0f\x00\x01\x02\x03\x00\x00\x00\x00\x04\x00\x00\x01\xf1\x07"
            b"\x55\xaa"
        ),
    }

    def _response(
        self, char_specifier: BleakGATTCharacteristic | int | str | UUID, data: Buffer
    ) -> bytearray:
        if isinstance(char_specifier, str) and normalize_uuid_str(
            char_specifier
        ) != normalize_uuid_str("fff2"):
            return bytearray()
        cmd: int = int.from_bytes(bytes(data)[2:4], byteorder="little")

        return self.RESP.get(cmd, bytearray())

    async def write_gatt_char(
        self,
        char_specifier: BleakGATTCharacteristic | int | str | UUID,
        data: Buffer,
        response: bool = None,  # noqa: RUF013 # same as upstream
    ) -> None:
        """Issue write command to GATT."""
        await super().write_gatt_char(char_specifier, data, response)

        assert self._notify_callback is not None

        self._notify_callback(
            "MockCBTpwrVBBleakClient", self._response(char_specifier, data)
        )


# class MockInvalidBleakClient(MockCBTpwrVBBleakClient):
#     """Emulate a CBT power VB series BMS BleakClient."""

#     RESP: dict[int, bytearray] = {
#         0x09: bytearray(b"\x12\x34\x00\x00\x00\x56\x78"),  # invalid start/end
#         0x0A: bytearray(
#             b"\xaa\x55\x0b\x08\x58\x34\x00\x00\xbc\xf3\xff\xff\x4c\x0d\x0a"
#         ),  # wrong answer to capacity req (0xA) with 0xB: voltage, cur -> pwr, charging
#         0x0B: bytearray(b"invalid_len"),  # invalid length
#         0x15: bytearray(b"\xaa\x55\x15\x04\x00\x00\x00\x00\x00\x0d\x0a"),  # wrong CRC
#         0x21: bytearray(0),  # empty frame
#     }

#     async def disconnect(self) -> bool:
#         """Mock disconnect to raise BleakError."""
#         raise BleakError


async def test_update(patch_bleak_client, reconnect_fixture: bool) -> None:
    """Test CBT power VB series BMS data update."""

    patch_bleak_client(MockCBTpwrVBBleakClient)

    bms = BMS(
        generate_ble_device("cc:cc:cc:cc:cc:cc", "MockBLEDevice", None, -73),
        reconnect_fixture,
    )

    result = await bms.async_update()

    assert result == ref_value()

    # query again to check already connected state
    result = await bms.async_update()
    assert bms._client.is_connected is not reconnect_fixture

    await bms.disconnect()


@pytest.fixture(
    name="wrong_response",
    params=[
        (
            bytearray(
                b"\xaa\xdd\x4d\x00\x01\x00\x00\x00\x02\x01\xd0\x0c\xe8\x0c\xf4\x0c\x28\x0c\x1e\x00"
                b"\x23\x00\x64\x00\x00\x00\x10\x27\x00\x00\xc8\x00\x00\x00\xa0\x00\x00\x00\x14\x00"
                b"\x00\x00\x0a\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\xdc\x05\xb4"
                b"\x04\xa0\x03\x02\x03\x1a\x00\x14\x00\x0f\x00\x01\x02\x03\x00\x00\x00\x00\x04\x00"
                b"\x00\x01\xf1\x07\x55\xaa"
            ),
            "wrong_SOF",
        ),
        (
            bytearray(
                b"\xaa\x55\x4d\x00\x01\x00\x00\x00\x02\x01\xd0\x0c\xe8\x0c\xf4\x0c\x28\x0c\x1e\x00"
                b"\x23\x00\x64\x00\x00\x00\x10\x27\x00\x00\xc8\x00\x00\x00\xa0\x00\x00\x00\x14\x00"
                b"\x00\x00\x0a\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\xdc\x05\xb4"
                b"\x04\xa0\x03\x02\x03\x1a\x00\x14\x00\x0f\x00\x01\x02\x03\x00\x00\x00\x00\x04\x00"
                b"\x00\x01\xf1\x07\xdd\xaa"
            ),
            "wrong_EOF",
        ),
        # (
        #     bytearray(
        #         b"\xea\xd1\x01\x0e\xff\x02\x04\x04\x04\x0d\x2f\x0d\x2a\x0d\x29\x0d\x2c\xf6\xf5"
        #     ),
        #     "wrong_length",
        # ),
        (
            bytearray(
                b"\xaa\x55\x4d\x00\x01\x00\x00\x00\x02\x01\xd0\x0c\xe8\x0c\xf4\x0c\x28\x0c\x1e\x00"
                b"\x23\x00\x64\x00\x00\x00\x10\x27\x00\x00\xc8\x00\x00\x00\xa0\x00\x00\x00\x14\x00"
                b"\x00\x00\x0a\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\xdc\x05\xb4"
                b"\x04\xa0\x03\x02\x03\x1a\x00\x14\x00\x0f\x00\x01\x02\x03\x00\x00\x00\x00\x04\x00"
                b"\x00\x01\xf1\x08\x55\xaa"
            ),
            "wrong_CRC",
        ),
        (bytearray(8), "critical_length"),
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

    patch_bms_timeout("cbtpwr_vb_bms")

    monkeypatch.setattr(
        MockCBTpwrVBBleakClient,
        "RESP",
        MockCBTpwrVBBleakClient.RESP | {0x0006: wrong_response},
    )

    patch_bleak_client(MockCBTpwrVBBleakClient)

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
                b"\xaa\x55\x4d\x00\x01\x00\x00\x00\x02\x01\xd0\x0c\xe8\x0c\xf4\x0c\x28\x0c\x1e\x00"
                b"\x23\x00\x64\x00\x00\x00\x10\x27\x00\x00\xc8\x00\x00\x00\xa0\x00\x00\x00\x14\x00"
                b"\x00\x00\x0a\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\xdc\x05\xb4"
                b"\x04\xa0\x03\x02\x03\x1a\x00\x14\x00\x0f\x00\x01\x02\x03\x01\x00\x00\x00\x04\x00"
                b"\x00\x01\xf2\x07\x55\xaa"
            ),
            "first_bit",
        ),
        (
            bytearray(
                b"\xaa\x55\x4d\x00\x01\x00\x00\x00\x02\x01\xd0\x0c\xe8\x0c\xf4\x0c\x28\x0c\x1e\x00"
                b"\x23\x00\x64\x00\x00\x00\x10\x27\x00\x00\xc8\x00\x00\x00\xa0\x00\x00\x00\x14\x00"
                b"\x00\x00\x0a\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\xdc\x05\xb4"
                b"\x04\xa0\x03\x02\x03\x1a\x00\x14\x00\x0f\x00\x01\x02\x03\x00\x00\x00\x80\x04\x00"
                b"\x00\x01\xf2\x07\x55\xaa"
            ),
            "last_bit",
        ),
    ],
    ids=lambda param: param[1],
)
def prb_response(request) -> tuple[dict[int, bytearray], str]:
    """Return faulty response frame."""
    return request.param


async def test_problem_response(
    monkeypatch, patch_bleak_client, problem_response: tuple[dict[int, bytearray], str]
) -> None:
    """Test data update with BMS returning error flags."""

    monkeypatch.setattr(  # patch response dictionary to only problem reports (no other data)
        MockCBTpwrVBBleakClient,
        "RESP",
        MockCBTpwrVBBleakClient.RESP | {0x0006: problem_response[0]},
    )

    patch_bleak_client(MockCBTpwrVBBleakClient)

    bms = BMS(generate_ble_device("cc:cc:cc:cc:cc:cc", "MockBLEdevice", None, -73))

    result: BMSsample = await bms.async_update()
    assert result == ref_value() | {
        "problem": True,
        "problem_code": 1 << (0 if problem_response[1] == "first_bit" else 31),
    }

    await bms.disconnect()
