"""Module to support Offgridtec Smart Pro BMS."""

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
)

from .basebms import BaseBMS, BMSsample

LOGGER: Final = logging.getLogger(__name__)
BAT_TIMEOUT: Final = 1

# magic crypt sequence of length 16
CRYPT_SEQ: Final = [2, 5, 4, 3, 1, 4, 1, 6, 8, 3, 7, 2, 5, 8, 9, 3]
# setup UUIDs, e.g. for receive: '0000fff4-0000-1000-8000-00805f9b34fb'
UUID_RX: Final = normalize_uuid_str("fff4")
UUID_TX: Final = normalize_uuid_str("fff6")
UUID_SERVICE: Final = normalize_uuid_str("fff0")


class BMS(BaseBMS):
    """Offgridtec LiFePO4 Smart Pro type A and type B battery class implementation."""

    IDX_NAME: Final = 0
    IDX_LEN: Final = 1
    IDX_FCT: Final = 2

    def __init__(self, ble_device: BLEDevice, reconnect: bool = False) -> None:
        """Intialize private BMS members."""
        self._reconnect = reconnect
        self._ble_device = ble_device
        self._client: BleakClient | None = None
        self._data_event = asyncio.Event()

        assert self._ble_device.name is not None
        self._type = self._ble_device.name[9]
        self._key = sum(
            CRYPT_SEQ[int(c, 16)] for c in (f"{int(self._ble_device.name[10:]):0>4X}")
        ) + (5 if (self._type == "A") else 8)
        LOGGER.info(
            "%s type: %c, ID: %s, key: 0x%x",
            self.device_id(),
            self._type,
            self._ble_device.name[10:],
            self._key,
        )
        self._values: BMSsample  # dictionary of BMS return values
        self._REGISTERS: dict[int, tuple[str, int, Callable[[int], int | float] | None]]
        if self._type == "A":
            self._REGISTERS = {
                # SOC (State of Charge)
                2: (ATTR_BATTERY_LEVEL, 1, None),
                4: (ATTR_CYCLE_CHRG, 3, lambda x: float(x) / 1000),
                8: (ATTR_VOLTAGE, 2, lambda x: float(x) / 1000),
                # MOS temperature
                12: (ATTR_TEMPERATURE, 2, lambda x: round(float(x) * 0.1 - 273.15, 1)),
                # 3rd byte of current is 0 (should be 1 as for B version)
                16: (ATTR_CURRENT, 3, lambda x: float(x) / 100),
                24: (ATTR_RUNTIME, 2, lambda x: int(x * 60)),
                44: (ATTR_CYCLES, 2, None),
                # Type A batteries have no cell voltage registers
            }
            self._HEADER = "+RAA"
        elif self._type == "B":
            self._REGISTERS = {
                # MOS temperature
                8: (ATTR_TEMPERATURE, 2, lambda x: round(float(x) * 0.1 - 273.15, 1)),
                9: (ATTR_VOLTAGE, 2, lambda x: float(x) / 1000),
                10: (ATTR_CURRENT, 3, lambda x: float(x) / 1000),
                # SOC (State of Charge)
                13: (ATTR_BATTERY_LEVEL, 1, None),
                15: (ATTR_CYCLE_CHRG, 3, lambda x: float(x) / 1000),
                18: (ATTR_RUNTIME, 2, lambda x: int(x * 60)),
                23: (ATTR_CYCLES, 2, None),
            }
            # add cell voltage registers, note: need to be last!
            self._REGISTERS |= {  # pragma: no branch
                63 - reg: (f"{KEY_CELL_VOLTAGE}{reg+1}", 2, lambda x: float(x) / 1000)
                for reg in range(16)
            }
            self._HEADER = "+R16"
        else:
            self._REGISTERS = {}
            LOGGER.exception("Unkown device type '%c'", self._type)

    @staticmethod
    def matcher_dict_list() -> list[dict[str, Any]]:
        """Return a list of Bluetooth matchers."""
        return [
            {
                "local_name": "SmartBat-A*",
                "service_uuid": UUID_SERVICE,
                "connectable": True,
            },
            {
                "local_name": "SmartBat-B*",
                "service_uuid": UUID_SERVICE,
                "connectable": True,
            },
        ]

    @staticmethod
    def device_info() -> dict[str, str]:
        """Return a dictionary of device information."""
        return {"manufacturer": "Offgridtec", "model": "LiFePo4 Smart Pro"}

    async def _wait_event(self) -> None:
        await self._data_event.wait()
        self._data_event.clear()

    async def async_update(self) -> BMSsample:
        """Update battery status information."""

        await self._connect()
        assert self._client is not None

        self._values = {}
        for key in list(self._REGISTERS):
            await self._read(key)
            try:
                await asyncio.wait_for(self._wait_event(), timeout=BAT_TIMEOUT)
            except TimeoutError:
                LOGGER.debug(
                    "Reading %s timed out", self._REGISTERS[key][self.IDX_NAME]
                )
            if key > 48 and f"{KEY_CELL_VOLTAGE}{64-key}" not in self._values:
                break

        self.calc_values(
            self._values,
            {ATTR_CYCLE_CAP, ATTR_POWER, ATTR_BATTERY_CHARGING, ATTR_DELTA_VOLTAGE},
        )

        # remove remaining runtime if battery is charging
        if self._values.get(ATTR_RUNTIME) == 0xFFFF * 60:
            del self._values[ATTR_RUNTIME]

        if self._reconnect:
            # disconnect after data update to force reconnect next time (slow!)
            await self.disconnect()
        return self._values

    def _on_disconnect(self, _client: BleakClient) -> None:
        """Disconnect callback function."""

        LOGGER.debug("Disconnected from BMS (%s)", self._ble_device.name)

    def _notification_handler(self, sender, data: bytearray) -> None:
        LOGGER.debug("Received BLE data: %s", data)

        valid, reg, nat_value = self._ogt_response(data)

        # check that descrambled message is valid and from the right characteristic
        if valid and sender.uuid == UUID_RX:
            name, _length, func = self._REGISTERS[reg]
            value = func(nat_value) if func else nat_value
            LOGGER.debug(
                "Decoded data: reg: %s (#%i), raw: %i, value: %f",
                name,
                reg,
                nat_value,
                value,
            )
            self._values[name] = value
        else:
            LOGGER.debug("Response data is invalid")
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
        """Disconnect the BMS, includes stoping notifications."""

        if self._client and self._client.is_connected:
            LOGGER.debug("Disconnecting BMS (%s)", self._ble_device.name)
            try:
                self._data_event.clear()
                await self._client.disconnect()
            except BleakError:
                LOGGER.warning("Disconnect failed!")

    def _ogt_response(self, resp: bytearray) -> tuple[bool, int, int]:
        """Descramble a response from the BMS."""

        msg = bytearray((resp[x] ^ self._key) for x in range(len(resp))).decode(
            encoding="ascii"
        )
        LOGGER.debug("response: %s", msg[:-2])
        # verify correct response
        if msg[4:7] == "Err" or msg[:4] != "+RD," or msg[-2:] != "\r\n":
            return False, 0, 0
        # 16-bit value in network order (plus optional multiplier for 24-bit values)
        # multiplier has 1 as minimum due to current value in A type battery
        signed = len(msg) > 12
        value = int.from_bytes(
            bytes.fromhex(msg[6:10]), byteorder="little", signed=signed
        ) * (max(int(msg[10:12], 16), 1) if signed else 1)
        return True, int(msg[4:6], 16), value

    def _ogt_command(self, command: int) -> bytes:
        """Put together an scambled query to the BMS."""

        cmd = (
            f"{self._HEADER}{command:0>2X}{self._REGISTERS[command][self.IDX_LEN]:0>2X}"
        )
        LOGGER.debug("command: %s", cmd)

        return bytearray(ord(cmd[i]) ^ self._key for i in range(len(cmd)))

    async def _read(self, reg: int) -> None:
        """Read a specific BMS register."""
        assert self._client is not None

        msg = self._ogt_command(reg)
        LOGGER.debug("BLE cmd frame %s", msg)
        await self._client.write_gatt_char(UUID_TX, data=msg)
