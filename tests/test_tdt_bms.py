"""Test the TDT implementation."""

from collections.abc import Buffer
from typing import Final
from uuid import UUID

from bleak.backends.characteristic import BleakGATTCharacteristic

# from bleak.exc import BleakError
from bleak.uuids import normalize_uuid_str

from custom_components.bms_ble.plugins.tdt_bms import BMS

from .bluetooth import generate_ble_device
from .conftest import MockBleakClient

BT_FRAME_SIZE = 200


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
        0x8C: bytearray(
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

        assert (
            self._notify_callback
        ), "write to characteristics but notification not enabled"

        resp = self._response(char_specifier, data)
        for notify_data in [
            resp[i : i + BT_FRAME_SIZE] for i in range(0, len(resp), BT_FRAME_SIZE)
        ]:
            self._notify_callback("MockTDTBleakClient", notify_data)


# class MockInvalidBleakClient(MockTDTBleakClient):
#     """Emulate a TDT BMS BleakClient returning wrong data."""

#     def _response(
#         self, char_specifier: BleakGATTCharacteristic | int | str | UUID, data: Buffer
#     ) -> bytearray:
#         if (
#             isinstance(char_specifier, str)
#             and normalize_uuid_str(char_specifier) == normalize_uuid_str("ff02")
#             and bytearray(data)[0] == self.HEAD_CMD
#         ):
#             if bytearray(data)[1:3] == self.CMD_INFO:
#                 return bytearray(  # wrong end
#                     b"\xdd\x03\x00\x1D\x06\x18\xFE\xE1\x01\xF2\x01\xF4\x00\x2A\x2C\x7C\x00\x00\x00"
#                     b"\x00\x00\x00\x80\x64\x03\x04\x03\x0B\x8B\x0B\x8A\x0B\x84\xf8\x84\xdd"
#                 )

#             return (  # wrong CRC
#                 bytearray(b"\xdd\x03\x00\x1d") + bytearray(31) + bytearray(b"\x77")
#             )

#         return bytearray()

#     async def disconnect(self) -> bool:
#         """Mock disconnect to raise BleakError."""
#         raise BleakError


# class MockOversizedBleakClient(MockTDTBleakClient):
#     """Emulate a TDT BMS BleakClient returning wrong data length."""

#     def _response(
#         self, char_specifier: BleakGATTCharacteristic | int | str | UUID, data: Buffer
#     ) -> bytearray:
#         if (
#             isinstance(char_specifier, str)
#             and normalize_uuid_str(char_specifier) == normalize_uuid_str("ff02")
#             and bytearray(data)[0] == self.HEAD_CMD
#         ):
#             if bytearray(data)[1:3] == self.CMD_INFO:
#                 return bytearray(
#                     b"\xdd\x03\x00\x1D\x06\x18\xFE\xE1\x01\xF2\x01\xF4\x00\x2A\x2C\x7C\x00\x00\x00"
#                     b"\x00\x00\x00\x80\x64\x03\x04\x03\x0B\x8B\x0B\x8A\x0B\x84\xf8\x84\x77"
#                     b"\00\00\00\00\00\00"  # oversized response
#                 )  # {'voltage': 15.6, 'current': -2.87, 'battery_level': 100, 'cycle_charge': 4.98, 'cycles': 42, 'temperature': 22.133333333333347}
#             if bytearray(data)[1:3] == self.CMD_CELL:
#                 return bytearray(
#                     b"\xdd\x04\x00\x08\x0d\x66\x0d\x61\x0d\x68\x0d\x59\xfe\x3c\x77"
#                     b"\00\00\00\00\00\00\00\00\00\00\00\00"  # oversized response
#                 )  # {'cell#0': 3.43, 'cell#1': 3.425, 'cell#2': 3.432, 'cell#3': 3.417}

#         return bytearray()

#     async def disconnect(self) -> bool:
#         """Mock disconnect to raise BleakError."""
#         raise BleakError


async def test_update(monkeypatch, reconnect_fixture) -> None:
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

    assert result == {
        "cell_count": 16,
        "temp_sensors": 6,
        "voltage": 52.7,
        "current": -5.7,
        "battery_level": 91,
        "cycle_charge": 99.1,
        "cycles": 8,
        "temperature": 22.55,
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
        "delta_voltage": 0.012,
        "runtime": 62589,
    }

    # query again to check already connected state
    result = await bms.async_update()
    assert (
        bms._client and bms._client.is_connected is not reconnect_fixture
    )  # noqa: SLF001

    await bms.disconnect()


# async def test_invalid_response(monkeypatch) -> None:
#     """Test data update with BMS returning invalid data (wrong CRC)."""

#     monkeypatch.setattr(
#         "custom_components.bms_ble.plugins.basebms.BleakClient",
#         MockInvalidBleakClient,
#     )

#     bms = BMS(generate_ble_device("cc:cc:cc:cc:cc:cc", "MockBLEdevice", None, -73))

#     result = await bms.async_update()

#     assert result == {}

#     await bms.disconnect()


# async def test_oversized_response(monkeypatch) -> None:
#     """Test data update with BMS returning oversized data, result shall still be ok."""

#     monkeypatch.setattr(
#         "custom_components.bms_ble.plugins.basebms.BleakClient",
#         MockOversizedBleakClient,
#     )

#     bms = BMS(generate_ble_device("cc:cc:cc:cc:cc:cc", "MockBLEdevice", None, -73))

#     result = await bms.async_update()

#     assert result == {
#         "temp_sensors": 3,
#         "voltage": 15.6,
#         "current": -2.87,
#         "battery_level": 100,
#         "cycle_charge": 4.98,
#         "cycles": 42,
#         "temperature": 22.133,
#         "cycle_capacity": 77.688,
#         "power": -44.772,
#         "battery_charging": False,
#         "runtime": 6246,
#         "cell#0": 3.43,
#         "cell#1": 3.425,
#         "cell#2": 3.432,
#         "cell#3": 3.417,
#         "temp#0": 22.4,
#         "temp#1": 22.3,
#         "temp#2": 21.7,
#         "delta_voltage": 0.015,
#     }

#     await bms.disconnect()
