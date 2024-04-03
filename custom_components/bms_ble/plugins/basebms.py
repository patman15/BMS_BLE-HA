from abc import ABCMeta, abstractmethod
from typing import Any

from homeassistant.components.bluetooth import BluetoothServiceInfoBleak
from homeassistant.components.bluetooth.match import (
    BluetoothMatcherOptional,
    ble_device_matches,
)


class BaseBMS(metaclass=ABCMeta):
    """Base class for battery management system"""

    def __init__(self) -> None:
        pass

    @staticmethod
    @abstractmethod
    def matcher_dict_list() -> list[dict[str, Any]]:
        pass

    @staticmethod
    @abstractmethod
    def device_info() -> dict[str, str]:
        """Returns a dictionary of device information
        keys: manufacturer, model
        """
        pass

    @classmethod
    def device_id(cls) -> str:
        """Return device information as string"""
        return " ".join(cls.device_info().values())

    @classmethod
    def supported(cls, discovery_info: BluetoothServiceInfoBleak) -> bool:
        """Returns true if service_info matches BMS type"""
        for matcher_dict in cls.matcher_dict_list():
            if ble_device_matches(
                BluetoothMatcherOptional(**matcher_dict), discovery_info
            ):
                return True
        return False

    async def disconnect(self) -> None:
        """Disconnect connection to BMS if active"""
        pass

    @abstractmethod
    async def async_update(self) -> dict[str, float]:
        """Retrieve updated values from the BMS

        Returns a dictionary of BMS values, where the keys need to match the keys in the SENSOR_TYPES list.
        """
        pass
