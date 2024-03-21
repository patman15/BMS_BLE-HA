"""Home Assistant coordinator for BLE Battery Management System integration."""
from datetime import timedelta
from homeassistant.components import bluetooth
from homeassistant.components.bluetooth import DOMAIN as BLUETOOTH_DOMAIN
from homeassistant.const import ATTR_IDENTIFIERS, ATTR_NAME
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo, CONNECTION_BLUETOOTH
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from bleak.backends.device import BLEDevice
from asyncio import CancelledError
from .const import DOMAIN, UPDATE_INTERVAL
from .ogtbms import OGTBms

import logging


class BTBmsCoordinator(DataUpdateCoordinator[None]):
    """Representation of a battery."""

    def __init__(
        self,
        hass: HomeAssistant,
        logger: logging.Logger,
        ble_device: BLEDevice,
    ) -> None:
        """Initialize BMS data coordinator."""
        super().__init__(
            hass=hass,
            logger=logger,
            name=ble_device.name,
            update_interval=timedelta(seconds=UPDATE_INTERVAL),
            always_update=False,  # only update when sensor value has changed
        )
        self._logger = logger
        self._mac = ble_device.address
        self._logger.debug("Init BTBms: %s (%s)",
                           ble_device.name, ble_device.address)
        self._device: OGTBms = OGTBms(ble_device)
        self.device_info = DeviceInfo(
            identifiers={(DOMAIN, ble_device.name),
                         (BLUETOOTH_DOMAIN, ble_device.address)},
            connections={(CONNECTION_BLUETOOTH, ble_device.address)},
            name=ble_device.name,
            configuration_url=None,
            # properties used in GUI:
            model=ble_device.name,
        )

    async def _async_update_data(self) -> dict:
        """Return the latest data from the device."""
        self._logger.debug(f"BMS {self.device_info[ATTR_NAME]} data update")

        service_info = bluetooth.async_last_service_info(
            self.hass, address=self._mac, connectable=True)
        try:
            battery_info = await self._device.async_update()
        except CancelledError:
            return {}
        except:
            raise UpdateFailed("Device communicating error.")

        return battery_info | {"rssi": service_info.rssi}
