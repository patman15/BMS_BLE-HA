"""Provide diagnostics data for a battery management system."""

from typing import Any, Final

from homeassistant.components.bluetooth import async_last_service_info
from homeassistant.components.bluetooth.const import DOMAIN as BT_DOMAIN
from homeassistant.components.diagnostics import async_redact_data
from homeassistant.const import ATTR_AREA_ID, ATTR_ID, ATTR_SERIAL_NUMBER
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr

from . import BTBmsConfigEntry
from .coordinator import BTBmsCoordinator

TO_REDACT: frozenset[str] = frozenset(
    {ATTR_AREA_ID, ATTR_ID, ATTR_SERIAL_NUMBER, "entry_id"}
)


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: BTBmsConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""

    adapter_info: str = "unavailable"
    coord: Final[BTBmsCoordinator] = entry.runtime_data
    mac: str = str(entry.unique_id)

    if (adv_data := async_last_service_info(hass, address=mac, connectable=True)) and (
        adapter := dr.async_get(hass).async_get_device(
            connections={(BT_DOMAIN, adv_data.source)}
        )
    ):
        adapter_info = (
            f"{adapter.name}, {adapter.manufacturer} ({adapter.model}/"
            f"{adapter.model_id}): {adapter.hw_version}, {adapter.sw_version}"
        )

    return {
        "config_entry": async_redact_data(entry.as_dict(), TO_REDACT),
        "adapter_data": adapter_info,
        "advertisement_data": async_redact_data(
            adv_data.as_dict() if adv_data else {}, TO_REDACT | {"source"}
        ),
        "bms_link_quality": coord.link_quality,
        "bms_info": async_redact_data(coord.device_info, TO_REDACT),
        "bms_data": coord.data,
        "update_data": {
            "last_update_success": coord.last_update_success,
            "last_exception": coord.last_exception,
            "interval": coord.update_interval,
        },
    }
