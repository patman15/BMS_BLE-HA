"""Module to support Daly Smart BMS."""

# import asyncio
from collections.abc import Callable
from datetime import datetime as dt
from typing import Any, Final

from bleak.backends.device import BLEDevice

# from bleak.exc import BleakError
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
    KEY_TEMP_SENS,
    KEY_TEMP_VALUE,
)

from .basebms import BaseBMS, BMSsample, crc_modbus


class BMS(BaseBMS):
    """Daly Smart BMS class implementation."""

    HEAD_READ: Final[bytes] = b"\xD2\x03"
    HEAD_WRITE: Final[bytes] = b"\xD2\x10"
    BAT_INFO: Final[bytes] = b"\x00\x00\x00\x3E"
    MOS_INFO: Final[bytes] = b"\x00\x3E\x00\x09"
    TIME_INFO: Final[bytes] = b"\x00\xD4\x00\x03"
    HEAD_LEN: Final[int] = 3
    CRC_LEN: Final[int] = 2
    MAX_CELLS: Final[int] = 32
    MAX_TEMP: Final[int] = 8
    INFO_LEN: Final[int] = 84 + HEAD_LEN + CRC_LEN + MAX_CELLS + MAX_TEMP
    MOS_TEMP_POS: Final[int] = HEAD_LEN + 8
    _FIELDS: Final[list[tuple[str, int, Callable[[int], int | float]]]] = [
        (ATTR_VOLTAGE, 80 + HEAD_LEN, lambda x: float(x / 10)),
        (ATTR_CURRENT, 82 + HEAD_LEN, lambda x: float((x - 30000) / 10)),
        (ATTR_BATTERY_LEVEL, 84 + HEAD_LEN, lambda x: float(x / 10)),
        (ATTR_CYCLE_CHRG, 96 + HEAD_LEN, lambda x: float(x / 10)),
        (KEY_CELL_COUNT, 98 + HEAD_LEN, lambda x: min(x, BMS.MAX_CELLS)),
        (KEY_TEMP_SENS, 100 + HEAD_LEN, lambda x: min(x, BMS.MAX_TEMP)),
        (ATTR_CYCLES, 102 + HEAD_LEN, lambda x: x),
        (ATTR_DELTA_VOLTAGE, 112 + HEAD_LEN, lambda x: float(x / 1000)),
    ]

    def __init__(self, ble_device: BLEDevice, reconnect: bool = False) -> None:
        """Intialize private BMS members."""
        super().__init__(__name__, self._notification_handler, ble_device, reconnect)

    @staticmethod
    def matcher_dict_list() -> list[dict[str, Any]]:
        """Provide BluetoothMatcher definition."""
        return [
            {
                "local_name": "DL-*",
                "service_uuid": BMS.uuid_services()[0],
                "connectable": True,
            },
            {"local_name": "DL-FB*", "manufacturer_id": 0x0303, "connectable": True},
        ]

    @staticmethod
    def device_info() -> dict[str, str]:
        """Return device information for the battery management system."""
        return {"manufacturer": "Daly", "model": "Smart BMS"}

    @staticmethod
    def uuid_services() -> list[str]:
        """Return list of 128-bit UUIDs of services required by BMS."""
        return [normalize_uuid_str("fff0"), normalize_uuid_str("ff00")]

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
            ATTR_CYCLE_CAP,
            ATTR_POWER,
            ATTR_BATTERY_CHARGING,
            ATTR_RUNTIME,
            ATTR_TEMPERATURE,
        }

    # def _not_handler(self, _sender, data: bytearray) -> None:
    #     self._log.debug("RX BLE data on 2a05: %s", data)

    async def _init_connection(self) -> None:
        """Connect to the BMS and setup notification if not connected."""
        await super()._init_connection()

        if not self.name.startswith("DL-FB4"):
            return

        # await self._client.start_notify("2a05", self._not_handler)

        # for char in ["ff01", "ff02", "fff1", "fff2", "fffa", "fffb", "fff3"]:
        #     try:
        #         self._log.debug(
        #             "Reading %s: %s", char, await self._client.read_gatt_char(char)
        #         )
        #         asyncio.sleep(0.3)
        #     except (BleakError, TimeoutError) as ex:
        #         self._log.debug("Exception reading %s: %s", char, ex)
        #         continue

        # await self._await_reply(
        #     b"\xa5\x40\x02\x08\x00\x00\x00\x00\x00\x00\x00\x00\xef",
        #     normalize_uuid_str("fff2"),
        #     False,
        # )
        # await asyncio.sleep(0.1)
        # await self._await_reply(
        #     b"\x81\x10\x0f\x05\x00\x01\x00\x00\x05\x59",
        #     normalize_uuid_str("fff2"),
        #     False,
        # )
        # await asyncio.sleep(0.1)

        # set timestamp for Bulltron battery
        ts: dt = dt.now()
        await self._await_reply(
            BMS._cmd_frame(
                BMS.TIME_INFO,
                bytes(
                    [ts.year - 2000, ts.month, ts.day, ts.hour, ts.minute, ts.second]
                ),
                BMS.HEAD_WRITE,
            ),
        )

    def _notification_handler(self, _sender, data: bytearray) -> None:
        self._log.debug("RX BLE data: %s", data)

        if not data.startswith((BMS.HEAD_READ, BMS.HEAD_WRITE)):
            self._log.debug("invalid response header")
            return

        if (
            data.startswith(BMS.HEAD_READ)
            and int(data[2]) + 1 != len(data) - len(BMS.HEAD_READ) - BMS.CRC_LEN
        ) or (data.startswith(BMS.HEAD_WRITE) and len(data) != 8):
            self._log.debug("invalid message length (%i)", len(data))
            return

        crc: Final[int] = crc_modbus(data[:-2])
        if crc != int.from_bytes(data[-2:], byteorder="little"):
            self._log.debug(
                "invalid checksum 0x%X != 0x%X",
                int.from_bytes(data[-2:], byteorder="little"),
                crc,
            )
            return

        self._data = data
        self._data_event.set()

    @staticmethod
    def _cmd_frame(request: bytes, data: bytes = b"", cmd: bytes = HEAD_READ) -> bytes:
        """Assemble a Daly Smart BMS command frame, default is read."""
        assert len(request) == 4
        frame: bytes = cmd + request[0:2] + request[2:4] + data
        frame += crc_modbus(bytearray(frame)).to_bytes(2, byteorder="little")
        return frame

    async def _async_update(self) -> BMSsample:
        """Update battery status information."""
        data: BMSsample = {}
        try:
            # request MOS temperature (possible outcome: response, empty response, no response)
            await self._await_reply(BMS._cmd_frame(BMS.MOS_INFO))

            if sum(self._data[BMS.MOS_TEMP_POS :][:2]):
                self._log.debug("MOS info: %s", self._data)
                data |= {
                    f"{KEY_TEMP_VALUE}0": float(
                        int.from_bytes(
                            self._data[BMS.MOS_TEMP_POS :][:2],
                            byteorder="big",
                            signed=True,
                        )
                        - 40
                    )
                }
        except TimeoutError:
            self._log.debug("no MOS temperature available.")

        await self._await_reply(BMS._cmd_frame(BMS.BAT_INFO))

        if len(self._data) != BMS.INFO_LEN:
            self._log.debug("incorrect frame length: %i", len(self._data))
            return {}

        data |= {
            key: func(
                int.from_bytes(self._data[idx : idx + 2], byteorder="big", signed=True)
            )
            for key, idx, func in BMS._FIELDS
        }

        # get temperatures
        # shift index if MOS temperature is available
        t_off: Final[int] = 1 if f"{KEY_TEMP_VALUE}0" in data else 0
        data |= {
            f"{KEY_TEMP_VALUE}{((idx-64-BMS.HEAD_LEN)>>1) + t_off}": float(
                int.from_bytes(self._data[idx : idx + 2], byteorder="big", signed=True)
                - 40
            )
            for idx in range(
                64 + self.HEAD_LEN, 64 + self.HEAD_LEN + int(data[KEY_TEMP_SENS]) * 2, 2
            )
        }

        # get cell voltages
        data |= {
            f"{KEY_CELL_VOLTAGE}{idx}": float(
                int.from_bytes(
                    self._data[BMS.HEAD_LEN + 2 * idx : BMS.HEAD_LEN + 2 * idx + 2],
                    byteorder="big",
                    signed=True,
                )
                / 1000
            )
            for idx in range(int(data[KEY_CELL_COUNT]))
        }

        return data
