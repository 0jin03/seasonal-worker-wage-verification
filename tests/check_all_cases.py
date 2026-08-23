"""저장소의 합성 사례 전체를 판정하고 기대 상태와 비교한다."""

from __future__ import annotations

import json
from pathlib import Path

from vitamin.io import load_case
from vitamin.pipeline import VitaminPipeline


ROOT = Path(__file__).parents[1]


def main() -> int:
    total = comparable = 0
    mismatches: list[tuple[str, list[str]]] = []

    for path in sorted(ROOT.rglob("*.json")):
        payload = json.loads(path.read_text(encoding="utf-8"))
        required_documents = {
            "contract", "timesheet", "payslip", "bank_statement"
        }
        if not required_documents.issubset(payload.get("documents", {})):
            continue
        total += 1
        report = VitaminPipeline(require_review=True).run(load_case(path))
        expected = {
            rule_id: values.get(f"{rule_id.lower()}_result")
            for rule_id, values in payload.get("rule_results", {}).items()
        }
        if not expected:
            continue
        comparable += 1
        actual = {item.rule_id: item.status.value for item in report.rules}
        differences = [
            f"{rule_id}(예상={status}, 실제={actual.get(rule_id)})"
            for rule_id, status in expected.items()
            if actual.get(rule_id) != status
        ]
        if differences:
            mismatches.append((payload.get("case_id", path.stem), differences))

    print(f"판정 사례: {total}")
    print(f"기대값 비교 사례: {comparable}")
    print(f"불일치 사례: {len(mismatches)}")
    for case_id, differences in mismatches:
        print(f"{case_id}: {', '.join(differences)}")
    return 1 if mismatches else 0


if __name__ == "__main__":
    raise SystemExit(main())
