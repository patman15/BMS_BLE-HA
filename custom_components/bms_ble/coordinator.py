"""Home Assistant coordinator for BLE Battery Management System integration."""

from collections import deque
from datetime import timedelta

from bleak.backends.device import BLEDevice
from bleak.exc import BleakError

from homeassistant.components.bluetooth import (
    DOMAIN as BLUETOOTH_DOMAIN,
    async_last_service_info,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import CONNECTION_BLUETOOTH, DeviceInfo
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN, LOGGER, UPDATE_INTERVAL
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
        self.name: str = ble_device.name
        self._mac = ble_device.address
        LOGGER.debug(
            "Initializing coordinator for %s (%s) as %s",
            self.name,
            self._mac,
            bms_device.device_id(),
        )
        self._link_q = deque([False], maxlen=100)  # track BMS update issues
        if service_info := async_last_service_info(
            self.hass, address=self._mac, connectable=True
        ):
            LOGGER.debug("device data: %s", service_info.as_dict())

        # retrieve BMS class and initialize it
        self._device: BaseBMS = bms_device
        device_info = self._device.device_info()
        self.device_info = DeviceInfo(
            identifiers={
                (DOMAIN, self._mac),
                (BLUETOOTH_DOMAIN, self._mac),
            },
            connections={(CONNECTION_BLUETOOTH, self._mac)},
            name=self.name,
            configuration_url=None,
            # properties used in GUI:
            manufacturer=device_info.get("manufacturer"),
            model=device_info.get("model"),
        )

    @property
    def rssi(self) -> int | None:
        """Return RSSI value for target BMS."""

        service_info = async_last_service_info(
            self.hass, address=self._mac, connectable=True
        )
        return service_info.rssi if service_info else None

    @property
    def link_quality(self) -> int:
        """Gives the precentage of successful BMS reads out of the last 100 attempts."""

        return int(self._link_q.count(True) * 100 / len(self._link_q))

    async def stop(self) -> None:
        """Stop connection to BMS instance."""

        LOGGER.debug("%s: stopping device", self.name)
        await self._device.disconnect()

    async def _async_update_data(self) -> BMSsample:
        """Return the latest data from the device."""

        LOGGER.debug("%s: BMS data update", self.name)

        try:
            battery_info = await self._device.async_update()
            if not battery_info:
                LOGGER.debug("%s: no valid data received", self.name)
                raise UpdateFailed("no valid data received.")
        except TimeoutError as err:
            LOGGER.debug("%s: device communication timed out", self.name)
            raise TimeoutError("device communication timed out") from err
        except (BleakError, EOFError) as err:
            LOGGER.debug(
                "%s: device communicating failed: %s (%s)",
                self.name,
                err,
                type(err).__name__,
            )
            raise UpdateFailed(
                f"device communicating failed: {err!s} ({type(err).__name__})"
            ) from err
        finally:
            self._link_q.append(False)

        self._link_q[-1] = True  # set success
        LOGGER.debug("BMS data sample %s", battery_info)
        return battery_info
