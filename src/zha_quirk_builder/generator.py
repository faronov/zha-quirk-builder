from __future__ import annotations

import keyword
import re
from collections import defaultdict

from zigpy.zcl import Cluster

from zha_quirk_builder.model import ZIGPY_TYPES, AttributeSpec, QuirkProject


def python_identifier(value: str, fallback: str = "attribute") -> str:
    identifier = re.sub(r"\W+", "_", value.strip().lower()).strip("_")
    if not identifier:
        identifier = fallback
    if identifier[0].isdigit():
        identifier = f"attr_{identifier}"
    if keyword.iskeyword(identifier):
        identifier = f"{identifier}_value"
    return identifier


def class_identifier(project: QuirkProject, cluster_id: int, endpoint_id: int) -> str:
    model = re.sub(r"[^A-Za-z0-9]+", " ", project.model).title().replace(" ", "")
    if not model or model[0].isdigit():
        model = f"Device{model}"
    return f"{model}Cluster{cluster_id:04X}Endpoint{endpoint_id}"


def enum_class_identifier(attribute: AttributeSpec) -> str:
    if attribute.enum_class:
        return attribute.enum_class
    name = re.sub(r"[^A-Za-z0-9]+", " ", attribute.name).title().replace(" ", "")
    return f"{name}Enum"


def standard_cluster_class(cluster_id: int) -> type[Cluster] | None:
    return Cluster._registry.get(cluster_id)


def entity_unique_id_suffix(attribute: AttributeSpec) -> str:
    return attribute.translation_key or attribute.device_class or attribute.name


def _value_argument(name: str, value: object | None) -> str | None:
    if value is None or value == "":
        return None
    return f"{name}={value!r}"


def _entity_lines(attribute: AttributeSpec) -> list[str]:
    arguments = [repr(attribute.name)]
    if attribute.entity_kind == "enum":
        arguments.append(enum_class_identifier(attribute))
    arguments.extend(
        [
            f"cluster_id=0x{attribute.cluster_id:04X}",
            f"endpoint_id={attribute.endpoint_id}",
        ]
    )
    for name, value in (
        ("translation_key", attribute.translation_key),
        ("fallback_name", attribute.fallback_name or attribute.name.replace("_", " ").title()),
        ("unique_id_suffix", entity_unique_id_suffix(attribute)),
    ):
        argument = _value_argument(name, value)
        if argument:
            arguments.append(argument)

    if attribute.entity_kind in {"sensor", "number", "binary_sensor"}:
        argument = _value_argument("device_class", attribute.device_class)
        if argument:
            arguments.append(argument)
    if attribute.entity_kind in {"sensor", "number"}:
        argument = _value_argument("unit", attribute.unit)
        if argument:
            arguments.append(argument)
    if attribute.entity_kind == "sensor":
        for name, value in (
            ("divisor", attribute.divisor),
            ("multiplier", attribute.multiplier),
        ):
            argument = _value_argument(name, value)
            if argument:
                arguments.append(argument)
        argument = _value_argument("state_class", attribute.state_class)
        if argument:
            arguments.append(argument)
    if attribute.entity_kind == "number":
        effective_multiplier: float | int | None = attribute.multiplier
        if attribute.divisor:
            effective_multiplier = (attribute.multiplier or 1) / attribute.divisor
        argument = _value_argument("multiplier", effective_multiplier)
        if argument and effective_multiplier != 1:
            arguments.append(argument)
        for name, value in (
            ("min_value", attribute.min_value),
            ("max_value", attribute.max_value),
            ("step", attribute.step),
        ):
            argument = _value_argument(name, value)
            if argument:
                arguments.append(argument)
    if attribute.reporting_min_interval is not None:
        arguments.append(
            "reporting_config=ReportingConfig(\n"
            f"                min_interval={attribute.reporting_min_interval},\n"
            f"                max_interval={attribute.reporting_max_interval},\n"
            f"                reportable_change={attribute.reporting_change},\n"
            "            )"
        )

    body = ",\n            ".join(arguments)
    return [f"    .{attribute.entity_kind}(", f"        {body},", "    )"]


def generate_quirk(project: QuirkProject) -> str:
    grouped: dict[tuple[int, int], list[AttributeSpec]] = defaultdict(list)
    for attribute in project.attributes:
        if attribute.define_attribute:
            grouped[(attribute.cluster_id, attribute.endpoint_id)].append(attribute)

    lines = [
        f'"""ZHA quirk for {project.manufacturer} {project.model}."""',
        "",
        "import zigpy.types as t",
    ]
    if grouped:
        lines.extend(
            [
                "from zhaquirks.clusters import CustomCluster",
                "from zigpy.zcl.foundation import BaseAttributeDefs, ZCLAttributeDef",
            ]
        )
        cluster_imports: dict[str, set[str]] = defaultdict(set)
        for cluster_id, _endpoint_id in grouped:
            cluster_class = standard_cluster_class(cluster_id)
            if cluster_class is not None:
                cluster_imports[cluster_class.__module__].add(cluster_class.__name__)
        for module, class_names in sorted(cluster_imports.items()):
            lines.append(f"from {module} import {', '.join(sorted(class_names))}")
    builder_imports = ["QuirkBuilder"]
    if any(attribute.reporting_min_interval is not None for attribute in project.attributes):
        builder_imports.append("ReportingConfig")
    lines.extend([f"from zhaquirks.builder import {', '.join(builder_imports)}", ""])

    enum_classes: dict[str, AttributeSpec] = {}
    for attribute in project.attributes:
        if attribute.entity_kind == "enum":
            enum_classes.setdefault(enum_class_identifier(attribute), attribute)
    for enum_class, attribute in enum_classes.items():
        lines.append(f"class {enum_class}(t.{attribute.data_type}):")
        if attribute.enum_values:
            for name, value in attribute.enum_values.items():
                lines.append(f"    {name} = {value}")
        else:
            lines.append("    pass")
        lines.append("")

    for (cluster_id, endpoint_id), attributes in sorted(grouped.items()):
        class_name = class_identifier(project, cluster_id, endpoint_id)
        cluster_class = standard_cluster_class(cluster_id)
        base_classes = (
            f"CustomCluster, {cluster_class.__name__}" if cluster_class else "CustomCluster"
        )
        attribute_defs_base = (
            f"{cluster_class.__name__}.AttributeDefs" if cluster_class else "BaseAttributeDefs"
        )
        lines.extend(
            [
                f"class {class_name}({base_classes}):",
                f"    cluster_id = 0x{cluster_id:04X}",
                "",
                f"    class AttributeDefs({attribute_defs_base}):",
            ]
        )
        for attribute in attributes:
            attribute_type = (
                enum_class_identifier(attribute)
                if attribute.entity_kind == "enum"
                else ZIGPY_TYPES[attribute.data_type]
            )
            definition = [
                f"id=0x{attribute.attribute_id:04X}",
                f"type={attribute_type}",
                f"access={attribute.access!r}",
            ]
            if attribute.manufacturer_specific:
                definition.append("is_manufacturer_specific=True")
            if attribute.manufacturer_code is not None:
                definition.append(f"manufacturer_code=0x{attribute.manufacturer_code:04X}")
            lines.append(f"        {attribute.name} = ZCLAttributeDef({', '.join(definition)})")
        lines.append("")

    lines.extend(["(", f"    QuirkBuilder({project.manufacturer!r}, {project.model!r})"])
    if project.friendly_model or project.friendly_manufacturer:
        arguments = []
        arguments.append(f"model={(project.friendly_model or project.model)!r}")
        arguments.append(
            f"manufacturer={(project.friendly_manufacturer or project.manufacturer)!r}"
        )
        lines.append(f"    .friendly_name({', '.join(arguments)})")

    for cluster_id, endpoint_id in sorted(grouped):
        lines.append(
            f"    .replaces({class_identifier(project, cluster_id, endpoint_id)}, "
            f"endpoint_id={endpoint_id})"
        )
    replaced_default_entities = {
        (attribute.endpoint_id, attribute.cluster_id)
        for attribute in project.attributes
        if attribute.replace_default_entity
    }
    for endpoint_id, cluster_id in sorted(replaced_default_entities):
        default_unique_id_suffix = f"{endpoint_id}-{cluster_id}"
        lines.append(
            "    .prevent_default_entity_creation("
            f"endpoint_id={endpoint_id}, cluster_id=0x{cluster_id:04X}, "
            f"unique_id_suffix={default_unique_id_suffix!r})"
        )
    for attribute in project.attributes:
        lines.extend(_entity_lines(attribute))
    lines.extend(["    .add_to_registry()", ")", ""])
    return "\n".join(lines)
