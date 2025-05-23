"""Base class defintion for battery management systems (BMS)."""

from abc import ABC, abstractmethod
import asyncio
from collections.abc import Callable
import logging
from statistics import fmean
from typing import Any, Final, Literal, TypedDict

from bleak import BleakClient
from bleak.backends.characteristic import BleakGATTCharacteristic
from bleak.backends.device import BLEDevice
from bleak.exc import BleakError
from bleak_retry_connector import BLEAK_TRANSIENT_BACKOFF_TIME, establish_connection

from homeassistant.components.bluetooth import BluetoothServiceInfoBleak
from homeassistant.components.bluetooth.match import ble_device_matches
from homeassistant.loader import BluetoothMatcherOptional

type BMSvalue = Literal[
    "battery_charging",
    "battery_level",
    "current",
    "power",
    "temperature",
    "voltage",
    "cycles",
    "cycle_capacity",
    "cycle_charge",
    "delta_voltage",
    "problem",
    "runtime",
    "balance_current",
    "cell_count",
    "cell_voltages",
    "design_capacity",
    "pack_count",
    "temp_sensors",
    "temp_values",
    "problem_code",
]

type BMSpackvalue = Literal[
    "pack_voltages",
    "pack_currents",
    "pack_battery_levels",
    "pack_cycles",
]


class BMSsample(TypedDict, total=False):
    """Dictionary representing a sample of battery management system (BMS) data."""

    battery_charging: bool  # True: battery charging
    battery_level: int | float  # [%]
    current: float  # [A] (positive: charging)
    power: float  # [W] (positive: charging)
    temperature: int | float  # [°C]
    voltage: float  # [V]
    cycle_capacity: int | float  # [Wh]
    cycles: int  # [#]
    delta_voltage: float  # [V]
    problem: bool  # True: problem detected
    runtime: int  # [s]
    # detailed information
    balance_current: float  # [A]
    cell_count: int  # [#]
    cell_voltages: list[float]  # [V]
    cycle_charge: int | float  # [Ah]
    design_capacity: int  # [Ah]
    pack_count: int  # [#]
    temp_sensors: int  # [#]
    temp_values: list[int | float]  # [°C]
    problem_code: int  # BMS specific code, 0 no problem
    # battery pack data
    pack_voltages: list[float]  # [V]
    pack_currents: list[float]  # [A]
    pack_battery_levels: list[int | float]  # [%]
    pack_cycles: list[int]  # [#]


class AdvertisementPattern(TypedDict, total=False):
    """Optional patterns that can match Bleak advertisement data."""

    local_name: str  # name pattern that supports Unix shell-style wildcards
    service_uuid: str  # 128-bit UUID that the device must advertise
    service_data_uuid: str  # service data for the service UUID
    manufacturer_id: int  # required manufacturer ID
    manufacturer_data_start: list[int]  # required starting bytes of manufacturer data
    connectable: bool  # True if active connections to the device are required


class BaseBMS(ABC):
    """Abstract base class for battery management system."""

    MAX_RETRY: Final[int] = 3  # max number of retries for data requests
    _MAX_TIMEOUT_FACTOR: Final[int] = 8  # limit timout increase to 8x
    TIMEOUT: Final[float] = BLEAK_TRANSIENT_BACKOFF_TIME * _MAX_TIMEOUT_FACTOR
    _MAX_CELL_VOLT: Final[float] = 5.906  # max cell potential
    _HRS_TO_SECS: Final[int] = 60 * 60  # seconds in an hour

    def __init__(
        self,
        logger_name: str,
        ble_device: BLEDevice,
        reconnect: bool = False,
    ) -> None:
        """Intialize the BMS.

        notification_handler: the callback function used for notifications from 'uuid_rx()'
            characteristic. Not defined as abstract in this base class, as it can be both,
            a normal or async function

        Args:
            logger_name (str): name of the logger for the BMS instance (usually file name)
            ble_device (BLEDevice): the Bleak device to connect to
            reconnect (bool): if true, the connection will be closed after each update

        """
        assert (
            getattr(self, "_notification_handler", None) is not None
        ), "BMS class must define _notification_handler method"
        self._ble_device: Final[BLEDevice] = ble_device
        self._reconnect: Final[bool] = reconnect
        self.name: Final[str] = self._ble_device.name or "undefined"
        self._log: Final[logging.Logger] = logging.getLogger(
            f"{logger_name.replace('.plugins', '')}::{self.name}:"
            f"{self._ble_device.address[-5:].replace(':','')})"
        )
        self._inv_wr_mode: bool = False  # invert write mode (WNR <-> W)
        self._reconnect_request: bool = False  # request reconnect if write mode changed

        self._log.debug(
            "initializing %s, BT address: %s", self.device_id(), ble_device.address
        )
        self._client: BleakClient = BleakClient(
            self._ble_device,
            disconnected_callback=self._on_disconnect,
            services=[*self.uuid_services()],
        )
        self._data: bytearray = bytearray()
        self._data_event: Final[asyncio.Event] = asyncio.Event()

    @staticmethod
    @abstractmethod
    def matcher_dict_list() -> list[AdvertisementPattern]:
        """Return a list of Bluetooth advertisement matchers."""

    @staticmethod
    @abstractmethod
    def device_info() -> dict[str, str]:
        """Return a dictionary of device information.

        keys: manufacturer, model
        """

    @classmethod
    def device_id(cls) -> str:
        """Return device information as string."""
        return " ".join(cls.device_info().values())

    @classmethod
    def supported(cls, discovery_info: BluetoothServiceInfoBleak) -> bool:
        """Return true if service_info matches BMS type."""
        for matcher_dict in cls.matcher_dict_list():
            if ble_device_matches(
                BluetoothMatcherOptional(**matcher_dict), discovery_info
            ):
                return True
        return False

    @staticmethod
    @abstractmethod
    def uuid_services() -> list[str]:
        """Return list of 128-bit UUIDs of services required by BMS."""

    @staticmethod
    @abstractmethod
    def uuid_rx() -> str:
        """Return 16-bit UUID of characteristic that provides notification/read property."""

    @staticmethod
    @abstractmethod
    def uuid_tx() -> str:
        """Return 16-bit UUID of characteristic that provides write property."""

    @staticmethod
    def _calc_values() -> frozenset[BMSvalue]:
        """Return values that the BMS cannot provide and need to be calculated.

        See _add_missing_values() function for the required input to actually do so.
        """
        return frozenset()

    @staticmethod
    def _add_missing_values(data: BMSsample, values: frozenset[BMSvalue]) -> None:
        """Calculate missing BMS values from existing ones.

        Args:
            data: data dictionary with values received from BMS
            values: list of values to calculate and add to the dictionary

        Returns:
            None

        """
        if not values or not data:
            return

        def can_calc(value: BMSvalue, using: frozenset[BMSvalue]) -> bool:
            """Check value to add does not exist, is requested, and needed data is available."""
            return (value in values) and (value not in data) and using.issubset(data)

        cell_voltages: Final[list[float]] = data.get("cell_voltages", [])
        battery_level: Final[int | float] = data.get("battery_level", 0)
        current: Final[float] = data.get("current", 0)

        calculations: dict[BMSvalue, tuple[set[BMSvalue], Callable[[], Any]]] = {
            "voltage": ({"cell_voltages"}, lambda: round(sum(cell_voltages), 3)),
            "delta_voltage": (
                {"cell_voltages"},
                lambda: (
                    round(max(cell_voltages) - min(cell_voltages), 3)
                    if len(cell_voltages)
                    else None
                ),
            ),
            "cycle_charge": (
                {"design_capacity", "battery_level"},
                lambda: (data.get("design_capacity", 0) * battery_level) / 100,
            ),
            "battery_level": (
                {"design_capacity", "cycle_charge"},
                lambda: round(
                    data.get("cycle_charge", 0) * data.get("design_capacity", 0) / 100,
                    1,
                ),
            ),
            "cycle_capacity": (
                {"voltage", "cycle_charge"},
                lambda: round(data.get("voltage", 0) * data.get("cycle_charge", 0), 3),
            ),
            "power": (
                {"voltage", "current"},
                lambda: round(data.get("voltage", 0) * current, 3),
            ),
            "battery_charging": ({"current"}, lambda: current > 0),
            "runtime": (
                {"current", "cycle_charge"},
                lambda: (
                    int(
                        data.get("cycle_charge", 0)
                        / abs(current)
                        * BaseBMS._HRS_TO_SECS
                    )
                    if current < 0
                    else None
                ),
            ),
            "temperature": (
                {"temp_values"},
                lambda: (
                    round(fmean(data.get("temp_values", [])), 3)
                    if data.get("temp_values")
                    else None
                ),
            ),
        }

        for attr, (required, calc_func) in calculations.items():
            if (
                can_calc(attr, frozenset(required))
                and (value := calc_func()) is not None
            ):
                data[attr] = value

        # do sanity check on values to set problem state
        data["problem"] = any(
            [
                data.get("problem", False),
                data.get("problem_code", False),
                data.get("voltage") is not None and data.get("voltage", 0) <= 0,
                any(v <= 0 or v > BaseBMS._MAX_CELL_VOLT for v in cell_voltages),
                data.get("delta_voltage", 0) > BaseBMS._MAX_CELL_VOLT,
                data.get("cycle_charge") is not None
                and data.get("cycle_charge", 0.0) <= 0.0,
                battery_level > 100,
            ]
        )

    def _on_disconnect(self, _client: BleakClient) -> None:
        """Disconnect callback function."""

        self._log.debug("disconnected from BMS")

    async def _init_connection(self) -> None:
        # reset any stale data from BMS
        self._data.clear()
        self._data_event.clear()

        await self._client.start_notify(
            self.uuid_rx(), getattr(self, "_notification_handler")
        )

    async def _connect(self) -> None:
        """Connect to the BMS and setup notification if not connected."""

        if self._client.is_connected:
            self._log.debug("BMS already connected")
            return

        self._log.debug("connecting BMS")
        self._client = await establish_connection(
            client_class=BleakClient,
            device=self._ble_device,
            name=self._ble_device.address,
            disconnected_callback=self._on_disconnect,
            services=[*self.uuid_services()],
        )

        try:
            await self._init_connection()
        except Exception as err:
            self._log.info(
                "failed to initialize BMS connection (%s)", type(err).__name__
            )
            await self.disconnect()
            raise

    def _write_mode(self, char: int | str) -> Literal["W", "WNR"]:
        char_tx: Final[BleakGATTCharacteristic | None] = (
            self._client.services.get_characteristic(char)
        )
        return "W" if char_tx and "write" in char_tx.properties else "WNR"

    async def _await_reply(
        self,
        data: bytes,
        char: int | str | None = None,
        wait_for_notify: bool = True,
        max_size: int = 0,
        no_reconnect: bool = False,
    ) -> None:
        """Send data to the BMS and wait for valid reply notification."""

        write_mode: Final[Literal["W", "WNR"]] = self._write_mode(
            char or self.uuid_tx()
        )

        for attempt in range(BaseBMS.MAX_RETRY):
            self._data_event.clear()  # clear event before requesting new data
            try:
                for chunk in (
                    data[i : i + (max_size or len(data))]
                    for i in range(0, len(data), max_size or len(data))
                ):
                    self._log.debug(
                        "TX BLE data #%i (%s%s): %s",
                        attempt + 1,
                        "!" if self._inv_wr_mode else "",
                        write_mode,
                        chunk.hex(" "),
                    )
                    await self._client.write_gatt_char(
                        char or self.uuid_tx(),
                        chunk,
                        response=(write_mode == "W") != self._inv_wr_mode,
                    )
                if wait_for_notify:
                    await asyncio.wait_for(
                        self._wait_event(),
                        BLEAK_TRANSIENT_BACKOFF_TIME
                        * min(2**attempt, BaseBMS._MAX_TIMEOUT_FACTOR),
                    )
                break # leave loop if no exception
            except (BleakError, TimeoutError) as exc:
                self._log.debug("TX BLE data failed (%s): %s", type(exc).__name__, exc)
                if not isinstance(exc, TimeoutError) or attempt == BaseBMS.MAX_RETRY-1:
                    self._inv_wr_mode = not self._inv_wr_mode
                    self._reconnect_request = not no_reconnect
                    raise

    async def disconnect(self) -> None:
        """Disconnect the BMS, includes stoping notifications."""

        if self._client.is_connected:
            self._log.debug("disconnecting BMS")
            try:
                self._data_event.clear()
                await self._client.disconnect()
            except BleakError:
                self._log.warning("disconnect failed!")

    async def _wait_event(self) -> None:
        """Wait for data event and clear it."""
        await self._data_event.wait()
        self._data_event.clear()

    @abstractmethod
    async def _async_update(self) -> BMSsample:
        """Return a dictionary of BMS values (keys need to come from the SENSOR_TYPES list)."""

    async def async_update(self) -> BMSsample:
        """Retrieve updated values from the BMS using method of the subclass.

        Args:
            raw (bool): if true, the raw data from the BMS is returned without
                any calculations or missing values added

        Returns:
            BMSsample: dictionary with BMS values

        """
        await self._connect()

        data: BMSsample = await self._async_update()
        self._add_missing_values(data, self._calc_values())

        if self._reconnect or self._reconnect_request:
            # disconnect after data update to force reconnect next time (slow!)
            self._reconnect_request = False
            await self.disconnect()

        return data


def crc_modbus(data: bytearray) -> int:
    """Calculate CRC-16-CCITT MODBUS."""
    crc: int = 0xFFFF
    for i in data:
        crc ^= i & 0xFF
        for _ in range(8):
            crc = (crc >> 1) ^ 0xA001 if crc % 2 else (crc >> 1)
    return crc & 0xFFFF


def lrc_modbus(data: bytearray) -> int:
    """Calculate MODBUS LRC."""
    return ((sum(data) ^ 0xFFFF) + 1) & 0xFFFF


def crc_xmodem(data: bytearray) -> int:
    """Calculate CRC-16-CCITT XMODEM."""
    crc: int = 0x0000
    for byte in data:
        crc ^= byte << 8
        for _ in range(8):
            crc = (crc << 1) ^ 0x1021 if (crc & 0x8000) else (crc << 1)
    return crc & 0xFFFF


def crc8(data: bytearray) -> int:
    """Calculate CRC-8/MAXIM-DOW."""
    crc: int = 0x00  # Initialwert für CRC

    for byte in data:
        crc ^= byte
        for _ in range(8):
            crc = (crc >> 1) ^ 0x8C if crc & 0x1 else crc >> 1

    return crc & 0xFF


def crc_sum(frame: bytearray, size: int = 1) -> int:
    """Calculate the checksum of a frame using a specified size.

    size : int, optional
        The size of the checksum in bytes (default is 1).
    """
    return sum(frame) & ((1 << (8 * size)) - 1)
