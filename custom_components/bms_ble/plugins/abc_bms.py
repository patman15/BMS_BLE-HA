"""Module to support ABC BMS."""

from collections.abc import Callable
from typing import Final

from bleak.backends.characteristic import BleakGATTCharacteristic
from bleak.backends.device import BLEDevice
from bleak.uuids import normalize_uuid_str

from custom_components.bms_ble.const import (
    ATTR_BATTERY_CHARGING,
    ATTR_BATTERY_LEVEL,
    ATTR_CURRENT,
    # ATTR_CYCLE_CAP,
    ATTR_CYCLE_CHRG,
    ATTR_CYCLES,
    # ATTR_DELTA_VOLTAGE,
    ATTR_POWER,
    # ATTR_RUNTIME,
    # ATTR_TEMPERATURE,
    ATTR_VOLTAGE,
    KEY_DESIGN_CAP,
)

from .basebms import BaseBMS, BMSsample, crc8


class BMS(BaseBMS):
    """ABC battery class implementation."""

    _HEAD_CMD: Final[int] = 0xEE
    _HEAD_RESP: Final[int] = 0xCC
    _INFO_LEN: Final[int] = 0x14
    _FIELDS: Final[
        list[tuple[str, int, int, int, bool, Callable[[int], int | float]]]
    ] = [
        #        (KEY_TEMP_SENS, 26, 1, False, lambda x: x),  # count is not limited
        (ATTR_VOLTAGE, 0xF0, 2, 3, False, lambda x: float(x / 1000)),
        (ATTR_CURRENT, 0xF0, 5, 3, True, lambda x: float(x / 100)),
        (KEY_DESIGN_CAP, 0xF0, 8, 3, False, lambda x: float(x / 1000)),
        (ATTR_BATTERY_LEVEL, 0xF0, 16, 1, False, lambda x: x),
        (ATTR_CYCLE_CHRG, 0xF0, 11, 3, False, lambda x: float(x / 1000)),
        (ATTR_CYCLES, 0xF0, 14, 2, False, lambda x: x),
        #        (KEY_PROBLEM, 20, 2, False, lambda x: x),
    ]  # general protocol v4
    _RESPS: Final[set[int]] = {field[1] for field in _FIELDS} | {
        field[1] for field in _FIELDS
    }

    def __init__(self, ble_device: BLEDevice, reconnect: bool = False) -> None:
        """Initialize BMS."""
        super().__init__(__name__, ble_device, reconnect)
        self._data_final: dict[int, bytearray] = {}

    @staticmethod
    def matcher_dict_list() -> list[dict]:
        """Provide BluetoothMatcher definition."""
        return [
            {
                "local_name": pattern,
                "service_uuid": normalize_uuid_str("fff0"),
                "connectable": True,
            }
            for pattern in ["SOK-*", "ABC-*"] # "NB-*", "Hoover",
        ]

    @staticmethod
    def device_info() -> dict[str, str]:
        """Return device information for the battery management system."""
        return {"manufacturer": "Chunguang Song", "model": "ABC BMS"}

    @staticmethod
    def uuid_services() -> list[str]:
        """Return list of 128-bit UUIDs of services required by BMS."""
        return [normalize_uuid_str("ffe0")]

    @staticmethod
    def uuid_rx() -> str:
        """Return 16-bit UUID of characteristic that provides notification/read property."""
        return "ffe1"

    @staticmethod
    def uuid_tx() -> str:
        """Return 16-bit UUID of characteristic that provides write property."""
        return "ffe2"

    @staticmethod
    def _calc_values() -> set[str]:
        return {
            ATTR_POWER,
            ATTR_BATTERY_CHARGING,
        }  # calculate further values from BMS provided set ones

    def _notification_handler(
        self, _sender: BleakGATTCharacteristic, data: bytearray
    ) -> None:
        """Handle the RX characteristics notify event (new data arrives)."""
        self._log.debug("RX BLE data: %s", data)

        if data[0] != BMS._HEAD_RESP:
            self._log.debug("Incorrect frame start")
            return

        if len(data) != BMS._INFO_LEN:
            self._log.debug("Incorrect frame length")
            return

        if (crc := crc8(data[:-1])) != data[-1]:
            self._log.debug("invalid checksum 0x%X != 0x%X", data[-1], crc)
            return

        # TODO: wait for right response
        self._data_final[data[1]] = data.copy()
        self._data_event.set()

    @staticmethod
    def _cmd(cmd: bytes) -> bytes:
        """Assemble a ABC BMS command."""
        frame = bytearray([BMS._HEAD_CMD, cmd[0], 0x00, 0x00, 0x00])
        frame += bytes([crc8(frame)])
        return frame

    @staticmethod
    def _decode_data(data: dict[int, bytearray]) -> dict[str, int | float]:
        return {
            key: func(
                int.from_bytes(
                    data[cmd][idx : idx + size],
                    byteorder="little",
                    signed=sign,
                )
            )
            for key, cmd, idx, size, sign, func in BMS._FIELDS
        }

    async def _async_update(self) -> BMSsample:
        """Update battery status information."""
        self._data_final.clear()
        for cmd in range(4):
            await self._await_reply(BMS._cmd(bytes([cmd])))
        if not BMS._RESPS.issubset(set(self._data_final.keys())):
            self._log.debug("Incomplete data set")
            return {}

        return BMS._decode_data(self._data_final)
