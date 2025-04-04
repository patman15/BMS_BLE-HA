"""Config flow for BLE Battery Management System integration."""

from dataclasses import dataclass
from types import ModuleType
from typing import Any, Final

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.components.bluetooth import (
    BluetoothServiceInfoBleak,
    async_discovered_service_info,
)
from homeassistant.config_entries import ConfigFlowResult
from homeassistant.const import CONF_ADDRESS, CONF_ID, CONF_MODEL, CONF_NAME
from homeassistant.helpers.device_registry import format_mac
from homeassistant.helpers.importlib import async_import_module
from homeassistant.helpers.selector import (
    SelectOptionDict,
    SelectSelector,
    SelectSelectorConfig,
)

from .const import BMS_TYPES, DOMAIN, LOGGER


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for BT Battery Management System."""

    VERSION = 1
    MINOR_VERSION = 0

    @dataclass
    class DiscoveredDevice:
        """A discovered Bluetooth device."""

        name: str
        discovery_info: BluetoothServiceInfoBleak
        type: str

        def model(self) -> str:
            """Return BMS type in capital letters, e.g. 'DUMMY BMS'."""
            return self.type.rsplit(".", 1)[-1].replace("_", " ").upper()

    def __init__(self) -> None:
        """Initialize the config flow."""

        self._disc_dev: ConfigFlow.DiscoveredDevice | None = None
        self._disc_devs: dict[str, ConfigFlow.DiscoveredDevice] = {}

    async def _async_device_supported(
        self, discovery_info: BluetoothServiceInfoBleak
    ) -> str | None:
        """Check if device is supported by an available BMS class."""
        for bms_type in BMS_TYPES:
            bms_plugin: ModuleType = await async_import_module(
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

        device_class: Final[str | None] = await self._async_device_supported(
            discovery_info
        )
        if device_class is None:
            return self.async_abort(reason="not_supported")

        self._disc_dev = ConfigFlow.DiscoveredDevice(
            discovery_info.name, discovery_info, device_class
        )
        self.context["title_placeholders"] = {
            CONF_NAME: self._disc_dev.name,
            CONF_ID: self._disc_dev.discovery_info.address[8:],  # remove OUI
            CONF_MODEL: self._disc_dev.model(),
        }
        return await self.async_step_bluetooth_confirm()

    async def async_step_bluetooth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Confirm bluetooth device discovery."""
        assert self._disc_dev is not None
        LOGGER.debug("confirm step for %s", self._disc_dev.name)

        if user_input is not None:
            return self.async_create_entry(
                title=self._disc_dev.name,
                data={"type": self._disc_dev.type},
            )

        self._set_confirm_only()

        return self.async_show_form(
            step_id="bluetooth_confirm",
            description_placeholders=self.context.get("title_placeholders"),
        )

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the user step to pick discovered device."""
        LOGGER.debug("user step")

        if user_input is not None:
            address: str = str(user_input[CONF_ADDRESS])
            await self.async_set_unique_id(address, raise_on_progress=False)
            self._abort_if_unique_id_configured()
            self._disc_dev = self._disc_devs[address]

            return self.async_create_entry(
                title=self._disc_dev.name,
                data={"type": self._disc_dev.type},
            )

        current_addresses: Final[set[str | None]] = self._async_current_ids()
        for discovery_info in async_discovered_service_info(self.hass, False):
            address = discovery_info.address
            if address in current_addresses or address in self._disc_devs:
                continue
            device_class: str | None = await self._async_device_supported(
                discovery_info
            )
            if not device_class:
                continue

            self._disc_devs[address] = ConfigFlow.DiscoveredDevice(
                discovery_info.name, discovery_info, device_class
            )

        if not self._disc_devs:
            return self.async_abort(reason="no_devices_found")

        titles: list[SelectOptionDict] = []
        for address, discovery in self._disc_devs.items():
            titles.append(
                SelectOptionDict(
                    value=address,
                    label=f"{discovery.name} ({address}) - {discovery.model()}",
                )
            )

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
