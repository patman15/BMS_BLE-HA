"""Module to support CBT Power Smart BMS."""

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
    KEY_CELL_COUNT,
    KEY_CELL_VOLTAGE,
    KEY_DESIGN_CAP,
    KEY_TEMP_VALUE,
)

from homeassistant.util.unit_conversion import _HRS_TO_SECS

from .basebms import BaseBMS, BMSsample

BAT_TIMEOUT: Final = 1
LOGGER: Final = logging.getLogger(__name__)


class BMS(BaseBMS):
    """CBT Power Smart BMS class implementation."""

    # setup UUIDs, e.g. for receive: '0000fff1-0000-1000-8000-00805f9b34fb'

    _UUID_RX = normalize_uuid_str("ffe4")
    _UUID_TX = normalize_uuid_str("ffe9")
    _UUID_SERVICES = [normalize_uuid_str("ffe5"), normalize_uuid_str("ffe0")]

    HEAD: Final = bytes([0xAA, 0x55])
    TAIL_RX: Final = bytes([0x0D, 0x0A])
    TAIL_TX: Final = bytes([0x0A, 0x0D])
    MIN_FRAME: Final = len(HEAD) + len(TAIL_RX) + 3  # CMD, LEN, CRC each 1 Byte
    CRC_POS: Final = -len(TAIL_RX) - 1
    LEN_POS: Final = 3
    CELL_VOLTAGE_CMDS: Final = range(5, 8)

    def __init__(self, ble_device: BLEDevice, reconnect: bool = False) -> None:
        """Intialize private BMS members."""
        super().__init__(LOGGER, self._notification_handler, ble_device, reconnect)
        self._data: bytearray = bytearray()
        self._data_event = asyncio.Event()
        self._FIELDS: Final[
            list[tuple[str, int, int, int, bool, Callable[[int], int | float]]]
        ] = [
            # (KEY_CELL_COUNT, 70, 4, False, lambda x: x.bit_count()),
            # (ATTR_DELTA_VOLTAGE, 76, 2, False, lambda x: float(x / 1000)),
            (ATTR_VOLTAGE, 0x0B, 4, 4, False, lambda x: float(x / 1000)),
            (ATTR_CURRENT, 0x0B, 8, 4, True, lambda x: float(x / 1000)),
            (ATTR_TEMPERATURE, 0x09, 4, 2, False, lambda x: x),
            (ATTR_BATTERY_LEVEL, 0x0A, 4, 1, False, lambda x: x),
            (KEY_DESIGN_CAP, 0x15, 4, 2, False, lambda x: x),
            (ATTR_CYCLES, 0x15, 6, 2, False, lambda x: x),
            (ATTR_RUNTIME, 0x0C, 14, 2, False, lambda x: float(x * _HRS_TO_SECS / 100)),
        ]  # + [  # add temperature sensors
        #  (f"{KEY_TEMP_VALUE}{i}", addr, 2, True, lambda x: float(x / 10))
        #  for i, addr in [(0, 144), (1, 162), (2, 164), (3, 256), (4, 258)]
        # ]

    @staticmethod
    def matcher_dict_list() -> list[dict[str, Any]]:
        """Provide BluetoothMatcher definition."""
        return [
            {
                "service_uuid": normalize_uuid_str("ffb0"),
                "connectable": True,
            },
        ]

    @staticmethod
    def device_info() -> dict[str, str]:
        """Return device information for the battery management system."""
        return {"manufacturer": "CBT Power", "model": "Smart BMS"}

    async def _wait_event(self) -> None:
        """Wait for data event and clear it."""
        await self._data_event.wait()
        self._data_event.clear()

    def _notification_handler(self, _sender, data: bytearray) -> None:
        """Retrieve BMS data update."""

        LOGGER.debug("(%s) Rx BLE data: %s", self._ble_device.name, data)

        self._data = bytearray()  # TODO: verify if needed!
        # verify that data long enough
        if (
            len(data) < self.MIN_FRAME
            or len(data) != self.MIN_FRAME + data[self.LEN_POS]
        ):
            LOGGER.debug(
                "(%s) incorrect frame length (%i): %s", self.name, len(data), data
            )
            return

        if not data.startswith(self.HEAD) or not data.endswith(self.TAIL_RX):
            LOGGER.debug("(%s) Incorrect frame start/end: %s", self.name, data)
            return

        crc = self._crc(data[len(self.HEAD) : len(data) + self.CRC_POS])
        if data[self.CRC_POS] != crc:
            LOGGER.debug(
                "(%s) Rx data CRC is invalid: 0x%x != 0x%x",
                self.name,
                data[len(data) + self.CRC_POS],
                crc,
            )
            return

        self._data = data
        self._data_event.set()

    def _crc(self, frame: bytes) -> int:
        """Calculate CBT Power frame CRC."""
        return sum(frame) & 0xFF

    def _gen_frame(self, cmd: bytes, value: list[int] | None = None) -> bytes:
        """Assemble a CBT Power BMS command."""
        value = [] if value is None else value
        assert len(value) <= 255
        frame = bytes([*self.HEAD, cmd[0]])
        frame += bytes([len(value), *value])
        frame += bytes([self._crc(frame[len(self.HEAD) :])])
        frame += bytes([*self.TAIL_TX])
        return frame

    def _cell_voltages(self, data: bytearray, cells: int) -> dict[str, float]:
        """Return cell voltages from status message."""
        return {
            f"{KEY_CELL_VOLTAGE}{idx}": int.from_bytes(
                data[4 + 2 * idx : 6 + 2 * idx],
                byteorder="little",
                signed=True,
            )
            / 1000
            for idx in range(cells)
        }

    async def _async_update(self) -> BMSsample:
        """Update battery status information."""

        await self._connect()

        data = {}
        resp_cache = {}  # variable to avoid multiple queries with same command
        # (ATTR_VOLTAGE, 0x0B, 150, 4, False, lambda x: float(x / 1000)),
        for field, cmd, pos, size, sign, fct in self._FIELDS:
            LOGGER.debug("(%s) request %s info", self.name, field)
            if resp_cache.get(cmd) is None:
                await self._client.write_gatt_char(
                    self._UUID_TX, data=self._gen_frame(cmd.to_bytes(1))
                )
                LOGGER.debug(f"({self.name}) {cmd=} {size=} {sign=}")
                try:
                    await asyncio.wait_for(self._wait_event(), timeout=BAT_TIMEOUT)
                except TimeoutError:
                    continue
                if self._data is None:
                    continue
                resp_cache[cmd] = self._data.copy()
            LOGGER.debug("(%s) %s", self.name, resp_cache)
            data |= {
                field: fct(
                    int.from_bytes(
                        resp_cache[cmd][pos : pos + size], "little", signed=sign
                    )
                )
            }

            voltages = {}
            for cmd in self.CELL_VOLTAGE_CMDS:
                await self._client.write_gatt_char(
                    self._UUID_TX, data=self._gen_frame(cmd.to_bytes(1))
                )
                try:
                    await asyncio.wait_for(self._wait_event(), timeout=BAT_TIMEOUT)
                except TimeoutError:
                    break
                voltages = self._cell_voltages(self._data, 5)
                if invalid := [k for k, v in voltages.items() if v == 0]:
                    for k in invalid:
                        voltages.pop(k)
                    break
            data |= voltages

        if self._data is None:
            return {}

        # get cycle charge from design capacity and SoC
        if data.get(KEY_DESIGN_CAP) and data.get(ATTR_BATTERY_LEVEL):
            data[ATTR_CYCLE_CHRG] = (
                data[KEY_DESIGN_CAP] * data[ATTR_BATTERY_LEVEL] / 100
            )
        # remove runtime if not discharging
        if data.get(ATTR_CURRENT, 0) >= 0:
            data.pop(ATTR_RUNTIME, None)

        self.calc_values(
            data,
            {
                ATTR_POWER,
                ATTR_BATTERY_CHARGING,
                ATTR_DELTA_VOLTAGE,
                ATTR_CYCLE_CAP,
                #                ATTR_RUNTIME, # is available?
                ATTR_TEMPERATURE,
            },
        )

        return data
