import ast

from zha_quirk_builder.generator import generate_quirk, python_identifier
from zha_quirk_builder.model import efekta_sample
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
