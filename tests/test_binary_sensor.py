"""Test the BLE Battery Management System integration binary sensor definition."""

from datetime import timedelta
from typing import Final

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

SEN_PREFIX: Final[str] = "binary_sensor.smartbat_b12345"


@pytest.mark.usefixtures("enable_bluetooth", "patch_default_bleak_client")
async def test_update(
    monkeypatch, bt_discovery: BluetoothServiceInfoBleak, hass: HomeAssistant
) -> None:
    """Test binary sensor value updates through coordinator."""

    async def patch_async_update(_self) -> BMSsample:
        """Patch async ble device from address to return a given value."""
        return {
            "voltage": 17.0,
            "current": 0,
            "problem": True,
            "problem_code": 0x73,
            "battery_mode": BMSmode.ABSORPTION,
        }

    config: MockConfigEntry = mock_config(bms="dummy_bms")
    config.add_to_hass(hass)

    inject_bluetooth_service_info_bleak(hass, bt_discovery)

    assert await hass.config_entries.async_setup(config.entry_id)
    await hass.async_block_till_done()

    assert config in hass.config_entries.async_entries()
    assert config.state is ConfigEntryState.LOADED
    assert len(hass.states.async_all(["binary_sensor"])) == 2
    for sensor, attribute, ref_state in (
        ("charging", "battery_mode", STATE_ON),
        ("problem", "problem_code", STATE_OFF),
    ):
        state: State | None = hass.states.get(f"{SEN_PREFIX}_{sensor}")
        assert state is not None
        assert state.state == ref_state
        assert not state.attributes.get(attribute)

    monkeypatch.setattr(
        "custom_components.bms_ble.plugins.dummy_bms.BMS.async_update",
        patch_async_update,
    )

    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(seconds=UPDATE_INTERVAL))
    await hass.async_block_till_done()

    for sensor, attribute, ref_state, ref_value in (
        ("charging", "battery_mode", STATE_OFF, "absorption"),
        ("problem", "problem_code", STATE_ON, 0x73),
    ):
        state = hass.states.get(f"{SEN_PREFIX}_{sensor}")
        assert state is not None
        assert state.state == ref_state
        assert state.attributes.get(attribute) == ref_value
