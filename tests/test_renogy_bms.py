"""Test the Renogy BMS implementation."""

# import asyncio
from collections.abc import Buffer
from uuid import UUID

from bleak.backends.characteristic import BleakGATTCharacteristic
from bleak.uuids import normalize_uuid_str
import pytest

from custom_components.bms_ble.plugins.renogy_bms import BMS, BMSsample

from .bluetooth import generate_ble_device
from .conftest import MockBleakClient

BT_FRAME_SIZE = 512  # ATT max is 512 bytes


def ref_value() -> BMSsample:
    """Return reference value for mock Seplos BMS."""
    return {
        "battery_charging": False,
        "battery_level": 97.2,
        "cell#0": 3.5,
        "cell#1": 3.3,
        "cell#2": 3.3,
        "cell#3": 3.3,
        "cell_count": 4,
        "current": 0.0,
        "cycle_capacity": 1321.92,
        "cycle_charge": 97.2,
        "delta_voltage": 0.2,
        "design_capacity": 100.0,
        "power": 0.0,
        "problem": False,
        "temp#0": 17.0,
        "temp#1": 17.0,
        "temp_sensors": 2,
        "temperature": 17.0,
        "voltage": 13.6,
    }


class MockRenogyBleakClient(MockBleakClient):
    """Emulate a Renogy BMS BleakClient."""

    RESP: dict[bytes, bytearray] = {
        b"\x30\x03\x13\x88\x00\x22\x45\x5c": bytearray(
            b"\x30\x03\x44\x00\x04\x00\x23\x00\x21\x00\x21\x00\x21\x00\x00\x00\x00\x00\x00\x00\x00"
            b"\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x02\x00\xaa\x00"
            b"\xaa\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00"
            b"\x00\x00\x00\x00\x00\x00\x00\x00\x25\x74"
        ),  # cell count (4/16), cell [0.1 V] (3.5, 3.3, 3.3, 3.3), temp count (2/16), temp [0.1°C] (17,17)
        b"\x30\x03\x13\xf0\x00\x1c\x44\x95": bytearray(  # system ID, name, firmware
            b"\x30\x03\x38\x00\x00\x00\x00\x00\x06\x00\x00\x00\x00\x00\xc8\x32\x30\x32\x31\x30\x35"
            b"\x32\x36\x00\x00\x00\x00\x00\x00\x00\x00\x20\x20\x20\x20\x20\x20\x20\x20\x52\x42\x54"
            b"\x31\x30\x30\x4c\x46\x50\x31\x32\x2d\x42\x54\x20\x20\x30\x31\x30\x30\x55\x2f"
        ),  # 08È20210526        RBT100LFP12-BT  0100
        b"\x30\x03\x13\xb2\x00\x06\x65\x4a": bytearray(
            b"\x30\x03\x0c\x00\x00\x00\x88\x00\x01\x7b\xb0\x00\x01\x86\xa0\x0c\xeb"
        ),  # 13.6V, 97.2% (4B), 100Ah [mAh]
        b"\x30\x03\x14\x02\x00\x08\xe4\x1d": bytearray(
            b"\x30\x03\x10\x52\x42\x54\x31\x30\x30\x4c\x46\x50\x31\x32\x2d\x42\x54\x20\x20\x58\xbb"
        ),  # 0RBT100LFP12-BT
    }

    def _response(
        self, char_specifier: BleakGATTCharacteristic | int | str | UUID, cmd: bytes
    ) -> bytearray:
        if isinstance(char_specifier, str) and normalize_uuid_str(
            char_specifier
        ) != normalize_uuid_str("ffd1"):
            return bytearray()

        return self.RESP.get(cmd, bytearray())

    async def write_gatt_char(
        self,
        char_specifier: BleakGATTCharacteristic | int | str | UUID,
        data: Buffer,
        response: bool = None,  # noqa: RUF013 # same as upstream
    ) -> None:
        """Issue write command to GATT."""
        await super().write_gatt_char(char_specifier, data, response)

        assert self._notify_callback is not None

        resp: bytearray = self._response(char_specifier, bytes(data))
        for notify_data in [
            resp[i : i + BT_FRAME_SIZE] for i in range(0, len(resp), BT_FRAME_SIZE)
        ]:
            self._notify_callback("MockRenogyBleakClient", notify_data)


async def test_update(patch_bleak_client, reconnect_fixture: bool) -> None:
    """Test Renogy BMS data update."""

    patch_bleak_client(MockRenogyBleakClient)

    bms = BMS(
        generate_ble_device("cc:cc:cc:cc:cc:cc", "MockBLEDevice", None, -73),
        reconnect_fixture,
    )

    result = await bms.async_update()

    assert result == ref_value()

    # query again to check already connected state
    result = await bms.async_update()
    assert bms._client.is_connected is not reconnect_fixture

    await bms.disconnect()


@pytest.fixture(
    name="wrong_response",
    params=[
        (
            b"\x30\x03\x0c\x00\x00\x00\x88\x00\x01\x7b\xb0\x00\x01\x86\xa0\x0d\xeb",
            "wrong_CRC",
        ),
        (
            b"\x31\x03\x0c\x00\x00\x00\x88\x00\x01\x7b\xb0\x00\x01\x86\xa0\x0c\xeb",
            "wrong_SOF",
        ),
        (
            b"\x30\x03\x0d\x00\x00\x00\x88\x00\x01\x7b\xb0\x00\x01\x86\xa0\x0c\xeb",
            "wrong_length",
        ),
        (bytes(2), "critical_length"),
    ],
    ids=lambda param: param[1],
)
def response(request) -> bytearray:
    """Return faulty response frame."""
    return bytearray(request.param[0])


async def test_invalid_response(
    monkeypatch, patch_bleak_client, patch_bms_timeout, wrong_response: bytearray
) -> None:
    """Test data up date with BMS returning invalid data."""

    patch_bms_timeout("renogy_bms")

    monkeypatch.setattr(
        MockRenogyBleakClient,
        "RESP",
        MockRenogyBleakClient.RESP
        | {b"\x30\x03\x13\xb2\x00\x06\x65\x4a": wrong_response},
    )

    patch_bleak_client(MockRenogyBleakClient)

    bms = BMS(generate_ble_device("cc:cc:cc:cc:cc:cc", "MockBLEDevice", None, -73))

    result: BMSsample = {}
    with pytest.raises(TimeoutError):
        result = await bms.async_update()

    assert not result
    await bms.disconnect()
