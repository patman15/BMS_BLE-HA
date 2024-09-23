"""Config flow for BLE Battery Management System integration."""

from dataclasses import dataclass
from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.components.bluetooth import (
    BluetoothServiceInfoBleak,
    async_discovered_service_info,
)
from homeassistant.config_entries import ConfigFlowResult
from homeassistant.const import CONF_ADDRESS
from homeassistant.helpers.device_registry import format_mac
from homeassistant.helpers.importlib import async_import_module
from homeassistant.helpers.selector import SelectSelector, SelectSelectorConfig

from .const import BMS_TYPES, DOMAIN, LOGGER


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for BT Battery Management System."""

    VERSION = 1
    MINOR_VERSION = 0

    @dataclass
    class DiscoveredDevice:
        """A discovered bluetooth device."""

        name: str
        discovery_info: BluetoothServiceInfoBleak
        type: str

    def __init__(self) -> None:
        """Initialize the config flow."""

        self._discovered_device: ConfigFlow.DiscoveredDevice | None = None
        self._discovered_devices: dict[str, ConfigFlow.DiscoveredDevice] = {}

    async def _async_device_supported(
        self, discovery_info: BluetoothServiceInfoBleak
    ) -> str | None:
        """Check if device is supported by an available BMS class."""
        for bms_type in BMS_TYPES:
            bms_plugin = await async_import_module(
                self.hass, f"custom_components.bms_ble.plugins.{bms_type}"
            )
            try:
                if bms_plugin.BMS.supported(discovery_info):
                    LOGGER.debug(
                        "Device %s (%s) detected as '%s'",
                        discovery_info.name,
                        format_mac(discovery_info.address),
                        bms_plugin.BMS.device_id(),
                    )
                    return bms_plugin.__name__
            except AttributeError:
                LOGGER.error("Invalid BMS plugin %s", bms_type)
        return None

    async def async_step_bluetooth(
        self, discovery_info: BluetoothServiceInfoBleak
    ) -> ConfigFlowResult:
        """Handle a flow initialized by Bluetooth discovery."""
        LOGGER.debug("Bluetooth device detected: %s", discovery_info)

        await self.async_set_unique_id(discovery_info.address)
        self._abort_if_unique_id_configured()

        device_class = await self._async_device_supported(discovery_info)
        if device_class is None:
            return self.async_abort(reason="not_supported")

        self._discovered_device = ConfigFlow.DiscoveredDevice(
            discovery_info.name, discovery_info, device_class
        )
        self.context["title_placeholders"] = {"name": self._discovered_device.name}
        return await self.async_step_bluetooth_confirm()

    async def async_step_bluetooth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Confirm bluetooth device discovery."""
        assert self._discovered_device is not None
        LOGGER.debug("confirm step for %s", self._discovered_device.name)

        if user_input is not None:
            return self.async_create_entry(
                title=self._discovered_device.name,
                data={"type": self._discovered_device.type},
            )

        self._set_confirm_only()

        return self.async_show_form(
            step_id="bluetooth_confirm",
            description_placeholders={"name": self._discovered_device.name},
        )

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the user step to pick discovered device."""
        LOGGER.debug("user step")

        if user_input is not None:
            address = user_input[CONF_ADDRESS]
            await self.async_set_unique_id(address, raise_on_progress=False)
            self._abort_if_unique_id_configured()
            self._discovered_device = self._discovered_devices[address]

            self.context["title_placeholders"] = {"name": self._discovered_device.name}

            return self.async_create_entry(
                title=self._discovered_device.name,
                data={"type": self._discovered_device.type},
            )

        current_addresses = self._async_current_ids()
        for discovery_info in async_discovered_service_info(self.hass, False):
            address = discovery_info.address
            if address in current_addresses or address in self._discovered_devices:
                continue
            device_class = await self._async_device_supported(discovery_info)
            if not device_class:
                continue

            self._discovered_devices[address] = ConfigFlow.DiscoveredDevice(
                discovery_info.name, discovery_info, device_class
            )

        if not self._discovered_devices:
            return self.async_abort(reason="no_devices_found")

        titles = []
        for address, discovery in self._discovered_devices.items():
            titles.append({"value": address, "label": f"{discovery.name} ({address})"})

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_ADDRESS): SelectSelector(
                        SelectSelectorConfig(options=titles)
                    )
                }
            ),
        )
