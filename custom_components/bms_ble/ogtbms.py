""" Offgridtec LiFePO4 Smart Pro type A and type B battery class implementation"""
from bleak.backends.device import BLEDevice
from bleak import BleakClient, normalize_uuid_str
import asyncio
from homeassistant.core import callback

import logging

BAT_TIMEOUT = 1


class OGTBms:
    # magic crypt sequence of length 16
    _CRYPT_NAME = [2, 5, 4, 3, 1, 4, 1, 6, 8, 3, 7, 2, 5, 8, 9, 3]
    # '0000fff4-0000-1000-8000-00805f9b34fb'
    UUID_RX = normalize_uuid_str("FFF4")
    UUID_TX = normalize_uuid_str("FFF6")
    UUID_SERVICE = normalize_uuid_str("FFF0")

    def __init__(
            self,
            ble_device: BLEDevice,
            reconnect=False) -> None:
        self.logger = logging.getLogger(__name__)
        self._reconnect = reconnect
        self._ble_device = ble_device
        self._client: BleakClient = None
        self._data_event = asyncio.Event()
        self._connected = False  # flag to indicate active BLE connection
        self._type = self._ble_device.name[9]
        self._key = sum(self._CRYPT_NAME[int(c, 16)] for c in (
            f'{int(self._ble_device.name[10:]):0>4X}')) + (5 if (self._ble_device.name[9] == 'A') else 8)
        self.logger.info(
            f"Offgridtec LiFePo4 Smart Pro type: {self._type}, ID: {self._ble_device.name[10:]}, key: 0x{self._key:0>2X}")
        self._values = {}  # dictionary of queried values

        if self._type == 'A':
            self._OGT_REGISTERS = {
                # SOC (State of Charge)
                2: dict(name="battery_level", len=1, func=lambda x: x),
                4: dict(name="cycle_capacity", len=3, func=lambda x: float(x)/1000),
                8: dict(name="voltage", len=2, func=lambda x: float(x)/1000),
                # MOS temperature
                12: dict(name="temperature", len=2, func=lambda x: round(float(x)*0.1-273.15, 1)),
                16: dict(name="current", len=3, func=lambda x: float(x)/1000),
                24: dict(name="runtime", len=2, func=lambda x: x*60),
            }
            self._OGT_HEADER = "+RAA"
        elif self._type == 'B':
            self._OGT_REGISTERS = {
                # MOS temperature
                8: dict(name="temperature", len=2, func=lambda x: round(float(x)*0.1-273.15, 1)),
                9: dict(name="voltage", len=2, func=lambda x: float(x)/1000),
                10: dict(name="current", len=3, func=lambda x: float(x)/1000),
                # SOC (State of Charge)
                13: dict(name="battery_level", len=1, func=lambda x: x),
                15: dict(name="cycle_capacity", len=3, func=lambda x: float(x)/1000),
                18: dict(name="runtime", len=2, func=lambda x: x*60),
                # 23: dict(name = "num_cycles", len = 2, func = lambda x: x),
                # 24: dict(name = "capacity", len = 3, func = lambda x: float(x & 0x00FFFF)*0.01)
                # 25: dict(name = "nom_voltage", len = 2, func = lambda x: float(x)/1000),
            }
            self._OGT_HEADER = "+R16"
        else:
            self._OGT_REGISTERS = {}
            self.logger.error(f"unkown device type: {self._type}")

    async def _wait_event(self) -> None:
        await self._data_event.wait()
        self._data_event.clear()

    @callback
    async def update(self) -> dict:
        """ Update battery status information """

        try:
            await self._connect()
        except Exception as e:
            self.logger.debug(
                f"failed to connect: {str(e)} ({type(e).__name__})")
            raise IOError
        except asyncio.CancelledError:
            return {}

        self._values.clear()
        for key in list(self._OGT_REGISTERS):
            await self._read(key)
            try:
                await asyncio.wait_for(self._wait_event(), timeout=BAT_TIMEOUT)
            except TimeoutError:
                self._logger.debug("timeout reading: %s",
                                   self._OGT_REGISTERS[key].name)
        if {"cycle_capacity", "voltage"}.issubset(self._values.keys()):
            # multiply with voltage to get Wh instead of Ah
            self._values["cycle_capacity"] = round(
                self._values["cycle_capacity"]*self._values["voltage"], 6)
        else:
            del self._values["cycle_capacity"]

        self.logger.debug("data collected: %s", self._values)
        if self._reconnect:
            # disconnect after data update to force reconnect next time (slow!)
            await self._disconnect()
        return self._values

    def _on_disconnect(self, client: BleakClient) -> None:
        """ disconnect callback """

        self.logger.debug("disconnected from %s", client.address)
        self._connected = False

    def _notification_handler(self, sender, data: bytearray) -> None:
        self.logger.debug(f"ble data frame {data}")

        valid, reg, nat_value = self._ogt_response(data)

        # check that descambled message is valid and from the right characteristic
        if valid and sender.uuid == self.UUID_RX:
            register = self._OGT_REGISTERS[reg]
            value = register['func'](nat_value)
            self.logger.debug(
                f"reg: {register['name']} (#{reg}), raw: {nat_value}, value: {value}")
            self._values[register['name']] = value
        else:
            self.logger.debug("invalid response")
        self._data_event.set()

    async def _connect(self) -> None:
        """ connect to the BMS and setup notification if not connected """

        if not self._connected:
            self.logger.debug(f"connecting BMS {self._ble_device.name}")
            self._client = BleakClient(self._ble_device.address,
                                       disconnected_callback=self._on_disconnect,
                                       services=[self.UUID_SERVICE]
                                       )
            await self._client.connect()
            await self._client.start_notify(self.UUID_RX, self._notification_handler)
            self._connected = True
        else:
            self.logger.debug(f"BMS {self._ble_device.name} already connected")

    async def _disconnect(self) -> None:
        """ disconnect the BMS, includes stoping notifications """
        if self._connected:
            self.logger.debug(f"disconnecting BMS ({self._ble_device.name})")
            try:
                await self._client.stop_notify(self.UUID_RX)
                self._data_event.clear()
                await self._client.disconnect()
            except:
                self.logger.warning("disconnect failed!")

        self._client = None

    def _ogt_response(self, resp: bytearray) -> tuple:
        """ descramble a response from the BMS """

        msg = bytearray(((resp[x] ^ self._key) for x in range(
            0, len(resp)))).decode(encoding="ascii")
        self.logger.debug(f"response: {msg[:-2]}")
        # verify correct response
        if msg[:4] != "+RD," or msg[-2:] != "\r\n":
            return False, None, None
        # 16-bit value in network order (plus optional multiplier for 24-bit values)
        signed = len(msg) > 12
        value = int.from_bytes(bytes.fromhex(
            msg[6:10]), byteorder='little', signed=signed) * (int(msg[10:12], 16) if signed else 1)
        return True, int(msg[4:6], 16), value

    def _ogt_command(self, command: int) -> bytes:
        """ put together an scambled query to the BMS """

        cmd = f"{self._OGT_HEADER}{command:0>2X}{self._OGT_REGISTERS[command]['len']:0>2X}"
        self.logger.debug(f"command: {cmd}")

        return bytearray(ord(cmd[i]) ^ self._key for i in range(len(cmd)))

    async def _read(self, reg: int) -> None:
        """ read a specific BMS register """

        msg = self._ogt_command(reg)
        self.logger.debug(f"ble cmd frame {msg}")
        await self._client.write_gatt_char(self.UUID_TX, data=msg)
