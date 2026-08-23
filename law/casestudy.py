"""케이스 스터디 리포트.

규칙 엔진 판정 + 법령 코퍼스 + 매핑을 결합해, 어떤 값이 왜 어긋났고
어떤 법령·계약 조항이 근거이며 무엇을 하면 되는지를 한 장으로 만든다.

LLM을 쓰지 않는다. 근거 검색과 조문 인용은 전부 결정적이므로
API 키 없이도 같은 결과가 나온다.

    python -m law.casestudy 계절근로자_결함케이스_30세트/CASE-2026-06-0004/CASE-2026-06-0004.json
    python -m law.casestudy <케이스1> <케이스2> ...          # 콘솔 출력
    python -m law.casestudy <케이스…> --md                   # 케이스리포트/<case>.md
    python -m law.casestudy <케이스…> --md=폴더명             # 출력 폴더 지정
    python -m law.casestudy <케이스…> --json                 # 구조화 JSON
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

from law import guidance, notice
from law.features import is_tolerance, label, source
from law.mapping import spec
from law.retrieval import Corpus, evidence

WIDTH = 78

# 단위는 필드명을 '_'로 쪼갠 토큰으로 판별한다.
# 부분 문자열로 보면 over[time]_pay 처럼 금액이 시간으로 잘못 잡힌다.
HOUR_TOKENS = {"hours", "hour"}
MINUTE_TOKENS = {"minutes", "minute"}
DAY_TOKENS = {"day", "days"}
COUNT_TOKENS = {"count"}
MONEY_TOKENS = {
    "pay", "wage", "amount", "cost", "deduction", "won", "deposit",
    "bonus", "gross", "net", "salary", "allowance", "insurance", "tax",
}


def unit_of(field: str) -> str:
    """필드의 단위를 정한다. 앞에 온 것이 우선한다."""
    tokens = set(field.split("_"))
    if field.endswith("_rate") or "coverage" in tokens:
        return "율"
    if field.endswith("_year"):
        return "년"
    if tokens & HOUR_TOKENS:
        return "시간"
    if tokens & MINUTE_TOKENS:
        return "분"
    if tokens & DAY_TOKENS:
        return "일"
    if tokens & COUNT_TOKENS:
        return "건"
    if tokens & MONEY_TOKENS:
        # 시급은 금액이 아니라 단가다. 총액과 섞이지 않게 구분한다.
        return "원/시간" if "hourly" in tokens else "원"
    return ""


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
        unit = unit_of(field)
        if unit == "율":
            return f"{value * 100:.1f}%"
        if unit == "년":
            return f"{value:d}년"
        if unit == "시간":
            text = f"{value:,.1f}시간"
            return text.replace(".0시간", "시간")
        if unit == "분":
            return f"{value:,.0f}분"
        if unit == "일":
            return f"{value:,.0f}일"
        if unit == "건":
            return f"{value:,.0f}건"
        if unit == "원/시간":
            return f"{value:,.0f}원/시간"
        if unit == "원":
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


# 비교값에 긴 배열(일별 근로시간 등)이 들어오면 앞부분만 남긴다.
LIST_PREVIEW = 5


def compact(value: Any) -> Any:
    """비교값을 싣기 좋게 줄인다."""
    if isinstance(value, list) and len(value) > LIST_PREVIEW:
        return {"앞부분": value[:LIST_PREVIEW], "전체개수": len(value)}
    if isinstance(value, dict):
        return {k: compact(v) for k, v in value.items()}
    return value


def iter_findings(case: dict) -> list[dict]:
    """케이스 JSON에서 규칙별 판정과 실제 비교값을 꺼낸다.

    두 가지 형태를 모두 받는다.
        데이터셋:  rule_results = {"R08": {"r08_result": ..., "r08_reason": ...}}
                  비교값은 derived["R08"] 에 따로 들어 있다.
        파이프라인: rule_results = [{"rule_id": "R08", "status": ..., "comparisons": {...}}]
    """
    results = case.get("rule_results")
    derived = case.get("derived") or {}
    common = derived.get("common") or {}
    findings: list[dict] = []

    if isinstance(results, dict):
        for rule_id, body in results.items():
            key = rule_id.lower()
            # 판정/사유를 뺀 나머지 + derived 의 해당 규칙 피처가 실제 비교값이다.
            comparisons = {
                k: v
                for k, v in body.items()
                if k not in (f"{key}_result", f"{key}_reason")
            }
            comparisons.update(derived.get(rule_id.upper()) or {})
            findings.append(
                {
                    "rule_id": rule_id.upper(),
                    "status": body.get(f"{key}_result", ""),
                    "reason": body.get(f"{key}_reason", ""),
                    "comparisons": compact({**common, **comparisons}),
                }
            )
    elif isinstance(results, list):
        for row in results:
            rule_id = str(row.get("rule_id", "")).upper()
            comparisons = dict(row.get("comparisons") or {})
            comparisons.update(derived.get(rule_id) or {})
            findings.append(
                {
                    "rule_id": rule_id,
                    "status": row.get("status", ""),
                    "reason": row.get("reason", ""),
                    "comparisons": compact({**common, **comparisons}),
                }
            )
    else:
        raise ValueError("케이스에 rule_results 가 없습니다.")

    return findings


def wage_check(finding: dict) -> str:
    """케이스가 쓴 최저임금이 공식 고시와 같은지 확인한다.

    지금까지 R11 은 케이스 JSON 의 ref_minimum_hourly_wage 를 그대로 믿었다.
    고시를 수집했으므로 그 값이 맞는지 대조할 수 있다.
    """
    쓴값 = finding["comparisons"].get("ref_minimum_hourly_wage")
    연도 = finding["comparisons"].get("calc_applicable_year")
    if 쓴값 is None or 연도 is None:
        return ""
    고시 = notice.minimum_wage(연도)
    if 고시 is None:
        return f"{연도}년 최저임금 고시를 수집하지 못해 기준값을 대조하지 못했습니다."
    if int(쓴값) != 고시["시간급"]:
        return (f"판정에 쓰인 최저시급 {int(쓴값):,}원이 {고시['고시번호']}의 "
                f"{고시['시간급']:,}원과 다릅니다. 기준값을 확인해야 합니다.")
    return f"판정에 쓰인 최저시급이 {고시['고시번호']}와 일치합니다."


def rule_section(rule_id: str, finding: dict, case: dict, corpus: Corpus) -> dict:
    ev = evidence(corpus, rule_id, 연도=finding["comparisons"].get("calc_applicable_year"))
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
        "허용오차": [
            (label(f), fmt(f, finding["comparisons"][f]))
            for f in guidance.SHOW.get(rule_id, ())
            if is_tolerance(f) and finding["comparisons"].get(f) is not None
        ],
        "검토필요": rule.검토필요,
        "기준값확인": wage_check(finding) if rule_id == "R11" else "",
        # 리포트에는 찍지 않는다. LLM 설명 단계(law/explain.py)에 제약으로 넘긴다.
        "금지표현": ev["금지표현"],
    }


def build_case(case: dict, corpus: Corpus, case_id: str = "case") -> dict:
    """이미 메모리에 있는 v6 판정 결과로 사용자 설명 리포트를 만든다."""
    contract = case.get("documents", {}).get("contract", {})
    findings = [f for f in iter_findings(case) if f["status"] != "PASS"]
    return {
        "case_id": case_id,
        "근로자": contract.get("ct_employee_name", ""),
        "사업장": contract.get("ct_employer_name", ""),
        "산정기간": f"{contract.get('ct_pay_period_start', '')} ~ {contract.get('ct_pay_period_end', '')}",
        "불일치": [rule_section(f["rule_id"], f, case, corpus) for f in findings],
    }


def build(case_path: Path | str, corpus: Corpus) -> dict:
    case_path = Path(case_path)
    case = json.loads(case_path.read_text(encoding="utf-8"))
    return build_case(case, corpus, case_path.stem)


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
        if s["허용오차"]:
            values = " / ".join(v for _, v in s["허용오차"])
            out.append(_wrap(
                f"※ 판정 사유의 '허용' 수치({values})는 법적으로 허용되는 범위가 아니라, "
                "반올림·환산 차이를 감안한 시스템 내부 비교 기준입니다."))

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
            식별자 = f" ({r['식별자']})" if r.get("식별자") else ""
            out.append(f"     [자료] {r['발행처']} 「{r['명칭']}」{식별자}")
            if r.get("기준값"):
                기준 = r["기준값"]
                out.append(_wrap(
                    f"시간급 {기준['시간급']:,}원 · 월환산 {기준['월환산액']:,}원"
                    f"(기준 {기준['월환산기준시간수']}시간) · 적용 {기준['적용기간']}", "            "))
            if r.get("주의"):
                out.append(_wrap(f"주의: {r['주의']}", "            "))
        if s["기준값확인"]:
            out.append(_wrap(f"※ {s['기준값확인']}", "     "))

        out.append("")
        out.append("  ▪ 법령에 근거한 설명")
        for line in s["해석"]:
            out.append(_wrap(line))
        if s["검토필요"]:
            out.append(_wrap(f"※ {s['검토필요']}"))

        # LLM 설명 단계에서만 채워진다(law/explain.py). 자료의 한계를 밝히는 항목이다.
        if s.get("확인사항"):
            out.append("")
            out.append("  ▪ 추가 확인사항")
            for line in s["확인사항"]:
                out.append(_wrap(f"- {line}"))

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


def _md_escape(text: str) -> str:
    """표 안에서 셀 구분자로 오해되지 않게 한다."""
    return str(text).replace("|", "\\|")


def render_markdown(report: dict) -> str:
    """케이스 한 건을 마크다운 문서로 만든다."""
    out: list[str] = []
    out.append(f"# {report['case_id']}")
    out.append("")
    out.append("| 항목 | 내용 |")
    out.append("|---|---|")
    out.append(f"| 근로자 | {_md_escape(report['근로자'])} |")
    out.append(f"| 사업장 | {_md_escape(report['사업장'])} |")
    out.append(f"| 산정기간 | {report['산정기간']} |")
    out.append(f"| 불일치 | {len(report['불일치'])}건 |")
    out.append("")

    if report["불일치"]:
        out.append("## 불일치 요약")
        out.append("")
        out.append("| # | 규칙 | 검사 내용 | 판정 | 성격 |")
        out.append("|---:|---|---|---|---|")
        for i, s in enumerate(report["불일치"], start=1):
            out.append(
                f"| {i} | `{s['rule_id']}` | {_md_escape(s['검사내용'])} "
                f"| `{s['판정']}` | {s['성격']} |"
            )
        out.append("")

    for i, s in enumerate(report["불일치"], start=1):
        out.append("---")
        out.append("")
        out.append(f"## {i}. {s['rule_id']} — {s['검사내용']}")
        out.append("")
        out.append(f"**판정** `{s['판정']}`  ·  **성격** {s['성격']}")
        out.append("")

        out.append("### 판정 사유")
        out.append("")
        out.append(s["판정사유"])
        if s["허용오차"]:
            values = " / ".join(v for _, v in s["허용오차"])
            out.append("")
            out.append(
                f"> 판정 사유의 '허용' 수치({values})는 법적으로 허용되는 범위가 아니라, "
                "반올림·환산 차이를 감안한 시스템 내부 비교 기준입니다."
            )
        out.append("")

        if s["비교값"]:
            out.append("### 비교된 값")
            out.append("")
            out.append("| 항목 | 값 | 출처 |")
            out.append("|---|---|---|")
            for name, value, src, strong in s["비교값"]:
                if strong:
                    name, value = f"**{name}**", f"**{value}**"
                out.append(f"| {_md_escape(name)} | {_md_escape(value)} | {_md_escape(src)} |")
            out.append("")
            if any(strong for *_, strong in s["비교값"]):
                out.append("굵게 표시한 항목이 허용 범위를 벗어난 값입니다.")
                out.append("")

        out.append("### 근거")
        out.append("")
        if not (s["계약서근거"] or s["근거조항"] or s["참고조항"]
                or s["조건부조항"] or s["참고자료"]):
            out.append("직접 대응하는 법령이 없습니다. 네 문서를 같은 사례로 묶기 위한 "
                       "시스템 확인 절차이므로 법적 근거를 인용하지 않습니다.")
            out.append("")
        for c in s["계약서근거"]:
            if c["역할"] != "primary":
                continue
            out.append(f"**1차 — {c['인용']}**")
            if c.get("공식인용") and c["공식인용"] != c["인용"]:
                out.append(f"공식 서식 기준: {c['공식인용']}")
            out.append("")
            out.append(c["확인내용"])
            out.append("")
        for c in s["근거조항"]:
            out.append(f"**법령 — {c['인용']}**  ·  시행 {c['시행일자']}")
            out.append("")
            out.append(f"> {c['본문']}")
            out.append("")
        for c in s["참고조항"]:
            out.append(f"**참고 — {c['인용']}**")
            out.append("")
            out.append(f"> {c['본문']}")
            out.append("")
        for c in s["조건부조항"]:
            out.append(f"**조건부 — {c['인용']}**")
            out.append("")
            out.append(f"> {c['본문']}")
            out.append("")
            out.append(f"{c['적용조건']}에만 적용됩니다.")
            out.append("")
        for r in s["참고자료"]:
            식별자 = f"  ·  {r['식별자']}" if r.get("식별자") else ""
            out.append(f"**자료 — {r['발행처']} 「{r['명칭']}」**{식별자}")
            out.append("")
            if r.get("기준값"):
                기준 = r["기준값"]
                out.append(
                    f"시간급 **{기준['시간급']:,}원** · 월환산 {기준['월환산액']:,}원"
                    f"(기준 {기준['월환산기준시간수']}시간) · 적용 {기준['적용기간']}"
                )
                out.append("")
            if r.get("주의"):
                out.append(f"> 주의: {r['주의']}")
                out.append("")
        if s["기준값확인"]:
            out.append(f"> {s['기준값확인']}")
            out.append("")

        out.append("### 법령에 근거한 설명")
        out.append("")
        for line in s["해석"]:
            out.append(line)
            out.append("")
        if s["검토필요"]:
            out.append(f"> 검토 필요: {s['검토필요']}")
            out.append("")

        if s.get("확인사항"):
            out.append("### 추가 확인사항")
            out.append("")
            for line in s["확인사항"]:
                out.append(f"- {line}")
            out.append("")

        if s["대응"]:
            out.append("### 대응 방법")
            out.append("")
            for j, action in enumerate(s["대응"], start=1):
                out.append(f"{j}. {action}")
            out.append("")

        if s["질문"]:
            out.append("### 확인 질문")
            out.append("")
            for question in s["질문"]:
                out.append(f"- {question}")
            out.append("")

    return "\n".join(out).rstrip() + "\n"


def write_markdown(reports: list[dict], out_dir: Path | str) -> list[Path]:
    """케이스별로 마크다운 파일을 하나씩 만든다."""
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    written = []
    for report in reports:
        path = out_dir / f"{report['case_id']}.md"
        path.write_text(render_markdown(report), encoding="utf-8")
        written.append(path)
    return written


if __name__ == "__main__":
    args = sys.argv[1:]
    paths = [a for a in args if not a.startswith("--")]
    flags = [a for a in args if a.startswith("--")]
    if not paths:
        raise SystemExit(__doc__)

    md_flag = next((f for f in flags if f == "--md" or f.startswith("--md=")), None)

    corpus = Corpus.load()
    reports = [build(p, corpus) for p in paths]

    if md_flag is not None:
        out_dir = md_flag.split("=", 1)[1] if "=" in md_flag else "케이스리포트"
        for path in write_markdown(reports, out_dir):
            print(f"  {path}")
    elif "--json" in flags:
        print(json.dumps(reports, ensure_ascii=False, indent=2))
    else:
        for report in reports:
            print(render(report))
