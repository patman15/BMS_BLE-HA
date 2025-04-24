"""Module to support Renogy BMS."""

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
    """Renogy battery class implementation."""

    _HEAD: Final[bytes] = b"\x30\x03"
    _CRC_POS: Final[int] = -2
    _TEMP_POS: Final[int] = 37
    _CELL_POS: Final[int] = 3
    _FIELDS: Final[list[tuple[str, int, int, bool, Callable[[int], int | float]]]] = [
        (ATTR_VOLTAGE, 5, 2, False, lambda x: float(x / 10)),
        (ATTR_CURRENT, 3, 2, True, lambda x: float(x / 10)),
        #        (ATTR_BATTERY_LEVEL, 7, 4, False, lambda x: x / 1000),
        (KEY_DESIGN_CAP, 11, 4, False, lambda x: x / 1000),
        (ATTR_CYCLE_CHRG, 7, 4, False, lambda x: float(x / 1000)),
        #        (ATTR_CYCLES, 12, 2, False, lambda x: x),
        #        (KEY_PROBLEM, 20, 2, False, lambda x: x),
    ]

    def __init__(self, ble_device: BLEDevice, reconnect: bool = False) -> None:
        """Initialize BMS."""
        super().__init__(__name__, ble_device, reconnect)

    @staticmethod
    def matcher_dict_list() -> list[dict]:
        """Provide BluetoothMatcher definition."""
        return [
            {
                "service_uuid": BMS.uuid_services()[0],
                "manufacturer_id": 0x9860,
                "connectable": True,
            }
        ]

    @staticmethod
    def device_info() -> dict[str, str]:
        """Return device information for the battery management system."""
        return {"manufacturer": "Renogy", "model": "Bluetooth battery"}

    @staticmethod
    def uuid_services() -> list[str]:
        """Return list of 128-bit UUIDs of services required by BMS."""
        return [normalize_uuid_str("ffd0"), normalize_uuid_str("fff0")]

    @staticmethod
    def uuid_rx() -> str:
        """Return 16-bit UUID of characteristic that provides notification/read property."""
        return "fff1"

    @staticmethod
    def uuid_tx() -> str:
        """Return 16-bit UUID of characteristic that provides write property."""
        return "ffd1"

    @staticmethod
    def _calc_values() -> frozenset[str]:
        return frozenset(
            {
                ATTR_POWER,
                ATTR_BATTERY_CHARGING,
                ATTR_TEMPERATURE,
                ATTR_CYCLE_CAP,
                ATTR_BATTERY_LEVEL,
                ATTR_RUNTIME,
                ATTR_DELTA_VOLTAGE,
            }
        )  # calculate further values from BMS provided set ones

    def _notification_handler(
        self, _sender: BleakGATTCharacteristic, data: bytearray
    ) -> None:
        """Handle the RX characteristics notify event (new data arrives)."""
        self._log.debug("RX BLE data: %s", data)

        if not data.startswith(BMS._HEAD) or len(data) < 3:
            self._log.debug("incorrect SOF")
            return

        if data[2] + 5 != len(data):
            self._log.debug("incorrect frame length: %i != %i", len(data), data[2] + 5)
            return

        if (crc := crc_modbus(data[: BMS._CRC_POS])) != int.from_bytes(
            data[BMS._CRC_POS :], "little"
        ):
            self._log.debug(
                "invalid checksum 0x%X != 0x%X",
                crc,
                int.from_bytes(data[BMS._CRC_POS :], "little"),
            )
            return

        self._data = data.copy()

        self._data_event.set()

    @staticmethod
    def _decode_data(data: bytearray) -> dict[str, int | float]:
        return {
            key: func(
                int.from_bytes(data[idx : idx + size], byteorder="big", signed=sign)
            )
            for key, idx, size, sign, func in BMS._FIELDS
        }

    @staticmethod
    def _cell_voltages(data: bytearray) -> dict[str, int | float]:
        """Return cell voltages from status message."""
        cells: Final[int] = min(16, data[BMS._CELL_POS + 1])  # max is 16, second byte
        return {KEY_CELL_COUNT: cells} | {
            f"{KEY_CELL_VOLTAGE}{idx}": int.from_bytes(
                data[BMS._CELL_POS + 2 + 2 * idx : BMS._CELL_POS + 4 + 2 * idx],
                byteorder="big",
            )
            / 10
            for idx in range(cells)
        }

    @staticmethod
    def _temp_sensors(data: bytearray) -> dict[str, float]:
        sensors: Final[int] = min(16, data[BMS._TEMP_POS + 1])  # max is 16, second byte
        return {KEY_TEMP_SENS: sensors} | {
            f"{KEY_TEMP_VALUE}{idx}": int.from_bytes(
                data[BMS._TEMP_POS + 2 + 2 * idx : BMS._TEMP_POS + 4 + 2 * idx],
                byteorder="big",
            )
            / 10
            for idx in range(sensors)
        }

    @staticmethod
    def _cmd(cmd: bytes) -> bytes:
        """Assemble a Seplos BMS command."""
        frame: bytearray = bytearray([*BMS._HEAD, *cmd])
        frame.extend(int.to_bytes(crc_modbus(frame), 2, byteorder="little"))
        return bytes(frame)

    async def _async_update(self) -> BMSsample:
        """Update battery status information."""

        await self._await_reply(self._cmd(b"\x13\xb2\x00\x06"))
        result: BMSsample = BMS._decode_data(self._data)

        await self._await_reply(self._cmd(b"\x13\x88\x00\x22"))
        result |= BMS._cell_voltages(self._data) | BMS._temp_sensors(self._data)

        return result
