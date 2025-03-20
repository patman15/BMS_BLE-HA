"""Test data for BLE Battery Management System integration config flow."""

from typing import Final

from .bluetooth import AdvertisementData, generate_advertisement_data

ADVERTISEMENTS: Final[list[tuple[AdvertisementData, str]]] = [
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
    (  # nRF Connect (https://github.com/patman15/BMS_BLE-HA/issues/82#issuecomment-2498299433)
        generate_advertisement_data(
            local_name="$PFLAC,R,RADIOID\x0d\x0a",
            manufacturer_data={65535: b"\x10\x55\x44\x33\xe8\xb4"},
            service_uuids=["0000ffe0-0000-1000-8000-00805f9b34fb"],
            rssi=-47,
        ),
        "ective_bms",
    ),
    (  # BTctl (https://github.com/patman15/BMS_BLE-HA/issues/137)
        generate_advertisement_data(
            local_name="NWJ20200720020539",
            manufacturer_data={0: b"\x34\x14\xb5\x9d\x78\xe7\x4c"},
            service_uuids=["0000ffe0-0000-1000-8000-00805f9b34fb"],
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
    (  # source BTctl (https://github.com/patman15/BMS_BLE-HA/issues/142)
        generate_advertisement_data(
            local_name="SP51B2407270006       ",
            service_uuids=[
                "00001800-0000-1000-8000-00805f9b34fb",
                "00001801-0000-1000-8000-00805f9b34fb",
                "0000fff0-0000-1000-8000-00805f9b34fb",
                "02f00000-0000-0000-8000-00000000fe00",
            ],
            rssi=-46,
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
    (  # advmon (https://github.com/patman15/BMS_BLE-HA/issues/214)
        generate_advertisement_data(
            local_name="SP47B-A2410230006",
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
    (  # proxy LOG (https://github.com/patman15/BMS_BLE-HA/issues/187)
        generate_advertisement_data(
            local_name="L-12V100AH-0902",
            tx_power=5,
            rssi=-87,
        ),
        "ej_bms",
    ),
    (  # proxy LOG (https://github.com/patman15/BMS_BLE-HA/issues/187)
        generate_advertisement_data(
            local_name="LT-12V-0002\r\n",
            tx_power=5,
            rssi=-94,
        ),
        "ej_bms",
    ),
    (  # source LOG, https://github.com/patman15/BMS_BLE-HA/issues/59
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
    (  # source LOG
        generate_advertisement_data(
            local_name="170R000086",
            manufacturer_data={
                21330: b"!4\xba\x03\xec\x11\x0c\xf8\x01\x05\x00\x01\x00\x00"
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
            rssi=-73,
        ),
        "cbtpwr_bms",
    ),
    (  # source BT monitor (https://github.com/patman15/BMS_BLE-HA/issues/176)
        generate_advertisement_data(
            local_name="140R000288",
            manufacturer_data={0: b"ffffffff6400ff000000000000000000"},
            service_uuids=["0000fff0-0000-1000-8000-00805f9b34fb"],
            rssi=-82,
        ),
        "cbtpwr_bms",
    ),
    (  # source PCAP
        generate_advertisement_data(
            manufacturer_data={54976: b"\x3c\x4f\xac\x50\xff"},
        ),
        "tdt_bms",
    ),
    (  # source BTctl (https://github.com/patman15/BMS_BLE-HA/issues/52#issuecomment-2390048120)
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
    (  # source LOG, proxy (https://github.com/patman15/BMS_BLE-HA/issues/160)
        generate_advertisement_data(
            local_name="DL-401710015C9B",
            manufacturer_data={770: b"\x16\x40\x17\x10\x01\x5c\x9b\x44\x4c"},
            rssi=-36,
        ),
        "daly_bms",
    ),
    (  # source BTctl (https://github.com/patman15/BMS_BLE-HA/issues/145)
        generate_advertisement_data(
            local_name="JHB-501812XXXXXX",
            manufacturer_data={260: b"\x01\x50\x18\x12\x01\xa3\xb3\x4a\x48\x42"},
            rssi=-46,
        ),
        "daly_bms",
    ),
    (  # source LOG (https://github.com/patman15/BMS_BLE-HA/issues/160#issuecomment-2629318416)
        generate_advertisement_data(
            local_name="Randomname",  # JHB-50181201A494
            manufacturer_data={260: b"\x01\x50\x18\x12\x01\xa4\x94JHB"},
            tx_power=-127,
            rssi=-36,
        ),
        "daly_bms",
    ),
    (  # source BTctl (https://github.com/patman15/BMS_BLE-HA/issues/174#issuecomment-2637936795)
        generate_advertisement_data(
            local_name="BT270-2",
            manufacturer_data={770: b"\x16\x40\x17\x12\x01\x11\x97\x44\x4c"},
            rssi=-60,
        ),
        "daly_bms",
    ),
    (  # source nRF (https://github.com/patman15/BMS_BLE-HA/issues/22#issuecomment-2198586195)
        generate_advertisement_data(  # Supervolt battery
            local_name="SX100P-B230201",
            service_uuids=["0000ff00-0000-1000-8000-00805f9b34fb"],
            manufacturer_data={31488: "\x02\xff\xff\x7d"},
        ),
        "jbd_bms",
    ),
    (  # source LOG (https://github.com/patman15/BMS_BLE-HA/issues/144)
        generate_advertisement_data(  # ECO-WORTHY LiFePO4 12V 100Ah
            local_name="DP04S007L4S100A",
            manufacturer_data={6226: b"\x28\x37\xc2\xa5"},  # MAC address, wrong
            service_uuids=["0000ff00-0000-1000-8000-00805f9b34fb"],
            rssi=-57,
        ),
        "jbd_bms",
    ),
    (  # source PCAP, BTctl (https://github.com/patman15/BMS_BLE-HA/issues/134)
        generate_advertisement_data(  # ECO-WORTHY LiFePO4 12V 100Ah
            local_name="DP04S007L4S100A",
            service_uuids=["0000ff00-0000-1000-8000-00805f9b34fb"],
            manufacturer_data={8856: "\x28\x37\xc2\xa5"},  # MAC address, wrong
            rssi=-53,
        ),
        "jbd_bms",
    ),
    (  # source LOG (https://github.com/patman15/BMS_BLE-HA/issues/134)
        # (https://github.com/patman15/BMS_BLE-HA/issues/157)
        generate_advertisement_data(  # ECO-WORTHY LiFePO4 12V 150Ah, DCHOUSE FW v6.6
            local_name="DP04S007L4S120A",
            manufacturer_data={42435: b"\x27\x37\xc2\xa5"},  # MAC address, wrong
            service_uuids=["0000ff00-0000-1000-8000-00805f9b34fb"],
            tx_power=-127,
            rssi=-49,
        ),
        "jbd_bms",
    ),
    (  # source LOG (https://github.com/patman15/BMS_BLE-HA/issues/160#issuecomment-2629318416)
        generate_advertisement_data(
            local_name="SP17S005P17S120A",
            manufacturer_data={34114: b"\34\37\xc2\xa5"},
            service_uuids=["0000ff00-0000-1000-8000-00805f9b34fb"],
            tx_power=-127,
            rssi=-31,
        ),
        "jbd_bms",
    ),
    (  # source LOG (https://github.com/patman15/BMS_BLE-HA/issues/173)
        generate_advertisement_data(  # Eleksol 12V300AH
            local_name="12300DE00013",
            manufacturer_data={44580: b"\x27\x37\xc2\xa5"},  # MAC address, wrong
            service_uuids=[
                "0000ff00-0000-1000-8000-00805f9b34fb",
            ],
            rssi=-60,
        ),
        "jbd_bms",
    ),
    (  # source BTctl (https://github.com/patman15/BMS_BLE-HA/issues/161)
        generate_advertisement_data(  # Felicity Solar LUX-Y-48300LG01
            local_name="F100011002424470238",
            rssi=-56,
        ),
        "felicity_bms",
    ),
    (  # source LOG, proxy (https://github.com/patman15/BMS_BLE-HA/issues/164#issue-2825586172)
        generate_advertisement_data(
            local_name="ECO-WORTHY 02_B8EF",
            manufacturer_data={49844: b"\xe0\xfa\xb8\xf0"},  # MAC address, correct
            service_uuids=[
                "00001800-0000-1000-8000-00805f9b34fb",
                "00001801-0000-1000-8000-00805f9b34fb",
                "0000fff0-0000-1000-8000-00805f9b34fb",
            ],
            rssi=-50,
        ),
        "ecoworthy_bms",
    ),
    (  # source BTctl (https://github.com/patman15/BMS_BLE-HA/issues/194)
        generate_advertisement_data(  # Topband
            local_name="ZM20210512010036�",
            manufacturer_data={0: "\xfc\x45\xc3\xbc\xd6\xa8"},
            service_uuids=["0000ffe0-0000-1000-8000-00805f9b34fb"],
            rssi=-48,
        ),
        "ective_bms",
    ),
    (  # source advmon (https://github.com/patman15/BMS_BLE-HA/issues/197)
        generate_advertisement_data(  # Creabest
            local_name="100R0002E3",
            manufacturer_data={21330: "2134ba03ec110909010500010000"},
            service_uuids=["000003c1-0000-1000-8000-00805f9b34fb"],
            rssi=-76,
            tx_power=0,
        ),
        "cbtpwr_bms",
    ),
    (  # source pcap (https://github.com/patman15/BMS_BLE-HA/issues/168)
        generate_advertisement_data(
            local_name="SOK-24V1127",
            service_uuids=["0000fff0-0000-1000-8000-00805f9b34fb"],
            rssi=-94,
        ),
        "abc_bms",
    ),
    (  # source advmon (https://github.com/patman15/BMS_BLE-HA/issues/204)
        generate_advertisement_data(  # 16S LiFePo 250A BMS
            local_name="DL-40160901534C",
            manufacturer_data={258: "04"},
            rssi=-87,
        ),
        "daly_bms",
    ),
    (  # source pcap (https://github.com/patman15/BMS_BLE-HA/issues/186)
        generate_advertisement_data(  # Epoch, BMS: RoyPow SPB22-TI04
            local_name=" B12100A 220600016 ",
            service_uuids=[
                "0000ffe0-0000-1000-8000-00805f9b34fb",
                "0000ffe7-0000-1000-8000-00805f9b34fb",
            ],
            manufacturer_data={424: "\x88\xa0\x12\x6c\x14\x39\x22\xb8"},
            rssi=-87,
        ),
        "roypow_bms",
    ),
    (  # source advmon (https://github.com/patman15/BMS_BLE-HA/issues/186)
        generate_advertisement_data(
            local_name="12-6C-14-39-28-1F",
            rssi=-50,
            manufacturer_data={2865: "88a0126c1439281f"},
            service_uuids=[
                "0000ffe0-0000-1000-8000-00805f9b34fb",
                "0000fee7-0000-1000-8000-00805f9b34fb",
            ],
        ),
        "roypow_bms",
    ),
    (  # source advmon (https://github.com/patman15/BMS_BLE-HA/issues/186)
        generate_advertisement_data(
            local_name="C6-6C-15-08-A7-E9",
            rssi=-66,
            manufacturer_data={35579: "88a0c66c1508a7e9"},
            service_uuids=[
                "0000ffe0-0000-1000-8000-00805f9b34fb",
                "0000fee7-0000-1000-8000-00805f9b34fb",
            ],
        ),
        "roypow_bms",
    ),
    (  # source advmon (https://github.com/patman15/BMS_BLE-HA/issues/226)
        generate_advertisement_data(  # A4:C1:37:42:3E:D9
            local_name="AP21S002-l21s",  # not 100% sure
            rssi=-84,
            manufacturer_data={16089: "4237c1a4"},  # MAC address, wrong
            service_uuids=[
                "0000ff00-0000-1000-8000-00805f9b34fb",
            ],
        ),
        "jbd_bms",
    ),
]
