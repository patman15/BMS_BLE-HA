"""Test the Felicity implementation."""

from collections.abc import Buffer
from typing import Final
from uuid import UUID

from bleak.backends.characteristic import BleakGATTCharacteristic

# from bleak.exc import BleakDeviceNotFoundError
from bleak.uuids import normalize_uuid_str
import pytest

from custom_components.bms_ble.plugins.felicity_bms import BMS

from .bluetooth import generate_ble_device
from .conftest import MockBleakClient

BT_FRAME_SIZE = 35


def ref_value() -> dict:
    """Return reference value for mock Seplos BMS."""
    return {
        "voltage": 52.8,
        "current": -0.1,
        "battery_level": 33.0,
        "cycle_charge": 99.0,
        "temperature": 13.0,
        "cycle_capacity": 5227.2,
        "power": -5.28,
        "battery_charging": False,
        "cell#0": 3.296,
        "cell#1": 3.296,
        "cell#2": 3.297,
        "cell#3": 3.297,
        "cell#4": 3.297,
        "cell#5": 3.297,
        "cell#6": 3.297,
        "cell#7": 3.297,
        "cell#8": 3.297,
        "cell#9": 3.297,
        "cell#10": 3.296,
        "cell#11": 3.297,
        "cell#12": 3.297,
        "cell#13": 3.297,
        "cell#14": 3.297,
        "cell#15": 3.297,
        "temp#0": 13.0,
        "temp#1": 13.0,
        "temp#2": 13.0,
        "temp#3": 13.0,
        "delta_voltage": 0.001,
        "runtime": 3564000,
    }


class MockFelicityBleakClient(MockBleakClient):
    """Emulate a Felicity BMS BleakClient."""

    HEAD_CMD: Final[int] = 0x7B
    TAIL_CMD: Final[int] = 0x7D
    CMDS: Final[dict[str, bytearray]] = {
        "dat": bytearray(b"wifilocalMonitor:get Date"),
        "bas": bytearray(b"wifilocalMonitor:get dev basice infor"),
        "rt": bytearray(b"wifilocalMonitor:get dev real infor"),
    }
    RESP: Final[dict[str, bytearray]] = {
        "dat": bytearray(
            b'{"CommVer":1,"wifiSN":"F100011002424470238","iotType":3,"dateTime":"20210101010459",'
            b'"timeZMin":480}'
        ),
        "rt": bytearray(
            b'{"CommVer":1,"wifiSN":"F100011002424470238","modID":1,"date":"20210101010501",'
            b'"DevSN":"100011002424470238","Type":112,"SubType":7300,"Estate":960,"Bfault":0,'
            b'"Bwarn":0,"Bstate":960,"BBfault":0,"BBwarn":0,"BTemp":[[130,130],[256,256]],"Batt":'
            b'[[52800],[-1],[null]],"Batsoc":[[3300,1000,300000]],"Templist":[[130,130],[0,0],'
            b'[65535,65535],[65535,65535]],"BattList":[[52750,65535],[-1,-1]],"BatsocList":'
            b'[[3300,1000,300000]],"BatcelList":[[3296,3296,3297,3297,3297,3297,3297,3297,3297,'
            b"3297,3296,3297,3297,3297,3297,3297],[65535,65535,65535,65535,65535,65535,65535,"
            b'65535,65535,65535,65535,65535,65535,65535,65535,65535]],"EMSpara":[[1,2]],"BMaxMin":'
            b'[[3297,3296],[2,0]],"LVolCur":[[576,480],[1500,1500]],"BMSpara":[[1,2]],"BLVolCu":'
            b'[[576,480],[1500,1500]],"BtemList":[[130,130,130,130,32767,32767,32767,32767]]}'
        ),
        "bas": bytearray(
            b'{"CommVer":1,"version":"2.06","wifiSN":"F100011002424470238","COM":3,"iotType":3,'
            b'"modID":1,"DevSN":"100011002424470238","Type":112,"SubType":7300,"DSwVer":65535,'
            b'"M1SwVer":519,"M2SwVer":16,"DHwVer":0,"CtHwVer":0,"PwHwVer":65535}'
        ),
    }

    def _response(
        self, char_specifier: BleakGATTCharacteristic | int | str | UUID, data: Buffer
    ) -> bytearray:

        if isinstance(char_specifier, str) and normalize_uuid_str(
            char_specifier
        ) == normalize_uuid_str("49535258-184d-4bd9-bc61-20c647249616"):
            for k, v in self.CMDS.items():
                if bytearray(data).startswith(v):
                    return self.RESP[k]

        return bytearray()

    async def write_gatt_char(
        self,
        char_specifier: BleakGATTCharacteristic | int | str | UUID,
        data: Buffer,
        response: bool | None = None,
    ) -> None:
        """Issue write command to GATT."""
        await super().write_gatt_char(char_specifier, data)

        assert (
            self._notify_callback
        ), "write to characteristics but notification not enabled"

        resp: bytearray = self._response(char_specifier, data)
        for notify_data in [
            resp[i : i + BT_FRAME_SIZE] for i in range(0, len(resp), BT_FRAME_SIZE)
        ]:
            self._notify_callback("MockFelicityBleakClient", notify_data)


async def test_update(monkeypatch, reconnect_fixture) -> None:
    """Test Felicity BMS data update."""

    monkeypatch.setattr(
        "custom_components.bms_ble.plugins.basebms.BleakClient",
        MockFelicityBleakClient,
    )

    bms = BMS(
        generate_ble_device("cc:cc:cc:cc:cc:cc", "MockBLEdevice", None, -73),
        reconnect_fixture,
    )

    result = await bms.async_update()

    assert result == ref_value()

    # query again to check already connected state
    result = await bms.async_update()
    assert bms._client and bms._client.is_connected is not reconnect_fixture

    await bms.disconnect()


@pytest.fixture(
    name="wrong_response",
    params=[
        (b'"CommVer":1,"wifiSN":"F100011002424470238"}', "invalid frame start"),
        (b'{"CommVer":1,"wifiSN":"F100011002424470238"', "invalid frame end"),
        (b'{"CommVer":2,"wifiSN":"F100011002424470238"}', "invalid protocol"),
    ],
    ids=lambda param: param[1],
)
def response(request):
    """Return faulty response frame."""
    return request.param[0]


async def test_invalid_response(monkeypatch, wrong_response) -> None:
    """Test data up date with BMS returning invalid data."""

    monkeypatch.setattr(
        "custom_components.bms_ble.plugins.felicity_bms.BMS.BAT_TIMEOUT",
        0.1,
    )

    monkeypatch.setattr(
        "tests.test_felicity_bms.MockFelicityBleakClient._response",
        lambda _s, _c_, d: wrong_response,
    )

    monkeypatch.setattr(
        "custom_components.bms_ble.plugins.basebms.BleakClient",
        MockFelicityBleakClient,
    )

    bms = BMS(generate_ble_device("cc:cc:cc:cc:cc:cc", "MockBLEDevice", None, -73))

    result = {}
    with pytest.raises(TimeoutError):
        result = await bms.async_update()

    assert not result
    await bms.disconnect()
