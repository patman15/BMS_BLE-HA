"""Test the BLE Battery Management System integration button definition."""

from typing import Final

from aiobmsble import BMSSample
from habluetooth import BluetoothServiceInfoBleak
import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant, State

from .bluetooth import inject_bluetooth_service_info_bleak
from .conftest import mock_config, mock_devinfo_min, mock_update_min

BTN_ENTITY: Final[str] = "button.config_test_dummy_bms_refresh"


@pytest.mark.usefixtures(
    "enable_bluetooth", "patch_default_bleak_client", "patch_entity_enabled_default"
)
@pytest.mark.parametrize("expected_lingering_timers", [True])
async def test_refresh_button(
    monkeypatch: pytest.MonkeyPatch,
    bt_discovery: BluetoothServiceInfoBleak,
    hass: HomeAssistant,
) -> None:
    """Test that the refresh button triggers an on-demand coordinator update."""

    calls: dict[str, int] = {"count": 0}

    async def patch_async_update(_self) -> BMSSample:
        calls["count"] += 1
        return await mock_update_min(_self)

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
    assert len(hass.states.async_all(["button"])) == 1

    state: State | None = hass.states.get(BTN_ENTITY)
    assert state is not None

    calls_before: Final[int] = calls["count"]

    await hass.services.async_call(
        "button",
        "press",
        {"entity_id": BTN_ENTITY},
        blocking=True,
    )
    await hass.async_block_till_done()

    assert calls["count"] == calls_before + 1, (
        "Pressing the refresh button did not trigger a new BMS poll."
    )
