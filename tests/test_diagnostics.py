"""Test the BLE Battery Management System integration constants definition."""

from datetime import timedelta
from typing import Any, Final

from habluetooth import BluetoothServiceInfoBleak
import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.bms_ble import DOMAIN
from custom_components.bms_ble.coordinator import BTBmsCoordinator
from custom_components.bms_ble.diagnostics import async_get_device_diagnostics
from homeassistant.components.bluetooth.const import DOMAIN as BT_DOMAIN
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr
from tests.bluetooth import inject_bluetooth_service_info_bleak
from tests.conftest import MockBleakClient, MockBMS, mock_config

BT_ADAPTER: Final[dict[str, Any]] = {
    "connections": {(BT_DOMAIN, "local")},
    "hw_version": 14,
    "manufacturer": "adapter mnf",
    "model": "adapter model",
    "model_id": 2,
    "name": "mock adapter",
    "sw_version": 3,
}

BMS_DEV: Final[dict[str, Any]] = {
    "connections": {("bluetooth", "CC:8D:A2:1F:70:F1")},
    "created_at": 1737117652.687534,
    "identifiers": {
        ("bluetooth", "CC:8D:A2:1F:70:F1"),
    },
    "labels": [],
    "manufacturer": "MyManufacturer",
    "model": "Smart Mock BMS",
    "modified_at": 1742845669.995203,
    "name": "mock_BMS",
}


@pytest.mark.usefixtures("enable_bluetooth")
async def test_diagnostics(
    monkeypatch: pytest.MonkeyPatch,
    bool_fixture: bool,
    bt_discovery: BluetoothServiceInfoBleak,
    hass: HomeAssistant,
) -> None:
    """Home Assistant device diagnostic download."""

    ce: MockConfigEntry = mock_config(bms="dummy")
    config_entry: ConfigEntry[BTBmsCoordinator] = ce
    ce.runtime_data = BTBmsCoordinator(
        hass, bt_discovery.device, MockBMS(), config_entry
    )
    ce.add_to_hass(hass)

    device_registry: dr.DeviceRegistry = dr.async_get(hass)
    device: dr.DeviceEntry = device_registry.async_get_or_create(
        config_entry_id=config_entry.entry_id,
        identifiers={(DOMAIN, ce.unique_id)} | BMS_DEV["identifiers"],
        connections=BMS_DEV["connections"],
        manufacturer=BMS_DEV["manufacturer"],
        model=BMS_DEV["model"],
        name=BMS_DEV["name"],
    )

    if bool_fixture:
        ad: MockConfigEntry = MockConfigEntry(  # create Bluetooth adapter
            domain=BT_DOMAIN,
            version=1,
            minor_version=0,
            unique_id="mockhci_01",
            title="mockBT adapter",
        )
        ad.add_to_hass(hass)
        device_registry.async_get_or_create(config_entry_id=ad.entry_id, **BT_ADAPTER)

    monkeypatch.setattr("aiobmsble.basebms.BleakClient", MockBleakClient)

    inject_bluetooth_service_info_bleak(hass, bt_discovery)
    await ce.runtime_data.async_refresh()

    diag_data: dict[str, Any] = await async_get_device_diagnostics(
        hass, config_entry, device
    )

    assert str(diag_data["adv_data"]) == str(bt_discovery)
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
    assert (
        diag_data["adapter_data"]
        == "mock adapter, adapter mnf (adapter model/2): 14, 3"
        if bool_fixture
        else "unavailable"
    )
    assert diag_data["device_data"]["config_entries"] == [config_entry.entry_id]
    assert diag_data["device_data"]["id"] == "**REDACTED**"
    assert diag_data["device_data"]["name"] == BMS_DEV["name"]
    assert diag_data["device_data"]["model"] == BMS_DEV["model"]
    assert diag_data["device_data"]["manufacturer"] == BMS_DEV["manufacturer"]
    assert diag_data["entry_data"] == {
        "type": "aiobmsble.bms.dummy",
    }
    assert diag_data["update_data"] == {
        "interval": timedelta(seconds=30),
        "last_exception": None,
        "last_update_success": True,
    }
