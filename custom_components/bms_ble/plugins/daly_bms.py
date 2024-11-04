"""Module to support Daly Smart BMS."""

import asyncio
from collections.abc import Callable
import logging
from typing import Any, Final

from bleak.backends.device import BLEDevice
from bleak.uuids import normalize_uuid_str
from custom_components.bms_ble.const import (
    ATTR_BATTERY_CHARGING,
    ATTR_BATTERY_LEVEL,
    ATTR_CURRENT,
    ATTR_CYCLE_CAP,
    ATTR_CYCLE_CHRG,
    ATTR_CYCLES,
    ATTR_DELTA_VOLTAGE,
    ATTR_POWER,
    ATTR_RUNTIME,
    ATTR_TEMPERATURE,
    ATTR_VOLTAGE,
    KEY_CELL_COUNT,
    KEY_CELL_VOLTAGE,
    KEY_TEMP_SENS,
    KEY_TEMP_VALUE,
)
from custom_components.bms_ble.plugins.basebms import BaseBMS, BMSsample, crc_xmodem

BAT_TIMEOUT: Final = 10
LOGGER: Final = logging.getLogger(__name__)


class BMS(BaseBMS):
    """Daly Smart BMS class implementation."""

    HEAD_READ: Final = bytearray(b"\xD2\x03")
    CMD_INFO: Final = bytearray(b"\x00\x00\x00\x3E\xD7\xB9")
    MOS_INFO: Final = bytearray(b"\x00\x3E\x00\x09\xF7\xA3")
    HEAD_LEN: Final = 3
    CRC_LEN: Final = 2
    MAX_CELLS: Final = 32
    MAX_TEMP: Final = 8
    INFO_LEN: Final = 84 + HEAD_LEN + CRC_LEN + MAX_CELLS + MAX_TEMP
    MOS_TEMP_POS: Final = HEAD_LEN + 8

    def __init__(self, ble_device: BLEDevice, reconnect: bool = False) -> None:
        """Intialize private BMS members."""
        super().__init__(LOGGER, self._notification_handler, ble_device, reconnect)
        self._data: bytearray | None = None
        self._FIELDS: Final[list[tuple[str, int, Callable[[int], int | float]]]] = [
            (ATTR_VOLTAGE, 80 + self.HEAD_LEN, lambda x: float(x / 10)),
            (ATTR_CURRENT, 82 + self.HEAD_LEN, lambda x: float((x - 30000) / 10)),
            (ATTR_BATTERY_LEVEL, 84 + self.HEAD_LEN, lambda x: float(x / 10)),
            (ATTR_CYCLE_CHRG, 96 + self.HEAD_LEN, lambda x: float(x / 10)),
            (KEY_CELL_COUNT, 98 + self.HEAD_LEN, lambda x: min(x, self.MAX_CELLS)),
            (KEY_TEMP_SENS, 100 + self.HEAD_LEN, lambda x: min(x, self.MAX_TEMP)),
            (ATTR_CYCLES, 102 + self.HEAD_LEN, lambda x: x),
            (ATTR_DELTA_VOLTAGE, 112 + self.HEAD_LEN, lambda x: float(x / 1000)),
        ]

    @staticmethod
    def matcher_dict_list() -> list[dict[str, Any]]:
        """Provide BluetoothMatcher definition."""
        return [
            {
                "local_name": "DL-*",
                "service_uuid": BMS.uuid_services()[0],
                "connectable": True,
            }
        ]

    @staticmethod
    def device_info() -> dict[str, str]:
        """Return device information for the battery management system."""
        return {"manufacturer": "Daly", "model": "Smart BMS"}

    @staticmethod
    def uuid_services() -> list[str]:
        """Return list of 128-bit UUIDs of services required by BMS"""
        return [normalize_uuid_str("fff0")]

    @staticmethod
    def uuid_rx() -> str:
        """Return 16-bit UUID of characteristic that provides notification/read property."""
        return "fff1"

    @staticmethod
    def uuid_tx() -> str:
        """Return 16-bit UUID of characteristic that provides write property."""
        return "fff2"

    def _notification_handler(self, _sender, data: bytearray) -> None:
        LOGGER.debug("Received BLE data: %s", data)

        if (
            len(data) < 3
            or data[0:2] != self.HEAD_READ
            or int(data[2]) + 1 != len(data) - len(self.HEAD_READ) - self.CRC_LEN
            or int.from_bytes(data[-2:], byteorder="big") != crc_xmodem(data[:-2])
        ):
            LOGGER.debug(
                "Response data is invalid, CRC: %s/%s",
                data[-2:],
                bytearray(crc_xmodem(data[:-2]).to_bytes(2)),
            )
            self._data = None
        else:
            self._data = data

        self._data_event.set()

    async def _async_update(self) -> BMSsample:
        """Update battery status information."""
        await self._client.write_gatt_char(
            BMS.uuid_tx(), data=self.HEAD_READ + self.MOS_INFO
        )
        await asyncio.wait_for(self._wait_event(), timeout=BAT_TIMEOUT)

        data = {}
        if self._data is not None and sum(self._data[self.MOS_TEMP_POS :][:2]):
            LOGGER.debug("%s: MOS info: %s", self._ble_device.name, self._data)
            data |= {
                f"{KEY_TEMP_VALUE}0": float(
                    int.from_bytes(
                        self._data[self.MOS_TEMP_POS :][:2],
                        byteorder="big",
                        signed=True,
                    )
                    - 40
                )
            }

        await self._client.write_gatt_char(
            BMS.uuid_tx(), data=self.HEAD_READ + self.CMD_INFO
        )

        await asyncio.wait_for(self._wait_event(), timeout=BAT_TIMEOUT)

        if self._data is None or len(self._data) != self.INFO_LEN:
            return {}

        data |= {
            key: func(
                int.from_bytes(self._data[idx : idx + 2], byteorder="big", signed=True)
            )
            for key, idx, func in self._FIELDS
        }

        # get temperatures
        # shift index if MOS temperature is available
        t_off: Final[int] = 1 if f"{KEY_TEMP_VALUE}0" in data else 0
        data |= {
            f"{KEY_TEMP_VALUE}{((idx-64-self.HEAD_LEN)>>1) + t_off}": float(
                int.from_bytes(self._data[idx : idx + 2], byteorder="big", signed=True)
                - 40
            )
            for idx in range(
                64 + self.HEAD_LEN, 64 + self.HEAD_LEN + int(data[KEY_TEMP_SENS]) * 2, 2
            )
        }

        # get cell voltages
        data |= {
            f"{KEY_CELL_VOLTAGE}{idx}": float(
                int.from_bytes(
                    self._data[self.HEAD_LEN + 2 * idx : self.HEAD_LEN + 2 * idx + 2],
                    byteorder="big",
                    signed=True,
                )
                / 1000
            )
            for idx in range(int(data[KEY_CELL_COUNT]))
        }

        self.calc_values(
            data,
            {
                ATTR_CYCLE_CAP,
                ATTR_POWER,
                ATTR_BATTERY_CHARGING,
                ATTR_RUNTIME,
                ATTR_TEMPERATURE,
            },
        )

        return data
