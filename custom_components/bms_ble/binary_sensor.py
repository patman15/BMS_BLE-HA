"""Support for BMS_BLE binary sensors."""

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.const import ATTR_BATTERY_CHARGING
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import format_mac
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import BTBmsConfigEntry
from .const import DOMAIN
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
    config_entry: BTBmsConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Add sensors for passed config_entry in Home Assistant."""

    bms: BTBmsCoordinator = config_entry.runtime_data
    for descr in BINARY_SENSOR_TYPES:
        async_add_entities([BMSBinarySensor(bms, descr)])


class BMSBinarySensor(CoordinatorEntity[BTBmsCoordinator], BinarySensorEntity):  # type: ignore[reportIncompatibleMethodOverride]
    """The generic BMS binary sensor implementation."""

    def __init__(
        self, bms: BTBmsCoordinator, descr: BinarySensorEntityDescription
    ) -> None:
        """Intialize BMS binary sensor."""
        self._attr_unique_id = f"{format_mac(bms.name)}-{descr.key}"
        self._attr_device_info = bms.device_info
        self._attr_has_entity_name = True
        self.entity_description = descr
        super().__init__(bms)

    @property
    def is_on(self) -> bool | None:  # type: ignore[reportIncompatibleVariableOverride]
        """Handle updated data from the coordinator."""
        return bool(self.coordinator.data.get(self.entity_description.key))
