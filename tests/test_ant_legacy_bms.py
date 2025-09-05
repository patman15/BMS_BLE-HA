"""Test the ANT implementation."""

import asyncio
from collections.abc import Buffer
from typing import Final
from uuid import UUID

from bleak.backends.characteristic import BleakGATTCharacteristic
import pytest

from custom_components.bms_ble.plugins.ant_legacy_bms import BMS
from custom_components.bms_ble.plugins.basebms import BMSsample

from .bluetooth import generate_ble_device
from .conftest import MockBleakClient

BT_ADDRESS = "aa:bb:cc:a2:34:56"
BT_FRAME_SIZE: Final[int] = 19  # ANT BMS frame size

_RESULT_DEFS: Final[BMSsample] = {
    "voltage": 54.2,
    "current": -0.0,
    "battery_level": 100,
    "cycle_charge": 140.0,
    "design_capacity": 140,
    "cycle_capacity": 140 * 54.2,
    "total_cycled_charge": 188250,  # ant_legacy_bms specific extra key
    "cycles": 1344,
    "power": -0.0,
    "battery_charging": False,
    "cell_count": 16,
    "cell_voltages": [
        3.338,
        3.339,
        3.339,
        3.339,
        3.413,
        3.391,
        3.436,
        3.4,
        3.464,
        3.446,
        3.398,
        3.506,
        3.339,
        3.339,
        3.339,
        3.339,
    ],
    "delta_voltage": 0.168,
    "cell_high_voltage": 3.506,  # ant_legacy_bms specific extra key
    "cell_low_voltage": 3.338,  # ant_legacy_bms specific extra key
    "temp_sensors": 6,
    "temp_values": [26, 29, -5, 21, 0, 0],
    "temperature": 26,
    "problem": False,
    "runtime": 169081843,
}


class MockANTLEGACYBleakClient(MockBleakClient):
    """Emulate a ANT (legacy) BMS BleakClient."""

    CMDS: Final[dict[BMS.ADR, bytearray]] = {
        BMS.ADR.STATUS: bytearray(b"\xdb\xdb\x00\x00\x00\x00"),
    }
    RESP: Final[dict[BMS.ADR, bytearray]] = {
        BMS.ADR.STATUS: bytearray(
            b"\xaaU\xaa\xff\x02\x1e\r\n\r\x0b\r\x0b\r\x0b\rU\r?\rl"
            b"\rH\r\x88\rv\rF\r\xb2\r\x0b\r\x0b\r\x0b\r\x0b\x00\x00"
            b"\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00"
            b"\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00d\x00\x00\x00\x00\x08"
            b"X\x1e\x02\x0b8yS\n\x13\xfb\xf3\x00\x1a\x00\x1d\xff\xfb\x00\x15\x00"
            b"\x00\x00\x00\x02\x01\x02\x00\x00\x00\x00\x00\x00\x00\x00\x00\x0c\r\xb2\x01\r"
            b"\n\r9\x10\xff\xef\x00\x80\x00\x00\x00\x00\x00\x00\x0bP4\t\x0f\r"
        ),
    }

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


async def test_update(patch_bms_timeout, patch_bleak_client, reconnect_fixture) -> None:
    """Test ANT BMS data update."""

    patch_bms_timeout()
    patch_bleak_client(MockANTLEGACYBleakClient)

    bms = BMS(
        generate_ble_device(BT_ADDRESS, "MockBLEdevice", None, -73),
        reconnect_fixture,
    )

    assert await bms.async_update() == _RESULT_DEFS

    # query again to check already connected state
    await bms.async_update()
    assert bms._client and bms._client.is_connected is not reconnect_fixture

    await bms.disconnect()


async def test_update_empty_battery(
    monkeypatch, patch_bms_timeout, patch_bleak_client
) -> None:
    """Test ANT BMS data update with 0% battery SOC."""

    patch_bms_timeout()

    monkeypatch.setattr(
        MockANTLEGACYBleakClient,
        "RESP",
        MockANTLEGACYBleakClient.RESP
        | {
            BMS.ADR.STATUS: bytearray(
                b"\xaaU\xaa\xff\x02\x1e\r\n\r\x0b\r\x0b\r\x0b\rU\r?\rl"
                b"\rH\r\x88\rv\rF\r\xb2\r\x0b\r\x0b\r\x0b\r\x0b\x00\x00"
                b"\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00"
                b"\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x08"
                b"X\x1e\x02\x0b8yS\n\x13\xfb\xf3\x00\x1a\x00\x1d\xff\xfb\x00\x15\x00"
                b"\x00\x00\x00\x02\x01\x02\x00\x00\x00\x00\x00\x00\x00\x00\x00\x0c\r\xb2\x01\r"
                b"\n\r9\x10\xff\xef\x00\x80\x00\x00\x00\x00\x00\x00\x0bP4\t\x0e\xa9"
            )
        },
    )

    patch_bleak_client(MockANTLEGACYBleakClient)

    bms = BMS(generate_ble_device(BT_ADDRESS, "MockBLEdevice", None, -73))

    assert await bms.async_update() == {
        "voltage": 54.2,
        "current": -0.0,
        "battery_level": 0,
        "cycle_charge": 140.0,
        "cycle_capacity": 140 * 54.2,
        "total_cycled_charge": 188250,  # ant_legacy_bms specific extra key
        "power": -0.0,
        "battery_charging": False,
        "cell_count": 16,
        "cell_voltages": [
            3.338,
            3.339,
            3.339,
            3.339,
            3.413,
            3.391,
            3.436,
            3.4,
            3.464,
            3.446,
            3.398,
            3.506,
            3.339,
            3.339,
            3.339,
            3.339,
        ],
        "delta_voltage": 0.168,
        "cell_high_voltage": 3.506,  # ant_legacy_bms specific extra key
        "cell_low_voltage": 3.338,  # ant_legacy_bms specific extra key
        "temp_sensors": 6,
        "temp_values": [26, 29, -5, 21, 0, 0],
        "temperature": 26,
        "problem": False,
        "runtime": 169081843,
    }

    await bms.disconnect()


@pytest.fixture(
    name="wrong_response",
    params=[
        (b"\x6e" + MockANTLEGACYBleakClient.RESP[BMS.ADR.STATUS][1:], "wrong_SOF"),
        (
            b"\xaa\x55\xaa\xfe" + MockANTLEGACYBleakClient.RESP[BMS.ADR.STATUS][4:],
            "unknown_type",
        ),
        (b"\xaa\x55\xaa", "too_short"),
        (
            MockANTLEGACYBleakClient.RESP[BMS.ADR.STATUS] + b"\xff",
            "too_long",
        ),
        (
            MockANTLEGACYBleakClient.RESP[BMS.ADR.STATUS][:-2] + b"\xff\xff",
            "wrong_CRC",
        ),
        (bytearray(1), "empty_response"),
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

    patch_bms_timeout()

    monkeypatch.setattr(
        MockANTLEGACYBleakClient,
        "RESP",
        MockANTLEGACYBleakClient.RESP | {BMS.ADR.STATUS: wrong_response},
    )

    patch_bleak_client(MockANTLEGACYBleakClient)

    bms = BMS(generate_ble_device(BT_ADDRESS, "MockBLEdevice", None, -73))

    result: BMSsample = {}
    with pytest.raises(TimeoutError):
        result = await bms.async_update()

    assert not result
    await bms.disconnect()
