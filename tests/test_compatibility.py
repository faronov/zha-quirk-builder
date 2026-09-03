from zha_quirk_builder.model import AttributeSpec, QuirkProject, efekta_sample
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
