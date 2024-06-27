"""Test the BLE Battery Management System integration sensor definition."""

from datetime import timedelta

from custom_components.bms_ble.const import (
    ATTR_CURRENT,
    ATTR_CYCLES,
    ATTR_POWER,
    ATTR_RUNTIME,
    ATTR_TEMPERATURE,
    ATTR_VOLTAGE,
    ATTR_DELTA_VOLTAGE,
    UPDATE_INTERVAL,
)
from pytest_homeassistant_custom_component.common import async_fire_time_changed

from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
import homeassistant.util.dt as dt_util

from .bluetooth import inject_bluetooth_service_info_bleak
from .conftest import mock_config


async def test_update(monkeypatch, BTdiscovery, hass: HomeAssistant) -> None:
    """Test sensor value updates through coordinator."""

    async def patch_async_update(self):
        """Patch async_update to return a specific value."""
        return {"voltage": 17.0, "current": 0}

    config = mock_config(bms="dummy_bms")
    config.add_to_hass(hass)

    inject_bluetooth_service_info_bleak(hass, BTdiscovery)

    assert await hass.config_entries.async_setup(config.entry_id)
    await hass.async_block_till_done()

    assert config in hass.config_entries.async_entries()
    assert config.state is ConfigEntryState.LOADED
    assert len(hass.states.async_all(["sensor"])) == 9
    data = {
        entity.entity_id: entity.state for entity in hass.states.async_all(["sensor"])
    }
    assert data == {
        f"sensor.smartbat_b12345_{ATTR_VOLTAGE}": "12",
        "sensor.smartbat_b12345_battery": "unknown",
        f"sensor.smartbat_b12345_{ATTR_TEMPERATURE}": "unknown",
        f"sensor.smartbat_b12345_{ATTR_CURRENT}": "1.5",
        "sensor.smartbat_b12345_stored_energy": "unknown",
        f"sensor.smartbat_b12345_{ATTR_CYCLES}": "unknown",
        f'sensor.smartbat_b12345_{ATTR_DELTA_VOLTAGE}': 'unknown',
        f"sensor.smartbat_b12345_{ATTR_POWER}": "18.0",
        f"sensor.smartbat_b12345_{ATTR_RUNTIME}": "unknown",
    }

    monkeypatch.setattr(
        "custom_components.bms_ble.plugins.dummy_bms.BMS.async_update",
        patch_async_update,
    )

    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(seconds=UPDATE_INTERVAL))
    await hass.async_block_till_done()
    data = {
        entity.entity_id: entity.state for entity in hass.states.async_all(["sensor"])
    }
    assert data == {
        f"sensor.smartbat_b12345_{ATTR_VOLTAGE}": "17.0",
        "sensor.smartbat_b12345_battery": "unknown",
        f"sensor.smartbat_b12345_{ATTR_TEMPERATURE}": "unknown",
        f"sensor.smartbat_b12345_{ATTR_CURRENT}": "0",
        "sensor.smartbat_b12345_stored_energy": "unknown",
        f"sensor.smartbat_b12345_{ATTR_CYCLES}": "unknown",
        f'sensor.smartbat_b12345_{ATTR_DELTA_VOLTAGE}': 'unknown',        
        f"sensor.smartbat_b12345_{ATTR_POWER}": "unknown",
        f"sensor.smartbat_b12345_{ATTR_RUNTIME}": "unknown",
    }
