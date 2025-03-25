"""Test the BLE Battery Management System integration constants definition."""

from datetime import timedelta
from typing import Any

from habluetooth import BluetoothServiceInfoBleak
import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.bms_ble import DOMAIN
from custom_components.bms_ble.coordinator import BTBmsCoordinator
from custom_components.bms_ble.diagnostics import async_get_device_diagnostics
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr

from .bluetooth import inject_bluetooth_service_info_bleak
from .conftest import Mock_BMS, MockBleakClient, mock_config

DEVICE: dict[str, Any] = {
    "connections": {("bluetooth", "CC:8D:A2:1F:70:F1")},
    "created_at": 1737117652.687534,
    "identifiers": {
        ("bluetooth", "CC:8D:A2:1F:70:F1"),
    },
    "labels": [],
    "manufacturer": "MyManufacturer",
    "model": "Smart BMS",
    "modified_at": 1742845669.995203,
    "name": "My BMS",
}


@pytest.mark.usefixtures("enable_bluetooth")
async def test_diagnostics(
    monkeypatch: pytest.MonkeyPatch,
    BTdiscovery: BluetoothServiceInfoBleak,
    hass: HomeAssistant,
) -> None:
    """Home Assistant device diagnostic download."""

    ce: MockConfigEntry = mock_config(bms="dummy")
    config_entry: ConfigEntry[BTBmsCoordinator] = ce
    ce.runtime_data = BTBmsCoordinator(
        hass, BTdiscovery.device, Mock_BMS(), config_entry
    )
    ce.add_to_hass(hass)

    device_registry: dr.DeviceRegistry = dr.async_get(hass)
    device: dr.DeviceEntry = device_registry.async_get_or_create(
        config_entry_id=config_entry.entry_id,
        identifiers={(DOMAIN, ce.unique_id)} | DEVICE["identifiers"],
        connections=DEVICE["connections"],
        manufacturer=DEVICE["manufacturer"],
        model=DEVICE["model"],
        name=DEVICE["name"],
    )

    monkeypatch.setattr(
        "custom_components.bms_ble.plugins.basebms.BleakClient", MockBleakClient
    )

    inject_bluetooth_service_info_bleak(hass, BTdiscovery)
    await ce.runtime_data.async_refresh()

    diag_data: dict[str, Any] = await async_get_device_diagnostics(
        hass, config_entry, device
    )

    assert str(diag_data["adv_data"]) == str(BTdiscovery)
    assert diag_data["bms_data"] == {
        "current": 1.7,
        "cycle_charge": 19,
        "cycles": 23,
        "voltage": 13,
    }
    assert diag_data["bt_data"] == {
        "link_quality": 50,
        "rssi": -61,
    }
    assert diag_data["device_data"]["config_entries"] == [config_entry.entry_id]
    assert diag_data["device_data"]["id"] == "**REDACTED**"
    assert diag_data["device_data"]["name"] == DEVICE["name"]
    assert diag_data["device_data"]["model"] == DEVICE["model"]
    assert diag_data["device_data"]["manufacturer"] == DEVICE["manufacturer"]
    assert diag_data["entry_data"] == {
        "type": "custom_components.bms_ble.plugins.dummy",
    }
    assert diag_data["update_data"] == {
        "interval": timedelta(seconds=30),
        "last_exception": None,
        "last_update_success": True,
    }
