"""The BLE Battery Management System integration."""

import logging
from asyncio import CancelledError

from homeassistant.components.bluetooth import async_ble_device_from_address
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady

from .const import DOMAIN
from .coordinator import BTBmsCoordinator

PLATFORMS: list[Platform] = [Platform.SENSOR]

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up BT Battery Management System from a config entry."""
    _LOGGER.debug("Setup of %s", repr(entry))

    if entry.unique_id is None:
        raise ConfigEntryNotReady(f"Missing unique ID for device.")

    ble_device = async_ble_device_from_address(
        hass=hass, address=entry.unique_id, connectable=True
    )

    if not ble_device:
        raise ConfigEntryNotReady(
            f"Could not find battery with address {entry.unique_id}"
        )

    coordinator = BTBmsCoordinator(hass, _LOGGER, ble_device, type=entry.data["type"])

    # Query the device the first time, initialise coordinator.data
    try:
        entry.async_create_background_task(
            hass=hass,
            target=coordinator.async_config_entry_first_refresh(),
            name="initialize",
        )
        # Insert the coordinator in the global registry
        hass.data.setdefault(DOMAIN, {})
        hass.data[DOMAIN][entry.entry_id] = coordinator
        await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
        return True
    except CancelledError:
        del coordinator
        return False


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        hass.data[DOMAIN].pop(entry.entry_id)

    _LOGGER.info(f"unloaded entry: {entry.unique_id}, ok? {unload_ok}!")
    return unload_ok
