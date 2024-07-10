"""Test the Seplos BMS implementation."""

from collections.abc import Awaitable, Buffer, Callable
import logging
from uuid import UUID

from bleak.backends.characteristic import BleakGATTCharacteristic
from bleak.exc import BleakError
from bleak.uuids import normalize_uuid_str
from custom_components.bms_ble.plugins.seplos_bms import BMS

from .bluetooth import generate_ble_device
from .conftest import MockBleakClient

LOGGER = logging.getLogger(__name__)
BT_FRAME_SIZE = 150
CHAR_UUID = "fff1"


class MockSeplosBleakClient(MockBleakClient):
    """Emulate a Seplos BMS BleakClient."""

    PKT_FRAME = 0x5  # header(3) + CRC(2)
    RESP = {
        "EIA": bytearray(
            b"\x00\x04\x34\x14\x72\x00\x00\xFF\xBD\xFF\xFF\x34\x64\x00\x00\x6D\x60\x00\x00\x00\xD5"
            b"\x00\x00\x6D\x60\x00\x00\x00\x01\x00\x00\x00\x00\x00\x00\x07\x08\x00\x00\x07\x08\x00"
            b"\x00\x02\x40\x01\xD0\x00\x02\x00\x09\x01\xDF\x03\xE7\xB3\x36"
        ),
        "EIB": bytearray(
            b"\x00\x04\x2C\x0C\xC9\x0C\xC6\x00\x02\x00\x07\x14\x72\x14\x72\x00\x00\x00\x00\x00\xFA"
            b"\x00\xEE\x00\xF4\x00\x00\x00\x01\x01\xDF\x01\xDF\x00\x09\x03\xE7\x01\x0A\x01\x0A\x01"
            b"\x0A\x00\x00\x00\x00\x57\x96"
        ),
        "PIB1": bytearray(
            b"\x01\x04\x34\x0C\xC8\x0C\xC8\x0C\xC8\x0C\xC7\x0C\xC7\x0C\xC7\x0C\xC7\x0C\xC6\x0C\xC6"
            b"\x0C\xC7\x0C\xC7\x0C\xC7\x0C\xC7\x0C\xC8\x0C\xC8\x0C\xC8\x0B\xA5\x0B\x99\x0B\x9A\x0B"
            b"\xA4\x0A\xAB\x0A\xAB\x0A\xAB\x0A\xAB\x0B\xC4\x0B\xB5\x97\x1F"
        ),
        "PIB2": bytearray(
            b"\x02\x04\x34\x0D\xC8\x0D\xC8\x0D\xC8\x0D\xC7\x0D\xC7\x0D\xC7\x0D\xC7\x0D\xC6\x0D\xC6"
            b"\x0D\xC7\x0D\xC7\x0D\xC7\x0D\xC7\x0D\xC8\x0D\xC8\x0D\xC9\x0B\xA5\x0B\x99\x0B\x9A\x0B"
            b"\xA4\x0A\xAB\x0A\xAB\x0A\xAB\x0A\xAB\x0B\xC4\x0B\xB5\x53\xF1"
        )
    }

    def _crc16(self, data: bytearray) -> int:
        """Calculate CRC-16-CCITT XMODEM (ModBus)."""

        crc: int = 0xFFFF
        for i in data:
            crc ^= i & 0xFF
            for _ in range(8):
                crc = (crc >> 1) ^ 0xA001 if crc % 2 else (crc >> 1)
        return ((0xFF00 & crc) >> 8) | ((crc & 0xFF) << 8)

    def _response(
        self, char_specifier: BleakGATTCharacteristic | int | str | UUID, data: Buffer
    ) -> bytearray:

        LOGGER.debug("response command")
        req = bytearray(data)

        assert int.from_bytes(req[-2:]) == self._crc16(req[:-2])  # check CRC of request
        assert req[1] == 0x04  # check if read command

        device, start, length = [
            int(req[0]),
            int.from_bytes(req[2:4], byteorder="big"),
            int.from_bytes(req[5:6], byteorder="big") * 2 + self.PKT_FRAME,
        ]
        LOGGER.debug("request device=%i start=0x%x length=%i", device, start, length)
        if device == 0x00:  # EMS device
            if start == 0x2000:
                assert length == len(self.RESP["EIA"])
                return self.RESP["EIA"]
            if start == 0x2100:
                assert length == len(self.RESP["EIB"])
                return self.RESP["EIB"]
        if device and device <= 0x10:  # BMS battery pack #1
            if start == 0x1100:
                assert length == len(self.RESP[f"PIB{device}"])
                return self.RESP[f"PIB{device}"]

        return bytearray()

    async def send_frag_response(
        self,
        char_specifier: BleakGATTCharacteristic | int | str | UUID,
        data: Buffer,
        response: bool = None,  # type: ignore[implicit-optional] # same as upstream
    ) -> None:
        """Send fragmented response."""

        assert (
            self._notify_callback
        ), "write to characteristics but notification not enabled"

        resp = self._response(char_specifier, data)
        for notify_data in [
            resp[i : i + BT_FRAME_SIZE] for i in range(0, len(resp), BT_FRAME_SIZE)
        ]:
            self._notify_callback("MockSeplosBleakClient", notify_data)

    async def write_gatt_char(
        self,
        char_specifier: BleakGATTCharacteristic | int | str | UUID,
        data: Buffer,
        response: bool = None,  # type: ignore[implicit-optional] # same as upstream
    ) -> None:
        """Issue write command to GATT."""

        assert (
            self._notify_callback
        ), "write to characteristics but notification not enabled"

        await self.send_frag_response(char_specifier, data)


class MockInvalidBleakClient(MockSeplosBleakClient):
    """Emulate a Seplos BMS BleakClient returning wrong data."""

    def _response(
        self, char_specifier: BleakGATTCharacteristic | int | str | UUID, data: Buffer
    ) -> bytearray:
        if char_specifier == normalize_uuid_str(CHAR_UUID):
            return bytearray(b"\xdd\x03\x00\x1d") + bytearray(31) + bytearray(b"\x77")

        return bytearray()

    async def disconnect(self) -> bool:
        """Mock disconnect to raise BleakError."""
        raise BleakError


class MockOversizedBleakClient(MockSeplosBleakClient):
    """Emulate a Seplos BMS BleakClient returning wrong data length."""

    def _response(
        self, char_specifier: BleakGATTCharacteristic | int | str | UUID, data: Buffer
    ) -> bytearray:
        if char_specifier == normalize_uuid_str(CHAR_UUID):
            if bytearray(data)[1:3] == self.CMD_INFO:
                return bytearray(
                    b"\xdd\x03\x00\x1D\x06\x18\xFE\xE1\x01\xF2\x01\xF4\x00\x2A\x2C\x7C\x00\x00\x00"
                    b"\x00\x00\x00\x80\x64\x03\x04\x03\x0B\x8B\x0B\x8A\x0B\x84\xf8\x84\x77"
                    b"\00\00\00\00\00\00"  # oversized response
                )  # {'voltage': 15.6, 'current': -2.87, 'battery_level': 100, 'cycle_charge': 4.98, 'cycles': 42, 'temperature': 22.133333333333347}
            if bytearray(data)[1:3] == self.CMD_CELL:
                LOGGER.debug("cell")
                return bytearray(
                    b"\xdd\x04\x00\x08\x0d\x66\x0d\x61\x0d\x68\x0d\x59\xfe\x3c\x77"
                    b"\00\00\00\00\00\00\00\00\00\00\00\00"  # oversized response
                )  # {'cell#0': 3.43, 'cell#1': 3.425, 'cell#2': 3.432, 'cell#3': 3.417}

        return bytearray()

    async def disconnect(self) -> bool:
        """Mock disconnect to raise BleakError."""
        raise BleakError


async def test_update(monkeypatch, reconnect_fixture) -> None:
    """Test Seplos BMS data update."""

    monkeypatch.setattr(
        "custom_components.bms_ble.plugins.seplos_bms.BleakClient",
        MockSeplosBleakClient,
    )

    bms = BMS(
        generate_ble_device("cc:cc:cc:cc:cc:cc", "MockBLEdevice", None, -73),
        reconnect_fixture,
    )

    result = await bms.async_update()

    assert result == {
        "voltage": 52.34,
        "current": -6.7,
        "battery_level": 47.9,
        "cycle_charge": 134.12,
        "cycles": 9,
        "temperature": 24.4,
        "cycle_capacity": 7019.841,
        "power": -350.678,
        "battery_charging": False,
        "runtime": 72064,
        "pack_count": 2,
        'cell#0': 3.272,
        'cell#1': 3.272,
        'cell#2': 3.272,
        'cell#3': 3.271,
        'cell#4': 3.271,
        'cell#5': 3.271,
        'cell#6': 3.271,
        'cell#7': 3.27,
        'cell#8': 3.27,
        'cell#9': 3.271,
        'cell#10': 3.271,
        'cell#11': 3.271,
        'cell#12': 3.271,
        'cell#13': 3.272,
        'cell#14': 3.272,
        'cell#15': 3.272,
        'cell#16': 3.528,
        'cell#17': 3.528,
        'cell#18': 3.528,
        'cell#19': 3.527,
        'cell#20': 3.527,
        'cell#21': 3.527,
        'cell#22': 3.527,
        'cell#23': 3.526,
        'cell#24': 3.526,
        'cell#25': 3.527,
        'cell#26': 3.527,
        'cell#27': 3.527,
        'cell#28': 3.527,
        'cell#29': 3.528,
        'cell#30': 3.528,
        'cell#31': 3.529,
        "delta_voltage": 0.003,
    }

    # query again to check already connected state
    result = await bms.async_update()
    assert bms._connected is not reconnect_fixture  # noqa: SLF001

    await bms.disconnect()


async def test_invalid_response(monkeypatch) -> None:
    """Test data update with BMS returning invalid data (wrong CRC)."""

    monkeypatch.setattr(
        "custom_components.bms_ble.plugins.seplos_bms.BleakClient",
        MockInvalidBleakClient,
    )

    bms = BMS(generate_ble_device("cc:cc:cc:cc:cc:cc", "MockBLEdevice", None, -73))

    result = await bms.async_update()

    assert result == {}

    await bms.disconnect()


async def test_oversized_response(monkeypatch) -> None:
    """Test data update with BMS returning oversized data, result shall still be ok."""

    monkeypatch.setattr(
        "custom_components.bms_ble.plugins.Seplos_bms.BleakClient",
        MockOversizedBleakClient,
    )

    bms = BMS(generate_ble_device("cc:cc:cc:cc:cc:cc", "MockBLEdevice", None, -73))

    result = await bms.async_update()

    assert result == {
        "temp_sensors": 3,
        "voltage": 15.6,
        "current": -2.87,
        "battery_level": 100,
        "cycle_charge": 4.98,
        "cycles": 42,
        "temperature": 22.133333333333347,
        "cycle_capacity": 77.688,
        "power": -44.772,
        "battery_charging": False,
        "runtime": 6246,
        "cell#0": 3.43,
        "cell#1": 3.425,
        "cell#2": 3.432,
        "cell#3": 3.417,
        "delta_voltage": 0.015,
    }

    await bms.disconnect()
