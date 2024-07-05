"""Module to support Seplos V3 Smart BMS."""

import asyncio
from collections.abc import Callable
import logging
from typing import Any

from bleak import BleakClient
from bleak.backends.device import BLEDevice
from bleak.exc import BleakError
from bleak.uuids import normalize_uuid_str

from ..const import (
    ATTR_BATTERY_CHARGING,
    ATTR_BATTERY_LEVEL,
    ATTR_CURRENT,
    ATTR_CYCLE_CAP,
    ATTR_CYCLE_CHRG,
    ATTR_CYCLES,
    ATTR_POWER,
    ATTR_RUNTIME,
    ATTR_TEMPERATURE,
    ATTR_VOLTAGE,
    KEY_CELL_VOLTAGE,
)
from .basebms import BaseBMS

BAT_TIMEOUT = 10
LOGGER = logging.getLogger(__name__)

# setup UUIDs
#    serv 0000fff0-0000-1000-8000-00805f9b34fb
# 	 char 0000fff1-0000-1000-8000-00805f9b34fb (#16): ['read', 'notify']
# 	 char 0000fff2-0000-1000-8000-00805f9b34fb (#20): ['read', 'write-without-response', 'write']
UUID_CHAR = normalize_uuid_str("fff1")
UUID_SERVICE = normalize_uuid_str("fff0")


class BMS(BaseBMS):
    """Seplos V3 Smart BMS class implementation."""

    CMD_READ: int = 0x04
    PART: list[int] = [0xE0, 0x00, 0x01]  # partitions: PIA, PIB, PIC
    HEAD_LEN: int = 3
    CRC_LEN: int = 2

    def __init__(self, ble_device: BLEDevice, reconnect: bool = False) -> None:
        """Intialize private BMS members."""
        self._reconnect = reconnect
        self._ble_device = ble_device
        assert self._ble_device.name is not None
        self._client: BleakClient | None = None
        self._data: bytearray | None = None
        self._exp_dat_len: int = 0
        self._data_final: dict[int, bytearray] = {
            part: bytearray() for part in self.PART
        }
        self._data_event = asyncio.Event()
        self._connected = False  # flag to indicate active BLE connection
        self._char_write_handle: int | None = None
        self._FIELDS: list[tuple[str, int, int, bool, Callable[[int], int | float]]] = [
            (ATTR_VOLTAGE, self.HEAD_LEN, 2, False, lambda x: float(x / 100)),
            (ATTR_CURRENT, self.HEAD_LEN + 2, 2, True, lambda x: float(x / 100)),
            (ATTR_CYCLE_CHRG, self.HEAD_LEN + 4, 2, False, lambda x: float(x / 100)),
            (
                ATTR_TEMPERATURE,
                self.HEAD_LEN + 6,
                2,
                False,
                lambda x: round(float(x) * 0.1 - 273.15, 1),
            ),
            (ATTR_BATTERY_LEVEL, self.HEAD_LEN + 10, 2, False, lambda x: float(x / 10)),
            (ATTR_CYCLES, self.HEAD_LEN + 14, 2, False, lambda x: x),
        ]  # Protocol Seplos V3

    @staticmethod
    def matcher_dict_list() -> list[dict[str, Any]]:
        """Provide BluetoothMatcher definition."""
        return [
            {
                "local_name": "SP0*",
                "service_uuid": UUID_SERVICE,
                "connectable": True,
            },
        ]

    @staticmethod
    def device_info() -> dict[str, str]:
        """Return device information for the battery management system."""
        return {"manufacturer": "Seplos", "model": "Smart BMS V3"}

    async def _wait_event(self) -> None:
        """Wait for data event and clear it."""
        await self._data_event.wait()
        self._data_event.clear()

    def _on_disconnect(self, client: BleakClient) -> None:
        """Disconnect callback function."""

        LOGGER.debug("Disconnected from BMS (%s)", self._ble_device.name)
        self._connected = False

    def _notification_handler(self, sender, data: bytearray) -> None:
        """Retrieve BMS data update."""

        if (
            len(data) > self.HEAD_LEN + self.CRC_LEN
            and data[1] == self.CMD_READ
            and data[0] in self.PART
            and data[2] >= self.HEAD_LEN + self.CRC_LEN
        ):
            self._data = data
            self._exp_dat_len = (
                data[2] + self.HEAD_LEN + self.CRC_LEN
            )  # expected packet length
        elif len(data) and self._data is not None:
            self._data += data

        LOGGER.debug(
            "(%s) Rx BLE data (%s): %s",
            self._ble_device.name,
            "start" if data == self._data else "cnt.",
            data,
        )

        # verify that data long enough
        if self._data is None or len(self._data) < self._exp_dat_len:
            return

        crc = int.from_bytes(
            self._data[self._exp_dat_len - 2 :], byteorder="little"
        )  # self._crc(self._data[0 : self._exp_dat_len - 2])
        if (
            int.from_bytes(self._data[self._exp_dat_len - 2 :], byteorder="little")
            != crc
        ):
            LOGGER.debug(
                "(%s) Rx data CRC is invalid: %i != %i",
                self._ble_device.name,
                int.from_bytes(self._data[self._exp_dat_len - 2 :], byteorder="little"),
                crc,
            )
            self._data_final[int(self._data[0])] = bytearray()  # reset invalid data
        else:
            self._data_final[int(self._data[0])] = self._data

        self._data_event.set()

    async def _connect(self) -> None:
        """Connect to the BMS and setup notification if not connected."""

        if not self._connected:
            LOGGER.debug("Connecting BMS (%s)", self._ble_device.name)
            self._client = BleakClient(
                self._ble_device,
                disconnected_callback=self._on_disconnect,
                services=[UUID_SERVICE],
            )
            await self._client.connect()
            await self._client.start_notify(UUID_CHAR, self._notification_handler)
            self._connected = True
        else:
            LOGGER.debug("BMS %s already connected", self._ble_device.name)

    async def disconnect(self) -> None:
        """Disconnect the BMS and includes stoping notifications."""

        if self._client and self._connected:
            LOGGER.debug("Disconnecting BMS (%s)", self._ble_device.name)
            try:
                self._data_event.clear()
                await self._client.disconnect()
            except BleakError:
                LOGGER.warning("Disconnect failed!")

        self._client = None

    # def _crc(self, frame: bytes):
    #     """Calculate Seplos V3 frame CRC."""
    #     return sum(frame) & 0xFF

    # def _cmd(self, cmd: bytes, value: list[int] | None = None) -> bytes:
    #     """Assemble a Seplos V3 BMS command."""
    #     if value is None:
    #         value = []
    #     assert len(value) <= 13
    #     frame = bytes([*self.HEAD_CMD, cmd[0]])
    #     frame += bytes([len(value), *value])
    #     frame += bytes([0] * (13 - len(value)))
    #     frame += bytes([self._crc(frame)])
    #     return frame

    async def async_update(self) -> dict[str, int | float | bool]:
        """Update battery status information."""
        await self._connect()
        assert self._client is not None
        if not self._connected:
            LOGGER.debug(
                "Update request, but device (%s) not connected", self._ble_device.name
            )
            return {}

        await self._client.write_gatt_char(0, b"")
        await asyncio.wait_for(self._wait_event(), timeout=BAT_TIMEOUT)


        LOGGER.debug(f"{self._data_final=} {self.PART=}")
        if not any(len(self._data_final[self.PART[x]]) for x in range(3)):
            return {}
        # if len(self._data_final) != self.INFO_LEN:
        #     LOGGER.debug(
        #         "(%s) Wrong data length (%i): %s",
        #         self._ble_device.name,
        #         len(self._data_final),
        #         self._data_final,
        #     )

        data = {
            key: func(
                int.from_bytes(
                    self._data_final[self.PART[0]][idx : idx + size],
                    byteorder="little",
                    signed=sign,
                )
            )
            for key, idx, size, sign, func in self._FIELDS
        }

        # get cell voltages
        if len(self._data_final[self.PART[1]]):
            data.update(
                {
                    f"{KEY_CELL_VOLTAGE}{idx}": float(
                        int.from_bytes(
                            self._data_final[self.PART[1]][
                                self.HEAD_LEN + 2 * idx : self.HEAD_LEN + 2 * idx + 2
                            ],
                            byteorder="little",
                            signed=False,
                        )
                        / 1000
                    )
                    for idx in range(16)
                }
            )

        self.calc_values(
            data, {ATTR_POWER, ATTR_BATTERY_CHARGING, ATTR_CYCLE_CAP, ATTR_RUNTIME}
        )

        self._data_final.clear()

        if self._reconnect:
            # disconnect after data update to force reconnect next time (slow!)
            await self.disconnect()

        return data
