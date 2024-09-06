"""Home Assistant coordinator for BLE Battery Management System integration."""

from datetime import timedelta

from bleak.backends.device import BLEDevice
from bleak.exc import BleakError

from homeassistant.components import bluetooth
from homeassistant.components.bluetooth import DOMAIN as BLUETOOTH_DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import CONNECTION_BLUETOOTH, DeviceInfo
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import ATTR_RSSI, DOMAIN, LOGGER, UPDATE_INTERVAL
from .plugins.basebms import BaseBMS, BMSsample


class BTBmsCoordinator(DataUpdateCoordinator[BMSsample]):
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
        self._name: str = ble_device.name
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
        LOGGER.debug("%s: stopping device", self._name)
        await self._device.disconnect()

    async def _async_update_data(self) -> BMSsample:
        """Return the latest data from the device."""
        LOGGER.debug("%s: BMS data update", self._name)

        try:
            battery_info = await self._device.async_update()
        except TimeoutError as err:
            LOGGER.debug("%s: device communication timed out", self._name)
            raise TimeoutError("device communication timed out") from err
        except BleakError as err:
            LOGGER.debug("%s: device communicating failed: %s (%s)", self._name, err, type(err).__name__)
            raise UpdateFailed(
                f"device communicating failed: {err!s} ({type(err).__name__})"
            ) from err

        if not battery_info:
            LOGGER.debug("%s: no valid data received", self._name)
            raise UpdateFailed("no valid data received.")

        if (
            service_info := bluetooth.async_last_service_info(
                self.hass, address=self._mac, connectable=True
            )
        ) is not None:
            battery_info.update({ATTR_RSSI: service_info.rssi})

        LOGGER.debug("BMS data sample %s", battery_info)
        return battery_info
