"""Test the BLE Battery Management System integration constants definition."""

from custom_components.bms_ble.const import UPDATE_INTERVAL, BMS_TYPES


async def test_update_interval() -> None:
    """Test general constants are not altered for debugging."""

    assert UPDATE_INTERVAL == 30  # ensure that update interval is 30 seconds
    assert len(BMS_TYPES) == 6  # check number of BMS types
