"""Platform for sensor integration."""

from typing import Final

from homeassistant.components.bluetooth import async_last_service_info
from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
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
from homeassistant.helpers.device_registry import DeviceInfo, format_mac
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import BTBmsConfigEntry
from .const import (
    ATTR_CELL_VOLTAGES,
    ATTR_CURRENT,
    ATTR_CYCLE_CAP,
    ATTR_CYCLES,
    ATTR_DELTA_VOLTAGE,
    ATTR_POWER,
    ATTR_RSSI,
    ATTR_RUNTIME,
    DOMAIN,
    KEY_CELL_VOLTAGE,
    LOGGER,
)
from .coordinator import BTBmsCoordinator

SENSOR_TYPES: Final[list[SensorEntityDescription]] = [
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
        key=ATTR_DELTA_VOLTAGE,
        translation_key=ATTR_DELTA_VOLTAGE,
        name="Delta voltage",
        icon="mdi:battery-sync",
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.VOLTAGE,
        entity_category=EntityCategory.DIAGNOSTIC,
        suggested_display_precision=3,
    ),
    SensorEntityDescription(
        key=ATTR_RSSI,
        translation_key=ATTR_RSSI,
        icon="mdi:bluetooth-connect",
        native_unit_of_measurement=SIGNAL_STRENGTH_DECIBELS_MILLIWATT,
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.SIGNAL_STRENGTH,
        entity_registry_enabled_default=False,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    SensorEntityDescription(
        key="link_qual",
        name="Link quality",
        icon="mdi:link",
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=False,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
]


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: BTBmsConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Add sensors for passed config_entry in Home Assistant."""

    bms: BTBmsCoordinator = config_entry.runtime_data
    mac: str = format_mac(config_entry.unique_id)
    for descr in SENSOR_TYPES:
        if descr.key == ATTR_RSSI:
            async_add_entities([RSSISensor(hass, descr, mac, bms.device_info)])
            continue
        async_add_entities([BMSSensor(bms, descr, mac)])


class BMSSensor(CoordinatorEntity[BTBmsCoordinator], SensorEntity):  # type: ignore[reportIncompatibleMethodOverride]
    """The generic BMS sensor implementation."""

    _attr_has_entity_name = True

    def __init__(
        self, bms: BTBmsCoordinator, descr: SensorEntityDescription, unique_id: str
    ) -> None:
        """Intitialize the BMS sensor."""
        self._attr_unique_id = f"{DOMAIN}-{unique_id}-{descr.key}"
        self._attr_device_info = bms.device_info
        self.entity_description = descr
        super().__init__(bms)

    @property
    def extra_state_attributes(self) -> dict[str, list[float]] | None:  # type: ignore[reportIncompatibleVariableOverride]
        """Return entity specific state attributes, e.g. cell voltages."""
        # TODO: add sorting?
        if self.entity_description.key == ATTR_DELTA_VOLTAGE:
            return {
                ATTR_CELL_VOLTAGES: [
                    v
                    for k, v in self.coordinator.data.items()
                    if k.startswith(KEY_CELL_VOLTAGE)
                ]
            }
        return None

    @property
    def native_value(self) -> int | float | None:  # type: ignore[reportIncompatibleVariableOverride]
        """Return the sensor value."""
        return self.coordinator.data.get(self.entity_description.key)


class RSSISensor(SensorEntity):  # type: ignore[reportIncompatibleVariableOverride]
    """The Bluetooth RSSI sensor."""

    _attr_has_entity_name = True
    _attr_native_value = -127

    def __init__(
        self,
        hass: HomeAssistant,
        descr: SensorEntityDescription,
        unique_id: str,
        device_info: DeviceInfo,
    ) -> None:
        """Intitialize the BMS sensor."""
        self._hass: Final = hass
        self._mac: Final = unique_id.upper()
        self._attr_unique_id = f"{DOMAIN}-{unique_id}-{descr.key}"
        self._attr_device_info = device_info
        self.entity_description = descr

    async def async_update(self) -> None:
        """Update RSSI sensor value."""
        self._attr_available = False

        if (
            service_info := async_last_service_info(
                self._hass, address=self._mac, connectable=True
            )
        ) is not None:
            self._attr_available = True
            self._attr_native_value = service_info.rssi

        LOGGER.debug(
            "%s: RSSI value: %i dBm, available: %s",
            self._mac,
            self._attr_native_value,
            self._attr_available,
        )
        self.async_write_ha_state()
