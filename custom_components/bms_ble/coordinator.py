"""Home Assistant coordinator for BLE Battery Management System integration."""

from collections import deque
from datetime import timedelta
from time import monotonic
from typing import Final

from bleak.backends.device import BLEDevice
from bleak.exc import BleakError
from habluetooth import BluetoothServiceInfoBleak

from homeassistant.components.bluetooth import async_last_service_info
from homeassistant.components.bluetooth.const import DOMAIN as BLUETOOTH_DOMAIN
from homeassistant.config_entries import ConfigEntry
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
        config_entry: ConfigEntry,
    ) -> None:
        """Initialize BMS data coordinator."""
        assert ble_device.name is not None
        super().__init__(
            hass=hass,
            logger=LOGGER,
            name=ble_device.name,
            update_interval=timedelta(seconds=UPDATE_INTERVAL),
            always_update=False,  # only update when sensor value has changed
            config_entry=config_entry,
        )
        self.name: Final[str] = ble_device.name
        self._mac: Final[str] = ble_device.address
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
            LOGGER.debug("%s: advertisement: %s", self.name, service_info.as_dict())

        # retrieve BMS class and initialize it
        self._device: Final[BaseBMS] = bms_device
        device_info: dict[str, str] = self._device.device_info()
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

        service_info: BluetoothServiceInfoBleak | None = async_last_service_info(
            self.hass, address=self._mac, connectable=True
        )
        return service_info.rssi if service_info else None

    def _rssi_msg(self) -> str:
        """Return check RSSI message if below -75dBm."""
        return (
            f", check signal strength ({self.rssi} dBm)"
            if self.rssi and self.rssi < -75
            else ""
        )

    @property
    def link_quality(self) -> int:
        """Gives the precentage of successful BMS reads out of the last 100 attempts."""

        return int(self._link_q.count(True) * 100 / len(self._link_q))

    async def async_shutdown(self) -> None:
        """Shutdown coordinator and any connection."""
        LOGGER.debug("Shutting down BMS device (%s)", self.name)
        await super().async_shutdown()
        await self._device.disconnect()

    async def _async_update_data(self) -> BMSsample:
        """Return the latest data from the device."""

        LOGGER.debug("%s: BMS data update", self.name)

        start: Final[float] = monotonic()
        try:
            if not (bms_data := await self._device.async_update()):
                LOGGER.debug("%s: no valid data received", self.name)
                raise UpdateFailed("no valid data received.")
        except TimeoutError as err:
            LOGGER.debug(
                "%s: device communication timed out%s", self.name, self._rssi_msg()
            )
            raise TimeoutError("device communication timed out") from err
        except (BleakError, EOFError) as err:
            LOGGER.debug(
                "%s: device communication failed%s: %s (%s)",
                self.name,
                self._rssi_msg(),
                err,
                type(err).__name__,
            )
            raise UpdateFailed(
                f"device communication failed{self._rssi_msg()}: {err!s} ({type(err).__name__})"
            ) from err
        finally:
            self._link_q.extend(
                [False] * (1 + int((monotonic() - start) / UPDATE_INTERVAL))
            )

        self._link_q[-1] = True  # set success
        LOGGER.debug("%s: BMS data sample %s", self.name, bms_data)
        return bms_data
