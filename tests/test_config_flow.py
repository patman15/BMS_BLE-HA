"""Test the BLE Battery Management System integration config flow."""

from custom_components.bms_ble.const import DOMAIN
from custom_components.bms_ble.plugins.basebms import BaseBMS

from homeassistant.config_entries import SOURCE_BLUETOOTH, SOURCE_USER, ConfigEntryState
from homeassistant.const import CONF_ADDRESS
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from .bluetooth import inject_bluetooth_service_info_bleak
from .conftest import mock_config


async def test_device_discovery(monkeypatch, BTdiscovery, hass: HomeAssistant) -> None:
    """Test discovery via bluetooth with a valid device."""

    def patch_async_ble_device_from_address(hass: HomeAssistant, address, connectable):
        """Patch async ble device from address to return a given value."""
        return BTdiscovery.device

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_BLUETOOTH},
        data=BTdiscovery,
    )

    assert result.get("type") == FlowResultType.FORM
    assert result.get("step_id") == "bluetooth_confirm"
    assert result.get("description_placeholders") == {"name": "SmartBat-B12345"}

    monkeypatch.setattr(
        "custom_components.bms_ble.async_ble_device_from_address",
        patch_async_ble_device_from_address,
    )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={"not": "empty"}
    )
    await hass.async_block_till_done()
    assert result.get("type") == FlowResultType.CREATE_ENTRY
    assert result.get("title") == "SmartBat-B12345"

    result_detail = result.get("result")
    assert result_detail is not None
    assert (
        result_detail.unique_id
        == "cc:cc:cc:cc:cc:cc"  # pyright: ignore[reportOptionalMemberAccess]
    )
    assert len(hass.states.async_all(["sensor", "binary_sensor"])) == 10


async def test_device_not_supported(
    BTdiscovery_notsupported, hass: HomeAssistant
) -> None:
    """Test discovery via bluetooth with a invalid device."""

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_BLUETOOTH},
        data=BTdiscovery_notsupported,
    )

    assert result.get("type") == FlowResultType.ABORT
    assert result.get("reason") == "not_supported"


async def test_invalid_plugin(monkeypatch, BTdiscovery, hass: HomeAssistant) -> None:
    """Test discovery via bluetooth with a valid device but invalid plugin.

    assertion is handled by internal function
    """

    monkeypatch.delattr(BaseBMS, "supported")
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_BLUETOOTH},
        data=BTdiscovery,
    )

    assert result.get("type") == FlowResultType.ABORT
    assert result.get("reason") == "not_supported"


async def test_already_configured(bms_fixture, hass: HomeAssistant) -> None:
    """Test that same device cannot be added twice."""

    config = mock_config(bms_fixture)
    config.add_to_hass(hass)

    await hass.config_entries.async_setup(config.entry_id)
    await hass.async_block_till_done()

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
        data={
            CONF_ADDRESS: "cc:cc:cc:cc:cc:cc",
            "type": "custom_components.bms_ble.plugins.ogt_bms",
        },
    )
    assert result.get("type") == FlowResultType.ABORT
    assert result.get("reason") == "already_configured"


async def test_async_setup_entry(
    monkeypatch, bms_fixture, BTdiscovery, hass: HomeAssistant
) -> None:
    """Test async_setup_entry with valid input."""

    def patch_async_ble_device_from_address(hass: HomeAssistant, address, connectable):
        """Patch async ble device from address to return a given value."""
        return BTdiscovery.device

    monkeypatch.setattr(
        "custom_components.bms_ble.async_ble_device_from_address",
        patch_async_ble_device_from_address,
    )

    config = mock_config(bms=bms_fixture)
    config.add_to_hass(hass)

    assert await hass.config_entries.async_setup(config.entry_id)
    await hass.async_block_till_done()

    assert config in hass.config_entries.async_entries()
    assert config.state is ConfigEntryState.LOADED


async def test_setup_entry_missing_unique_id(bms_fixture, hass: HomeAssistant) -> None:
    """Test async_setup_entry with missing unique id."""

    config = mock_config(bms=bms_fixture, unique_id=None)
    config.add_to_hass(hass)

    assert not await hass.config_entries.async_setup(config.entry_id)

    assert config in hass.config_entries.async_entries()
    assert config.state is ConfigEntryState.SETUP_ERROR


async def test_user_setup(monkeypatch, BTdiscovery, hass: HomeAssistant) -> None:
    """Check config flow for user adding previously discovered device."""

    def patch_async_ble_device_from_address(hass: HomeAssistant, address, connectable):
        """Patch async ble device from address to return a given value."""
        return BTdiscovery.device

    inject_bluetooth_service_info_bleak(hass, BTdiscovery)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result.get("type") == FlowResultType.FORM
    assert result.get("step_id") == "user"
    assert result.get("errors") is None

    data_schema = result.get("data_schema")
    assert data_schema is not None
    assert data_schema.schema.get(CONF_ADDRESS).serialize() == {
        "selector": {
            "select": {
                "options": [{"value": "cc:cc:cc:cc:cc:cc", "label": "SmartBat-B12345"}],
                "multiple": False,
                "custom_value": False,
                "sort": False,
            }
        }
    }

    monkeypatch.setattr(
        "custom_components.bms_ble.async_ble_device_from_address",
        patch_async_ble_device_from_address,
    )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={CONF_ADDRESS: "cc:cc:cc:cc:cc:cc"}
    )

    await hass.async_block_till_done()
    assert result.get("type") == FlowResultType.CREATE_ENTRY
    assert result.get("title") == "SmartBat-B12345"

    result_detail = result.get("result")
    assert result_detail is not None
    assert result_detail.unique_id == "cc:cc:cc:cc:cc:cc"
    assert len(hass.states.async_all(["sensor", "binary_sensor"])) == 10


async def test_user_setup_invalid(
    BTdiscovery_notsupported, hass: HomeAssistant
) -> None:
    """Check config flow for user adding previously discovered invalid device."""

    inject_bluetooth_service_info_bleak(hass, BTdiscovery_notsupported)
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result.get("type") == FlowResultType.ABORT


async def test_user_setup_double_configure(
    monkeypatch, BTdiscovery, hass: HomeAssistant
) -> None:
    """Check config flow for user adding previously already added device."""

    def patch_async_current_ids(self) -> set[str | None]:
        return {"cc:cc:cc:cc:cc:cc"}

    monkeypatch.setattr(
        "custom_components.bms_ble.config_flow.ConfigFlow._async_current_ids",
        patch_async_current_ids,
    )

    inject_bluetooth_service_info_bleak(hass, BTdiscovery)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result.get("type") == FlowResultType.ABORT


async def test_migrate_entry_future_version(
    monkeypatch, bms_fixture, hass: HomeAssistant
) -> None:
    """Test migrating entries from future version."""

    config = mock_config(bms=bms_fixture)
    monkeypatch.setattr(config, "version", 999)
    config.add_to_hass(hass)

    assert not await hass.config_entries.async_setup(config.entry_id)
    await hass.async_block_till_done()

    assert config in hass.config_entries.async_entries()
    assert config.state is ConfigEntryState.MIGRATION_ERROR


async def test_migrate_invalid_v_0_1(
    monkeypatch, bms_fixture, hass: HomeAssistant
) -> None:
    """Test migrating an invalid entry in version 0.1."""

    config = mock_config(bms=bms_fixture)
    monkeypatch.setattr(config, "version", 0)
    monkeypatch.setattr(config, "data", {"type": None})
    config.add_to_hass(hass)

    assert not await hass.config_entries.async_setup(config.entry_id)
    await hass.async_block_till_done()

    assert config in hass.config_entries.async_entries()
    assert config.state is ConfigEntryState.MIGRATION_ERROR


async def test_migrate_entry_from_v_0_1(
    monkeypatch, mock_config_v0_1, BTdiscovery, hass: HomeAssistant
) -> None:
    """Test migrating entries from version 0.1."""

    def patch_async_ble_device_from_address(hass: HomeAssistant, address, connectable):
        """Patch async ble device from address to return a given value."""
        return BTdiscovery.device

    monkeypatch.setattr(
        "custom_components.bms_ble.async_ble_device_from_address",
        patch_async_ble_device_from_address,
    )

    config = mock_config_v0_1
    config.add_to_hass(hass)

    assert await hass.config_entries.async_setup(config.entry_id)
    await hass.async_block_till_done()

    assert config in hass.config_entries.async_entries()
    assert config.version == 1
    assert config.minor_version == 0
    assert config.state is ConfigEntryState.LOADED
