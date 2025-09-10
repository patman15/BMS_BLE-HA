"""Test the Seplos BMS implementation."""

from collections.abc import Buffer
from uuid import UUID

from bleak.backends.characteristic import BleakGATTCharacteristic
from bleak.exc import BleakError
from bleak.uuids import normalize_uuid_str
import pytest

from custom_components.bms_ble.plugins.basebms import BMSsample
from custom_components.bms_ble.plugins.seplos_bms import BMS

from .bluetooth import generate_ble_device
from .conftest import MockBleakClient

BT_FRAME_SIZE = 27  # ATT maximum is 512, minimal 27
CHAR_UUID = "fff1"
REF_VALUE: BMSsample = {
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
    "pack_count": 2,  # last packet does not report data!
    "cell_voltages": [
        3.272,
        3.272,
        3.272,
        3.271,
        3.271,
        3.271,
        3.271,
        3.27,
        3.27,
        3.271,
        3.271,
        3.271,
        3.271,
        3.272,
        3.272,
        3.272,
        3.528,
        3.528,
        3.528,
        3.527,
        3.527,
        3.527,
        3.527,
        3.526,
        3.526,
        3.527,
        3.527,
        3.527,
        3.527,
        3.528,
        3.528,
        3.529,
    ],
    "delta_voltage": 0.003,
    "temp_values": [25.0, 23.8, 23.9, 24.9, 25.0, 23.8, 23.9, 24.9],
    "pack_battery_levels": [47.9, 48.0],
    "pack_currents": [-7.2, -7.19],
    "pack_cycles": [9, 10],
    "pack_voltages": [52.34, 52.35],
    "problem": False,
    "problem_code": 0,
}


class MockSeplosBleakClient(MockBleakClient):
    """Emulate a Seplos BMS BleakClient."""

    PKT_FRAME = 0x5  # header(3) + crc(2)
    RESP: dict[str, bytearray] = {
        "EIA": bytearray(
            b"\x00\x04\x34\x14\x72\x00\x00\xff\xbd\xff\xff\x34\x64\x00\x00\x6d\x60\x00\x00\x00\xd5"
            b"\x00\x00\x6d\x60\x00\x00\x00\x01\x00\x00\x00\x00\x00\x00\x07\x08\x00\x00\x07\x08\x00"
            b"\x00\x02\x40\x01\xd0\x00\x02\x00\x09\x01\xdf\x03\xe7\xb3\x36"  # A3F6
        ),
        "EIB": bytearray(
            b"\x00\x04\x2c\x0c\xc9\x0c\xc6\x00\x02\x00\x07\x14\x72\x14\x72\x00\x00\x00\x00\x00\xfa"
            b"\x00\xee\x00\xf4\x00\x00\x00\x01\x01\xdf\x01\xdf\x00\x09\x03\xe7\x01\x0a\x01\x0a\x01"
            b"\x0a\x00\x00\x00\x00\x57\x96"
        ),
        "EIC": bytearray(
            b"\x00\x01\x0a\x01\x00\x00\x00\x00\x00\x00\x03\x00\x00\x7e\x35"
        ),  # discharge, dis/charge-FET on, no alarm
        "EIX": bytearray(  # Note: unknown to the BMS implementation, just for testing
            b"\x00\x04\x20\x14\x72\xfd\x30\x34\x64\x6d\x60\x00\xd5\x01\xdf\x03\xe7\x00\x09\x0c\xc7"
            b"\x0b\x9f\x0c\xc8\x0c\xc6\x0b\xa5\x0b\x99\x00\x00\x00\xb4\x62\xb0"
        ),
        "PIA1": bytearray(
            b"\x01\x04\x22\x14\x72\xfd\x30\x34\x64\x6d\x60\x00\xd5\x01\xdf\x03\xe7\x00\x09\x0c\xc7"
            b"\x0b\x9f\x0c\xc8\x0c\xc6\x0b\xa5\x0b\x99\x00\x00\x00\xb4\x00\xb4\x6f\xf3"
        ),
        "PIA2": bytearray(
            b"\x02\x04\x22\x14\x73\xfd\x31\x34\x64\x6d\x60\x00\xd5\x01\xe0\x03\xe7\x00\x0a\x0c\xc7"
            b"\x0b\x9f\x0c\xc8\x0c\xc6\x0b\xa5\x0b\x99\x00\x00\x00\xb4\x00\xb4\xa6\xe2"
        ),
        "PIB1": bytearray(
            b"\x01\x04\x34\x0c\xc8\x0c\xc8\x0c\xc8\x0c\xc7\x0c\xc7\x0c\xc7\x0c\xc7\x0c\xc6\x0c\xc6"
            b"\x0c\xc7\x0c\xc7\x0c\xc7\x0c\xc7\x0c\xc8\x0c\xc8\x0c\xc8\x0b\xa5\x0b\x99\x0b\x9a\x0b"
            b"\xa4\x0a\xab\x0a\xab\x0a\xab\x0a\xab\x0b\xc4\x0b\xb5\x97\x1f"
        ),
        "PIB2": bytearray(
            b"\x02\x04\x34\x0d\xc8\x0d\xc8\x0d\xc8\x0d\xc7\x0d\xc7\x0d\xc7\x0d\xc7\x0d\xc6\x0d\xc6"
            b"\x0d\xc7\x0d\xc7\x0d\xc7\x0d\xc7\x0d\xc8\x0d\xc8\x0d\xc9\x0b\xa5\x0b\x99\x0b\x9a\x0b"
            b"\xa4\x0a\xab\x0a\xab\x0a\xab\x0a\xab\x0b\xc4\x0b\xb5\x53\xf1"
        ),
        "PIB3": bytearray(  # Note: incorrect answer for testing battery packet count mismatch
            b"\x02\x04\x34"
        )
        + bytearray(54),
    }

    def _crc16(self, data: bytearray) -> int:
        """Calculate CRC-16-CCITT XMODEM (ModBus)."""

        crc: int = 0xFFFF
        for i in data:
            crc ^= i & 0xFF
            for _ in range(8):
                crc = (crc >> 1) ^ 0xA001 if crc % 2 else (crc >> 1)
        return ((0xFF00 & crc) >> 8) | ((crc & 0xFF) << 8)

    def _response(self, data: Buffer) -> bytearray:

        req = bytearray(data)

        assert int.from_bytes(req[-2:]) == self._crc16(req[:-2])  # check CRC of request
        assert req[1] in [0x01, 0x04]  # check if read command

        device, start, length = [
            int(req[0]),
            int.from_bytes(req[2:4], byteorder="big"),
            int.from_bytes(req[4:6], byteorder="big") * (2 if req[1] == 0x4 else 0.125)
            + self.PKT_FRAME,
        ]

        if device == 0x00:  # EMS device
            if start == 0x2000:
                assert length == len(self.RESP["EIA"])
                return self.RESP["EIA"].copy()
            if start == 0x2100:
                assert length == len(self.RESP["EIB"])
                return self.RESP["EIB"].copy()
            if start == 0x2200:
                assert length == len(self.RESP["EIC"])
                return self.RESP["EIC"].copy()
        if device and device <= 0x10:  # BMS battery packs
            if start == 0x1000:
                assert length == len(self.RESP[f"PIA{device}"])
                return self.RESP[f"PIA{device}"].copy()
            if start == 0x1100:
                assert length == len(self.RESP[f"PIB{device}"])
                return self.RESP[f"PIB{device}"].copy()

        return bytearray()

    async def send_frag_response(
        self,
        data: Buffer,
        _response: bool | None = None,
    ) -> None:
        """Send fragmented response."""

        assert (
            self._notify_callback
        ), "write to characteristics but notification not enabled"

        resp: bytearray = self._response(data)
        for notify_data in [
            resp[i : min(len(resp), i + BT_FRAME_SIZE)]
            for i in range(0, len(resp), BT_FRAME_SIZE)
        ]:
            self._notify_callback("MockSeplosBleakClient", notify_data)

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
        assert isinstance(char_specifier, str) and normalize_uuid_str(
            char_specifier
        ) == normalize_uuid_str("fff2")

        await self.send_frag_response(data)


class MockWrongCRCBleakClient(MockSeplosBleakClient):
    """Emulate a Seplos BMS BleakClient returning wrong data."""

    async def send_frag_response(
        self,
        data: Buffer,
        _response: bool | None = None,
    ) -> None:
        """Send fragmented response."""

        assert (
            self._notify_callback
        ), "write to characteristics but notification not enabled"

        resp = self._response(data)
        resp[-2:] = bytearray(b"\00\00")  # make CRC invalid
        for notify_data in [
            resp[i : min(len(resp), i + BT_FRAME_SIZE)]
            for i in range(0, len(resp), BT_FRAME_SIZE)
        ]:
            self._notify_callback("MockInvalidBleakClient", notify_data)


class MockErrRespBleakClient(MockSeplosBleakClient):
    """Emulate a Seplos BMS BleakClient returning error message."""

    def _response(self, data: Buffer) -> bytearray:
        # return error code 0x2 on read request (0x04)
        return bytearray(b"\x00\x84\x02\x93\x01")

    async def disconnect(self) -> bool:
        """Mock disconnect to raise BleakError."""
        raise BleakError


class MockInvalidMessageBleakClient(MockSeplosBleakClient):
    """Emulate a Seplos BMS BleakClient returning unknown message type."""

    def _response(self, data: Buffer) -> bytearray:
        return self.RESP["EIX"]


class MockOversizedBleakClient(MockSeplosBleakClient):
    """Emulate a Seplos BMS BleakClient returning wrong data length."""

    async def send_frag_response(
        self,
        data: Buffer,
        _response: bool | None = None,
    ) -> None:
        """Send fragmented response and add trash to each message."""

        assert (
            self._notify_callback
        ), "write to characteristics but notification not enabled"

        # add garbage at the end for robustness
        resp = self._response(data) + bytearray(b"\xc0\xff\xee")

        for notify_data in [
            resp[i : min(len(resp), i + BT_FRAME_SIZE)]
            for i in range(0, len(resp), BT_FRAME_SIZE)
        ]:
            self._notify_callback("MockOversizedBleakClient", notify_data)


async def test_update(patch_bleak_client, keep_alive_fixture) -> None:
    """Test Seplos BMS data update."""

    patch_bleak_client(MockSeplosBleakClient)

    bms = BMS(
        generate_ble_device("cc:cc:cc:cc:cc:cc", "MockBLEdevice", None, -73),
        keep_alive_fixture,
    )

    assert await bms.async_update() == REF_VALUE

    # query again to check already connected state
    assert await bms.async_update() == REF_VALUE
    assert bms._client and bms._client.is_connected is keep_alive_fixture

    await bms.disconnect()


async def test_wrong_crc(patch_bleak_client, patch_bms_timeout) -> None:
    """Test data update with BMS returning invalid data (wrong CRC)."""

    patch_bms_timeout()

    patch_bleak_client(MockWrongCRCBleakClient)

    bms = BMS(generate_ble_device("cc:cc:cc:cc:cc:cc", "MockBLEdevice", None, -73))

    result: BMSsample = {}
    with pytest.raises(TimeoutError):
        result = await bms.async_update()

    assert not result

    await bms.disconnect()


async def test_error_response(patch_bleak_client, patch_bms_timeout) -> None:
    """Test data update with BMS returning error message."""

    patch_bms_timeout()

    patch_bleak_client(MockErrRespBleakClient)

    bms = BMS(generate_ble_device("cc:cc:cc:cc:cc:cc", "MockBLEdevice", None, -73))

    result: BMSsample = {}
    with pytest.raises(TimeoutError):
        result = await bms.async_update()

    assert not result

    await bms.disconnect()


async def test_oversized_response(patch_bleak_client) -> None:
    """Test data update with BMS returning oversized data, result shall still be ok."""

    patch_bleak_client(MockOversizedBleakClient)

    bms = BMS(generate_ble_device("cc:cc:cc:cc:cc:cc", "MockBLEdevice", None, -73))

    assert await bms.async_update() == REF_VALUE

    await bms.disconnect()


async def test_invalid_message(patch_bleak_client, patch_bms_timeout) -> None:
    """Test data update with BMS returning error message."""

    patch_bms_timeout()
    patch_bleak_client(MockInvalidMessageBleakClient)

    bms = BMS(generate_ble_device("cc:cc:cc:cc:cc:cc", "MockBLEdevice", None, -73))

    result: BMSsample = {}
    with pytest.raises(TimeoutError):
        result = await bms.async_update()

    assert not result

    await bms.disconnect()


# Alaramflags used: TB02, TB03, TB05, TB06, TB15
#          skipped: TB09, TB04, TB16, TB07, TB08
async def test_problem_response(monkeypatch, patch_bleak_client) -> None:
    """Test data update with BMS returning invalid data (wrong CRC)."""

    problem_resp: dict[str, bytearray] = MockSeplosBleakClient.RESP.copy()
    problem_resp["EIC"] = bytearray(
        b"\x00\x01\x0a\x01\xff\xff\xff\xff\xff\xff\xff\x03\xff\xcb\x45"
    )

    monkeypatch.setattr(MockSeplosBleakClient, "RESP", problem_resp)

    patch_bleak_client(MockSeplosBleakClient)

    bms = BMS(generate_ble_device("cc:cc:cc:cc:cc:cc", "MockBLEdevice", None, -73))

    assert await bms.async_update() == REF_VALUE | {
        "problem": True,
        "problem_code": 0xFFFF00FF00FF0000FF,
    }
