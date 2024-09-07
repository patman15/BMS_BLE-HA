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


async def test_update(
    monkeypatch, bool_fixture, BTdiscovery, hass: HomeAssistant
) -> None:
    """Test setting up creates the sensors."""

    def mock_last_service_info(hass, address, connectable) -> None:
        assert (
            isinstance(hass, HomeAssistant)
            and connectable is True
            and len(address) == 17
        ), "Call to get last advertisement is invalid."

    if (advertisement_avail := bool_fixture) is False:
        monkeypatch.setattr(
            "homeassistant.components.bluetooth.async_last_service_info",
            mock_last_service_info,
        )

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
    } | ({ATTR_RSSI: BTdiscovery.rssi} if advertisement_avail else {})


async def test_nodata(BTdiscovery, hass: HomeAssistant) -> None:
    """Test if coordinator raises exception in case no data, e.g. invalid CRC, is returned."""

    coordinator = BTBmsCoordinator(hass, BTdiscovery.device, Mock_BMS(ret_value={}))

    inject_bluetooth_service_info_bleak(hass, BTdiscovery)

    await coordinator.async_refresh()
    result = coordinator.data
    assert not coordinator.last_update_success

    await coordinator.stop()

    assert result is None


async def test_update_exception(
    BTdiscovery, mock_coordinator_exception, hass: HomeAssistant
) -> None:
    """Test if coordinator raises appropriate exception from BMS."""

    coordinator = BTBmsCoordinator(
        hass, BTdiscovery.device, Mock_BMS(mock_coordinator_exception)
    )

    await coordinator.async_refresh()
    assert not coordinator.last_update_success
    assert isinstance(
        coordinator.last_exception,
        TimeoutError if mock_coordinator_exception is TimeoutError else UpdateFailed,
    )
