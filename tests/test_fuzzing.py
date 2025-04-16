"""Test the BLE Battery Management System via fuzzing."""

from asyncio import iscoroutinefunction
from collections.abc import Callable
from types import ModuleType

from hypothesis import given, strategies as st
import pytest

from custom_components.bms_ble.const import BMS_TYPES
from custom_components.bms_ble.plugins.basebms import BaseBMS

from .bluetooth import generate_ble_device
from .conftest import MockBleakClient, MockRespChar


@given(
    data=st.binary(min_size=0, max_size=513)
)  # ATT is not allowed larger than 512 bytes
@pytest.mark.parametrize("plugin_fixture", BMS_TYPES, indirect=True)
async def test_notification_handler(
    monkeypatch: pytest.MonkeyPatch,
    patch_bleak_client,
    pytestconfig: pytest.Config,
    plugin_fixture: ModuleType,
    data: bytearray,
) -> None:
    """Test the notification handler."""

    # fuzzing can run from VScode (no coverage) or command line with option --no-cov
    if {"vscode_pytest", "--cov=bms_ble"}.issubset(
        set(pytestconfig.invocation_params.args)
    ) or (
        "vscode_pytest" not in pytestconfig.invocation_params.args
        and not pytestconfig.getoption("--no-cov")
    ):
        pytest.skip("Skipping fuzzing tests due to coverage generation!")

    async def patch_init() -> None:
        return

    patch_bleak_client(MockBleakClient)

    bms_instance: BaseBMS = plugin_fixture.BMS(  # char 10 needs to be A|B for OGT
        generate_ble_device("cc:cc:cc:cc:cc:cc", "MockFuzz-BLE", {"path": None}, -73)
    )

    monkeypatch.setattr(
        bms_instance, "_init_connection", patch_init
    )  # required for _init_connection overloads, e.g. JK BMS

    await bms_instance._connect()
    notify_handler: Callable = bms_instance._notification_handler  # type: ignore[attr-defined]

    if iscoroutinefunction(notify_handler):
        await notify_handler(MockRespChar(None, lambda: 0), data)
    else:
        notify_handler(MockRespChar(None, lambda: 0), data)
