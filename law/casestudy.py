"""케이스 스터디 리포트.

규칙 엔진 판정 + 법령 코퍼스 + 매핑을 결합해, 어떤 값이 왜 어긋났고
어떤 법령·계약 조항이 근거이며 무엇을 하면 되는지를 한 장으로 만든다.

LLM을 쓰지 않는다. 근거 검색과 조문 인용은 전부 결정적이므로
API 키 없이도 같은 결과가 나온다.

    python -m law.casestudy 계절근로자_결함케이스_30세트/CASE-2026-06-0004/CASE-2026-06-0004.json
    python -m law.casestudy <케이스1> <케이스2> ... [--json]
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

from law import guidance
from law.explain import iter_findings
from law.features import label, source
from law.mapping import spec
from law.retrieval import Corpus, evidence

WIDTH = 78

MONEY = ("wage", "pay", "amount", "cost", "deduction", "won", "deposit")
HOURS = ("hours", "time")
BOOLEAN = ("match", "occurred", "available", "confirmed", "complete",
           "exceeded", "due", "selected", "provided", "nonpositive",
           "below", "candidate", "partial")


def fmt(field: str, value: Any) -> str:
    """필드 성격에 맞게 값을 표기한다."""
    if value is None:
        return "없음"
    if isinstance(value, bool):
        if "match" in field:
            return "일치" if value else "불일치"
        return "예" if value else "아니오"
    if isinstance(value, list):
        return "없음" if not value else f"{len(value)}건: {', '.join(map(str, value[:3]))}"
    if isinstance(value, dict):
        return json.dumps(value, ensure_ascii=False)
    if isinstance(value, (int, float)):
        if field.endswith("_year"):
            return f"{value:d}년"
        if field.endswith("_rate"):
            return f"{value * 100:.1f}%"
        if any(k in field for k in HOURS):
            return f"{value:,.1f}시간".replace(".0시간", "시간")
        if field.endswith("_days") or "day" in field:
            return f"{value:,}일"
        if field.endswith("_count"):
            return f"{value:,}건"
        if any(k in field for k in MONEY):
            return f"{value:,.0f}원"
        return f"{value:,}"
    return str(value)


# 차이가 '양수'면 오히려 문제가 없는 항목. 최저임금을 넘긴 것은 위반이 아니다.
NEGATIVE_ONLY = {
    "cmp_contract_minimum_wage_gap",
    "cmp_payslip_minimum_wage_gap",
}


def is_problem(field: str, value: Any) -> bool:
    """이 값이 문제를 가리키는지. 강조 표시의 기준이다."""
    if not (field.startswith("cmp_") and "gap" in field):
        return False
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return False
    if field in NEGATIVE_ONLY:
        return value < 0
    return value != 0


def collect_values(rule_id: str, finding: dict, case: dict) -> list[tuple[str, str, str, bool]]:
    """(항목명, 값, 출처문서, 강조여부) 목록."""
    documents = case.get("documents", {})
    flat: dict[str, Any] = {}
    for body in documents.values():
        if isinstance(body, dict):
            flat.update({k: v for k, v in body.items() if not isinstance(v, (list, dict))})

    rows: list[tuple[str, str, str, bool]] = []
    seen: set[str] = set()

    def add(field: str, value: Any) -> None:
        if field in seen or value is None:
            return
        seen.add(field)
        strong = is_problem(field, value)
        rows.append((label(field), fmt(field, value), source(field), strong))

    for field in guidance.CONTRACT_CONTEXT.get(rule_id, ()):
        add(field, flat.get(field))
    for field in guidance.DOCUMENT_CONTEXT.get(rule_id, ()):
        add(field, flat.get(field))
    for field in guidance.SHOW.get(rule_id, ()):
        add(field, finding["comparisons"].get(field))
    return rows


def rule_section(rule_id: str, finding: dict, case: dict, corpus: Corpus) -> dict:
    ev = evidence(corpus, rule_id)
    rule = spec(rule_id)
    return {
        "rule_id": rule_id,
        "검사내용": ev["검사내용"],
        "성격": ev["성격"],
        "판정": finding["status"],
        "판정사유": finding["reason"],
        "비교값": collect_values(rule_id, finding, case),
        "근거조항": ev["근거조항"],
        "참고조항": ev["참고조항"],
        "조건부조항": ev["조건부조항"],
        "계약서근거": ev["계약서근거"],
        "참고자료": ev["참고자료"],
        "해석": guidance.interpretation(ev["성격"], finding["status"]),
        "대응": guidance.actions(rule_id, finding["status"]),
        "질문": guidance.questions(rule_id, finding["status"]),
        "검토필요": rule.검토필요,
    }


def build(case_path: Path | str, corpus: Corpus) -> dict:
    case_path = Path(case_path)
    case = json.loads(case_path.read_text(encoding="utf-8"))
    contract = case.get("documents", {}).get("contract", {})
    findings = [f for f in iter_findings(case) if f["status"] != "PASS"]
    return {
        "case_id": case_path.stem,
        "근로자": contract.get("ct_employee_name", ""),
        "사업장": contract.get("ct_employer_name", ""),
        "산정기간": f"{contract.get('ct_pay_period_start', '')} ~ {contract.get('ct_pay_period_end', '')}",
        "불일치": [rule_section(f["rule_id"], f, case, corpus) for f in findings],
    }


# --- 출력 -------------------------------------------------------------

def _wrap(text: str, indent: str = "     ", width: int = WIDTH) -> str:
    import textwrap

    return "\n".join(
        textwrap.fill(line, width=width, initial_indent=indent, subsequent_indent=indent)
        for line in text.split("\n")
    )


def render(report: dict) -> str:
    out: list[str] = []
    out.append("━" * WIDTH)
    out.append(f" {report['case_id']}")
    out.append(f" {report['근로자']} · {report['사업장']} · 산정기간 {report['산정기간']}")
    out.append(f" 불일치 {len(report['불일치'])}건")
    out.append("━" * WIDTH)

    for i, s in enumerate(report["불일치"], start=1):
        out.append("")
        out.append(f"[{i}] {s['rule_id']}  {s['검사내용']}")
        out.append(f"     판정 {s['판정']}  ·  성격 {s['성격']}")
        out.append("─" * WIDTH)
        out.append(f"  ▪ 판정 사유")
        out.append(_wrap(s["판정사유"]))

        if s["비교값"]:
            out.append("")
            out.append("  ▪ 비교된 값")
            width = max(len(n) for n, _, _, _ in s["비교값"])
            for name, value, src, strong in s["비교값"]:
                mark = " ←" if strong else ""
                src_text = f"  ({src})" if src else ""
                out.append(f"     {name:<{width}}  {value}{src_text}{mark}")

        out.append("")
        out.append("  ▪ 근거")
        if not (s["계약서근거"] or s["근거조항"] or s["참고조항"]
                or s["조건부조항"] or s["참고자료"]):
            out.append(_wrap("직접 대응하는 법령이 없습니다. 네 문서를 같은 사례로 묶기 위한 "
                             "시스템 확인 절차이므로 법적 근거를 인용하지 않습니다."))
        for c in s["계약서근거"]:
            if c["역할"] == "primary":
                out.append(f"     [1차] {c['인용']}")
                if c.get("공식인용") and c["공식인용"] != c["인용"]:
                    out.append(f"            (공식 서식 기준: {c['공식인용']})")
                out.append(_wrap(c["확인내용"], "            "))
        for c in s["근거조항"]:
            out.append(f"     [법령] {c['인용']}")
            out.append(_wrap(f"\"{c['본문'][:150]}{'…' if len(c['본문']) > 150 else ''}\"", "            "))
        for c in s["참고조항"]:
            out.append(f"     [참고] {c['인용']}")
            out.append(_wrap(f"\"{c['본문'][:110]}{'…' if len(c['본문']) > 110 else ''}\"", "            "))
        for c in s["조건부조항"]:
            out.append(f"     [조건부] {c['인용']}")
            out.append(_wrap(f"\"{c['본문'][:110]}{'…' if len(c['본문']) > 110 else ''}\"", "            "))
            out.append(_wrap(f"→ {c['적용조건']}에만 적용됩니다.", "            "))
        for r in s["참고자료"]:
            out.append(f"     [자료] {r['발행처']} 「{r['명칭']}」")
            if r.get("주의"):
                out.append(_wrap(f"주의: {r['주의']}", "            "))

        out.append("")
        out.append("  ▪ 법령에 근거한 설명")
        for line in s["해석"]:
            out.append(_wrap(line))
        if s["검토필요"]:
            out.append(_wrap(f"※ {s['검토필요']}"))

        if s["대응"]:
            out.append("")
            out.append("  ▪ 대응 방법")
            for j, action in enumerate(s["대응"], start=1):
                out.append(_wrap(f"{j}. {action}", "     "))

        if s["질문"]:
            out.append("")
            out.append("  ▪ 확인 질문")
            for question in s["질문"]:
                out.append(_wrap(f"Q. {question}", "     "))

    out.append("")
    return "\n".join(out)


if __name__ == "__main__":
    paths = [a for a in sys.argv[1:] if not a.startswith("--")]
    as_json = "--json" in sys.argv[1:]
    if not paths:
        raise SystemExit(__doc__)

    corpus = Corpus.load()
    reports = [build(p, corpus) for p in paths]
    if as_json:
        print(json.dumps(reports, ensure_ascii=False, indent=2))
    else:
        for report in reports:
            print(render(report))
