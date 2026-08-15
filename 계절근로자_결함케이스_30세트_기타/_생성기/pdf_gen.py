# -*- coding: utf-8 -*-
"""20개 계절근로자 결함 케이스의 4종 합성 PDF를 생성한다.

JSON의 documents 원본 피처를 문서에 그대로 옮기고, 현재 v3.2 JSON
스키마에 없는 국적ㆍ생년월일ㆍ여권번호ㆍ주소ㆍ계좌번호 등은 문서 양식용
결정적(deterministic) 합성값으로 보완한다.

필요 패키지: pymupdf, fonttools (macOS 한글 폰트의 굵은 글꼴 추출용)
"""

from __future__ import annotations

import argparse
import calendar
import hashlib
import json
import tempfile
from datetime import date, datetime, timedelta
from pathlib import Path

import pymupdf as fitz


A4 = (595.0, 842.0)
ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CASE_ROOT = ROOT / "계절근로자_결함케이스_20세트"

BLACK = (0.08, 0.08, 0.08)
WHITE = (1.0, 1.0, 1.0)
GRID = (0.45, 0.49, 0.51)
LIGHT_GRAY = (0.94, 0.95, 0.95)
PALE_BLUE = (0.92, 0.95, 0.98)
PALE_BLUE_2 = (0.86, 0.91, 0.96)
NAVY = (0.09, 0.24, 0.40)
BLUE = (0.13, 0.36, 0.58)
GREEN = (0.08, 0.38, 0.28)

DAY_KO = {
    "MON": "월요일",
    "TUE": "화요일",
    "WED": "수요일",
    "THU": "목요일",
    "FRI": "금요일",
    "SAT": "토요일",
    "SUN": "일요일",
}
WEEKDAY_KO = "월화수목금토일"
WAGE_KO = {"hourly": "시급제", "daily": "일급제", "weekly": "주급제", "monthly": "월급제"}
HOLIDAY_KO = {
    "weekly_sunday": "주휴일 매주 일요일",
    "weekly_sunday_and_agreed_holidays": "주휴일 매주 일요일 / 약정 휴일",
}

# specs.py의 케이스 설명에 명시된 국적. 국적은 v3.2 JSON 스키마에 없으므로
# PDF 양식에서만 사용하는 보조정보다.
COUNTRIES = {
    "0012": ("캄보디아", "Cambodia"),
    "0013": ("캄보디아", "Cambodia"),
    "0014": ("캄보디아", "Cambodia"),
    "0015": ("캄보디아", "Cambodia"),
    "0016": ("캄보디아", "Cambodia"),
    "0017": ("캄보디아", "Cambodia"),
    "0018": ("캄보디아", "Cambodia"),
    "0019": ("캄보디아", "Cambodia"),
    "0020": ("캄보디아", "Cambodia"),
    "0021": ("캄보디아", "Cambodia"),
    "0022": ("캄보디아", "Cambodia"),
    "0023": ("캄보디아", "Cambodia"),
    "0024": ("캄보디아", "Cambodia"),
    "0025": ("캄보디아", "Cambodia"),
    "0026": ("캄보디아", "Cambodia"),
    "0027": ("캄보디아", "Cambodia"),
    "0028": ("캄보디아", "Cambodia"),
    "0029": ("캄보디아", "Cambodia"),
    "0030": ("캄보디아", "Cambodia"),
    "0031": ("캄보디아", "Cambodia"),
}

# 표준근로계약서의 국적 표시는 전 케이스에서 동일하게 사용한다.
CONTRACT_NATIONALITY = ("캄보디아", "Cambodia")

LOCATIONS = [
    ("충청북도 진천군 이월면 계절로 27", "043", "시설하우스 채소 재배·수확 및 선별"),
    ("경상북도 영주시 문수면 들녘로 45", "054", "과수 재배·수확 및 저온창고 작업"),
    ("전라남도 나주시 봉황면 농산길 18", "061", "시설작물 재배·수확 및 포장"),
    ("강원특별자치도 평창군 진부면 수확길 62", "033", "고랭지 작물 재배·수확 및 운반"),
    ("충청남도 부여군 규암면 햇살로 103", "041", "딸기·채소 재배, 선별 및 포장"),
    ("전북특별자치도 고창군 대산면 농원길 31", "063", "과채류 관리·수확 및 출하 작업"),
    ("경상남도 밀양시 상남면 풍년로 76", "055", "시설원예 작물 재배·수확 및 포장"),
    ("제주특별자치도 서귀포시 남원읍 감귤로 88", "064", "과수 관리·수확 및 선별 작업"),
]
REPRESENTATIVES = ["김민수", "이정호", "박성진", "최영숙", "정해수", "윤태경", "한도윤", "서미경"]
PASSPORT_PREFIX = {
    "캄보디아": "N",
    "베트남": "C",
    "네팔": "PA",
    "태국": "AA",
    "우즈베키스탄": "FA",
    "필리핀": "P",
    "몽골": "E",
    "미얀마": "MD",
    "라오스": "P",
    "중국": "E",
    "인도네시아": "C",
    "키르기스스탄": "AC",
    "방글라데시": "A",
    "동티모르": "L",
    "스리랑카": "N",
}


def _font_files() -> tuple[str, str]:
    """사용 가능한 한글 Regular/Bold 글꼴 파일을 돌려준다."""
    mac_collection = Path("/System/Library/Fonts/AppleSDGothicNeo.ttc")
    if mac_collection.exists():
        cache = Path(tempfile.gettempdir()) / "seasonal_worker_pdf_fonts"
        regular = cache / "AppleSDGothicNeo-Regular.ttf"
        bold = cache / "AppleSDGothicNeo-Bold.ttf"
        if not regular.exists() or not bold.exists():
            cache.mkdir(parents=True, exist_ok=True)
            try:
                from fontTools.ttLib import TTCollection

                collection = TTCollection(str(mac_collection))
                collection.fonts[0].save(regular)
                collection.fonts[6].save(bold)
            except Exception:
                # fontTools를 쓸 수 없으면 TTC 첫 번째 서체를 두 용도로 쓴다.
                return str(mac_collection), str(mac_collection)
        return str(regular), str(bold)

    candidates = [
        (
            Path("/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc"),
            Path("/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc"),
        ),
        (
            Path("/usr/share/fonts/truetype/nanum/NanumGothic.ttf"),
            Path("/usr/share/fonts/truetype/nanum/NanumGothicBold.ttf"),
        ),
        (
            Path("/System/Library/Fonts/Supplemental/AppleGothic.ttf"),
            Path("/System/Library/Fonts/Supplemental/AppleGothic.ttf"),
        ),
    ]
    for regular, bold in candidates:
        if regular.exists():
            return str(regular), str(bold if bold.exists() else regular)
    raise RuntimeError("한글 PDF 생성에 사용할 글꼴을 찾을 수 없습니다.")


FONT_REGULAR, FONT_BOLD = _font_files()
MEASURE_REGULAR = fitz.Font(fontfile=FONT_REGULAR)
MEASURE_BOLD = fitz.Font(fontfile=FONT_BOLD)


def register_fonts(page: fitz.Page) -> None:
    page.insert_font(fontname="KR", fontfile=FONT_REGULAR)
    page.insert_font(fontname="KRB", fontfile=FONT_BOLD)


def _font(bold: bool) -> fitz.Font:
    return MEASURE_BOLD if bold else MEASURE_REGULAR


def _split_long_token(token: str, font: fitz.Font, fontsize: float, max_width: float) -> list[str]:
    parts: list[str] = []
    current = ""
    for ch in token:
        candidate = current + ch
        if current and font.text_length(candidate, fontsize=fontsize) > max_width:
            parts.append(current)
            current = ch
        else:
            current = candidate
    if current:
        parts.append(current)
    return parts or [""]


def wrap_text(text: object, max_width: float, fontsize: float, bold: bool = False) -> list[str]:
    value = "" if text is None else str(text)
    font = _font(bold)
    result: list[str] = []
    for paragraph in value.splitlines() or [""]:
        words = paragraph.split(" ")
        line = ""
        for word in words:
            pieces = _split_long_token(word, font, fontsize, max_width)
            for pos, piece in enumerate(pieces):
                candidate = piece if not line else line + (" " if pos == 0 else "") + piece
                if line and font.text_length(candidate, fontsize=fontsize) > max_width:
                    result.append(line)
                    line = piece
                else:
                    line = candidate
                if pos < len(pieces) - 1:
                    result.append(line)
                    line = ""
        result.append(line)
    return result or [""]


def draw_text(
    page: fitz.Page,
    rect: fitz.Rect | tuple[float, float, float, float],
    text: object,
    fontsize: float = 8,
    *,
    bold: bool = False,
    align: str = "left",
    color: tuple[float, float, float] = BLACK,
    padding: float = 3,
    max_lines: int | None = None,
    min_fontsize: float = 5,
) -> None:
    """셀 안에 가운데 세로정렬로 텍스트를 그린다."""
    rect = fitz.Rect(rect)
    value = "" if text is None else str(text)
    size = fontsize
    while size > min_fontsize:
        lines = wrap_text(value, max(1, rect.width - padding * 2), size, bold)
        line_height = size * 1.18
        if (max_lines is None or len(lines) <= max_lines) and len(lines) * line_height <= rect.height - 1:
            break
        size -= 0.25
    lines = wrap_text(value, max(1, rect.width - padding * 2), size, bold)
    if max_lines is not None:
        lines = lines[:max_lines]
    line_height = size * 1.18
    baseline = rect.y0 + max(0, (rect.height - line_height * len(lines)) / 2) + size
    font = _font(bold)
    fontname = "KRB" if bold else "KR"
    for index, line in enumerate(lines):
        width = font.text_length(line, fontsize=size)
        if align == "center":
            x = rect.x0 + (rect.width - width) / 2
        elif align == "right":
            x = rect.x1 - padding - width
        else:
            x = rect.x0 + padding
        page.insert_text((x, baseline + index * line_height), line, fontname=fontname, fontsize=size, color=color)


def draw_cell(
    page: fitz.Page,
    rect: fitz.Rect | tuple[float, float, float, float],
    text: object = "",
    *,
    fill: tuple[float, float, float] | None = None,
    border: tuple[float, float, float] = GRID,
    width: float = 0.55,
    fontsize: float = 8,
    bold: bool = False,
    align: str = "left",
    color: tuple[float, float, float] = BLACK,
    padding: float = 3,
    max_lines: int | None = None,
) -> None:
    rect = fitz.Rect(rect)
    page.draw_rect(rect, color=border, fill=fill, width=width, overlay=True)
    draw_text(
        page,
        rect,
        text,
        fontsize,
        bold=bold,
        align=align,
        color=color,
        padding=padding,
        max_lines=max_lines,
    )


def draw_row(
    page: fitz.Page,
    x: float,
    y: float,
    widths: list[float],
    height: float,
    values: list[object],
    *,
    fills: list[tuple[float, float, float] | None] | None = None,
    bolds: list[bool] | None = None,
    aligns: list[str] | None = None,
    fontsize: float = 8,
    colors: list[tuple[float, float, float]] | None = None,
) -> float:
    cursor = x
    for index, (cell_width, value) in enumerate(zip(widths, values)):
        draw_cell(
            page,
            (cursor, y, cursor + cell_width, y + height),
            value,
            fill=fills[index] if fills else None,
            bold=bolds[index] if bolds else False,
            align=aligns[index] if aligns else "left",
            fontsize=fontsize,
            color=colors[index] if colors else BLACK,
        )
        cursor += cell_width
    return y + height


def iso_date(value: str | None) -> date | None:
    return date.fromisoformat(value) if value else None


def dot_date(value: str | None) -> str:
    return value.replace("-", ".") if value else "해당 없음"


def ko_date(value: str | date | None) -> str:
    if value is None:
        return "해당 없음"
    d = value if isinstance(value, date) else date.fromisoformat(value)
    return f"{d.year}년 {d.month:02d}월 {d.day:02d}일"


def money(value: object) -> str:
    if value is None:
        return "판독불가"
    if isinstance(value, (int, float)):
        return f"{value:,.0f}"
    return str(value)


def number(value: object) -> str:
    if value is None:
        return "-"
    if isinstance(value, float):
        return f"{value:g}"
    return str(value)


def actual_hours(line: dict) -> float:
    start_h, start_m = map(int, line["ts_work_start_time"].split(":"))
    end_h, end_m = map(int, line["ts_work_end_time"].split(":"))
    minutes = end_h * 60 + end_m - (start_h * 60 + start_m)
    if minutes <= 0:
        minutes += 24 * 60
    return round((minutes - (line.get("ts_break_minutes") or 0)) / 60, 2)


def stable_number(case_id: str, salt: str, digits: int) -> str:
    raw = hashlib.sha256(f"{case_id}:{salt}".encode("utf-8")).hexdigest()
    value = int(raw[:16], 16) % (10**digits)
    return f"{value:0{digits}d}"


def profile(case_id: str, documents: dict) -> dict:
    suffix = case_id.rsplit("-", 1)[-1]
    serial = int(suffix) if suffix.isdigit() else int(stable_number(case_id, "profile-index", 4))
    # 기존 20세트의 양식용 합성값은 유지하고, 새 케이스 ID도 처리한다.
    legacy_case = case_id.startswith("CASE-2026-") and suffix in COUNTRIES
    index = serial - 12 if legacy_case else serial + len(COUNTRIES)
    source_country_ko, _source_country_en = (
        COUNTRIES[suffix] if legacy_case else CONTRACT_NATIONALITY
    )
    country_ko, country_en = CONTRACT_NATIONALITY
    address, area_code, duty = LOCATIONS[index % len(LOCATIONS)]
    birth = date(1988 + (index * 3) % 13, 1 + (index * 5) % 12, 1 + (index * 7) % 27)
    # 여권번호는 기존 값을 유지하고 계약서의 국적 표시만 변경한다.
    passport_prefix = PASSPORT_PREFIX.get(source_country_ko, "P")
    passport = passport_prefix + stable_number(case_id, "passport", 7)
    biz = f"{stable_number(case_id, 'biz-a', 3)}-9{index % 8 + 1}-{stable_number(case_id, 'biz-b', 5)}"
    phone = f"{area_code}-{stable_number(case_id, 'phone-a', 3)}-{stable_number(case_id, 'phone-b', 4)}"
    bank_mid = stable_number(case_id, "bank-mid", 8)
    bank_last = stable_number(case_id, "bank-last", 2)
    bank_full = f"352-{bank_mid[:4]}-{bank_mid[4:]}-{bank_last}"
    return {
        "country_ko": country_ko,
        "country_en": country_en,
        "birth": birth,
        "passport": passport,
        "business_number": biz,
        "address": address,
        "phone": phone,
        "duty": duty,
        "representative": REPRESENTATIVES[index % len(REPRESENTATIVES)],
        "bank_full": bank_full,
        "bank_masked": f"352-****-****-{bank_last}",
    }


def new_document() -> tuple[fitz.Document, fitz.Page]:
    doc = fitz.open()
    page = doc.new_page(width=A4[0], height=A4[1])
    register_fonts(page)
    return doc, page


def save_document(doc: fitz.Document, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        doc.subset_fonts(verbose=False)
    except Exception:
        pass
    doc.set_metadata(
        {
            "producer": "PyMuPDF synthetic seasonal-worker document generator",
            "creator": "R00-R11 v3.2 case PDF generator",
            "title": path.stem,
        }
    )
    doc.save(path, garbage=4, deflate=True, clean=True)
    doc.close()


def draw_contract(case_id: str, documents: dict, meta: dict, path: Path) -> None:
    ct = documents["contract"]
    doc, page = new_document()
    x, width = 31.0, 533.0

    draw_text(page, (x, 32, x + width, 43), "[별지 제1호서식]", 6.5)
    draw_text(page, (x, 43, x + width, 65), "표  준  근  로  계  약  서", 15, bold=True, align="center")
    draw_text(
        page,
        (x, 65, x + width, 79),
        "외국인 계절근로자 (E-8) / Standard Labor Contract for Seasonal Worker",
        6.4,
        align="center",
    )

    label_w = 107.0
    pair_w = [label_w, 157.0, label_w, 162.0]
    y = 83.0
    draw_text(page, (x, y, x + width, y + 14), "1. 당사자", 8.5, bold=True)
    y += 14
    y = draw_row(
        page,
        x,
        y,
        pair_w,
        16,
        ["사업체명", ct["ct_employer_name"], "사업자등록번호", meta["business_number"]],
        fills=[LIGHT_GRAY, None, LIGHT_GRAY, None],
        bolds=[True, False, True, False],
        aligns=["center", "left", "center", "left"],
        fontsize=7.2,
    )
    y = draw_row(
        page,
        x,
        y,
        [label_w, width - label_w],
        16,
        ["사업장 주소", f"{meta['address']} (전화 {meta['phone']})"],
        fills=[LIGHT_GRAY, None],
        bolds=[True, False],
        aligns=["center", "left"],
        fontsize=7.2,
    )
    y = draw_row(
        page,
        x,
        y,
        pair_w,
        16,
        ["근로자 성명", ct["ct_employee_name"], "생년월일", ko_date(meta["birth"])],
        fills=[LIGHT_GRAY, None, LIGHT_GRAY, None],
        bolds=[True, False, True, False],
        aligns=["center", "left", "center", "left"],
        fontsize=7.2,
    )
    y = draw_row(
        page,
        x,
        y,
        pair_w,
        16,
        ["국적", f"{meta['country_ko']} ({meta['country_en']})", "여권번호", meta["passport"]],
        fills=[LIGHT_GRAY, None, LIGHT_GRAY, None],
        bolds=[True, False, True, False],
        aligns=["center", "left", "center", "left"],
        fontsize=7.2,
    )

    y += 8
    draw_text(page, (x, y, x + width, y + 14), "2. 근로계약기간", 8.5, bold=True)
    y += 14
    new_selected = bool(ct["ct_new_or_reentry_selected"])
    change_selected = bool(ct["ct_workplace_change_selected"])
    y = draw_row(
        page,
        x,
        y,
        [label_w, width - label_w],
        16,
        ["계약 구분", f"{'■' if new_selected else '□'} 신규·재입국자   {'■' if change_selected else '□'} 근무처 변경자"],
        fills=[LIGHT_GRAY, None],
        bolds=[True, False],
        aligns=["center", "left"],
        fontsize=7.2,
    )
    new_period = (
        f"{ko_date(ct['ct_new_or_reentry_start_date'])}부터 {ko_date(ct['ct_new_or_reentry_end_date'])}까지"
        if new_selected
        else "해당 없음"
    )
    change_period = (
        f"{ko_date(ct['ct_workplace_change_start_date'])}부터 {ko_date(ct['ct_workplace_change_end_date'])}까지"
        if change_selected
        else "해당 없음"
    )
    y = draw_row(
        page,
        x,
        y,
        [label_w, width - label_w],
        16,
        ["신규·재입국자", new_period],
        fills=[LIGHT_GRAY, None],
        bolds=[True, False],
        aligns=["center", "left"],
        fontsize=7.2,
    )
    y = draw_row(
        page,
        x,
        y,
        [label_w, width - label_w],
        16,
        ["근무처 변경자", change_period],
        fills=[LIGHT_GRAY, None],
        bolds=[True, False],
        aligns=["center", "left"],
        fontsize=7.2,
    )

    y += 8
    draw_text(page, (x, y, x + width, y + 14), "3. 근로장소 및 업무내용", 8.5, bold=True)
    y += 14
    y = draw_row(
        page,
        x,
        y,
        [label_w, width - label_w],
        16,
        ["근로장소", f"{meta['address']} 일원"],
        fills=[LIGHT_GRAY, None],
        bolds=[True, False],
        aligns=["center", "left"],
        fontsize=7.2,
    )
    y = draw_row(
        page,
        x,
        y,
        [label_w, width - label_w],
        16,
        ["업무내용", meta["duty"]],
        fills=[LIGHT_GRAY, None],
        bolds=[True, False],
        aligns=["center", "left"],
        fontsize=7.2,
    )

    y += 8
    draw_text(page, (x, y, x + width, y + 14), "4. 근로시간·휴게·휴일", 8.5, bold=True)
    y += 14
    work_days = f"매주 {DAY_KO.get(ct['ct_work_day_start'], ct['ct_work_day_start'])} ~ {DAY_KO.get(ct['ct_work_day_end'], ct['ct_work_day_end'])}"
    rows = [
        ["소정근로시간", f"{ct['ct_work_start_time']} ~ {ct['ct_work_end_time']}", "월 소정근로시간", f"{number(ct['ct_monthly_work_hours'])} 시간"],
        ["1일 총 휴게시간", f"{number(ct['ct_break_hours'])} 시간 {number(ct['ct_break_minutes'])} 분", "소정근로요일", work_days],
        ["휴일 부여 방식", HOLIDAY_KO.get(ct["ct_holiday_type"], ct["ct_holiday_type"]), "계절·기상 요인에 따른\n1일 변경 상한시간", f"{number(ct['ct_max_daily_work_hours'])} 시간"],
    ]
    for values in rows:
        y = draw_row(
            page,
            x,
            y,
            [107, 153, 107, 166],
            19,
            values,
            fills=[LIGHT_GRAY, None, LIGHT_GRAY, None],
            bolds=[True, False, True, False],
            aligns=["center", "left", "center", "left"],
            fontsize=7.0,
        )

    y += 8
    draw_text(page, (x, y, x + width, y + 14), "5. 임금", 8.5, bold=True)
    y += 14
    checks = []
    for key, label in [("hourly", "시급"), ("daily", "일급"), ("weekly", "주급"), ("monthly", "월급")]:
        checks.append(f"{'■' if ct['ct_wage_type'] == key else '□'} {label}")
    bonus_yes = bool(ct["ct_bonus_extra_pay_paid"])
    weekly_included = bool(ct["ct_weekly_allowance_included"])
    period_start = iso_date(ct["ct_pay_period_start"])
    period_end = iso_date(ct["ct_pay_period_end"])
    period_text = (
        f"매월 {period_start.day}일 ~ {period_end.day}일"
        if period_start and period_end and period_start.month == period_end.month
        else f"{dot_date(ct['ct_pay_period_start'])} ~ {dot_date(ct['ct_pay_period_end'])}"
    )
    if ct["ct_pay_cycle"] == "weekly":
        weekday = DAY_KO.get(ct.get("ct_pay_weekday"), ct.get("ct_pay_weekday") or "지정일")
        payment_method = f"매주 {weekday} / 근로자 명의 예금통장 입금"
    else:
        timing = "익월" if ct["ct_pay_timing"] == "next_month" else "당월"
        payment_method = f"{timing} {ct.get('ct_pay_day') or '지정'}일 / 근로자 명의 예금통장 입금"
    wage_rows = [
        ["임금 형태", " ".join(checks), "임금액", f"{money(ct['ct_wage_amount'])} 원"],
        ["상여금·수당 지급 여부", f"{'■' if bonus_yes else '□'} 있음   {'□' if bonus_yes else '■'} 없음", "상여금·수당", f"상여금 {money(ct['ct_bonus_amount'])} 원 / 수당 {money(ct['ct_extra_pay_amount'])} 원"],
        ["주휴수당", f"{'■' if weekly_included else '□'} 임금에 포함   {'□' if weekly_included else '■'} 별도 지급", "연장근로 시간당 임금", f"{money(ct['ct_overtime_hourly_pay'])} 원"],
        ["임금 계산기간", period_text, "임금 지급일·방법", payment_method],
    ]
    for values in wage_rows:
        y = draw_row(
            page,
            x,
            y,
            [107, 148, 107, 171],
            18,
            values,
            fills=[LIGHT_GRAY, None, LIGHT_GRAY, None],
            bolds=[True, False, True, False],
            aligns=["center", "left", "center", "left"],
            fontsize=6.8,
        )

    y += 8
    draw_text(page, (x, y, x + width, y + 14), "6. 숙식 제공", 8.5, bold=True)
    y += 14
    housing = bool(ct["ct_housing_provided"])
    meal = bool(ct["ct_meal_provided"])
    y = draw_row(
        page,
        x,
        y,
        [107, 193, 107, 126],
        18,
        ["숙박시설 제공", f"{'■' if housing else '□'} 제공   {'□' if housing else '■'} 미제공", "월 숙박비 근로자 부담액", f"{money(ct['ct_housing_cost'])} 원"],
        fills=[LIGHT_GRAY, None, LIGHT_GRAY, None],
        bolds=[True, False, True, False],
        aligns=["center", "left", "center", "left"],
        fontsize=6.8,
    )
    y = draw_row(
        page,
        x,
        y,
        [107, 193, 107, 126],
        18,
        ["식사 제공", f"{'■' if meal else '□'} 제공   {'□' if meal else '■'} 미제공", "월 식비 근로자 부담액", f"{money(ct['ct_meal_cost'])} 원"],
        fills=[LIGHT_GRAY, None, LIGHT_GRAY, None],
        bolds=[True, False, True, False],
        aligns=["center", "left", "center", "left"],
        fontsize=6.8,
    )

    selected_start = iso_date(ct["ct_new_or_reentry_start_date"] or ct["ct_workplace_change_start_date"])
    contract_date = selected_start - timedelta(days=7) if selected_start else date(2026, 1, 1)
    y += 10
    draw_text(page, (x + 3, y, x + 65, y + 15), "계약일자", 7.2)
    draw_text(page, (x + 67, y, x + 240, y + 15), ko_date(contract_date), 7.2)
    y += 16
    draw_text(page, (x + 3, y, x + 65, y + 15), "사업주", 7.2)
    draw_text(page, (x + 67, y, x + 275, y + 15), f"{ct['ct_employer_name']} 대표 {meta['representative']}  (서명)", 7.2)
    draw_text(page, (x + 280, y, x + 330, y + 15), "근로자", 7.2)
    draw_text(page, (x + 335, y, x + width, y + 15), f"{ct['ct_employee_name']}  (서명)", 7.2)

    save_document(doc, path)


def draw_timesheet(case_id: str, documents: dict, meta: dict, path: Path) -> None:
    ts = documents["timesheet"]
    ct = documents["contract"]
    ps = documents["payslip"]
    lines = ts["lines"]
    doc, page = new_document()
    x, width = 31.0, 533.0

    draw_cell(page, (x, 35, x + 84, 49), "근로자 작성·확인용", fontsize=6, align="center")
    draw_text(page, (x, 45, x + width, 69), "근  무  기  록  부", 16, bold=True, align="center")
    period = f"{dot_date(ps['ps_pay_period_start'])} ~ {dot_date(ps['ps_pay_period_end'])}"
    draw_text(page, (x, 68, x + width, 81), period, 6.5, align="center")

    y = 87.0
    y = draw_row(
        page,
        x,
        y,
        [107, 74, 107, 66, 107, 72],
        18,
        ["근로자 성명", ts["ts_employee_name"], "사업장", ct["ct_employer_name"], "기록 대상기간", period],
        fills=[LIGHT_GRAY, None, LIGHT_GRAY, None, LIGHT_GRAY, None],
        bolds=[True, False, True, False, True, False],
        aligns=["center", "left", "center", "left", "center", "left"],
        fontsize=6.3,
    )
    y += 8

    widths = [27, 64, 27, 49, 49, 48, 50, 60, 159]
    headers = ["No", "근무일", "요일", "시작시각", "종료시각", "휴게(분)", "휴일근무", "실근로시간", "특이사항"]
    row_height = min(16.0, max(12.0, 398.0 / (max(len(lines), 1) + 2)))
    y = draw_row(
        page,
        x,
        y,
        widths,
        row_height + 1,
        headers,
        fills=[LIGHT_GRAY] * len(widths),
        bolds=[True] * len(widths),
        aligns=["center"] * len(widths),
        fontsize=6.4,
    )
    total_hours = 0.0
    if lines:
        for index, line in enumerate(lines, 1):
            d = date.fromisoformat(line["ts_work_date"])
            hours = actual_hours(line)
            total_hours += hours
            values = [
                index,
                dot_date(line["ts_work_date"]),
                WEEKDAY_KO[d.weekday()],
                line["ts_work_start_time"],
                line["ts_work_end_time"],
                number(line["ts_break_minutes"]),
                "예" if line["ts_holiday_worked"] else "아니오",
                number(hours),
                line.get("ts_work_note") or "",
            ]
            y = draw_row(
                page,
                x,
                y,
                widths,
                row_height,
                values,
                aligns=["center"] * 8 + ["left"],
                bolds=[False] * 7 + [True, False],
                fontsize=6.0,
            )
    else:
        draw_cell(
            page,
            (x, y, x + width, y + 30),
            "제출된 근무기록 없음",
            fill=PALE_BLUE,
            fontsize=8,
            bold=True,
            align="center",
        )
        y += 30

    y = draw_row(
        page,
        x,
        y,
        [216, 48, 50, 60, 159],
        row_height + 1,
        ["합 계", "-", "-", f"{number(total_hours)} 시간", f"근무일수 {len(lines)}일"],
        fills=[LIGHT_GRAY] * 5,
        bolds=[True] * 5,
        aligns=["center", "center", "center", "center", "left"],
        fontsize=6.5,
    )

    y += 7
    available = bool(ts["ts_record_available"])
    confirmed = bool(ts["ts_worker_confirmed"])
    y = draw_row(
        page,
        x,
        y,
        [107, 107, 107, 212],
        19,
        ["월 총근로시간", f"{number(total_hours)} 시간", "기록 보유 여부", f"{'■' if available else '□'} 보유   {'□' if available else '■'} 미보유"],
        fills=[LIGHT_GRAY, None, LIGHT_GRAY, None],
        bolds=[True, True, True, False],
        aligns=["center", "left", "center", "left"],
        fontsize=6.8,
    )
    confirm_date = iso_date(ps["ps_pay_period_end"]) + timedelta(days=1)
    confirmation = (
        f"■ 위 근무기록이 사실과 같음을 확인함     확인일 {ko_date(confirm_date)}     근로자 {ts['ts_employee_name']} 서명"
        if confirmed
        else "□ 근로자 확인 또는 서명 없음"
    )
    y = draw_row(
        page,
        x,
        y,
        [107, 426],
        22,
        ["근로자 확인", confirmation],
        fills=[LIGHT_GRAY, None],
        bolds=[True, False],
        aligns=["center", "left"],
        fontsize=6.4,
    )
    y = draw_row(
        page,
        x,
        y,
        [107, 426],
        27,
        ["기타사항", "근무기록이 일부만 제출된 경우 실제 제출분만 기재함" if available and len(lines) < 10 else ""],
        fills=[LIGHT_GRAY, None],
        bolds=[True, False],
        aligns=["center", "left"],
        fontsize=6.4,
    )
    y = draw_row(
        page,
        x,
        y,
        [107, 426],
        27,
        ["비고", ""],
        fills=[LIGHT_GRAY, None],
        bolds=[True, False],
        aligns=["center", "left"],
        fontsize=6.4,
    )
    y += 8
    draw_text(page, (x, y, x + width, y + 12), "※ 실근로시간 = 종료시각 − 시작시각 − 휴게시간. 휴게시간은 분 단위로 기재한다.", 5.4)
    draw_text(page, (x, y + 11, x + width, y + 23), "※ 기상·작업물량 등으로 소정근로시간과 달라진 날은 특이사항란에 사유를 적는다.", 5.4)

    save_document(doc, path)


def draw_payslip(case_id: str, documents: dict, meta: dict, path: Path) -> None:
    ps = documents["payslip"]
    bank = documents["bank_statement"]
    doc, page = new_document()
    x, width = 31.0, 533.0

    page.draw_rect((x, 31, x + 200, 98), fill=PALE_BLUE, color=PALE_BLUE, overlay=True)
    draw_text(page, (x + 8, 43, x + 195, 72), "급여 명세서", 21, bold=True, color=NAVY)
    payment_date = iso_date(ps["ps_payment_date"])
    draw_text(page, (x + 11, 72, x + 190, 90), f"{payment_date.year}.{payment_date.month:02d}월", 8.5, color=NAVY)

    y = 104.0
    info_w = [103, 327]
    info_rows = [
        ["성명", ps["ps_employee_name"]],
        ["지급일", dot_date(ps["ps_payment_date"])],
        ["생년월일", meta["birth"].strftime("%Y.%m.%d")],
        ["사업장", ps["ps_employer_name"]],
        ["임금 계산기간", f"{dot_date(ps['ps_pay_period_start'])} ~ {dot_date(ps['ps_pay_period_end'])}"],
        ["급여제도", WAGE_KO.get(ps["ps_wage_type"], ps["ps_wage_type"])],
    ]
    for label, value in info_rows:
        y = draw_row(
            page,
            x + 7,
            y,
            info_w,
            16,
            [label, value],
            fills=[PALE_BLUE, None],
            bolds=[True, False],
            aligns=["center", "center"],
            fontsize=7.0,
        )

    y += 6
    draw_cell(page, (x, y, x + width, y + 17), "근로시간 내역", fill=BLUE, border=BLUE, fontsize=7.5, bold=True, align="center", color=WHITE)
    y += 17
    hours_headers = ["기본근로시간", "연장근로시간", "야간근로시간", "휴일근로시간", "주휴시간", "출근일수", "통상시급"]
    hours_widths = [84, 84, 84, 84, 73, 60, 64]
    y = draw_row(
        page,
        x,
        y,
        hours_widths,
        17,
        hours_headers,
        fills=[PALE_BLUE] * 7,
        bolds=[True] * 7,
        aligns=["center"] * 7,
        fontsize=6.5,
    )
    hour_values = [
        number(ps["ps_paid_regular_hours"]),
        number(ps["ps_paid_overtime_hours"]),
        number(ps["ps_paid_night_hours"]),
        number(ps["ps_paid_holiday_hours"]),
        number(ps["ps_weekly_holiday_hours"]),
        number(ps["ps_paid_work_days"]),
        f"{money(ps['ps_ordinary_hourly_wage'])} 원",
    ]
    y = draw_row(
        page,
        x,
        y,
        hours_widths,
        18,
        hour_values,
        aligns=["center"] * 7,
        fontsize=6.8,
    )

    y += 7
    half = width / 2
    draw_cell(page, (x, y, x + half, y + 17), "임금지급내역", fill=NAVY, border=NAVY, fontsize=7.5, bold=True, align="center", color=WHITE)
    draw_cell(page, (x + half, y, x + width, y + 17), "공제내역", fill=NAVY, border=NAVY, fontsize=7.5, bold=True, align="center", color=WHITE)
    y += 17
    detail_widths = [117, 149.5, 117, 149.5]
    y = draw_row(
        page,
        x,
        y,
        detail_widths,
        17,
        ["임금항목", "지급금액(원)", "공제항목", "공제금액(원)"],
        fills=[BLUE] * 4,
        bolds=[True] * 4,
        aligns=["center"] * 4,
        fontsize=6.7,
        colors=[WHITE] * 4,
    )

    pay_lines = [(item["item_name"], item["amount"]) for item in ps["ps_pay_lines"]]
    deduction_lines = [
        ("소득세", ps["ps_income_tax"]),
        ("국민연금", ps["ps_national_pension"]),
        ("건강보험", ps["ps_health_insurance"]),
        ("고용보험", ps["ps_employment_insurance"]),
        ("식비", ps["ps_meal_deduction"]),
        ("장기요양보험료", ps["ps_long_term_care_insurance"]),
        ("지방소득세", ps["ps_local_income_tax"]),
        ("숙박비", ps["ps_housing_deduction"]),
        ("기타공제", ps["ps_other_deduction"]),
    ]
    body_rows = max(9, len(pay_lines), len(deduction_lines))
    for index in range(body_rows):
        pay_name, pay_amount = pay_lines[index] if index < len(pay_lines) else ("", "")
        ded_name, ded_amount = deduction_lines[index] if index < len(deduction_lines) else ("", "")
        y = draw_row(
            page,
            x,
            y,
            detail_widths,
            17,
            [pay_name, money(pay_amount) if pay_name else "", ded_name, money(ded_amount) if ded_name else ""],
            fills=[PALE_BLUE if index % 2 == 0 else None] * 4,
            bolds=[True, False, True, False],
            aligns=["center", "center", "center", "center"],
            fontsize=6.5,
        )
    y = draw_row(
        page,
        x,
        y,
        detail_widths,
        18,
        ["지급액 계", money(ps["ps_gross_pay"]), "공제액 계", money(ps["ps_total_deduction"])],
        fills=[PALE_BLUE] * 4,
        bolds=[True] * 4,
        aligns=["center"] * 4,
        fontsize=7.0,
    )
    y = draw_row(
        page,
        x,
        y,
        [117, 416],
        20,
        ["실지급액", money(ps["ps_net_pay"])],
        fills=[PALE_BLUE_2, PALE_BLUE_2],
        bolds=[True, True],
        aligns=["center", "center"],
        fontsize=8.0,
    )

    y += 7
    draw_cell(page, (x, y, x + width, y + 17), "계산 방법", fill=NAVY, border=NAVY, fontsize=7.5, bold=True, align="center", color=WHITE)
    y += 17
    calc_widths = [117, 256, 160]
    y = draw_row(
        page,
        x,
        y,
        calc_widths,
        17,
        ["구분", "산출식 또는 산출방법", "지급액(원)"],
        fills=[BLUE] * 3,
        bolds=[True] * 3,
        aligns=["center"] * 3,
        fontsize=6.7,
        colors=[WHITE] * 3,
    )
    calc_rows = [
        (ps["ps_calculation_item"], ps["ps_calculation_formula"], ps["ps_calculated_amount"]),
        ("주휴수당", "-", ps["ps_weekly_allowance"]),
        ("연장근로수당", "-", ps["ps_overtime_pay"]),
        ("야간근로수당", "-", ps["ps_night_work_pay"]),
        ("휴일근로수당", "-", ps["ps_holiday_work_pay"]),
    ]
    for label, formula, amount in calc_rows:
        y = draw_row(
            page,
            x,
            y,
            calc_widths,
            18,
            [label, formula, money(amount)],
            fills=[PALE_BLUE, None, None],
            bolds=[True, False, False],
            aligns=["center", "center", "center"],
            fontsize=6.5,
        )
    y += 8
    draw_text(page, (x, y, x + width, y + 13), f"※ 지급방법: NH농협은행 {meta['bank_full']} ({bank['bk_account_holder']}) 계좌 입금", 5.7)
    draw_text(page, (x, y + 12, x + width, y + 25), "※ 본 명세서는 문서 간 교차검증을 위한 합성데이터이며 실제 급여 증빙으로 사용할 수 없음.", 5.4)

    save_document(doc, path)


def draw_bank_statement(case_id: str, documents: dict, meta: dict, path: Path) -> None:
    bank = documents["bank_statement"]
    txs = bank["transactions"]
    doc, page = new_document()
    x, width = 31.0, 533.0

    page.draw_rect((x, 32, x + width, 72), fill=GREEN, color=GREEN, overlay=True)
    draw_text(page, (x + 10, 42, x + 330, 64), "NH농협은행 거래내역 조회", 12, bold=True, color=WHITE)
    draw_text(page, (x + 355, 42, x + width - 8, 64), "합성 예시 / 실제 은행 발급문서 아님", 6.2, bold=True, align="right", color=WHITE)

    inquiry_end = iso_date(bank["bk_inquiry_end_date"])
    lookup_hour = 9 + int(stable_number(case_id, "lookup-hour", 2)) % 8
    lookup_minute = int(stable_number(case_id, "lookup-minute", 2)) % 60
    lookup = f"{dot_date(bank['bk_inquiry_end_date'])}. {lookup_hour:02d}:{lookup_minute:02d}"
    y = 86.0
    info_widths = [74, 223, 74, 162]
    y = draw_row(
        page,
        x,
        y,
        info_widths,
        18,
        ["예금주", bank["bk_account_holder"], "계좌번호", meta["bank_masked"]],
        fills=[LIGHT_GRAY, None, LIGHT_GRAY, None],
        bolds=[True, False, True, False],
        aligns=["center", "left", "center", "left"],
        fontsize=6.8,
    )
    y = draw_row(
        page,
        x,
        y,
        info_widths,
        18,
        ["조회기간", f"{dot_date(bank['bk_inquiry_start_date'])}. ~ {dot_date(bank['bk_inquiry_end_date'])}.", "조회일시", lookup],
        fills=[LIGHT_GRAY, None, LIGHT_GRAY, None],
        bolds=[True, False, True, False],
        aligns=["center", "left", "center", "left"],
        fontsize=6.6,
    )
    y += 8
    tx_widths = [105, 65, 70, 83, 70, 140]
    headers = ["거래일시", "거래구분", "내용", "입금액(원)", "출금액(원)", "거래기록 / 메모"]
    y = draw_row(
        page,
        x,
        y,
        tx_widths,
        20,
        headers,
        fills=[LIGHT_GRAY] * 6,
        bolds=[True] * 6,
        aligns=["center"] * 6,
        fontsize=6.6,
    )
    total = 0
    for tx in txs:
        amount = tx["bk_deposit_amount"] or 0
        total += amount
        y = draw_row(
            page,
            x,
            y,
            tx_widths,
            21,
            [
                tx["bk_transaction_datetime"],
                "입금",
                tx["bk_transaction_content"],
                money(tx["bk_deposit_amount"]),
                "0",
                f"{tx['bk_transaction_record']} / {tx.get('bk_transfer_memo') or '-'}",
            ],
            bolds=[False, False, False, True, False, False],
            aligns=["center", "center", "center", "right", "right", "left"],
            fontsize=6.5,
        )
    y += 7
    draw_text(page, (x, y, x + width, y + 16), f"입금 합계: {money(total)}원 ({len(txs)}건)", 8, bold=True)
    y += 20
    draw_text(page, (x, y, x + width, y + 12), "※ 본 문서는 문서 간 교차검증 테스트를 위해 제작한 합성데이터이며 실제 금융거래 증빙으로 사용할 수 없음.", 5.5)
    draw_text(page, (x, y + 11, x + width, y + 23), "※ 거래기록은 입금 의뢰인이 등록한 명의, 메모는 입금 의뢰인이 직접 입력한 문구임.", 5.5)

    save_document(doc, path)


PDF_NAMES = [
    ("01_표준근로계약서", draw_contract),
    ("02_근무기록부", draw_timesheet),
    ("03_임금명세서", draw_payslip),
    ("04_입금내역서", draw_bank_statement),
]


def generate_case(json_path: Path, overwrite: bool = False) -> list[Path]:
    case = json.loads(json_path.read_text(encoding="utf-8"))
    documents = case["documents"]
    case_id = json_path.stem
    if case.get("derived", {}).get("R00", {}).get("sys_case_id"):
        case_id = case["derived"]["R00"]["sys_case_id"]
    meta = profile(case_id, documents)
    outputs: list[Path] = []
    for suffix, renderer in PDF_NAMES:
        output = json_path.parent / f"{case_id}_{suffix}.pdf"
        if output.exists() and not overwrite:
            raise FileExistsError(f"이미 존재하는 파일입니다: {output}")
        renderer(case_id, documents, meta, output)
        outputs.append(output)
    return outputs


def find_cases(case_root: Path) -> list[Path]:
    return sorted(case_root.glob("CASE-*/*.json"))


def main() -> int:
    parser = argparse.ArgumentParser(description="20세트 JSON에서 4종 합성 PDF를 생성합니다.")
    parser.add_argument("--case-root", type=Path, default=DEFAULT_CASE_ROOT)
    parser.add_argument("--case", help="특정 CASE ID만 생성")
    parser.add_argument("--overwrite", action="store_true", help="기존 PDF 덮어쓰기")
    args = parser.parse_args()

    paths = find_cases(args.case_root)
    if args.case:
        paths = [path for path in paths if path.parent.name == args.case]
    if not paths:
        raise SystemExit("생성할 케이스 JSON을 찾지 못했습니다.")

    generated: list[Path] = []
    for json_path in paths:
        outputs = generate_case(json_path, overwrite=args.overwrite)
        generated.extend(outputs)
        print(f"OK {json_path.parent.name}: {len(outputs)}개 PDF")
    print(f"완료: {len(paths)}개 케이스, PDF {len(generated)}개")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
