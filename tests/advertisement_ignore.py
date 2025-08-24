"""Test data for BLE Battery Management System integration config flow."""

from typing import Final

from .bluetooth import AdvertisementData, generate_advertisement_data

ADVERTISEMENTS_IGNORE: Final[list[tuple[AdvertisementData, str]]] = [
    (  # source advmon (https://github.com/patman15/BMS_BLE-HA/issues/282)
        generate_advertisement_data(
            local_name="ECO0AA8",
            manufacturer_data={64590: "fad60aa8"},  # MAC address, no OUI, correct
            service_uuids=[
                "0000ff00-0000-1000-8000-00805f9b34fb",
                "00000001-0000-1000-8000-00805f9b34fb",
            ],
            rssi=-80,
        ),
        "classic BT device",
    ),
    (  # source advmon (https://github.com/patman15/BMS_BLE-HA/issues/317)
        generate_advertisement_data(
            local_name="ECOBF9F",
            manufacturer_data={3053: "ce2ebf9f"},  # MAC address, no OUI, correct
            service_uuids=[
                "0000ff00-0000-1000-8000-00805f9b34fb",
                "00000001-0000-1000-8000-00805f9b34fb",
            ],
            rssi=-50,
        ),
        "classic BT device",
    ),
    (  # source advmon (https://github.com/patman15/BMS_BLE-HA/issues/408)
        generate_advertisement_data(
            local_name="BMS-SMART_708BFC",
            rssi=-78,
        ),
        "classic BT device",
    ),
]
