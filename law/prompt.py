"""LLM 설명 프롬프트.

결정적 리포트(law/casestudy.py)가 만든 한 섹션을 입력으로 받아,
A담당 스펙의 출력 6항목을 생성한다.

    1 쉬운 설명   2 비교된 값   3 관련 공식 근거
    4 추가 확인사항   5 추가 질문   6 다음 행동

이 중 2·3은 결정적 레이어가 이미 확정해 둔 값이다.
LLM 에도 만들게 하되 리포트에 싣는 것은 결정적 값이고,
LLM 이 만든 쪽은 숫자나 인용이 어긋나지 않았는지 대조하는 데 쓴다(law/explain.py).
설명 원칙 2·3이 요구하는 "변경하지 않음"을 실제로 확인하는 장치다.

법령 조문·계약 조항·고시 금액은 코퍼스 원문을 그대로 싣기 때문에
리포트에서는 틀릴 여지가 없다.
"""

from __future__ import annotations

from pathlib import Path

PROMPT_PATH = Path(__file__).with_name("prompts") / "worker_explanation_v1.yaml"


def _load_prompt(path: Path = PROMPT_PATH) -> tuple[str, str]:
    """의존성 없이 버전 관리되는 단순 YAML 프롬프트를 읽는다."""
    lines = path.read_text(encoding="utf-8").splitlines()
    version = next(line.split(":", 1)[1].strip() for line in lines if line.startswith("version:"))
    start = next(i for i, line in enumerate(lines) if line.startswith("system:")) + 1
    system = "\n".join(line[2:] if line.startswith("  ") else line for line in lines[start:]).strip()
    if not version or not system:
        raise ValueError(f"프롬프트 파일 형식이 올바르지 않습니다: {path}")
    return version, system


PROMPT_VERSION, SYSTEM = _load_prompt()

LEGACY_SYSTEM = """너는 외국인 계절근로자가 자신의 근로계약·근무·급여 자료를
쉽게 이해할 수 있도록 설명하는 AI임.

R00~R11 규칙 엔진의 판정은 이미 완료된 상태임.
판정을 새로 계산하거나 임의로 변경하지 않음.

[입력]
- Rule ID
- 판정 결과
- 판정 사유
- 실제 비교된 값
- 관련 공식 근거
- 추가 확인이 필요한 정보

[설명 원칙]

1. 어떤 문서의 어떤 값이 서로 다른지 가장 먼저 설명함.
2. 입력된 금액·시간·날짜·판정 결과를 변경하지 않음.
3. 제공된 공식 근거 안에서만 법령 및 제도 내용을 설명함.
4. 입력에 없는 사실이나 불일치 원인을 임의로 추측하지 않음.
5. 문서 간 불일치와 법 위반 여부를 구분함.
6. 업종·사업장 조건·계약내용 등에 따라 적용 여부가 달라질 수 있는 경우
   법 위반이라고 단정하지 않고 추가 확인이 필요하다고 설명함.
7. R05~R07과 같은 계산 검산 결과는 계산 또는 작성 내용의
   확인이 필요하다는 방식으로 설명함.
8. 추가 질문은 결과 해석을 위해 필요한 경우에만 생성함.
9. 이미 입력값으로 확인된 내용은 다시 질문하지 않음.
10. 입력에 없는 수당명, 계약변경, 사건, 동의 여부 등을 임의로 만들어내지 않음.
11. 전문적인 법률용어는 가능한 한 쉬운 한국어로 풀어 설명함.
12. 현재 자료만으로 법적 판단이 어려운 경우 그 한계를 함께 안내함.

[출력]

1. 쉬운 설명
2. 비교된 값
3. 관련 공식 근거
4. 추가 확인사항
5. 필요한 경우 추가 질문
6. 다음 행동

[판정 성격별 설명 수위]  ← 원칙 5·6·7을 규칙마다 적용하는 기준

법적기준   법령이 직접 정한 의무와 관련됨. 위반 가능성을 말할 수 있으나
           이 결과만으로 위반이 확정된 것은 아니라고 반드시 함께 밝힘.
문서정합성  문서에 적힌 값이 서로 다르다는 뜻임. 값이 다르다는 사실 자체는
           법 위반이 아님. 어느 쪽이 맞는지 확인하는 것이 먼저라고 씀.
산술검산   임금명세서 안의 계산이 맞는지 확인한 결과임. 법령이 이 계산식을
           정한 것이 아니므로 작성 내용 확인이 필요하다는 뜻으로만 씀.
시스템규칙  문서들을 같은 사례로 묶기 위한 절차임. 법적 판단이 아니라고 밝힘.

[작성 방식]
- 금지표현으로 지정된 말은 어떤 형태로도 쓰지 않음.
- 다음 행동에는 근로자가 직접 할 수 있는 일만 씀.
  사업주나 기관이 해야 할 일을 근로자의 행동으로 쓰지 않음.
- 추가 확인사항은 시스템이 판단할 수 없는 한계를 밝히는 것이고,
  추가 질문은 근로자에게 직접 묻는 문장임.
  확인이 필요한 사항이 있으면 그것을 근로자에게 묻는 질문으로도 만듦.
- 다음 행동은 서로 다른 행동만 씀. 같은 내용을 나눠 쓰지 않음.
  쓸 것이 2개뿐이면 2개만 씀. 개수를 채우려고 일반적인 조언을 넣지 않음.
- 각 항목은 완결된 한 문장으로 씀. 짧은 문장을 씀.
- 쉬운 설명 1~3문장. 비교된 값은 어긋난 항목만. 다음 행동 2~4개. 추가 질문 0~2개."""


# OpenAI Structured Outputs(strict) 규격.
# strict 모드는 모든 속성이 required 여야 하고 additionalProperties 를 허용하지 않는다.
OUTPUT_SCHEMA = {
    "type": "object",
    "properties": {
        "쉬운설명": {
            "type": "array",
            "description": "어떤 문서의 어떤 값이 어떻게 다른지, 그것이 무슨 뜻인지.",
            "items": {"type": "string"},
        },
        "비교된값": {
            "type": "array",
            "description": "어긋난 항목만. 입력에 있는 값을 그대로 쓴다. 새로 계산하지 않는다.",
            "items": {"type": "string"},
        },
        "관련공식근거": {
            "type": "array",
            "description": "입력의 근거 목록에서 이 판정에 실제로 쓰인 것. 조문을 새로 지어내지 않는다.",
            "items": {"type": "string"},
        },
        "추가확인사항": {
            "type": "array",
            "description": "현재 자료만으로 판단할 수 없는 부분과 그 한계.",
            "items": {"type": "string"},
        },
        "추가질문": {
            "type": "array",
            "description": "결과 해석에 필요한 경우에만. 이미 확인된 내용은 묻지 않는다.",
            "items": {"type": "string"},
        },
        "다음행동": {
            "type": "array",
            "description": "근로자가 직접 할 수 있는 일만. 순서대로.",
            "items": {"type": "string"},
        },
    },
    "required": ["쉬운설명", "비교된값", "관련공식근거", "추가확인사항", "추가질문", "다음행동"],
    "additionalProperties": False,
}

# 출력 6항목 전부.
FIELDS = ("쉬운설명", "비교된값", "관련공식근거", "추가확인사항", "추가질문", "다음행동")

# 리포트에 싣는 항목 ← LLM 출력 항목.
# 비교된값·관련공식근거는 싣지 않는다. 결정적 값이 이미 있고 그쪽이 원본이다.
REPORT_MAP = {
    "해석": "쉬운설명",
    "대응": "다음행동",
    "질문": "추가질문",
    "확인사항": "추가확인사항",
}

# 대조용 항목. 결정적 값과 어긋나면 그 섹션은 고정 문구로 되돌린다.
CHECK_FIELDS = ("비교된값", "관련공식근거")


def _citations(section: dict) -> list[str]:
    """근거 인용 목록. 본문은 앞부분만 넣는다.

    LLM 이 조문 전문을 옮겨 적지 않게 하되, 무엇이 근거인지는 알아야
    설명이 근거와 어긋나지 않는다(원칙 3).
    """
    lines: list[str] = []
    for key, mark in (("근거조항", "1차"), ("참고조항", "참고"), ("조건부조항", "조건부"), ("검색조항", "BM25 보조검색")):
        for c in section.get(key) or []:
            body = c["본문"]
            body = body[:120] + "…" if len(body) > 120 else body
            line = f"  [{mark}] {c['인용']} — {body}"
            if c.get("적용조건"):
                line += f" (적용조건: {c['적용조건']})"
            lines.append(line)
    for c in section.get("계약서근거") or []:
        lines.append(f"  [계약서] {c['인용']} — {c['확인내용']}")
    for r in section.get("참고자료") or []:
        line = f"  [자료] {r['발행처']} 「{r['명칭']}」"
        if r.get("기준값"):
            기준 = r["기준값"]
            line += f" — 시간급 {기준['시간급']:,}원 (적용 {기준['적용기간']})"
        lines.append(line)
    return lines


def build_user_message(report: dict, section: dict) -> str:
    """한 규칙의 판정 결과를 LLM 입력 텍스트로 만든다."""
    out: list[str] = []

    out.append("[사례]")
    out.append(f"  근로자 {report.get('근로자', '')} · 사업장 {report.get('사업장', '')}")
    out.append(f"  산정기간 {report.get('산정기간', '')}")

    out.append("")
    out.append("[Rule ID]")
    out.append(f"  {section['rule_id']} — {section['검사내용']}")
    out.append(f"  판정 성격 {section['성격']}")

    out.append("")
    out.append("[판정 결과]")
    out.append(f"  {section['판정']}")

    out.append("")
    out.append("[판정 사유]")
    out.append(f"  {section['판정사유']}")

    out.append("")
    out.append("[실제 비교된 값]")
    if section.get("비교값"):
        out.append("  ← 표시가 붙은 것이 허용 범위를 벗어난 값이다")
        for 항목, 값, 출처, 강조 in section["비교값"]:
            mark = "  ←" if 강조 else ""
            out.append(f"  {항목}: {값} ({출처}){mark}")
    else:
        out.append("  없음")

    if section.get("허용오차"):
        values = " / ".join(v for _, v in section["허용오차"])
        out.append("")
        out.append(f"  허용오차 {values}")
        out.append("  법이 허용하는 범위가 아니라 반올림·환산 차이를 감안한 시스템 내부 비교 기준이다.")
        out.append("  이것을 '법적으로 허용되는 범위'라고 설명하면 안 된다.")

    citations = _citations(section)
    missing = bool(section.get("근거미발견"))
    out.append("")
    out.append("[근거 검색 상태]")
    out.append(f"  근거미발견: {'true' if missing else 'false'}")
    if missing:
        out.append("  근거 조문을 찾지 못했습니다. 제공되지 않은 조문을 생성하지 말 것.")
        for item in section.get("미발견근거") or []:
            out.append(f"  미발견: {item}")
    out.append("")
    out.append("[관련 공식 근거]")
    if citations:
        out.extend(citations)
        out.append("  조문 전문을 옮겨 적지 말고, 어느 근거가 쓰였는지만 밝힐 것.")
    else:
        out.append("  없음. 직접 대응하는 법령이 없는 규칙이다. 법적 근거를 지어내지 말 것.")

    out.append("")
    out.append("[추가 확인이 필요한 정보]")
    if section.get("검토필요"):
        out.append(f"  {section['검토필요']}")
        out.append("  확정된 것처럼 설명하지 말 것. 근로자가 직접 해결할 일로 쓰지 말 것.")
    else:
        out.append("  없음")

    if section.get("금지표현"):
        out.append("")
        out.append("[금지표현]  ← 어떤 형태로도 쓰지 말 것")
        for word in section["금지표현"]:
            out.append(f"  {word}")

    out.append("")
    out.append("위 내용으로 출력 6항목을 만들어라.")
    return "\n".join(out)
