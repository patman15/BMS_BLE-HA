"""Common fixtures for the BLE Battery Management System integration tests."""

from collections.abc import Awaitable, Buffer, Callable, Iterable
import importlib
import logging
from typing import Any
from uuid import UUID
from homeassistant.config_entries import SOURCE_BLUETOOTH
from bleak import BleakClient
from bleak.backends.characteristic import BleakGATTCharacteristic
from bleak.backends.descriptor import BleakGATTDescriptor
from bleak.backends.device import BLEDevice
from bleak.exc import BleakError
from bleak.uuids import normalize_uuid_str, uuidstr_to_str
from home_assistant_bluetooth import BluetoothServiceInfoBleak

import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry
from custom_components.bms_ble.const import (
    ATTR_CURRENT,
    ATTR_CYCLE_CHRG,
    ATTR_CYCLES,
    ATTR_VOLTAGE,
    BMS_TYPES,
    DOMAIN,
    KEY_CELL_VOLTAGE,
    KEY_TEMP_VALUE,
)
from custom_components.bms_ble.plugins.basebms import BaseBMS, BMSsample


from .bluetooth import generate_advertisement_data, generate_ble_device

LOGGER = logging.getLogger(__name__)


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations: Any):
    """Auto add enable_custom_integrations."""
    return


@pytest.fixture(autouse=True)
def mock_bluetooth(enable_bluetooth):
    """Auto mock bluetooth."""


@pytest.fixture(params=[False, True])
def bool_fixture(request):
    """Return False, True for tests."""
    return request.param


@pytest.fixture(params=[*BMS_TYPES, "dummy_bms"])
def bms_fixture(request):
    """Return all possible BMS variants."""
    return request.param


@pytest.fixture(params=[-13, 0, 21])
def bms_data_fixture(request) -> BMSsample:
    """Return a fake BMS data dictionary."""

    return {
        ATTR_VOLTAGE: 7.0,
        ATTR_CURRENT: request.param,
        ATTR_CYCLE_CHRG: 34,
        f"{KEY_CELL_VOLTAGE}0": 3.456,
        f"{KEY_CELL_VOLTAGE}1": 3.567,
        f"{KEY_TEMP_VALUE}0": -273.15,
        f"{KEY_TEMP_VALUE}1": 0.01,
        f"{KEY_TEMP_VALUE}2": 35.555,
        f"{KEY_TEMP_VALUE}3": 100.0,
    }


@pytest.fixture
def BTdiscovery() -> BluetoothServiceInfoBleak:
    """Return a valid Bluetooth object for testing."""
    return BluetoothServiceInfoBleak(
        name="SmartBat-B12345",
        address="cc:cc:cc:cc:cc:cc",
        device=generate_ble_device(
            address="cc:cc:cc:cc:cc:cc",
            name="SmartBat-B12345",
        ),
        rssi=-61,
        service_uuids=["0000fff0-0000-1000-8000-00805f9b34fb"],
        manufacturer_data={},
        service_data={},
        advertisement=generate_advertisement_data(
            local_name="SmartBat-B12345",
            service_uuids=["0000fff0-0000-1000-8000-00805f9b34fb"],
        ),
        source=SOURCE_BLUETOOTH,
        connectable=True,
        time=0,
        tx_power=-76,
    )


# use inject_bluetooth_service_info
@pytest.fixture
def BTdiscovery_notsupported():
    """Return a Bluetooth object that describes a not supported device."""
    return BluetoothServiceInfoBleak(
        name="random",  # not supported name
        address="cc:cc:cc:cc:cc:cc",
        device=generate_ble_device(
            address="cc:cc:cc:cc:cc:cc",
            name="random",
        ),
        rssi=-61,
        service_uuids=[
            "b42e1c08-ade7-11e4-89d3-123b93f75cba",
        ],
        manufacturer_data={},
        service_data={},
        advertisement=generate_advertisement_data(local_name="random"),
        source="local",
        connectable=True,
        time=0,
        tx_power=-76,
    )


def mock_config(bms: str, unique_id: str | None = "cc:cc:cc:cc:cc:cc"):
    """Return a Mock of the HA entity config."""
    return MockConfigEntry(
        domain=DOMAIN,
        version=1,
        minor_version=0,
        unique_id=unique_id,
        data={"type": f"custom_components.bms_ble.plugins.{bms}"},
        title=bms,
    )


@pytest.fixture(params=["OGTBms", "DalyBms"])
def mock_config_v0_1(request, unique_id="cc:cc:cc:cc:cc:cc"):
    """Return a Mock of the HA entity config."""
    return MockConfigEntry(
        domain=DOMAIN,
        version=0,
        minor_version=1,
        unique_id=unique_id,
        data={"type": request.param},
        title="ogt_bms_v0_1",
    )


@pytest.fixture(params=[TimeoutError, BleakError, EOFError])
def mock_coordinator_exception(request):
    """Return possible exceptions for mock BMS update function."""
    return request.param


@pytest.fixture(params=[*BMS_TYPES, "dummy_bms"])
def plugin_fixture(request) -> BaseBMS:
    """Return instance of a BMS."""
    return importlib.import_module(
        f"custom_components.bms_ble.plugins.{request.param}",
        package=__name__[: __name__.rfind(".")],
    ).BMS


@pytest.fixture(params=[False, True])
def reconnect_fixture(request) -> bool:
    """Return False, True for reconnect test."""
    return request.param


# all names result in same encryption key for easier testing
@pytest.fixture(params=["SmartBat-A12345", "SmartBat-B12294"])
def ogt_bms_fixture(request) -> str:
    """Return OGT SmartBMS names."""
    return request.param


class Mock_BMS(BaseBMS):
    """Mock Battery Management System."""

    def __init__(
        self, exc: Exception | None = None, ret_value: BMSsample | None = None
    ) -> None:  # , ble_device, reconnect: bool = False
        """Initialize BMS."""
        LOGGER.debug("%s init(), Test except: %s", self.device_id(), str(exc))
        self._exception = exc
        self._ret_value: BMSsample = (
            ret_value
            if ret_value is not None
            else {
                ATTR_VOLTAGE: 13,
                ATTR_CURRENT: 1.7,
                ATTR_CYCLE_CHRG: 19,
                ATTR_CYCLES: 23,
            }
        )  # set fixed values for dummy battery

    @staticmethod
    def matcher_dict_list() -> list[dict[str, Any]]:
        """Provide BluetoothMatcher definition."""
        return [{"local_name": "mock", "connectable": True}]

    @staticmethod
    def device_info() -> dict[str, str]:
        """Return device information for the battery management system."""
        return {"manufacturer": "Mock Manufacturer", "model": "mock model"}

    async def disconnect(self) -> None:
        """Disconnect connection to BMS if active."""

    async def async_update(self) -> BMSsample:
        """Update battery status information."""
        if self._exception:
            raise self._exception

        return self._ret_value


class MockBleakClient(BleakClient):
    """Mock bleak client."""

    def __init__(
        self,
        address_or_ble_device: BLEDevice,
        disconnected_callback: Callable[[BleakClient], None] | None,
        services: Iterable[str] | None = None,
    ) -> None:
        """Mock init."""
        LOGGER.debug("Mock init")
        super().__init__(
            address_or_ble_device.address
        )  # call with address to avoid backend resolving
        self._connected: bool = False
        self._notify_callback: Callable | None = None
        self._disconnect_callback: Callable[[BleakClient], None] | None = (
            disconnected_callback
        )
        self._ble_device = address_or_ble_device

    @property
    def address(self) -> str:
        """Return device address."""
        return self._ble_device.address

    @property
    def is_connected(self) -> bool:
        """Mock connected."""
        return self._connected

    async def connect(self, *_args, **_kwargs):
        """Mock connect."""
        assert not self._connected, "connect called, but client already connected."
        self._connected = True
        return True

    async def start_notify(
        self,
        char_specifier: BleakGATTCharacteristic | int | str | UUID,
        callback: Callable[
            [BleakGATTCharacteristic, bytearray], None | Awaitable[None]
        ],
        **kwargs,
    ) -> None:
        """Mock start_notify."""
        LOGGER.debug("MockBleakClient start_notify for %s", char_specifier)
        assert self._connected, "start_notify called, but client not connected."
        self._notify_callback = callback

    async def write_gatt_char(
        self,
        char_specifier: BleakGATTCharacteristic | int | str | UUID,
        data: Buffer,
        response: bool = None,  # type: ignore[implicit-optional] # noqa: RUF013 # same as upstream
    ) -> None:
        """Mock write GATT characteristics."""
        LOGGER.debug(
            "MockBleakClient write_gatt_char for %s, data: %s", char_specifier, data
        )
        assert self._connected, "write_gatt_char called, but client not connected."

    async def disconnect(self) -> bool:
        """Mock disconnect."""
        assert self._connected, "Disconnect called, but client not connected."

        self._connected = False
        if self._disconnect_callback is not None:
            self._disconnect_callback(self)

        return True


class MockRespChar(BleakGATTCharacteristic):
    """Mock response characteristic."""

    @property
    def service_uuid(self) -> str:
        """The UUID of the Service containing this characteristic."""
        raise NotImplementedError

    @property
    def service_handle(self) -> int:
        """The integer handle of the Service containing this characteristic."""
        raise NotImplementedError

    @property
    def handle(self) -> int:
        """The handle for this characteristic."""
        raise NotImplementedError

    @property
    def uuid(self) -> str:
        """The UUID for this characteristic."""
        return normalize_uuid_str("fff4")

    @property
    def description(self) -> str:
        """Description for this characteristic."""
        return uuidstr_to_str(self.uuid)

    @property
    def properties(self) -> list[str]:
        """Properties of this characteristic."""
        raise NotImplementedError

    @property
    def descriptors(self) -> list[BleakGATTDescriptor]:
        """List of descriptors for this service."""
        raise NotImplementedError

    def get_descriptor(self, specifier: int | str | UUID) -> BleakGATTDescriptor | None:
        """Get a descriptor by handle (int) or UUID (str or uuid.UUID)."""
        raise NotImplementedError

    def add_descriptor(self, descriptor: BleakGATTDescriptor):
        """Add a :py:class:`~BleakGATTDescriptor` to the characteristic.

        Should not be used by end user, but rather by `bleak` itself.
        """
        raise NotImplementedError


async def mock_update_min(_self) -> BMSsample:
    """Minimal version of a BMS update to mock initial coordinator update easily."""
    return {ATTR_VOLTAGE: 12.3}
