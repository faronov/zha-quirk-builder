from __future__ import annotations

import ast
import importlib.metadata
import multiprocessing
import sys
import traceback
from dataclasses import dataclass
from multiprocessing.connection import Connection

from zha_quirk_builder.generator import generate_quirk, python_identifier
from zha_quirk_builder.model import ENTITY_KINDS, ZIGPY_TYPES, QuirkProject


@dataclass(frozen=True, slots=True)
class ValidationIssue:
    severity: str
    message: str


def validate_project(project: QuirkProject) -> list[ValidationIssue]:
    issues: list[ValidationIssue] = []
    if not project.manufacturer.strip():
        issues.append(ValidationIssue("error", "Manufacturer is required."))
    if not project.model.strip():
        issues.append(ValidationIssue("error", "Model is required."))
    if not project.attributes:
        issues.append(ValidationIssue("error", "Add at least one attribute."))

    seen: set[tuple[int, int, int]] = set()
    names: set[tuple[int, int, str]] = set()
    for index, attribute in enumerate(project.attributes, 1):
        prefix = f"Attribute {index}"
        if attribute.name != python_identifier(attribute.name):
            issues.append(
                ValidationIssue(
                    "error", f"{prefix}: name must be a valid snake_case Python identifier."
                )
            )
        key = (attribute.endpoint_id, attribute.cluster_id, attribute.attribute_id)
        if key in seen:
            issues.append(ValidationIssue("error", f"{prefix}: duplicate endpoint/cluster/ID."))
        seen.add(key)
        name_key = (attribute.endpoint_id, attribute.cluster_id, attribute.name)
        if name_key in names:
            issues.append(ValidationIssue("error", f"{prefix}: duplicate attribute name."))
        names.add(name_key)
        if attribute.data_type not in ZIGPY_TYPES:
            issues.append(ValidationIssue("error", f"{prefix}: unsupported zigpy datatype."))
        if attribute.entity_kind not in ENTITY_KINDS:
            issues.append(ValidationIssue("error", f"{prefix}: unsupported entity kind."))
        if not attribute.translation_key and not attribute.device_class:
            issues.append(
                ValidationIssue(
                    "error", f"{prefix}: translation_key or device_class is required by Quirk v2."
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
        if attribute.entity_kind == "number":
            if attribute.min_value is None or attribute.max_value is None:
                issues.append(
                    ValidationIssue("error", f"{prefix}: Number requires minimum and maximum.")
                )
            elif attribute.min_value >= attribute.max_value:
                issues.append(ValidationIssue("error", f"{prefix}: minimum must be below maximum."))

    if not issues:
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
