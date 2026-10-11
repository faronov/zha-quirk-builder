import json
from pathlib import Path
from unittest.mock import Mock

import pytest

from zha_quirk_builder.app import AttributeDialog, MainWindow
from zha_quirk_builder.model import AttributeSpec, QuirkProject
from zha_quirk_builder.profiles import LATEST_PROFILE
from zha_quirk_builder.validator import ValidationIssue


@pytest.fixture
def window(qtbot) -> MainWindow:
    widget = MainWindow()
    qtbot.addWidget(widget)
    return widget


def test_invalid_preview_is_cleared_instead_of_crashing(window: MainWindow) -> None:
    project = QuirkProject(
        manufacturer="Review",
        model="Invalid",
        attributes=[
            AttributeSpec(
                name="custom_value",
                cluster_id=0xFC00,
                attribute_id=1,
                data_type="unknown",
            )
        ],
    )

    window._load_project(project)

    assert window.code.toPlainText() == ""
    assert "unsupported zigpy datatype" in window.result.text()


def test_changing_entity_kind_does_not_keep_disabled_rounding(window: MainWindow, qtbot) -> None:
    attribute = AttributeSpec(
        name="custom_value",
        cluster_id=0xFC00,
        attribute_id=1,
        data_type="uint8",
        entity_kind="sensor",
        round_digits=1,
    )
    dialog = AttributeDialog(window, attribute)
    qtbot.addWidget(dialog)

    dialog.entity_kind.setCurrentText("number")

    assert not dialog.round_digits.isEnabled()
    assert dialog.value().round_digits is None
    dialog.entity_kind.setCurrentText("sensor")
    assert dialog.value().round_digits == 1


def test_enum_export_validates_selected_profile_and_generates_keys(
    window: MainWindow, qtbot, tmp_path: Path, monkeypatch
) -> None:
    project = QuirkProject(
        manufacturer="EfektaLab",
        model="EFEKTA_DigiBaro",
        attributes=[
            AttributeSpec(
                name="basic_data",
                cluster_id=1,
                attribute_id=0xF005,
                data_type="uint8",
                entity_kind="enum",
                enum_values={"Barometer": 0, "TH": 1},
            ),
            AttributeSpec(
                name="invert_color",
                cluster_id=1,
                attribute_id=0xF004,
                data_type="int8",
                entity_kind="enum",
                enum_values={"BW": 0, "WB": 1},
            ),
        ],
    )
    window._load_project(project)
    window.profile.setCurrentIndex(1)
    validator = Mock(return_value=[ValidationIssue("success", "Imported")])
    monkeypatch.setattr("zha_quirk_builder.app.validate_with_profile", validator)
    output = tmp_path / "digibaro.py"
    monkeypatch.setattr(
        "zha_quirk_builder.app.QFileDialog.getSaveFileName", lambda *args: (str(output), "")
    )

    window._export_python()

    validator.assert_called_once_with(project, LATEST_PROFILE)
    source = output.read_text()
    assert "translation_key='basic_data'" in source
    assert "translation_key='invert_color'" in source
    assert ".skip_configuration(" not in source
    dialog = AttributeDialog(window, project.attributes[0])
    qtbot.addWidget(dialog)
    assert "Automatic" in dialog.translation_key.placeholderText()


def test_import_failure_blocks_export(window: MainWindow, monkeypatch) -> None:
    monkeypatch.setattr(
        "zha_quirk_builder.app.validate_with_profile",
        lambda *args: [ValidationIssue("error", "Upstream import failed")],
    )
    warning = Mock()
    chooser = Mock()
    monkeypatch.setattr("zha_quirk_builder.app.QMessageBox.warning", warning)
    monkeypatch.setattr("zha_quirk_builder.app.QFileDialog.getSaveFileName", chooser)

    window._export_python()

    warning.assert_called_once()
    chooser.assert_not_called()
    assert "Upstream import failed" in window.result.text()


def test_warnings_allow_export_and_remain_visible(
    window: MainWindow, tmp_path: Path, monkeypatch
) -> None:
    monkeypatch.setattr(
        "zha_quirk_builder.app.validate_with_profile",
        lambda *args: [
            ValidationIssue("warning", "Fractional writes"),
            ValidationIssue("success", "OK"),
        ],
    )
    output = tmp_path / "warning.py"
    monkeypatch.setattr(
        "zha_quirk_builder.app.QFileDialog.getSaveFileName", lambda *args: (str(output), "")
    )

    window._export_python()

    assert output.is_file()
    assert "EXPORTED" in window.result.text()
    assert "WARNING · Fractional writes" in window.result.text()


@pytest.mark.parametrize(
    "bad_attribute",
    [
        {"name": "custom_value", "cluster_id": "0xFC00", "attribute_id": 1, "data_type": "uint8"},
        {"name": "custom_value", "cluster_id": 0xFC00, "attribute_id": 1, "data_type": "unknown"},
    ],
)
def test_invalid_import_keeps_current_project(
    window: MainWindow, tmp_path: Path, monkeypatch, bad_attribute: dict[str, object]
) -> None:
    original = window.project
    source = tmp_path / "invalid.json"
    source.write_text(
        json.dumps(
            {
                "manufacturer": "Review",
                "model": "Invalid",
                "attributes": [bad_attribute],
            }
        )
    )
    monkeypatch.setattr(
        "zha_quirk_builder.app.QFileDialog.getOpenFileName", lambda *args: (str(source), "")
    )
    error = Mock()
    monkeypatch.setattr("zha_quirk_builder.app.QMessageBox.critical", error)

    window._import_project()

    error.assert_called_once()
    assert window.project is original
