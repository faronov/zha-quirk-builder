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

ENTITY_KINDS = ("sensor", "number", "switch", "binary_sensor")


@dataclass(slots=True)
class AttributeSpec:
    name: str
    cluster_id: int
    attribute_id: int
    data_type: str
    endpoint_id: int = 1
    access: str = "rw"
    manufacturer_specific: bool = True
    manufacturer_code: int | None = None
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
    state_class: str = ""

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> AttributeSpec:
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
