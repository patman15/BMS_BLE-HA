"""Test the BLE Battery Management System integration sensor definition."""

from datetime import timedelta
from typing import Final

from habluetooth import BluetoothServiceInfoBleak
import pytest
from pytest_homeassistant_custom_component.common import (
    MockConfigEntry,
    async_fire_time_changed,
)

from custom_components.bms_ble.const import (
    ATTR_BALANCE_CUR,
    ATTR_CELL_VOLTAGES,
    ATTR_CURRENT,
    ATTR_CYCLES,
    ATTR_DELTA_VOLTAGE,
    ATTR_LQ,
    ATTR_POWER,
    ATTR_RUNTIME,
    ATTR_TEMP_SENSORS,
    ATTR_TEMPERATURE,
    ATTR_VOLTAGE,
    UPDATE_INTERVAL,
)
from custom_components.bms_ble.plugins.basebms import BMSsample
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant, State
from homeassistant.helpers.entity_component import async_update_entity
import homeassistant.util.dt as dt_util

from .bluetooth import inject_bluetooth_service_info_bleak
from .conftest import mock_config


@pytest.mark.usefixtures("enable_bluetooth", "patch_default_bleak_client")
async def test_update(
    monkeypatch,
    bt_discovery: BluetoothServiceInfoBleak,
    bool_fixture,
    hass: HomeAssistant,
) -> None:
    """Test sensor value updates through coordinator."""

    async def patch_async_update(_self) -> BMSsample:
        """Patch async_update to return a specific value."""
        return BMSsample(
            {
                "balance_current": -1.234,
                "battery_level": 42,
                "voltage": 17.0,
                "current": 0,
                "cell_voltages": [3, 3.123],
                "delta_voltage": 0.123,
                "temperature": 43.86,
            }
        ) | (
            {
                "temp_values": [73, 31.4, 27.18],
                "pack_battery_levels": [1.0, 2.0],
                "pack_count": 2,
                "pack_currents": [-3.14, 2.71],
                "pack_cycles": [0, 1],
                "pack_voltages": [12.34, 24.56],
            }
            if bool_fixture
            else {}
        )

    monkeypatch.setattr(
        "homeassistant.helpers.entity.Entity.entity_registry_enabled_default",
        lambda _: True,
    )

    config: MockConfigEntry = mock_config(bms="dummy_bms")
    config.add_to_hass(hass)

    inject_bluetooth_service_info_bleak(hass, bt_discovery)

    assert await hass.config_entries.async_setup(config.entry_id)
    await hass.async_block_till_done(wait_background_tasks=True)

    assert config in hass.config_entries.async_entries()
    assert config.state is ConfigEntryState.LOADED
    assert len(hass.states.async_all(["sensor"])) == 11
    data: dict[str, str] = {
        entity.entity_id: entity.state for entity in hass.states.async_all(["sensor"])
    }
    assert data == {
        f"sensor.smartbat_b12345_{ATTR_VOLTAGE}": "12",
        "sensor.smartbat_b12345_battery": "unknown",
        f"sensor.smartbat_b12345_{ATTR_TEMPERATURE}": "27.182",
        f"sensor.smartbat_b12345_{ATTR_CURRENT}": "1.5",
        "sensor.smartbat_b12345_stored_energy": "unknown",
        f"sensor.smartbat_b12345_{ATTR_CYCLES}": "unknown",
        f"sensor.smartbat_b12345_{ATTR_DELTA_VOLTAGE}": "unknown",
        f"sensor.smartbat_b12345_{ATTR_LQ}": "0",
        f"sensor.smartbat_b12345_{ATTR_POWER}": "18.0",
        "sensor.smartbat_b12345_signal_strength": "-127",
        f"sensor.smartbat_b12345_{ATTR_RUNTIME}": "unknown",
    }

    monkeypatch.setattr(
        "custom_components.bms_ble.plugins.dummy_bms.BMS.async_update",
        patch_async_update,
    )

    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(seconds=UPDATE_INTERVAL))
    await hass.async_block_till_done()

    # check that link quality has been updated, since the coordinator and the LQ sensor are
    # asynchronous to each other, a race condition can happen, thus update LQ sensor again
    # to cover the case that LQ is updated before the coordinator changes the value
    lq: Final[State | None] = hass.states.get(f"sensor.smartbat_b12345_{ATTR_LQ}")
    assert lq is not None and int(lq.state) >= 50
    await async_update_entity(hass, f"sensor.smartbat_b12345_{ATTR_LQ}")
    await hass.async_block_till_done()

    data = {
        entity.entity_id: entity.state for entity in hass.states.async_all(["sensor"])
    }

    # check all sensor have correct updated value
    assert data == {
        f"sensor.smartbat_b12345_{ATTR_VOLTAGE}": "17.0",
        "sensor.smartbat_b12345_battery": "42",
        f"sensor.smartbat_b12345_{ATTR_TEMPERATURE}": "43.86",
        f"sensor.smartbat_b12345_{ATTR_CURRENT}": "0",
        "sensor.smartbat_b12345_stored_energy": "unknown",
        f"sensor.smartbat_b12345_{ATTR_CYCLES}": "unknown",
        f"sensor.smartbat_b12345_{ATTR_DELTA_VOLTAGE}": "0.123",
        f"sensor.smartbat_b12345_{ATTR_LQ}": "66",  # initial update + one UPDATE_INTERVAL
        f"sensor.smartbat_b12345_{ATTR_POWER}": "unknown",
        "sensor.smartbat_b12345_signal_strength": "-61",
        f"sensor.smartbat_b12345_{ATTR_RUNTIME}": "unknown",
    }
    # check delta voltage sensor has cell voltage as attribute array
    delta_state: State | None = hass.states.get(
        f"sensor.smartbat_b12345_{ATTR_DELTA_VOLTAGE}"
    )
    assert delta_state is not None and delta_state.attributes[ATTR_CELL_VOLTAGES] == [
        3,
        3.123,
    ]

    # check temperature sensor has individual sensors as attribute array
    temp_state: State | None = hass.states.get(
        f"sensor.smartbat_b12345_{ATTR_TEMPERATURE}"
    )
    assert temp_state is not None and temp_state.attributes[ATTR_TEMP_SENSORS] == (
        [73, 31.4, 27.18] if bool_fixture else [float(temp_state.state)]
    )
    # check balance current as attribute
    current_state: State | None = hass.states.get(
        f"sensor.smartbat_b12345_{ATTR_CURRENT}"
    )
    assert current_state is not None and current_state.attributes[ATTR_BALANCE_CUR] == [
        -1.234
    ]

    # check battery pack attributes
    for sensor, attribute, ref_value in [
        (ATTR_CURRENT, "pack_currents", [-3.14, 2.71]),
        (ATTR_CYCLES, "pack_cycles", [0, 1]),
        ("battery", "pack_battery_levels", [1.0, 2.0]),
        (ATTR_VOLTAGE, "pack_voltages", [12.34, 24.56]),
    ]:
        pack_state: State | None = hass.states.get(f"sensor.smartbat_b12345_{sensor}")
        assert pack_state is not None, f"failed to get state of sensor '{sensor}'"
        assert pack_state.attributes.get(attribute, None) == (
            ref_value if bool_fixture else None
        ), f"faild to verify sensor '{sensor}' attribute '{attribute}'"
