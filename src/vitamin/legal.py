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
            # 원본 프롬프트의 '쉬운 한국어' 지시와 충돌하지 않게 언어 지시를
            # 교체하고, 최우선 제약을 앞뒤에 모두 둔다.
            system = system.replace("쉬운 한국어", "쉬운 캄보디아어(크메르어)")
            language_rule = (
                "[최우선 출력 언어 규칙]\n"
                "JSON 키를 제외한 모든 사용자용 문장은 반드시 캄보디아어(크메르어)로 작성함. "
                "한국어 문장을 출력하지 않음. 사람 이름, Rule ID, 숫자, 날짜, 법령명과 조문 번호만 입력값을 유지함.\n\n"
            )
            system = language_rule + system + "\n\n" + language_rule
        explain.explain_report(report, quiet=True, system=system)
    else:
        for section in report["불일치"]:
            section.setdefault("생성", "고정문구")
    fallback = any(section.get("생성") != "llm" for section in report["불일치"])
    report["llm"] = {
        "configured": llm_configured,
        "model": "gpt-4.1-mini",
        "temperature": explain.TEMPERATURE,
        "prompt_version": explain.PROMPT_VERSION,
        "fallback": fallback,
        "language": language,
    }
    return report
