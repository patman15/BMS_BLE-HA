"""Support for BMS_BLE binary sensors."""

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_BATTERY_CHARGING
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import format_mac
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, LOGGER
from .coordinator import BTBmsCoordinator

BINARY_SENSOR_TYPES: list[BinarySensorEntityDescription] = [
    BinarySensorEntityDescription(
        key=ATTR_BATTERY_CHARGING,
        translation_key=ATTR_BATTERY_CHARGING,
        device_class=BinarySensorDeviceClass.BATTERY_CHARGING,
    )
]


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Add sensors for passed config_entry in home assistant"""

    bms: BTBmsCoordinator = hass.data[DOMAIN][config_entry.entry_id]
    for descr in BINARY_SENSOR_TYPES:
        async_add_entities([BMSBinarySensor(bms, descr)])


class BMSBinarySensor(CoordinatorEntity[BTBmsCoordinator], BinarySensorEntity):  # type: ignore
    """Generic BMS binary sensor implementation"""

    def __init__(
        self, bms: BTBmsCoordinator, descr: BinarySensorEntityDescription
    ) -> None:
        self._bms: BTBmsCoordinator = bms
        self._attr_unique_id = f"{format_mac(self._bms.name)}-{descr.key}"
        self._attr_device_info = bms.device_info
        self._attr_has_entity_name = True
        self.entity_description = descr
        super().__init__(self._bms)

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""

        if self._bms.data is None:
            return

        if self.entity_description.key in self._bms.data:
            self._attr_is_on = bool(self._bms.data.get(self.entity_description.key))
            self._attr_available = True
        elif self._attr_available:
            self._attr_available = False
            LOGGER.info(f"No update available for {self.entity_description.key}.")

        self.async_write_ha_state()
