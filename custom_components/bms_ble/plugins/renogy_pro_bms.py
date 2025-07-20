"""Module to support Renogy Pro BMS."""

from bleak.backends.characteristic import BleakGATTCharacteristic
from bleak.uuids import normalize_uuid_str

from .basebms import AdvertisementPattern
from .renogy_bms import BMS as RenogyBMS


class BMS(RenogyBMS):
    """Renogy Pro battery class implementation."""

    HEAD: bytes = b"\xff\x03"  # SOP, read fct (x03)

    @staticmethod
    def matcher_dict_list() -> list[AdvertisementPattern]:
        """Provide BluetoothMatcher definition."""
        return [
            {
                "local_name": "RNGRBP*",
                "manufacturer_id": 0xE14C,
                "connectable": True,
            },
        ]

    @staticmethod
    def device_info() -> dict[str, str]:
        """Return device information for the battery management system."""
        return {"manufacturer": "Renogy", "model": "Bluetooth battery pro"}

    async def _init_connection(
        self, char_notify: BleakGATTCharacteristic | int | str | None = None
    ) -> None:
        """Initialize RX/TX characteristics and protocol state."""
        char_notify_handle: int = -1
        assert char_notify is None, "char_notify not used for Renogy Pro BMS"

        for service in self._client.services:
            for char in service.characteristics:
                self._log.debug(
                    "discovered %s (#%i): %s", char.uuid, char.handle, char.properties
                )
                if (
                    service.uuid == BMS.uuid_services()[1]
                    and char.uuid == normalize_uuid_str(BMS.uuid_rx())
                    and "notify" in char.properties
                ):
                    char_notify_handle = char.handle

        if char_notify_handle == -1:
            self._log.debug("failed to detect characteristics.")
            await self._client.disconnect()
            raise ConnectionError(f"Failed to detect characteristics from {self.name}.")
        self._log.debug(
            "using characteristics handle #%i (notify).",
            char_notify_handle,
        )

        await super()._init_connection(char_notify_handle)
