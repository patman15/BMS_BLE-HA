"""Test the BLE Battery Management System integration config flow."""

from typing import Final

from bleak.backends.scanner import AdvertisementData
from home_assistant_bluetooth import BluetoothServiceInfoBleak
import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry
from voluptuous import Schema

from custom_components.bms_ble.const import DOMAIN
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
from tests.advertisement_data import ADVERTISEMENTS
from tests.bluetooth import generate_ble_device, inject_bluetooth_service_info_bleak
from tests.conftest import mock_config, mock_config_v1_0, mock_update_min


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
        advertisement=dev,
        source=SOURCE_BLUETOOTH,
        connectable=True,
        time=0,
        tx_power=dev.tx_power,
    )


@pytest.mark.usefixtures("enable_bluetooth")
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
        == f"aiobmsble.bms.{advertisement.address.split('_',1)[-1]}"
    )


@pytest.mark.usefixtures("enable_bluetooth", "patch_default_bleak_client")
async def test_device_setup(
    monkeypatch,
    bt_discovery: BluetoothServiceInfoBleak,
    hass: HomeAssistant,
) -> None:
    """Test discovery via bluetooth with a valid device."""

    result: ConfigFlowResult = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_BLUETOOTH},
        data=bt_discovery,
    )

    assert result.get("type") == FlowResultType.FORM
    assert result.get("step_id") == "bluetooth_confirm"
    assert result.get("description_placeholders") == {
        "name": "SmartBat-B12345",
        "id": ":cc:cc:cc",
        "model": "OGT BMS",
    }

    inject_bluetooth_service_info_bleak(hass, bt_discovery)

    monkeypatch.setattr(
        "aiobmsble.bms.ogt_bms.BMS.async_update",
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
    assert len(hass.states.async_all(["sensor", "binary_sensor"])) == 11

    entities: er.EntityRegistryItems = er.async_get(hass).entities
    assert len(entities) == 13  # sensors, binary_sensors, rssi

    # check correct unique_id format of all sensor entries
    for entry in entities.get_entries_for_config_entry_id(result_detail.entry_id):
        assert entry.unique_id.startswith(f"{DOMAIN}-cc:cc:cc:cc:cc:cc-")


async def test_device_not_supported(
    bt_discovery_notsupported: BluetoothServiceInfoBleak, hass: HomeAssistant
) -> None:
    """Test discovery via bluetooth with a invalid device."""

    result: ConfigFlowResult = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_BLUETOOTH},
        data=bt_discovery_notsupported,
    )

    assert result.get("type") == FlowResultType.ABORT
    assert result.get("reason") == "not_supported"


# async def test_invalid_plugin(
#     monkeypatch, bt_discovery: BluetoothServiceInfoBleak, hass: HomeAssistant
# ) -> None:
#     """Test discovery via bluetooth with a valid device but invalid plugin.

#     assertion is handled by internal function
#     """

#     monkeypatch.delattr(BaseBMS, "async_update")
#     result: ConfigFlowResult = await hass.config_entries.flow.async_init(
#         DOMAIN,
#         context={"source": SOURCE_BLUETOOTH},
#         data=bt_discovery,
#     )

#     assert result.get("type") == FlowResultType.ABORT
#     assert result.get("reason") == "not_supported"


async def test_already_configured(bms_fixture: str, hass: HomeAssistant) -> None:
    """Test that same device cannot be added twice."""

    cfg: MockConfigEntry = mock_config(bms_fixture)
    cfg.add_to_hass(hass)

    await hass.config_entries.async_setup(cfg.entry_id)
    await hass.async_block_till_done()

    result: ConfigFlowResult = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
        data={
            CONF_ADDRESS: "cc:cc:cc:cc:cc:cc",
            "type": "aiobmsble.bms.ogt_bms",
        },
    )
    assert result.get("type") == FlowResultType.ABORT
    assert result.get("reason") == "already_configured"


@pytest.mark.usefixtures("enable_bluetooth", "patch_default_bleak_client")
async def test_async_setup_entry(
    monkeypatch,
    bms_fixture: str,
    bt_discovery: BluetoothServiceInfoBleak,
    hass: HomeAssistant,
) -> None:
    """Test async_setup_entry with valid input."""

    inject_bluetooth_service_info_bleak(hass, bt_discovery)

    cfg: MockConfigEntry = mock_config(bms=bms_fixture)
    cfg.add_to_hass(hass)

    monkeypatch.setattr(
        f"aiobmsble.bms.{bms_fixture}.BMS.async_update",
        mock_update_min,
    )

    assert await hass.config_entries.async_setup(cfg.entry_id)
    await hass.async_block_till_done()

    assert cfg in hass.config_entries.async_entries()
    assert cfg.state is ConfigEntryState.LOADED


async def test_setup_entry_missing_unique_id(bms_fixture, hass: HomeAssistant) -> None:
    """Test async_setup_entry with missing unique id."""

    cfg: MockConfigEntry = mock_config(bms=bms_fixture, unique_id=None)
    cfg.add_to_hass(hass)

    assert not await hass.config_entries.async_setup(cfg.entry_id)

    assert cfg in hass.config_entries.async_entries()
    assert cfg.state is ConfigEntryState.SETUP_ERROR


@pytest.mark.usefixtures("enable_bluetooth", "patch_default_bleak_client")
async def test_user_setup(
    monkeypatch, bt_discovery: BluetoothServiceInfoBleak, hass: HomeAssistant
) -> None:
    """Check config flow for user adding previously discovered device."""

    monkeypatch.setattr(
        "aiobmsble.bms.ogt_bms.BMS.async_update",
        mock_update_min,
    )

    inject_bluetooth_service_info_bleak(hass, bt_discovery)

    result: ConfigFlowResult = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result.get("type") == FlowResultType.FORM
    assert result.get("step_id") == "user"
    assert result.get("errors") is None

    data_schema: Final[Schema | None] = result.get("data_schema")
    assert data_schema is not None
    assert data_schema.schema.get(CONF_ADDRESS).serialize() == {
        "selector": {
            "select": {
                "options": [
                    {
                        "value": "cc:cc:cc:cc:cc:cc",
                        "label": "SmartBat-B12345 (cc:cc:cc:cc:cc:cc) - OGT BMS",
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
    assert len(hass.states.async_all(["sensor", "binary_sensor"])) == 11


@pytest.mark.usefixtures("enable_bluetooth")
async def test_user_setup_invalid(
    bt_discovery_notsupported: BluetoothServiceInfoBleak, hass: HomeAssistant
) -> None:
    """Check config flow for user adding previously discovered invalid device."""

    inject_bluetooth_service_info_bleak(hass, bt_discovery_notsupported)
    result: Final[ConfigFlowResult] = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result.get("type") == FlowResultType.ABORT


@pytest.mark.usefixtures("enable_bluetooth")
async def test_user_setup_double_configure(
    monkeypatch, bt_discovery: BluetoothServiceInfoBleak, hass: HomeAssistant
) -> None:
    """Check config flow for user adding previously already added device."""

    def patch_async_current_ids(_self) -> set[str | None]:
        return {"cc:cc:cc:cc:cc:cc"}

    monkeypatch.setattr(
        "custom_components.bms_ble.config_flow.ConfigFlow._async_current_ids",
        patch_async_current_ids,
    )

    inject_bluetooth_service_info_bleak(hass, bt_discovery)

    result: ConfigFlowResult = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result.get("type") == FlowResultType.ABORT


async def test_no_migration(bms_fixture: str, hass: HomeAssistant) -> None:
    """Test that entries of correct version are kept."""

    cfg: MockConfigEntry = mock_config(bms=bms_fixture)
    cfg.add_to_hass(hass)
    hass.config_entries.async_update_entry(cfg, minor_version=1)

    assert not await hass.config_entries.async_setup(cfg.entry_id)
    await hass.async_block_till_done()

    assert cfg in hass.config_entries.async_entries()
    assert cfg.version == 2
    assert cfg.minor_version == 1
    assert cfg.state is ConfigEntryState.SETUP_RETRY


async def test_migrate_entry_future_version(
    bms_fixture: str, hass: HomeAssistant
) -> None:
    """Test migrating entries from future version."""

    cfg: MockConfigEntry = mock_config(bms=bms_fixture)
    cfg.add_to_hass(hass)
    hass.config_entries.async_update_entry(cfg, version=999)

    assert not await hass.config_entries.async_setup(cfg.entry_id)
    await hass.async_block_till_done()

    assert cfg in hass.config_entries.async_entries()
    assert cfg.state is ConfigEntryState.MIGRATION_ERROR


async def test_migrate_invalid_v_0_1(bms_fixture: str, hass: HomeAssistant) -> None:
    """Test migrating an invalid entry in version 0.1."""

    cfg: MockConfigEntry = mock_config(bms=bms_fixture)
    cfg.add_to_hass(hass)
    hass.config_entries.async_update_entry(cfg, version=0, data={"type": None})

    assert not await hass.config_entries.async_setup(cfg.entry_id)
    await hass.async_block_till_done()

    assert cfg in hass.config_entries.async_entries()
    assert cfg.state is ConfigEntryState.MIGRATION_ERROR


@pytest.mark.usefixtures("enable_bluetooth", "patch_default_bleak_client")
async def test_migrate_entry_from_v1_0(
    monkeypatch: pytest.MonkeyPatch,
    bt_discovery: BluetoothServiceInfoBleak,
    bms_fixture: str,
    hass: HomeAssistant,
) -> None:
    """Test that entries from version 1.0 are migrate to latest version."""

    inject_bluetooth_service_info_bleak(hass, bt_discovery)

    cfg: MockConfigEntry = mock_config_v1_0(bms=bms_fixture)
    cfg.add_to_hass(hass)

    monkeypatch.setattr(
        f"aiobmsble.bms.{str(cfg.data["type"]).rsplit(".",1)[-1]}.BMS.async_update",
        mock_update_min,
    )

    assert await hass.config_entries.async_setup(cfg.entry_id)
    await hass.async_block_till_done()

    assert cfg in hass.config_entries.async_entries()
    assert cfg.version == 2
    assert cfg.minor_version == 0
    assert cfg.state is ConfigEntryState.LOADED


@pytest.mark.usefixtures("enable_bluetooth", "patch_default_bleak_client")
async def test_migrate_entry_from_v0_1(
    monkeypatch: pytest.MonkeyPatch,
    mock_config_v0_1: MockConfigEntry,
    bt_discovery: BluetoothServiceInfoBleak,
    hass: HomeAssistant,
) -> None:
    """Test migrating entries from version 0.1."""

    inject_bluetooth_service_info_bleak(hass, bt_discovery)

    cfg: MockConfigEntry = mock_config_v0_1
    cfg.add_to_hass(hass)

    monkeypatch.setattr(
        f"aiobmsble.bms.{(cfg.data["type"][:-3]).lower()}_bms.BMS.async_update",
        mock_update_min,
    )

    assert await hass.config_entries.async_setup(cfg.entry_id)
    await hass.async_block_till_done()

    assert cfg in hass.config_entries.async_entries()
    assert cfg.version == 2
    assert cfg.minor_version == 0
    assert cfg.state is ConfigEntryState.LOADED


async def test_migrate_unique_id(hass: HomeAssistant) -> None:
    """Verify that old style unique_ids are correctly migrated to new style."""
    cfg: MockConfigEntry = mock_config("jikong_bms")
    cfg.add_to_hass(hass)
    await hass.async_block_till_done()

    assert cfg in hass.config_entries.async_entries()
    config_entry = hass.config_entries.async_entries(domain=DOMAIN)[0]

    ent_reg: er.EntityRegistry = er.async_get(hass)
    # add entry with old unique_id style to be modified
    entry_old: Final[er.RegistryEntry] = ent_reg.async_get_or_create(
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
    entry_new: Final[er.RegistryEntry] = ent_reg.async_get_or_create(
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
    modified_entry: Final[er.RegistryEntry | None] = ent_reg.async_get(
        entry_old.entity_id
    )
    assert (modified_entry) is not None
    assert modified_entry.unique_id == f"{DOMAIN}-cc:cc:cc:cc:cc:cc-battery_level"

    # check that "new style" entry is not modified
    unmodified_entry: Final[er.RegistryEntry | None] = ent_reg.async_get(
        entry_new.entity_id
    )
    assert (unmodified_entry) is not None
    assert unmodified_entry.unique_id == f"{DOMAIN}-myJBD-test-battery_level"
