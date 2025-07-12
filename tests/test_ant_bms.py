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

BT_FRAME_SIZE: Final[int] = 27  # ANT BMS frame size

_RESULT_DEFS: Final[BMSsample] = {
    "cell_count": 4,
    "temp_sensors": 3,
    "voltage": 13.29,
    "current": -1.14,
    "battery_level": 72,
    "cycle_charge": 72.0,
    "design_capacity": 100,
    #        "cycles": 8,
    "temperature": 19.567,
    "cycle_capacity": 956.88,
    "power": -15.151,
    "battery_charging": False,
    "cell_voltages": [3.323, 3.325, 3.323, 3.322],
    "temp_values": [20.5, 19.2, 19.0],
    "delta_voltage": 0.003,
    "runtime": 227368,
    "problem": False,
    "problem_code": 0,
}


class MockANTBleakClient(MockBleakClient):
    """Emulate a ANT BMS BleakClient."""

    CMDS: Final[dict[int, bytearray]] = {
        0x01: bytearray(b"\x7e\xa1\x01\x00\x00\xbe\x18\x55\xaa\x55"),
        0x02: bytearray(b"\x7e\xa1\x02\x6c\x02\x20\x58\xc4\xaa\x55"),
    }
    RESP: Final[dict[int, bytearray]] = {
        0x1: bytearray(
            b"\xa1\x00\x00\x00\x65\x00\x00\x00\x00\x00\x18\x01\x03\x44\x00\x18\x00\x48\x00\x64\x05"
            b"\x31\xff\x8e\x00\x00\x27\x10\x00\x01\x00\x01\x00\x00\x00\x00\x00\x00\x00\x00\x00\x01"
            b"\x00\x02\x00\x00\xff\xff\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00"
            b"\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x21\x86"
        ),
        0x2: bytearray(  # 4 cells, 3 temp sensors
            b"\xa2\x00\x00\x00\x65\x00\x00\x00\x00\x00\x18\x01\x03\x56\x00\x04\x0c\xfb\x0c\xfd\x0c"
            b"\xfb\x0c\xfa\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff"
            b"\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff"
            b"\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\x00\x03\x00\xcd"
            b"\x00\xc0\x00\xbe\xfc\x18\xfc\x18\xfc\x18\xfc\x18\xfc\x18\xfc\x18\x97\x6a"
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
