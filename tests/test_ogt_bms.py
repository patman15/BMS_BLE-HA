"""Test the Daly BMS implementation."""

import asyncio
from collections.abc import Buffer
from typing import Final
from uuid import UUID

from bleak.backends.characteristic import BleakGATTCharacteristic
from bleak.uuids import normalize_uuid_str
import pytest

from custom_components.bms_ble.plugins.basebms import BMSsample
from custom_components.bms_ble.plugins.ogt_bms import BMS

from .bluetooth import generate_ble_device
from .conftest import MockBleakClient, MockRespChar

base_result: BMSsample = {
    "voltage": 45.681,
    "battery_level": 14,
    "cycles": 99,
    "cycle_charge": 8.0,
    "temperature": 21.8,
    "cycle_capacity": 365.448,
    "power": 56.188,
    "problem": False,
}


class MockOGTBleakClient(MockBleakClient):
    """Emulate an OGT BMS BleakClient."""

    KEY = 0x10  # key used for decoding, constants are encrypted with this key!
    RESP_TYPE_A: dict[int, bytearray] = {
        0x02: bytearray(b" U  \x1d\x1a"),  # battery_level: 14
        0x04: bytearray(b'"  # Q\x1d\x1a'),  # cycle_charge: 8.0
        0x08: bytearray(b"'!R\"\x1d\x1a"),  # voltage: 45.681
        0x0C: bytearray(b"(% R\x1d\x1a"),  # temperature: 21.8
        0x10: bytearray(b"(%VV  \x1d\x1a"),  # current: -1.23
        0x18: bytearray(b"'(  \x1d\x1a"),  # runtime: 7200
        0x2C: bytearray(b"&#  \x1d\x1a"),  # cycles: 99
    }
    RESP_TYPE_B: dict[int, bytearray] = {
        0x08: bytearray(b"(% R\x1d\x1a"),  # temperature: 21.8
        0x09: bytearray(b"'!R\"\x1d\x1a"),  # voltage: 45.681
        0x0A: bytearray(b"'R   Q\x1d\x1a"),  # current: 1.23
        0x0D: bytearray(b" U  \x1d\x1a"),  # battery_level: 14
        0x0F: bytearray(b'"  # Q\x1d\x1a'),  # cycle_charge: 8.0
        0x12: bytearray(b"VVVV\x1d\x1a"),  # runtime: 65536 (inf)
        0x17: bytearray(b"&#  \x1d\x1a"),  # cycles: 99
        0x3F: bytearray(b"UQ S\x1d\x1a"),  # 3.306
        0x3E: bytearray(b"U) S\x1d\x1a"),  # 3.300
        0x3D: bytearray(b"U( S\x1d\x1a"),  # 3.304
        0x3C: bytearray(b"U' S\x1d\x1a"),  # 3.303
    }

    async def _response(
        self, char_specifier: BleakGATTCharacteristic | int | str | UUID, data: Buffer
    ) -> bytearray:
        if isinstance(char_specifier, str) and normalize_uuid_str(
            char_specifier
        ) == normalize_uuid_str("fff6"):
            assert self._ble_device.name is not None
            if self._ble_device.name[9] == "A":
                assert (
                    bytearray(data)[0:4] == b";BQQ"
                ), "BMS type A command header incorrect."
            else:
                assert (
                    bytearray(data)[0:4] == b";B!&"
                ), "BMS type B command header incorrect."

            reg: Final[int] = int(
                bytearray((bytearray(data)[x] ^ self.KEY) for x in range(4, 6)).decode(
                    encoding="ascii"
                ),
                16,
            )
            assert self._ble_device.name is not None

            if self._ble_device.name[9] == "A" and reg in self.RESP_TYPE_A:
                return bytearray(b";BT<") + bytearray(data)[4:6] + self.RESP_TYPE_A[reg]

            if self._ble_device.name[9] == "B" and reg in self.RESP_TYPE_B:
                return bytearray(b";BT<") + bytearray(data)[4:6] + self.RESP_TYPE_B[reg]

            return bytearray(b";BT<") + bytearray(b"Ubb\x7f\x10")  # Error

        return bytearray()

    async def write_gatt_char(
        self,
        char_specifier: BleakGATTCharacteristic | int | str | UUID,
        data: Buffer,
        response: bool | None = None,
    ) -> None:
        """Issue write command to GATT."""
        assert self._notify_callback is not None
        value: Final[bytearray] = await self._response(char_specifier, data)

        asyncio.get_running_loop().call_soon(
            self._notify_callback, MockRespChar(None, lambda: 0), value
        )


async def test_update(patch_bleak_client, ogt_bms_fixture, keep_alive_fixture) -> None:
    """Test OGT BMS data update."""

    patch_bleak_client(MockOGTBleakClient)

    bms = BMS(
        generate_ble_device("cc:cc:cc:cc:cc:cc", ogt_bms_fixture, None, -73),
        keep_alive_fixture,
    )

    result: BMSsample = await bms.async_update()

    # verify all sensors are reported
    if str(ogt_bms_fixture)[9] == "A":
        assert result == base_result | {
            "current": -1.23,
            "power": -56.188,
            "battery_charging": False,
            "runtime": 7200,
        }
    else:
        assert result == base_result | {
            "current": 1.23,
            "delta_voltage": 0.003,
            "power": 56.188,
            "battery_charging": True,
            "cell_voltages": [3.306, 3.305, 3.304, 3.303],
        }

    # query again to check already connected state
    result = await bms.async_update()
    assert bms._client.is_connected is keep_alive_fixture

    await bms.disconnect()


async def test_update_16s(monkeypatch, patch_bleak_client) -> None:
    """Test OGT BMS data update for 16 cell (max possible)."""

    monkeypatch.setattr(
        MockOGTBleakClient,
        "RESP_TYPE_B",
        MockOGTBleakClient.RESP_TYPE_B
        | {
            key: bytearray(f"U{(chr(0x27),'(',')','Q')[key % 4]} S\x1d\x1a", "ascii")
            for key in range(0x30, 0x3C)
        },
    )
    patch_bleak_client(MockOGTBleakClient)

    bms = BMS(
        generate_ble_device("cc:cc:cc:cc:cc:cc", "SmartBat-B12294", None, -73), False
    )

    # verify all sensors are reported
    assert await bms.async_update() == base_result | {
        "current": 1.23,
        "delta_voltage": 0.003,
        "power": 56.188,
        "battery_charging": True,
        "cell_voltages": [
            3.306,
            3.305,
            3.304,
            3.303,
            3.306,
            3.305,
            3.304,
            3.303,
            3.306,
            3.305,
            3.304,
            3.303,
            3.306,
            3.305,
            3.304,
            3.303,
        ],
    }


@pytest.fixture(
    name="wrong_response",
    params=[
        (bytearray(7), "critical_length"),
        (bytearray(b";AT< )'!R\"\x1d\x1a"), "wrong_SOP"),
        (bytearray(b";BT< )'!R\""), "wrong_EOP"),
        (bytearray(b";BT<#RUN S\x1d\x1a"), "invalid_character"),
        (bytearray(b";BT<Ubb\x7f\x10"), "BMS_error"),
        (bytearray(b"invalid\xf0value"), "invalid_value"),
        (bytearray(b";BT<UQ S\x1d\x1a"), "wrong_reg"),
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

    async def patch_resp(
        _self, char_specifier: BleakGATTCharacteristic | int | str | UUID, _data: Buffer
    ) -> bytearray:
        if isinstance(char_specifier, str) and normalize_uuid_str(
            char_specifier
        ) == normalize_uuid_str("fff6"):
            return wrong_response
        raise NotImplementedError("wrong GATT characteristic")

    monkeypatch.setattr(MockOGTBleakClient, "_response", patch_resp)

    patch_bleak_client(MockOGTBleakClient)

    bms = BMS(generate_ble_device("cc:cc:cc:cc:cc:cc", "SmartBat-B12294", None, -73))

    result: BMSsample = {}
    with pytest.raises(TimeoutError):
        result = await bms.async_update()

    assert not result
    await bms.disconnect()


async def test_invalid_bms_type(patch_bleak_client) -> None:
    """Test BMS with invalid type 'C'."""

    patch_bleak_client(MockOGTBleakClient)

    bms = BMS(generate_ble_device("cc:cc:cc:cc:cc:cc", "SmartBat-C12294", None, -73))

    result: BMSsample = await bms.async_update()
    assert not result
    assert bms._client.is_connected
    await bms.disconnect()
