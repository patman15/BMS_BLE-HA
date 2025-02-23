"""Test the ABC BMS implementation."""

from collections.abc import Buffer
from uuid import UUID

from bleak.backends.characteristic import BleakGATTCharacteristic
from bleak.uuids import normalize_uuid_str

# import pytest
from custom_components.bms_ble.plugins.abc_bms import BMS  # , BMSsample

from .bluetooth import generate_ble_device
from .conftest import MockBleakClient


class MockABCBleakClient(MockBleakClient):
    """Emulate a ABC BMS BleakClient."""

    RESP: dict[int, bytearray] = {
        0xF0: bytearray(
            b"\xcc\xf0\xa2\x6b\x00\x00\x00\x00\xa0\x86\x01\x40\x9e\x01\x07\x00\x63\x00\x00\x21"
        ),
        0xF1: bytearray(
            b"\xcc\xf1\x53\x4f\x4b\x2d\x42\x4d\x53\x0d\x00\x00\x00\x00\x00\x00\x00\x00\x00\x40"
        ),
        0xF2: bytearray(
            b"\xcc\xf2\x01\x01\x01\x14\x00\x00\x00\x00\x00\x00\x00\x02\x00\x00\x00\x00\x00\x7f"
        ),
        0xF3: bytearray(
            b"\xcc\xf3\x17\x03\x12\x00\x64\x00\x00\x01\x00\x00\x00\x00\x00\x00\x00\x00\x00\x36"
        ),
        0xF4: bytearray(
            b"\xcc\xf4\x01\x72\x0d\x00\x02\xa8\x0d\x00\x03\x2f\x0d\x00\x04\x88\x0d\x00\x00\x8b"
        ),
        0xF5: bytearray(
            b"\xcc\xf5\x42\x0e\x10\x0e\xc4\x09\xf6\x09\xa0\x86\x01\xa0\x86\x01\x00\x00\x00\x55"
        ),
        0xF6: bytearray(
            b"\xcc\xf6\x10\x72\x00\x80\x70\x00\x37\x00\x32\x00\x00\x00\x05\x00\x00\x00\x00\x23"
        ),
        0xF7: bytearray(
            b"\xcc\xf7\x20\x4e\x00\x40\x51\x00\x4b\x00\x46\x00\xec\xff\xf1\xff\x00\x00\x00\x8f"
        ),
        0xF8: bytearray(
            b"\xcc\xf8\x00\x64\x00\x80\x57\x00\x80\x70\x00\x10\x27\x00\x00\x00\x00\x00\x00\x3e"
        ),
        0xF9: bytearray(
            b"\xcc\xf9\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\xed"
        ),
        0xFA: bytearray(
            b"\xcc\xfa\x48\x0d\x14\x00\x0f\x27\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\xd6"
        ),
    }

    def _response(
        self, char_specifier: BleakGATTCharacteristic | int | str | UUID, data: Buffer
    ) -> bytearray:
        if isinstance(char_specifier, str) and normalize_uuid_str(
            char_specifier
        ) != normalize_uuid_str("ffe2"):
            return bytearray()

        # if (cmd := int(bytearray(data)[1]) | 0xF0) not in self.RESP:
        #     pytest.fail("Unknown query 0x%X" % cmd)

        return self.RESP.get(int(bytearray(data)[1]) | 0xF0, bytearray())

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
            "MockABCBleakClient", self._response(char_specifier, data)
        )


# class MockInvalidBleakClient(MockABCBleakClient):
#     """Emulate a ABC BMS BleakClient."""

#     RESP: dict[int, bytearray] = {
#         0x09: bytearray(b"\x12\x34\x00\x00\x00\x56\x78"),  # invalid start/end
#         0x0A: bytearray(
#             b"\xAA\x55\x0B\x08\x58\x34\x00\x00\xBC\xF3\xFF\xFF\x4C\x0D\x0A"
#         ),  # wrong answer to capacity req (0xA) with 0xB: voltage, cur -> pwr, charging
#         0x0B: bytearray(b"invalid_len"),  # invalid length
#         0x15: bytearray(b"\xAA\x55\x15\x04\x00\x00\x00\x00\x00\x0D\x0A"),  # wrong CRC
#         0x21: bytearray(0),  # empty frame
#     }

#     async def disconnect(self) -> bool:
#         """Mock disconnect to raise BleakError."""
#         raise BleakError


# class MockPartBaseDatBleakClient(MockABCBleakClient):
#     """Emulate a ABC BMS BleakClient."""

#     RESP: dict[int, bytearray] = {
#         0x0B: bytearray(
#             b"\xAA\x55\x0B\x08\x58\x34\x00\x00\x00\x00\x00\x00\x9F\x0D\x0A"
#         )  # voltage/current frame, positive current
#     }


# class MockAllCellsBleakClient(MockABCBleakClient):
#     """Emulate a ABC BMS BleakClient."""

#     RESP: dict[int, bytearray] = {
#         0x05: bytearray(
#             b"\xAA\x55\x05\x0A\x0B\x0D\x0A\x0D\x09\x0D\x08\x0D\x07\x0D\x7D\x0D\x0A"
#         ),
#         0x06: bytearray(
#             b"\xAA\x55\x06\x0A\x06\x0D\x05\x0D\x04\x0D\x03\x0D\x02\x0D\x65\x0D\x0A"
#         ),
#         0x07: bytearray(
#             b"\xAA\x55\x07\x0A\x01\x0D\x00\x0D\xFF\x0C\xFE\x0C\xFD\x0C\x4A\x0D\x0A"
#         ),
#         0x08: bytearray(
#             b"\xAA\x55\x08\x0A\xFC\x0C\xFB\x0C\xFA\x0C\xF9\x0C\xF8\x0C\x30\x0D\x0A"
#         ),
#         0x09: bytearray(
#             b"\xAA\x55\x09\x0C\x15\x00\x15\x00\x00\x00\x00\x00\x00\x00\x00\x00\x3F\x0D\x0A"
#         ),  # temperature frame
#         0x0B: bytearray(
#             b"\xAA\x55\x0B\x08\x58\x34\x00\x00\xBC\xF3\xFF\xFF\x4C\x0D\x0A"
#         ),  # voltage/current frame
#         0x15: bytearray(
#             b"\xAA\x55\x15\x04\x28\x00\x03\x00\x44\x0D\x0A"
#         ),  # cycle info frame
#         0x0A: bytearray(
#             b"\xAA\x55\x0A\x06\x64\x13\x0D\x00\x00\x00\x94\x0D\x0A"
#         ),  # capacity frame
#         0x0C: bytearray(
#             b"\xAA\x55\x0C\x0C\x00\x00\x00\x00\x5B\x06\x00\x00\x03\x00\x74\x02\xF2\x0D\x0A"
#         ),  # runtime info frame, 6.28h*100
#         0x21: bytearray(
#             b"\xAA\x55\x21\x04\x00\x00\x00\x00\x25\x0D\x0A"
#         ),  # warnings frame
#     }

#     def _response(
#         self, char_specifier: BleakGATTCharacteristic | int | str | UUID, data: Buffer
#     ) -> bytearray:
#         if isinstance(char_specifier, str) and normalize_uuid_str(
#             char_specifier
#         ) != normalize_uuid_str("ffe9"):
#             return bytearray()
#         cmd: int = int(bytearray(data)[2])

#         return self.RESP.get(cmd, bytearray())


async def test_update(monkeypatch, reconnect_fixture: bool) -> None:
    """Test ABC BMS data update."""

    monkeypatch.setattr(
        "custom_components.bms_ble.plugins.basebms.BleakClient", MockABCBleakClient
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
        "problem": False,
        "problem_code": 0,
    }

    # query again to check already connected state
    result = await bms.async_update()
    assert bms._client.is_connected is not reconnect_fixture

    await bms.disconnect()


# async def test_invalid_response(monkeypatch) -> None:
#     """Test data update with BMS returning invalid data."""

#     monkeypatch.setattr(
#         "custom_components.bms_ble.plugins.abc_bms.BMS.BAT_TIMEOUT", 0.1
#     )

#     monkeypatch.setattr(
#         "custom_components.bms_ble.plugins.basebms.BleakClient", MockInvalidBleakClient
#     )

#     bms = BMS(generate_ble_device("cc:cc:cc:cc:cc:cc", "MockBLEDevice", None, -73))

#     result = await bms.async_update()
#     assert result == {
#         "battery_charging": False,
#         "current": -3.14,
#         "power": -42.076,
#         "voltage": 13.4,
#         "problem": False,
#     }

#     await bms.disconnect()


# async def test_partly_base_data(monkeypatch) -> None:
#     """Test data update with BMS returning invalid data."""

#     monkeypatch.setattr(
#         "custom_components.bms_ble.plugins.abc_bms.BMS.BAT_TIMEOUT", 0.1
#     )

#     monkeypatch.setattr(
#         "custom_components.bms_ble.plugins.basebms.BleakClient",
#         MockPartBaseDatBleakClient,
#     )

#     bms = BMS(generate_ble_device("cc:cc:cc:cc:cc:cc", "MockBLEDevice", None, -73))

#     result = await bms.async_update()
#     assert result == {
#         "battery_charging": False,
#         "current": 0.0,
#         "power": 0.0,
#         "voltage": 13.4,
#         "problem": False,
#     }

#     await bms.disconnect()


# async def test_all_cell_voltages(monkeypatch) -> None:
#     """Test data update with BMS returning invalid data."""

#     monkeypatch.setattr(
#         "custom_components.bms_ble.plugins.abc_bms.BMS.BAT_TIMEOUT", 0.1
#     )

#     monkeypatch.setattr(
#         "custom_components.bms_ble.plugins.basebms.BleakClient", MockAllCellsBleakClient
#     )

#     bms = BMS(generate_ble_device("cc:cc:cc:cc:cc:cc", "MockBLEDevice", None, -73))

#     result = await bms.async_update()
#     assert result == {
#         "voltage": 13.4,
#         "current": -3.14,
#         "battery_level": 100,
#         "cycles": 3,
#         "cycle_charge": 40.0,
#         "cell#0": 3.339,
#         "cell#1": 3.338,
#         "cell#2": 3.337,
#         "cell#3": 3.336,
#         "cell#4": 3.335,
#         "cell#5": 3.334,
#         "cell#6": 3.333,
#         "cell#7": 3.332,
#         "cell#8": 3.331,
#         "cell#9": 3.330,
#         "cell#10": 3.329,
#         "cell#11": 3.328,
#         "cell#12": 3.327,
#         "cell#13": 3.326,
#         "cell#14": 3.325,
#         "cell#15": 3.324,
#         "cell#16": 3.323,
#         "cell#17": 3.322,
#         "cell#18": 3.321,
#         "cell#19": 3.320,
#         "delta_voltage": 0.019,
#         "temperature": 21,
#         "cycle_capacity": 536.0,
#         "design_capacity": 40,
#         "power": -42.076,
#         "runtime": 22608,
#         "battery_charging": False,
#         "problem": False,
#         "problem_code": 0,
#     }

#     await bms.disconnect()


# @pytest.fixture(
#     name="problem_response",
#     params=[
#         (
#             {0x21: bytearray(b"\xAA\x55\x21\x04\x01\x00\x00\x00\x26\x0D\x0A")},
#             "first_bit",
#         ),
#         (
#             {0x21: bytearray(b"\xAA\x55\x21\x04\x00\x00\x00\x80\xA5\x0D\x0A")},
#             "last_bit",
#         ),
#     ],
#     ids=lambda param: param[1],
# )
# def prb_response(request) -> dict[int, bytearray]:
#     """Return faulty response frame."""
#     return request.param[0]


# async def test_problem_response(monkeypatch, problem_response: dict[int, bytearray]) -> None:
#     """Test data update with BMS returning error flags."""

#     monkeypatch.setattr(  # patch response dictionary to only problem reports (no other data)
#         "tests.test_abc_bms.MockABCBleakClient.RESP", problem_response
#     )

#     monkeypatch.setattr(
#         "custom_components.bms_ble.plugins.basebms.BleakClient", MockABCBleakClient
#     )

#     bms = BMS(generate_ble_device("cc:cc:cc:cc:cc:cc", "MockBLEdevice", None, -73))

#     result: BMSsample = await bms.async_update()
#     assert result.get("problem", False)  # expect a problem report

#     await bms.disconnect()
