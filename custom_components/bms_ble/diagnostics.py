"""Provide diagnostics data for a battery management system."""

from typing import Any, Final

from homeassistant.components.bluetooth import async_last_service_info
from homeassistant.components.bluetooth.const import DOMAIN as BT_DOMAIN
from homeassistant.components.diagnostics import async_redact_data
from homeassistant.const import ATTR_AREA_ID, ATTR_ID
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr

from . import BTBmsConfigEntry
from .const import ATTR_LQ, ATTR_RSSI
from .coordinator import BTBmsCoordinator

TO_REDACT: frozenset[str] = frozenset({ATTR_ID, ATTR_AREA_ID})


async def async_get_device_diagnostics(
    hass: HomeAssistant, entry: BTBmsConfigEntry, device: dr.DeviceEntry
) -> dict[str, Any]:
    """Return diagnostics for a BMS device."""
    adapter_info: str = "unavailable"
    coord: Final[BTBmsCoordinator] = entry.runtime_data
    mac: str = next(
        (id_value for domain, id_value in device.identifiers if domain == "bms_ble"), ""
    )
    if (adv_data := async_last_service_info(hass, address=mac, connectable=True)) and (
        adapter := dr.async_get(hass).async_get_device(
            connections={(BT_DOMAIN, adv_data.source)}
        )
    ):
        adapter_info = (
            f"name: {adapter.name}, {adapter.manufacturer} ({adapter.model}/"
            f"{adapter.model_id}): {adapter.hw_version}, {adapter.sw_version}"
        )

    return {
        "entry_data": async_redact_data(entry.data, TO_REDACT),
        "device_data": async_redact_data(device.dict_repr, TO_REDACT),
        "adapter_data": adapter_info,
        "adv_data": adv_data,
        "bms_data": entry.runtime_data.data,
        "bt_data": {ATTR_RSSI: coord.rssi, ATTR_LQ: coord.link_quality},
        "update_data": {
            "last_update_success": coord.last_update_success,
            "last_exception": coord.last_exception,
            "interval": coord.update_interval,
        },
    }
