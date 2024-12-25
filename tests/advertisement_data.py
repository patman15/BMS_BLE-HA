"""Test data for BLE Battery Management System integration config flow."""

from typing import Final

from .bluetooth import generate_advertisement_data

ADVERTISEMENTS: Final[list] = [
    ( # conflicting integrated component: https://github.com/patman15/BMS_BLE-HA/issues/123
        generate_advertisement_data(
            local_name="NWJ20221223010330",#\x11",
            manufacturer_data={65535: b"0UD7\xa2\xd2"},
            service_uuids=["0000ffe0-0000-1000-8000-00805f9b34fb"],
            rssi=-56,
        ),
        "ective_bms",
    ),
    # (
    #     generate_advertisement_data(
    #         local_name="NWJ20221223010388",#\x11",
    #         manufacturer_data={65535: b"0UD7b\xec"},
    #         service_uuids=["0000ffe0-0000-1000-8000-00805f9b34fb"],
    #         rssi=-47,
    #     ),
    #     "ective_bms",
    # ),
    (
        generate_advertisement_data(
            local_name="BatteryOben-00",
            manufacturer_data={2917: b"\x88\xa0\xc8G\x80\x0f\xd5\xc5"},
            service_uuids=["0000ffe0-0000-1000-8000-00805f9b34fb"],
            tx_power=-127,
            rssi=-83,
        ),
        "jikong_bms",
    ),
    (
        generate_advertisement_data(
            local_name="BatterieUnten-01",
            manufacturer_data={2917: b"\x88\xa0\xc8G\x80\r\x08k"},
            service_uuids=["0000ffe0-0000-1000-8000-00805f9b34fb"],
            tx_power=-127,
            rssi=-68,
        ),
        "jikong_bms",
    ),
    (
        generate_advertisement_data(
            local_name="JK_B2A8S20P",
            manufacturer_data={2917: b"\x88\xa0\xc8G\x80\x14\x88\xb7"},
            service_uuids=[
                "00001800-0000-1000-8000-00805f9b34fb",
                "00001801-0000-1000-8000-00805f9b34fb",
                "0000180a-0000-1000-8000-00805f9b34fb",
                "0000180f-0000-1000-8000-00805f9b34fb",
                "0000fee7-0000-1000-8000-00805f9b34fb",
                "0000ffe0-0000-1000-8000-00805f9b34fb",
                "f000ffc0-0451-4000-b000-000000000000",
            ],
            rssi=-67,
        ),
        "jikong_bms",
    ),
    (
        generate_advertisement_data(
            local_name="SP05B2312190075       ",
            service_uuids=["0000fff0-0000-1000-8000-00805f9b34fb"],
            tx_power=-127,
            rssi=-76,
        ),
        "seplos_bms",
    ),
    (
        generate_advertisement_data(
            local_name="BP02",
            service_uuids=["0000ff00-0000-1000-8000-00805f9b34fb"],
            rssi=-81,
        ),
        "seplos_v2_bms",
    ),
    (
        generate_advertisement_data(
            local_name="BP02",
            service_uuids=[
                "00001800-0000-1000-8000-00805f9b34fb",
                "00001801-0000-1000-8000-00805f9b34fb",
                "0000ff00-0000-1000-8000-00805f9b34fb",
            ],
            rssi=-90,
        ),
        "seplos_v2_bms",
    ),
    (
        generate_advertisement_data(
            local_name="LT-12V-1544",
            manufacturer_data={33384: b"\x01\x02\x00\x07\x81\xb5N"},
            tx_power=-127,
            rssi=-71,
        ),
        "ej_bms",
    ),
]
