from zha_quirk_builder.model import efekta_sample
from zha_quirk_builder.validator import validate_import


def test_efekta_quirk_imports_with_installed_upstream_stack() -> None:
    issues = validate_import(efekta_sample())

    assert issues
    assert issues[-1].severity == "success", issues
    assert "zigpy" in issues[-1].message
    assert "ZHA" in issues[-1].message
    assert "zha-quirks" in issues[-1].message
