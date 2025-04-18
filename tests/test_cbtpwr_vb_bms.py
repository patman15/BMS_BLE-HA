"""Test the CBT power VB series BMS implementation."""

from collections.abc import Buffer
from typing import Final
from uuid import UUID

from bleak.backends.characteristic import BleakGATTCharacteristic
from bleak.uuids import normalize_uuid_str
import pytest

from custom_components.bms_ble.plugins.cbtpwr_vb_bms import BMS, BMSsample

from .bluetooth import generate_ble_device
from .conftest import MockBleakClient

BT_FRAME_SIZE = 32


def ref_value() -> BMSsample:
    """Return reference value for mock CBT power VB series BMS."""
    return {
        "voltage": 13.3,
        "current": 0.0,
        "battery_level": 96,
        "cycles": 0,
        "cycle_charge": 192.0,
        "cell_count": 4,
        "cell#0": 3.328,
        "cell#1": 3.326,
        "cell#2": 3.326,
        "cell#3": 3.326,
        "delta_voltage": 0.002,
        "design_capacity": 200.0,
        "temp#0": 6.2,
        "temp#1": 7.3,
        "temp_sensors": 2,
        "temperature": 6.75,
        "cycle_capacity": 2553.6,
        "power": 0.0,
        #        "runtime": 22608,
        "battery_charging": False,
        "problem": False,
        "problem_code": 0,
    }


class MockCBTpwrVBBleakClient(MockBleakClient):
    """Emulate a CBT power VB series BMS BleakClient."""

    _wr_buffer: bytearray = bytearray()  # collect individual write calls
    RESP: dict[bytes, bytearray] = {
        b"~11014642E00201FD35\r": bytearray(
            b"\x7e\x32\x32\x30\x31\x34\x36\x30\x30\x36\x30\x34\x36\x30\x34\x30\x44\x30\x30\x30"
            b"\x43\x46\x45\x30\x43\x46\x45\x30\x43\x46\x45\x30\x32\x30\x30\x33\x45\x30\x30\x34"
            b"\x39\x30\x30\x30\x30\x30\x30\x38\x35\x30\x30\x36\x30\x30\x37\x30\x30\x30\x30\x30"
            b"\x30\x38\x36\x30\x30\x30\x30\x30\x30\x30\x30\x30\x30\x30\x30\x30\x30\x30\x30\x30"
            b"\x30\x30\x30\x45\x46\x36\x30\x0d"
        ),
        b"~11014681A006010001FC71\r": bytearray(
            b"\x7e\x32\x32\x30\x31\x34\x36\x30\x30\x43\x30\x30\x34\x30\x37\x44\x30\x46\x43\x42"
            b"\x46\x0d"
        ),
    }

    def _response(
        self, char_specifier: BleakGATTCharacteristic | int | str | UUID, data: Buffer
    ) -> bytearray:
        if isinstance(char_specifier, str) and normalize_uuid_str(
            char_specifier
        ) != normalize_uuid_str("ffe9"):
            return bytearray()
        # cmd: int = int(bytes(data)[7:9], 16)

        return self.RESP.get(bytes(data), bytearray())

    async def write_gatt_char(
        self,
        char_specifier: BleakGATTCharacteristic | int | str | UUID,
        data: Buffer,
        response: bool = None,  # noqa: RUF013 # same as upstream
    ) -> None:
        """Issue write command to GATT."""
        await super().write_gatt_char(char_specifier, data, response)

        if bytes(data).startswith(b"\x7e"):
            self._wr_buffer = bytearray(data)
        else:
            # concatenate write commands (BMS only accepts 20 bytes at once)
            self._wr_buffer.extend(bytes(data))
        if not bytes(data).endswith(b"\x0d"):
            return

        assert self._notify_callback is not None

        resp: Final[bytearray] = self._response(char_specifier, self._wr_buffer)
        for notify_data in [
            resp[i : i + BT_FRAME_SIZE] for i in range(0, len(resp), BT_FRAME_SIZE)
        ]:
            self._notify_callback("MockCBTpwrVBBleakClient", notify_data)


async def test_update(patch_bleak_client, reconnect_fixture: bool) -> None:
    """Test CBT power VB series BMS data update."""

    patch_bleak_client(MockCBTpwrVBBleakClient)

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
            bytearray(
                b"\x0e\x32\x32\x30\x31\x34\x36\x30\x30\x43\x30\x30\x34\x30\x37\x44\x30\x46\x43\x42"
                b"\x46\x0d"
            ),
            "wrong_SOF",
        ),
        (
            bytearray(
                b"\x7e\x32\x32\x30\x31\x34\x36\x30\x30\x43\x30\x30\x34\x30\x37\x44\x30\x46\x43\x42"
                b"\x46\x0c"
            ),
            "wrong_EOF",
        ),
        (
            bytearray(
                b"\x7e\x29\x32\x30\x31\x34\x36\x30\x30\x43\x30\x30\x34\x30\x37\x44\x30\x46\x43\x42"
                b"\x46\x0d"
            ),
            "wrong_ENC",
        ),
        (
            bytearray(
                b"\x7e\x32\x31\x30\x31\x34\x36\x30\x30\x43\x30\x30\x34\x30\x37\x44\x30\x46\x43\x42"
                b"\x46\x0d"
            ),
            "wrong_VER",
        ),
        (
            bytearray(
                b"\x7e\x32\x32\x30\x31\x34\x36\x30\x30\x43\x30\x30\x34\x30\x37\x44\x30\x46\x43\x42"
                b"\x30\x0d"
            ),
            "wrong_CRC",
        ),
        (
            bytearray(
                b"\x7e\x32\x32\x30\x31\x34\x36\x30\x30\x30\x30\x30\x34\x30\x37\x44\x30\x46\x43\x42"
                b"\x30\x0d"
            ),
            "wrong_LRC",
        ),
        (bytearray(12), "critical_length"),
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

    patch_bms_timeout("cbtpwr_vb_bms")

    monkeypatch.setattr(
        MockCBTpwrVBBleakClient,
        "RESP",
        MockCBTpwrVBBleakClient.RESP | {b"~11014681A006010001FC71\r": wrong_response},
    )

    patch_bleak_client(MockCBTpwrVBBleakClient)

    bms = BMS(generate_ble_device("cc:cc:cc:cc:cc:cc", "MockBLEDevice", None, -73))

    result: BMSsample = {}
    with pytest.raises(TimeoutError):
        result = await bms.async_update()

    assert not result
    await bms.disconnect()


@pytest.fixture(
    name="problem_response",
    params=[
        (
            bytearray(
                b"\x7e\x32\x32\x30\x31\x34\x36\x30\x30\x36\x30\x34\x36\x30\x34\x30\x44\x30\x30\x30"
                b"\x43\x46\x45\x30\x43\x46\x45\x30\x43\x46\x45\x30\x32\x30\x30\x33\x45\x30\x30\x34"
                b"\x39\x30\x30\x30\x30\x30\x30\x38\x35\x30\x30\x36\x30\x30\x37\x30\x30\x30\x30\x30"
                b"\x30\x38\x36\x30\x30\x30\x30\x30\x30\x30\x30\x30\x30\x30\x30\x30\x30\x30\x30\x30"
                b"\x30\x30\x31\x45\x46\x35\x46\x0d"
            ),
            "first_bit",
        ),
        (
            bytearray(
                b"\x7e\x32\x32\x30\x31\x34\x36\x30\x30\x36\x30\x34\x36\x30\x34\x30\x44\x30\x30\x30"
                b"\x43\x46\x45\x30\x43\x46\x45\x30\x43\x46\x45\x30\x32\x30\x30\x33\x45\x30\x30\x34"
                b"\x39\x30\x30\x30\x30\x30\x30\x38\x35\x30\x30\x36\x30\x30\x37\x30\x30\x30\x30\x30"
                b"\x30\x38\x36\x30\x30\x30\x30\x30\x30\x30\x30\x38\x30\x30\x30\x30\x30\x30\x30\x30"
                b"\x30\x30\x30\x45\x46\x35\x38\x0d"
            ),
            "last_bit",
        ),
    ],
    ids=lambda param: param[1],
)
def prb_response(request) -> tuple[dict[int, bytearray], str]:
    """Return faulty response frame."""
    return request.param


async def test_problem_response(
    monkeypatch, patch_bleak_client, problem_response: tuple[dict[int, bytearray], str]
) -> None:
    """Test data update with BMS returning error flags."""

    monkeypatch.setattr(  # patch response dictionary to only problem reports (no other data)
        MockCBTpwrVBBleakClient,
        "RESP",
        MockCBTpwrVBBleakClient.RESP | {b"~11014642E00201FD35\r": problem_response[0]},
    )

    patch_bleak_client(MockCBTpwrVBBleakClient)

    bms = BMS(generate_ble_device("cc:cc:cc:cc:cc:cc", "MockBLEdevice", None, -73))

    result: BMSsample = await bms.async_update()
    assert result == ref_value() | {
        "problem": True,
        "problem_code": 1 << (0 if problem_response[1] == "first_bit" else 47),
    }

    await bms.disconnect()
