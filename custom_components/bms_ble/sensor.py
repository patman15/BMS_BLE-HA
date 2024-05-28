"""Platform for sensor integration."""

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    ATTR_BATTERY_LEVEL,
    ATTR_TEMPERATURE,
    ATTR_VOLTAGE,
    PERCENTAGE,
    SIGNAL_STRENGTH_DECIBELS_MILLIWATT,
    EntityCategory,
    UnitOfElectricCurrent,
    UnitOfElectricPotential,
    UnitOfEnergy,
    UnitOfPower,
    UnitOfTemperature,
    UnitOfTime,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import format_mac
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
    ATTR_CURRENT,
    ATTR_CYCLE_CAP,
    ATTR_CYCLES,
    ATTR_POWER,
    ATTR_RSSI,
    ATTR_RUNTIME,
    DOMAIN,
)
from .coordinator import BTBmsCoordinator

SENSOR_TYPES: list[SensorEntityDescription] = [
    SensorEntityDescription(
        key=ATTR_VOLTAGE,
        translation_key=ATTR_VOLTAGE,
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.VOLTAGE,
        suggested_display_precision=1,
    ),
    SensorEntityDescription(
        key=ATTR_BATTERY_LEVEL,
        translation_key=ATTR_BATTERY_LEVEL,
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.BATTERY,
    ),
    SensorEntityDescription(
        key=ATTR_TEMPERATURE,
        translation_key=ATTR_TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.TEMPERATURE,
        suggested_display_precision=1,
    ),
    SensorEntityDescription(
        key=ATTR_CURRENT,
        translation_key=ATTR_CURRENT,
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.CURRENT,
    ),
    SensorEntityDescription(
        key=ATTR_CYCLE_CAP,
        translation_key=ATTR_CYCLE_CAP,
        native_unit_of_measurement=UnitOfEnergy.WATT_HOUR,
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.ENERGY_STORAGE,
        suggested_display_precision=1,
    ),
    SensorEntityDescription(
        key=ATTR_CYCLES,
        translation_key=ATTR_CYCLES,
        name="Cycles",
        state_class=SensorStateClass.TOTAL_INCREASING,
    ),
    SensorEntityDescription(
        key=ATTR_POWER,
        translation_key=ATTR_POWER,
        native_unit_of_measurement=UnitOfPower.WATT,
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.POWER,
        suggested_display_precision=1,
    ),
    SensorEntityDescription(
        key=ATTR_RUNTIME,
        translation_key=ATTR_RUNTIME,
        name="Runtime",
        native_unit_of_measurement=UnitOfTime.SECONDS,
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.DURATION,
    ),
    SensorEntityDescription(
        key=ATTR_RSSI,
        translation_key=ATTR_RSSI,
        native_unit_of_measurement=SIGNAL_STRENGTH_DECIBELS_MILLIWATT,
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.SIGNAL_STRENGTH,
        entity_registry_enabled_default=False,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
]


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Add sensors for passed config_entry in Home Assistant."""

    bms: BTBmsCoordinator = hass.data[DOMAIN][config_entry.entry_id]
    for descr in SENSOR_TYPES:
        async_add_entities([BMSSensor(bms, descr)])


class BMSSensor(CoordinatorEntity[BTBmsCoordinator], SensorEntity):  # type: ignore[reportIncompatibleMethodOverride]
    """The generic BMS sensor implementation."""

    _attr_has_entity_name = True

    def __init__(self, bms: BTBmsCoordinator, descr: SensorEntityDescription) -> None:
        """Intitialize the BMS sensor."""
        self._attr_unique_id = f"{format_mac(bms.name)}-{descr.key}"
        self._attr_device_info = bms.device_info
        self.entity_description = descr
        super().__init__(bms)

    @property
    def native_value(self) -> int | float | None:  # type: ignore[reportIncompatibleVariableOverride]
        """Return the sensor value."""
        return self.coordinator.data.get(self.entity_description.key)
