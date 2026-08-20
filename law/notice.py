"""고시·별지서식 수집.

법령 본문 API(law/collect.py)로 받을 수 없는 두 가지를 따로 모은다.

    최저임금 고시    행정규칙 API가 '조문내용'을 빈 문자열로 주고 본문은 PDF 첨부에만 있다.
                    R11 의 판정 기준값(시간급 최저임금액)이 여기 들어 있다.
    별지 제3호서식   조문이 아니라 별표·서식이라 target=licbyl 로 찾아야 한다.
                    표준 계절근로계약서의 항 번호 근거다(law/contract.py).

    export LAW_OC="발급받은OC"
    python -m law.notice              # API 호출 + PDF 내려받기 + 파싱
    python -m law.notice --rebuild    # 내려받은 PDF만으로 재파싱 (API 호출 없음)

산출물:
    법령데이터/고시/<연도>년_적용_최저임금_고시.pdf   원본
    법령데이터/고시/최저임금.json                   연도별 시간급·월환산액·적용기간
    법령데이터/서식/표준_계절근로계약서_별지제3호서식.pdf  원본
    법령데이터/서식/index.json                     서식 메타
"""

from __future__ import annotations

import json
import re
import sys
from functools import lru_cache
from pathlib import Path

from law.client import LawApiError, download, fetch_admrul, search_admrul, search_licbyl

NOTICE_DIR = Path("법령데이터/고시")
FORM_DIR = Path("법령데이터/서식")
WAGE_PATH = NOTICE_DIR / "최저임금.json"
FORM_INDEX = FORM_DIR / "index.json"

# 「최저임금법」 제10조제1항에 따라 고용노동부장관이 매년 8월 5일까지 고시한다.
NOTICE_QUERY = "적용 최저임금 고시"
NOTICE_MINISTRY = "고용노동부"
# '최저임금안 고시'(심의 중인 안)와 '선원 최저임금 고시'(해양수산부)를 걸러낸다.
NOTICE_NAME = re.compile(r"^(\d{4})년 적용 최저임금 고시$")

FORM_QUERY = "표준 계절근로계약서"
FORM_NUMBER = "000300"  # 별지 제3호서식


# --- PDF 파싱 ---------------------------------------------------------

def pdf_text(path: Path) -> str:
    """PDF 전체 텍스트를 공백 없이 잇는다.

    고시 PDF는 자간이 글자 단위로 벌어져 있어 '1 0 ,3 2 0원'처럼 추출된다.
    공백을 모두 지워야 숫자를 온전히 읽을 수 있다.
    """
    try:
        import pypdf
    except ImportError as exc:
        raise SystemExit("pypdf 가 필요합니다: pip install pypdf") from exc

    reader = pypdf.PdfReader(path)
    return "".join("".join(page.extract_text().split()) for page in reader.pages)


def _number(text: str, pattern: str) -> int | None:
    match = re.search(pattern, text)
    return int(match.group(1).replace(",", "")) if match else None


def parse_wage_notice(text: str) -> dict:
    """최저임금 고시 본문에서 판정에 쓰는 값을 뽑는다."""
    번호 = re.search(r"고용노동부고시제(\d{4})[–\-−‑](\d+)호", text)
    기간 = re.search(
        r"최저임금적용기간[:：]?(\d{4})\.(\d{1,2})\.(\d{1,2})\.?~(\d{4})\.(\d{1,2})\.(\d{1,2})",
        text,
    )
    parsed = {
        "고시번호": f"고용노동부 고시 제{번호.group(1)}-{번호.group(2)}호" if 번호 else None,
        # '시간급' 뒤에 업종 구분(모든산업)이 끼어 있어 사이를 건너뛴다.
        "시간급": _number(text, r"시간급[^\d]{0,20}([\d,]{5,})원"),
        "월환산액": _number(text, r"월환산액([\d,]+)원"),
        "월환산기준시간수": _number(text, r"월환산기준시간수(\d+)시간"),
        "업종별구분": "없음" if "구분없이모든사업장에동일하게적용" in text else "확인필요",
    }
    if 기간:
        y1, m1, d1, y2, m2, d2 = 기간.groups()
        parsed["적용시작"] = f"{y1}-{int(m1):02d}-{int(d1):02d}"
        parsed["적용종료"] = f"{y2}-{int(m2):02d}-{int(d2):02d}"
    return parsed


# --- 수집 -------------------------------------------------------------

def collect_wage_notices() -> dict:
    """최저임금 고시를 연도별로 수집한다."""
    NOTICE_DIR.mkdir(parents=True, exist_ok=True)
    notices: dict[str, dict] = {}

    for hit in search_admrul(NOTICE_QUERY):
        name = str(hit.get("행정규칙명") or "").strip()
        matched = NOTICE_NAME.match(name)
        if not matched or str(hit.get("소관부처명") or "").strip() != NOTICE_MINISTRY:
            continue

        year = matched.group(1)
        detail = fetch_admrul(str(hit.get("행정규칙일련번호")))
        basic = detail.get("행정규칙기본정보", {})
        attachments = detail.get("첨부파일", {})
        links = attachments.get("첨부파일링크") or []
        names = attachments.get("첨부파일명") or []
        links = links if isinstance(links, list) else [links]
        names = names if isinstance(names, list) else [names]

        # 첨부가 여럿인 해가 있다(예: 2026년은 '재개정 이유서'가 함께 온다).
        # 고시 본문만 고른다.
        pair = next(
            ((l, n) for l, n in zip(links, names) if "최저임금 고시" in n and "이유서" not in n),
            None,
        )
        if pair is None:
            print(f"  [본문 없음] {name} — 첨부 {names}", file=sys.stderr)
            continue

        path = NOTICE_DIR / f"{year}년_적용_최저임금_고시.pdf"
        path.write_bytes(download(pair[0]))

        notices[year] = {
            "연도": int(year),
            "행정규칙명": name,
            "행정규칙일련번호": str(hit.get("행정규칙일련번호")),
            "발령일자": str(basic.get("발령일자") or ""),
            "시행일자": str(basic.get("시행일자") or ""),
            "현행여부": str(basic.get("현행여부") or ""),
            "원본파일": str(path),
            **parse_wage_notice(pdf_text(path)),
        }
        print(f"  {name:<24} 시간급 {notices[year]['시간급']:,}원  ({notices[year]['고시번호']})")

    return notices


def collect_forms() -> list[dict]:
    """표준 계절근로계약서 별지 서식을 수집한다."""
    FORM_DIR.mkdir(parents=True, exist_ok=True)
    forms: list[dict] = []

    for hit in search_licbyl(FORM_QUERY):
        if str(hit.get("별표번호") or "") != FORM_NUMBER:
            continue
        link = hit.get("별표서식PDF파일링크") or hit.get("별표서식파일링크")
        if not link:
            continue

        path = FORM_DIR / "표준_계절근로계약서_별지제3호서식.pdf"
        path.write_bytes(download(str(link)))

        forms.append(
            {
                "별표명": str(hit.get("별표명") or ""),
                "별표번호": FORM_NUMBER,
                "관련법령명": str(hit.get("관련법령명") or ""),
                "법령종류": str(hit.get("법령종류") or ""),
                "공포일자": str(hit.get("공포일자") or ""),
                "별표일련번호": str(hit.get("별표일련번호") or ""),
                "원본파일": str(path),
                "항목": form_items(pdf_text(path)),
            }
        )
        print(f"  {forms[-1]['별표명']:<32} 항목 {len(forms[-1]['항목'])}개 (공포 {forms[-1]['공포일자']})")

    return forms


# 서식 본문의 '1. 근로계약기간' ~ '13. …' 머리 항목. 한글 사이 공백이 벌어져 있다.
FORM_ITEM = re.compile(r"(?<![0-9])(1[0-3]|[1-9])\.([가-힣]{2,12})(?=[A-Za-z\[(※])")


def form_items(text: str) -> dict[str, str]:
    """서식의 항 번호와 이름을 뽑는다. contract.py 의 공식항 검증용이다."""
    items: dict[str, str] = {}
    for match in FORM_ITEM.finditer(text):
        items.setdefault(match.group(1), match.group(2))
    return items


# --- 조회 -------------------------------------------------------------

@lru_cache(maxsize=1)
def wage_notices(path: str | Path = WAGE_PATH) -> dict[str, dict]:
    path = Path(path)
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def minimum_wage(year: int | str) -> dict | None:
    """해당 연도에 적용되는 최저임금 고시. 없으면 None."""
    return wage_notices().get(str(year))


# --- 실행 -------------------------------------------------------------

def write(notices: dict, forms: list[dict]) -> None:
    if notices:
        NOTICE_DIR.mkdir(parents=True, exist_ok=True)
        WAGE_PATH.write_text(
            json.dumps(dict(sorted(notices.items())), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        print(f"\n고시 {len(notices)}건 → {WAGE_PATH}")
    if forms:
        FORM_DIR.mkdir(parents=True, exist_ok=True)
        FORM_INDEX.write_text(json.dumps(forms, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"서식 {len(forms)}건 → {FORM_INDEX}")


def rebuild() -> None:
    """API 없이 내려받아 둔 PDF만으로 다시 파싱한다."""
    notices = {n["연도"]: n for n in wage_notices().values()}
    for year, notice in notices.items():
        path = Path(notice["원본파일"])
        if path.exists():
            notice.update(parse_wage_notice(pdf_text(path)))
            print(f"  {year}년  시간급 {notice['시간급']:,}원")

    forms = json.loads(FORM_INDEX.read_text(encoding="utf-8")) if FORM_INDEX.exists() else []
    for form in forms:
        path = Path(form["원본파일"])
        if path.exists():
            form["항목"] = form_items(pdf_text(path))
            print(f"  {form['별표명']}  항목 {len(form['항목'])}개")

    write({str(y): n for y, n in notices.items()}, forms)


if __name__ == "__main__":
    if "--rebuild" in sys.argv[1:]:
        rebuild()
    else:
        try:
            write(collect_wage_notices(), collect_forms())
        except LawApiError as exc:
            raise SystemExit(f"수집 실패: {exc}")
