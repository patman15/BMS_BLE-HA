"""Test the BLE Battery Management System integration initialization."""

from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from .bluetooth import inject_bluetooth_service_info_bleak
from .conftest import mock_config, mock_update_exc, mock_update_min


async def test_init_fail(
    monkeypatch, bms_fixture, BTdiscovery, hass: HomeAssistant
) -> None:
    """Test entries are unloaded correctly."""

    monkeypatch.setattr(
        f"custom_components.bms_ble.plugins.{bms_fixture}.BMS.async_update",
        mock_update_exc,
    )

    trace_fct = {"stop_called": False}

    async def mock_coord_stop(_self) -> None:
        trace_fct["stop_called"] = True

    monkeypatch.setattr(
        "custom_components.bms_ble.BTBmsCoordinator.stop",
        mock_coord_stop,
    )

    inject_bluetooth_service_info_bleak(hass, BTdiscovery)

    cfg = mock_config(bms=bms_fixture)
    cfg.add_to_hass(hass)

    assert not await hass.config_entries.async_setup(
        cfg.entry_id
    ), "test did not make setup fail!"
    await hass.async_block_till_done()

    # verify it is no yet loaded
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


async def test_unload_entry(
    monkeypatch, bms_fixture, bool_fixture, BTdiscovery, hass: HomeAssistant
) -> None:
    """Test entries are unloaded correctly."""
    unload_fail: bool = bool_fixture

    # first load entry (see test_async_setup_entry)
    inject_bluetooth_service_info_bleak(hass, BTdiscovery)

    cfg = mock_config(bms=bms_fixture)
    cfg.add_to_hass(hass)

    monkeypatch.setattr(
        f"custom_components.bms_ble.plugins.{bms_fixture}.BMS.async_update",
        mock_update_min,
    )

    assert await hass.config_entries.async_setup(cfg.entry_id)
    await hass.async_block_till_done()

    # verify it is loaded
    assert cfg in hass.config_entries.async_entries()
    assert cfg.state is ConfigEntryState.LOADED

    # run removal of entry (actual test)
    trace_fct = {"stop_called": False}

    def mock_coord_stop(_self) -> None:
        trace_fct["stop_called"] = True

    async def mock_unload_platforms(_self, _entry, _platforms) -> bool:
        return False

    if unload_fail:
        monkeypatch.setattr(
            "homeassistant.config_entries.ConfigEntries.async_unload_platforms",
            mock_unload_platforms,
        )

    monkeypatch.setattr(
        "custom_components.bms_ble.BTBmsCoordinator.stop",
        mock_coord_stop,
    )
    assert await hass.config_entries.async_remove(cfg.entry_id)

    assert (
        trace_fct["stop_called"] is not unload_fail
    ), "Failed to call coordinator stop()."
    assert (
        cfg not in hass.config_entries.async_entries()
    ), "Failed to remove configuration entry."
    # Assert platforms unloaded
    await hass.async_block_till_done()
    assert (
        len(hass.states.async_all(["sensor", "binary_sensor"])) == 0
    ), "Failed to remove platforms."
