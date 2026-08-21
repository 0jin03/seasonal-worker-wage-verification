"""결정적 리포트의 해석·대응·질문을 케이스 값에 맞춰 다시 쓴다 (GPT API).

law/casestudy.py 가 만든 리포트를 그대로 받아, 세 항목만 LLM 으로 교체한다.

    비교된 값 · 법령 조문 · 계약 조항 · 고시 금액   그대로 둔다 (결정적)
    해석 · 대응 · 질문                              LLM 이 케이스 값을 보고 생성

고정 문구는 규칙 ID 와 판정 상태만 보고 고르기 때문에 케이스에 안 맞는 안내가 섞인다.
예: 근로자명이 네 문서 모두 일치하는데도 "이름 철자가 다르면 정정을 요청하세요"가 나간다.
실제로 어긋난 항목을 보고 써야 하는 문장이라 LLM 이 필요하다.

호출이 실패하거나 키가 없으면 고정 문구를 그대로 쓴다. 리포트는 항상 나온다.

    python -m law.explain 예시케이스/CASE-2026-10-0029.json
    python -m law.explain 예시케이스/*.json --md=케이스리포트_llm
    python -m law.explain 예시케이스/*.json --json
    python -m law.explain 예시케이스/*.json --dry-run    # 전송 내용만 확인, 호출 없음
"""

from __future__ import annotations

import json
import os
import re
import ssl
import sys
import time
import urllib.error
import urllib.request

from law import casestudy, guidance
from law.prompt import (
    CHECK_FIELDS,
    FIELDS,
    OUTPUT_SCHEMA,
    REPORT_MAP,
    SYSTEM,
    build_user_message,
)
from law.retrieval import Corpus


# API 키는 코드에 저장하지 않고 OPENAI_API_KEY 환경변수로 주입한다.
API_KEY = ""

MODEL = "gpt-4.1-mini"

# ─────────────────────────────────────────────────────────────────────

ENDPOINT = "https://api.openai.com/v1/chat/completions"
TIMEOUT = 120
RETRY = 3
RETRY_WAIT = 2.0

# 사실을 옮겨 적는 작업이라 창의성 필요 없음 그냥 낮게 설정
TEMPERATURE = 0.2


class ExplainError(RuntimeError):
    """LLM 호출이 실패한 경우."""


def _ssl_context() -> ssl.SSLContext:
    """CA 번들을 명시적으로 지정한다.

    python.org 설치본은 'Install Certificates.command'를 실행하지 않으면
    cert.pem 이 없어 모든 HTTPS 검증이 실패한다. law/client.py 와 같은 이유다.
    """
    try:
        import certifi

        return ssl.create_default_context(cafile=certifi.where())
    except ImportError:
        return ssl.create_default_context()


def api_key() -> str:
    key = API_KEY or os.environ.get("OPENAI_API_KEY", "")
    if not key:
        raise ExplainError(
            "API 키가 없습니다.\n"
            "  law/explain.py 의 API_KEY 를 채우거나\n"
            '  export OPENAI_API_KEY="sk-..." 를 실행하세요.'
        )
    return key


def model_name() -> str:
    if not MODEL:
        raise ExplainError(
            "모델 이름이 없습니다. law/explain.py 의 MODEL 을 채우세요.\n"
            '  예: MODEL = "gpt-4o"'
        )
    return MODEL


def request_body(system: str, user: str, temperature: float | None = TEMPERATURE) -> dict:
    """Structured Outputs 로 세 항목만 받는다.

    strict 모드라 스키마에 없는 키가 섞이거나 항목이 빠질 수 없다.
    추론 모델은 temperature 를 받지 않으므로 None 이면 넣지 않는다.
    """
    return {
        "model": model_name(),
        **({"temperature": temperature} if temperature is not None else {}),
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        "response_format": {
            "type": "json_schema",
            "json_schema": {
                "name": "wage_explanation",
                "strict": True,
                "schema": OUTPUT_SCHEMA,
            },
        },
    }


def _post(body: dict) -> str:
    request = urllib.request.Request(
        ENDPOINT,
        data=json.dumps(body, ensure_ascii=False).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {api_key()}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=TIMEOUT, context=_ssl_context()) as response:
        return response.read().decode("utf-8")


def call_llm(system: str, user: str) -> dict:
    """한 번 호출해 파싱된 결과를 돌려준다."""
    temperature: float | None = TEMPERATURE
    last: Exception | None = None

    for attempt in range(RETRY):
        try:
            raw = _post(request_body(system, user, temperature))
            break
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", "replace")[:400]
            # 추론 모델은 temperature 를 거부한다. 빼고 한 번 더 보낸다.
            if exc.code == 400 and temperature is not None and "temperature" in detail:
                temperature = None
                continue
            # 그 밖의 4xx 는 다시 보내도 같은 결과다.
            if exc.code < 500 and exc.code != 429:
                raise ExplainError(f"HTTP {exc.code}\n{detail}") from exc
            last = ExplainError(f"HTTP {exc.code}\n{detail}")
            if attempt < RETRY - 1:
                time.sleep(RETRY_WAIT * (attempt + 1))
        except (urllib.error.URLError, TimeoutError) as exc:
            last = exc
            if attempt < RETRY - 1:
                time.sleep(RETRY_WAIT * (attempt + 1))
    else:
        raise ExplainError(f"호출 실패: {last}")

    body = json.loads(raw)
    choice = body["choices"][0]
    message = choice["message"]

    # 안전장치나 길이 제한으로 잘리면 JSON 이 깨진 채로 온다.
    if message.get("refusal"):
        raise ExplainError(f"모델이 응답을 거절했습니다: {message['refusal']}")
    if choice.get("finish_reason") not in (None, "stop"):
        raise ExplainError(f"응답이 완결되지 않았습니다: {choice.get('finish_reason')}")

    try:
        return json.loads(message["content"])
    except json.JSONDecodeError as exc:
        raise ExplainError(f"JSON 이 아닙니다:\n{message['content'][:400]}") from exc


def clean(value) -> list[str]:
    """모델 출력을 문자열 목록으로 정리한다."""
    if isinstance(value, str):
        value = [value]
    return [" ".join(str(v).split()) for v in (value or []) if str(v).strip()]


NUMBER = re.compile(r"\d[\d,]*")


def known_numbers(section: dict) -> set[str]:
    """이 섹션에 실제로 등장하는 숫자. 대조 기준이다."""
    text = " ".join(
        [section["판정사유"]]
        + [f"{항목} {값}" for 항목, 값, _, _ in section.get("비교값") or []]
    )
    return {m.group().replace(",", "").lstrip("0") or "0" for m in NUMBER.finditer(text)}


def check_numbers(section: dict, filled: dict) -> list[str]:
    """LLM 이 만든 '비교된값'에 없는 숫자가 섞였는지 본다.

    설명 원칙 2가 요구하는 '입력된 금액·시간·날짜를 변경하지 않음'을 실제로 확인한다.
    리포트에 싣는 것은 결정적 값이지만, 대조에서 어긋나면 쉬운설명 쪽도 믿을 수 없다.
    한 자리 수는 순서 표기('1.', '2번')로 흔히 나오므로 세 자리 이상만 본다.
    """
    known = known_numbers(section)
    unknown: list[str] = []
    for line in filled.get("비교된값", []):
        for m in NUMBER.finditer(line):
            raw = m.group().replace(",", "")
            if len(raw) < 3:
                continue
            if (raw.lstrip("0") or "0") not in known:
                unknown.append(m.group())
    return unknown


def check_forbidden(section: dict, filled: dict) -> list[str]:
    """금지표현이 섞였는지 확인한다.

    프롬프트로 막아도 새어 나올 수 있다. 새어 나오면 그 규칙은 LLM 결과를 버리고
    고정 문구로 되돌린다. 임금 문제를 잘못 단정하는 것보다 밋밋한 편이 낫다.
    """
    text = " ".join(" ".join(filled.get(f, [])) for f in FIELDS)
    return [word for word in section.get("금지표현") or () if word in text]


def explain_section(report: dict, section: dict) -> tuple[bool, str]:
    """한 규칙의 설명 6항목을 만들어 리포트에 반영한다. (성공여부, 사유)"""
    user = build_user_message(report, section)
    try:
        result = call_llm(SYSTEM, user)
    except ExplainError as exc:
        return False, str(exc).split("\n")[0]

    filled = {field: clean(result.get(field)) for field in FIELDS}
    if not filled["쉬운설명"] or not filled["다음행동"]:
        return False, "쉬운설명 또는 다음행동이 비어 있음"

    leaked = check_forbidden(section, filled)
    if leaked:
        return False, f"금지표현 사용: {', '.join(leaked)}"

    unknown = check_numbers(section, filled)
    if unknown:
        return False, f"입력에 없는 숫자: {', '.join(unknown[:3])}"

    # 리포트에 싣는 것은 결정적 값이다. 비교된값·관련공식근거는 대조용으로만 보관한다.
    for 리포트항목, 출력항목 in REPORT_MAP.items():
        section[리포트항목] = filled[출력항목]

    # 판정을 끝내지 못한 경우에는 무엇이 부족한지 반드시 알려야 한다.
    if section["판정"] in ("NOT_CHECKABLE", "NOT_EVALUABLE") and not section["확인사항"]:
        section["확인사항"] = list(guidance.MISSING_INFO)

    section["대조"] = {f: filled[f] for f in CHECK_FIELDS}
    section["생성"] = "llm"
    return True, ""


def explain_report(report: dict, quiet: bool = False) -> dict:
    """리포트의 모든 불일치 섹션을 LLM 설명으로 바꾼다."""
    for section in report["불일치"]:
        section.setdefault("생성", "고정문구")
        ok, reason = explain_section(report, section)
        if not quiet:
            mark = "생성" if ok else f"고정문구 ({reason})"
            print(f"  {report['case_id']} {section['rule_id']:<4} {mark}", file=sys.stderr)
    return report


def dry_run(report: dict) -> str:
    """호출 없이 전송될 내용을 보여준다."""
    out = [f"SYSTEM ({len(SYSTEM)}자)", "─" * 78, SYSTEM, ""]
    for section in report["불일치"]:
        user = build_user_message(report, section)
        out += [
            "",
            f"USER — {report['case_id']} {section['rule_id']} ({len(user)}자)",
            "─" * 78,
            user,
        ]
    out += [
        "",
        "─" * 78,
        f"모델 {MODEL or '(미설정)'} · 키 {'설정됨' if (API_KEY or os.environ.get('OPENAI_API_KEY')) else '없음'}",
        f"요청 {len(report['불일치'])}건 (섹션당 1회)",
    ]
    return "\n".join(out)


if __name__ == "__main__":
    args = sys.argv[1:]
    paths = [a for a in args if not a.startswith("--")]
    flags = [a for a in args if a.startswith("--")]
    if not paths:
        raise SystemExit(__doc__)

    corpus = Corpus.load()
    reports = [casestudy.build(p, corpus) for p in paths]

    if "--dry-run" in flags:
        for report in reports:
            print(dry_run(report))
        raise SystemExit(0)

    for report in reports:
        explain_report(report)

    md_flag = next((f for f in flags if f == "--md" or f.startswith("--md=")), None)
    if md_flag is not None:
        out_dir = md_flag.split("=", 1)[1] if "=" in md_flag else "케이스리포트"
        for path in casestudy.write_markdown(reports, out_dir):
            print(f"  {path}")
    elif "--json" in flags:
        print(json.dumps(reports, ensure_ascii=False, indent=2))
    else:
        for report in reports:
            print(casestudy.render(report))
