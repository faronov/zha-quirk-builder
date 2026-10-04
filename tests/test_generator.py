import ast

from zha_quirk_builder.generator import generate_quirk, python_identifier
from zha_quirk_builder.model import AttributeSpec, QuirkProject, efekta_sample
from zha_quirk_builder.validator import validate_project


def test_efekta_sample_generates_valid_quirk_v2_python() -> None:
    source = generate_quirk(efekta_sample())

    ast.parse(source)
    assert "QuirkBuilder('EFEKTA', 'EFEKTA_iAQ3')" in source
    assert (
        "class EfektaIaq3Cluster040DEndpoint1("
        "CustomCluster, CarbonDioxideConcentration):" in source
    )
    assert "class AttributeDefs(CarbonDioxideConcentration.AttributeDefs):" in source
    assert ".replaces(EfektaIaq3Cluster040DEndpoint1, endpoint_id=1)" in source
    assert "report_delay = ZCLAttributeDef(id=0x0201" in source
    assert ".number(" in source
    assert ".switch(" in source
    assert "multiplier=0.1" in source
    assert "from zhaquirks.builder import QuirkBuilder" in source
    assert (
        ".prevent_default_entity_creation(endpoint_id=1, cluster_id=0x0402, "
        "unique_id_suffix='1-1026')" in source
    )
    assert "unique_id_suffix='temperature'" in source
    assert "unique_id_suffix='humidity'" in source
    assert "unique_id_suffix='battery'" in source
    assert "reportable_change=25" in source
    assert "reportable_change=50" in source
    assert "max_interval=21600" in source
    assert source.rstrip().endswith(".add_to_registry()\n)")


def test_efekta_sample_passes_structural_validation() -> None:
    assert validate_project(efekta_sample()) == []


def test_python_identifier_normalizes_unsafe_names() -> None:
    assert python_identifier("Report delay") == "report_delay"
    assert python_identifier("123 value") == "attr_123_value"
    assert python_identifier("class") == "class_value"


def test_standard_cluster_reporting_override() -> None:
    project = QuirkProject(
        manufacturer="Example",
        model="Temperature",
        attributes=[
            AttributeSpec(
                name="measured_value",
                cluster_id=0x0402,
                attribute_id=0x0000,
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

    source = generate_quirk(project)

    ast.parse(source)
    assert "class TemperatureCluster" not in source
    assert "from zhaquirks.builder import QuirkBuilder, ReportingConfig" in source
    assert (
        ".prevent_default_entity_creation(endpoint_id=1, cluster_id=0x0402, "
        "unique_id_suffix='1-1026')" in source
    )
    assert "min_interval=30" in source
    assert "max_interval=300" in source
    assert "reportable_change=25" in source


def test_enum_entity_generates_enum_class_and_builder_call() -> None:
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

    source = generate_quirk(project)

    ast.parse(source)
    assert "from enum import IntEnum" in source
    assert "class TxRadioPowerEnum(IntEnum):" in source
    assert "type=t.int8s" in source
    assert ".enum(" in source
    assert "'tx_radio_power',\n            TxRadioPowerEnum," in source
    assert validate_project(project) == []


def test_sensor_rounding_applies_after_scaling() -> None:
    project = QuirkProject(
        manufacturer="EfektaLab",
        model="EFEKTA_T1_v2_LR",
        attributes=[
            AttributeSpec(
                name="uptime",
                cluster_id=0x000A,
                attribute_id=0x0006,
                data_type="uint32",
                entity_kind="sensor",
                translation_key="uptime",
                unit="h",
                divisor=3600,
                round_digits=0,
            )
        ],
    )

    source = generate_quirk(project)

    assert "attribute_converter=lambda value: round((value) / 3600, 0)" in source
    assert "divisor=3600" not in source


def test_output_cluster_generates_client_cluster_type() -> None:
    project = QuirkProject(
        manufacturer="Example",
        model="ClientCluster",
        attributes=[
            AttributeSpec(
                name="on_off",
                cluster_id=0x0006,
                attribute_id=0x0000,
                data_type="bool",
                endpoint_id=2,
                cluster_type="client",
                define_attribute=False,
                manufacturer_specific=False,
                entity_kind="binary_sensor",
                translation_key="remote_on_off",
                fallback_name="Opening",
                device_class="opening",
            )
        ],
    )

    source = generate_quirk(project)

    ast.parse(source)
    assert "from zigpy.zcl import ClusterType" in source
    assert (
        ".replaces(OnOff, endpoint_id=2, cluster_type=ClusterType.Client)" in source
    )
    assert ".binary_sensor(" in source
    assert "cluster_type=ClusterType.Client" in source
    assert "fallback_name='Opening'" in source
    assert "device_class='opening'" in source
    assert validate_project(project) == []


def test_old_project_json_defaults_to_input_cluster() -> None:
    attribute = AttributeSpec.from_dict(
        {
            "name": "measured_value",
            "cluster_id": 0x0402,
            "attribute_id": 0,
            "data_type": "int16",
        }
    )

    assert attribute.cluster_type == "server"


def test_custom_attributes_preserve_standard_cluster_attributes() -> None:
    project = QuirkProject(
        manufacturer="EfektaLab",
        model="EFEKTA_TH_Max",
        attributes=[
            AttributeSpec(
                name="air_enthalpy",
                cluster_id=0x0402,
                attribute_id=0x0204,
                data_type="int16",
                entity_kind="sensor",
                translation_key="air_enthalpy",
                fallback_name="Air enthalpy",
                divisor=100,
            )
        ],
    )

    source = generate_quirk(project)
    namespace = {"__name__": "generated_quirk", "__file__": "<generated-quirk>"}
    exec(compile(source, "<generated-quirk>", "exec"), namespace)  # noqa: S102
    cluster = namespace["EfektaThMaxCluster0402Endpoint1"]

    assert "measured_value" in cluster.attributes_by_name
    assert "air_enthalpy" in cluster.attributes_by_name


def test_undefined_custom_attribute_is_rejected() -> None:
    project = QuirkProject(
        manufacturer="EfektaLab",
        model="EFEKTA_TH_Max",
        attributes=[
            AttributeSpec(
                name="air_enthalpy",
                cluster_id=0x0402,
                attribute_id=0x0204,
                data_type="int16",
                define_attribute=False,
                entity_kind="sensor",
                translation_key="air_enthalpy",
            )
        ],
    )

    issues = validate_project(project)

    assert any("must be defined in a CustomCluster" in issue.message for issue in issues)
