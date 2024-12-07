"""Test the Seplos v2 implementation."""

from collections.abc import Buffer
from uuid import UUID

from bleak.backends.characteristic import BleakGATTCharacteristic

# from bleak.exc import BleakError
from bleak.uuids import normalize_uuid_str

from custom_components.bms_ble.plugins.seplos_v2_bms import BMS

from .bluetooth import generate_ble_device
from .conftest import MockBleakClient

BT_FRAME_SIZE = 20


class MockSeplosv2BleakClient(MockBleakClient):
    """Emulate a Seplos v2 BMS BleakClient."""

    HEAD_CMD = 0x7E
    CMD_GSMD = bytearray([HEAD_CMD]) + bytearray(
        b"\x10\x00\x46\x61\x00\x01"
    )  # get single machine data
    CMD_GPD = bytearray([HEAD_CMD]) + bytearray(
        b"\x10\x00\x46\x62\x00\x00"
    )  # get parallel data

    def _response(
        self, char_specifier: BleakGATTCharacteristic | int | str | UUID, data: Buffer
    ) -> bytearray:

        if (
            isinstance(char_specifier, str)
            and normalize_uuid_str(char_specifier) == normalize_uuid_str("ff02")
            and bytearray(data)[0] == self.HEAD_CMD
        ):
            if bytearray(data).startswith(self.CMD_GSMD):
                return bytearray(
                    b"\x7e\x14\x02\x61\x00\x00\x6a\x00\x02\x10\x0c\xf0\x0c\xf1\x0c\xf1\x0c\xf1\x0c"
                    b"\xf1\x0c\xf0\x0c\xf1\x0c\xf3\x0c\xef\x0c\xf0\x0c\xf1\x0c\xf1\x0c\xf1\x0c\xf0"
                    b"\x0c\xf1\x0c\xf1\x06\x0b\x8f\x0b\x89\x0b\x8a\x0b\x93\x0b\xc0\x0b\x98\x02\xad"
                    b"\x14\xb4\x38\x3a\x06\x6d\x60\x02\x02\x6d\x60\x00\x80\x03\xe8\x14\xbb\x00\x00"
                    b"\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00"
                    b"\x00\x00\x00\x02\x03\x08\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\xc1"
                    b"\xd7\x0d"
                )
                # return bytearray(
                #     b"\x7E\x10\x00\x61\x00\x00\x6A\x00\x00\x10\x00\x17\x00\x30\x00\x4E\x00\x12\x00"
                #     b"\x12\x00\x12\x00\x12\x00\x12\x00\x12\x00\x15\x00\x1D\x00\x32\x00\x70\x01\x3B"
                #     b"\x04\x0D\x00\x0F\xD5\x06\x08\xB7\x08\xB7\x08\xB7\x08\xB7\x0B\xB8\x0B\xB5\x00"
                #     b"\x00\x02\x4B\x24\xF5\x06\x27\x10\x03\xB2\x27\x10\x00\x00\x03\xE8\x13\x93\x01"
                #     b"\x01\x01\x01\x01\x01\x01\x01\x01\x01\x01\x01\x01\x01\x01\x02\x01\x01\x00\x01"
                #     b"\x01\x00\x00\x00\x01\x20\x00\x08\x12\x8A\x08\x00\x00\x10\x00\x00\x00\x00\x00"
                #     b"\x00\x44\xCF\x0D"
                # )  # TODO: values
            if bytearray(data).startswith(self.CMD_GPD):
                return bytearray(
                    b"\x7e\x14\x00\x62\x00\x00\x30\x00\x00\x10\x0c\xf4\x0c\xee\x06\x0b\x93\x0b\x7f"
                    b"\x0b\xb6\x0b\x8d\x00\xd7\x14\xb4\x11\x14\x07\x20\xd0\x02\x08\x20\xd0\x00\x71"
                    b"\x03\xe8\x14\xb9\x07\x00\x02\x03\x08\x00\x00\x00\x00\x00\x00\x00\x00\x76\x31"
                    b"\x0d"
                )

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
            self._notify_callback("MockSeplosv2BleakClient", notify_data)


# class MockInvalidBleakClient(MockSeplosv2BleakClient):
#     """Emulate a Seplos V2 BMS BleakClient returning wrong data."""

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


# class MockOversizedBleakClient(MockSeplosv2BleakClient):
#     """Emulate a Seplos V2 BMS BleakClient returning wrong data length."""

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
    """Test Seplos V2 BMS data update."""

    monkeypatch.setattr(
        "custom_components.bms_ble.plugins.basebms.BleakClient",
        MockSeplosv2BleakClient,
    )

    bms = BMS(
        generate_ble_device("cc:cc:cc:cc:cc:cc", "MockBLEdevice", None, -73),
        reconnect_fixture,
    )

    result = await bms.async_update()

    assert result == {
        "cell_count": 16,
        "temp_sensors": 6,
        "voltage": 53.0,
        "current": 2.15,
        "battery_level": 52.0,
        "cycle_charge": 43.72,
        "cycles": 113,
        "temperature": 22.55,
        "cycle_capacity": 2317.16,
        "power": 113.95,
        "battery_charging": True,
        "cell#0": 3.312,
        "cell#1": 3.313,
        "cell#2": 3.313,
        "cell#3": 3.313,
        "cell#4": 3.313,
        "cell#5": 3.312,
        "cell#6": 3.313,
        "cell#7": 3.315,
        "cell#8": 3.311,
        "cell#9": 3.312,
        "cell#10": 3.313,
        "cell#11": 3.313,
        "cell#12": 3.313,
        "cell#13": 3.312,
        "cell#14": 3.313,
        "cell#15": 3.313,
        "delta_voltage": 0.004,
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
