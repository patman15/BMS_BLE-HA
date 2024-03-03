"""The BT Battery Management System integration."""

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.components.bluetooth import async_ble_device_from_address
from asyncio import CancelledError

from .const import DOMAIN
from .btbms import BTBms

import logging

PLATFORMS: list[Platform] = [Platform.SENSOR]

_LOGGER = logging.getLogger(__name__)

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up BT Battery Management System from a config entry."""
    _LOGGER.debug("Setup of %s", repr(entry))

    ble_device = async_ble_device_from_address(hass=hass, address=entry.unique_id, connectable=True)

    if not ble_device:
        raise ConfigEntryNotReady(
            f"Could not find battery with address {entry.unique_id}"
        )    
    
    if ble_device.name[9] not in "AB":
        _LOGGER.error(f"Unknonw device type: {ble_device.name[9]}")
        return False

    coordinator = BTBms(hass, _LOGGER, ble_device)
    
    # Query the device the first time, initialise coordinator.data
    try:
        await coordinator.async_config_entry_first_refresh()
        # Insert the coordinator in the global registry
        hass.data.setdefault(DOMAIN, {})
        hass.data[DOMAIN][entry.entry_id] = coordinator
        await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
        return True
    except CancelledError:
        return False


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        hass.data[DOMAIN].pop(entry.entry_id)

    _LOGGER.info(f"unloaded entry: {entry.unique_id}, ok? {unload_ok}!")
    return unload_ok

