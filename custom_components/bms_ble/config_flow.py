"""Config flow for BT Battery Management System integration."""

from habluetooth import BluetoothServiceInfoBleak
from homeassistant import config_entries
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers.device_registry import format_mac
from typing import Any

from .const import DOMAIN
import logging

_LOGGER = logging.getLogger(__name__)

class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for BT Battery Management System."""

    VERSION = 0
    MINOR_VERSION = 1

    def __init__(self) -> None:
        """Initialize the config flow."""
        self._discovery_info: BluetoothServiceInfoBleak | None = None
        # self._discovered_device: SensirionBluetoothDeviceData | None = None
        # self._discovered_devices: dict[str, str] = {}

    async def async_step_bluetooth(
        self, discovery_info: BluetoothServiceInfoBleak
    ) -> FlowResult:
        """Handle a flow initialized by Bluetooth discovery."""
        _LOGGER.debug(f"Bluetooth device detected: {format_mac(discovery_info.address)}")
        await self.async_set_unique_id(discovery_info.address)
        self._abort_if_unique_id_configured()
        self._discovery_info = discovery_info
        self.context["title_placeholders"] = {"name": self._discovery_info.name}        

        return await self.async_step_bluetooth_confirm()
        # return self.async_create_entry(title=discovery_info.name, data={})

    async def async_step_bluetooth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Confirm bluetooth device discovery."""
        _LOGGER.warning(f"confirm step {self._discovery_info.name}")
        assert self._discovery_info is not None
        title = self._discovery_info.name

        if user_input is not None:
            return self.async_create_entry(title=title , data={})

        self._set_confirm_only()
        placeholders = {"name": title}
        return self.async_show_form(step_id="bluetooth_confirm", description_placeholders=placeholders)

