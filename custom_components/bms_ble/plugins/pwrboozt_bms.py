"""Module to support E&J Technology BMS."""

from enum import IntEnum

from bleak.uuids import normalize_uuid_str

from .basebms import AdvertisementPattern, BMSsample
from .ej_bms import BMS as EJBMS


class Cmd(IntEnum):
    """BMS operation codes."""

    RT = 0x2
    CAP = 0x10


class BMS(EJBMS):
    """E&J Technology BMS implementation."""

    @staticmethod
    def matcher_dict_list() -> list[AdvertisementPattern]:
        """Provide BluetoothMatcher definition."""
        return [
            {
                "local_name": "BT-Battery*",
                "manufacturer_id": 32516,
                "service_uuid": BMS.uuid_services()[0],
                "connectable": True,
            },
        ]

    @staticmethod
    def device_info() -> dict[str, str]:
        """Return device information for the battery management system."""
        return {"manufacturer": "Powerboozt", "model": "Battery"}

    @staticmethod
    def uuid_services() -> list[str]:
        """Return list of 128-bit UUIDs of services required by BMS."""
        return [normalize_uuid_str("fff0")]

    @staticmethod
    def uuid_rx() -> str:
        """Return 128-bit UUID of characteristic that provides notification/read property."""
        return "fff6"

    @staticmethod
    def uuid_tx() -> str:
        """Return 128-bit UUID of characteristic that provides write property."""
        return "fff6"

    async def _async_update(self) -> BMSsample:
        """Update battery status information."""
        raw_data: dict[int, bytearray] = {}

        # query real-time information and capacity
        for cmd in (b":015150000EFE~",):
            await self._await_reply(cmd)
            rsp: int = int(self._data_final[3:5], 16) & 0x7F
            raw_data[rsp] = self._data_final

        if len(raw_data) != len(list(Cmd)) or not all(
            len(value) > 0 for value in raw_data.values()
        ):
            return {}

        return self._conv_data(raw_data) | {
            "cell_voltages": BMS._cell_voltages(
                raw_data[Cmd.RT], cells=BMS._MAX_CELLS, start=25, size=4
            )
        }
