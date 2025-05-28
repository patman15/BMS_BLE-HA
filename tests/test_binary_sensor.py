"""Test the BLE Battery Management System integration binary sensor definition."""

from datetime import timedelta

from habluetooth import BluetoothServiceInfoBleak
import pytest
from pytest_homeassistant_custom_component.common import (
    MockConfigEntry,
    async_fire_time_changed,
)

from custom_components.bms_ble.const import UPDATE_INTERVAL
from custom_components.bms_ble.plugins.basebms import BMSmode, BMSsample
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import STATE_OFF, STATE_ON
from homeassistant.core import HomeAssistant, State
import homeassistant.util.dt as dt_util

from .bluetooth import inject_bluetooth_service_info_bleak
from .conftest import mock_config


@pytest.mark.usefixtures("enable_bluetooth", "patch_default_bleak_client")
async def test_update(
    monkeypatch, bt_discovery: BluetoothServiceInfoBleak, hass: HomeAssistant
) -> None:
    """Test binary sensor value updates through coordinator."""

    async def patch_async_update(_self) -> BMSsample:
        """Patch async ble device from address to return a given value."""
        return {"voltage": 17.0, "current": 0, "problem": True, "battery_mode": BMSmode.ABSORPTION}

    config: MockConfigEntry = mock_config(bms="dummy_bms")
    config.add_to_hass(hass)

    inject_bluetooth_service_info_bleak(hass, bt_discovery)

    assert await hass.config_entries.async_setup(config.entry_id)
    await hass.async_block_till_done()

    assert config in hass.config_entries.async_entries()
    assert config.state is ConfigEntryState.LOADED
    assert len(hass.states.async_all(["binary_sensor"])) == 2
    assert hass.states.is_state("binary_sensor.smartbat_b12345_charging", STATE_ON)
    assert hass.states.is_state("binary_sensor.smartbat_b12345_problem", STATE_OFF)
    charging_state: State | None = hass.states.get("binary_sensor.smartbat_b12345_charging")
    assert charging_state
    assert not charging_state.attributes.get("battery_mode")

    monkeypatch.setattr(
        "custom_components.bms_ble.plugins.dummy_bms.BMS.async_update",
        patch_async_update,
    )

    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(seconds=UPDATE_INTERVAL))
    await hass.async_block_till_done()

    assert hass.states.is_state("binary_sensor.smartbat_b12345_charging", STATE_OFF)
    assert hass.states.is_state("binary_sensor.smartbat_b12345_problem", STATE_ON)
    charging_state = hass.states.get("binary_sensor.smartbat_b12345_charging")
    assert charging_state
    assert charging_state.attributes.get("battery_mode") == "absorption"
