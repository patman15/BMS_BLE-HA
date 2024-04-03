"""The BLE Battery Management System integration."""

from homeassistant.components.bluetooth import async_ble_device_from_address
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady

from .const import DOMAIN, LOGGER
from .coordinator import BTBmsCoordinator

PLATFORMS: list[Platform] = [Platform.SENSOR, Platform.BINARY_SENSOR]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up BT Battery Management System from a config entry."""
    LOGGER.debug(f"Setup of {repr(entry)}")

    if entry.unique_id is None:
        raise ConfigEntryNotReady(f"Missing unique ID for device.")

    ble_device = async_ble_device_from_address(
        hass=hass, address=entry.unique_id, connectable=True
    )

    if not ble_device:
        raise ConfigEntryNotReady(
            f"Could not find battery with address {entry.unique_id}"
        )

    coordinator = BTBmsCoordinator(hass, ble_device, type=entry.data["type"])

    # Query the device the first time, initialise coordinator.data
    try:
        # Insert the coordinator in the global registry
        hass.data.setdefault(DOMAIN, {})
        hass.data[DOMAIN][entry.entry_id] = coordinator
        await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
        return True
    except:
        del coordinator
        return False


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        await hass.data[DOMAIN][entry.entry_id].stop()
        hass.data[DOMAIN].pop(entry.entry_id)

    LOGGER.info(f"unloaded entry: {entry.unique_id}, ok? {unload_ok}!")
    return unload_ok
