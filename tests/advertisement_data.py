"""Test data for BLE Battery Management System integration config flow."""

from typing import Final

from .bluetooth import generate_advertisement_data

ADVERTISEMENTS: Final[list] = [
    (  # source LOG
        generate_advertisement_data(
            local_name="NWJ20221223010330\x11",
            manufacturer_data={65535: b"0UD7\xa2\xd2"},
            service_uuids=["0000ffe0-0000-1000-8000-00805f9b34fb"],
            rssi=-56,
        ),
        "ective_bms",
    ),
    (  # source LOG
        generate_advertisement_data(
            local_name="NWJ20221223010388\x11",
            manufacturer_data={65535: b"0UD7b\xec"},
            service_uuids=["0000ffe0-0000-1000-8000-00805f9b34fb"],
            rssi=-47,
        ),
        "ective_bms",
    ),
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
    (  # source LOG
        generate_advertisement_data(
            local_name="BatterieUnten-01",
            manufacturer_data={2917: b"\x88\xa0\xc8G\x80\r\x08k"},
            service_uuids=["0000ffe0-0000-1000-8000-00805f9b34fb"],
            tx_power=-127,
            rssi=-68,
        ),
        "jikong_bms",
    ),
    (  # source LOG
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
    (  # source LOG
        generate_advertisement_data(
            local_name="SP05B2312190075       ",
            service_uuids=["0000fff0-0000-1000-8000-00805f9b34fb"],
            tx_power=-127,
            rssi=-76,
        ),
        "seplos_bms",
    ),
    (  # source LOG
        generate_advertisement_data(
            local_name="SP66B2404270002       ",
            service_uuids=["0000fff0-0000-1000-8000-00805f9b34fb"],
            rssi=-81,
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
    (  # source LOG
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
    (  # source LOG
        generate_advertisement_data(
            local_name="LT-12V-1544",
            manufacturer_data={33384: b"\x01\x02\x00\x07\x81\xb5N"},
            tx_power=-127,
            rssi=-71,
        ),
        "ej_bms",
    ),
    (  # source LOG
        generate_advertisement_data(
            local_name="170R000121",
            manufacturer_data={
                21330: b"!4\xba\x03\xec\x11\x0c\xb4\x01\x05\x00\x01\x00\x00"
            },
            service_uuids=[
                "00001800-0000-1000-8000-00805f9b34fb",
                "00001801-0000-1000-8000-00805f9b34fb",
                "0000180a-0000-1000-8000-00805f9b34fb",
                "0000fd00-0000-1000-8000-00805f9b34fb",
                "0000ff90-0000-1000-8000-00805f9b34fb",
                "0000ffb0-0000-1000-8000-00805f9b34fb",
                "0000ffc0-0000-1000-8000-00805f9b34fb",
                "0000ffd0-0000-1000-8000-00805f9b34fb",
                "0000ffe0-0000-1000-8000-00805f9b34fb",
                "0000ffe5-0000-1000-8000-00805f9b34fb",
                "0000fff0-0000-1000-8000-00805f9b34fb",
            ],
            tx_power=0,
            rssi=-75,
        ),
        "cbtpwr_bms",
    ),
    (  # source PCAP
        generate_advertisement_data(
            manufacturer_data={54976: b"\x3c\x4f\xac\x50\xff"},
        ),
        "tdt_bms",
    ),
    (  # source bluetoothctl (https://github.com/patman15/BMS_BLE-HA/issues/52#issuecomment-2390048120)
        generate_advertisement_data(
            local_name="TBA-13500277",
            service_uuids=[
                "00001800-0000-1000-8000-00805f9b34fb",
                "00001801-0000-1000-8000-00805f9b34fb",
                "0000180a-0000-1000-8000-00805f9b34fb",
                "0000fff0-0000-1000-8000-00805f9b34fb",
            ],
            rssi=-72,
        ),
        "dpwrcore_bms",
    ),
    (  # source LOG
        generate_advertisement_data(
            local_name="SmartBat-B15051",
            service_uuids=["0000fff0-0000-1000-8000-00805f9b34fb"],
            tx_power=3,
            rssi=-66,
        ),
        "ogt_bms",
    ),
    (  # source PCAP
        generate_advertisement_data(
            local_name="R-24100BNN160-A00643",
            service_uuids=["0000ffe0-0000-1000-8000-00805f9b34fb"],
            manufacturer_data={22618: b"\xc8\x47\x80\x15\xd8\x34"},
        ),
        "redodo_bms",
    ),
    (  # source LOG (https://github.com/patman15/BMS_BLE-HA/issues/89)
        generate_advertisement_data(
            local_name="DL-46640102XXXX",
            manufacturer_data={25670: b"\x01\x02\t\xac"},
            service_uuids=["0000fff0-0000-1000-8000-00805f9b34fb"],
            tx_power=-127,
            rssi=-58,
        ),
        "daly_bms",
    ),
    (  # source nRF (https://github.com/patman15/BMS_BLE-HA/issues/22#issuecomment-2198586195)
        generate_advertisement_data(  # Supervolt battery
            local_name="SX100P-B230201",
            service_uuids=["0000ff00-0000-1000-8000-00805f9b34fb"],
            manufacturer_data={31488: "\x02\xFF\xFF\x7D"},
        ),
        "jbd_bms",
    ),
    (  # source bluetoothctl (https://github.com/patman15/BMS_BLE-HA/issues/134)
        generate_advertisement_data(  # ECO-WORTHY LiFePO4 12V 100Ah
            service_uuids=["0000ff00-0000-1000-8000-00805f9b34fb"],
            manufacturer_data={8856: "\x28\x37\xc2\xa5"},
            rssi=-53,
        ),
        "jbd_bms",
    ),
]
