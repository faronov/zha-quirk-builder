from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

ZIGPY_TYPES = {
    "bool": "t.Bool",
    "bitmap8": "t.bitmap8",
    "bitmap16": "t.bitmap16",
    "enum8": "t.enum8",
    "enum16": "t.enum16",
    "string": "t.CharacterString",
    "uint8": "t.uint8_t",
    "uint16": "t.uint16_t",
    "uint32": "t.uint32_t",
    "int8": "t.int8s",
    "int16": "t.int16s",
    "int32": "t.int32s",
    "float": "t.Single",
}

ENTITY_KINDS = ("sensor", "number", "switch", "binary_sensor", "enum")


@dataclass(slots=True)
class AttributeSpec:
    name: str
    cluster_id: int
    attribute_id: int
    data_type: str
    endpoint_id: int = 1
    cluster_type: str = "server"
    access: str = "rw"
    manufacturer_specific: bool = True
    manufacturer_code: int | None = None
    define_attribute: bool = True
    replace_default_entity: bool = False
    entity_kind: str = "number"
    fallback_name: str = ""
    translation_key: str = ""
    device_class: str = ""
    unit: str = ""
    min_value: float | None = None
    max_value: float | None = None
    step: float | None = None
    divisor: int | None = None
    multiplier: int | None = None
    round_digits: int | None = None
    state_class: str = ""
    enum_class: str = ""
    enum_values: dict[str, int] = field(default_factory=dict)
    reporting_min_interval: int | None = None
    reporting_max_interval: int | None = None
    reporting_change: int | None = None

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> AttributeSpec:
        if not isinstance(data, dict):
            raise TypeError("Each attribute must be a JSON object.")
        for name in (
            "name",
            "data_type",
            "cluster_type",
            "access",
            "entity_kind",
            "fallback_name",
            "translation_key",
            "device_class",
            "unit",
            "state_class",
            "enum_class",
        ):
            if name in data and not isinstance(data[name], str):
                raise ValueError(f"Attribute {name} must be a string.")
        for name in (
            "cluster_id",
            "attribute_id",
            "endpoint_id",
            "manufacturer_code",
            "divisor",
            "multiplier",
            "round_digits",
            "reporting_min_interval",
            "reporting_max_interval",
            "reporting_change",
        ):
            if name not in data:
                continue
            value = data[name]
            if value is None and name not in {"cluster_id", "attribute_id", "endpoint_id"}:
                continue
            if type(value) is not int:
                raise ValueError(f"Attribute {name} must be an integer.")
        for name in ("min_value", "max_value", "step"):
            if name in data and data[name] is not None and type(data[name]) not in (int, float):
                raise ValueError(f"Attribute {name} must be a number.")
        for name in ("manufacturer_specific", "define_attribute", "replace_default_entity"):
            if name in data and type(data[name]) is not bool:
                raise ValueError(f"Attribute {name} must be a boolean.")
        if "enum_values" in data:
            values = data["enum_values"]
            if not isinstance(values, dict) or any(
                not isinstance(name, str) or type(value) is not int
                for name, value in values.items()
            ):
                raise ValueError("Enum values must be a JSON object mapping names to integers.")
        return cls(**data)


@dataclass(slots=True)
class QuirkProject:
    manufacturer: str
    model: str
    friendly_manufacturer: str = ""
    friendly_model: str = ""
    attributes: list[AttributeSpec] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> QuirkProject:
        if not isinstance(data, dict):
            raise TypeError("Project must be a JSON object.")
        for name in ("manufacturer", "model", "friendly_manufacturer", "friendly_model"):
            if name in data and not isinstance(data[name], str):
                raise ValueError(f"Project {name} must be a string.")
        if not isinstance(data.get("attributes", []), list):
            raise TypeError("Project attributes must be a JSON array.")
        payload = dict(data)
        payload["attributes"] = [
            AttributeSpec.from_dict(item) for item in payload.get("attributes", [])
        ]
        return cls(**payload)


def efekta_sample() -> QuirkProject:
    return QuirkProject(
        manufacturer="EFEKTA",
        model="EFEKTA_iAQ3",
        friendly_manufacturer="EFEKTA",
        friendly_model="iAQ3",
        attributes=[
            AttributeSpec(
                name="measured_value",
                cluster_id=0x0402,
                attribute_id=0x0000,
                data_type="int16",
                access="rp",
                manufacturer_specific=False,
                define_attribute=False,
                replace_default_entity=True,
                entity_kind="sensor",
                fallback_name="Temperature",
                device_class="temperature",
                unit="°C",
                divisor=100,
                state_class="measurement",
                reporting_min_interval=30,
                reporting_max_interval=300,
                reporting_change=25,
            ),
            AttributeSpec(
                name="measured_value",
                cluster_id=0x0405,
                attribute_id=0x0000,
                data_type="uint16",
                access="rp",
                manufacturer_specific=False,
                define_attribute=False,
                replace_default_entity=True,
                entity_kind="sensor",
                fallback_name="Humidity",
                device_class="humidity",
                unit="%",
                divisor=100,
                state_class="measurement",
                reporting_min_interval=30,
                reporting_max_interval=300,
                reporting_change=50,
            ),
            AttributeSpec(
                name="battery_percentage_remaining",
                cluster_id=0x0001,
                attribute_id=0x0021,
                data_type="uint8",
                access="rp",
                manufacturer_specific=False,
                define_attribute=False,
                replace_default_entity=True,
                entity_kind="sensor",
                fallback_name="Battery",
                device_class="battery",
                unit="%",
                divisor=2,
                state_class="measurement",
                reporting_min_interval=3600,
                reporting_max_interval=21600,
                reporting_change=2,
            ),
            AttributeSpec(
                name="report_delay",
                cluster_id=0x040D,
                attribute_id=0x0201,
                data_type="uint16",
                fallback_name="Report delay",
                translation_key="report_delay",
                unit="min",
                min_value=1,
                max_value=240,
                step=1,
            ),
            AttributeSpec(
                name="temperature_offset",
                cluster_id=0x040D,
                attribute_id=0x0210,
                data_type="int16",
                fallback_name="Temperature offset",
                translation_key="temperature_offset",
                unit="°C",
                min_value=-5,
                max_value=5,
                step=0.1,
                divisor=10,
            ),
            AttributeSpec(
                name="display_enabled",
                cluster_id=0x040D,
                attribute_id=0x0220,
                data_type="bool",
                entity_kind="switch",
                fallback_name="Display",
                translation_key="display_enabled",
            ),
        ],
    )
