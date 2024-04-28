"""The BLE Battery Management System integration."""

import importlib

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
    LOGGER.debug("Setup of %s", repr(entry))

    if entry.unique_id is None:
        raise ConfigEntryNotReady("Missing unique ID for device.")

    ble_device = async_ble_device_from_address(
        hass=hass, address=entry.unique_id, connectable=True
    )

    if not ble_device:
        raise ConfigEntryNotReady(
            f"Could not find battery with address {entry.unique_id}"
        )

    plugin = importlib.import_module(entry.data["type"])
    coordinator = BTBmsCoordinator(hass, ble_device, bms_device=plugin.BMS(ble_device))
    # Query the device the first time, initialise coordinator.data
    try:
        await coordinator.async_config_entry_first_refresh()
    except ConfigEntryNotReady:
        # Ignore, e.g. timeouts, to gracefully handle connection issues
        LOGGER.warning("Failed to initialize BMS %s, continuing", ble_device.name)

    # Insert the coordinator in the global registry
    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        await hass.data[DOMAIN][entry.entry_id].stop()
        hass.data[DOMAIN].pop(entry.entry_id)

    LOGGER.info("Unloaded config entry: %s, ok? %s!", entry.unique_id, str(unload_ok))
    return unload_ok

async def async_migrate_entry(hass: HomeAssistant, config_entry: ConfigEntry) -> bool:
    """Migrate old entry."""
    LOGGER.debug("Migrating from version %s", config_entry.version)

    if config_entry.version > 1:
      # This means the user has downgraded from a future version
      return False

    if config_entry.version == 0:
        bms_type = config_entry.data["type"]
        if bms_type == "OGTBms":
            new = {"type": "homeassistant.components.bms_ble.plugins.ogt_bms" }
        elif bms_type == "DalyBms":
            new = {"type": "homeassistant.components.bms_ble.plugins.daly_bms"}
        else:
            LOGGER.debug("Entry: %s", config_entry.data)
            LOGGER.error("Migration from version %s.%s failed", config_entry.version, config_entry.minor_version)
            return False

        hass.config_entries.async_update_entry(config_entry, data=new, minor_version=0, version=1)
        LOGGER.debug("Migration to version %s.%s successful", config_entry.version, config_entry.minor_version)

    return True

