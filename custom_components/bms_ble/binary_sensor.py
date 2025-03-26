"""Support for BMS_BLE binary sensors."""

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.const import ATTR_BATTERY_CHARGING, EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import format_mac
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import BTBmsConfigEntry
from .const import ATTR_PROBLEM, DOMAIN
from .coordinator import BTBmsCoordinator

PARALLEL_UPDATES = 0

BINARY_SENSOR_TYPES: list[BinarySensorEntityDescription] = [
    BinarySensorEntityDescription(
        key=ATTR_BATTERY_CHARGING,
        translation_key=ATTR_BATTERY_CHARGING,
        device_class=BinarySensorDeviceClass.BATTERY_CHARGING,
    ),
    BinarySensorEntityDescription(
        key=ATTR_PROBLEM,
        translation_key=ATTR_PROBLEM,
        icon="mdi:battery-alert",
        device_class=BinarySensorDeviceClass.PROBLEM,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
]


async def async_setup_entry(
    _hass: HomeAssistant,
    config_entry: BTBmsConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Add sensors for passed config_entry in Home Assistant."""

    bms: BTBmsCoordinator = config_entry.runtime_data
    for descr in BINARY_SENSOR_TYPES:
        async_add_entities(
            [BMSBinarySensor(bms, descr, format_mac(config_entry.unique_id))]
        )


class BMSBinarySensor(CoordinatorEntity[BTBmsCoordinator], BinarySensorEntity):  # type: ignore[reportIncompatibleMethodOverride]
    """The generic BMS binary sensor implementation."""

    def __init__(
        self,
        bms: BTBmsCoordinator,
        descr: BinarySensorEntityDescription,
        unique_id: str,
    ) -> None:
        """Intialize BMS binary sensor."""
        self._attr_unique_id = f"{DOMAIN}-{unique_id}-{descr.key}"
        self._attr_device_info = bms.device_info
        self._attr_has_entity_name = True
        self.entity_description = descr
        super().__init__(bms)

    @property
    def is_on(self) -> bool | None:  # type: ignore[reportIncompatibleVariableOverride]
        """Handle updated data from the coordinator."""
        return bool(self.coordinator.data.get(self.entity_description.key))

    @property
    def extra_state_attributes(self) -> dict | None:  # type: ignore[reportIncompatibleVariableOverride]
        """Return entity specific state attributes, e.g. problem code."""
        # add problem code to sensor attributes
        # if self.entity_description.key == ATTR_PROBLEM:
        #    return {KEY_PROBLEM: self.coordinator.data.get(self.entity_description.key)}
        return None
