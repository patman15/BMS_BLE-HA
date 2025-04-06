"""Module to support CBT Power VB series BMS."""

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
    # ATTR_CYCLE_CHRG,
    ATTR_CYCLES,
    # ATTR_DELTA_VOLTAGE,
    ATTR_POWER,
    ATTR_RUNTIME,
    # ATTR_TEMPERATURE,
    ATTR_VOLTAGE,
    KEY_CELL_VOLTAGE,
    KEY_PROBLEM,
)

from .basebms import BaseBMS, BMSsample, crc_sum


class BMS(BaseBMS):
    """CBT Power VB series battery class implementation."""

    HEAD: Final[bytes] = bytes([0xAA, 0x55])
    TAIL: Final[bytes] = bytes([0x55, 0xAA])
    MIN_FRAME: Final[int] = 9

    _FIELDS: Final[list[tuple[str, int, int, bool, Callable[[int], int | float]]]] = [
        (ATTR_VOLTAGE, 28, 4, False, lambda x: float(x) / 1000),
        (ATTR_CURRENT, 32, 4, True, lambda x: float(x) / 1000),
        # (ATTR_TEMPERATURE, 4, 2, True, lambda x: x),
        (ATTR_BATTERY_LEVEL, 24, 4, False, lambda x: x / 100),
        # (KEY_DESIGN_CAP, 0x15, 4, 2, False, lambda x: x),
        (ATTR_CYCLES, 40, 2, False, lambda x: x),
        (KEY_PROBLEM, 69, 4, False, lambda x: x),
    ]

    def __init__(self, ble_device: BLEDevice, reconnect: bool = False) -> None:
        """Initialize BMS."""
        super().__init__(__name__, ble_device, reconnect)

    @staticmethod
    def matcher_dict_list() -> list[dict]:
        """Provide BluetoothMatcher definition."""
        return [
            {  # Creabest
                "service_uuid": normalize_uuid_str("fff0"),
                "manufacturer_id": 16963,
                "connectable": True,
            },
        ]

    @staticmethod
    def device_info() -> dict[str, str]:
        """Return device information for the battery management system."""
        return {"manufacturer": "CBT Power", "model": "VB series"}

    @staticmethod
    def uuid_services() -> list[str]:
        """Return list of 128-bit UUIDs of services required by BMS."""
        return [normalize_uuid_str("fff0")]  # change service UUID here!

    @staticmethod
    def uuid_rx() -> str:
        """Return 16-bit UUID of characteristic that provides notification/read property."""
        return "fff1"

    @staticmethod
    def uuid_tx() -> str:
        """Return 16-bit UUID of characteristic that provides write property."""
        return "fff2"

    @staticmethod
    def _calc_values() -> frozenset[str]:
        return frozenset(
            {ATTR_POWER, ATTR_BATTERY_CHARGING, ATTR_RUNTIME}
        )  # calculate further values from BMS provided set ones

    def _notification_handler(
        self, _sender: BleakGATTCharacteristic, data: bytearray
    ) -> None:
        """Handle the RX characteristics notify event (new data arrives)."""
        self._log.debug("RX BLE data: %s", data)

        # verify that data is long enough
        if len(data) < BMS.MIN_FRAME:
            self._log.debug("incorrect frame length (%i): %s", len(data), data)
            return

        if not data.startswith(BMS.HEAD) or not data.endswith(BMS.TAIL):
            self._log.debug("incorrect frame start/end: %s", data)
            return

        if (crc := crc_sum(data[5:-5], 2)) != int.from_bytes(
            data[-4:-2], byteorder="little", signed=False
        ):
            self._log.debug(
                "invalid checksum 0x%X != 0x%X",
                crc,
                int.from_bytes(data[-4:-2], byteorder="little", signed=False),
            )
            return

        self._data = data
        self._data_event.set()

    @staticmethod
    def _cell_voltages(data: bytearray) -> dict[str, float]:
        """Return cell voltages from status message."""
        return {
            f"{KEY_CELL_VOLTAGE}{idx}": int.from_bytes(
                data[10 + 2 * idx : 12 + 2 * idx], byteorder="little", signed=True
            )
            / 1000
            for idx in range(4)
        }

    @staticmethod
    def _decode_data(frame: bytearray) -> BMSsample:
        data: BMSsample = {}
        for field, pos, size, sign, fct in BMS._FIELDS:
            data[field] = fct(
                int.from_bytes(frame[pos : pos + size], "little", signed=sign)
            )
        return data

    @staticmethod
    def _cmd(cmd: bytes, dev_id: int = 0, value: list[int] | None = None) -> bytes:
        """Assemble a CBT Power BMS command."""
        value = [] if value is None else value

        frame = bytearray([*BMS.HEAD, *cmd[:2], dev_id, *value])
        frame.append(crc_sum(frame[5:], 2))
        frame.extend(BMS.TAIL)
        return bytes(frame)

    async def _async_update(self) -> BMSsample:
        """Update battery status information."""
        await self._await_reply(
            BMS._cmd(b"\x06\x00", 0, [0x0, 0x1, 0x0])
        )  # request basic battery info

        return BMS._decode_data(self._data) | BMS._cell_voltages(self._data)
