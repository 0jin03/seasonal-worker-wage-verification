from __future__ import annotations

from functools import lru_cache
from typing import Any

from law import casestudy
from law import explain
from law.retrieval import Corpus

from .holidays import env_value


@lru_cache(maxsize=1)
def _corpus() -> Corpus:
    return Corpus.load()


def build_legal_explanation(
    v6_result: dict[str, Any], case_id: str | None, language: str = "ko"
) -> dict[str, Any]:
    """규칙 판정을 바꾸지 않고 공식 근거와 사용자용 설명만 덧붙인다."""
    report = casestudy.build_case(v6_result, _corpus(), case_id or "case")
    api_key = env_value("OPENAI_API_KEY")
    llm_configured = bool(api_key)
    if llm_configured:
        # 키는 코드나 응답에 넣지 않고, 기존 호출 모듈의 메모리에만 전달한다.
        explain.API_KEY = api_key or ""
        system = explain.SYSTEM
        if language == "km":
            system += (
                "\n\n[출력 언어]\n모든 사용자용 문장은 자연스럽고 쉬운 캄보디아어(크메르어)로 작성함. "
                "Rule ID, 숫자, 날짜, 법령명과 조문 번호는 입력값을 그대로 유지함."
            )
        explain.explain_report(report, quiet=True, system=system)
    else:
        for section in report["불일치"]:
            section.setdefault("생성", "고정문구")
    fallback = any(section.get("생성") != "llm" for section in report["불일치"])
    report["llm"] = {
        "configured": llm_configured,
        "model": "gpt-4.1-mini",
        "fallback": fallback,
        "language": language,
    }
    return report
