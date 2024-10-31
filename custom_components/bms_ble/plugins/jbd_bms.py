"""Module to support JBD Smart BMS."""

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
    KEY_CELL_VOLTAGE,
    KEY_TEMP_SENS,
    KEY_TEMP_VALUE,
)

from .basebms import BaseBMS, BMSsample

BAT_TIMEOUT: Final = 10
LOGGER: Final = logging.getLogger(__name__)

# setup UUIDs, e.g. for receive: '0000fff1-0000-1000-8000-00805f9b34fb'
UUID_RX: Final = normalize_uuid_str("ff01")
UUID_TX: Final = normalize_uuid_str("ff02")
UUID_SERVICE: Final = normalize_uuid_str("ff00")


class BMS(BaseBMS):
    """JBD Smart BMS class implementation."""

    HEAD_RSP: Final = bytes([0xDD])  # header for responses
    HEAD_CMD: Final = bytes([0xDD, 0xA5])  # read header for commands

    INFO_LEN: Final = 7  # minimum frame size
    BASIC_INFO: Final = 23  # basic info data length

    def __init__(self, ble_device: BLEDevice, reconnect: bool = False) -> None:
        """Intialize private BMS members."""
        self._reconnect: Final[bool] = reconnect
        self._ble_device = ble_device
        assert self._ble_device.name is not None
        self._client: BleakClient | None = None
        self._data: bytearray = bytearray()
        self._data_final: bytearray | None = None
        self._data_event = asyncio.Event()
        self._FIELDS: Final[
            list[tuple[str, int, int, bool, Callable[[int], int | float]]]
        ] = [
            (KEY_TEMP_SENS, 26, 1, False, lambda x: x),  # count is not limited
            (ATTR_VOLTAGE, 4, 2, False, lambda x: float(x / 100)),
            (ATTR_CURRENT, 6, 2, True, lambda x: float(x / 100)),
            (ATTR_BATTERY_LEVEL, 23, 1, False, lambda x: x),
            (ATTR_CYCLE_CHRG, 8, 2, False, lambda x: float(x / 100)),
            (ATTR_CYCLES, 12, 2, False, lambda x: x),
        ]  # general protocol v4

    @staticmethod
    def matcher_dict_list() -> list[dict[str, Any]]:
        """Provide BluetoothMatcher definition."""
        return [
            {
                "service_uuid": UUID_SERVICE,
                "connectable": True,
            },
        ]

    @staticmethod
    def device_info() -> dict[str, str]:
        """Return device information for the battery management system."""
        return {"manufacturer": "Jiabaida", "model": "Smart BMS"}

    async def _wait_event(self) -> None:
        await self._data_event.wait()
        self._data_event.clear()

    def _on_disconnect(self, _client: BleakClient) -> None:
        """Disconnect callback function."""

        LOGGER.debug("Disconnected from BMS (%s)", self._ble_device.name)

    def _notification_handler(self, _sender, data: bytearray) -> None:
        if self._data_event.is_set():
            return

        # check if answer is a heading of basic info (0x3) or cell block info (0x4)
        if (
            data[0 : len(self.HEAD_RSP)] == self.HEAD_RSP
            and (data[1] == 0x03 or data[1] == 0x04)
            and data[2] == 0x00
        ):
            self._data = bytearray()

        self._data += data
        LOGGER.debug(
            "(%s) Rx BLE data (%s): %s",
            self._ble_device.name,
            "start" if data == self._data else "cnt.",
            data,
        )

        # verify that data long enough and has correct frame ending (0x77)
        if (
            len(self._data) < self.INFO_LEN + self._data[3]
            or self._data[self.INFO_LEN + self._data[3] - 1] != 0x77
        ):
            return

        frame_end: Final[int] = self.INFO_LEN + self._data[3] - 1
        crc: Final[int] = self._crc(self._data[2 : frame_end - 2])
        if int.from_bytes(self._data[frame_end - 2 : frame_end], "big") != crc:
            LOGGER.debug(
                "(%s) Rx data CRC is invalid: %i != %i",
                self._ble_device.name,
                int.from_bytes(self._data[frame_end - 2 : frame_end], "big"),
                crc,
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
            await self._client.start_notify(UUID_RX, self._notification_handler)
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
        """Calculate JBD frame CRC."""
        return 0x10000 - sum(frame)

    def _cmd(self, cmd: bytes) -> bytes:
        """Assemble a JBD BMS command."""
        frame = bytes([*self.HEAD_CMD, cmd[0], 0x00])
        frame += self._crc(frame[2:4]).to_bytes(2, "big")
        frame += bytes([0x77])
        return frame

    def _decode_data(self, data: bytearray) -> dict[str, int | float]:
        result = {
            key: func(
                int.from_bytes(data[idx : idx + size], byteorder="big", signed=sign)
            )
            for key, idx, size, sign, func in self._FIELDS
        }

        # calculate average temperature
        result |= {
            f"{KEY_TEMP_VALUE}{(idx-27)>>1}": (
                (int.from_bytes(data[idx : idx + 2], byteorder="big") - 2731) / 10
            )
            for idx in range(27, 27 + int(result[KEY_TEMP_SENS]) * 2, 2)
        }

        return result

    def _cell_voltages(self, data: bytearray) -> dict[str, float]:
        return {
            f"{KEY_CELL_VOLTAGE}{idx}": float(
                int.from_bytes(
                    data[4 + idx * 2 : 4 + idx * 2 + 2], byteorder="big", signed=False
                )
            )
            / 1000
            for idx in range(int(data[3] / 2))
        }

    async def async_update(self) -> BMSsample:
        """Update battery status information."""
        await self._connect()
        assert self._client is not None

        data = {}
        for cmd, exp_len, dec_fct in [
            (self._cmd(b"\x03"), self.BASIC_INFO, self._decode_data),
            (self._cmd(b"\x04"), 0, self._cell_voltages),
        ]:
            await self._client.write_gatt_char(UUID_TX, data=cmd)
            await asyncio.wait_for(self._wait_event(), timeout=BAT_TIMEOUT)

            if self._data_final is None:
                continue
            if (
                len(self._data_final) != self.INFO_LEN + self._data_final[3]
                or len(self._data_final) < self.INFO_LEN + exp_len
            ):
                LOGGER.debug(
                    "(%s) Wrong data length (%i): %s",
                    self._ble_device.name,
                    len(self._data_final),
                    self._data_final,
                )

            data.update(dec_fct(self._data_final))

        self.calc_values(
            data,
            {
                ATTR_POWER,
                ATTR_BATTERY_CHARGING,
                ATTR_CYCLE_CAP,
                ATTR_RUNTIME,
                ATTR_DELTA_VOLTAGE,
                ATTR_TEMPERATURE,
            },
        )

        if self._reconnect:
            # disconnect after data update to force reconnect next time (slow!)
            await self.disconnect()

        return data
