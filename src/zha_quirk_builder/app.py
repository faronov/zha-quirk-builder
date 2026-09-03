from __future__ import annotations

import json
import sys
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QFontDatabase
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPlainTextEdit,
    QProgressDialog,
    QPushButton,
    QSpinBox,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from zha_quirk_builder.generator import generate_quirk, python_identifier
from zha_quirk_builder.model import (
    ENTITY_KINDS,
    ZIGPY_TYPES,
    AttributeSpec,
    QuirkProject,
    efekta_sample,
)
from zha_quirk_builder.profiles import (
    BUNDLED_PROFILE,
    LATEST_PROFILE,
    CompatibilityProfile,
    validate_with_profile,
)
from zha_quirk_builder.validator import installed_profile, validate_import, validate_project

STYLE = """
QWidget {
    background: #f3f1ea;
    color: #20302a;
    font-family: "Avenir Next", "Segoe UI";
    font-size: 13px;
}
QMainWindow { background: #ebe8df; }
QFrame#panel {
    background: #fffdf8;
    border: 1px solid #d9ddd5;
    border-radius: 14px;
}
QLabel#eyebrow {
    color: #39715f;
    font-size: 11px;
    font-weight: 800;
    letter-spacing: 2px;
}
QLabel#title {
    color: #17241f;
    font-size: 28px;
    font-weight: 700;
}
QLabel#muted { color: #68766f; }
QComboBox#profile {
    color: #285847;
    background: #e8f1eb;
    border: 1px solid #c9ddd0;
    border-radius: 10px;
    padding: 8px 12px;
}
QLineEdit, QComboBox, QSpinBox, QPlainTextEdit, QTableWidget {
    color: #20302a;
    background: #f9faf6;
    border: 1px solid #ccd3cc;
    border-radius: 7px;
    padding: 7px;
    selection-background-color: #39715f;
    selection-color: #ffffff;
}
QLineEdit:focus, QComboBox:focus, QSpinBox:focus, QPlainTextEdit:focus {
    border-color: #39715f;
}
QLineEdit:disabled, QComboBox:disabled, QSpinBox:disabled {
    color: #929b95;
    background: #eff0eb;
}
QPlainTextEdit {
    color: #24342d;
    background: #f5f7f2;
    border-color: #c7d0c8;
}
QTableWidget {
    alternate-background-color: #f3f5f0;
    gridline-color: #e1e5df;
    padding: 0;
}
QTableWidget::item:selected {
    color: #183328;
    background: #dcebe1;
}
QHeaderView::section {
    color: #50645a;
    background: #edf1eb;
    border: 0;
    border-bottom: 1px solid #d5dbd4;
    padding: 8px;
    font-weight: 700;
}
QPushButton {
    color: #30473d;
    background: #f5f6f1;
    border: 1px solid #cbd3cc;
    border-radius: 8px;
    padding: 9px 14px;
    font-weight: 700;
}
QPushButton:hover {
    color: #204f3e;
    border-color: #7da491;
    background: #eef5ef;
}
QPushButton:pressed { background: #dfeae2; }
QPushButton#primary {
    color: #ffffff;
    background: #39715f;
    border-color: #39715f;
}
QPushButton#primary:hover {
    background: #2f624f;
    border-color: #2f624f;
}
QPushButton#danger {
    color: #a54b42;
    background: #fff7f4;
    border-color: #e7c7c1;
}
QDialog { background: #f3f1ea; }
QCheckBox { spacing: 8px; }
QSplitter::handle { background: #d6dbd5; width: 2px; }
"""


def parse_int(value: str) -> int:
    return int(value.strip(), 0)


def parse_optional_int(value: str) -> int | None:
    return parse_int(value) if value.strip() else None


def parse_optional_float(value: str) -> float | None:
    return float(value.strip()) if value.strip() else None


class AttributeDialog(QDialog):
    def __init__(self, parent: QWidget, attribute: AttributeSpec | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Attribute mapping")
        self.setMinimumWidth(520)
        source = attribute or AttributeSpec(
            name="custom_value",
            cluster_id=0xFC00,
            attribute_id=0x0001,
            data_type="uint16",
            fallback_name="Custom value",
            translation_key="custom_value",
            min_value=0,
            max_value=100,
            step=1,
        )

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        heading = QLabel("MAP ZIGBEE ATTRIBUTE")
        heading.setObjectName("eyebrow")
        layout.addWidget(heading)
        form = QFormLayout()
        form.setVerticalSpacing(11)
        layout.addLayout(form)

        self.name = QLineEdit(source.name)
        self.cluster_id = QLineEdit(f"0x{source.cluster_id:04X}")
        self.attribute_id = QLineEdit(f"0x{source.attribute_id:04X}")
        self.endpoint_id = QSpinBox()
        self.endpoint_id.setRange(1, 240)
        self.endpoint_id.setValue(source.endpoint_id)
        self.data_type = QComboBox()
        self.data_type.addItems(ZIGPY_TYPES)
        self.data_type.setCurrentText(source.data_type)
        self.access = QComboBox()
        self.access.addItems(("r", "rw", "rp", "rwp", "w"))
        self.access.setCurrentText(source.access)
        self.manufacturer_specific = QCheckBox("Manufacturer-specific attribute")
        self.manufacturer_specific.setChecked(source.manufacturer_specific)
        self.define_attribute = QCheckBox("Define attribute in a CustomCluster")
        self.define_attribute.setChecked(source.define_attribute)
        self.replace_default_entity = QCheckBox("Replace ZHA default entity for this cluster")
        self.replace_default_entity.setChecked(source.replace_default_entity)
        self.manufacturer_code = QLineEdit(
            f"0x{source.manufacturer_code:04X}" if source.manufacturer_code is not None else ""
        )
        self.entity_kind = QComboBox()
        self.entity_kind.addItems(ENTITY_KINDS)
        self.entity_kind.setCurrentText(source.entity_kind)
        self.fallback_name = QLineEdit(source.fallback_name)
        self.translation_key = QLineEdit(source.translation_key)
        self.device_class = QLineEdit(source.device_class)
        self.unit = QLineEdit(source.unit)
        self.minimum = QLineEdit("" if source.min_value is None else str(source.min_value))
        self.maximum = QLineEdit("" if source.max_value is None else str(source.max_value))
        self.step = QLineEdit("" if source.step is None else str(source.step))
        self.divisor = QLineEdit("" if source.divisor is None else str(source.divisor))
        self.multiplier = QLineEdit("" if source.multiplier is None else str(source.multiplier))
        self.state_class = QComboBox()
        self.state_class.addItems(("", "measurement", "total", "total_increasing"))
        self.state_class.setCurrentText(source.state_class)
        self.reporting_min = QLineEdit(
            "" if source.reporting_min_interval is None else str(source.reporting_min_interval)
        )
        self.reporting_max = QLineEdit(
            "" if source.reporting_max_interval is None else str(source.reporting_max_interval)
        )
        self.reporting_change = QLineEdit(
            "" if source.reporting_change is None else str(source.reporting_change)
        )

        for label, widget in (
            ("Python attribute name", self.name),
            ("Cluster ID", self.cluster_id),
            ("Attribute ID", self.attribute_id),
            ("Endpoint", self.endpoint_id),
            ("zigpy datatype", self.data_type),
            ("Access", self.access),
            ("Flags", self.manufacturer_specific),
            ("Cluster definition", self.define_attribute),
            ("Default entity", self.replace_default_entity),
            ("Manufacturer code", self.manufacturer_code),
            ("Entity", self.entity_kind),
            ("Fallback name", self.fallback_name),
            ("Translation key", self.translation_key),
            ("Device class", self.device_class),
            ("Unit", self.unit),
            ("Minimum", self.minimum),
            ("Maximum", self.maximum),
            ("Step", self.step),
            ("Divisor", self.divisor),
            ("Multiplier", self.multiplier),
            ("State class", self.state_class),
            ("Reporting min (seconds)", self.reporting_min),
            ("Reporting max (seconds)", self.reporting_max),
            ("Reporting change (raw ZCL)", self.reporting_change),
        ):
            form.addRow(label, widget)

        buttons = QDialogButtonBox(QDialogButtonBox.Cancel | QDialogButtonBox.Save)
        buttons.rejected.connect(self.reject)
        buttons.accepted.connect(self._accept_if_valid)
        layout.addWidget(buttons)

    def _accept_if_valid(self) -> None:
        try:
            self.value()
        except ValueError as error:
            QMessageBox.warning(self, "Invalid attribute", str(error))
            return
        self.accept()

    def value(self) -> AttributeSpec:
        name = self.name.text().strip()
        if name != python_identifier(name):
            raise ValueError("Attribute name must be a snake_case Python identifier.")
        return AttributeSpec(
            name=name,
            cluster_id=parse_int(self.cluster_id.text()),
            attribute_id=parse_int(self.attribute_id.text()),
            endpoint_id=self.endpoint_id.value(),
            data_type=self.data_type.currentText(),
            access=self.access.currentText(),
            manufacturer_specific=self.manufacturer_specific.isChecked(),
            manufacturer_code=parse_optional_int(self.manufacturer_code.text()),
            define_attribute=self.define_attribute.isChecked(),
            replace_default_entity=self.replace_default_entity.isChecked(),
            entity_kind=self.entity_kind.currentText(),
            fallback_name=self.fallback_name.text().strip(),
            translation_key=self.translation_key.text().strip(),
            device_class=self.device_class.text().strip(),
            unit=self.unit.text().strip(),
            min_value=parse_optional_float(self.minimum.text()),
            max_value=parse_optional_float(self.maximum.text()),
            step=parse_optional_float(self.step.text()),
            divisor=parse_optional_int(self.divisor.text()),
            multiplier=parse_optional_int(self.multiplier.text()),
            state_class=self.state_class.currentText(),
            reporting_min_interval=parse_optional_int(self.reporting_min.text()),
            reporting_max_interval=parse_optional_int(self.reporting_max.text()),
            reporting_change=parse_optional_int(self.reporting_change.text()),
        )


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.project = efekta_sample()
        self.setWindowTitle("ZHA Quirk Builder")
        self.resize(1480, 900)

        splitter = QSplitter()
        splitter.addWidget(self._build_editor())
        splitter.addWidget(self._build_preview())
        splitter.setSizes([680, 800])
        self.setCentralWidget(splitter)
        self._load_project(self.project)

    def _panel(self) -> tuple[QFrame, QVBoxLayout]:
        frame = QFrame()
        frame.setObjectName("panel")
        layout = QVBoxLayout(frame)
        layout.setContentsMargins(22, 22, 22, 22)
        layout.setSpacing(14)
        return frame, layout

    def _build_editor(self) -> QWidget:
        container = QWidget()
        outer = QVBoxLayout(container)
        outer.setContentsMargins(18, 18, 9, 18)

        panel, layout = self._panel()
        outer.addWidget(panel)
        eyebrow = QLabel("STANDALONE · QUIRKBUILDER V2")
        eyebrow.setObjectName("eyebrow")
        title = QLabel("Device definition")
        title.setObjectName("title")
        subtitle = QLabel(
            "Describe what the device reports. No coordinator or hub connection is used."
        )
        subtitle.setObjectName("muted")
        subtitle.setWordWrap(True)
        layout.addWidget(eyebrow)
        layout.addWidget(title)
        layout.addWidget(subtitle)

        form = QFormLayout()
        self.manufacturer = QLineEdit()
        self.model = QLineEdit()
        self.friendly_manufacturer = QLineEdit()
        self.friendly_model = QLineEdit()
        form.addRow("Basic manufacturer", self.manufacturer)
        form.addRow("Basic model", self.model)
        form.addRow("Display manufacturer", self.friendly_manufacturer)
        form.addRow("Display model", self.friendly_model)
        layout.addLayout(form)

        sample_row = QHBoxLayout()
        load_sample = QPushButton("Load EFEKTA sample")
        load_sample.clicked.connect(lambda: self._load_project(efekta_sample()))
        import_button = QPushButton("Import project JSON")
        import_button.clicked.connect(self._import_project)
        sample_row.addWidget(load_sample)
        sample_row.addWidget(import_button)
        layout.addLayout(sample_row)

        mapping_label = QLabel("ATTRIBUTE MAPPINGS")
        mapping_label.setObjectName("eyebrow")
        layout.addWidget(mapping_label)
        self.table = QTableWidget(0, 8)
        self.table.setHorizontalHeaderLabels(
            ("Name", "Endpoint", "Cluster", "Attribute", "Type", "Entity", "Reporting", "Label")
        )
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(7, QHeaderView.Stretch)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.table.setAlternatingRowColors(True)
        self.table.doubleClicked.connect(self._edit_attribute)
        layout.addWidget(self.table, 1)

        attribute_buttons = QHBoxLayout()
        add_button = QPushButton("+ Add mapping")
        add_button.setObjectName("primary")
        add_button.clicked.connect(self._add_attribute)
        edit_button = QPushButton("Edit")
        edit_button.clicked.connect(self._edit_attribute)
        remove_button = QPushButton("Remove")
        remove_button.setObjectName("danger")
        remove_button.clicked.connect(self._remove_attribute)
        attribute_buttons.addWidget(add_button)
        attribute_buttons.addWidget(edit_button)
        attribute_buttons.addWidget(remove_button)
        attribute_buttons.addStretch()
        layout.addLayout(attribute_buttons)
        return container

    def _build_preview(self) -> QWidget:
        container = QWidget()
        outer = QVBoxLayout(container)
        outer.setContentsMargins(9, 18, 18, 18)
        panel, layout = self._panel()
        outer.addWidget(panel)

        header = QHBoxLayout()
        heading = QVBoxLayout()
        eyebrow = QLabel("GENERATED ARTIFACT")
        eyebrow.setObjectName("eyebrow")
        title = QLabel("Python preview")
        title.setObjectName("title")
        heading.addWidget(eyebrow)
        heading.addWidget(title)
        self.profile = QComboBox()
        self.profile.setObjectName("profile")
        self.profile.addItem(BUNDLED_PROFILE.label, BUNDLED_PROFILE)
        self.profile.addItem(LATEST_PROFILE.label, LATEST_PROFILE)
        self.profile.addItem("Custom versions…", None)
        self.profile.currentIndexChanged.connect(self._profile_changed)
        header.addLayout(heading)
        header.addStretch()
        header.addWidget(self.profile)
        layout.addLayout(header)

        self.code = QPlainTextEdit()
        self.code.setReadOnly(True)
        fixed_font = QFontDatabase.systemFont(QFontDatabase.FixedFont)
        fixed_font.setPointSize(12)
        self.code.setFont(fixed_font)
        layout.addWidget(self.code, 1)

        self.result = QLabel("Generate a quirk to inspect its validation status.")
        self.result.setObjectName("muted")
        self.result.setWordWrap(True)
        layout.addWidget(self.result)

        actions = QHBoxLayout()
        generate_button = QPushButton("Generate")
        generate_button.clicked.connect(self._generate)
        validate_button = QPushButton("Validate against installed ZHA")
        validate_button.setObjectName("primary")
        validate_button.clicked.connect(self._validate)
        export_button = QPushButton("Export .py")
        export_button.clicked.connect(self._export_python)
        save_project_button = QPushButton("Save project")
        save_project_button.clicked.connect(self._save_project)
        for button in (generate_button, validate_button, export_button, save_project_button):
            actions.addWidget(button)
        layout.addLayout(actions)
        return container

    def _current_project(self) -> QuirkProject:
        return QuirkProject(
            manufacturer=self.manufacturer.text().strip(),
            model=self.model.text().strip(),
            friendly_manufacturer=self.friendly_manufacturer.text().strip(),
            friendly_model=self.friendly_model.text().strip(),
            attributes=list(self.project.attributes),
        )

    def _load_project(self, project: QuirkProject) -> None:
        self.project = project
        self.manufacturer.setText(project.manufacturer)
        self.model.setText(project.model)
        self.friendly_manufacturer.setText(project.friendly_manufacturer)
        self.friendly_model.setText(project.friendly_model)
        self._refresh_table()
        self._generate()

    def _refresh_table(self) -> None:
        self.table.setRowCount(len(self.project.attributes))
        for row, attribute in enumerate(self.project.attributes):
            values = (
                attribute.name,
                str(attribute.endpoint_id),
                f"0x{attribute.cluster_id:04X}",
                f"0x{attribute.attribute_id:04X}",
                attribute.data_type,
                attribute.entity_kind,
                (
                    f"{attribute.reporting_min_interval}/"
                    f"{attribute.reporting_max_interval}/"
                    f"{attribute.reporting_change}"
                    if attribute.reporting_min_interval is not None
                    else "ZHA default"
                ),
                attribute.fallback_name,
            )
            for column, value in enumerate(values):
                self.table.setItem(row, column, QTableWidgetItem(value))

    def _selected_row(self) -> int | None:
        rows = self.table.selectionModel().selectedRows()
        return rows[0].row() if rows else None

    def _add_attribute(self) -> None:
        dialog = AttributeDialog(self)
        if dialog.exec() == QDialog.Accepted:
            self.project.attributes.append(dialog.value())
            self._refresh_table()
            self._generate()

    def _edit_attribute(self) -> None:
        row = self._selected_row()
        if row is None:
            QMessageBox.information(self, "Edit mapping", "Select an attribute mapping first.")
            return
        dialog = AttributeDialog(self, self.project.attributes[row])
        if dialog.exec() == QDialog.Accepted:
            self.project.attributes[row] = dialog.value()
            self._refresh_table()
            self.table.selectRow(row)
            self._generate()

    def _remove_attribute(self) -> None:
        row = self._selected_row()
        if row is None:
            QMessageBox.information(self, "Remove mapping", "Select an attribute mapping first.")
            return
        del self.project.attributes[row]
        self._refresh_table()
        self._generate()

    def _generate(self) -> None:
        project = self._current_project()
        issues = validate_project(project)
        if issues:
            self.result.setText("\n".join(f"ERROR · {issue.message}" for issue in issues))
        else:
            self.result.setText("STRUCTURE OK · Ready for upstream import validation.")
        self.code.setPlainText(generate_quirk(project) if project.attributes else "")
        profile = installed_profile()
        self.profile.setItemText(
            0,
            "Bundled · "
            f"zigpy {profile['zigpy']} / ZHA {profile['zha']} / quirks {profile['zha-quirks']}",
        )

    def _validate(self) -> None:
        profile = self.profile.currentData()
        if not isinstance(profile, CompatibilityProfile):
            return
        progress = QProgressDialog(
            f"Preparing {profile.name} compatibility environment…",
            "",
            0,
            0,
            self,
        )
        progress.setWindowTitle("Validating quirk")
        progress.setCancelButton(None)
        progress.setWindowModality(Qt.WindowModal)
        progress.show()
        QApplication.processEvents()
        QApplication.setOverrideCursor(Qt.WaitCursor)
        try:
            issues = validate_with_profile(self._current_project(), profile)
        finally:
            QApplication.restoreOverrideCursor()
            progress.close()
        self.result.setText(
            "\n".join(f"{issue.severity.upper()} · {issue.message}" for issue in issues)
            or "VALID · No compatibility issues found."
        )

    def _profile_changed(self, index: int) -> None:
        if self.profile.itemData(index) is not None:
            return
        dialog = QDialog(self)
        dialog.setWindowTitle("Custom compatibility profile")
        layout = QFormLayout(dialog)
        zigpy = QLineEdit("2.1.0")
        zha = QLineEdit("2.2.1")
        quirks = QLineEdit("2.2.1")
        layout.addRow("zigpy version", zigpy)
        layout.addRow("ZHA version", zha)
        layout.addRow("zha-quirks version", quirks)
        buttons = QDialogButtonBox(QDialogButtonBox.Cancel | QDialogButtonBox.Save)
        buttons.rejected.connect(dialog.reject)
        buttons.accepted.connect(dialog.accept)
        layout.addRow(buttons)
        if dialog.exec() != QDialog.Accepted:
            self.profile.setCurrentIndex(0)
            return
        versions = (zigpy.text().strip(), zha.text().strip(), quirks.text().strip())
        if not all(versions):
            QMessageBox.warning(dialog, "Invalid profile", "All three versions are required.")
            self.profile.setCurrentIndex(0)
            return
        custom = CompatibilityProfile("Custom", *versions)
        custom_index = self.profile.count() - 1
        self.profile.insertItem(custom_index, custom.label, custom)
        self.profile.setCurrentIndex(custom_index)

    def _export_python(self) -> None:
        project = self._current_project()
        issues = validate_project(project)
        if issues:
            QMessageBox.warning(
                self,
                "Cannot export",
                "\n".join(issue.message for issue in issues),
            )
            return
        suggested = (
            f"{python_identifier(project.manufacturer)}_{python_identifier(project.model)}.py"
        )
        path, _ = QFileDialog.getSaveFileName(
            self, "Export ZHA quirk", suggested, "Python files (*.py)"
        )
        if not path:
            return
        try:
            Path(path).write_text(generate_quirk(project), encoding="utf-8")
        except OSError as error:
            QMessageBox.critical(self, "Export failed", str(error))
            return
        self.result.setText(f"EXPORTED · {path}")

    def _save_project(self) -> None:
        path, _ = QFileDialog.getSaveFileName(
            self, "Save builder project", "quirk-project.json", "JSON files (*.json)"
        )
        if not path:
            return
        try:
            Path(path).write_text(
                json.dumps(self._current_project().to_dict(), indent=2, ensure_ascii=False),
                encoding="utf-8",
            )
        except OSError as error:
            QMessageBox.critical(self, "Save failed", str(error))

    def _import_project(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, "Import builder project", "", "JSON files (*.json)"
        )
        if not path:
            return
        try:
            data = json.loads(Path(path).read_text(encoding="utf-8"))
            project = QuirkProject.from_dict(data)
        except (OSError, json.JSONDecodeError, TypeError, ValueError) as error:
            QMessageBox.critical(self, "Import failed", str(error))
            return
        self._load_project(project)


def main() -> int:
    if "--self-test" in sys.argv:
        issues = validate_import(efekta_sample())
        for issue in issues:
            print(f"{issue.severity.upper()} · {issue.message}")
        return 1 if any(issue.severity == "error" for issue in issues) else 0

    app = QApplication(sys.argv)
    app.setApplicationName("ZHA Quirk Builder")
    app.setStyleSheet(STYLE)
    window = MainWindow()
    window.show()
    return app.exec()
