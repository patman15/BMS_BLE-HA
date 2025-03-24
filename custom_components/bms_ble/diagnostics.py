"""Provide diagnostics data for a battery management system."""

from typing import Any, Final

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.const import ATTR_AREA_ID, ATTR_ID
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceEntry

from . import BTBmsConfigEntry
from .const import ATTR_LQ, ATTR_RSSI
from .coordinator import BTBmsCoordinator

TO_REDACT: frozenset[str] = frozenset({ATTR_ID, ATTR_AREA_ID})


async def async_get_device_diagnostics(
    _hass: HomeAssistant, entry: BTBmsConfigEntry, device: DeviceEntry
) -> dict[str, Any]:
    """Return diagnostics for a BMS device."""
    coord: Final[BTBmsCoordinator] = entry.runtime_data
    return {
        "entry_data": async_redact_data(entry.data, TO_REDACT),
        "device_data": async_redact_data(device.dict_repr, TO_REDACT),
        "bms_data": entry.runtime_data.data,
        "bt_data": {ATTR_RSSI: coord.rssi, ATTR_LQ: coord.link_quality},
        "update_data": {
            "last_update_success": coord.last_update_success,
            "last_exception": coord.last_exception,
            "interval": coord.update_interval,
        },
    }
