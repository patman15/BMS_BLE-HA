"""Test the BLE Battery Management System integration binary sensor definition."""

from datetime import timedelta

from custom_components.bms_ble.const import UPDATE_INTERVAL
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import STATE_OFF, STATE_ON
from homeassistant.core import HomeAssistant
import homeassistant.util.dt as dt_util
from .conftest import mock_config
from pytest_homeassistant_custom_component.common import async_fire_time_changed
from .bluetooth import inject_bluetooth_service_info_bleak



async def test_update(monkeypatch, BTdiscovery, hass: HomeAssistant) -> None:
    """Test binary sensor value updates through coordinator."""

    async def patch_device(self):
        """Patch async ble device from address to return a given value."""
        return {"voltage": 17.0, "current": 0}

    config = mock_config(bms="dummy_bms")
    config.add_to_hass(hass)

    inject_bluetooth_service_info_bleak(hass, BTdiscovery)

    assert await hass.config_entries.async_setup(config.entry_id)
    await hass.async_block_till_done()

    assert config in hass.config_entries.async_entries()
    assert config.state is ConfigEntryState.LOADED
    assert len(hass.states.async_all(["binary_sensor"])) == 1
    assert hass.states.is_state("binary_sensor.smartbat_b12345_charging", STATE_ON)

    monkeypatch.setattr(
        "custom_components.bms_ble.plugins.dummy_bms.BMS.async_update",
        patch_device,
    )

    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(seconds=UPDATE_INTERVAL))
    await hass.async_block_till_done()

    assert hass.states.is_state("binary_sensor.smartbat_b12345_charging", STATE_OFF)
