"""Test the E&J technology BMS implementation."""

from collections.abc import Buffer
from uuid import UUID

from bleak.backends.characteristic import BleakGATTCharacteristic
from bleak.uuids import normalize_uuid_str
import pytest

from custom_components.bms_ble.plugins.basebms import BMSsample
from custom_components.bms_ble.plugins.ej_bms import BMS

from .bluetooth import generate_ble_device
from .conftest import MockBleakClient

BT_FRAME_SIZE = 20


class MockEJBleakClient(MockBleakClient):
    """Emulate a E&J technology BMS BleakClient."""

    def _response(
        self, char_specifier: BleakGATTCharacteristic | int | str | UUID, data: Buffer
    ) -> bytearray:
        if isinstance(char_specifier, str) and normalize_uuid_str(
            char_specifier
        ) != normalize_uuid_str("6e400002-b5a3-f393-e0a9-e50e24dcca9e"):
            return bytearray()
        cmd: int = int(bytearray(data)[3:5], 16)
        if cmd == 0x02:
            return bytearray(
                b":0082310080000101C00000880F540F3C0F510FD70F310F2C0F340F3A0FED0FED0000000000000000"
                b"000000000000000248424242F0000000000000000001AB~"
            )  # TODO: put numbers
        if cmd == 0x10:
            return bytearray(b":009031001E00000002000A000AD8~")  # TODO: put numbers
        return bytearray()

    async def write_gatt_char(
        self,
        char_specifier: BleakGATTCharacteristic | int | str | UUID,
        data: Buffer,
        response: bool | None = None,
    ) -> None:
        """Issue write command to GATT."""
        await super().write_gatt_char(char_specifier, data, response)
        assert self._notify_callback is not None
        self._notify_callback("MockEctiveBleakClient", bytearray(b"AT\r\n"))
        self._notify_callback("MockEctiveBleakClient", bytearray(b"AT\r\nillegal"))
        for notify_data in [
            self._response(char_specifier, data)[i : i + BT_FRAME_SIZE]
            for i in range(0, len(self._response(char_specifier, data)), BT_FRAME_SIZE)
        ]:
            self._notify_callback("MockEctiveBleakClient", notify_data)


class MockEJsfBleakClient(MockEJBleakClient):
    """Emulate a E&J technology BMS BleakClient with single frame protocol."""

    def _response(
        self, char_specifier: BleakGATTCharacteristic | int | str | UUID, data: Buffer
    ) -> bytearray:
        if isinstance(char_specifier, str) and normalize_uuid_str(
            char_specifier
        ) != normalize_uuid_str("6e400002-b5a3-f393-e0a9-e50e24dcca9e"):
            return bytearray()

        if int(bytearray(data)[3:5], 16) == 0x02:
            return bytearray(
                b":008231008C000000000000000CBF0CC00CEA0CD50000000000000000000000000000000000000000"
                b"00000000008C000041282828F000000000000100004B044C05DC05DCB2~"
            )
        return bytearray()

    @staticmethod
    def values() -> BMSsample:
        """Return correct data sample values for single frame protocol sample."""
        return {
            "voltage": 13.118,
            "current": 1.4,
            "battery_level": 75,
            "cycles": 1,
            "cycle_charge": 110.0,
            "cell_voltages": [3.263, 3.264, 3.306, 3.285],
            "delta_voltage": 0.043,
            "temperature": 25,
            "cycle_capacity": 1442.98,
            "power": 18.365,
            "battery_charging": True,
            "problem": False,
            "problem_code": 0,
        }


class MockEJsfnoCRCBleakClient(MockEJsfBleakClient):
    """Emulate a E&J technology BMS BleakClient with single frame protocol."""

    def _response(
        self, char_specifier: BleakGATTCharacteristic | int | str | UUID, data: Buffer
    ) -> bytearray:
        ret: bytearray = MockEJsfBleakClient._response(self, char_specifier, data)
        ret[-3:-1] = b"FB"  # patch to static CRC
        return ret


class MockEJinvalidBleakClient(MockEJBleakClient):
    """Emulate a E&J technology BMS BleakClient without sending second frame."""

    def _response(
        self, char_specifier: BleakGATTCharacteristic | int | str | UUID, data: Buffer
    ) -> bytearray:
        if isinstance(char_specifier, str) and normalize_uuid_str(
            char_specifier
        ) != normalize_uuid_str("6e400002-b5a3-f393-e0a9-e50e24dcca9e"):
            return bytearray()

        return bytearray(
            b":0082310080000101C00000880F540F3C0F510FD70F310F2C0F340F3A0FED0FED0000000000000000"
            b"000000000000000248424242F0000000000000000001AB~"
        )  # TODO: put numbers


async def test_update(patch_bleak_client, reconnect_fixture) -> None:
    """Test E&J technology BMS data update."""

    patch_bleak_client(MockEJBleakClient)

    bms = BMS(
        generate_ble_device("cc:cc:cc:cc:cc:cc", "MockBLEDevice", None, -73),
        reconnect_fixture,
    )

    assert await bms.async_update() == {
        "voltage": 39.517,
        "current": -0.02,
        "battery_level": 1,
        "cycles": 0,
        "cycle_charge": 0.2,
        "cell_voltages": [
            3.924,
            3.900,
            3.921,
            4.055,
            3.889,
            3.884,
            3.892,
            3.898,
            4.077,
            4.077,
        ],
        "delta_voltage": 0.193,
        "temperature": 32,
        "cycle_capacity": 7.903,
        "power": -0.79,
        "runtime": 36000,
        "battery_charging": False,
        "problem": False,
        "problem_code": 0,
    }

    # query again to check already connected state
    await bms.async_update()
    assert bms._client.is_connected is not reconnect_fixture

    await bms.disconnect()


async def test_update_single_frame(patch_bleak_client, reconnect_fixture) -> None:
    """Test E&J technology BMS data update."""

    patch_bleak_client(MockEJsfBleakClient)

    bms = BMS(
        generate_ble_device("cc:cc:cc:cc:cc:cc", "MockBLEDevice", None, -73),
        reconnect_fixture,
    )

    assert await bms.async_update() == MockEJsfBleakClient.values()

    # query again to check already connected state
    await bms.async_update()
    assert bms._client.is_connected is not reconnect_fixture

    await bms.disconnect()


async def test_update_sf_no_crc(patch_bleak_client) -> None:
    """Test E&J technology BMS data update."""

    patch_bleak_client(MockEJsfnoCRCBleakClient)

    bms = BMS(
        generate_ble_device("cc:cc:cc:cc:cc:cc", "libattU_MockBLEDevice", None, -73),
        True,
    )

    assert await bms.async_update() == MockEJsfnoCRCBleakClient.values()

    await bms.disconnect()


async def test_invalid(patch_bleak_client) -> None:
    """Test E&J technology BMS data update."""

    patch_bleak_client(MockEJinvalidBleakClient)

    bms = BMS(generate_ble_device("cc:cc:cc:cc:cc:cc", "MockBLEDevice", None, -73))

    assert await bms.async_update() == {}
    await bms.disconnect()


@pytest.fixture(
    name="wrong_response",
    params=[
        (b"x009031001E0000001400080016F4~", "wrong SOI"),
        (b":009031001E0000001400080016F4x", "wrong EOI"),
        (b":009031001D0000001400080016F4~", "wrong length"),
        (b":009031001E00000002000A000AD9~", "wrong CRC"),
        (b":009031001E000X001400080016F4~", "wrong encoding"),
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
        MockEJBleakClient, "_response", lambda _s, _c, _d: wrong_response
    )

    patch_bleak_client(MockEJBleakClient)

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
                b":008231008C000000000000000CBF0CC00CEA0CD50000000000000000000000000000000000000000"
                b"00000000008C000041282828F004000000000100004B044C05DC05DCAE~"
            ),
            "first_bit",
        ),
        (
            bytearray(
                b":008231008C000000000000000CBF0CC00CEA0CD50000000000000000000000000000000000000000"
                b"00000000008C000041282828F800000000000100004B044C05DC05DCAA~"
            ),
            "last_bit",
        ),
    ],
    ids=lambda param: param[1],
)
def prb_response(request):
    """Return faulty response frame."""
    return request.param


async def test_problem_response(
    monkeypatch, patch_bleak_client, problem_response
) -> None:
    """Test data update with BMS returning error flags."""

    monkeypatch.setattr(
        MockEJBleakClient, "_response", lambda _s, _c, _d: problem_response[0]
    )

    patch_bleak_client(MockEJBleakClient)

    bms = BMS(generate_ble_device("cc:cc:cc:cc:cc:cc", "MockBLEdevice", None, -73))

    result: BMSsample = await bms.async_update()
    assert result.get("problem", False)  # we expect a problem
    assert result.get("problem_code", 0) == (
        0x4 if problem_response[1] == "first_bit" else 0x800
    )

    await bms.disconnect()
