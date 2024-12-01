"""Test the BLE Battery Management System integration constants definition."""

from custom_components.bms_ble.const import BMS_TYPES, UPDATE_INTERVAL


async def test_critical_constants() -> None:
    """Test general constants are not altered for debugging."""

    assert UPDATE_INTERVAL == 30  # ensure that update interval is 30 seconds
    assert len(BMS_TYPES) == 10  # check number of BMS types
