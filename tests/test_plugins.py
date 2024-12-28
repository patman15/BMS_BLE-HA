"""Test the BLE Battery Management System base class functions."""

from custom_components.bms_ble.const import BMS_TYPES
from custom_components.bms_ble.plugins.basebms import BaseBMS

from .advertisement_data import ADVERTISEMENTS


def test_device_info(plugin_fixture: BaseBMS) -> None:
    """Test that the BMS returns valid device information."""
    bms_instance: BaseBMS = plugin_fixture
    result = bms_instance.device_info()
    assert "manufacturer" in result
    assert "model" in result


def test_matcher_dict(plugin_fixture: BaseBMS) -> None:
    """Test that the BMS returns BT matcher."""
    bms_instance: BaseBMS = plugin_fixture
    assert len(bms_instance.matcher_dict_list())

def test_advertisements_complete() -> None:
    """Check that each BMS has at least one advertisement."""
    bms_unchecked: list[str] = BMS_TYPES
    for _adv, bms in ADVERTISEMENTS:
        if bms in bms_unchecked:
            bms_unchecked.remove(bms)
    assert not bms_unchecked, f"{len(bms_unchecked)} missing BMS type advertisements: {bms_unchecked}"
