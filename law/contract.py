"""표준 계절근로계약서 조항 카탈로그.

R01~R04·R08~R10의 1차 근거는 법령이 아니라 표준 계절근로계약서다.
공식 서식은 「농어업고용인력 지원 특별법 시행규칙」 별지 제3호서식이며
2026년 2월 15일부터 시행됐다.

주의 — 조항 번호로 참조하지 않는다.
    공식 서식(별지 제3호)과 합성데이터 서식(별지 제1호)은 항 구성이 다르다.
        공식:   제4항 근로시간 / 제5항 휴게시간 / 제6항 휴일 / 제7항 임금
               / 제8항 임금 지급일 / 제9항 임금 지급방법 / 제10항 숙식 제공
        합성:   4. 근로시간·휴게·휴일 (통합) / 5. 임금 (지급일·방법 포함)
               / 6. 숙식 제공
    번호로 매핑하면 서식이 바뀔 때마다 근거가 어긋난다.
    의미 키(Clause.key)로 참조하고, 번호는 인용 문자열을 만들 때만 쓴다.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class Clause:
    key: str
    이름: str
    공식항: str | None          # 별지 제3호서식 기준 항 번호
    합성항: str | None          # 합성데이터(별지 제1호서식) 기준 절 번호
    확인내용: str
    계약필드: tuple[str, ...] = ()   # 케이스 JSON documents.contract 의 필드


CLAUSES: dict[str, Clause] = {
    "근로시간": Clause(
        "근로시간", "근로시간", "4", "4",
        "소정근로시간, 월 소정근로시간, 소정근로요일, 계절·기상 요인에 따른 1일 변경 상한시간",
        ("ct_work_start_time", "ct_work_end_time", "ct_monthly_work_hours",
         "ct_work_day_start", "ct_work_day_end", "ct_max_daily_work_hours"),
    ),
    "휴게시간": Clause(
        "휴게시간", "휴게시간", "5", "4",
        "1일 총 휴게시간",
        ("ct_break_hours", "ct_break_minutes"),
    ),
    "휴일": Clause(
        "휴일", "휴일", "6", "4",
        "휴일 부여 방식(주휴일 요일 등)",
        ("ct_holiday_type",),
    ),
    "임금": Clause(
        "임금", "임금", "7", "5",
        "임금 형태(시급·일급·주급·월급), 임금액, 상여금·수당, 주휴수당 포함 여부, 연장근로 시간당 임금",
        ("ct_wage_type", "ct_wage_amount", "ct_bonus_amount", "ct_extra_pay_amount",
         "ct_weekly_allowance_included", "ct_overtime_hourly_pay"),
    ),
    "임금지급일": Clause(
        "임금지급일", "임금 지급일", "8", "5",
        "임금 계산기간과 지급일. 지급일이 공휴일인 경우 전날 지급",
        ("ct_pay_day", "ct_pay_cycle", "ct_pay_timing", "ct_pay_weekday",
         "ct_pay_period_start", "ct_pay_period_end"),
    ),
    "임금지급방법": Clause(
        "임금지급방법", "임금 지급방법", "9", "5",
        "근로자 명의 예금통장에 전액 직접 입금",
        (),
    ),
    "숙식제공": Clause(
        "숙식제공", "숙식 제공", "10", "6",
        "숙박시설·식사 제공 여부, 월 숙박비·식비 근로자 부담액",
        ("ct_housing_provided", "ct_housing_cost", "ct_meal_provided", "ct_meal_cost"),
    ),
}

SOURCE = "농어업고용인력 지원 특별법 시행규칙 별지 제3호서식 「표준 계절근로계약서」"


def cite(key: str, 서식: str = "공식") -> str:
    """인용 문자열을 만든다."""
    clause = CLAUSES[key]
    번호 = clause.공식항 if 서식 == "공식" else clause.합성항
    if 번호 is None:
        return f"표준 계절근로계약서 「{clause.이름}」"
    return f"표준 계절근로계약서 제{번호}항 「{clause.이름}」"


def clause(key: str) -> Clause:
    return CLAUSES[key]
