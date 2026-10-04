"""A small JSON Schema validator for the subset the vmmbench schemas use.

Keywords: type (incl. lists and "integer"), const, enum, required, properties,
additionalProperties (bool or schema), items. Enough for vmmbench/schemas/*.json without a new
dependency; any other keyword in a schema raises, so the subset cannot drift silently.
"""

from __future__ import annotations

import json
from pathlib import Path

SCHEMAS = Path(__file__).resolve().parent / "schemas"
KNOWN = {
    "$schema", "$id", "title", "description", "type", "const", "enum", "required",
    "properties", "additionalProperties", "items",
}  # fmt: skip
TYPES = {
    "object": dict,
    "array": list,
    "string": str,
    "boolean": bool,
    "null": type(None),
}


class ValidationError(ValueError):
    pass


def _is(value, t: str) -> bool:
    if t == "integer":
        return isinstance(value, int) and not isinstance(value, bool)
    if t == "number":
        return isinstance(value, int | float) and not isinstance(value, bool)
    return isinstance(value, TYPES[t])


def validate(value, schema: dict, path: str = "$") -> None:
    unknown = set(schema) - KNOWN
    if unknown:
        raise ValidationError(f"{path}: unsupported schema keywords {sorted(unknown)}")
    if "const" in schema and value != schema["const"]:
        raise ValidationError(f"{path}: expected {schema['const']!r}, got {value!r}")
    if "enum" in schema and value not in schema["enum"]:
        raise ValidationError(f"{path}: {value!r} not in {schema['enum']}")
    if "type" in schema:
        ts = schema["type"] if isinstance(schema["type"], list) else [schema["type"]]
        if not any(_is(value, t) for t in ts):
            raise ValidationError(f"{path}: expected type {ts}, got {type(value).__name__}")
    if isinstance(value, dict):
        for k in schema.get("required", []):
            if k not in value:
                raise ValidationError(f"{path}: missing required {k!r}")
        props = schema.get("properties", {})
        extra = schema.get("additionalProperties", True)
        for k, v in value.items():
            if k in props:
                validate(v, props[k], f"{path}.{k}")
            elif extra is False:
                raise ValidationError(f"{path}: unexpected property {k!r}")
            elif isinstance(extra, dict):
                validate(v, extra, f"{path}.{k}")
    if isinstance(value, list) and "items" in schema:
        for i, v in enumerate(value):
            validate(v, schema["items"], f"{path}[{i}]")


def load(name: str) -> dict:
    return json.loads((SCHEMAS / f"{name}.schema.json").read_text())


def check(value, name: str) -> None:
    """Validate against vmmbench/schemas/<name>.schema.json."""
    validate(value, load(name))
