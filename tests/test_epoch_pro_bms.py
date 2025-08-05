"""Test the Epoch Pro BMS implementation."""

from collections.abc import Buffer
from uuid import UUID

from bleak.backends.characteristic import BleakGATTCharacteristic

# from bleak.exc import BleakError
from bleak.uuids import normalize_uuid_str
import pytest

from custom_components.bms_ble.plugins.basebms import BMSsample
from custom_components.bms_ble.plugins.epoch_pro_bms import BMS

from .bluetooth import generate_ble_device
from .conftest import MockBleakClient

BT_FRAME_SIZE = 32  # ATT maximum is 512, minimal 27
REF_VALUE: BMSsample = {
    "voltage": 53.21,
    "current": 0,
    "battery_level": 91,
    # "cycle_charge": 134.12,
    # "cycles": 9,
    "temperature": 27.0,
    # "cycle_capacity": 7019.841,
    "power": 0.0,
    "battery_charging": False,
    # "runtime": 72064,
    "pack_count": 2,
    "cell_voltages": [
        3.326,
        3.325,
        3.325,
        3.325,
        3.326,
        3.326,
        3.325,
        3.325,
        3.326,
        3.326,
        3.326,
        3.326,
        3.326,
        3.327,
        3.326,
        3.326,
        3.326,
        3.324,
        3.325,
        3.325,
        3.325,
        3.325,
        3.325,
        3.325,
        3.326,
        3.326,
        3.326,
        3.325,
        3.327,
        3.327,
        3.327,
        3.327,
    ],
    "delta_voltage": 0.003,
    "temp_values": [27] * 8,
    "pack_battery_levels": [91.0, 91.0],
    "pack_currents": [0.0, 0.0],
    "pack_cycles": [10, 10],
    "pack_voltages": [53.21, 53.21],
    "problem": False,
    # "problem_code": 0,
}


class MockEpochProBleakClient(MockBleakClient):
    """Emulate a Epoch Pro BMS BleakClient."""

    PKT_FRAME = 0x5  # header(3) + crc(2)
    RESP: dict[bytes, bytearray] = {
        b"\xfa\xf3\x16\x76\x54\x01\x00\x37\xc7\x24": bytearray(  # overall
            b"\xfa\xf3\x16\x01\x6e\x00\x00\x00\x00\x04\xb0\x00\x00\x00\x5b\x00\x64\x23\x8c\x14"
            b"\xc9\x00\x00\x01\x0e\x00\x00\x00\x00\x18\x7a\x00\x00\x00\x00\x00\x00\x00\x00\x00"
            b"\x00\x00\x00\x00\x00\x00\x00\x00\x02\x00\x00\x00\x00\x00\x00\x0c\xfd\x0c\xff\x00"
            b"\x1b\x00\x1b\x32\x30\x31\x2d\x00\x31\x00\x00\x32\x30\x31\x2d\x00\x34\x00\x00\x31"
            b"\x30\x30\x2d\x00\x31\x00\x00\x31\x30\x30\x2d\x00\x31\x00\x00\x00\x00\x00\x00\x00"
            b"\x00\x00\x00\x00\x38\xaa\xa8\x02\xaa\xaa\xa8\x00\x82\x00\x3c\x6b\x2f"
        ),
        b"\xfa\xf3\x16\x75\xf8\x01\x00\x52\x62\x5f": bytearray(  # pack 1
            b"\xfa\xf3\x16\x01\xa4\x02\x40\x01\xe0\x02\x58\x01\x2c\xc8\x78\x00\x00\x00\x00\x75"
            b"\x30\x00\x0a\x00\x00\x0c\x2c\x00\x00\x00\x00\x79\x7c\x00\x10\x0c\xfe\x0c\xfd\x00"
            b"\x10\x00\x07\x00\x1b\x00\x1b\x00\x04\x00\x03\x14\xc9\x00\x00\x10\x04\x00\x00\x00"
            b"\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x03\x8e\x00\x64\x00\x00\x0c\xfe\x0c"
            b"\xfd\x0c\xfd\x0c\xfd\x0c\xfe\x0c\xfe\x0c\xfd\x0c\xfd\x0c\xfe\x0c\xfe\x0c\xfe\x0c"
            b"\xfe\x0c\xfe\x0c\xff\x0c\xfe\x0c\xfe\x00\x1b\x00\x1b\x00\x1b\x00\x1b\x00\x22\x00"
            b"\x1d\x00\x1d\x0c\x17\x00\x12\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x31\x36\x36"
            b"\x00\x00\x31\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x32\x33\x31"
            b"\x31\x33\x30\x30\x31\x30\x32\x38\x33\x75\xb5"
        ),
        b"\xfa\xf3\x16\x75\xf8\x02\x00\x52\x92\x5f": bytearray(  # pack 2
            b"\xfa\xf3\x16\x02\xa4\x02\x40\x01\xe0\x02\x58\x01\x2c\xc8\x78\x00\x00\x00\x00\x75"
            b"\x30\x00\x0a\x00\x00\x0c\x4e\x00\x00\x00\x00\x7b\x0c\x00\x10\x0c\xff\x0c\xfc\x00"
            b"\x10\x00\x02\x00\x1b\x00\x1b\x00\x04\x00\x03\x14\xc9\x00\x00\x10\x04\x00\x00\x00"
            b"\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x03\x8e\x00\x64\x00\x00\x0c\xfe\x0c"
            b"\xfc\x0c\xfd\x0c\xfd\x0c\xfd\x0c\xfd\x0c\xfd\x0c\xfd\x0c\xfe\x0c\xfe\x0c\xfe\x0c"
            b"\xfd\x0c\xff\x0c\xff\x0c\xff\x0c\xff\x00\x1b\x00\x1b\x00\x1b\x00\x1b\x00\x23\x00"
            b"\x1d\x00\x1d\x0c\x17\x00\x12\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x31\x36\x36"
            b"\x00\x00\x31\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x32\x33\x31"
            b"\x31\x33\x30\x30\x31\x30\x34\x33\x34\xae\x94"
        ),
    }

    async def send_frag_response(
        self,
        data: Buffer,
        _response: bool | None = None,
    ) -> None:
        """Send fragmented response."""

        assert (
            self._notify_callback
        ), "write to characteristics but notification not enabled"

        resp: bytearray = self.RESP.get(bytes(data), bytearray())
        for notify_data in [
            resp[i : min(len(resp), i + BT_FRAME_SIZE)]
            for i in range(0, len(resp), BT_FRAME_SIZE)
        ]:
            self._notify_callback("MockEpoch ProBleakClient", notify_data)

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
        ) == normalize_uuid_str("ffe1")

        await self.send_frag_response(data)


async def test_update(patch_bleak_client, reconnect_fixture) -> None:
    """Test Epoch Pro BMS data update."""

    patch_bleak_client(MockEpochProBleakClient)

    bms = BMS(
        generate_ble_device("cc:cc:cc:cc:cc:cc", "MockBLEdevice", None, -73),
        reconnect_fixture,
    )

    assert await bms.async_update() == REF_VALUE

    # query again to check already connected state
    assert await bms.async_update() == REF_VALUE
    assert bms._client and bms._client.is_connected is not reconnect_fixture

    await bms.disconnect()


@pytest.fixture(
    name="wrong_response",
    params=[
        (
            bytearray(  # overall
                b"\xaa\xf3\x16\x01\x6e\x00\x00\x00\x00\x04\xb0\x00\x00\x00\x5b\x00\x64\x23\x8c\x14"
                b"\xc9\x00\x00\x01\x0e\x00\x00\x00\x00\x18\x7a\x00\x00\x00\x00\x00\x00\x00\x00\x00"
                b"\x00\x00\x00\x00\x00\x00\x00\x00\x02\x00\x00\x00\x00\x00\x00\x0c\xfd\x0c\xff\x00"
                b"\x1b\x00\x1b\x32\x30\x31\x2d\x00\x31\x00\x00\x32\x30\x31\x2d\x00\x34\x00\x00\x31"
                b"\x30\x30\x2d\x00\x31\x00\x00\x31\x30\x30\x2d\x00\x31\x00\x00\x00\x00\x00\x00\x00"
                b"\x00\x00\x00\x00\x38\xaa\xa8\x02\xaa\xaa\xa8\x00\x82\x00\x3c\x6b\x2f"
            ),
            "wrong_SOF",
        ),
        (
            bytearray(  # overall
                b"\xfa\xf3\x16\x01\x6e\x00\x00\x00\x00\x04\xb0\x00\x00\x00\x5b\x00\x64\x23\x8c\x14"
                b"\xc9\x00\x00\x01\x0e\x00\x00\x00\x00\x18\x7a\x00\x00\x00\x00\x00\x00\x00\x00\x00"
                b"\x00\x00\x00\x00\x00\x00\x00\x00\x02\x00\x00\x00\x00\x00\x00\x0c\xfd\x0c\xff\x00"
                b"\x1b\x00\x1b\x32\x30\x31\x2d\x00\x31\x00\x00\x32\x30\x31\x2d\x00\x34\x00\x00\x31"
                b"\x30\x30\x2d\x00\x31\x00\x00\x31\x30\x30\x2d\x00\x31\x00\x00\x00\x00\x00\x00\x00"
                b"\x00\x00\x00\x00\x38\xaa\xa8\x02\xaa\xaa\xa8\x00\x82\x00\x3c\x00\x00"
            ),
            "wrong_CRC",
        ),
        (bytearray(7), "critical_length"),
    ],
    ids=lambda param: param[1],
)
def fix_response(request) -> bytearray:
    """Return faulty response frame."""
    return request.param[0]


async def test_invalid_response(
    monkeypatch, patch_bleak_client, patch_bms_timeout, wrong_response: bytearray
) -> None:
    """Test data up date with BMS returning invalid data."""

    patch_bms_timeout()

    monkeypatch.setattr(
        MockEpochProBleakClient,
        "RESP",
        MockEpochProBleakClient.RESP
        | {b"\xfa\xf3\x16\x76\x54\x01\x00\x37\xc7\x24": wrong_response},
    )

    patch_bleak_client(MockEpochProBleakClient)

    bms = BMS(generate_ble_device("cc:cc:cc:cc:cc:cc", "MockBLEDevice", None, -73))

    result: BMSsample = {}
    with pytest.raises(TimeoutError):
        result = await bms.async_update()

    assert not result
    await bms.disconnect()


async def test_wrong_length(monkeypatch, patch_bleak_client, patch_bms_timeout) -> None:
    """Test data up date with BMS returning incorrect length, but valid data."""

    patch_bms_timeout()

    monkeypatch.setattr(
        MockEpochProBleakClient,
        "RESP",
        MockEpochProBleakClient.RESP
        | {
            b"\xfa\xf3\x16\x76\x54\x01\x00\x37\xc7\x24": MockEpochProBleakClient.RESP[
                b"\xfa\xf3\x16\x76\x54\x01\x00\x37\xc7\x24"
            ]
            + bytes(2)
        },
    )

    patch_bleak_client(MockEpochProBleakClient)

    bms = BMS(generate_ble_device("cc:cc:cc:cc:cc:cc", "MockBLEDevice", None, -73))

    assert await bms.async_update() == REF_VALUE
    await bms.disconnect()
