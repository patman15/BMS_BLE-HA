"""Module to support Pro BMS."""

import asyncio
from typing import Final

from bleak.backends.characteristic import BleakGATTCharacteristic
from bleak.backends.device import BLEDevice
from bleak.uuids import normalize_uuid_str

from .basebms import AdvertisementPattern, BaseBMS, BMSdp, BMSsample, BMSvalue


class BMS(BaseBMS):
    """Pro BMS Smart Shunt class implementation."""

    # Protocol constants
    _HEAD: Final[bytes] = bytes([0x55, 0xAA])
    _MIN_LEN: Final[int] = 5
    _INIT_RESP: Final[int] = 0x03
    _RT_DATA: Final[int] = 0x04

    # Commands from btsnoop capture
    _CMD_INIT: Final[bytes] = bytes.fromhex("55aa0a0101558004077f648e682b")
    _CMD_ACK: Final[bytes] = bytes.fromhex("55aa070101558040000095")
    _CMD_DATA_STREAM: Final[bytes] = bytes.fromhex("55aa070101558042000097")
    # Critical 4th command that triggers data streaming (Function 0x43)
    _CMD_TRIGGER_DATA: Final[bytes] = bytes.fromhex("55aa0901015580430000120084")

    _FIELDS: Final[tuple[BMSdp, ...]] = (
        BMSdp("voltage", 8, 2, False, lambda x: x / 100),
        BMSdp(
            "current",
            12,
            4,
            False,
            lambda x: ((x & 0xFFFF) / 1000) * (-1 if (x >> 24) & 0x80 else 1),
        ),
        BMSdp("problem_code", 15, 4, False, lambda x: x & 0x7F),
        BMSdp(
            "temperature",
            16,
            3,
            False,
            lambda x: ((x & 0xFFFF) / 10) * (-1 if x >> 16 else 1),
        ),
        BMSdp("cycle_charge", 20, 4, False, lambda x: x / 100),
        BMSdp("battery_level", 24, 1, False, lambda x: x),
        BMSdp("power", 32, 4, False, lambda x: x / 100),
    )

    def __init__(self, ble_device: BLEDevice, reconnect: bool = True) -> None:
        """Initialize private BMS members."""
        super().__init__(__name__, ble_device, reconnect)
        self._valid_reply: int = BMS._RT_DATA

    @staticmethod
    def matcher_dict_list() -> list[AdvertisementPattern]:
        """Provide BluetoothMatcher definition."""
        return [
            AdvertisementPattern(
                local_name="Pro BMS",
                service_uuid=BMS.uuid_services()[0],
                connectable=True,
            )
        ]

    @staticmethod
    def device_info() -> dict[str, str]:
        """Return device information for the battery management system."""
        return {"manufacturer": "Pro BMS", "model": "Smart Shunt"}

    @staticmethod
    def uuid_services() -> list[str]:
        """Return list of 128-bit UUIDs of services required by BMS."""
        return [normalize_uuid_str("fff0")]

    @staticmethod
    def uuid_rx() -> str:
        """Return 16-bit UUID of characteristic that provides notification/read property."""
        return "fff4"

    @staticmethod
    def uuid_tx() -> str:
        """Return 16-bit UUID of characteristic that provides write property."""
        return "fff3"

    @staticmethod
    def _calc_values() -> frozenset[BMSvalue]:
        return frozenset({"battery_charging", "cycle_capacity", "runtime"})

    def _notification_handler(
        self, _sender: BleakGATTCharacteristic, data: bytearray
    ) -> None:
        self._log.debug("RX BLE data: %s", data)

        # Check for valid packet header
        if len(data) < BMS._MIN_LEN or not data.startswith(BMS._HEAD):
            self._log.debug("Invalid packet header")
            return

        if data[3] != self._valid_reply:
            self._log.debug("unexpected response (type 0x%X)", data[3])
            return

        if len(data) != data[2] + BMS._MIN_LEN:
            self._log.debug("incorrect frame length: %i).", len(self._data))
            return

        self._data = data
        self._data_event.set()

    async def _init_connection(
        self, char_notify: BleakGATTCharacteristic | int | str | None = None
    ) -> None:
        """Initialize RX/TX characteristics and protocol state."""
        await super()._init_connection()
        self._valid_reply = BMS._INIT_RESP

        # Perform complete initialization sequence if not already done
        self._log.debug("Starting initialization sequence")

        # Step 1: Send initialization command
        self._log.debug("Sending CMD_INIT")
        self._data_event.clear()
        await self._await_reply(BMS._CMD_INIT)
        # Step 2: Wait for initialization response

        # Step 3: Send ACK command
        self._log.debug("Sending CMD_ACK")
        await self._await_reply(BMS._CMD_ACK, wait_for_notify=False)

        # Small delay to ensure ACK is processed
        # await asyncio.sleep(0.1)

        # Step 4: Send data stream command
        self._log.debug("Sending CMD_DATA_STREAM")

        await self._await_reply(BMS._CMD_DATA_STREAM, wait_for_notify=False)

        # Small delay to ensure data stream command is processed
        # await asyncio.sleep(0.1)

        # Step 5: Send trigger data command 0x43 - CRITICAL for starting data flow
        self._log.debug("Sending CMD_TRIGGER_DATA")
        await self._await_reply(BMS._CMD_TRIGGER_DATA, wait_for_notify=False)

        self._log.debug("Initialization sequence complete")

        self._valid_reply = BMS._RT_DATA

    async def _async_update(self) -> BMSsample:
        """Update battery status information."""

        # Always clear the event to ensure we get fresh data on each update
        self._data_event.clear()
        try:
            # Wait for new data packet
            await asyncio.wait_for(self._wait_event(), timeout=BMS.TIMEOUT)
        except TimeoutError:
            await self.disconnect()
            raise

        result: BMSsample = BMS._decode_data(
            BMS._FIELDS, self._data, byteorder="little"
        )
        result["power"] *= -1 if result["current"] < 0 else 1
        return result
