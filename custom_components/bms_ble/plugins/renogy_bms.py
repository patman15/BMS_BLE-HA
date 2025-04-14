"""Module to support Renogy BMS."""

import contextlib
from typing import Final

from bleak.backends.characteristic import BleakGATTCharacteristic
from bleak.backends.device import BLEDevice
from bleak.uuids import normalize_uuid_str

from custom_components.bms_ble.const import (
    ATTR_BATTERY_CHARGING,
    # ATTR_BATTERY_LEVEL,
    ATTR_CURRENT,
    # ATTR_CYCLE_CAP,
    # ATTR_CYCLE_CHRG,
    # ATTR_CYCLES,
    # ATTR_DELTA_VOLTAGE,
    ATTR_POWER,
    # ATTR_RUNTIME,
    ATTR_TEMPERATURE,
    ATTR_VOLTAGE,
)

from .basebms import BaseBMS, BMSsample, crc_modbus


class BMS(BaseBMS):
    """Renogy battery class implementation."""

    _HEAD: Final[bytes] = b"\x30\x03"
    _CRC_POS: Final[int] = -2

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
            {ATTR_POWER, ATTR_BATTERY_CHARGING}
        )  # calculate further values from BMS provided set ones

    def _notification_handler(
        self, _sender: BleakGATTCharacteristic, data: bytearray
    ) -> None:
        """Handle the RX characteristics notify event (new data arrives)."""
        self._log.debug("RX BLE data: %s", data)

        if not data.startswith(BMS._HEAD):
            self._log.debug("incorrect SOF")

        if len(data) < 3 or data[2] + 5 != len(data):
            self._log.debug("incorrect frame length: %i != %i", len(data), data[2] + 5)

        if (crc := crc_modbus(data[: BMS._CRC_POS])) != int.from_bytes(
            data[BMS._CRC_POS :], "little"
        ):
            self._log.debug(
                "invalid checksum 0x%X != 0x%X",
                crc,
                int.from_bytes(data[BMS._CRC_POS :], "little"),
            )
            return
        #
        # # do things like checking correctness of frame here and
        # # store it into a instance variable, e.g. self._data
        #
        # self._data_event.set()

    @staticmethod
    def _cmd(cmd: bytes) -> bytes:
        """Assemble a Seplos BMS command."""
        frame: bytearray = bytearray([*BMS._HEAD, *cmd])
        frame.extend(int.to_bytes(crc_modbus(frame), 2, byteorder="little"))
        return bytes(frame)

    async def _async_update(self) -> BMSsample:
        """Update battery status information."""
        for cmd in (
            b"\x13\x88\x00\x22",
            b"\x13\xf0\x00\x1c",
            b"\x13\xb2\x00\x06",
            b"\x14\x02\x00\x08",
        ):
            with contextlib.suppress(TimeoutError):
                await self._await_reply(self._cmd(cmd))

        return {
            ATTR_VOLTAGE: 12,
            ATTR_CURRENT: 1.5,
            ATTR_TEMPERATURE: 27.182,
        }  # fixed values, replace parsed data
