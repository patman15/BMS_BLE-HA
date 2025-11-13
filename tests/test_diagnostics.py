"""Test the BLE Battery Management System integration constants definition."""

from datetime import timedelta
from typing import Any, Final

from habluetooth import BluetoothServiceInfoBleak
import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.bms_ble.const import DOMAIN
from custom_components.bms_ble.coordinator import BTBmsCoordinator
from custom_components.bms_ble.diagnostics import async_get_config_entry_diagnostics
from homeassistant.components.bluetooth.const import DOMAIN as BT_DOMAIN
from homeassistant.components.diagnostics.const import REDACTED
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
    "connections": {("bluetooth", "cc:cc:cc:cc:cc:cc")},  # bt_discovery fixture
    "created_at": 1737117652.687534,
    "identifiers": {
        ("bluetooth", "cc:cc:cc:cc:cc:cc"),
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

    ce: MockConfigEntry = mock_config(
        bms=BMS_DEV["name"], unique_id=next(iter(BMS_DEV["identifiers"]))[1]
    )
    config_entry: ConfigEntry[BTBmsCoordinator] = ce
    ce.runtime_data = BTBmsCoordinator(
        hass, bt_discovery.device, MockBMS(), config_entry
    )
    ce.add_to_hass(hass)

    device_registry: dr.DeviceRegistry = dr.async_get(hass)

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

    expected_diag_data: Final[dict[str, Any]] = {
        "config_entry": {
            "created_at": ce.created_at.isoformat(),
            "data": {
                "type": "aiobmsble.bms.mock_BMS",
            },
            "disabled_by": None,
            "discovery_keys": {},
            "domain": DOMAIN,
            "entry_id": REDACTED,
            "minor_version": 0,
            "modified_at": ce.modified_at.isoformat(),
            "options": {},
            "pref_disable_new_entities": False,
            "pref_disable_polling": False,
            "source": "user",
            "subentries": [],
            "title": "config_test_mock_BMS",
            "unique_id": "cc:cc:cc:cc:cc:cc",
            "version": 2,
        },
        "adapter_data": (
            "mock adapter, adapter mnf (adapter model/2): 14, 3"
            if bool_fixture
            else "unavailable"
        ),
        "advertisement_data": bt_discovery.as_dict() | {"source": REDACTED },
        "bms_link_quality": 50,
        "bms_info": {
            "connections": {(BT_DOMAIN, ce.unique_id)},
            "identifiers": {(BT_DOMAIN, ce.unique_id), (DOMAIN, ce.unique_id)},
            "name": ce.title,
            "manufacturer": MockBMS.INFO.get("default_manufacturer"),
            "model": MockBMS.INFO.get("default_model"),
            "sw_version": None,
            "hw_version": None,
            "model_id": None,
            "serial_number": None,
        },
        "bms_data": {
            "current": 1.7,
            "cycle_charge": 19,
            "cycles": 23,
            "voltage": 13,
        },
        "update_data": {
            "interval": timedelta(seconds=30),
            "last_exception": None,
            "last_update_success": True,
        },
    }

    monkeypatch.setattr("aiobmsble.basebms.BleakClient", MockBleakClient)

    inject_bluetooth_service_info_bleak(hass, bt_discovery)
    await ce.runtime_data._async_setup()
    await ce.runtime_data.async_refresh()

    diag_data: dict[str, Any] = await async_get_config_entry_diagnostics(
        hass, config_entry
    )

    assert repr(diag_data.pop("advertisement_data")) == repr(
        expected_diag_data.pop("advertisement_data")
    )
    assert diag_data == expected_diag_data
