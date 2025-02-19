"""Module to support Dummy BMS."""

from collections.abc import Callable
from typing import Final

from bleak.backends.characteristic import BleakGATTCharacteristic
from bleak.backends.device import BLEDevice
from bleak.uuids import normalize_uuid_str

from custom_components.bms_ble.const import (
    ATTR_BATTERY_CHARGING,
    ATTR_BATTERY_LEVEL,
    ATTR_CURRENT,
    ATTR_CYCLE_CAP,
    ATTR_CYCLE_CHRG,
    # ATTR_CYCLES,
    ATTR_DELTA_VOLTAGE,
    ATTR_POWER,
    ATTR_RUNTIME,
    ATTR_TEMPERATURE,
    ATTR_VOLTAGE,
    KEY_CELL_COUNT,
    KEY_CELL_VOLTAGE,
    KEY_DESIGN_CAP,
    KEY_TEMP_SENS,
    KEY_TEMP_VALUE,
)

from .basebms import BaseBMS, BMSsample, crc_modbus


class BMS(BaseBMS):
    """Dummy battery class implementation."""

    _HEAD: Final[list[int]] = [0xA1, 0xA2]
    _CELL_POS: Final[int] = 14
    _TEMP_POS: Final[int] = 80
    _FIELDS: Final[
        list[tuple[str, int, int, int, bool, Callable[[int], int | float]]]
    ] = [
        (ATTR_BATTERY_LEVEL, 0xA1, 16, 2, False, lambda x: x),
        (ATTR_VOLTAGE, 0xA1, 20, 2, False, lambda x: float(x / 100)),
        (ATTR_CURRENT, 0xA1, 22, 2, True, lambda x: float(x / 100)),
        # (ATTR_CYCLE_CHRG, 0xA1, 16, 2, False, lambda x: float(x / 10)),
        (KEY_DESIGN_CAP, 0xA1, 26, 2, False, lambda x: float(x / 100)),
        (KEY_CELL_COUNT, 0xA2, _CELL_POS, 2, False, lambda x: x),
        (KEY_TEMP_SENS, 0xA2, _TEMP_POS, 2, False, lambda x: x),
        # (ATTR_CYCLES, 0xA1, 8, 2, False, lambda x: x),
    ]

    def __init__(self, ble_device: BLEDevice, reconnect: bool = False) -> None:
        """Initialize BMS."""
        super().__init__(__name__, ble_device, reconnect)
        self._data_final: dict[int, bytearray] = {}

    @staticmethod
    def matcher_dict_list() -> list[dict]:
        """Provide BluetoothMatcher definition."""
        return [
            {
                "local_name": "ECO-WORTHY*",
                "manufacturer_id": 0xC2B4,
                "connectable": True,
            }
        ]

    @staticmethod
    def device_info() -> dict[str, str]:
        """Return device information for the battery management system."""
        return {"manufacturer": "ECO-WORTHY", "model": "BW02"}

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

    def _notification_handler(
        self, _sender: BleakGATTCharacteristic, data: bytearray
    ) -> None:
        """Handle the RX characteristics notify event (new data arrives)."""
        self._log.debug("RX BLE data: %s", data)

        if data[0] not in BMS._HEAD:
            self._log.debug("Invalid frame type: 0x%X", data[0])
            return

        crc: Final[int] = crc_modbus(data[:-2])
        if int.from_bytes(data[-2:], "little") != crc:
            self._log.debug(
                "invalid checksum 0x%X != 0x%X",
                int.from_bytes(data[-2:], "little"),
                crc,
            )
            self._data = bytearray()
            return

        self._data_final[data[0]] = data.copy()
        self._data_event.set()

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
    def _cell_voltages(data: bytearray, cells: int, offs: int) -> dict[str, float]:
        return {KEY_CELL_COUNT: cells} | {
            f"{KEY_CELL_VOLTAGE}{idx}": float(
                int.from_bytes(
                    data[offs + idx * 2 : offs + idx * 2 + 2],
                    byteorder="big",
                    signed=False,
                )
            )
            / 1000
            for idx in range(cells)
        }

    @staticmethod
    def _temp_sensors(data: bytearray, sensors: int, offs: int) -> dict[str, float]:
        return {
            f"{KEY_TEMP_VALUE}{idx}": (
                int.from_bytes(
                    data[offs + idx * 2 : offs + (idx + 1) * 2],
                    byteorder="big",
                    signed=True,
                )
            )
            / 10
            for idx in range(sensors)
        }

    async def _async_update(self) -> BMSsample:
        """Update battery status information."""
        # await self._send(b"<some_command>")

        result: BMSsample = BMS._decode_data(self._data_final)

        # get cycle charge from design capacity and SoC
        if result.get(KEY_DESIGN_CAP) and result.get(ATTR_BATTERY_LEVEL):
            result[ATTR_CYCLE_CHRG] = (
                result[KEY_DESIGN_CAP] * result[ATTR_BATTERY_LEVEL] / 100
            )

        result |= BMS._cell_voltages(
            self._data_final[0xA2],
            int(result.get(KEY_CELL_COUNT, 0)),
            BMS._CELL_POS + 2,
        )
        result |= BMS._temp_sensors(
            self._data_final[0xA2], int(result.get(KEY_TEMP_SENS, 0)), BMS._TEMP_POS + 2
        )

        return result
