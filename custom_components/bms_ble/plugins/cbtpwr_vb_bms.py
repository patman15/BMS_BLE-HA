"""Module to support CBT Power VB series BMS."""

from collections.abc import Callable
from string import hexdigits
from typing import Final

from bleak.backends.characteristic import BleakGATTCharacteristic
from bleak.backends.device import BLEDevice
from bleak.uuids import normalize_uuid_str

from custom_components.bms_ble.const import (
    # ATTR_BATTERY_CHARGING,
    ATTR_BATTERY_LEVEL,
    # ATTR_CURRENT,
    # ATTR_CYCLE_CAP,
    # ATTR_CYCLE_CHRG,
    # ATTR_CYCLES,
    ATTR_DELTA_VOLTAGE,
    # ATTR_POWER,
    # ATTR_RUNTIME,
    # ATTR_TEMPERATURE,
    # ATTR_VOLTAGE,
    KEY_CELL_VOLTAGE,
    # KEY_PROBLEM,
)

from .basebms import BaseBMS, BMSsample  # , crc_sum


class BMS(BaseBMS):
    """CBT Power VB series battery class implementation."""

    _HEAD: Final[bytes] = b"\x7e"
    _TAIL: Final[bytes] = b"\x0d"
    _MIN_LEN: Final[int] = 10  # FIXME! define correctly
    _MAX_LEN: Final[int] = 255

    _FIELDS: Final[list[tuple[str, int, int, Callable[[int], int | float]]]] = [
        # (ATTR_VOLTAGE, 28, 4, lambda x: float(x) / 1000),
        # (ATTR_CURRENT, 32, 4, lambda x: float(x) / 1000),
        # (ATTR_TEMPERATURE, 4, 2, lambda x: x),
        (ATTR_BATTERY_LEVEL, 8, 2, lambda x: x),
        # (KEY_DESIGN_CAP, 0x15, 4, 2, lambda x: x),
        # (ATTR_CYCLES, 40, 2, lambda x: x),
        # (KEY_PROBLEM, 69, 4, lambda x: x),
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
        return [
            normalize_uuid_str("ffe0"),
            normalize_uuid_str("ffe5"),
        ]

    @staticmethod
    def uuid_rx() -> str:
        """Return 16-bit UUID of characteristic that provides notification/read property."""
        return "ffe4"

    @staticmethod
    def uuid_tx() -> str:
        """Return 16-bit UUID of characteristic that provides write property."""
        return "ffe9"

    @staticmethod
    def _calc_values() -> frozenset[str]:
        return frozenset(
            {ATTR_DELTA_VOLTAGE}
        )  # calculate further values from BMS provided set ones

    def _notification_handler(
        self, _sender: BleakGATTCharacteristic, data: bytearray
    ) -> None:
        """Handle the RX characteristics notify event (new data arrives)."""

        if data.startswith(BMS._HEAD):
            self._data = bytearray()

        self._data += data
        self._log.debug(
            "RX BLE data (%s): %s", "start" if data == self._data else "cnt.", data
        )

        if not data.endswith(BMS._TAIL):
            if len(self._data) >= BMS._MAX_LEN:
                self._data.clear()
            return

        # verify that data is long enough
        if len(data) % 2 or len(data) < BMS._MIN_LEN:
            self._log.debug("incorrect frame length (%i): %s", len(data), data)
            self._data.clear()
            return

        if not all(chr(c) in hexdigits for c in self._data[1:-1]):
            self._log.debug("incorrect frame encoding.")
            self._data.clear()
            return

        # if (crc := crc_sum(data[5:-5], 2)) != int.from_bytes(
        #     data[-4:-2], byteorder="little", signed=False
        # ):
        #     self._log.debug(
        #         "invalid checksum 0x%X != 0x%X",
        #         crc,
        #         int.from_bytes(data[-4:-2], byteorder="little", signed=False),
        #     )
        #     return

        self._data = data[1:-1]
        self._data_event.set()

    @staticmethod
    def _cell_voltages(data: bytearray) -> dict[str, float]:
        """Return cell voltages from status message."""
        return {
            f"{KEY_CELL_VOLTAGE}{idx}": int(data[14 + 4 * idx : 18 + 4 * idx], 16)
            / 1000
            for idx in range(4)
        }

    @staticmethod
    def _decode_data(frame: bytearray) -> BMSsample:
        return {
            key: func(int(frame[idx : idx + size], 16))
            for key, idx, size, func in BMS._FIELDS
        }

    # @staticmethod
    # def _cmd(cmd: bytes, dev_id: int = 0, value: list[int] | None = None) -> bytes:
    #     """Assemble a CBT Power BMS command."""
    #     value = [] if value is None else value

    #     frame = bytearray([*BMS._HEAD, *cmd[:2], dev_id, *value])
    #     frame.append(crc_sum(frame[5:], 2))
    #     frame.extend(BMS._TAIL)
    #     return bytes(frame)

    async def _async_update(self) -> BMSsample:
        """Update battery status information."""
        await self._await_reply(
            b"\x7e\x31\x31\x30\x31\x34\x36\x34\x32\x45\x30\x30\x32\x30\x31\x46\x44\x33\x35\x0d"
        )  # request basic battery info

        return BMS._decode_data(self._data) | BMS._cell_voltages(self._data)
