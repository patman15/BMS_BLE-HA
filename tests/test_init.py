"""Test the BLE Battery Management System integration initialization."""

from bleak.backends.device import BLEDevice
from habluetooth import BluetoothServiceInfoBleak
import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant

from .bluetooth import inject_bluetooth_service_info_bleak
from .conftest import mock_config, mock_update_exc, mock_update_min


@pytest.mark.usefixtures("enable_bluetooth", "patch_default_bleak_client")
async def test_init_fail(
    monkeypatch,
    bms_fixture: str,
    bt_discovery: BluetoothServiceInfoBleak,
    hass: HomeAssistant,
) -> None:
    """Test entries are unloaded correctly."""

    monkeypatch.setattr(
        f"custom_components.bms_ble.plugins.{bms_fixture}.BMS.async_update",
        mock_update_exc,
    )

    trace_fct: dict[str, bool] = {"stop_called": False}

    async def mock_coord_shutdown(_self) -> None:
        trace_fct["stop_called"] = True

    monkeypatch.setattr(
        "custom_components.bms_ble.BTBmsCoordinator.async_shutdown",
        mock_coord_shutdown,
    )

    inject_bluetooth_service_info_bleak(hass, bt_discovery)

    cfg: MockConfigEntry = mock_config(bms=bms_fixture)
    cfg.add_to_hass(hass)

    assert not await hass.config_entries.async_setup(
        cfg.entry_id
    ), "test did not make setup fail!"
    await hass.async_block_till_done()

    # verify it is not yet loaded
    assert cfg.state is ConfigEntryState.SETUP_RETRY

    assert trace_fct["stop_called"] is True, "Failed to call coordinator stop()."
    assert (
        cfg in hass.config_entries.async_entries()
    ), "Incorrect configuration entry found."
    # Assert platforms unloaded
    await hass.async_block_till_done()
    assert (
        len(hass.states.async_all(["sensor", "binary_sensor"])) == 0
    ), "Failure: config entry generated sensors."


@pytest.mark.usefixtures("enable_bluetooth", "patch_default_bleak_client")
async def test_unload_entry(
    monkeypatch,
    bms_fixture: str,
    bool_fixture: bool,
    bt_discovery: BluetoothServiceInfoBleak,
    hass: HomeAssistant,
) -> None:
    """Test entries are unloaded correctly."""
    unload_fail: bool = bool_fixture

    # first load entry (see test_async_setup_entry)
    inject_bluetooth_service_info_bleak(hass, bt_discovery)

    cfg: MockConfigEntry = mock_config(bms=bms_fixture)
    cfg.add_to_hass(hass)

    monkeypatch.setattr(
        f"custom_components.bms_ble.plugins.{bms_fixture}.BMS.async_update",
        mock_update_min,
    )

    def mock_coord_shutdown(_self) -> None:
        trace_fct["shutdown_called"] = True

    async def mock_unload_platforms(_self, _entry, _platforms) -> bool:
        return False

    if unload_fail:
        monkeypatch.setattr(
            "homeassistant.config_entries.ConfigEntries.async_unload_platforms",
            mock_unload_platforms,
        )

    monkeypatch.setattr(
        "custom_components.bms_ble.BTBmsCoordinator.async_shutdown",
        mock_coord_shutdown,
    )

    assert await hass.config_entries.async_setup(cfg.entry_id)
    await hass.async_block_till_done()

    # verify it is loaded
    assert cfg in hass.config_entries.async_entries()
    assert cfg.state is ConfigEntryState.LOADED

    # run removal of entry (actual test)
    trace_fct: dict[str, bool] = {"shutdown_called": False}

    assert await hass.config_entries.async_remove(cfg.entry_id)
    await hass.async_block_till_done(wait_background_tasks=True)

    assert (  # shutdown is only called if entry unload succeeded
        trace_fct["shutdown_called"] or unload_fail
    ), "Failed to call coordinator async_shutdown()."
    assert (
        cfg not in hass.config_entries.async_entries()
    ), "Failed to remove configuration entry."
    # Assert platforms unloaded
    assert (
        len(hass.states.async_all(["sensor", "binary_sensor"])) == 0
    ), "Failed to remove platforms."


@pytest.mark.usefixtures("enable_bluetooth")
async def test_device_name_none(
    monkeypatch,
    bt_discovery: BluetoothServiceInfoBleak,
    hass: HomeAssistant,
) -> None:
    """Test that setup fails gracefully when device name is None."""

    def mock_device_from_address(_hass, _address, _connectable) -> BLEDevice:
        return BLEDevice(
            address="cc:cc:cc:cc:cc:cc", name=None, details={"path": None}, rssi=-85
        )

    monkeypatch.setattr(
        "custom_components.bms_ble.async_ble_device_from_address",
        mock_device_from_address,
    )

    inject_bluetooth_service_info_bleak(hass, bt_discovery)

    cfg: MockConfigEntry = mock_config(bms="dummy_bms")
    cfg.add_to_hass(hass)

    # Setup should fail with ConfigEntryNotReady
    assert not await hass.config_entries.async_setup(cfg.entry_id)
    await hass.async_block_till_done()

    # Verify the entry is in retry state
    assert cfg.state is ConfigEntryState.SETUP_RETRY
