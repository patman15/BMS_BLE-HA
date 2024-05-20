"""Test the BLE Battery Management System base class functions."""

from custom_components.bms_ble.plugins.basebms import BaseBMS


def test_device_info(plugin_fixture) -> None:
    """Test that the BMS returns valid device information."""
    bms_instance: BaseBMS = plugin_fixture
    result = bms_instance.device_info()
    assert "manufacturer" in result
    assert "model" in result


def test_matcher_dict(plugin_fixture) -> None:
    """Test that the BMS returns BT matcher."""
    bms_instance: BaseBMS = plugin_fixture
    assert len(bms_instance.matcher_dict_list())
