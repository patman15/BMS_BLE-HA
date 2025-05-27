"""Test the Jikong BMS implementation."""

import asyncio
from collections.abc import Buffer
from copy import deepcopy
from typing import Final
from uuid import UUID

from bleak.backends.characteristic import BleakGATTCharacteristic
from bleak.backends.descriptor import BleakGATTDescriptor
from bleak.backends.service import BleakGATTService, BleakGATTServiceCollection
from bleak.exc import BleakError
from bleak.uuids import normalize_uuid_str, uuidstr_to_str
import pytest

from custom_components.bms_ble.plugins.basebms import BMSsample
from custom_components.bms_ble.plugins.jikong_bms import BMS, BMSmode, crc_sum

from .bluetooth import generate_ble_device
from .conftest import MockBleakClient

BT_FRAME_SIZE = 29

_PROTO_DEFS: Final[dict[str, dict[str, bytearray]]] = {
    "JK02_24S": {
        "dev": bytearray(  # JK02_24S (SW: 10.08)
            b"\x55\xaa\xeb\x90\x03\x79\x4a\x4b\x2d\x42\x32\x41\x32\x30\x53\x32\x30\x50\x00\x00\x00"
            b"\x00\x31\x30\x2e\x58\x47\x00\x00\x00\x31\x30\x2e\x30\x38\x00\x00\x00\xe4\xe7\x6c\x03"
            b"\x11\x00\x00\x00\x4a\x4b\x2d\x42\x4d\x53\x2d\x41\x00\x00\x00\x00\x00\x00\x00\x00\x31"
            b"\x32\x33\x34\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x32\x32\x30\x37\x30\x31"
            b"\x00\x00\x32\x30\x33\x32\x38\x31\x36\x30\x31\x32\x00\x30\x30\x30\x30\x00\x4d\x61\x72"
            b"\x69\x6f\x00\x00\x00\x00\x00\x00\x00\x00\x61\x00\x00\x31\x32\x33\x34\x35\x36\x00\x00"
            b"\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00"
            b"\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00"
            b"\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00"
            b"\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00"
            b"\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00"
            b"\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00"
            b"\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00"
            b"\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00"
            b"\x00\x00\x00\x00\x00\x93"
        ),
        "ack": bytearray(
            b"\xaa\x55\x90\xeb\xc8\x01\x01\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x44\x41"
            b"\x54\x0d\x0a"
        ),  # ACKnowledge message with attached AT\r\n message (needs to be filtered)
        "cell": bytearray(  # JK02_24S (SW: 10.08)
            b"\x55\xaa\xeb\x90\x02\xc8\xee\x0c\xf2\x0c\xf1\x0c\xf0\x0c\xf0\x0c\xec\x0c\xf0\x0c\xed"
            b"\x0c\xed\x0c\xed\x0c\xed\x0c\xf0\x0c\xf1\x0c\xed\x0c\xee\x0c\xed\x0c\x00\x00\x00\x00"
            b"\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\xff\xff\x00\x00\xef\x0c\x05\x00\x01"
            b"\x09\x36\x00\x37\x00\x39\x00\x38\x00\x37\x00\x37\x00\x35\x00\x41\x00\x42\x00\x36\x00"
            b"\x37\x00\x3a\x00\x38\x00\x34\x00\x36\x00\x37\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00"
            b"\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\xeb\xce\x00\x00\xc7\x0d\x02\x00"
            b"\x19\x09\x00\x00\xb5\x00\xba\x00\xe4\x00\x00\x00\x02\x00\x00\x38\x5d\xba\x01\x00\x10"
            b"\x15\x03\x00\x3c\x00\x00\x00\xa4\x65\xb9\x00\x64\x00\xd9\x02\x8b\xe8\x6c\x03\x01\x01"
            b"\xb3\x06\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x07\x00\x01\x00\x00\x00\x23"
            b"\x04\x0b\x00\x00\x00\x9f\x19\x40\x40\x00\x00\x00\x00\xe2\x04\x00\x00\x00\x00\x00\x01"
            b"\x00\x03\x00\x00\x83\xd5\x37\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00"
            b"\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00"
            b"\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00"
            b"\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00"
            b"\x00\x00\x00\x00\x00\xbd"
        ),
    },
    "JK02_32S": {  # JK02_32 (SW: V11.48)
        "dev": bytearray(
            b"\x55\xaa\xeb\x90\x03\xa3\x4a\x4b\x5f\x42\x32\x41\x38\x53\x32\x30\x50\x00\x00\x00\x00"
            b"\x00\x31\x31\x2e\x58\x41\x00\x00\x00\x31\x31\x2e\x34\x38\x00\x00\x00\xe4\xa7\x46\x00"
            b"\x07\x00\x00\x00\x31\x32\x76\x34\x32\x30\x61\x00\x00\x00\x00\x00\x00\x00\x00\x00\x31"
            b"\x32\x33\x34\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x32\x34\x30\x37\x30\x34"
            b"\x00\x00\x34\x30\x34\x30\x39\x32\x43\x32\x32\x36\x32\x00\x30\x30\x30\x00\x49\x6e\x70"
            b"\x75\x74\x20\x55\x73\x65\x72\x64\x61\x74\x61\x00\x00\x31\x34\x30\x37\x30\x33\x00\x00"
            b"\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00"
            b"\x00\x00\x00\xfe\xf9\xff\xff\x1f\x2d\x00\x02\x00\x00\x00\x00\x90\x1f\x00\x00\x00\x00"
            b"\xc0\xd8\xe7\x32\x00\x00\x00\x01\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x07\x04\x00"
            b"\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x41\x00\x00\x00\x00\x00\x00\x00"
            b"\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00"
            b"\x00\x00\x00\x09\x00\x00\x00\x64\x00\x00\x00\x5f\x00\x00\x00\x00\x00\x00\x00\x00\x00"
            b"\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00"
            b"\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\xfe\xbf\x21\x06\x00\x00\x00"
            b"\x00\x00\x00\x00\x00\xd8"
        ),  # Vendor_ID: JK_B2A8S20P, SN: 404092C2262, HW: V11.XA, SW: V11.48, power-on: 7, Version: 4.28.0
        "ack": bytearray(
            b"\xaa\x55\x90\xeb\xc8\x01\x01\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x44\x41"
            b"\x54\x0d\x0a"
        ),  # ACKnowledge message with attached AT\r\n message (needs to be filtered)
        "cell": bytearray(
            b"\x55\xaa\xeb\x90\x02\xad\xf3\x0c\xf3\x0c\xf3\x0c\xf0\x0c\xf1\x0c\xf0\x0c\xf1\x0c\xf1"
            b"\x0c\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00"
            b"\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00"
            b"\x00\x00\x00\x00\x00\x00\x00\xff\x00\x00\x00\xf2\x0c\x03\x00\x00\x07\x38\x00\x37\x00"
            b"\x36\x00\x37\x00\x36\x00\x37\x00\x36\x00\x37\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00"
            b"\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00"
            b"\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x36\x01\x00"
            b"\x00\x00\x00\x8d\x67\x00\x00\x60\xdb\x02\x00\x69\xe4\xff\xff\x1c\x01\x24\x01\x00\x00"
            b"\x00\x00\x00\x00\x00\x44\x80\x2c\x02\x00\x50\x34\x03\x00\x15\x00\x00\x00\xbc\x62\x44"
            b"\x00\x64\x00\x00\x00\x1e\xf3\x68\x00\x01\x01\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00"
            b"\x00\x00\x00\x00\xff\x00\x01\x00\x00\x00\xf1\x03\x00\x00\x23\x00\x29\xb4\x3f\x40\x00"
            b"\x00\x00\x00\x5a\x0a\x00\x00\x00\x01\x00\x01\x00\x06\x00\x00\xef\x3d\x08\x04\x00\x00"
            b"\x00\x00\x36\x01\x00\x00\x00\x00\xf1\x03\x64\x39\x67\x00\x1a\x00\x00\x00\x80\x51\x01"
            b"\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x01\xfe\xff\x7f\xdc\x0f\x01\x00"
            b"\x80\x03\x00\x00\x00\xb4"
        ),
    },
    "JK02_32S_v15": {  # JK02_32 (SW: V15.38)
        "dev": bytearray(
            b"\x55\xaa\xeb\x90\x03\x21\x4a\x4b\x5f\x50\x42\x32\x41\x31\x36\x53\x32\x30\x50\x00\x00"
            b"\x00\x31\x35\x41\x00\x00\x00\x00\x00\x31\x35\x2e\x33\x38\x00\x00\x00\x20\x48\x01\x00"
            b"\x05\x00\x00\x00\x34\x31\x30\x31\x38\x34\x39\x32\x35\x35\x35\x00\x50\x00\x00\x00\x31"
            b"\x32\x33\x34\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x32\x35\x30\x32\x31\x30"
            b"\x00\x00\x34\x31\x30\x31\x38\x34\x39\x32\x35\x35\x35\x00\x30\x30\x30\x00\x4a\x4b\x2d"
            b"\x42\x4d\x53\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x37\x31\x32\x30\x33\x00\x00\x00"
            b"\x00\x00\x00\x00\x00\x00\x00\x00\x4a\x4b\x2d\x42\x4d\x53\x00\x00\x00\x00\x00\x00\x00"
            b"\x00\x00\x00\xfe\xff\xff\xff\x8f\xe9\x1d\x02\x00\x00\x00\x00\x90\x1f\x00\x00\x00\x00"
            b"\xc0\xd8\xe7\xfe\x3f\x00\x00\x01\x00\x00\x00\x00\x00\x00\x00\x00\x00\x02\xff\x67\x00"
            b"\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\xff\x0f\x00\x00\x00\x00\x00\x00"
            b"\x00\x00\x00\x00\x00\x00\x00\x00\x01\xff\x67\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00"
            b"\x00\x00\x00\x09\x08\x00\x01\x64\x00\x00\x00\x5f\x00\x00\x00\x3c\x00\x00\x00\x32\x00"
            b"\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x10\x0e\x00\x00\x0a\x50\x01\x1e\x00\x00\x00"
            b"\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\xfe\x9f\xe9\xff\x0f\x00\x00"
            b"\x00\x00\x00\x00\x00\xf1"
        ),  # TODO: values
        "ack": bytearray(
            b"\xaa\x55\x90\xeb\xc8\x01\x01\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x44\x41"
            b"\x54\x0d\x0a"
        ),  # ACKnowledge message with attached AT\r\n message (needs to be filtered)
        "cell": bytearray(
            b"\x55\xaa\xeb\x90\x02\xf7\x51\x0d\x50\x0d\x52\x0d\x52\x0d\x53\x0d\x51\x0d\x53\x0d\x57"
            b"\x0d\x58\x0d\x52\x0d\x54\x0d\x54\x0d\x53\x0d\x52\x0d\x53\x0d\x53\x0d\x00\x00\x00\x00"
            b"\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00"
            b"\x00\x00\x00\x00\x00\x00\x00\xff\xff\x00\x00\x53\x0d\x08\x00\x08\x01\x3b\x00\x3c\x00"
            b"\x47\x00\x49\x00\x55\x00\x5d\x00\x6a\x00\x77\x00\x7e\x00\x76\x00\x6d\x00\x6a\x00\x62"
            b"\x00\x4b\x00\x48\x00\x3d\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00"
            b"\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\xba\x00\x00"
            b"\x00\x00\x00\x2f\xd5\x00\x00\x0a\xbe\x15\x00\xfd\x65\x00\x00\xbf\x00\xbf\x00\x00\x00"
            b"\x00\x00\x00\x00\x00\x62\xf3\x2f\x04\x00\xc0\x45\x04\x00\x40\x00\x00\x00\xfe\x90\x11"
            b"\x01\x64\x00\x00\x00\x62\xe4\x4a\x01\x01\x01\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00"
            b"\x00\x00\x00\x00\xff\x00\x01\x00\x00\x00\xb2\x03\x45\x00\x00\x00\x54\x29\x40\x40\x00"
            b"\x00\x00\x00\x51\x15\x00\x00\x00\x01\x01\x01\x00\x06\x00\x00\xa2\x81\x00\x00\x00\x00"
            b"\x00\x00\xba\x00\xba\x00\xc3\x00\xb2\x03\x83\xa6\x9f\x09\x0b\x00\x00\x00\x80\x51\x01"
            b"\x00\x00\x00\x03\x02\x00\x00\x00\x00\x00\x00\x00\x00\x00\xfe\xff\x7f\xdc\x2f\x01\x01"
            b"\xb0\xcf\x07\x00\x00\x93"
        ),  # TODO: values
    },
}

_RESULT_DEFS: Final[dict[str, BMSsample]] = {
    "JK02_24S": {
        "cell_count": 16,
        "delta_voltage": 0.005,
        "temperature": 19.833,
        "voltage": 52.971,
        "current": 2.329,
        "balance_current": 0.002,
        "battery_level": 56,
        "cycle_charge": 113.245,
        "cycles": 60,
        "cell_voltages": [
            3.310,
            3.314,
            3.313,
            3.312,
            3.312,
            3.308,
            3.312,
            3.309,
            3.309,
            3.309,
            3.309,
            3.312,
            3.313,
            3.309,
            3.310,
            3.309,
        ],
        "cycle_capacity": 5998.701,
        "power": 123.369,
        "battery_charging": True,
        "temp_values": [18.1, 18.6, 22.8],
        "temp_sensors": 7,
        "problem": False,
        "problem_code": 0,
    },
    "JK02_32S": {
        "cell_count": 8,
        "delta_voltage": 0.003,
        "voltage": 26.509,
        "current": -7.063,
        "battery_level": 68,
        "cycle_charge": 142.464,
        "cycles": 21,
        "balance_current": 0.0,
        "temp_sensors": 255,
        "problem_code": 0,
        "temp_values": [31.0, 28.4, 29.2, 31.0],
        "cell_voltages": [3.315, 3.315, 3.315, 3.312, 3.313, 3.312, 3.313, 3.313],
        "cycle_capacity": 3776.578,
        "power": -187.233,
        "battery_charging": False,
        "runtime": 72613,
        "temperature": 29.9,
        "problem": False,
    },
    "JK02_32S_v15": {
        "cell_count": 16,
        "delta_voltage": 0.008,
        "voltage": 54.575,
        "current": 26.109,
        "battery_level": 98,
        "cycle_charge": 274.419,
        "cycles": 64,
        "balance_current": 0.0,
        "temp_sensors": 255,
        "problem_code": 0,
        "temp_values": [18.6, 19.1, 19.1, 18.6, 18.6, 19.5],
        "cell_voltages": [
            3.409,
            3.408,
            3.41,
            3.41,
            3.411,
            3.409,
            3.411,
            3.415,
            3.416,
            3.41,
            3.412,
            3.412,
            3.411,
            3.41,
            3.411,
            3.411,
        ],
        "cycle_capacity": 14976.417,
        "power": 1424.899,
        "battery_charging": True,
        "battery_mode": BMSmode.BULK,
        "temperature": 18.917,
        "problem": False,
    },
}


@pytest.fixture(
    name="protocol_type",
    params=["JK02_24S", "JK02_32S", "JK02_32S_v15"],
)
def proto(request: pytest.FixtureRequest) -> str:
    """Protocol fixture."""
    return request.param


class MockJikongBleakClient(MockBleakClient):
    """Emulate a Jikong BMS BleakClient."""

    HEAD_CMD: Final = bytearray(b"\xaa\x55\x90\xeb")
    CMD_INFO: Final = bytearray(b"\x96")
    DEV_INFO: Final = bytearray(b"\x97")
    _FRAME: dict[str, bytearray] = {}

    _task: asyncio.Task

    def _response(
        self, char_specifier: BleakGATTCharacteristic | int | str | UUID, data: Buffer
    ) -> bytearray:
        if char_specifier != 3:
            return bytearray()
        if bytearray(data)[0:5] == self.HEAD_CMD + self.CMD_INFO:
            return (
                bytearray(b"\x41\x54\x0d\x0a") + self._FRAME["cell"]
            )  # added AT\r\n command
        if bytearray(data)[0:5] == self.HEAD_CMD + self.DEV_INFO:
            return self._FRAME["dev"]

        return bytearray()

    async def _send_confirm(self) -> None:
        assert self._notify_callback, "send confirm called but notification not enabled"
        await asyncio.sleep(0.01)
        self._notify_callback(
            "MockJikongBleakClient",
            b"\xaa\x55\x90\xeb\xc8\x01\x01\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x44",
        )

    async def write_gatt_char(
        self,
        char_specifier: BleakGATTCharacteristic | int | str | UUID,
        data: Buffer,
        response: bool | None = None,
    ) -> None:
        """Issue write command to GATT."""

        assert (
            self._notify_callback
        ), "write to characteristics but notification not enabled"
        self._notify_callback(
            "MockJikongBleakClient", bytearray(b"\x41\x54\x0d\x0a")
        )  # interleaved AT\r\n command
        resp = self._response(char_specifier, data)
        for notify_data in [
            resp[i : i + BT_FRAME_SIZE] for i in range(0, len(resp), BT_FRAME_SIZE)
        ]:
            self._notify_callback("MockJikongBleakClient", notify_data)
        if (
            bytearray(data)[0:5] == self.HEAD_CMD + self.DEV_INFO
        ):  # JK BMS confirms commands with a command in reply
            self._task = asyncio.create_task(self._send_confirm())

    async def disconnect(self) -> bool:
        """Mock disconnect and wait for send task."""
        await asyncio.wait_for(self._task, 0.1)
        assert self._task.done(), "send task still running!"
        return await super().disconnect()

    class JKservice(BleakGATTService):
        """Mock the main battery info service from JiKong BMS."""

        class CharBase(BleakGATTCharacteristic):
            """Basic characteristic for common properties.

            Note that Jikong BMS has two characteristics with same UUID!
            """

            @property
            def service_handle(self) -> int:
                """The integer handle of the Service containing this characteristic."""
                return 0

            @property
            def handle(self) -> int:
                """The handle for this characteristic."""
                return 3

            @property
            def service_uuid(self) -> str:
                """The UUID of the Service containing this characteristic."""
                return normalize_uuid_str("ffe0")

            @property
            def uuid(self) -> str:
                """The UUID for this characteristic."""
                return normalize_uuid_str("ffe1")

            @property
            def descriptors(self) -> list[BleakGATTDescriptor]:
                """List of descriptors for this service."""
                return []

            def get_descriptor(
                self, specifier: int | str | UUID
            ) -> BleakGATTDescriptor | None:
                """Get a descriptor by handle (int) or UUID (str or uuid.UUID)."""
                raise NotImplementedError

            def add_descriptor(self, descriptor: BleakGATTDescriptor) -> None:
                """Add a :py:class:`~BleakGATTDescriptor` to the characteristic.

                Should not be used by end user, but rather by `bleak` itself.
                """
                raise NotImplementedError

        class CharNotify(CharBase):
            """Characteristic for notifications."""

            @property
            def properties(self) -> list[str]:
                """Properties of this characteristic."""
                return ["notify"]

        class CharWrite(CharBase):
            """Characteristic for writing."""

            @property
            def properties(self) -> list[str]:
                """Properties of this characteristic."""
                return ["write", "write-without-response"]

        class CharFaulty(CharBase):
            """Characteristic for writing."""

            @property
            def uuid(self) -> str:
                """The UUID for this characteristic."""
                return normalize_uuid_str("0000")

            @property
            def properties(self) -> list[str]:
                """Properties of this characteristic."""
                return ["write", "write-without-response"]

        @property
        def handle(self) -> int:
            """The handle of this service."""

            return 2

        @property
        def uuid(self) -> str:
            """The UUID to this service."""

            return normalize_uuid_str("ffe0")

        @property
        def description(self) -> str:
            """String description for this service."""

            return uuidstr_to_str(self.uuid)

        @property
        def characteristics(self) -> list[BleakGATTCharacteristic]:
            """List of characteristics for this service."""

            return [
                self.CharNotify(None, lambda: 350),
                self.CharWrite(None, lambda: 350),
                self.CharFaulty(None, lambda: 350),  # leave last!
            ]

        def add_characteristic(self, characteristic: BleakGATTCharacteristic) -> None:
            """Add a :py:class:`~BleakGATTCharacteristic` to the service.

            Should not be used by end user, but rather by `bleak` itself.
            """
            raise NotImplementedError

    @property
    def services(self) -> BleakGATTServiceCollection:
        """Emulate JiKong BT service setup."""

        serv_col = BleakGATTServiceCollection()
        serv_col.add_service(self.JKservice(None))

        return serv_col


class MockStreamBleakClient(MockJikongBleakClient):
    """Mock JiKong BMS that already sends battery data (no request required)."""

    async def _send_all(self) -> None:
        assert (
            self._notify_callback
        ), "send_all frames called but notification not enabled"
        for resp in self._FRAME.values():
            self._notify_callback("MockJikongBleakClient", resp)
            await asyncio.sleep(0.01)

    async def write_gatt_char(
        self,
        char_specifier: BleakGATTCharacteristic | int | str | UUID,
        data: Buffer,
        response: bool | None = None,
    ) -> None:
        """Issue write command to GATT."""

        assert (
            self._notify_callback
        ), "write to characteristics but notification not enabled"
        self._notify_callback(
            "MockJikongBleakClient", bytearray(b"\x41\x54\x0d\x0a")
        )  # interleaved AT\r\n command
        if bytearray(data).startswith(
            self.HEAD_CMD + self.DEV_INFO
        ):  # send all responses as a series
            self._task = asyncio.create_task(self._send_all())


class MockWrongBleakClient(MockBleakClient):
    """Mock invalid service for JiKong BMS."""

    @property
    def services(self) -> BleakGATTServiceCollection:
        """Emulate JiKong BT service setup."""

        return BleakGATTServiceCollection()


class MockInvalidBleakClient(MockJikongBleakClient):
    """Emulate a Jikong BMS BleakClient with disconnect error."""

    async def disconnect(self) -> bool:
        """Mock disconnect to raise BleakError."""
        raise BleakError


class MockOversizedBleakClient(MockJikongBleakClient):
    """Emulate a Jikong BMS BleakClient returning wrong data length."""

    def _response(
        self, char_specifier: BleakGATTCharacteristic | int | str | UUID, data: Buffer
    ) -> bytearray:
        if char_specifier != 3:
            return bytearray()
        if bytearray(data)[0:5] == self.HEAD_CMD + self.CMD_INFO:
            return (  # added AT\r\n command and oversized
                bytearray(b"\x41\x54\x0d\x0a") + self._FRAME["cell"] + bytearray(6)
            )
        if bytearray(data)[0:5] == self.HEAD_CMD + self.DEV_INFO:
            return self._FRAME["dev"] + bytearray(6)  # oversized

        return bytearray()


@pytest.mark.asyncio
async def test_update(
    monkeypatch, patch_bleak_client, protocol_type, reconnect_fixture
) -> None:
    """Test Jikong BMS data update."""

    monkeypatch.setattr(MockJikongBleakClient, "_FRAME", _PROTO_DEFS[protocol_type])

    patch_bleak_client(MockJikongBleakClient)

    bms = BMS(
        generate_ble_device("cc:cc:cc:cc:cc:cc", "MockBLEdevice", None, -73),
        reconnect_fixture,
    )

    assert await bms.async_update() == _RESULT_DEFS[protocol_type]

    # query again to check already connected state
    assert await bms.async_update() == _RESULT_DEFS[protocol_type]
    assert bms._client and bms._client.is_connected is not reconnect_fixture

    await bms.disconnect()


async def test_hide_temp_sensors(
    monkeypatch, patch_bleak_client, protocol_type
) -> None:
    """Test Jikong BMS data update with not connected temperature sensors."""

    temp12_hide: dict[str, bytearray] = deepcopy(_PROTO_DEFS[protocol_type])

    # clear temp sensor #2
    if protocol_type == "JK02_24S":
        temp12_hide["cell"][182:184] = bytearray(b"\x03\x00")
        temp12_hide["cell"][132:134] = bytearray(b"\x30\xf8")  # -200.0
    else:
        temp12_hide["cell"][214:216] = bytearray(b"\xfb\x00")
        temp12_hide["cell"][162:164] = bytearray(b"\x30\xf8")  # -200.0
    # recalculate CRC
    temp12_hide["cell"][-1] = crc_sum(temp12_hide["cell"][:-1])

    monkeypatch.setattr(MockJikongBleakClient, "_FRAME", temp12_hide)

    patch_bleak_client(MockJikongBleakClient)

    bms = BMS(generate_ble_device("cc:cc:cc:cc:cc:cc", "MockBLEdevice", None, -73))

    # modify result dict to match removed temp#1, temp#2
    ref_result: BMSsample = deepcopy(_RESULT_DEFS[protocol_type])
    if protocol_type == "JK02_24S":
        ref_result |= {"temp_sensors": 3, "temperature": 18.1}
    elif protocol_type == "JK02_32S":
        ref_result |= {"temp_sensors": 251, "temperature": 31.0}
    elif protocol_type == "JK02_32S_v15":
        ref_result |= {"temp_sensors": 251, "temperature": 18.825}

    temp_values: list[int | float] = ref_result.get("temp_values", [])
    temp_values.pop(1)  # remove sensor 1
    temp_values.pop(1)  # remove sensor 2
    ref_result["temp_values"] = temp_values.copy()

    assert await bms.async_update() == ref_result

    await bms.disconnect()


async def test_stream_update(
    monkeypatch, patch_bleak_client, protocol_type, reconnect_fixture
) -> None:
    """Test Jikong BMS data update."""

    monkeypatch.setattr(MockStreamBleakClient, "_FRAME", _PROTO_DEFS[protocol_type])
    patch_bleak_client(MockStreamBleakClient)
    monkeypatch.setattr(  # mock that response has already been received
        "custom_components.bms_ble.plugins.basebms.asyncio.Event.is_set", lambda _: True
    )

    bms = BMS(
        generate_ble_device("cc:cc:cc:cc:cc:cc", "MockBLEdevice", None, -73),
        reconnect_fixture,
    )

    assert await bms.async_update() == _RESULT_DEFS[protocol_type]

    # query again to check already connected state
    assert await bms.async_update() == _RESULT_DEFS[protocol_type]
    assert bms._client and bms._client.is_connected is not reconnect_fixture

    await bms.disconnect()


async def test_invalid_response(
    monkeypatch, patch_bleak_client, patch_bms_timeout
) -> None:
    """Test data update with BMS returning invalid data."""

    patch_bms_timeout("jikong_bms")

    # return type 0x03 (first requested message) with incorrect CRC
    monkeypatch.setattr(
        MockInvalidBleakClient,
        "_response",
        lambda _s, _c, _d: bytearray(b"\x55\xaa\xeb\x90\x03") + bytearray(295),
    )

    patch_bleak_client(MockInvalidBleakClient)

    bms = BMS(generate_ble_device("cc:cc:cc:cc:cc:cc", "MockBLEdevice", None, -73))

    result: BMSsample = {}
    with pytest.raises(TimeoutError):
        result = await bms.async_update()
    assert not result

    await bms.disconnect()


async def test_invalid_frame_type(
    monkeypatch, patch_bleak_client, patch_bms_timeout
) -> None:
    """Test data update with BMS returning invalid data."""

    patch_bms_timeout("jikong_bms")

    monkeypatch.setattr(
        MockInvalidBleakClient,
        "_response",
        lambda _s, _c, _d: bytearray(b"\x55\xaa\xeb\x90\x05")
        + bytearray(295),  # invalid frame type (0x5)
    )

    patch_bleak_client(MockInvalidBleakClient)

    bms = BMS(generate_ble_device("cc:cc:cc:cc:cc:cc", "MockBLEdevice", None, -73))

    result: BMSsample = {}
    with pytest.raises(TimeoutError):
        result = await bms.async_update()
    assert not result

    await bms.disconnect()


async def test_oversized_response(
    monkeypatch, patch_bleak_client, protocol_type
) -> None:
    """Test data update with BMS returning oversized data, result shall still be ok."""

    monkeypatch.setattr(MockOversizedBleakClient, "_FRAME", _PROTO_DEFS[protocol_type])

    patch_bleak_client(MockOversizedBleakClient)

    bms = BMS(generate_ble_device("cc:cc:cc:cc:cc:cc", "MockBLEdevice", None, -73))

    assert await bms.async_update() == _RESULT_DEFS[protocol_type]

    await bms.disconnect()


async def test_invalid_device(patch_bleak_client) -> None:
    """Test data update with BMS returning invalid data."""

    patch_bleak_client(MockWrongBleakClient)

    bms = BMS(generate_ble_device("cc:cc:cc:cc:cc:cc", "MockBLEdevice", None, -73))

    result: BMSsample = {}

    with pytest.raises(
        ConnectionError, match=r"^Failed to detect characteristics from.*"
    ):
        result = await bms.async_update()

    assert not result

    await bms.disconnect()


async def test_non_stale_data(
    monkeypatch, patch_bleak_client, patch_bms_timeout
) -> None:
    """Test if BMS class is reset if connection is reset."""

    patch_bms_timeout("jikong_bms")

    monkeypatch.setattr(MockJikongBleakClient, "_FRAME", _PROTO_DEFS["JK02_32S"])

    orig_response = MockJikongBleakClient._response
    monkeypatch.setattr(
        MockJikongBleakClient,
        "_response",
        lambda _s, _c, _d: bytearray(b"\x55\xaa\xeb\x90\x05")
        + bytearray(10),  # invalid frame type (0x5)
    )

    patch_bleak_client(MockJikongBleakClient)

    bms = BMS(generate_ble_device("cc:cc:cc:cc:cc:cc", "MockBLEdevice", None, -73))

    # run an update which provides half a valid message and then disconnects
    result: BMSsample = {}
    with pytest.raises(TimeoutError):
        result = await bms.async_update()
    assert not result
    await bms.disconnect()

    # restore working BMS responses and run a test again to see if stale data is kept
    monkeypatch.setattr(MockJikongBleakClient, "_response", orig_response)

    assert await bms.async_update() == _RESULT_DEFS["JK02_32S"]


@pytest.fixture(
    name="problem_response",
    params=[
        (bytearray(b"\x01\x00"), "first_bit"),
        (bytearray(b"\x00\x80"), "last_bit"),
    ],
    ids=lambda param: param[1],
)
def prb_response(request) -> bytearray:
    """Return faulty response frame."""
    return request.param


async def test_problem_response(
    monkeypatch, patch_bleak_client, protocol_type: str, problem_response
) -> None:
    """Test data update with BMS returning system problem flags."""

    def frame_update(data: bytearray, update: bytearray, pos: int) -> None:
        data[pos : pos + 2] = update
        data[-1] = (int(data[-1]) + sum(update)) & 0xFF

    protocol_def: dict[str, dict[str, bytearray]] = deepcopy(_PROTO_DEFS)
    # set error flags in the copy

    frame_update(
        protocol_def[protocol_type]["cell"],
        problem_response[0],
        136 if protocol_type == "JK02_24S" else 166,
    )

    monkeypatch.setattr(MockJikongBleakClient, "_FRAME", protocol_def[protocol_type])

    patch_bleak_client(MockJikongBleakClient)

    bms = BMS(
        generate_ble_device("cc:cc:cc:cc:cc:cc", "MockBLEdevice", None, -73), False
    )

    assert await bms.async_update() == _RESULT_DEFS[protocol_type] | {
        "problem": True,
        "problem_code": 1 << (0 if problem_response[1] == "first_bit" else 15),
    }

    await bms.disconnect()
