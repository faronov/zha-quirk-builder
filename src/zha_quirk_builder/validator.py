from __future__ import annotations

import ast
import importlib.metadata
import keyword
import math
import multiprocessing
import sys
import traceback
from dataclasses import dataclass
from multiprocessing.connection import Connection

from zhaquirks.builder.metadata import (
    BinarySensorDeviceClass,
    NumberDeviceClass,
    SensorDeviceClass,
    SensorStateClass,
)

from zha_quirk_builder.generator import (
    entity_unique_id_suffix,
    enum_class_identifier,
    generate_quirk,
    number_multiplier,
    python_identifier,
    reserved_enum_names,
    standard_cluster_class,
)
from zha_quirk_builder.model import ENTITY_KINDS, ZIGPY_TYPES, QuirkProject

ENUM_DATA_TYPES = {
    "bitmap8": (0, 0xFF),
    "bitmap16": (0, 0xFFFF),
    "enum8": (0, 0xFF),
    "enum16": (0, 0xFFFF),
    "uint8": (0, 0xFF),
    "uint16": (0, 0xFFFF),
    "uint32": (0, 0xFFFFFFFF),
    "int8": (-0x80, 0x7F),
    "int16": (-0x8000, 0x7FFF),
    "int32": (-0x80000000, 0x7FFFFFFF),
}

DEVICE_CLASSES = {
    "sensor": SensorDeviceClass,
    "number": NumberDeviceClass,
    "binary_sensor": BinarySensorDeviceClass,
}


@dataclass(frozen=True, slots=True)
class ValidationIssue:
    severity: str
    message: str


def validate_project(project: QuirkProject) -> list[ValidationIssue]:
    issues: list[ValidationIssue] = []
    try:
        QuirkProject.from_dict(project.to_dict())
    except (TypeError, ValueError) as error:
        return [ValidationIssue("error", f"Invalid project data: {error}")]
    if not project.manufacturer.strip():
        issues.append(ValidationIssue("error", "Manufacturer is required."))
    if not project.model.strip():
        issues.append(ValidationIssue("error", "Model is required."))
    if not project.attributes:
        issues.append(ValidationIssue("error", "Add at least one attribute."))

    seen: set[tuple[int, int, str, int]] = set()
    names: set[tuple[int, int, str, str]] = set()
    enum_classes: dict[str, tuple[str, dict[str, int]]] = {}
    reserved_names = reserved_enum_names(project)
    entity_unique_ids: set[tuple[int, str]] = set()
    for index, attribute in enumerate(project.attributes, 1):
        prefix = f"Attribute {index}"
        if attribute.name != python_identifier(attribute.name):
            issues.append(
                ValidationIssue(
                    "error", f"{prefix}: name must be a valid snake_case Python identifier."
                )
            )
        key = (
            attribute.endpoint_id,
            attribute.cluster_id,
            attribute.cluster_type,
            attribute.attribute_id,
        )
        if key in seen:
            issues.append(ValidationIssue("error", f"{prefix}: duplicate endpoint/cluster/ID."))
        seen.add(key)
        name_key = (
            attribute.endpoint_id,
            attribute.cluster_id,
            attribute.cluster_type,
            attribute.name,
        )
        if name_key in names:
            issues.append(ValidationIssue("error", f"{prefix}: duplicate attribute name."))
        names.add(name_key)
        entity_unique_id = (attribute.endpoint_id, entity_unique_id_suffix(attribute))
        if entity_unique_id in entity_unique_ids:
            issues.append(
                ValidationIssue(
                    "error",
                    f"{prefix}: duplicate entity unique ID suffix "
                    f"{entity_unique_id_suffix(attribute)!r} on endpoint "
                    f"{attribute.endpoint_id}.",
                )
            )
        entity_unique_ids.add(entity_unique_id)
        if attribute.data_type not in ZIGPY_TYPES:
            issues.append(ValidationIssue("error", f"{prefix}: unsupported zigpy datatype."))
        if attribute.entity_kind not in ENTITY_KINDS:
            issues.append(ValidationIssue("error", f"{prefix}: unsupported entity kind."))
        if attribute.cluster_type not in {"server", "client"}:
            issues.append(ValidationIssue("error", f"{prefix}: unsupported cluster direction."))
        cluster_class = standard_cluster_class(attribute.cluster_id)
        if not attribute.define_attribute and (
            cluster_class is None or attribute.name not in cluster_class.attributes_by_name
        ):
            issues.append(
                ValidationIssue(
                    "error",
                    f"{prefix}: custom attribute must be defined in a CustomCluster.",
                )
            )
        elif not attribute.define_attribute and cluster_class is not None:
            standard_attribute = cluster_class.attributes_by_name[attribute.name]
            if attribute.attribute_id != standard_attribute.id:
                issues.append(
                    ValidationIssue(
                        "error",
                        f"{prefix}: {attribute.name} has standard attribute ID "
                        f"0x{standard_attribute.id:04X}, not 0x{attribute.attribute_id:04X}.",
                    )
                )
        device_classes = DEVICE_CLASSES.get(attribute.entity_kind)
        if (
            attribute.device_class
            and device_classes is not None
            and attribute.device_class not in {value.value for value in device_classes}
        ):
            issues.append(
                ValidationIssue(
                    "error",
                    f"{prefix}: invalid {attribute.entity_kind} device_class "
                    f"{attribute.device_class!r}.",
                )
            )
        if (
            attribute.entity_kind == "sensor"
            and attribute.state_class
            and attribute.state_class not in {value.value for value in SensorStateClass}
        ):
            issues.append(
                ValidationIssue(
                    "error", f"{prefix}: invalid sensor state_class {attribute.state_class!r}."
                )
            )
        if not 1 <= attribute.endpoint_id <= 240:
            issues.append(ValidationIssue("error", f"{prefix}: endpoint must be 1..240."))
        if not 0 <= attribute.cluster_id <= 0xFFFF:
            issues.append(ValidationIssue("error", f"{prefix}: invalid cluster ID."))
        if not 0 <= attribute.attribute_id <= 0xFFFF:
            issues.append(ValidationIssue("error", f"{prefix}: invalid attribute ID."))
        if attribute.access not in {"r", "w", "rw", "rp", "rwp"}:
            issues.append(ValidationIssue("error", f"{prefix}: unsupported access mode."))
        if (
            attribute.manufacturer_code is not None
            and not 0 <= attribute.manufacturer_code <= 0xFFFF
        ):
            issues.append(ValidationIssue("error", f"{prefix}: invalid manufacturer code."))
        if attribute.divisor == 0:
            issues.append(ValidationIssue("error", f"{prefix}: divisor must not be zero."))
        for name in ("min_value", "max_value", "step"):
            value = getattr(attribute, name)
            if isinstance(value, float) and not math.isfinite(value):
                issues.append(ValidationIssue("error", f"{prefix}: {name} must be finite."))
        reporting = (
            attribute.reporting_min_interval,
            attribute.reporting_max_interval,
            attribute.reporting_change,
        )
        if any(value is not None for value in reporting):
            if any(value is None for value in reporting):
                issues.append(
                    ValidationIssue(
                        "error",
                        f"{prefix}: reporting requires min interval, max interval and change.",
                    )
                )
            elif not 0 <= attribute.reporting_min_interval <= 0xFFFF:
                issues.append(ValidationIssue("error", f"{prefix}: invalid reporting minimum."))
            elif not 1 <= attribute.reporting_max_interval <= 0xFFFF:
                issues.append(ValidationIssue("error", f"{prefix}: invalid reporting maximum."))
            elif attribute.reporting_min_interval > attribute.reporting_max_interval:
                issues.append(
                    ValidationIssue("error", f"{prefix}: reporting minimum exceeds maximum.")
                )
            elif attribute.reporting_change < 0:
                issues.append(ValidationIssue("error", f"{prefix}: reporting change is negative."))
        if attribute.entity_kind == "number":
            effective_multiplier = None
            if attribute.divisor != 0:
                try:
                    effective_multiplier = number_multiplier(attribute)
                except OverflowError:
                    issues.append(
                        ValidationIssue(
                            "error",
                            f"{prefix}: Number scaling is outside the finite numeric range.",
                        )
                    )
            if effective_multiplier == 0:
                issues.append(
                    ValidationIssue("error", f"{prefix}: Number multiplier must not be zero.")
                )
            if attribute.data_type not in ENUM_DATA_TYPES and attribute.data_type != "float":
                issues.append(
                    ValidationIssue("error", f"{prefix}: Number requires a numeric datatype.")
                )
            if attribute.step is not None and attribute.step <= 0:
                issues.append(ValidationIssue("error", f"{prefix}: Number step must be positive."))
            if attribute.min_value is None or attribute.max_value is None:
                issues.append(
                    ValidationIssue("error", f"{prefix}: Number requires minimum and maximum.")
                )
            elif attribute.min_value >= attribute.max_value:
                issues.append(ValidationIssue("error", f"{prefix}: minimum must be below maximum."))
            if effective_multiplier is not None and (
                attribute.data_type == "float" or effective_multiplier % 1 != 0
            ):
                issues.append(
                    ValidationIssue(
                        "warning",
                        f"{prefix} ({attribute.name}): fractional Number writes may be "
                        "truncated by ZHA (confirmed on ZHA 2.2.0 and 2.3.0). Import validation does not "
                        "verify writes; check the selected ZHA version with the device.",
                    )
                )
        if attribute.round_digits is not None:
            if attribute.entity_kind != "sensor":
                issues.append(
                    ValidationIssue("error", f"{prefix}: rounding is only supported for sensors.")
                )
            elif not 0 <= attribute.round_digits <= 15:
                issues.append(ValidationIssue("error", f"{prefix}: rounding digits must be 0..15."))
        if attribute.entity_kind == "enum":
            enum_class = enum_class_identifier(attribute)
            if not enum_class.isidentifier() or keyword.iskeyword(enum_class):
                issues.append(ValidationIssue("error", f"{prefix}: invalid enum class name."))
            elif enum_class in reserved_names:
                issues.append(
                    ValidationIssue(
                        "error",
                        f"{prefix}: enum class {enum_class!r} conflicts with a generated "
                        "class, import, or converter.",
                    )
                )
            if attribute.data_type not in ENUM_DATA_TYPES:
                issues.append(
                    ValidationIssue("error", f"{prefix}: Enum requires an integer datatype.")
                )
            if not attribute.enum_values:
                issues.append(ValidationIssue("error", f"{prefix}: Enum requires values."))
            minimum, maximum = ENUM_DATA_TYPES.get(attribute.data_type, (0, 0))
            for name, value in attribute.enum_values.items():
                if not name.isidentifier() or keyword.iskeyword(name):
                    issues.append(
                        ValidationIssue("error", f"{prefix}: invalid enum value name {name!r}.")
                    )
                if not isinstance(value, int) or not minimum <= value <= maximum:
                    issues.append(
                        ValidationIssue(
                            "error",
                            f"{prefix}: enum value {name!r} must be {minimum}..{maximum}.",
                        )
                    )
            enum_definition = (attribute.data_type, attribute.enum_values)
            previous_definition = enum_classes.setdefault(enum_class, enum_definition)
            if previous_definition != enum_definition:
                issues.append(
                    ValidationIssue(
                        "error", f"{prefix}: enum class {enum_class!r} has conflicting values."
                    )
                )

    if not any(issue.severity == "error" for issue in issues):
        try:
            ast.parse(generate_quirk(project))
        except SyntaxError as error:
            issues.append(ValidationIssue("error", f"Generated Python is invalid: {error}"))
    return issues


def installed_profile() -> dict[str, str]:
    profile = {"python": sys.version.split()[0]}
    for distribution in ("zigpy", "zha", "zha-quirks"):
        try:
            profile[distribution] = importlib.metadata.version(distribution)
        except importlib.metadata.PackageNotFoundError:
            profile[distribution] = "not installed"
    return profile


def _import_worker(source: str, connection: Connection) -> None:
    try:
        namespace = {"__name__": "generated_quirk", "__file__": "<generated-quirk>"}
        exec(compile(source, "<generated-quirk>", "exec"), namespace)  # noqa: S102
    except Exception as error:  # noqa: BLE001
        detail = "".join(traceback.format_exception_only(type(error), error)).strip()
        connection.send(("error", detail))
    else:
        connection.send(("success", ""))
    finally:
        connection.close()


def validate_import(project: QuirkProject, timeout: int = 15) -> list[ValidationIssue]:
    issues = validate_project(project)
    if any(issue.severity == "error" for issue in issues):
        return issues

    context = multiprocessing.get_context("spawn")
    receiver, sender = context.Pipe(duplex=False)
    process = context.Process(target=_import_worker, args=(generate_quirk(project), sender))
    process.start()
    sender.close()
    process.join(timeout)
    if process.is_alive():
        process.terminate()
        process.join()
        receiver.close()
        issues.append(
            ValidationIssue("error", f"Upstream import exceeded the {timeout} second timeout.")
        )
        return issues

    if receiver.poll():
        try:
            status, detail = receiver.recv()
        except EOFError:
            status, detail = "error", f"validator process exited with code {process.exitcode}"
    else:
        status, detail = "error", f"validator process exited with code {process.exitcode}"
    receiver.close()
    if status == "error":
        issues.append(ValidationIssue("error", f"Upstream import failed: {detail}"))
    else:
        versions = installed_profile()
        issues.append(
            ValidationIssue(
                "success",
                "Imported with "
                f"zigpy {versions['zigpy']}, ZHA {versions['zha']}, "
                f"zha-quirks {versions['zha-quirks']} on Python {versions['python']}.",
            )
        )
    return issues
