"""Support for BMS_BLE binary sensors."""

from collections.abc import Callable

from custom_components.bms_ble.plugins.basebms import BMSmode, BMSsample
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


class BmsBinaryEntityDescription(BinarySensorEntityDescription, frozen_or_thawed=True):
    """Describes BMS sensor entity."""

    attr_fn: Callable[[BMSsample], dict[str, int | str]] | None = None


BINARY_SENSOR_TYPES: list[BmsBinaryEntityDescription] = [
    BmsBinaryEntityDescription(
        key=ATTR_BATTERY_CHARGING,
        translation_key=ATTR_BATTERY_CHARGING,
        device_class=BinarySensorDeviceClass.BATTERY_CHARGING,
        attr_fn=lambda data: (
            {"battery_mode": data.get("battery_mode", BMSmode.UNKNOWN).name.lower()}
            if "battery_mode" in data
            else {}
        ),
    ),
    BmsBinaryEntityDescription(
        key=ATTR_PROBLEM,
        translation_key=ATTR_PROBLEM,
        device_class=BinarySensorDeviceClass.PROBLEM,
        entity_category=EntityCategory.DIAGNOSTIC,
        attr_fn=lambda data: (
            {"problem_code": data.get("problem_code", 0)}
            if "problem_code" in data
            else {}
        ),
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


class BMSBinarySensor(CoordinatorEntity[BTBmsCoordinator], BinarySensorEntity):
    """The generic BMS binary sensor implementation."""

    entity_description: BmsBinaryEntityDescription

    def __init__(
        self,
        bms: BTBmsCoordinator,
        descr: BmsBinaryEntityDescription,
        unique_id: str,
    ) -> None:
        """Intialize BMS binary sensor."""
        self._attr_unique_id = f"{DOMAIN}-{unique_id}-{descr.key}"
        self._attr_device_info = bms.device_info
        self._attr_has_entity_name = True
        self.entity_description: BmsBinaryEntityDescription = descr
        super().__init__(bms)

    @property
    def is_on(self) -> bool | None:
        """Handle updated data from the coordinator."""
        return bool(self.coordinator.data.get(self.entity_description.key))

    @property
    def extra_state_attributes(self) -> dict[str, int | str] | None:
        """Return entity specific state attributes, e.g. cell voltages."""
        return (
            fn(self.coordinator.data)
            if (fn := self.entity_description.attr_fn)
            else None
        )
