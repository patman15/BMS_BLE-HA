"""Test the RoyPow BMS implementation."""

from collections.abc import Buffer
from typing import Final
from uuid import UUID

from bleak.backends.characteristic import BleakGATTCharacteristic
from bleak.uuids import normalize_uuid_str

from custom_components.bms_ble.plugins.roypow_bms import BMS, BMSsample

from .bluetooth import generate_ble_device
from .conftest import MockBleakClient

BT_FRAME_SIZE = 20


def ref_value() -> BMSsample:
    """Return reference value for mock Seplos BMS."""
    return {
        "temp_sensors": 4,
        "voltage": 13.48,
        "current": 0.35,
        "battery_level": 96,
#        "cycle_charge": 72.0,
        "cycles": 2,
        "temperature": 19.25,
#        "cycle_capacity": 956.88,
        "power": 4.718,
        "battery_charging": True,
        "cell#0": 3.375,
        "cell#1": 3.370,
        "cell#2": 3.369,
        "cell#3": 3.372,
        "temp#0": 19,
        "temp#1": 19,
        "temp#2": 19,
        "temp#3": 20,
        "delta_voltage": 0.006,
        "problem": False,
        "problem_code": 0,
    }


class MockRoyPowBleakClient(MockBleakClient):
    """Emulate a RoyPow BMS BleakClient."""

    CMDS: Final[dict[int, bytearray]] = {
        0x02: bytearray(b"\xea\xd1\x01\x04\xff\x02\xf9\xf5"),
        0x03: bytearray(b"\xea\xd1\x01\x04\xff\x03\xf8\xf5"),
        0x04: bytearray(b"\xea\xd1\x01\x04\xff\x04\xff\xf5"),
    }
    RESP: Final[dict[int, bytearray]] = {
        0x02: bytearray(  # cell info
            b"\xea\xd1\x01\x0f\xff\x02\x04\x04\x04\x0d\x2f\x0d\x2a\x0d\x29\x0d\x2c\xf6\xf5"
        ),
        0x03: bytearray(
            b"\xea\xd1\x01\x1a\xff\x03\x32\x00\x23\x00\x00\x00\x00\x04\x3b\x3b\x3b\x3c\x00\x10"
            b"\x00\x00\x00\x0c\x07\x00\x00\x00\xef\xf5"

        ),
        0x04: bytearray(  # 13.5V, 0A, 96%, 98.2Ah/105.0Ah
            b"\xea\xd1\x01\x39\xff\x04\x01\x60\x02\x00\x02\x03\x00\x01\x04\x9a\x28\x05\x00\x01\x06"
            b"\x9e\x24\x07\x00\x01\x08\x7f\x7d\x09\xff\xff\x0a\x04\xd4\x0b\x00\x16\x4a\x70\x0c\x25"
            b"\x03\x17\x00\x51\x45\x05\x44\x0d\x2e\x0d\x29\x0d\x14\x4e\x00\x00\x00\x6f\xf5"
        ),
    }

    def _response(
        self, char_specifier: BleakGATTCharacteristic | int | str | UUID, data: Buffer
    ) -> bytearray:

        if isinstance(char_specifier, str) and normalize_uuid_str(
            char_specifier
        ) == normalize_uuid_str("ffe1"):
            for k, v in self.CMDS.items():
                if bytearray(data).startswith(v):
                    return self.RESP[k]

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

        resp: Final[bytearray] = self._response(char_specifier, data)
        for notify_data in [
            resp[i : i + BT_FRAME_SIZE] for i in range(0, len(resp), BT_FRAME_SIZE)
        ]:
            self._notify_callback("MockRoyPowBleakClient", notify_data)


async def test_update(monkeypatch, reconnect_fixture: bool) -> None:
    """Test RoyPow BMS data update."""

    monkeypatch.setattr(
        "custom_components.bms_ble.plugins.basebms.BleakClient",
        MockRoyPowBleakClient,
    )

    bms = BMS(
        generate_ble_device("cc:cc:cc:cc:cc:cc", "MockBLEdevice", None, -73),
        reconnect_fixture,
    )

    result = await bms.async_update()

    assert result == ref_value()

    # query again to check already connected state
    result = await bms.async_update()
    assert bms._client and bms._client.is_connected is not reconnect_fixture

    await bms.disconnect()


# @pytest.fixture(
#     name="wrong_response",
#     params=[
#         (
#             bytearray(
#                 b"\xa3\x00\x00\x00\x65\x00\x00\x00\x00\x00\x18\x01\x03\x44\x00\x18\x00\x48\x00\x64\x05"
#                 b"\x31\xff\x8e\x00\x00\x27\x10\x00\x01\x00\x01\x00\x00\x00\x00\x00\x00\x00\x00\x00\x01"
#                 b"\x00\x02\x00\x00\xff\xff\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00"
#                 b"\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x70\x20"
#             ),
#             "wrong_type",
#         ),
#         (
#             bytearray(
#                 b"\xa2\x00\x00\x00\x65\x00\x00\x00\x00\x00\x18\x01\x03\x56\x00\x04\x0c\xfb\x0c\xfd\x0c"
#                 b"\xfb\x0c\xfa\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff"
#                 b"\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff"
#                 b"\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\x00\x03\x00\xcd"
#                 b"\x00\xc0\x00\xbe\xfc\x18\xfc\x18\xfc\x18\xfc\x18\xfc\x18\xfc\x18\x97\x6a"
#             ),
#             "single_type_sent",
#         ),
#         (
#             bytearray(  # correct CRC: 0x2186
#                 b"\xa1\x00\x00\x00\x65\x00\x00\x00\x00\x00\x18\x01\x03\x44\x00\x18\x00\x48\x00\x64\x05"
#                 b"\x31\xff\x8e\x00\x00\x27\x10\x00\x01\x00\x01\x00\x00\x00\x00\x00\x00\x00\x00\x00\x01"
#                 b"\x00\x02\x00\x00\xff\xff\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00"
#                 b"\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x21\x87"
#             ),
#             "wrong_CRC",
#         ),
#     ],
#     ids=lambda param: param[1],
# )
# def response(request):
#     """Return faulty response frame."""
#     return request.param[0]


# async def test_tx_notimplemented(monkeypatch) -> None:
#     """Test Ective BMS uuid_tx not implemented for coverage."""

#     monkeypatch.setattr(
#         "custom_components.bms_ble.plugins.basebms.BleakClient", MockECOWBleakClient
#     )

#     bms = BMS(
#         generate_ble_device("cc:cc:cc:cc:cc:cc", "MockBLEDevice", None, -73), False
#     )

#     with pytest.raises(NotImplementedError):
#         _ret: str = bms.uuid_tx()


# async def test_invalid_response(monkeypatch, wrong_response) -> None:
#     """Test data up date with BMS returning invalid data."""

#     monkeypatch.setattr(
#         "custom_components.bms_ble.plugins.ecoworthy_bms.BMS.BAT_TIMEOUT", 0.2
#     )

#     monkeypatch.setattr(
#         "tests.test_ecoworthy_bms.MockECOWBleakClient.RESP",
#         {0xA1: wrong_response, 0xA2: MockECOWBleakClient.RESP[0xA2]},
#     )

#     monkeypatch.setattr(
#         "custom_components.bms_ble.plugins.basebms.BleakClient",
#         MockECOWBleakClient,
#     )

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
#                 b"\xa1\x00\x00\x00\x65\x00\x00\x00\x00\x00\x18\x01\x03\x44\x00\x18\x00\x48\x00\x64\x05"
#                 b"\x31\xff\x8e\x00\x00\x27\x10\x00\x01\x00\x01\x00\x00\x00\x00\x00\x00\x00\x00\x00\x01"
#                 b"\x00\x02\x00\x00\xff\xff\x00\x00\x00\x00\x01\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00"
#                 b"\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x20\xD6"
#             ),
#             "first_bit",
#         ),
#         (
#             bytearray(
#                 b"\xa1\x00\x00\x00\x65\x00\x00\x00\x00\x00\x18\x01\x03\x44\x00\x18\x00\x48\x00\x64\x05"
#                 b"\x31\xff\x8e\x00\x00\x27\x10\x00\x01\x00\x01\x00\x00\x00\x00\x00\x00\x00\x00\x00\x01"
#                 b"\x00\x02\x00\x00\xff\xff\x00\x00\x00\x80\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00"
#                 b"\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x20\x0E"
#             ),
#             "last_bit",
#         ),
#     ],
#     ids=lambda param: param[1],
# )
# def prb_response(request):
#     """Return faulty response frame."""
#     return request.param


# async def test_problem_response(monkeypatch, problem_response) -> None:
#     """Test data update with BMS returning error flags."""

#     monkeypatch.setattr(
#         "tests.test_ecoworthy_bms.MockECOWBleakClient.RESP",
#         {0xA1: problem_response[0], 0xA2: MockECOWBleakClient.RESP[0xA2]},
#     )

#     monkeypatch.setattr(
#         "custom_components.bms_ble.plugins.basebms.BleakClient",
#         MockECOWBleakClient,
#     )

#     bms = BMS(generate_ble_device("cc:cc:cc:cc:cc:cc", "MockBLEdevice", None, -73))

#     result: BMSsample = await bms.async_update()
#     assert result == ref_value() | {
#         "problem": True,
#         "problem_code": 1 << (0 if problem_response[1] == "first_bit" else 15),
#     }

#     await bms.disconnect()
