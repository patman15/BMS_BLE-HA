"""Platform for sensor integration."""

from typing import Final

from homeassistant.components.sensor import SensorEntity, SensorEntityDescription
from homeassistant.components.sensor.const import SensorDeviceClass, SensorStateClass
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

from . import BTBmsConfigEntry
from .const import (
    ATTR_BALANCE_CUR,
    ATTR_CELL_VOLTAGES,
    ATTR_CURRENT,
    ATTR_CYCLE_CAP,
    ATTR_CYCLES,
    ATTR_DELTA_VOLTAGE,
    ATTR_LQ,
    ATTR_POWER,
    ATTR_RSSI,
    ATTR_RUNTIME,
    ATTR_TEMP_SENSORS,
    DOMAIN,
    KEY_CELL_VOLTAGE,
    KEY_PACK,
    KEY_PACK_COUNT,
    KEY_TEMP_VALUE,
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
        icon="mdi:current-dc",
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
        icon="mdi:autorenew",
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
        native_unit_of_measurement=UnitOfTime.HOURS,
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
        key=ATTR_LQ,
        translation_key=ATTR_LQ,
        name="Link quality",
        icon="mdi:link",
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=False,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
]


async def async_setup_entry(
    _hass: HomeAssistant,
    config_entry: BTBmsConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Add sensors for passed config_entry in Home Assistant."""

    bms: Final[BTBmsCoordinator] = config_entry.runtime_data
    mac: Final[str] = format_mac(config_entry.unique_id)
    for descr in SENSOR_TYPES:
        if descr.key == ATTR_RSSI:
            async_add_entities([RSSISensor(bms, descr, mac)])
            continue
        if descr.key == ATTR_LQ:
            async_add_entities([LQSensor(bms, descr, mac)])
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

    def _get_attr_list(self, key_prefix: str) -> list[float]:
        return [v for k, v in self.coordinator.data.items() if k.startswith(key_prefix)]

    @property
    def extra_state_attributes(self) -> dict[str, list[float]] | None:  # type: ignore[reportIncompatibleVariableOverride]
        """Return entity specific state attributes, e.g. cell voltages."""
        sensor_key: Final[str] = self.entity_description.key
        # add cell voltages to delta voltage sensor
        if sensor_key == ATTR_DELTA_VOLTAGE:
            return {ATTR_CELL_VOLTAGES: self._get_attr_list(KEY_CELL_VOLTAGE)}
        # add individual temperature values to temperature sensor
        if sensor_key == ATTR_TEMPERATURE:
            temp_sensors: Final = self._get_attr_list(KEY_TEMP_VALUE)
            if temp_sensors:
                return {ATTR_TEMP_SENSORS: temp_sensors}
            if temp := self.coordinator.data.get(ATTR_TEMPERATURE):
                return {ATTR_TEMP_SENSORS: [temp]}

        result: dict[str, list[float]] = {}
        # add balance current as attribute to current sensor
        if sensor_key == ATTR_CURRENT:
            if ATTR_BALANCE_CUR in self.coordinator.data:
                result[ATTR_BALANCE_CUR] = [self.coordinator.data[ATTR_BALANCE_CUR]]
        # add per-pack values as attributes to corresponding sensor
        if self.coordinator.data.get(KEY_PACK_COUNT, 0) and sensor_key in [
            ATTR_CURRENT,
            ATTR_VOLTAGE,
            ATTR_CYCLES,
            ATTR_BATTERY_LEVEL,
        ]:
            result[f"{KEY_PACK}_{sensor_key}"] = self._get_attr_list(
                f"{KEY_PACK}_{sensor_key}"
            )

        return result

    @property
    def native_value(self) -> int | float | None:  # type: ignore[reportIncompatibleVariableOverride]
        """Return the sensor value."""
        return self.coordinator.data.get(self.entity_description.key)


class RSSISensor(SensorEntity):  # type: ignore[reportIncompatibleVariableOverride]
    """The Bluetooth RSSI sensor."""

    LIMIT: Final[int] = 127  # limit to +/- this range
    _attr_has_entity_name = True
    _attr_native_value = -LIMIT

    def __init__(
        self, bms: BTBmsCoordinator, descr: SensorEntityDescription, unique_id: str
    ) -> None:
        """Intitialize the BMS sensor."""

        self._attr_unique_id = f"{DOMAIN}-{unique_id}-{descr.key}"
        self._attr_device_info = bms.device_info
        self.entity_description = descr
        self._bms: Final[BTBmsCoordinator] = bms

    async def async_update(self) -> None:
        """Update RSSI sensor value."""

        self._attr_native_value = max(
            min(self._bms.rssi or -self.LIMIT, self.LIMIT), -self.LIMIT
        )
        self._attr_available = self._bms.rssi is not None

        LOGGER.debug("%s: RSSI value: %i dBm", self._bms.name, self._attr_native_value)
        self.async_write_ha_state()


class LQSensor(SensorEntity):  # type: ignore[reportIncompatibleVariableOverride]
    """The BMS link quality sensor."""

    _attr_has_entity_name = True
    _attr_available = True  # always available
    _attr_native_value = 0

    def __init__(
        self, bms: BTBmsCoordinator, descr: SensorEntityDescription, unique_id: str
    ) -> None:
        """Intitialize the BMS link quality sensor."""

        self._attr_unique_id = f"{DOMAIN}-{unique_id}-{descr.key}"
        self._attr_device_info = bms.device_info
        self.entity_description = descr
        self._bms: Final[BTBmsCoordinator] = bms

    async def async_update(self) -> None:
        """Update BMS link quality sensor value."""

        self._attr_native_value = self._bms.link_quality

        LOGGER.debug("%s: Link quality: %i %%", self._bms.name, self._attr_native_value)
        self.async_write_ha_state()
