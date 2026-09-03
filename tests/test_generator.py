import ast

from zha_quirk_builder.generator import generate_quirk, python_identifier
from zha_quirk_builder.model import AttributeSpec, QuirkProject, efekta_sample
from zha_quirk_builder.validator import validate_project


def test_efekta_sample_generates_valid_quirk_v2_python() -> None:
    source = generate_quirk(efekta_sample())

    ast.parse(source)
    assert "QuirkBuilder('EFEKTA', 'EFEKTA_iAQ3')" in source
    assert ".replaces(EfektaIaq3Cluster040DEndpoint1, endpoint_id=1)" in source
    assert "report_delay = ZCLAttributeDef(id=0x0201" in source
    assert ".number(" in source
    assert ".switch(" in source
    assert "multiplier=0.1" in source
    assert "from zhaquirks.builder import QuirkBuilder" in source
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
    assert ".prevent_default_entity_creation(endpoint_id=1, cluster_id=0x0402)" in source
    assert "min_interval=30" in source
    assert "max_interval=300" in source
    assert "reportable_change=25" in source
