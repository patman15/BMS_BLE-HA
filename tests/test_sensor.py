"""Test the BLE Battery Management System integration sensor definition."""

from datetime import timedelta
from typing import Final

from aiobmsble import BMSSample, PackSample, TempSensor as TS
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
    DOMAIN,
    LINK_SENSORS,
    OPT_SENSORS,
    PACK_SENSORS,
    SENSORS,
    UPDATE_INTERVAL,
)
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import ATTR_TEMPERATURE, ATTR_VOLTAGE, STATE_UNKNOWN
from homeassistant.core import HomeAssistant, State
from homeassistant.helpers import device_registry as dr, entity_registry as er
from homeassistant.helpers.entity_component import async_update_entity
import homeassistant.util.dt as dt_util

from .bluetooth import inject_bluetooth_service_info_bleak
from .conftest import mock_config, mock_devinfo_min

DEV_NAME: Final[str] = "sensor.config_test_dummy_bms"
PACK_NAME: Final[str] = "pack"


@pytest.mark.usefixtures(
    "enable_bluetooth", "patch_default_bleak_client", "patch_entity_enabled_default"
)  # enable bluetooth, patch bleak client and enable all sensors
async def test_update(
    monkeypatch: pytest.MonkeyPatch,
    bt_discovery: BluetoothServiceInfoBleak,
    hass: HomeAssistant,
) -> None:
    """Test sensor value updates through coordinator."""

    async def patch_async_update(_self) -> BMSSample:
        """Patch async_update to return a specific value."""
        return BMSSample(
            balance_current=-1.234,
            heater_current=2.5,
            battery_level=42,
            voltage=17.0,
            current=1.5,
            delta_cell_voltage=0.123,
            temperature=[TS(43.86)],
            problem=True,
            problem_code=0x73,
            cell_voltages=[3.1, 3, 3.123],
            pack_count=2,
            packs=[
                PackSample(
                    battery_level=1.0,
                    current=-3.14,
                    cycles=0,
                    voltage=12.34,
                    temperature=[TS(73), TS(31.4)],
                    cell_voltages=[4.1, 4],
                ),
                PackSample(
                    battery_level=2.0,
                    current=2.71,
                    cycles=1,
                    voltage=24.56,
                    temperature=[TS(27.18)],
                    cell_voltages=[4.123],
                ),
            ],
        )

    _result_dict: Final[dict[str, str]] = {
        f"{DEV_NAME}_{ATTR_VOLTAGE}": "17.0",
        f"{DEV_NAME}_battery": "42",
        f"{DEV_NAME}_{ATTR_TEMPERATURE}": "43.86",
        f"{DEV_NAME}_{ATTR_CURRENT}": "1.5",
        f"{DEV_NAME}_stored_energy": STATE_UNKNOWN,
        f"{DEV_NAME}_{ATTR_CYCLES}": STATE_UNKNOWN,
        f"{DEV_NAME}_{ATTR_DELTA_VOLTAGE}": "0.123",
        f"{DEV_NAME}_highest_cell_voltage": "3.123",
        f"{DEV_NAME}_lowest_cell_voltage": "3",
        f"{DEV_NAME}_{ATTR_POWER}": STATE_UNKNOWN,
        f"{DEV_NAME}_{ATTR_RUNTIME}": STATE_UNKNOWN,
        f"{DEV_NAME}_{PACK_NAME}_1_battery": "1.0",
        f"{DEV_NAME}_{PACK_NAME}_1_current": "-3.14",
        f"{DEV_NAME}_{PACK_NAME}_1_cycles": "0",
        f"{DEV_NAME}_{PACK_NAME}_1_delta_cell_voltage": STATE_UNKNOWN,
        f"{DEV_NAME}_{PACK_NAME}_1_highest_cell_voltage": "4.1",
        f"{DEV_NAME}_{PACK_NAME}_1_lowest_cell_voltage": "4",
        f"{DEV_NAME}_{PACK_NAME}_1_power": STATE_UNKNOWN,
        f"{DEV_NAME}_{PACK_NAME}_1_sensor_1_generic_temperature": "73.0",
        f"{DEV_NAME}_{PACK_NAME}_1_sensor_2_generic_temperature": "31.4",
        f"{DEV_NAME}_{PACK_NAME}_1_stored_energy": STATE_UNKNOWN,
        f"{DEV_NAME}_{PACK_NAME}_1_temperature": "52.2",
        f"{DEV_NAME}_{PACK_NAME}_1_voltage": "12.34",
        f"{DEV_NAME}_{PACK_NAME}_2_battery": "2.0",
        f"{DEV_NAME}_{PACK_NAME}_2_current": "2.71",
        f"{DEV_NAME}_{PACK_NAME}_2_cycles": "1",
        f"{DEV_NAME}_{PACK_NAME}_2_delta_cell_voltage": STATE_UNKNOWN,
        f"{DEV_NAME}_{PACK_NAME}_2_highest_cell_voltage": "4.123",
        f"{DEV_NAME}_{PACK_NAME}_2_lowest_cell_voltage": "4.123",
        f"{DEV_NAME}_{PACK_NAME}_2_power": STATE_UNKNOWN,
        f"{DEV_NAME}_{PACK_NAME}_2_stored_energy": STATE_UNKNOWN,
        f"{DEV_NAME}_{PACK_NAME}_2_temperature": "27.18",
        f"{DEV_NAME}_{PACK_NAME}_2_voltage": "24.56",
    }

    bms_class: Final[str] = "aiobmsble.bms.dummy_bms.BMS"
    monkeypatch.setattr(f"{bms_class}.device_info", mock_devinfo_min)
    monkeypatch.setattr(f"{bms_class}.async_update", patch_async_update)

    config: MockConfigEntry = mock_config()
    config.add_to_hass(hass)

    inject_bluetooth_service_info_bleak(hass, bt_discovery)

    assert await hass.config_entries.async_setup(config.entry_id)
    await hass.async_block_till_done()

    assert config in hass.config_entries.async_entries()
    assert config.state is ConfigEntryState.LOADED

    data: dict[str, str] = {  # check sensors only (ignore other platforms)
        entity.entity_id: entity.state for entity in hass.states.async_all(["sensor"])
    }
    assert len(data) == (SENSORS - OPT_SENSORS) + LINK_SENSORS + PACK_SENSORS * 2
    assert (
        data
        == {
            f"{DEV_NAME}_{ATTR_LQ}": "0",
            f"{DEV_NAME}_signal_strength": STATE_UNKNOWN,
        }
        | _result_dict
    )

    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(seconds=UPDATE_INTERVAL))
    await hass.async_block_till_done(wait_background_tasks=True)

    # check that link quality has been updated, since the coordinator and the LQ sensor are
    # asynchronous to each other, a race condition can happen, thus update LQ sensor again
    # to cover the case that LQ is updated before the coordinator changes the value
    lq: Final[State | None] = hass.states.get(f"{DEV_NAME}_{ATTR_LQ}")
    assert lq is not None and int(lq.state) >= 50
    await async_update_entity(hass, f"{DEV_NAME}_{ATTR_LQ}")
    await hass.async_block_till_done()

    data = {  # check sensors only (ignore other platforms)
        entity.entity_id: entity.state for entity in hass.states.async_all(["sensor"])
    }
    # check all sensor have correct updated value (translated names: EN)
    assert (
        data
        == {
            f"{DEV_NAME}_{ATTR_LQ}": "66",  # initial update + one UPDATE_INTERVAL
            f"{DEV_NAME}_signal_strength": "-61",
        }
        | _result_dict
    )

    # check that attributes to sensors were updated
    pack_states: dict[str, str] = {
        entity.entity_id: entity.state
        for entity in hass.states.async_all(["sensor"])
        if f"_{PACK_NAME}_" in entity.entity_id
    }
    assert len(pack_states) == PACK_SENSORS * 2

    device_registry: dr.DeviceRegistry = dr.async_get(hass)
    parent: dr.DeviceEntry | None = device_registry.async_get_device_by_identifier(
        (DOMAIN, "cc:cc:cc:cc:cc:cc"), config.entry_id
    )
    pack_device: list[dr.ChildDeviceEntry | None] = [
        device_registry.async_get_child_device_by_identifier(
            (DOMAIN, f"cc:cc:cc:cc:cc:cc_pack_{idx}"), config.entry_id
        )
        for idx in range(1, 3)
    ]
    assert parent is not None
    pack_device_ids: set[str] = set()
    for device in pack_device:
        assert device is not None
        assert device.parent_device_id == parent.id
        pack_device_ids.add(device.id)

    entity_registry: er.EntityRegistry = er.async_get(hass)
    for entity_id in pack_states:
        assert hass.states.get(entity_id) is not None
        pack_entity: er.RegistryEntry | None = entity_registry.async_get(entity_id)
        assert pack_entity is not None
        assert pack_entity.device_id in pack_device_ids

    for sensor, attribute, value in (
        (ATTR_DELTA_VOLTAGE, ATTR_CELL_VOLTAGES, [3.1, 3, 3.123]),
        ("highest_cell_voltage", "cell_number", [3]),
        ("lowest_cell_voltage", "cell_number", [2]),
        (
            ATTR_CURRENT,
            ATTR_BALANCE_CUR,
            [-1.234],
        ),
        (
            ATTR_CURRENT,
            "heater_current",
            [2.5],
        ),
    ):
        state: State | None = hass.states.get(f"{DEV_NAME}_{sensor}")
        assert (
            state is not None and state.attributes[attribute] == value
        ), f"failed to verify attribute {attribute} for sensor {sensor}"
