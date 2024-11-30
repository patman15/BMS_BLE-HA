"""Base class defintion for battery management systems (BMS)."""

import asyncio.events
import logging
from abc import ABCMeta, abstractmethod
from collections.abc import Awaitable, Callable
from statistics import fmean
from typing import Any, Final

from bleak import BleakClient
from bleak.backends.characteristic import BleakGATTCharacteristic
from bleak.backends.device import BLEDevice
from bleak.exc import BleakError
from bleak_retry_connector import establish_connection
from homeassistant.components.bluetooth import BluetoothServiceInfoBleak
from homeassistant.components.bluetooth.match import ble_device_matches
from homeassistant.loader import BluetoothMatcherOptional
from homeassistant.util.unit_conversion import _HRS_TO_SECS

from custom_components.bms_ble.const import (
    ATTR_BATTERY_CHARGING,
    ATTR_CURRENT,
    ATTR_CYCLE_CAP,
    ATTR_CYCLE_CHRG,
    ATTR_DELTA_VOLTAGE,
    ATTR_POWER,
    ATTR_RUNTIME,
    ATTR_TEMPERATURE,
    ATTR_VOLTAGE,
    KEY_CELL_VOLTAGE,
    KEY_TEMP_VALUE,
)

type BMSsample = dict[str, int | float | bool]


class BaseBMS(metaclass=ABCMeta):
    """Base class for battery management system."""

    def __init__(
        self,
        logger: logging.Logger,
        notification_handler: Callable[
            [BleakGATTCharacteristic, bytearray], None | Awaitable[None]
        ],
        ble_device: BLEDevice,
        reconnect: bool = False,
    ) -> None:
        """Intialize the BMS.

        logger: logger for the BMS instance
        notification_handler: the callback used for notifications from 'uuid_rx()' characteristics
        ble_device: the Bleak device to connect to
        reconnect: if true, the connection will be closed after each update
        """
        self.logger: Final = logger
        self._notification_method: Final = notification_handler
        self._ble_device: Final = ble_device
        self._reconnect: Final = reconnect
        self._client = BleakClient(
            self._ble_device,
            disconnected_callback=self._on_disconnect,
            services=[*self.uuid_services()],
        )
        self.name: Final[str] = self._ble_device.name or "undefined"
        self._data_event: Final[asyncio.Event] = asyncio.Event()

    @staticmethod
    @abstractmethod
    def matcher_dict_list() -> list[dict[str, Any]]:
        """Return a list of Bluetooth matchers."""

    @staticmethod
    @abstractmethod
    def device_info() -> dict[str, str]:
        """Return a dictionary of device information.

        keys: manufacturer, model
        """

    @classmethod
    def device_id(cls) -> str:
        """Return device information as string."""
        return " ".join(cls.device_info().values())

    @classmethod
    def supported(cls, discovery_info: BluetoothServiceInfoBleak) -> bool:
        """Return true if service_info matches BMS type."""
        for matcher_dict in cls.matcher_dict_list():
            if ble_device_matches(
                BluetoothMatcherOptional(**matcher_dict), discovery_info
            ):
                return True
        return False

    @staticmethod
    @abstractmethod
    def uuid_services() -> list[str]:
        """Return list of 128-bit UUIDs of services required by BMS."""

    @staticmethod
    @abstractmethod
    def uuid_rx() -> str:
        """Return 16-bit UUID of characteristic that provides notification/read property."""

    @staticmethod
    @abstractmethod
    def uuid_tx() -> str:
        """Return 16-bit UUID of characteristic that provides write property."""

    @staticmethod
    def _calc_values() -> set[str]:
        """Return values that the BMS cannot provide and need to be calculated.

        See calc_values() function for the required input to actually do so.
        """
        return set()

    @staticmethod
    def _add_missing_values(data: BMSsample, values: set[str]):
        """Calculate missing BMS values from existing ones.

        data: data dictionary from BMS
        values: list of values to add to the dictionary
        """
        if not values:
            return

        def can_calc(value: str, using: frozenset[str]) -> bool:
            """Check value to add does not exist, is requested, and needed data is available."""
            return (value in values) and (value not in data) and using.issubset(data)

        # calculate total voltage (sum of all cell voltages)
        if can_calc(ATTR_VOLTAGE, frozenset({f"{KEY_CELL_VOLTAGE}0"})):
            cell_voltages = [
                v for k, v in data.items() if k.startswith(KEY_CELL_VOLTAGE)
            ]
            data[ATTR_VOLTAGE] = round(sum(cell_voltages), 3)

        # calculate delta voltage (maximum cell voltage difference)
        if can_calc(ATTR_DELTA_VOLTAGE, frozenset({f"{KEY_CELL_VOLTAGE}1"})):
            cell_voltages = [
                v for k, v in data.items() if k.startswith(KEY_CELL_VOLTAGE)
            ]
            data[ATTR_DELTA_VOLTAGE] = round(max(cell_voltages) - min(cell_voltages), 3)

        # calculate cycle capacity from voltage and cycle charge
        if can_calc(ATTR_CYCLE_CAP, frozenset({ATTR_VOLTAGE, ATTR_CYCLE_CHRG})):
            data[ATTR_CYCLE_CAP] = round(data[ATTR_VOLTAGE] * data[ATTR_CYCLE_CHRG], 3)

        # calculate current power from voltage and current
        if can_calc(ATTR_POWER, frozenset({ATTR_VOLTAGE, ATTR_CURRENT})):
            data[ATTR_POWER] = round(data[ATTR_VOLTAGE] * data[ATTR_CURRENT], 3)

        # calculate charge indicator from current
        if can_calc(ATTR_BATTERY_CHARGING, frozenset({ATTR_CURRENT})):
            data[ATTR_BATTERY_CHARGING] = data[ATTR_CURRENT] > 0

        # calculate runtime from current and cycle charge
        if (
            can_calc(ATTR_RUNTIME, frozenset({ATTR_CURRENT, ATTR_CYCLE_CHRG}))
            and data[ATTR_CURRENT] < 0
        ):
            data[ATTR_RUNTIME] = int(
                data[ATTR_CYCLE_CHRG] / abs(data[ATTR_CURRENT]) * _HRS_TO_SECS
            )
        # calculate temperature (average of all sensors)
        if can_calc(ATTR_TEMPERATURE, frozenset({f"{KEY_TEMP_VALUE}0"})):
            temp_values = [v for k, v in data.items() if k.startswith(KEY_TEMP_VALUE)]
            data[ATTR_TEMPERATURE] = round(fmean(temp_values), 3)

    def _on_disconnect(self, _client: BleakClient) -> None:
        """Disconnect callback function."""

        self.logger.debug("Disconnected from BMS (%s)", self.name)

    async def _init_characteristics(self) -> None:
        await self._client.start_notify(self.uuid_rx(), self._notification_method)

    async def _connect(self) -> None:
        """Connect to the BMS and setup notification if not connected."""

        if self._client.is_connected:
            self.logger.debug("BMS %s already connected", self.name)
            return

        self.logger.debug("Connecting BMS (%s)", self._ble_device.name)
        self._client = await establish_connection(
            client_class=BleakClient,
            device=self._ble_device,
            name=self._ble_device.address,
            disconnected_callback=self._on_disconnect,
            services=[*self.uuid_services()],
        )
        await self._init_characteristics()

    async def disconnect(self) -> None:
        """Disconnect the BMS, includes stoping notifications."""

        if self._client.is_connected:
            self.logger.debug("Disconnecting BMS (%s)", self.name)
            try:
                self._data_event.clear()
                await self._client.disconnect()
            except BleakError:
                self.logger.warning("Disconnect failed!")

    async def _wait_event(self) -> None:
        """Wait for data event and clear it."""
        await self._data_event.wait()
        self._data_event.clear()

    @abstractmethod
    async def _async_update(self) -> BMSsample:
        """Return a dictionary of BMS values (keys need to come from the SENSOR_TYPES list)."""

    async def async_update(self) -> BMSsample:
        """Retrieve updated values from the BMS using method of the subclass."""
        await self._connect()

        data = await self._async_update()

        self._add_missing_values(data, self._calc_values())

        if self._reconnect:
            # disconnect after data update to force reconnect next time (slow!)
            await self.disconnect()

        return data


def crc_xmodem(data: bytearray) -> int:
    """Calculate CRC-16-CCITT XMODEM (ModBus)."""
    crc: int = 0xFFFF
    for i in data:
        crc ^= i & 0xFF
        for _ in range(8):
            crc = (crc >> 1) ^ 0xA001 if crc % 2 else (crc >> 1)
    return ((0xFF00 & crc) >> 8) | ((crc & 0xFF) << 8)


def crc_sum(frame: bytes) -> int:
    """Calculate frame CRC."""
    return sum(frame) & 0xFF
