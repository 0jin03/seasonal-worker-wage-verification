"""Small standard-library validator for the JSON Schema features used by v6."""

import re
from datetime import date


def schema_errors(value, schema, path="$"):
    errors = []
    if "oneOf" in schema:
        matches = sum(not schema_errors(value, branch, path) for branch in schema["oneOf"])
        return [] if matches == 1 else [f"{path}: expected exactly one oneOf branch"]
    if "anyOf" in schema:
        return [] if any(not schema_errors(value, branch, path) for branch in schema["anyOf"]) else [f"{path}: did not match any anyOf branch"]

    checks = {
        "null": lambda item: item is None,
        "boolean": lambda item: isinstance(item, bool),
        "integer": lambda item: isinstance(item, int) and not isinstance(item, bool),
        "number": lambda item: isinstance(item, (int, float)) and not isinstance(item, bool),
        "string": lambda item: isinstance(item, str),
        "object": lambda item: isinstance(item, dict),
        "array": lambda item: isinstance(item, list),
    }
    expected = schema.get("type")
    if expected:
        allowed = [expected] if isinstance(expected, str) else expected
        if not any(checks[name](value) for name in allowed):
            return [f"{path}: expected {allowed}, got {type(value).__name__}"]
    if "const" in schema and value != schema["const"]:
        errors.append(f"{path}: expected const {schema['const']!r}")
    if "enum" in schema and value not in schema["enum"]:
        errors.append(f"{path}: {value!r} not in enum")
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        if "minimum" in schema and value < schema["minimum"]:
            errors.append(f"{path}: below minimum {schema['minimum']}")
        if "maximum" in schema and value > schema["maximum"]:
            errors.append(f"{path}: above maximum {schema['maximum']}")
    if isinstance(value, str):
        if "pattern" in schema and not re.search(schema["pattern"], value):
            errors.append(f"{path}: does not match pattern")
        if schema.get("format") == "date":
            try:
                date.fromisoformat(value)
            except ValueError:
                errors.append(f"{path}: invalid ISO date")
    if isinstance(value, dict):
        properties = schema.get("properties", {})
        for name in schema.get("required", []):
            if name not in value:
                errors.append(f"{path}.{name}: required property missing")
        for name, item in value.items():
            child = f"{path}.{name}"
            if name in properties:
                errors.extend(schema_errors(item, properties[name], child))
            elif schema.get("additionalProperties") is False:
                errors.append(f"{child}: additional property not allowed")
    if isinstance(value, list) and "items" in schema:
        for index, item in enumerate(value):
            errors.extend(schema_errors(item, schema["items"], f"{path}[{index}]"))
    return errors
