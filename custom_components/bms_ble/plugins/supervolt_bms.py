"""Module to support Dummy BMS."""

import logging
from typing import Any, Optional

from bleak.backends.device import BLEDevice
from bleak import BleakClient
from bleak.uuids import normalize_uuid_str

from ..const import (
    ATTR_BATTERY_CHARGING,
    # ATTR_BATTERY_LEVEL,
    ATTR_CURRENT,
    # ATTR_CYCLE_CAP,
    # ATTR_CYCLE_CHRG,
    # ATTR_CYCLES,
    ATTR_POWER,
    # ATTR_RUNTIME,
    # ATTR_TEMPERATURE,
    ATTR_VOLTAGE,
)
from .basebms import BaseBMS

LOGGER = logging.getLogger(__name__)

UUID_SERVICE = normalize_uuid_str("1800")
UUID_RX = normalize_uuid_str("1801")
UUID_TX = normalize_uuid_str("180a")


class BMS(BaseBMS):
    """Dummy battery class implementation."""

    def __init__(self, ble_device: BLEDevice, reconnect: bool = False) -> None:
        """Initialize BMS."""
        LOGGER.debug("%s init(), BT address: %s", self.device_id(), ble_device.address)
        self._reconnect: bool = reconnect
        self._ble_device: BLEDevice = ble_device
        assert self._ble_device is not None
        self._client: Optional[BleakClient] = None
        self._connected: bool = False

    @staticmethod
    def matcher_dict_list() -> list[dict[str, Any]]:
        """Provide BluetoothMatcher definition."""
        return [
            {
                "local_name": "SX100P-*",
                # "service_uuid": UUID_SERVICE,
                "connectable": True,
            }
        ]

    @staticmethod
    def device_info() -> dict[str, str]:
        """Return device information for the battery management system."""
        return {"manufacturer": "Supervolt", "model": "dummy model"}

    async def _connect(self) -> None:
        """Connect to the BMS and setup notification if not connected."""

        if not self._connected:
            LOGGER.debug("Connecting BMS (%s)", self._ble_device.name)
            self._client = BleakClient(
                self._ble_device,
                disconnected_callback=self._on_disconnect,
                services=[UUID_SERVICE],
            )
            LOGGER.debug("connect inner")
            await self._client.connect()
            LOGGER.debug("set notify")
            await self._client.start_notify(UUID_RX, self._notification_handler)
            LOGGER.debug("connected.....................")
            self._connected = True
        else:
            LOGGER.debug("BMS %s already connected", self._ble_device.name)

    def _notification_handler(self, sender, data: bytearray) -> None:
        LOGGER.debug("Received BLE data: %s", data)
        self._data = data
        self._data_event.set()

    def _on_disconnect(self, client: BleakClient) -> None:
        """Disconnect callback function."""

        LOGGER.debug("Disconnected from BMS (%s)", client.address)
        self._connected = False

    async def disconnect(self) -> None:
        """Disconnect connection to BMS if active."""

    async def async_update(self) -> dict[str, int | float | bool]:
        """Update battery status information."""
        LOGGER.debug("connecting for update")
        await self._connect()
        assert self._client is not None

        data = {
            ATTR_VOLTAGE: 12,
            ATTR_CURRENT: 1.5,
        }  # set fixed values for dummy battery
        self.calc_values(
            data, {ATTR_POWER, ATTR_BATTERY_CHARGING}
        )  # calculate further values from previously set ones
        return data
