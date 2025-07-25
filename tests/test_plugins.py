"""Test the BLE Battery Management System base class functions."""

from collections.abc import Callable
import importlib
from types import ModuleType
from typing import Final

from home_assistant_bluetooth import BluetoothServiceInfoBleak

from custom_components.bms_ble.const import BMS_TYPES
from custom_components.bms_ble.plugins.basebms import BaseBMS

from .advertisement_data import ADVERTISEMENTS
from .advertisement_ignore import ADVERTISEMENTS_IGNORE
from .bluetooth import generate_ble_device

BMS_SUPPORTED_FCTS: Final[
    set[tuple[str, Callable[[BluetoothServiceInfoBleak], bool]]]
] = {
    (
        bms_type,
        importlib.import_module(
            f"custom_components.bms_ble.plugins.{bms_type}",
            package=__name__[: __name__.rfind(".")],
        ).BMS.supported,
    )
    for bms_type in BMS_TYPES
}


def test_device_info(plugin_fixture: ModuleType) -> None:
    """Test that the BMS returns valid device information."""
    bms_instance: BaseBMS = plugin_fixture.BMS
    result: dict[str, str] = bms_instance.device_info()
    assert "manufacturer" in result
    assert "model" in result


def test_matcher_dict(plugin_fixture: ModuleType) -> None:
    """Test that the BMS returns BT matcher."""
    bms_instance: BaseBMS = plugin_fixture.BMS
    assert len(bms_instance.matcher_dict_list())


def test_advertisements_complete() -> None:
    """Check that each BMS has at least one advertisement."""
    bms_tocheck: list[str] = BMS_TYPES
    for _adv, bms in ADVERTISEMENTS:
        if bms in bms_tocheck:
            bms_tocheck.remove(bms)
    assert (
        not bms_tocheck
    ), f"{len(bms_tocheck)} missing BMS type advertisements: {bms_tocheck}"


def test_advertisements_unique() -> None:
    """Check that each advertisement only matches one, the right BMS."""

    for adv, bms_real in ADVERTISEMENTS:
        for bms_test, fct_supported in BMS_SUPPORTED_FCTS:
            supported: bool = fct_supported(
                BluetoothServiceInfoBleak.from_scan(
                    device=generate_ble_device(
                        address="cc:cc:cc:cc:cc:cc",
                        name="MockBLEDevice",
                    ),
                    advertisement_data=adv,
                    source="test_advertisement_data",
                    monotonic_time=0.0,
                    connectable=True,
                )
            )
            assert supported == (
                bms_real == bms_test
            ), f"{adv} {"incorrectly matches"if supported else "does not match"} {bms_test}!"


def test_advertisements_ignore() -> None:
    """Check that each advertisement only matches one, the right BMS."""
    for adv, reason in ADVERTISEMENTS_IGNORE:
        for bms, fct_supported in BMS_SUPPORTED_FCTS:
            supported: bool = fct_supported(
                BluetoothServiceInfoBleak.from_scan(
                    device=generate_ble_device(
                        address="cc:cc:cc:cc:cc:cc",
                        name="MockBLEDevice",
                    ),
                    advertisement_data=adv,
                    source="test_advertisement_ignore",
                    monotonic_time=0.0,
                    connectable=True,
                )
            )
            assert not supported, f"{adv} incorrectly matches {bms}! {reason=}"
