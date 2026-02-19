"""The BLE Battery Management System integration."""

from dataclasses import dataclass
from typing import Final

from homeassistant.components.bluetooth import async_ble_device_from_address
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryError, ConfigEntryNotReady
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.device_registry import format_mac
from homeassistant.helpers.importlib import async_import_module

from .config_flow import ConfigFlow
from .const import DOMAIN, LOGGER
from .coordinator import BTBmsCoordinator

PLATFORMS: list[Platform] = [Platform.BINARY_SENSOR, Platform.SENSOR]

type BTBmsConfigEntry = ConfigEntry[BTBmsCoordinator]


async def async_setup_entry(hass: HomeAssistant, entry: BTBmsConfigEntry) -> bool:
    """Set up BT Battery Management System from a config entry."""
    LOGGER.debug("Setup of %s", repr(entry))

    if entry.unique_id is None:
        raise ConfigEntryError(
            translation_domain=DOMAIN,
            translation_key="missing_unique_id",
        )

    # migrate old entries
    migrate_sensor_entities(hass, entry)

    ble_device = async_ble_device_from_address(hass, entry.unique_id, True)

    if ble_device is None:
        LOGGER.debug("Failed to discover device %s via Bluetooth", entry.unique_id)
        raise ConfigEntryNotReady(
            translation_domain=DOMAIN,
            translation_key="device_not_found",
            translation_placeholders={
                "mac": entry.unique_id,
            },
        )

    plugin = await async_import_module(hass, entry.data["type"])
    coordinator = BTBmsCoordinator(hass, ble_device, plugin.BMS(ble_device), entry)

    # Query the device the first time, initialise coordinator.data
    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: BTBmsConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok: Final = await hass.config_entries.async_unload_platforms(
        entry, PLATFORMS
    )
    LOGGER.debug("Unloaded config entry: %s, ok? %s!", entry.unique_id, str(unload_ok))

    if unload_ok and getattr(entry, "runtime_data", None) is not None:
        await entry.runtime_data.async_shutdown()

    return unload_ok


async def async_migrate_entry(
    hass: HomeAssistant, config_entry: BTBmsConfigEntry
) -> bool:
    """Migrate old entry."""

    @dataclass(repr=False, eq=False, slots=True)
    class EntryVersion:
        major: int
        minor: int

    if config_entry.version > ConfigFlow.VERSION:
        # This means the user has downgraded from a future major version (incompatible)
        LOGGER.debug("Cannot downgrade from version %s", config_entry.version)
        return False

    LOGGER.debug(
        "Migrating from version %s.%s", config_entry.version, config_entry.minor_version
    )

    bms_type: Final[str] = str(config_entry.data["type"])
    new_data: dict[str, str] = config_entry.data.copy()
    entry_version: EntryVersion = EntryVersion(
        config_entry.version,
        config_entry.minor_version,
    )

    if entry_version.major == 0:
        if bms_type == "OGTBms":
            new_data["type"] = "custom_components.bms_ble.plugins.ogt_bms"
        elif bms_type == "DalyBms":
            new_data["type"] = "custom_components.bms_ble.plugins.daly_bms"
        else:
            LOGGER.debug("Entry: %s", config_entry.data)
            LOGGER.error(
                "Migration from version %s.%s failed",
                config_entry.version,
                config_entry.minor_version,
            )
            return False
        entry_version = EntryVersion(1, 0)

    if entry_version.major < 2:
        new_data["type"] = f"aiobmsble.bms.{new_data["type"].rsplit('.', 1)[-1]}"
        entry_version = EntryVersion(2, 0)

    if config_entry.version < 3:
        # rename Ective BMS to Topband BMS
        if bms_type.endswith("ective_bms"):
            new_data["type"] = "aiobmsble.bms.topband_bms"
        entry_version = EntryVersion(3, 0)

    hass.config_entries.async_update_entry(
        config_entry,
        data=new_data,
        minor_version=entry_version.minor,
        version=entry_version.major,
    )

    LOGGER.debug(
        "Migration to version %s.%s successful",
        config_entry.version,
        config_entry.minor_version,
    )

    return True


def migrate_sensor_entities(
    hass: HomeAssistant,
    config_entry: BTBmsConfigEntry,
) -> None:
    """Migrate old unique_ids with wrong format (name) to new format (MAC address) if needed."""
    ent_reg: Final[er.EntityRegistry] = er.async_get(hass)
    entities: Final[er.EntityRegistryItems] = ent_reg.entities

    for entry in entities.get_entries_for_config_entry_id(config_entry.entry_id):
        unique_id: str = entry.unique_id
        # update entries from wrong old format using no domain prefix
        if not entry.unique_id.startswith(f"{DOMAIN}-"):
            unique_id = f"{DOMAIN}-{format_mac(config_entry.unique_id)}-{unique_id.split('-')[-1]}"
        # rename delta_voltage sensor to be consistent with min/max cell voltage sensor
        if unique_id.endswith("-delta_voltage"):
            unique_id = unique_id.removesuffix("-delta_voltage") + "-delta_cell_voltage"

        if unique_id == entry.unique_id:
            continue

        LOGGER.debug(
            "migrating %s with old unique_id '%s' to new '%s'",
            entry.entity_id,
            entry.unique_id,
            unique_id,
        )
        ent_reg.async_update_entity(entry.entity_id, new_unique_id=unique_id)
