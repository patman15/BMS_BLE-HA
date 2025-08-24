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
    (  # source advmon (https://github.com/patman15/BMS_BLE-HA/issues/418)
        generate_advertisement_data(
            local_name="BP21",
            service_uuids=["0000ff00-0000-1000-8000-00805f9b34fb"],
            rssi=-62,
        ),
        "seplos_v2_bms",
    ),
    (  # source advmon (https://github.com/patman15/BMS_BLE-HA/issues/418)
        generate_advertisement_data(
            local_name="BP00",
            service_uuids=[
                "00001800-0000-1000-8000-00805f9b34fb",
                "00001801-0000-1000-8000-00805f9b34fb",
                "0000ff00-0000-1000-8000-00805f9b34fb",
            ],
            rssi=-62,
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
    (  # source advmon (https://github.com/patman15/BMS_BLE-HA/issues/350)
        generate_advertisement_data(
            local_name="LT-24100B-A00249",
            manufacturer_data={22618: "\xc8\x47\x80\x0b\xb6\x54"},
            rssi=-55,
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
            manufacturer_data={
                0: b"\xff\xff\xff\xff\x64\x00\xff\x00\x00\x00\x00\x00\x00\x00\x00\x00"
            },
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
    (  # Pro BMS test: name and service UUID matching
        generate_advertisement_data(
            local_name="Pro BMS",
            service_uuids=["0000fff0-0000-1000-8000-00805f9b34fb"],
            rssi=-60,
        ),
        "pro_bms",
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
            manufacturer_data={31488: b"\x02\xff\xff\x7d"},
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
            manufacturer_data={8856: b"\x28\x37\xc2\xa5"},  # MAC address, wrong
            rssi=-53,
        ),
        "jbd_bms",
    ),
    (  # source bluetoothctl (https://github.com/patman15/BMS_BLE-HA/issues/141)
        generate_advertisement_data(  # https://liontron.com/download/german/LISMART1240LX.pdf
            service_uuids=["0000ff00-0000-1000-8000-00805f9b34fb"],
            manufacturer_data={15984: b"\x97\xd1\xc1\x8c"},  # MAC address, correct
            rssi=-53,
        ),
        "jbd_bms",
    ),
    (  # source bluetoothctl (https://github.com/patman15/BMS_BLE-HA/issues/174)
        generate_advertisement_data(  # LionTron XL19110253
            service_uuids=["0000ff00-0000-1000-8000-00805f9b34fb"],
            manufacturer_data={49572: b"\x38\x99\x15\x54"},  # MAC address, correct
            rssi=-53,
        ),
        "jbd_bms",
    ),
    (  # source bluetoothctl (https://github.com/patman15/BMS_BLE-HA/issues/174)
        generate_advertisement_data(  # LionTron LT40AH
            local_name="LT40AH",
            service_uuids=["0000ff00-0000-1000-8000-00805f9b34fb"],
            manufacturer_data={19011: b"\x1b\x38\xc1\xa4"},  # MAC address, wrong
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
            manufacturer_data={
                49844: b"\xe0\xfa\xb8\xf0"
            },  # MAC address, correct, public
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
            manufacturer_data={0: b"\xfc\x45\xc3\xbc\xd6\xa8"},
            service_uuids=["0000ffe0-0000-1000-8000-00805f9b34fb"],
            rssi=-48,
        ),
        "ective_bms",
    ),
    (  # source advmon (https://github.com/patman15/BMS_BLE-HA/issues/197)
        generate_advertisement_data(  # Creabest
            local_name="100R0002E3",
            manufacturer_data={
                21330: b"\x21\x34\xba\x03\xec\x11\x09\x09\x01\x05\x00\x01\x00\x00"
            },
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
    (  # source log (https://github.com/patman15/BMS_BLE-HA/issues/394)
        generate_advertisement_data(
            local_name="SOK-AA02120",
            service_uuids=[
                "00001800-0000-1000-8000-00805f9b34fb",
                "00001801-0000-1000-8000-00805f9b34fb",
                "0000180a-0000-1000-8000-00805f9b34fb",
                "0000180f-0000-1000-8000-00805f9b34fb",
                "0000ffe0-0000-1000-8000-00805f9b34fb",
                "0000fff0-0000-1000-8000-00805f9b34fb",
                "f000ffc0-0451-4000-b000-000000000000",
            ],
            rssi=-62,
        ),
        "abc_bms",
    ),
    (  # source advmon (https://github.com/patman15/BMS_BLE-HA/issues/204)
        generate_advertisement_data(  # 16S LiFePo 250A BMS
            local_name="DL-40160901534C",
            manufacturer_data={258: b"\x04"},
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
            manufacturer_data={424: b"\x88\xa0\x12\x6c\x14\x39\x22\xb8"},
            rssi=-87,
        ),
        "roypow_bms",
    ),
    (  # source advmon (https://github.com/patman15/BMS_BLE-HA/issues/186)
        generate_advertisement_data(  # no name advertised
            rssi=-50,
            manufacturer_data={2865: b"\x88\xa0\x12\x6c\x14\x39\x28\x1f"},
            service_uuids=[
                "0000ffe0-0000-1000-8000-00805f9b34fb",
                "0000fee7-0000-1000-8000-00805f9b34fb",
            ],
        ),
        "roypow_bms",
    ),
    (  # source advmon (https://github.com/patman15/BMS_BLE-HA/issues/186)
        generate_advertisement_data(  # no name advertised
            rssi=-66,
            manufacturer_data={35579: b"\x88\xa0\xc6\x6c\x15\x08\xa7\xe9"},
            service_uuids=[
                "0000ffe0-0000-1000-8000-00805f9b34fb",
                "0000fee7-0000-1000-8000-00805f9b34fb",
            ],
        ),
        "roypow_bms",
    ),
    (  # source advmon (https://github.com/patman15/BMS_BLE-HA/issues/226)
        generate_advertisement_data(  # A4:C1:37:42:3E:D9
            local_name="AP21S002-L21S",
            rssi=-84,
            manufacturer_data={16089: b"\x42\x37\xc1\xa4"},  # MAC address, wrong
            service_uuids=[
                "0000ff00-0000-1000-8000-00805f9b34fb",
            ],
        ),
        "jbd_bms",
    ),
    (  # source advmon (https://github.com/patman15/BMS_BLE-HA/issues/231)
        generate_advertisement_data(
            local_name="CSY012405290042",
            rssi=-78,
            service_uuids=[
                "0000fff0-0000-1000-8000-00805f9b34fb",
            ],
        ),
        "seplos_bms",
    ),
    (  # source advmon (https://github.com/patman15/BMS_BLE-HA/issues/236)
        generate_advertisement_data(
            local_name="SBL-12330BLH1-242055",
            rssi=-84,
            manufacturer_data={123: b"\x02\xff\xff\x7d"},
            service_uuids=["0000ff00-0000-1000-8000-00805f9b34fb"],
        ),
        "jbd_bms",
    ),
    (  # source advmon (https://github.com/patman15/BMS_BLE-HA/issues/240)
        generate_advertisement_data(  # Creabest
            local_name="VB024000390",
            rssi=-73,
            manufacturer_data={16963: b"\x54\x5e\x02\x11\xf8\x2e\x0c\xa8\x89\x42"},
            service_uuids=[
                "0000fff0-0000-1000-8000-00805f9b34fb",
                "0000ffb0-0000-1000-8000-00805f9b34fb",
            ],
        ),
        "cbtpwr_vb_bms",
    ),
    (  # source advmon (https://github.com/patman15/BMS_BLE-HA/issues/236)
        generate_advertisement_data(
            local_name="162400552210210097",
            rssi=-35,
            manufacturer_data={49572: b"\x37\x55\x32\xf9"},  # MAC address, correct
            service_uuids=["0000ff00-0000-1000-8000-00805f9b34fb"],
        ),
        "jbd_bms",
    ),
    (  # source BTctl (https://github.com/patman15/BMS_BLE-HA/issues/242)
        generate_advertisement_data(
            local_name="PKT2201PB121000084",
            rssi=-46,
            manufacturer_data={30669: b"\xe4\x38\xc1\xa4"},  # MAC address, wrong
            service_uuids=["0000ff00-0000-1000-8000-00805f9b34fb"],
        ),
        "jbd_bms",
    ),
    (  # source advmon (https://github.com/patman15/BMS_BLE-HA/issues/241)
        generate_advertisement_data(
            local_name="V-12V200Ah-0215",
            rssi=-74,
        ),
        "ej_bms",
    ),
    (  # source BTctl (https://github.com/patman15/BMS_BLE-HA/issues/253)
        generate_advertisement_data(
            local_name="ECO-WORTHY 02_50DB",
            manufacturer_data={
                47912: b"\xed\x00\x50\xdc"
            },  # MAC address, correct, public
            rssi=-49,
        ),
        "ecoworthy_bms",
    ),
    (  # source advmon (https://github.com/patman15/BMS_BLE-HA/issues/247)
        generate_advertisement_data(
            local_name="BT-TH-66EDFC11",
            rssi=-65,
            manufacturer_data={39008: b"\x66\xed\xfc\x11"},  # MAC address correct
            service_uuids=["0000ffd0-0000-1000-8000-00805f9b34fb"],
        ),
        "renogy_bms",
    ),
    (  # source BTctl (https://github.com/patman15/BMS_BLE-HA/issues/264)
        generate_advertisement_data(
            local_name="gokwh battery",
            manufacturer_data={16666: b"\x29\x37\xc2\xa5"},  # MAC address, wrong
            service_uuids=["0000ff00-0000-1000-8000-00805f9b34fb"],
            rssi=-72,
        ),
        "jbd_bms",
    ),
    (  # source advmon (https://github.com/patman15/BMS_BLE-HA/issues/276)
        generate_advertisement_data(
            local_name="xxxxxxx20126\f",  # renamed
            manufacturer_data={
                65535: b"\x30\x55\x44\x37\x92\xf2"
            },  # value: MAC address
            service_uuids=[
                "00001800-0000-1000-8000-00805f9b34fb",
                "00001801-0000-1000-8000-00805f9b34fb",
                "0000ffe0-0000-1000-8000-00805f9b34fb",
                "f000ffc0-0451-4000-b000-000000000000",
            ],
            rssi=-127,
        ),
        "ective_bms",
    ),
    (  # source advmon (https://github.com/patman15/BMS_BLE-HA/issues/280)
        generate_advertisement_data(
            local_name="P-24050BNNA70-A01152",
            manufacturer_data={22618: b"\xc8\x47\x80\x18\xbc\x81"},
            service_uuids=["0000ffe0-0000-1000-8000-00805f9b34fb"],
            rssi=-57,
        ),
        "redodo_bms",
    ),
    (  # source advmon (https://github.com/patman15/BMS_BLE-HA/issues/286)
        generate_advertisement_data(
            local_name="ECO-WORTHY 0B_5AD4",
            manufacturer_data={
                57570: b"\x5a\x78\x3c\x31"
            },  # MAC address, correct, private
            service_uuids=["0000fff0-0000-1000-8000-00805f9b34fb"],
            rssi=-86,
        ),
        "ecoworthy_bms",
    ),
    (  # source advmon (https://github.com/patman15/BMS_BLE-HA/issues/284)
        generate_advertisement_data(
            local_name="ECO-LFP48100-3U-8EC7",
            manufacturer_data={
                49834: b"\x37\x01\x8e\xc7\x00\x01\x4c\x03"
            },  # MAC address correct
            service_uuids=["0000ff00-0000-1000-8000-00805f9b34fb"],
            rssi=-70,
        ),
        "jbd_bms",
    ),
    (  # source proxy LOG (https://github.com/patman15/BMS_BLE-HA/issues/295)
        generate_advertisement_data(
            local_name="ECO-WORTHY 02_3DDF",
            manufacturer_data={
                15996: b"\x82\x1c\x3d\xe0"
            },  # MAC address, correct, public
            rssi=-49,
        ),
        "ecoworthy_bms",
    ),
    (  # source advmon (https://github.com/patman15/BMS_BLE-HA/issues/301)
        generate_advertisement_data(  # PowerQueen
            local_name="PQ-24100B-A00292",
            rssi=-65,
            manufacturer_data={22618: b"\xc8\x47\x80\x10\xb7\x9a"},
            service_uuids=["0000ffe0-0000-1000-8000-00805f9b34fb"],
        ),
        "redodo_bms",
    ),
    (  # source advmon (https://github.com/patman15/BMS_BLE-HA/issues/302)
        generate_advertisement_data(
            local_name="OGR-48100-123456789",
            manufacturer_data={13880: b"\x13\x01\x4e\x9a"},
            service_uuids=[
                "0000ff00-0000-1000-8000-00805f9b34fb",
                "00000001-0000-1000-8000-00805f9b34fb",
            ],
            rssi=-47,
        ),
        "jbd_bms",
    ),
    (  # source advmon (https://github.com/patman15/BMS_BLE-HA/issues/314)
        generate_advertisement_data(
            local_name="SV12V150224041",
            manufacturer_data={33384: b"\x01\x02\x00\x07\xa0\x30\xf7"},
            rssi=-39,
        ),
        "ej_bms",
    ),
    (  # source advmon (https://github.com/patman15/BMS_BLE-HA/issues/309)
        generate_advertisement_data(
            local_name="JBD-SP16S020-L8S",
            manufacturer_data={13880: b"\x13\x01\x4e\x9a"},
            service_uuids=[
                "00001800-0000-1000-8000-00805f9b34fb",
                "00001801-0000-1000-8000-00805f9b34fb",
                "0000180a-0000-1000-8000-00805f9b34fb",
                "0000ff00-0000-1000-8000-00805f9b34fb",
                "00010203-0405-0607-0809-0a0b0c0d1912",
            ],
            rssi=-81,
        ),
        "jbd_bms",
    ),
    (  # source advmon (https://github.com/patman15/BMS_BLE-HA/issues/291)
        generate_advertisement_data(
            local_name="GW-24Srenamed1",
            rssi=-88,
            manufacturer_data={34952: b"\x88\x88\xbf\x95\x01\x11\x36\x38"},
            service_uuids=[
                "0000ffe0-0000-1000-8000-00805f9b34fb",
                "0000fee7-0000-1000-8000-00805f9b34fb",
            ],
        ),
        "neey_bms",
    ),
    (  # source advmon (https://github.com/patman15/BMS_BLE-HA/issues/291)
        generate_advertisement_data(
            local_name="GW-24Srenamed2",
            rssi=-88,
            service_uuids=[
                "0000ffe0-0000-1000-8000-00805f9b34fb",
                "0000fee7-0000-1000-8000-00805f9b34fb",
            ],
        ),
        "neey_bms",
    ),
    (  # source advmon (https://github.com/patman15/BMS_BLE-HA/issues/291)
        generate_advertisement_data(
            local_name="GW-24Srenamed3",
            rssi=-73,
            manufacturer_data={
                55769: b"\x88\xa0\x2b\x80\x03\xf2\xfc\x9b"
            },  # MAC address
            service_uuids=[
                "0000ffe0-0000-1000-8000-00805f9b34fb",
                "0000fee7-0000-1000-8000-00805f9b34fb",
            ],
        ),
        "neey_bms",
    ),
    (  # proxy LOG (https://github.com/patman15/BMS_BLE-HA/issues/85)
        generate_advertisement_data(  # Bulltron battery
            local_name="DL-FB4C2E0000000",  # MAC address (Bouffalo Lab)
            manufacturer_data={771: " \x00\xb4\xc2\xe0\x00\x00\x00\x44\x4c\x00"},
            service_uuids=[],
            rssi=-81,
        ),
        "daly_bms",
    ),
    (  # source advmon (https://github.com/patman15/BMS_BLE-HA/issues/326)
        generate_advertisement_data(
            local_name="DCHOUSE 01_4F9F",
            rssi=-68,
            manufacturer_data={57570: b"\x5a\x72\xa7\x45"},  # MAC address correct
            service_uuids=["0000fff0-0000-1000-8000-00805f9b34fb"],
        ),
        "ecoworthy_bms",
    ),
    (  # source advmon (https://github.com/patman15/BMS_BLE-HA/issues/329)
        generate_advertisement_data(
            local_name="DWCK00309J-029",  # Vatrer battery
            manufacturer_data={49148: b"\x34\x37\xc1\xa4"},  # MAC address, wrong
            service_uuids=["0000ff00-0000-1000-8000-00805f9b34fb"],
            rssi=-46,
        ),
        "jbd_bms",
    ),
    (  # source advmon (https://github.com/patman15/BMS_BLE-HA/issues/346)
        generate_advertisement_data(
            local_name="LT-12100BG-A06359",
            manufacturer_data={22618: b"\x36\x34\x24\x62\xa2\x6b"},
            service_uuids=["0000ffe0-0000-1000-8000-00805f9b34fb"],
            rssi=-87,
        ),
        "ej_bms",
    ),
    (  # source advmon (https://github.com/patman15/BMS_BLE-HA/issues/358)
        generate_advertisement_data(
            local_name="libattU12E9",
            manufacturer_data={21320: b"8428089d12e96400"},
            service_uuids=[
                "00001800-0000-1000-8000-00805f9b34fb",
                "00001801-0000-1000-8000-00805f9b34fb",
                "6e400001-b5a3-f393-e0a9-e50e24dcca9e",
            ],
            rssi=-62,
        ),
        "ej_bms",
    ),
    (  # source advmon (https://github.com/patman15/BMS_BLE-HA/issues/346)
        generate_advertisement_data(
            local_name="xiaoxiang BMS",
            manufacturer_data={11313: b"\x20\x37\xc1\xa4"},  # MAC address, wrong
            service_uuids=["0000ff00-0000-1000-8000-00805f9b34fb"],
            rssi=-43,
        ),
        "jbd_bms",
    ),
    (  # source advmon (https://github.com/patman15/BMS_BLE-HA/issues/370)
        generate_advertisement_data(
            local_name="L-12100BNNA70-A09683",
            rssi=-46,
            manufacturer_data={22618: b"\xc8\x47\x80\x15\xde\x04"},
            service_uuids=["0000ffe0-0000-1000-8000-00805f9b34fb"],
        ),
        "redodo_bms",
    ),
    (  # source advmon (https://github.com/patman15/BMS_BLE-HA/issues/367)
        generate_advertisement_data(
            local_name="RO-24100B-A00162",
            rssi=-45,
            manufacturer_data={22618: b"\xc8\x47\x80\x12\xd5\xe7"},
            service_uuids=["0000ffe0-0000-1000-8000-00805f9b34fb"],
        ),
        "redodo_bms",
    ),
    (  # source advmon (https://github.com/patman15/BMS_BLE-HA/issues/366)
        generate_advertisement_data(
            local_name="ANT-BLE24C-001",
            rssi=-70,
            manufacturer_data={8979: b"\x88\xa0\xaa\xbb\xcc\x90\x00\x01"},
            service_uuids=["0000ffe0-0000-1000-8000-00805f9b34fb"],
        ),
        "ant_bms",
    ),
    (  # source advmon (https://github.com/patman15/BMS_BLE-HA/issues/390)
        generate_advertisement_data(
            local_name="RNGRBP1228000830",
            rssi=-44,
            manufacturer_data={57676: b"\x74\x57\x94\x7b"},  # MAC address, correct
        ),
        "renogy_pro_bms",
    ),
    (  # source advmon (https://github.com/patman15/BMS_BLE-HA/issues/360)
        generate_advertisement_data(
            local_name="LT-51230BGC-A00229",
            rssi=-64,
            manufacturer_data={22618: b"\xc8\x47\x80\x12\xd6\x4e"},  # MAC address
            service_uuids=["0000ffe0-0000-1000-8000-00805f9b34fb"],
        ),
        "redodo_bms",
    ),
    (  # source advmon (https://github.com/patman15/BMS_BLE-HA/issues/386)
        generate_advertisement_data(
            local_name="ECO-WORTHY 0B_198D",
            manufacturer_data={
                59362: b"\x79\x8e\x37\x3d"
            },  # MAC address, correct, private
            service_uuids=["0000fff0-0000-1000-8000-00805f9b34fb"],
            rssi=-50,
        ),
        "ecoworthy_bms",
    ),
    (  # source advmon (https://github.com/patman15/BMS_BLE-HA/issues/406)
        generate_advertisement_data(
            local_name="AL12-100-4S-B01",
            manufacturer_data={36783: b"\x30\x37\xc1\xa4"},  # MAC address, wrong
            service_uuids=["0000ff00-0000-1000-8000-00805f9b34fb"],
            rssi=-63,
        ),
        "jbd_bms",
    ),
    (  # source advmon (https://github.com/patman15/BMS_BLE-HA/issues/406)
        generate_advertisement_data(
            local_name="AL12-100-4S-B02",
            manufacturer_data={21516: b"\x50\x37\xc1\xa4"},  # MAC address, wrong
            service_uuids=["0000ff00-0000-1000-8000-00805f9b34fb"],
            rssi=-62,
        ),
        "jbd_bms",
    ),
    (  # source advmon (https://github.com/patman15/BMS_BLE-HA/issues/402)
        generate_advertisement_data(
            local_name="LT-12100BG-A07700",  # -A07248
            manufacturer_data={22618: b"\xc8\x47\x80\x12\xb3\xb8"},
            service_uuids=["0000ffe0-0000-1000-8000-00805f9b34fb"],
            rssi=-87,
        ),
        "redodo_bms",
    ),
    (  # source PCAP (https://github.com/patman15/BMS_BLE-HA/issues/412)
        generate_advertisement_data(  # OUI: 90:a6:bf
            local_name="TP_123456",
            rssi=-87,
        ),
        "tianpwr_bms",
    ),
    (  # source advmon (https://github.com/patman15/BMS_BLE-HA/issues/423)
        generate_advertisement_data(
            local_name="DXDB00213J-020",
            manufacturer_data={58324: b"\x32\x38\xc1\xa4"},
            service_uuids=["0000ff00-0000-1000-8000-00805f9b34fb"],
            rssi=-94,
        ),
        "jbd_bms",
    ),
    (  # source advmon (https://github.com/patman15/BMS_BLE-HA/issues/427)
        generate_advertisement_data(
            local_name="06201000690",
            manufacturer_data={
                529: b"\x00\x00\x40\x00\x2a\xbb\x7f\xff\x2b\x38\x2b\x43\xc8\xcb\x00\x7c\x00\xbf\xbf\xbf\xc0\x00\x00\x00\x00\x25\x80"
            },
            service_data={"0000262a-0000-1000-8000-00805f9b34fb": b"\x46\x00\x3e"},
            service_uuids=[
                "00001800-0000-1000-8000-00805f9b34fb",
                "00001801-0000-1000-8000-00805f9b34fb",
                "0000180a-0000-1000-8000-00805f9b34fb",
                "0000180f-0000-1000-8000-00805f9b34fb",
                "0000262a-0000-1000-8000-00805f9b34fb",
                "0000fa00-0000-1000-8000-00805f9b34fb",
                "0000ff00-0000-1000-8000-00805f9b34fb",
            ],
            rssi=-48,
        ),
        "jbd_bms",
    ),
    (  # source advmon (https://github.com/patman15/BMS_BLE-HA/issues/439)
        generate_advertisement_data(
            local_name="L-51030GBNGC2-A00263",
            rssi=-66,
            manufacturer_data={22618: "\xc8\x47\x80\x14\xec\x68"},
            service_uuids=["0000ffe0-0000-1000-8000-00805f9b34fb"],
        ),
        "redodo_bms",
    ),
    (  # source pcap (https://github.com/patman15/BMS_BLE-HA/issues/444)
        generate_advertisement_data(
            local_name="BS202212-01-0168",
            rssi=-91,
            service_uuids=["0000ff00-0000-1000-8000-00805f9b34fb"],
        ),
        "jbd_bms",
    ),
    (  # source advmon (https://github.com/patman15/BMS_BLE-HA/issues/454)
        generate_advertisement_data(
            local_name="EK-16S2EB",
            rssi=-73,
            service_uuids=[
                "0000ffe0-0000-1000-8000-00805f9b34fb",
                "0000fee7-0000-1000-8000-00805f9b34fb",
            ],
        ),
        "neey_bms",
    ),
    (  # source advmon (https://github.com/patman15/BMS_BLE-HA/issues/454)
        generate_advertisement_data(
            local_name="SP95B-B2503190001",
            rssi=-65,
            service_uuids=["0000fff0-0000-1000-8000-00805f9b34fb"],
        ),
        "seplos_bms",
    ),
]
