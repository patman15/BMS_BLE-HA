"""Test the BLE Battery Management System integration constants definition."""

from pathlib import Path

from custom_components.bms_ble.const import BMS_TYPES, UPDATE_INTERVAL


async def test_critical_constants() -> None:
    """Test general constants are not altered for debugging."""

    assert (  # ensure that update interval is 30 seconds
        UPDATE_INTERVAL == 30
    ), "Update interval incorrect!"

    assert (
        len(BMS_TYPES)
        == sum(1 for _ in Path("custom_components/bms_ble/plugins/").glob("*_bms.py"))
        - 1  # remove dummy_bms
    ), "missing BMS type in type list!"
