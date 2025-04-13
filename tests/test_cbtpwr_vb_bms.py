"""Test the CBT power VB series BMS implementation."""

from collections.abc import Buffer
from typing import Final
from uuid import UUID

from bleak.backends.characteristic import BleakGATTCharacteristic

# from bleak.exc import BleakError
from bleak.uuids import normalize_uuid_str
import pytest

from custom_components.bms_ble.plugins.cbtpwr_vb_bms import BMS, BMSsample

from .bluetooth import generate_ble_device
from .conftest import MockBleakClient

BT_FRAME_SIZE = 32


def ref_value() -> BMSsample:
    """Return reference value for mock CBT power VB series BMS."""
    return {
        "voltage": 13.3,
        "current": 0.0,
        "battery_level": 96,
        "cycles": 0,
        "cycle_charge": 192.0,
        "cell_count": 4,
        "cell#0": 3.328,
        "cell#1": 3.326,
        "cell#2": 3.326,
        "cell#3": 3.326,
        "delta_voltage": 0.002,
        "design_capacity": 200.0,
        "temp#0": 6.2,
        "temp#1": 7.3,
        "temp_sensors": 2,
        "temperature": 6.75,
        "cycle_capacity": 2553.6,
        "power": 0.0,
        #        "runtime": 22608,
        "battery_charging": False,
        "problem": False,
        "problem_code": 0,
    }


class MockCBTpwrVBBleakClient(MockBleakClient):
    """Emulate a CBT power VB series BMS BleakClient."""

    RESP: dict[bytes, bytearray] = {
        b"~11014642E00201FD35\r": bytearray(
            b"\x7e\x32\x32\x30\x31\x34\x36\x30\x30\x36\x30\x34\x36\x30\x34\x30\x44\x30\x30\x30"
            b"\x43\x46\x45\x30\x43\x46\x45\x30\x43\x46\x45\x30\x32\x30\x30\x33\x45\x30\x30\x34"
            b"\x39\x30\x30\x30\x30\x30\x30\x38\x35\x30\x30\x36\x30\x30\x37\x30\x30\x30\x30\x30"
            b"\x30\x38\x36\x30\x30\x30\x30\x30\x30\x30\x30\x30\x30\x30\x30\x30\x30\x30\x30\x30"
            b"\x30\x30\x30\x45\x46\x36\x30\x0d"
        ),
        b"~11014681A00601A101FC5F\r": bytearray(
            b"\x7e\x32\x32\x30\x31\x34\x36\x30\x30\x43\x30\x30\x34\x30\x37\x44\x30\x46\x43\x42"
            b"\x46\x0d"
        ),
        # 0x81: bytearray(
        #     b"\x7e\x32\x32\x30\x31\x34\x36\x30\x30\x30\x30\x34\x43\x35\x36\x34\x32\x33\x30\x33"
        #     b"\x32\x33\x34\x34\x32\x33\x31\x33\x32\x33\x32\x33\x32\x33\x30\x33\x30\x33\x30\x33"
        #     b"\x33\x33\x39\x33\x30\x30\x30\x30\x30\x30\x30\x30\x30\x30\x32\x30\x33\x35\x36\x34"
        #     b"\x32\x33\x34\x35\x33\x35\x46\x35\x32\x33\x31\x30\x30\x30\x30\x30\x30\x30\x32\x30"
        #     b"\x32\x46\x37\x46\x46\x32\x46\x34\x38\x45\x45\x34\x37\x0d"
        # ),
    }

    def _response(
        self, char_specifier: BleakGATTCharacteristic | int | str | UUID, data: Buffer
    ) -> bytearray:
        if isinstance(char_specifier, str) and normalize_uuid_str(
            char_specifier
        ) != normalize_uuid_str("ffe9"):
            return bytearray()
        # cmd: int = int(bytes(data)[7:9], 16)

        return self.RESP.get(bytes(data), bytearray())

    async def write_gatt_char(
        self,
        char_specifier: BleakGATTCharacteristic | int | str | UUID,
        data: Buffer,
        response: bool = None,  # noqa: RUF013 # same as upstream
    ) -> None:
        """Issue write command to GATT."""
        await super().write_gatt_char(char_specifier, data, response)

        assert self._notify_callback is not None

        resp: Final[bytearray] = self._response(char_specifier, data)
        for notify_data in [
            resp[i : i + BT_FRAME_SIZE] for i in range(0, len(resp), BT_FRAME_SIZE)
        ]:
            self._notify_callback("MockCBTpwrVBBleakClient", notify_data)


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
