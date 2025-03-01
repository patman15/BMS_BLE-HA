"""Test the BLE Battery Management System via fuzzing."""

from asyncio import iscoroutinefunction
from types import ModuleType

from hypothesis import HealthCheck, given, settings, strategies as st

# from custom_components.bms_ble.const import BMS_TYPES
from custom_components.bms_ble.plugins.basebms import BaseBMS

from .bluetooth import generate_ble_device
from .conftest import MockBleakClient, MockRespChar


@given(
    data=st.binary(min_size=1, max_size=513)
)  # ATT is not allowed larger than 512 bytes
@settings(
    max_examples=1000, suppress_health_check=[HealthCheck.function_scoped_fixture]
)
async def test_notification_handler(
    monkeypatch, plugin_fixture: ModuleType, data: bytearray
) -> None:
    """Test the notification handler."""

    async def patch_init() -> None:
        return

    monkeypatch.setattr(  # patch BleakClient to allow write calls in handler
        "custom_components.bms_ble.plugins.basebms.BleakClient",
        MockBleakClient,
    )

    bms_instance: BaseBMS = plugin_fixture.BMS(
        generate_ble_device("cc:cc:cc:cc:cc:cc", "MockBLEDev123", {"path": None}, -73)
    )

    monkeypatch.setattr(
        bms_instance, "_init_connection", patch_init
    )  # required for _init_connection overloads, e.g. JK BMS

    await bms_instance._connect()

    if iscoroutinefunction(bms_instance._notification_handler):  # type: ignore[attr-defined]
        await bms_instance._notification_handler(MockRespChar, data)  # type: ignore[attr-defined]
    else:
        bms_instance._notification_handler(MockRespChar, data)  # type: ignore[attr-defined]
