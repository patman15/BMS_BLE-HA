"""Home Assistant coordinator for BLE Battery Management System integration."""

from datetime import timedelta

from bleak.backends.device import BLEDevice
from bleak.exc import BleakError

from homeassistant.components import bluetooth
from homeassistant.components.bluetooth import DOMAIN as BLUETOOTH_DOMAIN
from homeassistant.const import ATTR_NAME
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import CONNECTION_BLUETOOTH, DeviceInfo
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import ATTR_RSSI, DOMAIN, LOGGER, UPDATE_INTERVAL
from .plugins.basebms import BaseBMS


class BTBmsCoordinator(DataUpdateCoordinator[dict[str, int | float | bool]]):
    """Update coordinator for a battery management system."""

    def __init__(
        self,
        hass: HomeAssistant,
        ble_device: BLEDevice,
        bms_device: BaseBMS,
    ) -> None:
        """Initialize BMS data coordinator."""
        assert ble_device.name is not None
        super().__init__(
            hass=hass,
            logger=LOGGER,
            name=ble_device.name,
            update_interval=timedelta(seconds=UPDATE_INTERVAL),
            always_update=False,  # only update when sensor value has changed
        )

        self._mac = ble_device.address
        LOGGER.debug(
            "Initializing coordinator for %s (%s) as %s",
            ble_device.name,
            ble_device.address,
            bms_device.device_id(),
        )
        if service_info := bluetooth.async_last_service_info(
            self.hass, address=self._mac, connectable=True
        ):
            LOGGER.debug("device data: %s", service_info.as_dict())

        # retrieve BMS class and initialize it
        self._device: BaseBMS = bms_device
        device_info = self._device.device_info()
        self.device_info = DeviceInfo(
            identifiers={
                (DOMAIN, ble_device.name),
                (BLUETOOTH_DOMAIN, ble_device.address),
            },
            connections={(CONNECTION_BLUETOOTH, ble_device.address)},
            name=ble_device.name,
            configuration_url=None,
            # properties used in GUI:
            manufacturer=device_info.get("manufacturer"),
            model=device_info.get("model"),
        )

    async def stop(self) -> None:
        """Stop connection to BMS instance."""
        LOGGER.debug("Stopping device %s", self.device_info.get(ATTR_NAME))
        await self._device.disconnect()

    async def _async_update_data(self) -> dict[str, int | float | bool]:
        """Return the latest data from the device."""
        LOGGER.debug("BMS %s data update", self.device_info.get(ATTR_NAME))

        battery_info: dict[str, int | float | bool] = {}
        try:
            battery_info.update(await self._device.async_update())
        except TimeoutError:
            LOGGER.debug("Device communication timeout")
            raise
        except BleakError as err:
            raise UpdateFailed(
                f"device communicating failed: {err!s} ({type(err).__name__})"
            ) from err

        service_info = bluetooth.async_last_service_info(
            self.hass, address=self._mac, connectable=True
        )
        if service_info is not None:
            battery_info.update({ATTR_RSSI: service_info.rssi})

        LOGGER.debug("BMS data sample %s", battery_info)
        return battery_info
