"""Test the Renogy BMS implementation."""

# import asyncio
from collections.abc import Buffer
from uuid import UUID

from bleak.backends.characteristic import BleakGATTCharacteristic
from bleak.uuids import normalize_uuid_str

# import pytest
from custom_components.bms_ble.plugins.renogy_bms import BMS  # , BMSsample

from .bluetooth import generate_ble_device
from .conftest import MockBleakClient

BT_FRAME_SIZE = 512  # ATT max is 512 bytes


class MockRenogyBleakClient(MockBleakClient):
    """Emulate a Renogy BMS BleakClient."""

    RESP: dict[bytes, bytearray] = {
        b"\x30\x03\x13\x88\x00\x22\x45\x5c": bytearray(
            b"\x30\x03\x44\x00\x04\x00\x23\x00\x21\x00\x21\x00\x21\x00\x00\x00\x00\x00\x00\x00\x00"
            b"\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x02\x00\xaa\x00"
            b"\xaa\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00"
            b"\x00\x00\x00\x00\x00\x00\x00\x00\x25\x74"
        ),
        b"\x30\x03\x13\xf0\x00\x1c\x44\x95": bytearray(  # system ID
            b"\x30\x03\x38\x00\x00\x00\x00\x00\x06\x00\x00\x00\x00\x00\xc8\x32\x30\x32\x31\x30\x35"
            b"\x32\x36\x00\x00\x00\x00\x00\x00\x00\x00\x20\x20\x20\x20\x20\x20\x20\x20\x52\x42\x54"
            b"\x31\x30\x30\x4c\x46\x50\x31\x32\x2d\x42\x54\x20\x20\x30\x31\x30\x30\x55\x2f"
        ),  # 08È20210526        RBT100LFP12-BT  0100
        b"\x30\x03\x13\xb2\x00\x06\x65\x4a": bytearray(
            b"\x30\x03\x0c\x00\x00\x00\x88\x00\x01\x82\xb8\x00\x01\x86\xa0\xf9\x43"
        ),
        b"\x30\x03\x14\x02\x00\x08\xe4\x1d": bytearray(
            b"\x30\x03\x10\x52\x42\x54\x31\x30\x30\x4c\x46\x50\x31\x32\x2d\x42\x54\x20\x20\x58\xbb"
        ),  # 0RBT100LFP12-BT
    }

    def _response(
        self, char_specifier: BleakGATTCharacteristic | int | str | UUID, cmd: bytes
    ) -> bytearray:
        if isinstance(char_specifier, str) and normalize_uuid_str(
            char_specifier
        ) != normalize_uuid_str("ffd1"):
            return bytearray()

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

        resp: bytearray = self._response(char_specifier, bytes(data))
        for notify_data in [
            resp[i : i + BT_FRAME_SIZE] for i in range(0, len(resp), BT_FRAME_SIZE)
        ]:
            self._notify_callback("MockRenogyBleakClient", notify_data)


async def test_update(patch_bleak_client, reconnect_fixture: bool) -> None:
    """Test Renogy BMS data update."""

    patch_bleak_client(MockRenogyBleakClient)

    bms = BMS(
        generate_ble_device("cc:cc:cc:cc:cc:cc", "MockBLEDevice", None, -73),
        reconnect_fixture,
    )

    result = await bms.async_update()

    assert result == {
        "temp_sensors": 1,
        "voltage": 27.554,
        "current": 0.0,
        "battery_level": 99,
        "cycle_charge": 106.048,
        "cycles": 7,
        "problem_code": 0,
        "cell#0": 3.442,
        "cell#1": 3.496,
        "cell#2": 3.375,
        "cell#3": 3.464,
        "cell#4": 3.457,
        "cell#5": 3.429,
        "cell#6": 3.359,
        "cell#7": 3.42,
        "temp#0": 20,
        "delta_voltage": 0.137,
        "cycle_capacity": 2922.047,
        "power": 0.0,
        "battery_charging": False,
        "temperature": 20.0,
        "problem": False,
    }

    # query again to check already connected state
    result = await bms.async_update()
    assert bms._client.is_connected is not reconnect_fixture

    await bms.disconnect()


# @pytest.fixture(
#     name="wrong_response",
#     params=[
#         (
#             b"\xcc\xf0\xa2\x6b\x00\x00\x00\x00\xa0\x86\x01\x40\x9e\x01\x07\x00\x63\x00\x00\x20",
#             "wrong_CRC",
#         ),
#         (
#             b"\xc0\xf0\xa2\x6b\x00\x00\x00\x00\xa0\x86\x01\x40\x9e\x01\x07\x00\x63\x00\x00\x21",
#             "wrong_SOF",
#         ),
#         (
#             b"\xcc\xfe\xa2\x6b\x00\x00\x00\x00\xa0\x86\x01\x40\x9e\x01\x07\x00\x63\x00\x00\x4f",
#             "wrong_CMD",
#         ),
#         (
#             b"\xcc\xf0\xa2\x6b\x00\x00\x00\x00\xa0\x86\x01\x40\x9e\x01\x07\x00\x63\x00\x21",
#             "wrong_length",
#         ),
#     ],
#     ids=lambda param: param[1],
# )
# def response(request) -> bytearray:
#     """Return faulty response frame."""
#     return bytearray(request.param[0])
#
#
# async def test_invalid_response(
#     monkeypatch, patch_bleak_client, patch_bms_timeout, wrong_response: bytearray
# ) -> None:
#     """Test data up date with BMS returning invalid data."""

#     patch_bms_timeout("renogy_bms")

#     monkeypatch.setattr(
#         MockRenogyBleakClient,
#         "RESP",
#         MockRenogyBleakClient.RESP | {0xF0: wrong_response},
#     )

#     patch_bleak_client(MockRenogyBleakClient)

#     bms = BMS(generate_ble_device("cc:cc:cc:cc:cc:cc", "MockBLEDevice", None, -73))

#     result: BMSsample = {}
#     with pytest.raises(TimeoutError):
#         result = await bms.async_update()

#     assert not result
#     await bms.disconnect()


# @pytest.fixture(
#     name="problem_response",
#     params=[
#         (
#             b"\xcc\xf9\x69\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x1d",
#             "first_bit",
#         ),
#         (
#             b"\xcc\xf9\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x69\x00\x05",
#             "last_bit",
#         ),
#     ],
#     ids=lambda param: param[1],
# )
# def prb_response(request) -> tuple[bytearray, str]:
#     """Return faulty response frame."""
#     return request.param


# async def test_problem_response(
#     monkeypatch, patch_bleak_client, problem_response: tuple[bytearray, str]
# ) -> None:
#     """Test data update with BMS returning error flags."""

#     monkeypatch.setattr(
#         MockRenogyBleakClient,
#         "RESP",
#         MockRenogyBleakClient.RESP | {0xF9: bytearray(problem_response[0])},
#     )

#     patch_bleak_client(MockRenogyBleakClient)

#     bms = BMS(generate_ble_device("cc:cc:cc:cc:cc:cc", "MockBLEdevice", None, -73))

#     result: BMSsample = await bms.async_update()
#     assert result.get("problem", False)  # expect a problem report
#     assert result.get("problem_code", 0) == (
#         0x1 if problem_response[1] == "first_bit" else 0x8000
#     )

#     await bms.disconnect()
