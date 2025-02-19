"""Test the BLE Battery Management System integration config flow."""

from typing import Final

from bleak.backends.scanner import AdvertisementData
from home_assistant_bluetooth import BluetoothServiceInfoBleak
import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.bms_ble.const import DOMAIN
from custom_components.bms_ble.plugins.basebms import BaseBMS
from homeassistant.config_entries import (
    SOURCE_BLUETOOTH,
    SOURCE_USER,
    ConfigEntryState,
    ConfigFlowResult,
)
from homeassistant.const import CONF_ADDRESS
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers import entity_registry as er

from .advertisement_data import ADVERTISEMENTS
from .bluetooth import (
    generate_advertisement_data,
    generate_ble_device,
    inject_bluetooth_service_info_bleak,
)
from .conftest import mock_config, mock_update_min


@pytest.fixture(
    name="advertisement",
    params=ADVERTISEMENTS,
    ids=lambda param: param[1],
)
def bms_advertisement(request) -> BluetoothServiceInfoBleak:
    """Return faulty response frame."""
    dev: Final[AdvertisementData] = request.param[0]
    address: Final[str] = "c0:ff:ee:c0:ff:ee"
    return BluetoothServiceInfoBleak(
        name=str(dev.local_name),
        address=f"{address}_{request.param[1]}",
        device=generate_ble_device(address=address, name=dev.local_name),
        rssi=dev.rssi,
        service_uuids=dev.service_uuids,
        manufacturer_data=dev.manufacturer_data,
        service_data=dev.service_data,
        advertisement=generate_advertisement_data(**dev._asdict()),
        source=SOURCE_BLUETOOTH,
        connectable=True,
        time=0,
        tx_power=dev.tx_power,
    )


async def test_bluetooth_discovery(
    hass: HomeAssistant, advertisement: BluetoothServiceInfoBleak
) -> None:
    """Test bluetooth device discovery."""

    inject_bluetooth_service_info_bleak(hass, advertisement)
    await hass.async_block_till_done(wait_background_tasks=True)

    flowresults: list[ConfigFlowResult] = (
        hass.config_entries.flow.async_progress_by_handler(DOMAIN)
    )
    assert len(flowresults) == 1, f"Expected one flow result for {advertisement}"
    result: ConfigFlowResult = flowresults[0]
    assert result.get("step_id") == "bluetooth_confirm"
    assert result.get("context", {}).get("unique_id") == advertisement.address

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={"not": "empty"}
    )
    await hass.async_block_till_done()
    assert result.get("type") == FlowResultType.CREATE_ENTRY
    assert (
        result.get("title") == advertisement.name or advertisement.address
    )  # address is used as name by Bleak if name is not available

    # BluetoothServiceInfoBleak contains BMS type as trailer to the address, see bms_advertisement
    assert (
        hass.config_entries.async_entries()[1].data["type"]
        == f"custom_components.bms_ble.plugins.{advertisement.address.split('_',1)[-1]}"
    )


async def test_device_setup(
    monkeypatch,
    patch_bleakclient: None,
    BTdiscovery: BluetoothServiceInfoBleak,
    hass: HomeAssistant,
) -> None:
    """Test discovery via bluetooth with a valid device."""

    result: ConfigFlowResult = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_BLUETOOTH},
        data=BTdiscovery,
    )

    assert result.get("type") == FlowResultType.FORM
    assert result.get("step_id") == "bluetooth_confirm"
    assert result.get("description_placeholders") == {"name": "SmartBat-B12345"}

    inject_bluetooth_service_info_bleak(hass, BTdiscovery)

    monkeypatch.setattr(
        "custom_components.bms_ble.plugins.ogt_bms.BMS.async_update",
        mock_update_min,
    )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={"not": "empty"}
    )
    await hass.async_block_till_done()
    assert result.get("type") == FlowResultType.CREATE_ENTRY
    assert result.get("title") == "SmartBat-B12345"

    result_detail = result.get("result")
    assert result_detail is not None
    assert result_detail.unique_id == "cc:cc:cc:cc:cc:cc"
    assert len(hass.states.async_all(["sensor", "binary_sensor"])) == 10

    entities = er.async_get(hass).entities
    assert len(entities) == 12  # sensors, binary_sensors, rssi

    # check correct unique_id format of all sensor entries
    for entry in entities.get_entries_for_config_entry_id(result_detail.entry_id):
        assert entry.unique_id.startswith(f"{DOMAIN}-cc:cc:cc:cc:cc:cc-")


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
    result: ConfigFlowResult = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_BLUETOOTH},
        data=BTdiscovery,
    )

    assert result.get("type") == FlowResultType.ABORT
    assert result.get("reason") == "not_supported"


async def test_already_configured(bms_fixture, hass: HomeAssistant) -> None:
    """Test that same device cannot be added twice."""

    cfg = mock_config(bms_fixture)
    cfg.add_to_hass(hass)

    await hass.config_entries.async_setup(cfg.entry_id)
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
    monkeypatch, patch_bleakclient, bms_fixture, BTdiscovery, hass: HomeAssistant
) -> None:
    """Test async_setup_entry with valid input."""

    inject_bluetooth_service_info_bleak(hass, BTdiscovery)

    cfg = mock_config(bms=bms_fixture)
    cfg.add_to_hass(hass)

    monkeypatch.setattr(
        f"custom_components.bms_ble.plugins.{bms_fixture}.BMS.async_update",
        mock_update_min,
    )

    assert await hass.config_entries.async_setup(cfg.entry_id)
    await hass.async_block_till_done()

    assert cfg in hass.config_entries.async_entries()
    assert cfg.state is ConfigEntryState.LOADED


async def test_setup_entry_missing_unique_id(bms_fixture, hass: HomeAssistant) -> None:
    """Test async_setup_entry with missing unique id."""

    cfg = mock_config(bms=bms_fixture, unique_id=None)
    cfg.add_to_hass(hass)

    assert not await hass.config_entries.async_setup(cfg.entry_id)

    assert cfg in hass.config_entries.async_entries()
    assert cfg.state is ConfigEntryState.SETUP_ERROR


async def test_user_setup(
    monkeypatch, patch_bleakclient, BTdiscovery, hass: HomeAssistant
) -> None:
    """Check config flow for user adding previously discovered device."""

    monkeypatch.setattr(
        "custom_components.bms_ble.plugins.ogt_bms.BMS.async_update",
        mock_update_min,
    )

    inject_bluetooth_service_info_bleak(hass, BTdiscovery)

    result: ConfigFlowResult = await hass.config_entries.flow.async_init(
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
                "options": [
                    {
                        "value": "cc:cc:cc:cc:cc:cc",
                        "label": "SmartBat-B12345 (cc:cc:cc:cc:cc:cc)",
                    }
                ],
                "multiple": False,
                "custom_value": False,
                "sort": False,
            }
        }
    }

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

    def patch_async_current_ids(_self) -> set[str | None]:
        return {"cc:cc:cc:cc:cc:cc"}

    monkeypatch.setattr(
        "custom_components.bms_ble.config_flow.ConfigFlow._async_current_ids",
        patch_async_current_ids,
    )

    inject_bluetooth_service_info_bleak(hass, BTdiscovery)

    result: ConfigFlowResult = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result.get("type") == FlowResultType.ABORT


async def test_no_migration(bms_fixture, hass: HomeAssistant) -> None:
    """Test that entries of correct version are kept."""

    cfg: MockConfigEntry = mock_config(bms=bms_fixture)
    #monkeypatch.setattr(cfg, "minor_version", 1)
    cfg.add_to_hass(hass)
    hass.config_entries.async_update_entry(cfg, minor_version=1)

    assert not await hass.config_entries.async_setup(cfg.entry_id)
    await hass.async_block_till_done()

    assert cfg in hass.config_entries.async_entries()
    assert cfg.version == 1
    assert cfg.minor_version == 1
    assert cfg.state is ConfigEntryState.SETUP_RETRY


async def test_migrate_entry_future_version(bms_fixture, hass: HomeAssistant) -> None:
    """Test migrating entries from future version."""

    cfg: MockConfigEntry = mock_config(bms=bms_fixture)
    # monkeypatch.setattr(cfg, "version", 999)
    cfg.add_to_hass(hass)
    hass.config_entries.async_update_entry(cfg, version=999)

    assert not await hass.config_entries.async_setup(cfg.entry_id)
    await hass.async_block_till_done()

    assert cfg in hass.config_entries.async_entries()
    assert cfg.state is ConfigEntryState.MIGRATION_ERROR


async def test_migrate_invalid_v_0_1(bms_fixture, hass: HomeAssistant) -> None:
    """Test migrating an invalid entry in version 0.1."""

    cfg: MockConfigEntry = mock_config(bms=bms_fixture)
    # monkeypatch.setattr(cfg, "version", 0)
    # monkeypatch.setattr(cfg, "data", {"type": None})
    cfg.add_to_hass(hass)
    hass.config_entries.async_update_entry(cfg, version=0, data={"type": None})

    assert not await hass.config_entries.async_setup(cfg.entry_id)
    await hass.async_block_till_done()

    assert cfg in hass.config_entries.async_entries()
    assert cfg.state is ConfigEntryState.MIGRATION_ERROR


async def test_migrate_entry_from_v_0_1(
    monkeypatch, patch_bleakclient, mock_config_v0_1, BTdiscovery, hass: HomeAssistant
) -> None:
    """Test migrating entries from version 0.1."""

    inject_bluetooth_service_info_bleak(hass, BTdiscovery)

    cfg: MockConfigEntry = mock_config_v0_1
    cfg.add_to_hass(hass)

    monkeypatch.setattr(
        f"custom_components.bms_ble.plugins.{(cfg.data["type"][:-3]).lower()}_bms.BMS.async_update",
        mock_update_min,
    )

    assert await hass.config_entries.async_setup(cfg.entry_id)
    await hass.async_block_till_done()

    assert cfg in hass.config_entries.async_entries()
    assert cfg.version == 1
    assert cfg.minor_version == 0
    assert cfg.state is ConfigEntryState.LOADED


async def test_migrate_unique_id(hass: HomeAssistant) -> None:
    """Verify that old style unique_ids are correctly migrated to new style."""
    cfg: MockConfigEntry = mock_config("jikong_bms")
    cfg.add_to_hass(hass)
    await hass.async_block_till_done()

    assert cfg in hass.config_entries.async_entries()
    config_entry = hass.config_entries.async_entries(domain=DOMAIN)[0]

    ent_reg = er.async_get(hass)
    # add entry with old unique_id style to be modified
    entry_old = ent_reg.async_get_or_create(
        capabilities={"state_class": "measurement"},
        config_entry=config_entry,
        domain=DOMAIN,
        has_entity_name=True,
        original_device_class="battery",
        original_name="Battery",
        platform="bms_ble",
        supported_features=0,
        translation_key="battery_level",
        unique_id="myJBD-test-battery_level",
        unit_of_measurement="%",
    )

    # generate another entry that should be kept untouched
    entry_new = ent_reg.async_get_or_create(
        capabilities={"state_class": "measurement"},
        config_entry=config_entry,
        domain=DOMAIN,
        has_entity_name=True,
        original_device_class="battery",
        original_name="Battery",
        platform="bms_ble",
        supported_features=0,
        translation_key="battery_level",
        unique_id=f"{DOMAIN}-myJBD-test-battery_level",
        unit_of_measurement="%",
    )

    await hass.config_entries.async_setup(cfg.entry_id)
    await hass.async_block_till_done()

    # check that "old_style" entry is migrated
    modified_entry = ent_reg.async_get(entry_old.entity_id)
    assert (modified_entry) is not None
    assert modified_entry.unique_id == f"{DOMAIN}-cc:cc:cc:cc:cc:cc-battery_level"

    # check that "new style" entry is not modified
    unmodified_entry = ent_reg.async_get(entry_new.entity_id)
    assert (unmodified_entry) is not None
    assert unmodified_entry.unique_id == f"{DOMAIN}-myJBD-test-battery_level"
