"""Test the BLE Battery Management System update coordinator."""

from custom_components.bms_ble.const import (
    ATTR_CURRENT,
    ATTR_CYCLE_CHRG,
    ATTR_CYCLES,
    ATTR_RSSI,
    ATTR_VOLTAGE,
)
from custom_components.bms_ble.coordinator import BTBmsCoordinator

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import UpdateFailed

from .bluetooth import inject_bluetooth_service_info_bleak
from .conftest import Mock_BMS


async def test_update(BTdiscovery, hass: HomeAssistant) -> None:
    """Test setting up creates the sensors."""

    coordinator = BTBmsCoordinator(hass, BTdiscovery.device, Mock_BMS())

    inject_bluetooth_service_info_bleak(hass, BTdiscovery)

    await coordinator.async_refresh()
    result = coordinator.data
    assert coordinator.last_update_success

    await coordinator.stop()

    assert result == {
        ATTR_VOLTAGE: 13,
        ATTR_CURRENT: 1.7,
        ATTR_CYCLE_CHRG: 19,
        ATTR_CYCLES: 23,
        ATTR_RSSI: BTdiscovery.rssi,
    }


async def test_update_exception(
    BTdiscovery, mock_coordinator_exception, hass: HomeAssistant
) -> None:
    """Test setting up creates the sensors."""

    coordinator = BTBmsCoordinator(
        hass, BTdiscovery.device, Mock_BMS(mock_coordinator_exception)
    )

    await coordinator.async_refresh()
    assert not coordinator.last_update_success
    assert isinstance(
        coordinator.last_exception,
        TimeoutError if mock_coordinator_exception == TimeoutError else UpdateFailed,
    )
