"""Module to support Seplos V3 Smart BMS."""

import asyncio
from collections.abc import Callable
import logging
from typing import Any, Final

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
    KEY_CELL_VOLTAGE,
    KEY_PACK_COUNT,
    KEY_TEMP_VALUE,
)

from .basebms import BaseBMS, BMSsample, crc_xmodem

BAT_TIMEOUT: Final = 5
LOGGER = logging.getLogger(__name__)


class BMS(BaseBMS):
    """Seplos V3 Smart BMS class implementation."""

    CMD_READ: Final = 0x04
    HEAD_LEN: Final = 3
    CRC_LEN: Final = 2
    PIB_LEN: Final = 0x1A
    EIA_LEN: Final = PIB_LEN
    EIB_LEN: Final = 0x16
    TEMP_START: Final = HEAD_LEN + 32
    QUERY: Final[dict[str, tuple[int, int, int]]] = {
        # name: cmd, reg start, length
        "EIA": (0x4, 0x2000, EIA_LEN),
        "EIB": (0x4, 0x2100, EIB_LEN),
        "PIB": (0x4, 0x1100, PIB_LEN),
    }

    def __init__(self, ble_device: BLEDevice, reconnect: bool = False) -> None:
        """Intialize private BMS members."""
        super().__init__(LOGGER, self._notification_handler, ble_device, reconnect)
        self._data: bytearray = bytearray()
        self._exp_len: int = 0  # expected packet length
        self._data_final: dict[int, bytearray] = {}
        self._pack_count = 0
        self._char_write_handle: int | None = None
        self._FIELDS: Final[
            list[tuple[str, int, int, int, bool, Callable[[int], int | float]]]
        ] = [
            (ATTR_TEMPERATURE, self.EIB_LEN, 20, 2, False, lambda x: float(x / 10)),
            (
                ATTR_VOLTAGE,
                self.EIA_LEN,
                0,
                4,
                False,
                lambda x: float(self._swap32(x) / 100),
            ),
            (
                ATTR_CURRENT,
                self.EIA_LEN,
                4,
                4,
                False,
                lambda x: float((self._swap32(x, True)) / 10),
            ),
            (
                ATTR_CYCLE_CHRG,
                self.EIA_LEN,
                8,
                4,
                False,
                lambda x: float(self._swap32(x) / 100),
            ),
            (KEY_PACK_COUNT, self.EIA_LEN, 44, 2, False, lambda x: x),
            (ATTR_CYCLES, self.EIA_LEN, 46, 2, False, lambda x: x),
            (ATTR_BATTERY_LEVEL, self.EIA_LEN, 48, 2, False, lambda x: float(x / 10)),
        ]  # Protocol Seplos V3

    @staticmethod
    def matcher_dict_list() -> list[dict[str, Any]]:
        """Provide BluetoothMatcher definition."""
        return [
            {
                "local_name": "SP0*",
                "service_uuid": BMS.uuid_services()[0],
                "connectable": True,
            },
            {
                "local_name": "SP1*",
                "service_uuid": BMS.uuid_services()[0],
                "connectable": True,
            },
        ]

    @staticmethod
    def device_info() -> dict[str, str]:
        """Return device information for the battery management system."""
        return {"manufacturer": "Seplos", "model": "Smart BMS V3"}

    # setup UUIDs
    #    serv 0000fff0-0000-1000-8000-00805f9b34fb
    # 	 char 0000fff1-0000-1000-8000-00805f9b34fb (#16): ['read', 'notify']
    # 	 char 0000fff2-0000-1000-8000-00805f9b34fb (#20): ['read', 'write-without-response', 'write']
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
        return {ATTR_POWER, ATTR_BATTERY_CHARGING, ATTR_CYCLE_CAP, ATTR_RUNTIME}

    def _notification_handler(self, _sender, data: bytearray) -> None:
        """Retrieve BMS data update."""

        if (
            len(data) > self.HEAD_LEN + self.CRC_LEN
            and data[0] <= self._pack_count
            and data[1] & 0x7F == self.CMD_READ  # include read errors
            and data[2] >= self.HEAD_LEN + self.CRC_LEN
        ):
            self._data = bytearray()
            self._exp_len = data[2] + self.HEAD_LEN + self.CRC_LEN
        elif (  # error message
            len(data) == self.HEAD_LEN + self.CRC_LEN
            and data[0] <= self._pack_count
            and data[1] & 0x80
        ):
            LOGGER.debug("%s: Rx BLE error: %x", self._ble_device.name, int(data[2]))
            self._data = bytearray()
            self._exp_len = self.HEAD_LEN + self.CRC_LEN

        self._data += data
        LOGGER.debug(
            "%s: Rx BLE data (%s): %s",
            self._ble_device.name,
            "start" if data == self._data else "cnt.",
            data,
        )

        # verify that data long enough
        if len(self._data) < self._exp_len:
            return

        crc = crc_xmodem(self._data[: self._exp_len - 2])
        if int.from_bytes(self._data[self._exp_len - 2 : self._exp_len]) != crc:
            LOGGER.debug(
                "%s: Rx data CRC is invalid: 0x%X != 0x%X",
                self._ble_device.name,
                int.from_bytes(self._data[self._exp_len - 2 : self._exp_len]),
                crc,
            )
            self._data_final[int(self._data[0])] = bytearray()  # reset invalid data
        elif (
            not (self._data[2] == self.EIA_LEN * 2 or self._data[2] == self.EIB_LEN * 2)
            and not self._data[1] & 0x80
        ):
            LOGGER.debug(
                "%s: unknown message: %s, length: %s",
                self._ble_device.name,
                self._data[0:2],
                self._data[2],
            )
            self._data = bytearray()
            return
        else:
            self._data_final[int(self._data[0]) << 8 | int(self._data[2])] = self._data
            if len(self._data) != self._exp_len:
                LOGGER.debug(
                    "%s: Wrong data length (%i!=%s): %s",
                    self._ble_device.name,
                    len(self._data),
                    self._exp_len,
                    self._data,
                )

        self._data_event.set()

    def _swap32(self, value: int, signed: bool = False) -> int:
        """Swap high and low 16bit in 32bit integer."""

        value = ((value >> 16) & 0xFFFF) | (value & 0xFFFF) << 16
        if signed and value & 0x80000000:
            value = -0x100000000 + value
        return value

    def _cmd(self, device: int, cmd: int, start: int, count: int) -> bytearray:
        """Assemble a Seplos BMS command."""
        assert device >= 0x00 and (device <= 0x10 or device in (0xC0, 0xE0))
        assert cmd in (0x01, 0x04)  # allow only read commands
        assert start >= 0 and count > 0 and start + count <= 0xFFFF
        frame = bytearray([device, cmd])
        frame += bytearray(int.to_bytes(start, 2, byteorder="big"))
        frame += bytearray(int.to_bytes(count, 2, byteorder="big"))
        frame += bytearray(int.to_bytes(crc_xmodem(frame), 2, byteorder="big"))
        return frame

    async def _async_update(self) -> BMSsample:
        """Update battery status information."""
        for block in ["EIA", "EIB"]:
            await self._client.write_gatt_char(
                BMS.uuid_tx(), data=self._cmd(0x0, *self.QUERY[block])
            )
            await asyncio.wait_for(self._wait_event(), timeout=BAT_TIMEOUT)
            # check if a valid frame was received otherwise terminate immediately
            if self.QUERY[block][2] * 2 not in self._data_final:
                return {}

        data = {
            key: func(
                int.from_bytes(
                    self._data_final[msg * 2][
                        self.HEAD_LEN + idx : self.HEAD_LEN + idx + size
                    ],
                    byteorder="big",
                    signed=sign,
                )
            )
            for key, msg, idx, size, sign, func in self._FIELDS
        }
        self._pack_count = min(int(data.get(KEY_PACK_COUNT, 0)), 0x10)

        for pack in range(1, 1 + self._pack_count):
            await self._client.write_gatt_char(
                BMS.uuid_tx(), data=self._cmd(pack, *self.QUERY["PIB"])
            )
            await asyncio.wait_for(self._wait_event(), timeout=BAT_TIMEOUT)
            # get cell voltages
            if pack << 8 | self.PIB_LEN * 2 in self._data_final:
                pack_cells = [
                    float(
                        int.from_bytes(
                            self._data_final[pack << 8 | self.PIB_LEN * 2][
                                self.HEAD_LEN + idx * 2 : self.HEAD_LEN + idx * 2 + 2
                            ],
                            byteorder="big",
                        )
                        / 1000
                    )
                    for idx in range(16)
                ]
                # update per pack delta voltage
                data |= {
                    ATTR_DELTA_VOLTAGE: max(
                        float(data.get(ATTR_DELTA_VOLTAGE, 0)),
                        round(max(pack_cells) - min(pack_cells), 3),
                    )
                }
                # add individual cell voltages
                data |= {
                    f"{KEY_CELL_VOLTAGE}{idx+16*(pack-1)}": pack_cells[idx]
                    for idx in range(16)
                }
                # add temperature sensors (4x cell temperature + 4 reserved)
                data |= {
                    f"{KEY_TEMP_VALUE}{idx+8*(pack-1)}": (
                        int.from_bytes(
                            self._data_final[pack << 8 | self.PIB_LEN * 2][
                                self.TEMP_START
                                + idx * 2 : self.TEMP_START
                                + idx * 2
                                + 2
                            ],
                            byteorder="big",
                        )
                        - 2731.5
                    )
                    / 10
                    for idx in range(4)
                }

        self._data_final.clear()

        return data
