import pytest

from zha_quirk_builder.generator import generate_quirk
from zha_quirk_builder.model import ENTITY_KINDS, AttributeSpec, QuirkProject, efekta_sample
from zha_quirk_builder.validator import validate_import


def test_efekta_quirk_imports_with_installed_upstream_stack() -> None:
    issues = validate_import(efekta_sample())

    assert issues
    assert issues[-1].severity == "success", issues
    assert "zigpy" in issues[-1].message
    assert "ZHA" in issues[-1].message
    assert "zha-quirks" in issues[-1].message


def test_standard_reporting_override_imports_with_upstream_stack() -> None:
    project = QuirkProject(
        manufacturer="Example",
        model="Temperature",
        attributes=[
            AttributeSpec(
                name="measured_value",
                cluster_id=0x0402,
                attribute_id=0,
                data_type="int16",
                define_attribute=False,
                manufacturer_specific=False,
                replace_default_entity=True,
                entity_kind="sensor",
                device_class="temperature",
                divisor=100,
                reporting_min_interval=30,
                reporting_max_interval=300,
                reporting_change=25,
            )
        ],
    )

    issues = validate_import(project)

    assert issues[-1].severity == "success", issues


@pytest.mark.parametrize("entity_kind", ENTITY_KINDS)
def test_automatic_translation_key_imports_with_upstream_stack(entity_kind: str) -> None:
    project = QuirkProject(
        manufacturer="Example",
        model="AutomaticTranslationKey",
        attributes=[
            AttributeSpec(
                name="custom_value",
                cluster_id=0xFC00,
                attribute_id=0x0001,
                data_type="uint8",
                entity_kind=entity_kind,
                min_value=0,
                max_value=100,
                enum_values={"OFF": 0, "ON": 1},
            )
        ],
    )

    issues = validate_import(project)

    assert issues[-1].severity == "success", issues


def test_digibaro_enum_translation_keys_are_generated_and_import_with_upstream_stack() -> None:
    project = QuirkProject(
        manufacturer="EfektaLab",
        model="EFEKTA_DigiBaro",
        attributes=[
            AttributeSpec(
                name="basic_data",
                cluster_id=0x0001,
                attribute_id=0xF005,
                data_type="uint8",
                access="r",
                manufacturer_specific=False,
                entity_kind="enum",
                enum_class="BasicDataEnum",
                enum_values={"Barometer": 0, "TH": 1},
            ),
            AttributeSpec(
                name="invert_color",
                cluster_id=0x0001,
                attribute_id=0xF004,
                data_type="int8",
                access="r",
                manufacturer_specific=False,
                entity_kind="enum",
                enum_class="InvertEnum",
                enum_values={"BW": 0, "WB": 1},
            ),
        ],
    )

    source = generate_quirk(project)

    assert "translation_key='basic_data'" in source
    assert "translation_key='invert_color'" in source
    assert "from zhaquirks.clusters import CustomCluster" in source
    assert "access='r'" in source
    assert ".skip_configuration(" not in source
    issues = validate_import(project)
    assert issues[-1].severity == "success", issues


def test_enum_entity_imports_with_upstream_stack() -> None:
    project = QuirkProject(
        manufacturer="EFEKTA",
        model="TH_DUO_LR",
        attributes=[
            AttributeSpec(
                name="tx_radio_power",
                cluster_id=0x0001,
                attribute_id=0xFF01,
                data_type="int8",
                entity_kind="enum",
                enum_class="TxRadioPowerEnum",
                enum_values={"MINUS_20_DBM": -20, "PLUS_4_DBM": 4},
                translation_key="tx_radio_power",
                fallback_name="Set TX Radio Power",
            )
        ],
    )

    issues = validate_import(project)

    assert issues[-1].severity == "success", issues
