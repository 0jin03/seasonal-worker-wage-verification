from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .models import RuleResult


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_SCHEMA_PATH = PROJECT_ROOT / "references" / "R00-R11_최종_JSON_Schema_v6.json"


def load_v6_schema(path: str | Path = DEFAULT_SCHEMA_PATH) -> dict[str, Any]:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _blank_required_object(schema: dict[str, Any]) -> dict[str, Any]:
    return {name: None for name in schema.get("required", [])}


def build_v6_result(
    documents: dict[str, Any],
    flat_derived: dict[str, Any],
    rules: list[RuleResult],
    schema: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build the exact v6 top-level structure without leaking engine-only keys."""
    schema = schema or load_v6_schema()
    derived_schema = schema["properties"]["derived"]
    rule_schema = schema["properties"]["rule_results"]

    derived: dict[str, Any] = {}
    for rule_id, group_schema in derived_schema["properties"].items():
        group = _blank_required_object(group_schema)
        for field_name in group_schema.get("properties", {}):
            if field_name in flat_derived:
                value = flat_derived[field_name]
                if field_name == "ts_daily_actual_hours" and isinstance(value, list):
                    value = [item.get("hours") if isinstance(item, dict) else item for item in value]
                group[field_name] = value
        derived[rule_id] = group

    by_id = {item.rule_id: item for item in rules}
    rule_results: dict[str, Any] = {}
    for rule_id, group_schema in rule_schema["properties"].items():
        group = _blank_required_object(group_schema)
        result = by_id.get(rule_id)
        if result is not None:
            prefix = rule_id.lower()
            group[f"{prefix}_result"] = str(result.status)
            group[f"{prefix}_reason"] = result.reason
        rule_results[rule_id] = group

    return {
        "documents": documents,
        "derived": derived,
        "rule_results": rule_results,
    }
