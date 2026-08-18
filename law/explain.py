"""판정 결과를 근로자가 이해할 수 있는 설명으로 바꾼다 (Anthropic API).

    export ANTHROPIC_API_KEY="..."
    python -m law.explain R00_R11_FINAL/R08/CASE-R08-2026-01-0001/CASE-R08-2026-01-0001.json
    python -m law.explain <케이스.json> --dry-run     # API 호출 없이 전송 내용만 확인

규칙 엔진 판정을 다시 계산하지 않는다. 판정 + 비교값 + 공식 근거를 받아 설명만 만든다.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Any

from law.prompt import OUTPUT_SCHEMA, SYSTEM, build_user_message
from law.retrieval import Corpus, evidence

MODEL = "claude-opus-5"
MAX_TOKENS = 8000
EFFORT = "high"

# 정책 거절 시 서버가 대체 모델로 자동 재실행한다. 거절은 오류가 아니라 HTTP 200으로 오므로
# 이 옵션이 없으면 요청이 그냥 멈춘다.
FALLBACK_BETA = "server-side-fallback-2026-07-01"


def _client():
    import anthropic

    if not os.environ.get("ANTHROPIC_API_KEY"):
        raise RuntimeError(
            'ANTHROPIC_API_KEY 환경변수가 없습니다.\n  export ANTHROPIC_API_KEY="..."'
        )
    return anthropic.Anthropic()


def call_llm(system: str, user: str) -> dict:
    """구조화 출력으로 한 번 호출한다."""
    import anthropic

    client = _client()
    params: dict[str, Any] = {
        "model": MODEL,
        "max_tokens": MAX_TOKENS,
        "system": system,
        "messages": [{"role": "user", "content": user}],
        "output_config": {
            "effort": EFFORT,
            "format": {"type": "json_schema", "schema": OUTPUT_SCHEMA},
        },
    }

    try:
        response = client.beta.messages.create(
            betas=[FALLBACK_BETA], fallbacks="default", **params
        )
    except anthropic.BadRequestError:
        # 조직에 fallback 베타가 열려 있지 않으면 그냥 일반 경로로 간다.
        response = client.messages.create(**params)

    if response.stop_reason == "refusal":
        category = getattr(getattr(response, "stop_details", None), "category", None)
        raise RuntimeError(f"모델이 응답을 거절했습니다 (category={category}).")

    text = next((b.text for b in response.content if b.type == "text"), "")
    return json.loads(text)


# 긴 배열을 그대로 넘기면 프롬프트만 부풀고 설명에 도움이 안 된다.
LIST_PREVIEW = 6


def compact(value: Any) -> Any:
    """비교값을 프롬프트에 싣기 좋게 줄인다."""
    if isinstance(value, list) and len(value) > LIST_PREVIEW:
        head = value[:LIST_PREVIEW]
        return {"앞부분": head, "전체개수": len(value)}
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


def build_requests(case: dict, corpus: Corpus, only_failed: bool = True) -> list[dict]:
    """LLM에 보낼 요청을 규칙별로 만든다. 실제 호출은 하지 않는다."""
    requests = []
    for finding in iter_findings(case):
        if only_failed and finding["status"] == "PASS":
            continue
        ev = evidence(corpus, finding["rule_id"])
        requests.append(
            {
                **finding,
                "성격": ev["성격"],
                "evidence": ev,
                "user_message": build_user_message(
                    finding["rule_id"],
                    finding["status"],
                    finding["reason"],
                    finding["comparisons"],
                    ev,
                ),
            }
        )
    return requests


def explain_case(
    case_path: Path | str, corpus: Corpus | None = None, only_failed: bool = True
) -> dict:
    """케이스 한 건을 설명한다. 5단계 출력 JSON의 원형이다."""
    case_path = Path(case_path)
    case = json.loads(case_path.read_text(encoding="utf-8"))
    corpus = corpus or Corpus.load()

    findings = []
    for request in build_requests(case, corpus, only_failed):
        explanation = call_llm(SYSTEM, request["user_message"])
        findings.append(
            {
                "rule_id": request["rule_id"],
                "검사내용": request["evidence"]["검사내용"],
                "성격": request["성격"],
                "판정결과": request["status"],
                "판정사유": request["reason"],
                "설명": explanation,
                "근거출처": {
                    "법령": [c["인용"] for c in request["evidence"]["근거조항"]],
                    "참고": [c["인용"] for c in request["evidence"]["참고조항"]],
                    "계약서": [c["인용"] for c in request["evidence"]["계약서근거"]],
                    "자료": [r["명칭"] for r in request["evidence"]["참고자료"]],
                },
            }
        )

    return {
        "case_id": case_path.stem,
        "모델": MODEL,
        "규칙수": len(findings),
        "findings": findings,
    }


def dry_run(case_path: Path | str, only_failed: bool = True) -> None:
    """API를 호출하지 않고 전송될 내용을 그대로 보여준다."""
    case_path = Path(case_path)
    case = json.loads(case_path.read_text(encoding="utf-8"))
    requests = build_requests(case, Corpus.load(), only_failed)

    print(f"케이스: {case_path.stem}")
    print(f"설명 대상 규칙: {len(requests)}건 / 모델: {MODEL} (effort={EFFORT})\n")
    for request in requests:
        print("=" * 74)
        print(f"[{request['rule_id']}] {request['status']} · 성격={request['성격']}")
        print("=" * 74)
        print(request["user_message"])
        print()
    print(f"시스템 프롬프트 {len(SYSTEM)}자 + 요청 {len(requests)}건")


if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    flags = {a for a in sys.argv[1:] if a.startswith("--")}
    if not args:
        raise SystemExit(__doc__)

    if "--dry-run" in flags:
        dry_run(args[0], only_failed="--all" not in flags)
    else:
        result = explain_case(args[0], only_failed="--all" not in flags)
        print(json.dumps(result, ensure_ascii=False, indent=2))
