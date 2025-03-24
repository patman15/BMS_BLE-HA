"""Test the BLE Battery Management System integration constants definition."""

from habluetooth import BluetoothServiceInfoBleak
import pytest

from custom_components.bms_ble.coordinator import BTBmsCoordinator
from custom_components.bms_ble.diagnostics import async_get_device_diagnostics
from homeassistant.core import HomeAssistant

from .bluetooth import inject_bluetooth_service_info_bleak
from .conftest import Mock_BMS, mock_config


async def test_diagnostics(
    BTdiscovery: BluetoothServiceInfoBleak,
    hass: HomeAssistant,
) -> None:
    """Home Assistant device diagnostic download."""

    coordinator = BTBmsCoordinator(
        hass, BTdiscovery.device, Mock_BMS(), mock_config(bms="update")
    )

    inject_bluetooth_service_info_bleak(hass, BTdiscovery)

    await coordinator.async_refresh()
    assert (
        await async_get_device_diagnostics(hass, coordinator.config_entry, None) == {}
    )

    pytest.fail("not implemented")
