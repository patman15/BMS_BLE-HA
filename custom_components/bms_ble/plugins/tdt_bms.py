"""Module to support TDT BMS."""

import asyncio
import logging
from typing import Any, Callable, Final

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

from .basebms import BaseBMS, BMSsample, crc_modbus

LOGGER = logging.getLogger(__name__)
BAT_TIMEOUT = 5


class BMS(BaseBMS):
    """Dummy battery class implementation."""

    _HEAD: Final[int] = 0x7E
    _TAIL: Final[int] = 0x0D
    _CMD_VER: Final[int] = 0x10
    _RSP_VER: Final[int] = 0x14
    _INFO_LEN: Final[int] = 10  # minimal frame length
    _FIELDS: Final[
        list[tuple[str, int, int, int, bool, Callable[[int], int | float]]]
    ] = [
        (ATTR_VOLTAGE, 0x8C, 56, 2, False, lambda x: float(x / 100)),
        (
            ATTR_CURRENT,
            0x8C,
            54,
            2,
            False,
            lambda x: float((x & 0x3FFF) / 10 * (-1 if x >> 15 else 1)),
        ),
        (ATTR_CYCLE_CHRG, 0x8C, 58, 2, False, lambda x: float(x / 10)),
        (ATTR_BATTERY_LEVEL, 0x8C, 67, 1, False, lambda x: x),
        (ATTR_CYCLES, 0x8C, 62, 2, False, lambda x: x),
        (KEY_CELL_COUNT, 0x8C, 8, 1, False, lambda x: x),
        (KEY_TEMP_SENS, 0x8C, 41, 1, False, lambda x: x),
    ]
    _CMDS: Final[list[int]] = list({field[1] for field in _FIELDS})

    def __init__(self, ble_device: BLEDevice, reconnect: bool = False) -> None:
        """Initialize BMS."""
        LOGGER.debug("%s init(), BT address: %s", self.device_id(), ble_device.address)
        super().__init__(LOGGER, self._notification_handler, ble_device, reconnect)
        self._data: bytearray = bytearray()
        self._exp_len: int = 0
        self._data_final: dict[int, bytearray] = {}

    @staticmethod
    def matcher_dict_list() -> list[dict[str, Any]]:
        """Provide BluetoothMatcher definition."""
        return [
            {
                "local_name": "XDZN*",
                "service_uuid": BMS.uuid_services()[0],
                "connectable": True,
            }
        ]

    @staticmethod
    def device_info() -> dict[str, str]:
        """Return device information for the battery management system."""
        return {"manufacturer": "TDT", "model": "Smart BMS"}

    @staticmethod
    def uuid_services() -> list[str]:
        """Return list of 128-bit UUIDs of services required by BMS."""
        return [normalize_uuid_str("fff0")]

    @staticmethod
    def uuid_rx() -> str:
        """Return 16-bit UUID of characteristic that provides notification/read property."""
        return "fff1"

    @staticmethod
    def uuid_tx() -> str:
        """Return 16-bit UUID of characteristic that provides write property."""
        return "fff2"

    @staticmethod
    def _calc_values() -> set[str]:
        return {
            ATTR_BATTERY_CHARGING,
            ATTR_CYCLE_CAP,
            ATTR_DELTA_VOLTAGE,
            ATTR_POWER,
            ATTR_RUNTIME,
            ATTR_TEMPERATURE,
        }  # calculate further values from BMS provided set ones

    def _notification_handler(self, _sender, data: bytearray) -> None:
        """Handle the RX characteristics notify event (new data arrives)."""
        LOGGER.debug("%s: Received BLE data: %s", self.name, data)

        if (
            data[0] == BMS._HEAD
            and len(data) > BMS._INFO_LEN
            and len(self._data) >= self._exp_len
        ):
            self._exp_len = BMS._INFO_LEN + int.from_bytes(data[6:8])
            self._data = bytearray()

        self._data += data
        LOGGER.debug(
            "%s: RX BLE data (%s): %s",
            self._ble_device.name,
            "start" if data == self._data else "cnt.",
            data,
        )

        # verify that data long enough
        if len(self._data) < self._exp_len:
            return

        if self._data[-1] != BMS._TAIL:
            LOGGER.debug("%s: frame end incorrect: %s", self.name, self._data)
            return

        if self._data[4]:
            LOGGER.debug("%s: BMS reported error code: 0x%X", self.name, self._data[4])
            return

        crc = crc_modbus(self._data[:-3])
        if int.from_bytes(self._data[-3:-1], "little") != crc:
            LOGGER.debug(
                "%s: RX data CRC is invalid: 0x%X != 0x%X",
                self._ble_device.name,
                int.from_bytes(self._data[-3:-1], "little"),
                crc,
            )
            return
        self._data_final[self._data[5]] = self._data
        self._data_event.set()

    @staticmethod
    def _cmd(cmd: int, data: bytearray = bytearray()) -> bytearray:
        """Assemble a TDT BMS command."""
        assert cmd in (0x8C, 0x8D, 0x92)  # allow only read commands
        frame = bytearray([BMS._HEAD, 0x0, 0x1, 0x3, 0x0, cmd])  # fixed version
        frame += len(data).to_bytes(2, "big", signed=False) + data
        frame += bytearray(int.to_bytes(crc_modbus(frame), 2, byteorder="little"))
        frame += bytearray([BMS._TAIL])
        return frame

    @staticmethod
    def _decode_data(data: dict[int, bytearray]) -> dict[str, int | float]:
        return {
            key: func(
                int.from_bytes(
                    data[cmd][idx : idx + size], byteorder="big", signed=sign
                )
            )
            for key, cmd, idx, size, sign, func in BMS._FIELDS
        }

    @staticmethod
    def _cell_voltages(data: bytearray) -> dict[str, float]:
        return {
            f"{KEY_CELL_VOLTAGE}{idx}": float(
                int.from_bytes(
                    data[9 + idx * 2 : 9 + idx * 2 + 2], byteorder="big", signed=False
                )
            )
            / 1000
            for idx in range(data[8])
        }

    @staticmethod
    def _temp_sensors(data: bytearray, sensors: int) -> dict[str, float]:
        return {
            f"{KEY_TEMP_VALUE}{idx}": (
                int.from_bytes(
                    data[42 + idx * 2 : 44 + idx * 2],
                    byteorder="big",
                    signed=False,
                )
                - 2731.5
            )
            / 10
            for idx in range(sensors)
            if int.from_bytes(
                data[42 + idx * 2 : 44 + idx * 2],
                byteorder="big",
                signed=False,
            )
        }

    async def _async_update(self) -> BMSsample:
        """Update battery status information."""

        for cmd in BMS._CMDS:
            await self._client.write_gatt_char(BMS.uuid_tx(), data=BMS._cmd(cmd))
            await asyncio.wait_for(self._wait_event(), timeout=BAT_TIMEOUT)
            # check if a valid frame was received otherwise terminate immediately
            if cmd not in self._data_final:
                return {}

        result = BMS._decode_data(self._data_final)
        result |= BMS._cell_voltages(self._data_final[0x8C])
        result |= BMS._temp_sensors(
            self._data_final[0x8C], int(result.get(KEY_TEMP_SENS, 0))
        )

        self._data_final.clear()

        return result
