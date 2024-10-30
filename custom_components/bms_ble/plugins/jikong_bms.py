"""Module to support Jikong Smart BMS."""

import asyncio
from collections.abc import Callable
import logging
from typing import Any, Final

from bleak import BleakClient
from bleak.backends.device import BLEDevice
from bleak.exc import BleakError
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
    KEY_TEMP_VALUE,
)

from .basebms import BaseBMS, BMSsample

BAT_TIMEOUT: Final = 10
LOGGER: Final = logging.getLogger(__name__)

# setup UUIDs, e.g. for receive: '0000fff1-0000-1000-8000-00805f9b34fb'
UUID_CHAR: Final = normalize_uuid_str("ffe1")
UUID_SERVICE: Final = normalize_uuid_str("ffe0")


class BMS(BaseBMS):
    """Jikong Smart BMS class implementation."""

    HEAD_RSP: Final = bytes([0x55, 0xAA, 0xEB, 0x90])  # header for responses
    HEAD_CMD: Final = bytes([0xAA, 0x55, 0x90, 0xEB])  # header for commands (endiness!)
    BT_MODULE_MSG: Final = bytes([0x41, 0x54, 0x0D, 0x0A])  # AT\r\n from BLE module

    INFO_LEN: Final = 300

    def __init__(self, ble_device: BLEDevice, reconnect: bool = False) -> None:
        """Intialize private BMS members."""
        self._reconnect = reconnect
        self._ble_device = ble_device
        assert self._ble_device.name is not None
        self._client: BleakClient | None = None
        self._data: bytearray = bytearray()
        self._data_final: bytearray | None = None
        self._data_event = asyncio.Event()
        self._char_write_handle: int | None = None
        self._FIELDS: Final[
            list[tuple[str, int, int, bool, Callable[[int], int | float]]]
        ] = [  # Protocol: JK02_32S; JK02_24S has offset -32
            (KEY_CELL_COUNT, 70, 4, False, lambda x: x.bit_count()),
            (ATTR_DELTA_VOLTAGE, 76, 2, False, lambda x: float(x / 1000)),
            (ATTR_VOLTAGE, 150, 4, False, lambda x: float(x / 1000)),
            (ATTR_CURRENT, 158, 4, True, lambda x: float(x / 1000)),
            (ATTR_BATTERY_LEVEL, 173, 1, False, lambda x: x),
            (ATTR_CYCLE_CHRG, 174, 4, False, lambda x: float(x / 1000)),
            (ATTR_CYCLES, 182, 4, False, lambda x: x),
        ] + [  # add temperature sensors
            (f"{KEY_TEMP_VALUE}{i}", addr, 2, True, lambda x: float(x / 10))
            for i, addr in [(0, 144), (1, 162), (2, 164), (3, 256), (4, 258)]
        ]

    @staticmethod
    def matcher_dict_list() -> list[dict[str, Any]]:
        """Provide BluetoothMatcher definition."""
        return [
            {
                "service_uuid": UUID_SERVICE,
                "connectable": True,
                "manufacturer_id": 0x0B65,
            },
        ]

    @staticmethod
    def device_info() -> dict[str, str]:
        """Return device information for the battery management system."""
        return {"manufacturer": "Jikong", "model": "Smart BMS"}

    async def _wait_event(self) -> None:
        """Wait for data event and clear it."""
        await self._data_event.wait()
        self._data_event.clear()

    def _on_disconnect(self, _client: BleakClient) -> None:
        """Disconnect callback function."""

        LOGGER.debug("Disconnected from BMS (%s)", self._ble_device.name)

    def _notification_handler(self, _sender, data: bytearray) -> None:
        """Retrieve BMS data update."""

        if data[0 : len(self.BT_MODULE_MSG)] == self.BT_MODULE_MSG:
            LOGGER.debug("(%s) filtering AT cmd", self._ble_device.name)
            if len(data) == len(self.BT_MODULE_MSG):
                return
            data = data[len(self.BT_MODULE_MSG) :]

        if data[0 : len(self.HEAD_RSP)] == self.HEAD_RSP:
            self._data = bytearray()

        self._data += data

        LOGGER.debug(
            "(%s) Rx BLE data (%s): %s",
            self._ble_device.name,
            "start" if data == self._data else "cnt.",
            data,
        )

        # verify that data long enough and if answer is cell info (0x2)
        if len(self._data) < self.INFO_LEN or self._data[4] != 0x2:
            return

        crc = self._crc(self._data[0 : self.INFO_LEN - 1])
        if self._data[self.INFO_LEN - 1] != crc:
            LOGGER.debug(
                "(%s) Rx data CRC is invalid: %i != %i",
                self._ble_device.name,
                self._data[self.INFO_LEN - 1],
                self._crc(self._data[0 : self.INFO_LEN - 1]),
            )
            self._data_final = None  # reset invalid data
        else:
            self._data_final = self._data

        self._data_event.set()

    async def _connect(self) -> None:
        """Connect to the BMS and setup notification if not connected."""

        if self._client is None or not self._client.is_connected:
            LOGGER.debug("Connecting BMS (%s)", self._ble_device.name)
            if self._client is None:
                self._client = BleakClient(
                    self._ble_device,
                    disconnected_callback=self._on_disconnect,
                    services=[UUID_SERVICE],
                )
            await self._client.connect()
            char_notify_handle: int | None = None
            self._char_write_handle = None
            for service in self._client.services:
                for char in service.characteristics:
                    LOGGER.debug(
                        "(%s) Discovered %s (#%i): %s",
                        self._ble_device.name,
                        char.uuid,
                        char.handle,
                        char.properties,
                    )
                    if char.uuid == UUID_CHAR:
                        if "notify" in char.properties:
                            char_notify_handle = char.handle
                        if (
                            "write" in char.properties
                            or "write-without-response" in char.properties
                        ):
                            self._char_write_handle = char.handle
            if char_notify_handle is None or self._char_write_handle is None:
                LOGGER.debug(
                    "(%s) Failed to detect characteristics", self._ble_device.name
                )
                await self._client.disconnect()
                raise ConnectionError(
                    f"Failed to detect characteristics from {self._ble_device.name}."
                )
            LOGGER.debug(
                "(%s) Using characteristics handle #%i (notify), #%i (write)",
                self._ble_device.name,
                char_notify_handle,
                self._char_write_handle,
            )
            await self._client.start_notify(
                char_notify_handle or 0, self._notification_handler
            )

            # query device info
            await self._client.write_gatt_char(
                self._char_write_handle or 0, data=self._cmd(b"\x97")
            )
        else:
            LOGGER.debug("BMS %s already connected", self._ble_device.name)

    async def disconnect(self) -> None:
        """Disconnect the BMS and includes stoping notifications."""

        if self._client and self._client.is_connected:
            LOGGER.debug("Disconnecting BMS (%s)", self._ble_device.name)
            try:
                self._data_event.clear()
                await self._client.disconnect()
            except BleakError:
                LOGGER.warning("Disconnect failed!")

    def _crc(self, frame: bytes) -> int:
        """Calculate Jikong frame CRC."""
        return sum(frame) & 0xFF

    def _cmd(self, cmd: bytes, value: list[int] | None = None) -> bytes:
        """Assemble a Jikong BMS command."""
        value = [] if value is None else value
        assert len(value) <= 13
        frame = bytes([*self.HEAD_CMD, cmd[0]])
        frame += bytes([len(value), *value])
        frame += bytes([0] * (13 - len(value)))
        frame += bytes([self._crc(frame)])
        return frame

    def _cell_voltages(self, data: bytearray, cells: int) -> dict[str, float]:
        """Return cell voltages from status message."""
        return {
            f"{KEY_CELL_VOLTAGE}{idx}": int.from_bytes(
                data[6 + 2 * idx : 6 + 2 * idx + 2],
                byteorder="little",
                signed=True,
            )
            / 1000
            for idx in range(cells)
        }

    def _decode_data(self, data: bytearray) -> BMSsample:
        """Return BMS data from status message."""
        return {
            key: func(
                int.from_bytes(data[idx : idx + size], byteorder="little", signed=sign)
            )
            for key, idx, size, sign, func in self._FIELDS
        }

    async def async_update(self) -> BMSsample:
        """Update battery status information."""

        await self._connect()
        assert self._client is not None

        if not self._data_event.is_set():
            # request cell info (only if data is not constantly published)
            LOGGER.debug("(%s) request cell info", self._ble_device.name)
            await self._client.write_gatt_char(
                self._char_write_handle or 0, data=self._cmd(b"\x96")
            )

        await asyncio.wait_for(self._wait_event(), timeout=BAT_TIMEOUT)

        if self._data_final is None:
            return {}
        if len(self._data_final) != self.INFO_LEN:
            LOGGER.debug(
                "(%s) Wrong data length (%i): %s",
                self._ble_device.name,
                len(self._data_final),
                self._data_final,
            )

        data = self._decode_data(self._data_final)
        data.update(self._cell_voltages(self._data_final, int(data[KEY_CELL_COUNT])))

        self.calc_values(
            data,
            {
                ATTR_POWER,
                ATTR_BATTERY_CHARGING,
                ATTR_CYCLE_CAP,
                ATTR_RUNTIME,
                ATTR_TEMPERATURE,
            },
        )

        if self._reconnect:
            # disconnect after data update to force reconnect next time (slow!)
            await self.disconnect()

        return data
