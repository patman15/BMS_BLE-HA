"""Platform for sensor integration."""

from collections.abc import Callable
from typing import Final, cast

from aiobmsble import BMSpackvalue, BMSSample

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
    ATTR_CURRENT,
    ATTR_CYCLE_CAP,
    ATTR_CYCLES,
    ATTR_DELTA_VOLTAGE,
    ATTR_LQ,
    ATTR_MAX_VOLTAGE,
    ATTR_MIN_VOLTAGE,
    ATTR_POWER,
    ATTR_RSSI,
    ATTR_RUNTIME,
    DOMAIN,
    LOGGER,
)
from .coordinator import BTBmsCoordinator

PARALLEL_UPDATES = 0


class BmsEntityDescription(SensorEntityDescription, frozen_or_thawed=True):
    """Describes BMS sensor entity."""

    value_fn: Callable[[BMSSample], float | int | None]
    attr_fn: Callable[[BMSSample], dict[str, list[int | float]]] | None = None


def _attr_pack(
    data: BMSSample, key: BMSpackvalue, default: list[int | float]
) -> dict[str, list[int | float]]:
    """Return a dictionary with the given key and default value."""
    return (
        {str(key): cast("list[int | float]", data.get(key, default))}
        if key in data
        else {}
    )


SENSOR_TYPES: Final[list[BmsEntityDescription]] = [
    BmsEntityDescription(
        key=ATTR_VOLTAGE,
        translation_key=ATTR_VOLTAGE,
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.VOLTAGE,
        suggested_display_precision=1,
        value_fn=lambda data: data.get("voltage"),
        attr_fn=lambda data: _attr_pack(data, "pack_voltages", [0.0]),
    ),
    BmsEntityDescription(
        key=ATTR_BATTERY_LEVEL,
        translation_key=ATTR_BATTERY_LEVEL,
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.BATTERY,
        value_fn=lambda data: data.get("battery_level"),
        attr_fn=lambda data: _attr_pack(data, "pack_battery_levels", [0.0]),
    ),
    BmsEntityDescription(
        key=ATTR_TEMPERATURE,
        translation_key=ATTR_TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.TEMPERATURE,
        suggested_display_precision=1,
        value_fn=lambda data: data.get("temperature"),
        attr_fn=lambda data: (
            {"temperature_sensors": data.get("temp_values", [])}
            if "temp_values" in data
            else (
                {"temperature_sensors": [data.get("temperature", 0.0)]}
                if "temperature" in data
                else {}
            )
        ),
    ),
    BmsEntityDescription(
        key=ATTR_CURRENT,
        translation_key=ATTR_CURRENT,
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.CURRENT,
        value_fn=lambda data: data.get("current"),
        attr_fn=lambda data: (
            {"balance_current": [data.get("balance_current", 0.0)]}
            if "balance_current" in data
            else {}
        )
        | _attr_pack(data, "pack_currents", [0.0]),
    ),
    BmsEntityDescription(
        key=ATTR_CYCLE_CAP,
        translation_key=ATTR_CYCLE_CAP,
        native_unit_of_measurement=UnitOfEnergy.WATT_HOUR,
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.ENERGY_STORAGE,
        suggested_display_precision=1,
        value_fn=lambda data: data.get("cycle_capacity"),
    ),
    BmsEntityDescription(
        key=ATTR_CYCLES,
        translation_key=ATTR_CYCLES,
        name="Cycles",
        state_class=SensorStateClass.TOTAL_INCREASING,
        value_fn=lambda data: data.get("cycles"),
        attr_fn=lambda data: _attr_pack(data, "pack_cycles", [0]),
    ),
    BmsEntityDescription(
        key=ATTR_POWER,
        translation_key=ATTR_POWER,
        native_unit_of_measurement=UnitOfPower.WATT,
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.POWER,
        suggested_display_precision=1,
        value_fn=lambda data: data.get("power"),
    ),
    BmsEntityDescription(
        key=ATTR_RUNTIME,
        translation_key=ATTR_RUNTIME,
        name="Runtime",
        native_unit_of_measurement=UnitOfTime.SECONDS,
        suggested_unit_of_measurement=UnitOfTime.HOURS,
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.DURATION,
        value_fn=lambda data: data.get("runtime"),
    ),
    BmsEntityDescription(
        key=ATTR_DELTA_VOLTAGE,
        translation_key=ATTR_DELTA_VOLTAGE,
        name="Delta cell voltage",
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.VOLTAGE,
        entity_category=EntityCategory.DIAGNOSTIC,
        suggested_display_precision=3,
        value_fn=lambda data: data.get("delta_voltage"),
        attr_fn=lambda data: (
            {"cell_voltages": data.get("cell_voltages", [])}
            if "cell_voltages" in data
            else {}
        ),
    ),
    BmsEntityDescription(
        key=ATTR_MAX_VOLTAGE,
        translation_key=ATTR_MAX_VOLTAGE,
        name="Maximal cell voltage",
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.VOLTAGE,
        entity_registry_enabled_default=False,
        entity_category=EntityCategory.DIAGNOSTIC,
        suggested_display_precision=3,
        value_fn=lambda data: (
            max(cells) if (cells := data.get("cell_voltages", [])) else None
        ),
        attr_fn=lambda data: (
            {"cell_number": [cells.index(max(cells))]}
            if (cells := data.get("cell_voltages", []))
            else {}
        ),
    ),
    BmsEntityDescription(
        key=ATTR_MIN_VOLTAGE,
        translation_key=ATTR_MIN_VOLTAGE,
        name="Minimal cell voltage",
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.VOLTAGE,
        entity_registry_enabled_default=False,
        entity_category=EntityCategory.DIAGNOSTIC,
        suggested_display_precision=3,
        value_fn=lambda data: (
            min(cells) if (cells := data.get("cell_voltages", [])) else None
        ),
        attr_fn=lambda data: (
            {"cell_number": [cells.index(min(cells))]}
            if (cells := data.get("cell_voltages", []))
            else {}
        ),
    ),
    BmsEntityDescription(
        key=ATTR_RSSI,
        translation_key=ATTR_RSSI,
        native_unit_of_measurement=SIGNAL_STRENGTH_DECIBELS_MILLIWATT,
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.SIGNAL_STRENGTH,
        entity_registry_enabled_default=False,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda data: None,  # RSSI is handled in a separate class
    ),
    BmsEntityDescription(
        key=ATTR_LQ,
        translation_key=ATTR_LQ,
        name="Link quality",
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=False,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda data: None,  # LQ is handled in a separate class
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


class BMSSensor(CoordinatorEntity[BTBmsCoordinator], SensorEntity):
    """The generic BMS sensor implementation."""

    _attr_has_entity_name = True
    entity_description: BmsEntityDescription

    def __init__(
        self, bms: BTBmsCoordinator, descr: BmsEntityDescription, unique_id: str
    ) -> None:
        """Intitialize the BMS sensor."""
        self._attr_unique_id = f"{DOMAIN}-{unique_id}-{descr.key}"
        self._attr_device_info = bms.device_info
        self.entity_description = descr
        super().__init__(bms)

    @property
    def extra_state_attributes(self) -> dict[str, list[int | float]] | None:
        """Return entity specific state attributes, e.g. cell voltages."""
        if self.entity_description.attr_fn:
            return self.entity_description.attr_fn(self.coordinator.data)

        return None

    @property
    def native_value(self) -> int | float | None:
        """Return the sensor value."""
        return self.entity_description.value_fn(self.coordinator.data)


class RSSISensor(SensorEntity):
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


class LQSensor(SensorEntity):
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
