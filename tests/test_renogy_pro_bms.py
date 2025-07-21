"""Test the Renogy Pro BMS implementation."""

from collections.abc import Buffer
from typing import Final
from uuid import UUID

from bleak.backends.characteristic import BleakGATTCharacteristic
from bleak.backends.descriptor import BleakGATTDescriptor
from bleak.backends.service import BleakGATTService, BleakGATTServiceCollection
from bleak.uuids import normalize_uuid_str, uuidstr_to_str

from custom_components.bms_ble.plugins.basebms import BMSsample
from custom_components.bms_ble.plugins.renogy_pro_bms import BMS

from .bluetooth import generate_ble_device
from .conftest import MockBleakClient

BT_FRAME_SIZE = 512  # ATT max is 512 bytes


def ref_value() -> BMSsample:
    """Return reference value for mock Seplos BMS."""
    return {
        "battery_charging": False,
        "battery_level": 97.2,
        "cell_voltages": [3.5, 3.3, 3.3, 3.3],
        "cell_count": 4,
        "current": -0.86,
        "cycle_capacity": 1321.92,
        "cycle_charge": 97.2,
        "cycles": 15,
        "delta_voltage": 0.2,
        "design_capacity": 100,
        "power": -11.696,
        "problem": False,
        "problem_code": 0,
        "runtime": 406883,
        "temp_values": [17.0, 17.0],
        "temp_sensors": 2,
        "temperature": 17.0,
        "voltage": 13.6,
    }


BASE_VALUE_CMD: Final[bytes] = b"\x30\x03\x13\xb2\x00\x07\xa4\x8a"


class MockRenogyProBleakClient(MockBleakClient):
    """Emulate a Renogy Pro BMS BleakClient."""

    RESP: dict[bytes, bytearray] = {
        b"\x30\x03\x13\x88\x00\x22\x45\x5c": bytearray(
            b"0\x03D\x00\x04\x00!\x00!\x00!\x00!\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x03\x01\x11\x01\x0c\x01\x13\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00eJ"
        ),
        BASE_VALUE_CMD: bytearray(
            b"\x30\x03\x0e\xff\xf4\x00\x85\x00\x03\x30\x42\x00\x03\x3b\xda\x00\x06\x3e\x33"
        ), # -1.2A, 13.3V, #### 97.2% (4B), 100Ah [mAh], (15 cycles (generated))
        b"\x30\x03\x13\xec\x00\x07\xc5\x58": bytearray(
            b"0\x03\x0e\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x0e+N"
        ),
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
        response: bool | None = None,
    ) -> None:
        """Issue write command to GATT."""
        await super().write_gatt_char(char_specifier, data, response)

        assert self._notify_callback is not None

        resp: bytearray = self._response(char_specifier, bytes(data))
        for notify_data in [
            resp[i : i + BT_FRAME_SIZE] for i in range(0, len(resp), BT_FRAME_SIZE)
        ]:
            self._notify_callback("MockRenogyProBleakClient", notify_data)

    class RenogyProService(BleakGATTService):
        """Mock the main battery info service from JiKong BMS."""

        def __init__(self, uuid: str) -> None:
            """Initialize the service."""
            super().__init__({"uuid": uuid})

        class CharBase(BleakGATTCharacteristic):
            """Basic characteristic for common properties.

            Note that Jikong BMS has two characteristics with same UUID!
            """

            @property
            def service_handle(self) -> int:
                """The integer handle of the Service containing this characteristic."""
                return 0

            @property
            def handle(self) -> int:
                """The handle for this characteristic."""
                return 3

            @property
            def service_uuid(self) -> str:
                """The UUID of the Service containing this characteristic."""
                return normalize_uuid_str("ffe0")

            @property
            def uuid(self) -> str:
                """The UUID for this characteristic."""
                return normalize_uuid_str("ffe1")

            @property
            def descriptors(self) -> list[BleakGATTDescriptor]:
                """List of descriptors for this service."""
                return []

            def get_descriptor(
                self, specifier: int | str | UUID
            ) -> BleakGATTDescriptor | None:
                """Get a descriptor by handle (int) or UUID (str or uuid.UUID)."""
                raise NotImplementedError

            def add_descriptor(self, descriptor: BleakGATTDescriptor) -> None:
                """Add a :py:class:`~BleakGATTDescriptor` to the characteristic.

                Should not be used by end user, but rather by `bleak` itself.
                """
                raise NotImplementedError

        class CharNotify(CharBase):
            """Characteristic for notifications."""

            @property
            def properties(self) -> list[str]:
                """Properties of this characteristic."""
                return ["notify"]

        class CharWrite(CharBase):
            """Characteristic for writing."""

            @property
            def properties(self) -> list[str]:
                """Properties of this characteristic."""
                return ["write", "write-without-response"]

        class CharFaulty(CharBase):
            """Characteristic for writing."""

            @property
            def uuid(self) -> str:
                """The UUID for this characteristic."""
                return normalize_uuid_str("0000")

            @property
            def properties(self) -> list[str]:
                """Properties of this characteristic."""
                return ["write", "write-without-response"]

        @property
        def handle(self) -> int:
            """The handle of this service."""

            return 2

        @property
        def uuid(self) -> str:
            """The UUID to this service."""

            return normalize_uuid_str(self.obj.get("uuid", ""))

        @property
        def description(self) -> str:
            """String description for this service."""

            return uuidstr_to_str(self.uuid)

        @property
        def characteristics(self) -> list[BleakGATTCharacteristic]:
            """List of characteristics for this service."""

            return [
                self.CharNotify(None, lambda: 350),
                self.CharWrite(None, lambda: 350),
                self.CharFaulty(None, lambda: 350),  # leave last!
            ]

        def add_characteristic(self, characteristic: BleakGATTCharacteristic) -> None:
            """Add a :py:class:`~BleakGATTCharacteristic` to the service.

            Should not be used by end user, but rather by `bleak` itself.
            """
            raise NotImplementedError

    @property
    def services(self) -> BleakGATTServiceCollection:
        """Emulate JiKong BT service setup."""

        serv_col = BleakGATTServiceCollection()
        serv_col.add_service(self.RenogyProService(uuid="ffd0"))
        serv_col.add_service(self.RenogyProService(uuid="fff0"))

        return serv_col


async def test_update(patch_bleak_client, reconnect_fixture: bool) -> None:
    """Test Renogy Pro BMS data update."""

    patch_bleak_client(MockRenogyProBleakClient)

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
