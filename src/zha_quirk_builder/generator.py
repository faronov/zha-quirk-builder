from __future__ import annotations

import keyword
import re
from collections import defaultdict

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


def _value_argument(name: str, value: object | None) -> str | None:
    if value is None or value == "":
        return None
    return f"{name}={value!r}"


def _entity_lines(attribute: AttributeSpec) -> list[str]:
    arguments = [
        repr(attribute.name),
        f"cluster_id=0x{attribute.cluster_id:04X}",
        f"endpoint_id={attribute.endpoint_id}",
    ]
    for name, value in (
        ("translation_key", attribute.translation_key),
        ("fallback_name", attribute.fallback_name),
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

    body = ",\n            ".join(arguments)
    return [f"    .{attribute.entity_kind}(", f"        {body},", "    )"]


def generate_quirk(project: QuirkProject) -> str:
    grouped: dict[tuple[int, int], list[AttributeSpec]] = defaultdict(list)
    for attribute in project.attributes:
        grouped[(attribute.cluster_id, attribute.endpoint_id)].append(attribute)

    lines = [
        f'"""ZHA quirk for {project.manufacturer} {project.model}."""',
        "",
        "import zigpy.types as t",
        "from zigpy.quirks import CustomCluster",
        "from zigpy.zcl.foundation import BaseAttributeDefs, ZCLAttributeDef",
        "from zhaquirks.builder import QuirkBuilder",
        "",
    ]

    for (cluster_id, endpoint_id), attributes in sorted(grouped.items()):
        class_name = class_identifier(project, cluster_id, endpoint_id)
        lines.extend(
            [
                f"class {class_name}(CustomCluster):",
                f"    cluster_id = 0x{cluster_id:04X}",
                "",
                "    class AttributeDefs(BaseAttributeDefs):",
            ]
        )
        for attribute in attributes:
            definition = [
                f"id=0x{attribute.attribute_id:04X}",
                f"type={ZIGPY_TYPES[attribute.data_type]}",
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
    for attribute in project.attributes:
        lines.extend(_entity_lines(attribute))
    lines.extend(["    .add_to_registry()", ")", ""])
    return "\n".join(lines)
