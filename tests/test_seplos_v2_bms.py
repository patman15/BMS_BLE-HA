"""Test the Seplos v2 implementation."""

from collections.abc import Buffer
from typing import Final
from uuid import UUID

from bleak.backends.characteristic import BleakGATTCharacteristic
from bleak.uuids import normalize_uuid_str
import pytest

from custom_components.bms_ble.plugins.seplos_v2_bms import BMS, BMSsample

from .bluetooth import generate_ble_device
from .conftest import MockBleakClient

BT_FRAME_SIZE = 20
REF_VALUE: BMSsample = {
    "cell_count": 16,
    "temp_sensors": 6,
    "voltage": 53.0,
    "current": 6.85,
    "battery_level": 51.4,
    "cycle_charge": 143.94,
    "cycles": 128,
    "temperature": 23.6,
    "cycle_capacity": 7628.82,
    "power": 363.05,
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
    "temp#0": 22.75,
    "temp#1": 22.15,
    "temp#2": 22.25,
    "temp#3": 23.15,
    "temp#4": 27.65,
    "temp#5": 23.65,
    "delta_voltage": 0.004,
    "pack_count": 1,
    "problem": False,
    "problem_code": 0,
}

MI_RESP: Final[bytearray] = bytearray(  # manufacturer information
    b"\x7e\x14\x00\x51\x00\x00\x24\x43\x41\x4e\x3a\x50\x4e\x47\x5f\x44\x59\x45\x5f"
    b"\x4c\x75\x78\x70\x5f\x54\x42\x42\x31\x31\x30\x31\x2d\x53\x50\x37\x36\x20\x10"
    b"\x06\x01\x01\x46\x01\xa2\x6c\x0d"
)


class MockSeplosv2BleakClient(MockBleakClient):
    """Emulate a Seplos v2 BMS BleakClient."""

    HEAD_CMD = 0x7E
    PROTOCOL = 0x10
    CMD_GSMD = bytearray(b"\x46\x61\x00\x01\x00")  # get single machine data
    CMD_GPD = bytearray(
        bytes([HEAD_CMD, PROTOCOL]) + b"\x00\x46\x62\x00\x00"
    )  # get parallel data
    CMD_GMI = bytearray(
        bytes([HEAD_CMD, PROTOCOL]) + b"\00\x46\x51\x00\x00\x3a\x7f\x0d"
    )

    def _response(
        self, char_specifier: BleakGATTCharacteristic | int | str | UUID, data: Buffer
    ) -> bytearray:

        if (
            isinstance(char_specifier, str)
            and normalize_uuid_str(char_specifier) == normalize_uuid_str("ff02")
            and bytearray(data)[0] == self.HEAD_CMD
        ):
            if bytearray(data)[1] == self.PROTOCOL and bytearray(data)[3:].startswith(
                self.CMD_GSMD
            ):
                return bytearray(  # TODO: respond with correct address
                    b"\x7e\x14\x02\x61\x00\x00\x6a\x00\x02\x10\x0c\xf0\x0c\xf1\x0c\xf1\x0c\xf1\x0c"
                    b"\xf1\x0c\xf0\x0c\xf1\x0c\xf3\x0c\xef\x0c\xf0\x0c\xf1\x0c\xf1\x0c\xf1\x0c\xf0"
                    b"\x0c\xf1\x0c\xf1\x06\x0b\x8f\x0b\x89\x0b\x8a\x0b\x93\x0b\xc0\x0b\x98\x02\xad"
                    b"\x14\xb4\x38\x3a\x06\x6d\x60\x02\x02\x6d\x60\x00\x80\x03\xe8\x14\xbb\x00\x00"
                    b"\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00"
                    b"\x00\x00\x00\x02\x03\x08\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\xc1"
                    b"\xd7\x0d"
                )  # TODO: values
            if bytearray(data).startswith(self.CMD_GPD):
                return bytearray(
                    b"\x7e\x14\x00\x62\x00\x00\x30\x00\x00\x10\x0c\xf4\x0c\xee\x06\x0b\x93\x0b\x7f"
                    b"\x0b\xb6\x0b\x8d\x00\xd7\x14\xb4\x11\x14\x07\x20\xd0\x02\x08\x20\xd0\x00\x71"
                    b"\x03\xe8\x14\xb9\x07\x00\x02\x03\x08\x00\x00\x00\x00\x00\x00\x00\x00\x76\x31"
                    b"\x0d"
                )
            if bytearray(data).startswith(self.CMD_GMI):
                return MI_RESP

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

        resp: bytearray = self._response(char_specifier, data)
        for notify_data in [
            resp[i : i + BT_FRAME_SIZE] for i in range(0, len(resp), BT_FRAME_SIZE)
        ]:
            self._notify_callback("MockSeplosv2BleakClient", notify_data)


async def test_update(patch_bleak_client, reconnect_fixture) -> None:
    """Test Seplos V2 BMS data update."""

    patch_bleak_client(MockSeplosv2BleakClient)

    bms = BMS(
        generate_ble_device("cc:cc:cc:cc:cc:cc", "MockBLEdevice", None, -73),
        reconnect_fixture,
    )

    result = await bms.async_update()

    assert result == REF_VALUE

    # query again to check already connected state
    result = await bms.async_update()
    assert bms._client and bms._client.is_connected is not reconnect_fixture

    await bms.disconnect()


@pytest.fixture(
    name="wrong_response",
    params=[
        (b"\x7e\x14\x00\x51\x00\x00\x01\x00\x7a\xef\x00", "invalid frame end"),
        (b"\x7e\x10\x00\x51\x00\x00\x01\x00\xbb\x29\x0d", "invalid version"),
        (b"\x7e\x14\x00\x51\x80\x00\x01\x00\xa7\xd7\x0d", "error response"),
        (b"\x7e\x14\x00\x51\x00\x00\x01\x00\x7a\xee\x0d", "invalid CRC"),
        (b"\x7e\x14\x00\x51\x00\x00\x01\x00\x7a\xef\x0d\x00", "oversized frame"),
        (b"\x7e\x14\x00\x51\x00\x00\x02\x00\x7a\xef\x0d", "undersized frame"),
    ],
    ids=lambda param: param[1],
)
def fix_response(request):
    """Return faulty response frame."""
    return request.param[0]


async def test_invalid_response(
    monkeypatch, patch_bleak_client, patch_bms_timeout, wrong_response
) -> None:
    """Test data up date with BMS returning invalid data."""

    patch_bms_timeout("seplos_v2_bms")

    monkeypatch.setattr(
        MockSeplosv2BleakClient, "_response", lambda _s, _c, _d: wrong_response
    )

    patch_bleak_client(MockSeplosv2BleakClient)

    bms = BMS(generate_ble_device("cc:cc:cc:cc:cc:cc", "MockBLEDevice", None, -73))

    result = {}
    with pytest.raises(TimeoutError):
        result = await bms.async_update()

    assert not result
    await bms.disconnect()


# Alarm flags: Events 1-6, excluding 7-8
async def test_problem_response(monkeypatch, patch_bleak_client) -> None:
    """Test data update with BMS returning invalid data (wrong CRC)."""

    def prb_response(
        self, char_specifier: BleakGATTCharacteristic | int | str | UUID, data: Buffer
    ) -> bytearray:

        if (
            isinstance(char_specifier, str)
            and normalize_uuid_str(char_specifier) == normalize_uuid_str("ff02")
            and bytearray(data)[0] == self.HEAD_CMD
        ):
            if bytearray(data)[1] == self.PROTOCOL and bytearray(data)[3:].startswith(
                self.CMD_GSMD
            ):
                return bytearray(  # TODO: respond with correct address
                    b"\x7e\x14\x02\x61\x00\x00\x6a\x00\x02\x10\x0c\xf0\x0c\xf1\x0c\xf1\x0c\xf1\x0c"
                    b"\xf1\x0c\xf0\x0c\xf1\x0c\xf3\x0c\xef\x0c\xf0\x0c\xf1\x0c\xf1\x0c\xf1\x0c\xf0"
                    b"\x0c\xf1\x0c\xf1\x06\x0b\x8f\x0b\x89\x0b\x8a\x0b\x93\x0b\xc0\x0b\x98\x02\xad"
                    b"\x14\xb4\x38\x3a\x06\x6d\x60\x02\x02\x6d\x60\x00\x80\x03\xe8\x14\xbb\x00\x00"
                    b"\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00"
                    b"\x00\x00\x00\x02\x03\x08\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\xc1"
                    b"\xd7\x0d"
                )  # TODO: values
            if bytearray(data).startswith(self.CMD_GPD):
                return bytearray(
                    b"\x7e\x14\x00\x62\x00\x00\x30\x00\x00\x10\x0c\xf4\x0c\xee\x06\x0b\x93\x0b\x7f"
                    b"\x0b\xb6\x0b\x8d\x00\xd7\x14\xb4\x11\x14\x07\x20\xd0\x02\x08\x20\xd0\x00\x71"
                    b"\x03\xe8\x14\xb9\x07\x00\x02\x03\x08\xff\xff\xff\xff\xff\xff\xff\xff\xd0\xd0"
                    b"\x0d"
                )
            if bytearray(data).startswith(self.CMD_GMI):
                return MI_RESP

        return bytearray()

    monkeypatch.setattr(MockSeplosv2BleakClient, "_response", prb_response)

    patch_bleak_client(MockSeplosv2BleakClient)

    bms = BMS(generate_ble_device("cc:cc:cc:cc:cc:cc", "MockBLEdevice", None, -73))

    assert await bms.async_update() == REF_VALUE | {
        "problem": True,
        "problem_code": 0xFFFFFFFFFFFF,
    }
