from dataclasses import replace

import pytest

from zha_quirk_builder.generator import class_identifier, generate_quirk
from zha_quirk_builder.model import AttributeSpec, QuirkProject
from zha_quirk_builder.validator import validate_project


def project_with(**changes: object) -> QuirkProject:
    attribute = AttributeSpec(
        name="custom_value",
        cluster_id=0xFC00,
        attribute_id=1,
        data_type="uint8",
        entity_kind="number",
        min_value=0,
        max_value=100,
        step=1,
    )
    return QuirkProject(
        manufacturer="Review", model="Validation", attributes=[replace(attribute, **changes)]
    )


@pytest.mark.parametrize(
    ("changes", "message"),
    [
        ({"divisor": 0}, "divisor must not be zero"),
        ({"multiplier": 0}, "Number multiplier must not be zero"),
        ({"multiplier": 0, "divisor": 10}, "Number multiplier must not be zero"),
        ({"step": 0}, "Number step must be positive"),
        ({"step": -0.1}, "Number step must be positive"),
        ({"min_value": float("nan")}, "min_value must be finite"),
        ({"max_value": float("inf")}, "max_value must be finite"),
        ({"step": float("-inf")}, "step must be finite"),
        ({"manufacturer_code": -1}, "invalid manufacturer code"),
        ({"manufacturer_code": 0x10000}, "invalid manufacturer code"),
        ({"cluster_id": "0xFC00"}, "must be an integer"),
        ({"enum_values": {"ON": "1"}}, "mapping names to integers"),
        ({"entity_kind": "sensor", "divisor": 0}, "divisor must not be zero"),
        ({"entity_kind": "sensor", "divisor": 0, "round_digits": 1}, "divisor must not be zero"),
        ({"data_type": "string"}, "Number requires a numeric datatype"),
        ({"divisor": 10**1000}, "Number multiplier must not be zero"),
        ({"multiplier": 10**1000, "divisor": 1}, "Number scaling is outside"),
    ],
)
def test_invalid_numeric_and_project_data_are_rejected(
    changes: dict[str, object], message: str
) -> None:
    issues = validate_project(project_with(**changes))

    assert any(issue.severity == "error" and message in issue.message for issue in issues)


def test_zero_number_multiplier_is_not_replaced_with_one() -> None:
    source = generate_quirk(project_with(multiplier=0, divisor=10))

    assert "multiplier=0.0" in source
    assert "multiplier=0.1" not in source


def test_zero_sensor_multiplier_is_valid_and_preserved() -> None:
    project = project_with(entity_kind="sensor", multiplier=0, divisor=10)

    assert validate_project(project) == []
    assert "multiplier=0" in generate_quirk(project)


@pytest.mark.parametrize(
    ("entity_kind", "device_class"),
    [("sensor", "opening"), ("number", "enum"), ("binary_sensor", "temperature")],
)
def test_device_class_is_validated_for_its_platform(entity_kind: str, device_class: str) -> None:
    issues = validate_project(project_with(entity_kind=entity_kind, device_class=device_class))

    assert any(f"invalid {entity_kind} device_class" in issue.message for issue in issues)


def test_invalid_sensor_state_class_is_rejected() -> None:
    issues = validate_project(project_with(entity_kind="sensor", state_class="wrong"))

    assert any("invalid sensor state_class" in issue.message for issue in issues)


def test_standard_attribute_id_must_match_name() -> None:
    project = project_with(
        name="measured_value",
        cluster_id=0x0402,
        attribute_id=123,
        data_type="int16",
        define_attribute=False,
        entity_kind="sensor",
        device_class="temperature",
    )

    issues = validate_project(project)

    assert any("standard attribute ID 0x0000" in issue.message for issue in issues)


@pytest.mark.parametrize(
    "enum_class",
    [
        "t",
        "IntEnum",
        "QuirkBuilder",
        "CustomCluster",
        "BaseAttributeDefs",
        "ZCLAttributeDef",
        "ReportingConfig",
        "ClusterType",
        "round",
        "PowerConfiguration",
    ],
)
def test_enum_cannot_shadow_imports_and_converter_names(enum_class: str) -> None:
    issues = validate_project(
        project_with(
            cluster_id=0x0001, entity_kind="enum", enum_class=enum_class, enum_values={"ON": 1}
        )
    )

    assert any("conflicts with a generated class" in issue.message for issue in issues)


def test_enum_cannot_shadow_generated_cluster_class() -> None:
    project = project_with(entity_kind="enum", enum_values={"ON": 1})
    project.attributes[0].enum_class = class_identifier(project, 0xFC00, 1)

    issues = validate_project(project)

    assert any("conflicts with a generated class" in issue.message for issue in issues)


@pytest.mark.parametrize("changes", [{"data_type": "float"}, {"data_type": "int16", "divisor": 10}])
def test_fractional_number_write_limitations_are_warnings(changes: dict[str, object]) -> None:
    project = project_with(**changes)
    issues = validate_project(project)

    assert not any(issue.severity == "error" for issue in issues)
    assert any(
        issue.severity == "warning" and "fractional Number writes" in issue.message
        for issue in issues
    )
    assert f"type={'t.Single' if project.attributes[0].data_type == 'float' else 't.int16s'}" in (
        generate_quirk(project)
    )


@pytest.mark.parametrize(
    "payload",
    [
        [],
        {"manufacturer": 123, "model": "Example"},
        {"manufacturer": "Review", "model": "Example", "attributes": "wrong"},
        {"manufacturer": "Review", "model": "Example", "attributes": [None]},
        {
            "manufacturer": "Review",
            "model": "Example",
            "attributes": [
                {
                    "name": "custom_value",
                    "cluster_id": "0xFC00",
                    "attribute_id": 1,
                    "data_type": "uint8",
                }
            ],
        },
    ],
)
def test_malformed_json_types_are_rejected(payload: object) -> None:
    with pytest.raises((TypeError, ValueError)):
        QuirkProject.from_dict(payload)


def test_project_json_roundtrip_preserves_types_and_missing_optional_defaults() -> None:
    project = project_with()

    assert QuirkProject.from_dict(project.to_dict()) == project
    old_project = QuirkProject.from_dict(
        {
            "manufacturer": "Review",
            "model": "Old",
            "attributes": [
                {
                    "name": "custom_value",
                    "cluster_id": 0xFC00,
                    "attribute_id": 1,
                    "data_type": "uint8",
                }
            ],
        }
    )
    assert old_project.attributes[0].cluster_type == "server"
