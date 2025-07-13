"""Test the ANT implementation."""

import asyncio
from collections.abc import Buffer
from typing import Final
from uuid import UUID

from bleak.backends.characteristic import BleakGATTCharacteristic

# import pytest
from custom_components.bms_ble.plugins.ant_bms import BMS
from custom_components.bms_ble.plugins.basebms import BMSsample

from .bluetooth import generate_ble_device
from .conftest import MockBleakClient

BT_FRAME_SIZE: Final[int] = 20  # ANT BMS frame size

_RESULT_DEFS: Final[BMSsample] = {
    "cell_count": 22,
    "temp_sensors": 4,
    "voltage": 50.88,
    "current": 2.2,
    "battery_level": 10,
    "cycle_charge": 99,
    "design_capacity": 800,
    # "cycles": 8,
    "temperature": 29.333,
    "cycle_capacity": 5037.12,
    "power": 111.0,
    "battery_charging": False,
    "cell_voltages": [
        2.334,
        2.331,
        2.334,
        2.333,
        2.333,
        2.334,
        2.336,
        2.334,
        2.191,
        2.19,
        2.192,
        2.338,
        2.284,
        2.336,
        2.336,
        2.335,
        2.334,
        2.335,
        2.334,
        2.335,
        2.337,
        2.335,
    ],
    "temp_values": [29.0, 29.0, 29.0, 29.0, 30.0, 30.0],
    "delta_voltage": 0.148,
    # "runtime": 227368,
    "problem": True,
    "problem_code": 25690112,
}


class MockANTBleakClient(MockBleakClient):
    """Emulate a ANT BMS BleakClient."""

    CMDS: Final[dict[int, bytearray]] = {
        0x01: bytearray(b"\x7e\xa1\x01\x00\x00\xbe\x18\x55\xaa\x55"),
        0x02: bytearray(b"\x7e\xa1\x02\x6c\x02\x20\x58\xc4\xaa\x55"),
    }
    RESP: Final[dict[int, bytearray]] = {
        0x1: bytearray(
            b"\x7e\xa1\x11\x00\x00\x9e\x05\x04\x04\x16\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00"
            b"\x88\x01\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x1e\x09\x1b\x09\x1e\x09"
            b"\x1d\x09\x1d\x09\x1e\x09\x20\x09\x1e\x09\x8f\x08\x8e\x08\x90\x08\x22\x09\xec\x08"
            b"\x20\x09\x20\x09\x1f\x09\x1e\x09\x1f\x09\x1e\x09\x1f\x09\x21\x09\x1f\x09\x1d\x00"
            b"\x1d\x00\x1d\x00\x1d\x00\x1e\x00\x1e\x00\xe0\x13\x16\x00\x0a\x00\x64\x00\x01\x01"
            b"\x00\x00\x00\xb4\xc4\x04\xa5\x4d\x98\x00\x2e\xed\xe8\x00\x6f\x00\x00\x00\x7a\xf2"
            b"\xc0\x03\x00\x00\x00\x00\x22\x09\x0c\x00\x8e\x08\x0a\x00\x94\x00\x08\x09\x00\x00"
            b"\x6d\x00\x6a\x00\xaf\x02\xf3\xfa\x34\x74\xe5\x00\x28\x66\xec\x00\x9c\x5d\x62\x00"
            b"\x02\x02\x20\x0f\x00\x0b\x00\x04\x00\x1b\x10\x00\xcc\xb3\x92\x00\xd9\x85\xaa\x55"
        ),
            # b"\x7e\xa1\x11\x00\x00\x8e\x05\x01\x02\x10\x00\x00\x00\x00\x00\x00\x00\x00\x80\x00"
            # b"\x80\x01\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\xe4\x0c\xe4\x0c\xe5\x0c"
            # b"\xe5\x0c\xe8\x0c\xe7\x0c\xe7\x0c\xe6\x0c\xe8\x0c\xe7\x0c\xe7\x0c\xe7\x0c\xe7\x0c"
            # b"\xe7\x0c\xe6\x0c\xe9\x0c\x01\x00\x02\x00\x02\x00\x07\x00\xa4\x14\x03\x00\x5b\x00"
            # b"\x64\x00\x01\x01\x00\x00\x00\x76\xb0\x10\xd5\x67\x0e\x0f\xba\x32\x4a\x00\x0f\x00"
            # b"\x00\x00\x10\x58\x2e\x02\x00\x00\x00\x00\xe9\x0c\x10\x00\xe4\x0c\x01\x00\x05\x00"
            # b"\xe6\x0c\x00\x00\x80\x00\x7a\x00\x0f\x02\xf2\xfa\xb9\x8c\x3b\x00\xbb\xd8\x58\x00"
            # b"\xda\x2d\x43\x00\xe8\xb6\x49\x00\x05\x43\xaa\x55" # 16 cells
        0x2: bytearray(
            b"\x7e\xa1\x12\x6c\x02\x20\x32\x34\x42\x48\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00"
            b"\x00\x00\x32\x34\x42\x48\x55\x42\x30\x30\x2d\x32\x31\x31\x30\x32\x36\x41\x57\x96"
            b"\xff\x0b\x00\x00\x41\xf2\xaa\x55"
        ),
    }

    _task: asyncio.Task

    async def _notify(self) -> None:
        """Notify function."""

        assert (
            self._notify_callback
        ), "write to characteristics but notification not enabled"

        while True:
            for msg in self.RESP.values():
                self._notify_callback("MockANTBleakClient", msg)
                await asyncio.sleep(0.1)

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

        resp: Final[bytearray] = self.RESP.get(int(bytes(data)[2]), bytearray())
        for notify_data in [
            resp[i : i + BT_FRAME_SIZE] for i in range(0, len(resp), BT_FRAME_SIZE)
        ]:
            self._notify_callback("MockANTBleakClient", notify_data)


async def test_update(monkeypatch, patch_bleak_client, reconnect_fixture) -> None:
    """Test ANT BMS data update."""

    patch_bleak_client(MockANTBleakClient)

    bms = BMS(
        generate_ble_device("cc:cc:cc:cc:cc:cc", "MockBLEdevice", None, -73),
        reconnect_fixture,
    )

    assert await bms.async_update() == _RESULT_DEFS

    # query again to check already connected state
    await bms.async_update()
    assert bms._client and bms._client.is_connected is not reconnect_fixture

    await bms.disconnect()


# @pytest.fixture(
#     name="wrong_response",
#     params=[
#         (
#             bytearray(
#                 b"\xa3\x00\x00\x00\x65\x00\x00\x00\x00\x00\x18\x01\x03\x44\x00\x18\x00\x48\x00\x64"
#                 b"\x05\x31\xff\x8e\x00\x00\x27\x10\x00\x01\x00\x01\x00\x00\x00\x00\x00\x00\x00\x00"
#                 b"\x00\x01\x00\x02\x00\x00\xff\xff\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00"
#                 b"\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00"
#                 b"\x00\x00\x70\x20"
#             ),
#             "wrong_type",
#         ),
#         (
#             bytearray(
#                 b"\xa2\x00\x00\x00\x65\x00\x00\x00\x00\x00\x18\x01\x03\x56\x00\x04\x0c\xfb\x0c\xfd"
#                 b"\x0c\xfb\x0c\xfa\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff"
#                 b"\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff"
#                 b"\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff"
#                 b"\x00\x03\x00\xcd\x00\xc0\x00\xbe\xfc\x18\xfc\x18\xfc\x18\xfc\x18\xfc\x18\xfc\x18"
#                 b"\x97\x6a"
#             ),
#             "single_type_sent",
#         ),
#         (
#             bytearray(  # correct CRC: 0x2186
#                 b"\xa1\x00\x00\x00\x65\x00\x00\x00\x00\x00\x18\x01\x03\x44\x00\x18\x00\x48\x00\x64"
#                 b"\x05\x31\xff\x8e\x00\x00\x27\x10\x00\x01\x00\x01\x00\x00\x00\x00\x00\x00\x00\x00"
#                 b"\x00\x01\x00\x02\x00\x00\xff\xff\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00"
#                 b"\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00"
#                 b"\x00\x00\x21\x87"
#             ),
#             "wrong_CRC",
#         ),
#         (
#             bytearray(b""),
#             "empty_response",
#         ),
#     ],
#     ids=lambda param: param[1],
# )
# def response(request):
#     """Return faulty response frame."""
#     return request.param[0]


# async def test_invalid_response(
#     monkeypatch, patch_bleak_client, patch_bms_timeout, protocol_type, wrong_response
# ) -> None:
#     """Test data up date with BMS returning invalid data."""

#     patch_bms_timeout("ecoworthy_bms")

#     monkeypatch.setattr(MockANTBleakClient, "RESP", _PROTO_DEFS[protocol_type])
#     monkeypatch.setattr(
#         MockANTBleakClient,
#         "RESP",
#         {0xA1: wrong_response, 0xA2: MockANTBleakClient.RESP[0xA2]},
#     )

#     patch_bleak_client(MockANTBleakClient)

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
#             bytearray(
#                 b"\xa1\x00\x00\x00\x65\x00\x00\x00\x00\x00\x18\x01\x03\x44\x00\x18\x00\x48\x00\x64"
#                 b"\x05\x31\xff\x8e\x00\x00\x27\x10\x00\x01\x00\x01\x00\x00\x00\x00\x00\x00\x00\x00"
#                 b"\x00\x01\x00\x02\x00\x00\xff\xff\x00\x00\x00\x00\x01\x00\x00\x00\x00\x00\x00\x00"
#                 b"\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00"
#                 b"\x00\x00\x20\xd6"
#             ),
#             "first_bit",
#         ),
#         (
#             bytearray(
#                 b"\xa1\x00\x00\x00\x65\x00\x00\x00\x00\x00\x18\x01\x03\x44\x00\x18\x00\x48\x00\x64"
#                 b"\x05\x31\xff\x8e\x00\x00\x27\x10\x00\x01\x00\x01\x00\x00\x00\x00\x00\x00\x00\x00"
#                 b"\x00\x01\x00\x02\x00\x00\xff\xff\x00\x00\x00\x80\x00\x00\x00\x00\x00\x00\x00\x00"
#                 b"\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00"
#                 b"\x00\x00\x20\x0e"
#             ),
#             "last_bit",
#         ),
#     ],
#     ids=lambda param: param[1],
# )
# def prb_response(request) -> tuple[bytearray, str]:
#     """Return faulty response frame."""
#     return request.param


# async def test_problem_response(
#     monkeypatch, patch_bleak_client, problem_response
# ) -> None:
#     """Test data update with BMS returning error flags."""

#     monkeypatch.setattr(MockANTBleakClient, "RESP", _PROTO_DEFS[0x1])
#     monkeypatch.setattr(
#         MockANTBleakClient,
#         "RESP",
#         {
#             0xA1: problem_response[0],
#             0xA2: MockANTBleakClient.RESP[0xA2],
#         },
#     )

#     patch_bleak_client(MockANTBleakClient)

#     bms = BMS(generate_ble_device("cc:cc:cc:cc:cc:cc", "MockBLEdevice", None, -73))

#     result: BMSsample = await bms.async_update()
#     assert result == _RESULT_DEFS[0x1] | {
#         "problem": True,
#         "problem_code": 1 << (0 if problem_response[1] == "first_bit" else 15),
#     }

#     await bms.disconnect()
