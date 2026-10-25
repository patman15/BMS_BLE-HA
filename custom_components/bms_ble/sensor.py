"""Platform for sensor integration."""

from collections.abc import Callable
from dataclasses import replace
from functools import cached_property
from statistics import fmean
from typing import Final, override

from aiobmsble import BMSSample, PackSample, TempSensor as TS

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
    MATCH_ALL,
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
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.device_registry import ChildDeviceInfo, format_mac
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import BTBmsConfigEntry
from .const import (
    ATTR_BALANCE_CUR,
    ATTR_BATTERY_HEALTH,
    ATTR_CELL_NUMBER,
    ATTR_CELL_VOLTAGES,
    ATTR_CURRENT,
    ATTR_CYCLE_CAP,
    ATTR_CYCLES,
    ATTR_DELTA_VOLTAGE,
    ATTR_DESIGN_CAP,
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

    attr_fn: Callable[[BMSSample | PackSample], dict[str, list[int | float]] | None] = (
        lambda data: None
    )
    optional: bool = False
    value_fn: Callable[[BMSSample | PackSample], float | int | None]


SENSOR_TYPES: Final[list[BmsEntityDescription]] = [
    BmsEntityDescription(
        device_class=SensorDeviceClass.VOLTAGE,
        key=ATTR_VOLTAGE,
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
        value_fn=lambda data: data.get("voltage"),
    ),
    BmsEntityDescription(
        device_class=SensorDeviceClass.BATTERY,
        key=ATTR_BATTERY_LEVEL,
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data: data.get("battery_level"),
    ),
    BmsEntityDescription(
        key=ATTR_BATTERY_HEALTH,
        native_unit_of_measurement=PERCENTAGE,
        optional=True,
        state_class=SensorStateClass.MEASUREMENT,
        translation_key=ATTR_BATTERY_HEALTH,
        value_fn=lambda data: data.get("battery_health"),
    ),
    BmsEntityDescription(
        device_class=SensorDeviceClass.TEMPERATURE,
        key=ATTR_TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
        value_fn=lambda data: (
            fmean(s.value for s in ([t for t in temps if t.type == TS.T.CELL] or temps))
            if (temps := data.get("temperature"))
            else None
        ),
    ),
    BmsEntityDescription(
        attr_fn=lambda data: (
            (
                {ATTR_BALANCE_CUR: [data.get("balance_current", 0.0)]}
                if "balance_current" in data
                else {}
            )
            | (
                {"heater_current": [data.get("heater_current", 0.0)]}
                if "heater_current" in data
                else {}
            )
        ),
        device_class=SensorDeviceClass.CURRENT,
        key=ATTR_CURRENT,
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        state_class=SensorStateClass.MEASUREMENT,
        translation_key=ATTR_CURRENT,
        value_fn=lambda data: data.get("current"),
    ),
    BmsEntityDescription(
        device_class=SensorDeviceClass.ENERGY_STORAGE,
        key=ATTR_CYCLE_CAP,
        native_unit_of_measurement=UnitOfEnergy.WATT_HOUR,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
        value_fn=lambda data: data.get("cycle_capacity"),
    ),
    BmsEntityDescription(
        key=ATTR_CYCLES,
        state_class=SensorStateClass.TOTAL_INCREASING,
        translation_key=ATTR_CYCLES,
        value_fn=lambda data: data.get("cycles"),
    ),
    BmsEntityDescription(
        entity_category=EntityCategory.DIAGNOSTIC,
        key=ATTR_DESIGN_CAP,
        native_unit_of_measurement="Ah",
        optional=True,
        translation_key=ATTR_DESIGN_CAP,
        value_fn=lambda data: data.get("design_capacity"),
    ),
    BmsEntityDescription(
        device_class=SensorDeviceClass.POWER,
        key=ATTR_POWER,
        native_unit_of_measurement=UnitOfPower.WATT,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
        value_fn=lambda data: data.get("power"),
    ),
    BmsEntityDescription(
        device_class=SensorDeviceClass.DURATION,
        key=ATTR_RUNTIME,
        native_unit_of_measurement=UnitOfTime.SECONDS,
        suggested_unit_of_measurement=UnitOfTime.HOURS,
        state_class=SensorStateClass.MEASUREMENT,
        translation_key=ATTR_RUNTIME,
        value_fn=lambda data: data.get("runtime"),
    ),
    BmsEntityDescription(
        attr_fn=lambda data: (
            {ATTR_CELL_VOLTAGES: data.get("cell_voltages", [])}
            if ATTR_CELL_VOLTAGES in data
            else {}
        ),
        device_class=SensorDeviceClass.VOLTAGE,
        entity_category=EntityCategory.DIAGNOSTIC,
        key=ATTR_DELTA_VOLTAGE,
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=3,
        translation_key=ATTR_DELTA_VOLTAGE,
        value_fn=lambda data: data.get("delta_cell_voltage"),
    ),
    BmsEntityDescription(
        attr_fn=lambda data: (
            {ATTR_CELL_NUMBER: [cells.index(max(cells)) + 1]}
            if (cells := data.get("cell_voltages", []))
            else {}
        ),
        device_class=SensorDeviceClass.VOLTAGE,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        key=ATTR_MAX_VOLTAGE,
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=3,
        translation_key=ATTR_MAX_VOLTAGE,
        value_fn=lambda data: (
            max(cells) if (cells := data.get("cell_voltages", [])) else None
        ),
    ),
    BmsEntityDescription(
        attr_fn=lambda data: (
            {ATTR_CELL_NUMBER: [cells.index(min(cells)) + 1]}
            if (cells := data.get("cell_voltages", []))
            else {}
        ),
        device_class=SensorDeviceClass.VOLTAGE,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        key=ATTR_MIN_VOLTAGE,
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=3,
        translation_key=ATTR_MIN_VOLTAGE,
        value_fn=lambda data: (
            min(cells) if (cells := data.get("cell_voltages", [])) else None
        ),
    ),
    BmsEntityDescription(
        device_class=SensorDeviceClass.SIGNAL_STRENGTH,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        key=ATTR_RSSI,
        native_unit_of_measurement=SIGNAL_STRENGTH_DECIBELS_MILLIWATT,
        state_class=SensorStateClass.MEASUREMENT,
        translation_key=ATTR_RSSI,
        value_fn=lambda data: None,
    ),
    BmsEntityDescription(
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        key=ATTR_LQ,
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        translation_key=ATTR_LQ,
        value_fn=lambda data: None,
    ),
]

PACK_SENSOR_TYPES: Final[list[BmsEntityDescription]] = [
    descr
    for descr in SENSOR_TYPES
    if descr.key not in (ATTR_LQ, ATTR_RSSI, ATTR_RUNTIME)
]


def _gen_temperature_sensors(
    bms: BTBmsCoordinator,
    descr: BmsEntityDescription,
    mac: str,
    pack_idx: int = -1,
    entry_id: str = "",
) -> list[BMSSensor]:
    if (
        not (
            temp_sensors := (
                bms.data.get("temperature")
                if pack_idx == -1
                else bms.data.get("packs", [])[pack_idx - 1].get("temperature")
            )
        )
        or len(temp_sensors) < 2
    ):
        return []

    sensors: list[BMSSensor] = []
    for idx in range(1, len(temp_sensors) + 1):
        sensor = temp_sensors[idx - 1]
        sensor_descr = replace(
            descr,
            entity_category=EntityCategory.DIAGNOSTIC,
            entity_registry_enabled_default=False,
            key=descr.key + f"-probe-{idx}-{sensor.type.name}",
            translation_key=descr.key + f"_{sensor.type.name}".lower(),
            translation_placeholders={"id": str(idx)},
            value_fn=lambda data, idx=idx - 1: data.get("temperature")[idx].value,
        )
        sensors.append(
            PackSensor(bms, sensor_descr, mac, pack_idx, entry_id)
            if pack_idx != -1
            else BMSSensor(bms, sensor_descr, mac)
        )

    return sensors


async def async_setup_entry(
    _hass: HomeAssistant,
    config_entry: BTBmsConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Add sensors for passed config_entry in Home Assistant."""

    bms: Final = config_entry.runtime_data
    mac: Final = format_mac(config_entry.unique_id)
    entities: list[SensorEntity] = []
    for descr in SENSOR_TYPES:
        if descr.key == ATTR_RSSI:
            entities.append(RSSISensor(bms, descr, mac))
            continue
        if descr.key == ATTR_LQ:
            entities.append(LQSensor(bms, descr, mac))
            continue
        if descr.optional and descr.key not in bms.data:
            continue
        if descr.key == ATTR_TEMPERATURE:
            entities.extend(_gen_temperature_sensors(bms, descr, mac))
        entities.append(BMSSensor(bms, descr, mac))
    async_add_entities(entities)

    pack_sensors: list[SensorEntity] = []
    for pack_idx, pack in enumerate(bms.data.get("packs", []), start=1):
        for descr in PACK_SENSOR_TYPES:
            if descr.optional and descr.key not in pack:
                continue
            if descr.key == ATTR_TEMPERATURE:
                pack_sensors.extend(
                    _gen_temperature_sensors(
                        bms, descr, mac, pack_idx, config_entry.entry_id
                    )
                )
            pack_sensors.append(
                PackSensor(bms, descr, mac, pack_idx, config_entry.entry_id)
            )
    if pack_sensors:
        async_add_entities(pack_sensors)


class BMSSensor(CoordinatorEntity[BTBmsCoordinator], SensorEntity):
    """The generic BMS sensor implementation."""

    _unrecorded_attributes: frozenset[str] = frozenset({MATCH_ALL})
    _attr_has_entity_name = True
    entity_description: BmsEntityDescription

    def __init__(
        self, bms: BTBmsCoordinator, descr: BmsEntityDescription, unique_id: str
    ) -> None:
        """Initialize the BMS sensor."""
        self._attr_unique_id = f"{DOMAIN}-{unique_id}-{descr.key}"
        self._attr_device_info = bms.device_info
        self.entity_description = descr
        super().__init__(bms)

    @property
    @override
    def extra_state_attributes(self) -> dict[str, list[int | float]] | None:
        """Return entity specific state attributes, e.g. cell voltages."""
        if self.coordinator.data:
            return self.entity_description.attr_fn(self.coordinator.data)

        return None

    @property
    @override
    def native_value(self) -> int | float | None:
        """Return the sensor value."""
        return (
            self.entity_description.value_fn(self.coordinator.data)
            if self.coordinator.data
            else None
        )


class PackSensor(BMSSensor):
    """A sensor belonging to one battery pack child device."""

    def __init__(
        self,
        bms: BTBmsCoordinator,
        descr: BmsEntityDescription,
        unique_id: str,
        pack_index: int,
        config_entry_id: str,
    ) -> None:
        """Initialize a pack sensor."""

        def pack_data(data: BMSSample) -> PackSample | None:
            packs = data.get("packs", [])
            return packs[pack_index - 1] if len(packs) >= pack_index else None

        def pack_value(data: BMSSample) -> float | int | None:
            pack = pack_data(data)
            return descr.value_fn(pack) if pack is not None else None

        def pack_attr(data: BMSSample) -> dict[str, list[int | float]] | None:
            if (pack := pack_data(data)) is None:
                return None
            return descr.attr_fn(pack)

        pack_descr = replace(descr, attr_fn=pack_attr, value_fn=pack_value)
        super().__init__(bms, pack_descr, unique_id)
        self._attr_unique_id = f"{DOMAIN}-{unique_id}-pack-{pack_index}-{descr.key}"
        self._pack_index = pack_index
        self._config_entry_id = config_entry_id
        self._parent_identifier = next(
            identifier
            for domain, identifier in bms.device_info.get("identifiers", set())
            if domain == DOMAIN
        )

    @cached_property
    @override
    def device_info(self) -> ChildDeviceInfo:
        """Return child-device information for this battery pack."""
        identifiers = {(DOMAIN, f"{self._parent_identifier}_pack_{self._pack_index}")}
        parent_device_id = dr.async_get_device_id_by_identifier(
            self.hass,
            (DOMAIN, self._parent_identifier),
            config_entry_id=self._config_entry_id,
        )
        return ChildDeviceInfo(
            identifiers=identifiers,
            translation_key="pack",
            translation_placeholders={"id": str(self._pack_index)},
            parent_device_id=parent_device_id,
        )


class RSSISensor(SensorEntity):
    """The Bluetooth RSSI sensor."""

    LIMIT: Final = 127  # limit to +/- this range
    _attr_has_entity_name = True

    def __init__(
        self, bms: BTBmsCoordinator, descr: SensorEntityDescription, unique_id: str
    ) -> None:
        """Initialize the BMS sensor."""

        self._attr_unique_id = f"{DOMAIN}-{unique_id}-{descr.key}"
        self._attr_device_info = bms.device_info
        self.entity_description = descr
        self._bms: Final = bms

    async def async_update(self) -> None:
        """Update RSSI sensor value."""

        self._attr_native_value = (
            max(min(self._bms.rssi, self.LIMIT), -self.LIMIT)
            if self._bms.rssi is not None
            else -self.LIMIT
        )
        self._attr_available = self._bms.rssi is not None

        LOGGER.debug("%s: RSSI value: %i dBm", self._bms.name, self._attr_native_value)


class LQSensor(SensorEntity):
    """The BMS link quality sensor."""

    _attr_has_entity_name = True
    _attr_available = True  # always available
    _attr_native_value = 0

    def __init__(
        self, bms: BTBmsCoordinator, descr: SensorEntityDescription, unique_id: str
    ) -> None:
        """Initialize the BMS link quality sensor."""

        self._attr_unique_id = f"{DOMAIN}-{unique_id}-{descr.key}"
        self._attr_device_info = bms.device_info
        self.entity_description = descr
        self._bms: Final = bms

    async def async_update(self) -> None:
        """Update BMS link quality sensor value."""

        self._attr_native_value = self._bms.link_quality

        LOGGER.debug("%s: Link quality: %i %%", self._bms.name, self._attr_native_value)
