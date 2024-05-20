"""Common fixtures for the BLE Battery Management System integration tests."""

from collections.abc import Callable, Iterable
import importlib
import logging
from typing import Any, Union
from uuid import UUID

from bleak import (
    BleakClient,
    BleakError,
    BleakGATTCharacteristic,
    BLEDevice,
    normalize_uuid_str,
)

from homeassistant.core import HomeAssistant
from bleak.backends.descriptor import BleakGATTDescriptor
from bleak.backends.scanner import AdvertisementData, BLEDevice
from bleak.uuids import uuidstr_to_str
import pytest
from typing_extensions import Buffer

from homeassistant.components.bluetooth import BluetoothServiceInfoBleak, SOURCE_LOCAL, async_get_advertisement_callback


from pytest_homeassistant_custom_component.common import MockConfigEntry
# from pytest_homeassistant_custom_component.components.bluetooth import generate_advertisement_data, generate_ble_device

ADVERTISEMENT_DATA_DEFAULTS = {
    "local_name": "",
    "manufacturer_data": {},
    "service_data": {},
    "service_uuids": [],
    "rssi": -127,
    "platform_data": ((),),
    "tx_power": -127,
}

BLE_DEVICE_DEFAULTS = {
    "name": None,
    "rssi": -127,
    "details": None,
}

def generate_advertisement_data(**kwargs: Any) -> AdvertisementData:
    """Generate advertisement data with defaults."""
    new = kwargs.copy()
    for key, value in ADVERTISEMENT_DATA_DEFAULTS.items():
        new.setdefault(key, value)
    return AdvertisementData(**new)


def generate_ble_device(
    address: str | None = None,
    name: str | None = None,
    details: Any | None = None,
    rssi: int | None = None,
    **kwargs: Any,
) -> BLEDevice:
    """Generate a BLEDevice with defaults."""
    new = kwargs.copy()
    if address is not None:
        new["address"] = address
    if name is not None:
        new["name"] = name
    if details is not None:
        new["details"] = details
    if rssi is not None:
        new["rssi"] = rssi
    for key, value in BLE_DEVICE_DEFAULTS.items():
        new.setdefault(key, value)
    return BLEDevice(**new)

def inject_advertisement_with_time_and_source_connectable(
    hass: HomeAssistant,
    device: BLEDevice,
    adv: AdvertisementData,
    time: float,
    source: str,
    connectable: bool,
) -> None:
    """Inject an advertisement into the manager from a specific source at a time and connectable status."""
    async_get_advertisement_callback(hass)(
        BluetoothServiceInfoBleak(
            name=adv.local_name or device.name or device.address,
            address=device.address,
            rssi=adv.rssi,
            manufacturer_data=adv.manufacturer_data,
            service_data=adv.service_data,
            service_uuids=adv.service_uuids,
            source=source,
            device=device,
            advertisement=adv,
            connectable=connectable,
            time=time,
        )
    )

def inject_bluetooth_service_info_bleak(
    hass: HomeAssistant, info: BluetoothServiceInfoBleak
) -> None:
    """Inject an advertisement into the manager with connectable status."""
    advertisement_data = generate_advertisement_data(
        local_name=None if info.name == "" else info.name,
        manufacturer_data=info.manufacturer_data,
        service_data=info.service_data,
        service_uuids=info.service_uuids,
        rssi=info.rssi,
    )
    device = generate_ble_device(  # type: ignore[no-untyped-call]
        address=info.address,
        name=info.name,
        details={},
    )
    inject_advertisement_with_time_and_source_connectable(
        hass,
        device,
        advertisement_data,
        info.time,
        SOURCE_LOCAL,
        connectable=info.connectable,
    )
