"""Test the BLE Battery Management System base class functions."""

from collections.abc import Buffer, Callable
from typing import Final
from uuid import UUID

from bleak.backends.characteristic import BleakGATTCharacteristic
from bleak.backends.device import BLEDevice
from bleak.exc import BleakError
from bleak.uuids import normalize_uuid_str
import pytest

from custom_components.bms_ble.plugins.basebms import (
    AdvertisementPattern,
    BaseBMS,
    BMSsample,
    crc8,
    crc_modbus,
    crc_xmodem,
)

from .bluetooth import generate_ble_device
from .conftest import MockBleakClient


class MockWriteModeBleakClient(MockBleakClient):
    """Emulate a BleakClient with selectable write mode response."""

    # The following attributes are used to simulate the behavior of the BleakClient
    # They need to be set via monkeypatching in the test since init() is called by the BMS
    PATTERN: list[bytes | Exception | None] = []
    VALID_WRITE_MODES: list[str] = ["write-without_response", "write"]
    EXP_WRITE_RESPONSE: list[bool] = []

    async def write_gatt_char(
        self,
        char_specifier: BleakGATTCharacteristic | int | str | UUID,
        data: Buffer,
        response: bool | None = None,
    ) -> None:
        """Issue write command to GATT."""
        await super().write_gatt_char(char_specifier, data, response)

        assert self._notify_callback is not None
        if self.PATTERN:
            # check if we have a pattern to return
            pattern: bytes | Exception | None = self.PATTERN.pop(0)
            exp_wr_mode: Final[bool] = self.EXP_WRITE_RESPONSE.pop(0)
            if isinstance(pattern, Exception):
                raise pattern

            req_wr_mode: Final[str] = "write" if response else "write-without_response"
            assert response == exp_wr_mode, "write response mismatch"

            if isinstance(pattern, bytes) and req_wr_mode in self.VALID_WRITE_MODES:
                # check if we have a dict to return
                self._notify_callback("rx_char", bytearray(pattern))
                return

            # if None was selected do not return (trigger timeout) and wait for next pattern
            return

        # no pattern left, raise exception
        raise ValueError


class WMTestBMS(BaseBMS):
    """Test BMS implementation."""

    def __init__(
        self,
        char_tx_properties: list[str],
        ble_device: BLEDevice,
        reconnect: bool = False,
    ) -> None:
        """Initialize BMS."""
        super().__init__(ble_device, reconnect)
        self._char_tx_properties: list[str] = char_tx_properties

    @staticmethod
    def matcher_dict_list() -> list[AdvertisementPattern]:
        """Provide BluetoothMatcher definition."""
        return [{"local_name": "Test", "connectable": True}]

    @staticmethod
    def device_info() -> dict[str, str]:
        """Return device information for the battery management system."""
        return {"manufacturer": "Test Manufacturer", "model": "write mode test"}

    @staticmethod
    def uuid_services() -> list[str]:
        """Return list of 128-bit UUIDs of services required by BMS."""
        return [normalize_uuid_str("afe0")]

    @staticmethod
    def uuid_rx() -> str:
        """Return 16-bit UUID of characteristic that provides notification/read property."""
        return "afe1"

    @staticmethod
    def uuid_tx() -> str:
        """Return 16-bit UUID of characteristic that provides write property."""
        return "afe2"

    def _wr_response(self, char: int | str) -> bool:
        return bool("write" in self._char_tx_properties)

    def _notification_handler(
        self, _sender: BleakGATTCharacteristic, data: bytearray
    ) -> None:
        """Handle the RX characteristics notify event (new data arrives)."""
        self._log.debug("RX BLE data: %s", data)
        self._data = data
        self._data_event.set()

    async def _async_update(self) -> BMSsample:
        """Update battery status information."""
        await self._await_reply(b"mock_command")

        return {"problem_code": int.from_bytes(self._data, "big", signed=False)}

def test_calc_missing_values(bms_data_fixture: BMSsample) -> None:
    """Check if missing data is correctly calculated."""
    bms_data: BMSsample = bms_data_fixture
    ref: BMSsample = bms_data_fixture.copy()

    BaseBMS._add_missing_values(
        bms_data,
        frozenset(
            {
                "battery_charging",
                "cycle_capacity",
                "power",
                "runtime",
                "delta_voltage",
                "temperature",
                "voltage",  # check that not overwritten
            }
        ),
    )
    ref = ref | {
        "cycle_capacity": 238,
        "delta_voltage": 0.111,
        "power": (
            -91
            if bms_data.get("current", 0) < 0
            else 0 if bms_data.get("current") == 0 else 147
        ),
        # battery is charging if current is positive
        "battery_charging": bms_data.get("current", 0) > 0,
        "temperature": -34.396,
        "problem": False,
    }
    if bms_data.get("current", 0) < 0:
        ref |= {"runtime": 9415}

    assert bms_data == ref


def test_calc_voltage() -> None:
    """Check if missing data is correctly calculated."""
    bms_data: BMSsample = {"cell_voltages": [3.456, 3.567]}
    ref: BMSsample = bms_data.copy()
    BaseBMS._add_missing_values(bms_data, frozenset({"voltage"}))
    assert bms_data == ref | {"voltage": 7.023, "problem": False}


def test_calc_cycle_chrg() -> None:
    """Check if missing data is correctly calculated."""
    bms_data: BMSsample = {"battery_level": 73, "design_capacity": 125}
    ref: BMSsample = bms_data.copy()
    BaseBMS._add_missing_values(bms_data, frozenset({"cycle_charge"}))
    assert bms_data == ref | {"cycle_charge": 91.25, "problem": False}

def test_calc_battery_level() -> None:
    """Check if missing battery_level is correctly calculated."""
    bms_data: BMSsample = {"cycle_charge": 421, "design_capacity": 983}
    ref: BMSsample = bms_data.copy()
    BaseBMS._add_missing_values(bms_data, frozenset({"battery_level"}))
    assert bms_data == ref | {"battery_level": 42.8, "problem": False}

@pytest.fixture(
    name="problem_samples",
    params=[
        ({"voltage": -1}, "negative overall voltage"),
        ({"cell_voltages": [5.907]}, "high cell voltage"),
        ({"cell_voltages": [-0.001]}, "negative cell voltage"),
        ({"delta_voltage": 5.907}, "doubtful delta voltage"),
        ({"cycle_charge": 0}, "doubtful cycle charge"),
        ({"battery_level": 101}, "doubtful SoC"),
        ({"problem_code": 0x1}, "BMS problem code"),
        ({"problem": True}, "BMS problem report"),
    ],
    ids=lambda param: param[1],
)
def mock_bms_data(request: pytest.FixtureRequest) -> BMSsample:
    """Return BMS data to check error handling function."""
    return request.param[0]


def test_problems(problem_samples: BMSsample) -> None:
    """Check if missing data is correctly calculated."""
    bms_data: BMSsample = problem_samples.copy()

    BaseBMS._add_missing_values(bms_data, frozenset({"runtime"}))

    assert bms_data == problem_samples | {"problem": True}


@pytest.mark.parametrize(
    ("replies", "exp_wr_response", "exp_output"),
    [
        ([b"\x12"], [True], [0x12]),
        (
            [None] * 2 * (BaseBMS.MAX_RETRY),
            [True] * (BaseBMS.MAX_RETRY) + [False] * (BaseBMS.MAX_RETRY),
            [TimeoutError()],
        ),
        (
            [None] * (BaseBMS.MAX_RETRY - 1) + [b"\x13"],
            [True] * (BaseBMS.MAX_RETRY),
            [0x13],
        ),
        (
            [None] * (BaseBMS.MAX_RETRY) + [b"\x14"],
            [True] * (BaseBMS.MAX_RETRY) + [False],
            [0x14],
        ),
        (
            [BleakError()]
            + [None] * (BaseBMS.MAX_RETRY - 1)
            + [b"\x15"]
            + [None] * (BaseBMS.MAX_RETRY - 1)
            + [b"\x16"],
            [True] + [False] * BaseBMS.MAX_RETRY + [False] * BaseBMS.MAX_RETRY,
            [0x15, 0x16],
        ),
        (
            [None] * (BaseBMS.MAX_RETRY - 1) + [ValueError()],
            [True] * (BaseBMS.MAX_RETRY),
            [ValueError()],
        ),
    ],
    ids=[
        "basic_test",
        "no_response",
        "retry_count-1",
        "retry_count",
        "mode_switch",
        "unhandled_exc",
    ],
)
async def test_write_mode(
    monkeypatch,
    patch_bleak_client,
    patch_bms_timeout,
    replies: list[bytearray | Exception | None],
    exp_wr_response: list[bool],
    exp_output: list[int | Exception],
    request: pytest.FixtureRequest,
) -> None:
    """Check if write mode selection works correctly."""

    assert len(replies) == len(
        exp_wr_response
    ), "Replies and expected responses must match in length!"
    patch_bms_timeout()
    monkeypatch.setattr(MockWriteModeBleakClient, "PATTERN", replies)
    monkeypatch.setattr(MockWriteModeBleakClient, "EXP_WRITE_RESPONSE", exp_wr_response)

    patch_bleak_client(MockWriteModeBleakClient)

    bms = WMTestBMS(
        ["write-no-response", "write"],
        generate_ble_device("cc:cc:cc:cc:cc:cc", "MockBLEDevice", None, -73),
        False,
    )

    # NOTE: output must reflect the end result after one call, as init of HA resets the whole BMS!
    for output in exp_output:
        if isinstance(output, Exception):
            with pytest.raises(type(output)):
                await bms.async_update()
        else:
            assert await bms.async_update() == {
                "problem_code": output
            }, f"{request.node.name} failed!"
def test_crc_calculations() -> None:
    """Check if CRC calculations are correct."""
    # Example data for CRC calculation
    data: bytearray = bytearray([0x31, 0x32, 0x33, 0x34, 0x35, 0x36, 0x37, 0x38, 0x39])
    test_fn: list[tuple[Callable[[bytearray], int], int]] = [
        (crc_modbus, 0x4B37),
        (crc8, 0xA1),
        (crc_xmodem, 0x31C3),
    ]

    for crc_fn, expected_crc in test_fn:
        calculated_crc: int = crc_fn(data)
        assert (
            calculated_crc == expected_crc
        ), f"Expected {expected_crc}, got {calculated_crc}"
