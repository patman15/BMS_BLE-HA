"""Base class defintion for battery management systems (BMS)."""

from abc import ABCMeta, abstractmethod
from statistics import fmean
from typing import Any

from bleak.backends.device import BLEDevice

from homeassistant.components.bluetooth import BluetoothServiceInfoBleak
from homeassistant.components.bluetooth.match import (
    BluetoothMatcherOptional,
    ble_device_matches,
)
from homeassistant.util.unit_conversion import _HRS_TO_SECS

from ..const import (
    ATTR_BATTERY_CHARGING,
    ATTR_CURRENT,
    ATTR_CYCLE_CAP,
    ATTR_CYCLE_CHRG,
    ATTR_DELTA_VOLTAGE,
    ATTR_POWER,
    ATTR_RUNTIME,
    ATTR_VOLTAGE,
    ATTR_TEMPERATURE,
    KEY_CELL_VOLTAGE,
    KEY_TEMP_VALUE,
)

type BMSsample = dict[str, int | float | bool]


class BaseBMS(metaclass=ABCMeta):
    """Base class for battery management system."""

    def __init__(self, ble_device: BLEDevice, reconnect: bool = False) -> None:
        """Intialize the BMS.

        ble_device: the Bleak device to connect to
        reconnect: if true, the connection will be closed after each update
        """

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

    @classmethod
    def calc_values(cls, data: BMSsample, values: set[str]):
        """Calculate missing BMS values from existing ones.

        data: data dictionary from BMS
        values: list of values to add to the dictionary
        """

        def can_calc(value: str, using: frozenset[str]) -> bool:
            """Check that value to add does not exist, is requested, and needed parameters are available."""
            return (value in values) and (value not in data) and using.issubset(data)

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
        if can_calc(ATTR_RUNTIME, frozenset({ATTR_CURRENT, ATTR_CYCLE_CHRG})):
            if data[ATTR_CURRENT] < 0:
                data[ATTR_RUNTIME] = int(
                    data[ATTR_CYCLE_CHRG] / abs(data[ATTR_CURRENT]) * _HRS_TO_SECS
                )
        # calculate delta voltage (maximum cell voltage difference)
        if can_calc(ATTR_DELTA_VOLTAGE, frozenset({f"{KEY_CELL_VOLTAGE}1"})):
            cell_voltages = [
                v for k, v in data.items() if k.startswith(KEY_CELL_VOLTAGE)
            ]
            data[ATTR_DELTA_VOLTAGE] = round(max(cell_voltages) - min(cell_voltages), 3)
        # calculate temperature (average of all sensors)
        if can_calc(ATTR_TEMPERATURE, frozenset({f"{KEY_TEMP_VALUE}0"})):
            temp_values = [v for k, v in data.items() if k.startswith(KEY_TEMP_VALUE)]
            data[ATTR_TEMPERATURE] = round(fmean(temp_values),3)

    async def disconnect(self) -> None:
        """Disconnect connection to BMS if active."""

    @abstractmethod
    async def async_update(self) -> BMSsample:
        """Retrieve updated values from the BMS.

        Returns a dictionary of BMS values, where the keys need to match
        the keys in the SENSOR_TYPES list.
        """


def crc_xmodem(data: bytearray) -> int:
    """Calculate CRC-16-CCITT XMODEM (ModBus)."""
    crc: int = 0xFFFF
    for i in data:
        crc ^= i & 0xFF
        for _ in range(8):
            crc = (crc >> 1) ^ 0xA001 if crc % 2 else (crc >> 1)
    return ((0xFF00 & crc) >> 8) | ((crc & 0xFF) << 8)
