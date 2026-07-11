"""Support for BMS_BLE buttons."""

from typing import Final, override

from homeassistant.components.button import ButtonEntity
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import format_mac
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import BTBmsConfigEntry
from .const import DOMAIN
from .coordinator import BTBmsCoordinator

PARALLEL_UPDATES = 0


async def async_setup_entry(
    _hass: HomeAssistant,
    config_entry: BTBmsConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Add buttons for passed config_entry in Home Assistant."""

    bms: BTBmsCoordinator = config_entry.runtime_data
    async_add_entities([BMSRefreshButton(bms, format_mac(config_entry.unique_id))])


class BMSRefreshButton(ButtonEntity):
    """Button to request an immediate BMS data refresh."""

    _attr_has_entity_name = True
    _attr_entity_category = EntityCategory.CONFIG
    _attr_translation_key = "refresh"

    def __init__(self, bms: BTBmsCoordinator, unique_id: str) -> None:
        """Initialize the BMS refresh button."""
        self._attr_unique_id = f"{DOMAIN}-{unique_id}-refresh"
        self._attr_device_info = bms.device_info
        self._bms: Final = bms

    @override
    async def async_press(self) -> None:
        """Request an immediate refresh of the BMS data."""
        await self._bms.async_request_refresh()
