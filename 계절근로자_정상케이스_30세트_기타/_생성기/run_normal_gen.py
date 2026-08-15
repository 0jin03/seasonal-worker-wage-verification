# -*- coding: utf-8 -*-
"""R00~R11 전 규칙 PASS 정상 케이스 30개를 생성하고 검증한다."""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path

from jsonschema import Draft202012Validator

HERE = Path(__file__).resolve().parent
OUT = HERE.parent
WORKSPACE = OUT.parent
SHARED_GENERATOR = WORKSPACE / "계절근로자_결함케이스_20세트" / "_생성기"
sys.path.insert(0, str(SHARED_GENERATOR))

from gen_engine import make  # noqa: E402
from normal_specs import SPECS  # noqa: E402


SCHEMA_PATH = WORKSPACE / "R00-R11_최종_JSON_Schema_v3.2.json"
SCHEMA = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
VALIDATOR = Draft202012Validator(SCHEMA)


def validate_case(case: dict) -> tuple[list, list]:
    schema_errors = sorted(VALIDATOR.iter_errors(case), key=lambda error: list(error.path))
    non_pass = []
    for rule in [f"R{number:02d}" for number in range(12)]:
        result = case["rule_results"][rule][f"{rule.lower()}_result"]
        if result != "PASS":
            non_pass.append((rule, result, case["rule_results"][rule][f"{rule.lower()}_reason"]))
    return schema_errors, non_pass


def write_summary(rows: list[tuple[dict, dict, dict]]) -> None:
    lines = [
        "# 계절근로자 정상 케이스 30세트 요약",
        "",
        "- 기준: R00-R11_통합_표준피처정의서_v3.2",
        "- JSON: R00-R11_최종_JSON_Schema_v3.2",
        "- 판정: 30개 케이스 모두 R00~R11 PASS",
        "- 문서 국적: 캄보디아 (Cambodia)",
        "",
        "| No | case_id | 근로자 | 사업장 | 임금형태 | 산정기간 | 총지급액 | 총공제액 | 실수령액 |",
        "|---:|---|---|---|---|---|---:|---:|---:|",
    ]
    for index, (spec, case, ctx) in enumerate(rows, 1):
        ps = case["documents"]["payslip"]
        lines.append(
            f"| {index} | {spec['id']} | {spec['name']} | {spec['employer']} | "
            f"{ps['ps_wage_type']} | {ps['ps_pay_period_start']}~{ps['ps_pay_period_end']} | "
            f"{ps['ps_gross_pay']:,.0f} | {ps['ps_total_deduction']:,.0f} | {ps['ps_net_pay']:,.0f} |"
        )
    lines += [
        "",
        "각 케이스 폴더에는 JSON과 표준근로계약서·근무기록부·임금명세서·입금내역서 PDF가 포함됩니다.",
        "",
    ]
    (OUT / "정상케이스_30세트_요약.md").write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="R00~R11 전 규칙 PASS 정상 케이스 30개 생성")
    parser.add_argument("--write", action="store_true", help="검증 성공 시 JSON 파일 저장")
    args = parser.parse_args()

    all_ok = True
    rows: list[tuple[dict, dict, dict]] = []
    results = Counter()
    for spec in SPECS:
        case, ctx = make(spec)
        schema_errors, non_pass = validate_case(case)
        ok = not schema_errors and not non_pass
        all_ok &= ok
        for rule in case["rule_results"].values():
            key = next(key for key in rule if key.endswith("_result"))
            results[rule[key]] += 1
        print(f"{'OK' if ok else 'XX'} {spec['id']} {spec['name']:<20} schema={len(schema_errors)} non_pass={len(non_pass)}")
        for error in schema_errors[:5]:
            print("   schema:", "/".join(map(str, error.path)), "->", error.message)
        for rule, result, reason in non_pass:
            print(f"   {rule}: {result} — {reason}")
        rows.append((spec, case, ctx))

    print("결과 분포:", dict(results))
    if not all_ok:
        print("검증 실패: 파일을 저장하지 않습니다.")
        return 1
    if args.write:
        for spec, case, _ctx in rows:
            case_dir = OUT / spec["id"]
            case_dir.mkdir(parents=True, exist_ok=True)
            output = case_dir / f"{spec['id']}.json"
            output.write_text(json.dumps(case, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        write_summary(rows)
        print(f"저장 완료: {len(rows)}개 JSON -> {OUT}")
    else:
        print("검증 완료. 저장하려면 --write 옵션을 사용하세요.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

