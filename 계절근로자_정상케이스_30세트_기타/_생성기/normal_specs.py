# -*- coding: utf-8 -*-
"""R00~R11이 모두 PASS가 되도록 구성한 캄보디아 계절근로자 30개 명세."""

from __future__ import annotations

import calendar
import datetime as dt


MON_FRI = [0, 1, 2, 3, 4]
MON_SAT = [0, 1, 2, 3, 4, 5]

NAMES = [
    "SOK DARA",
    "CHAN SREYNEANG",
    "CHEA VANNATH",
    "HENG SOKHA",
    "KIM SOVANN",
    "LIM PHEAKDEY",
    "MEAS CHANNARY",
    "NHEM VISAL",
    "OU SREYPOV",
    "PENH RATHANA",
    "ROS BOREY",
    "SAN MAKARA",
    "SOKUN CHANTREA",
    "SUON PISEY",
    "TEK BUNTHOEUN",
    "THY SAMNANG",
    "TOUCH SREYMOM",
    "VANN SOPHEAP",
    "YIM CHHUNLY",
    "KEAT SOKHENG",
    "LAY MONY",
    "LONG VICHEKA",
    "MOK KUNTHEA",
    "NOP SOVANNARA",
    "OUM KHEMRA",
    "PHAN SOPHAL",
    "RIN SAVUTH",
    "SEM CHANVUTHY",
    "SIM SREYLEAK",
    "UNG BUNNA",
]

EMPLOYERS = [
    "고운들농원",
    "햇살채소농장",
    "푸른강영농조합",
    "새봄과수원",
    "다온시설농장",
    "참들농산",
    "바른뜰농원",
    "한마음영농조합",
    "솔빛채소농장",
    "가람과수원",
    "들꽃농산",
    "청명농원",
    "늘푸른영농조합",
    "해맑은농장",
    "온누리과수원",
    "산들채소농장",
    "행복뜰농원",
    "큰나무영농조합",
    "맑은샘농산",
    "아침이슬농장",
    "평화과수원",
    "좋은들농원",
    "꿈나무영농조합",
    "정다운농산",
    "초록별농장",
    "보람뜰농원",
    "우리들과수원",
    "한결영농조합",
    "풍년채소농장",
    "새희망농산",
]


def add_month(value: dt.date, months: int) -> dt.date:
    year = value.year + (value.month - 1 + months) // 12
    month = (value.month - 1 + months) % 12 + 1
    day = min(value.day, calendar.monthrange(year, month)[1])
    return dt.date(year, month, day)


def first_weekday(year: int, month: int, weekday: int, after_day: int = 1) -> dt.date:
    value = dt.date(year, month, after_day)
    while value.weekday() != weekday:
        value += dt.timedelta(days=1)
    return value


def last_weekday(year: int, month: int, weekday: int) -> dt.date:
    value = dt.date(year, month, calendar.monthrange(year, month)[1])
    while value.weekday() != weekday:
        value -= dt.timedelta(days=1)
    return value


def count_weekdays(start: dt.date, end: dt.date, weekdays: list[int]) -> int:
    total = 0
    value = start
    while value <= end:
        total += value.weekday() in weekdays
        value += dt.timedelta(days=1)
    return total


def C(**overrides):
    base = dict(
        ct_bonus_amount=0,
        ct_bonus_extra_pay_paid=False,
        ct_break_hours=1,
        ct_break_minutes=0,
        ct_employee_name=None,
        ct_employer_name=None,
        ct_extra_pay_amount=0,
        ct_holiday_type="weekly_sunday",
        ct_housing_cost=0,
        ct_housing_provided=False,
        ct_max_daily_work_hours=10.0,
        ct_meal_cost=0,
        ct_meal_provided=False,
        ct_monthly_work_hours=176.0,
        ct_new_or_reentry_end_date=None,
        ct_new_or_reentry_selected=True,
        ct_new_or_reentry_start_date=None,
        ct_overtime_hourly_pay=0,
        ct_pay_cycle="monthly",
        ct_pay_day=10,
        ct_pay_period_end=None,
        ct_pay_period_start=None,
        ct_pay_timing="next_month",
        ct_pay_weekday=None,
        ct_wage_amount=0,
        ct_wage_type="hourly",
        ct_weekly_allowance_included=False,
        ct_work_day_end="FRI",
        ct_work_day_start="MON",
        ct_work_end_time="17:00",
        ct_work_start_time="08:00",
        ct_workplace_change_end_date=None,
        ct_workplace_change_selected=False,
        ct_workplace_change_start_date=None,
    )
    base.update(overrides)
    return base


def make_spec(index: int) -> dict:
    """서로 다른 정상 변형을 포함하되 모든 비교값을 정확히 일치시킨다."""
    serial = index + 1
    year = 2026
    month = index % 12 + 1
    start = dt.date(year, month, 1)
    end = dt.date(year, month, calendar.monthrange(year, month)[1])
    case_id = f"CASE-PASS-{year}-{month:02d}-{serial:04d}"
    name = NAMES[index]
    employer = EMPLOYERS[index]

    weekdays = MON_SAT if index in {7, 17, 27} else MON_FRI
    work_day_end = "SAT" if weekdays == MON_SAT else "FRI"
    scheduled_days = count_weekdays(start, end, weekdays)
    monthly_hours = float(scheduled_days * 8)

    night = index in {2, 10, 18, 25}
    work_start = "20:00" if night else "08:00"
    work_end = "05:00" if night else "17:00"
    schedule = {"weekdays": weekdays, "start": work_start, "end": work_end, "break": 60}

    # 1시간 연장근로: 계약 월시간과 실제시간 차이는 R10 허용범위 안이다.
    overtime = index in {1, 6, 11, 16, 21, 27}
    if overtime:
        overtime_day = first_weekday(year, month, weekdays[0], after_day=8)
        schedule["overrides"] = {
            overtime_day.isoformat(): (
                work_start,
                "18:00",
                60,
                False,
                "수확 물량 증가에 따른 사전 합의 연장근로",
            )
        }

    # 1회의 휴일근로 8시간: R10 허용 상한 8시간 이내이며 명세서에도 동일 반영한다.
    holiday = index in {4, 12, 22}
    if holiday:
        holiday_day = first_weekday(year, month, 6, after_day=8)
        schedule["extra"] = {
            holiday_day.isoformat(): (
                "08:00",
                "17:00",
                60,
                True,
                "출하 일정에 따른 사전 합의 휴일근로",
            )
        }

    wage_type = ("hourly", "monthly", "daily")[index % 3]
    hourly_rate = 11200 + (index % 8) * 300
    if wage_type == "hourly":
        wage_amount = hourly_rate
        calc_formula = f"시급 {hourly_rate:,}원 × 기본근로 {monthly_hours:g}시간"
    elif wage_type == "monthly":
        wage_amount = int(hourly_rate * monthly_hours)
        calc_formula = f"월급 {wage_amount:,}원 (월 소정근로시간 {monthly_hours:g}시간)"
    else:
        wage_amount = hourly_rate * 8
        calc_formula = f"일급 {wage_amount:,}원 × 근무일수 {scheduled_days}일"

    bonus_amount = 100000 + (index % 3) * 50000 if index in {3, 8, 13, 18, 23, 28} else 0
    extra_amount = 50000 + (index % 2) * 20000 if index in {5, 15, 25} else 0
    housing_provided = index % 2 == 0
    meal_provided = index % 3 != 1
    housing_cost = 90000 + (index % 4) * 10000 if housing_provided else 0
    meal_cost = 70000 + (index % 3) * 10000 if meal_provided else 0

    pay_cycle = "weekly" if index in {9, 19, 29} else "monthly"
    if pay_cycle == "weekly":
        next_period = add_month(end, 1)
        payment = first_weekday(next_period.year, next_period.month, 4)
        pay_day = None
        pay_weekday = "FRI"
        scheduled_override = payment.isoformat()
    else:
        pay_day = (5, 10, 15)[index % 3]
        next_period = add_month(end, 1)
        payment = dt.date(next_period.year, next_period.month, min(pay_day, calendar.monthrange(next_period.year, next_period.month)[1]))
        pay_weekday = None
        scheduled_override = None

    contract_start = start - dt.timedelta(days=75 + index % 20)
    contract_end = end + dt.timedelta(days=90 + index % 30)
    contract = C(
        ct_bonus_amount=bonus_amount,
        ct_bonus_extra_pay_paid=bool(bonus_amount or extra_amount),
        ct_employee_name=name,
        ct_employer_name=employer,
        ct_extra_pay_amount=extra_amount,
        ct_holiday_type="weekly_sunday_and_agreed_holidays" if holiday else "weekly_sunday",
        ct_housing_cost=housing_cost,
        ct_housing_provided=housing_provided,
        ct_meal_cost=meal_cost,
        ct_meal_provided=meal_provided,
        ct_monthly_work_hours=monthly_hours,
        ct_new_or_reentry_end_date=contract_end.isoformat(),
        ct_new_or_reentry_start_date=contract_start.isoformat(),
        ct_overtime_hourly_pay=round(hourly_rate * 1.5),
        ct_pay_cycle=pay_cycle,
        ct_pay_day=pay_day,
        ct_pay_period_end=end.isoformat(),
        ct_pay_period_start=start.isoformat(),
        ct_pay_timing="next_month",
        ct_pay_weekday=pay_weekday,
        ct_wage_amount=wage_amount,
        ct_wage_type=wage_type,
        ct_weekly_allowance_included=(wage_type == "monthly"),
        ct_work_day_end=work_day_end,
        ct_work_end_time=work_end,
        ct_work_start_time=work_start,
    )

    salary_record = dict(
        datetime=f"{payment.isoformat()} 09:{(index * 7) % 60:02d}:{(index * 11) % 60:02d}",
        record=employer,
        content="급여",
        memo=f"{month}월 급여",
        salary=True,
    )
    if index in {8, 18, 28}:
        first_payment = payment - dt.timedelta(days=2)
        transactions = [
            dict(
                datetime=f"{first_payment.isoformat()} 10:10:00",
                record=employer,
                content="급여",
                memo=f"{month}월 급여 1차",
                net_ratio=0.5,
                salary=True,
            ),
            dict(
                datetime=salary_record["datetime"],
                record=employer,
                content="급여",
                memo=f"{month}월 급여 잔액",
                net_rest=True,
                salary=True,
            ),
        ]
    elif index in {7, 17, 27}:
        private_day = payment - dt.timedelta(days=3)
        transactions = [
            dict(
                datetime=f"{private_day.isoformat()} 14:20:00",
                record="SOK CHENDA",
                content="타행이체",
                memo="개인송금",
                amount=120000 + index * 1000,
                salary=False,
            ),
            salary_record,
        ]
    else:
        transactions = [salary_record]

    spec = dict(
        id=case_id,
        name=name,
        employer=employer,
        period=(start.isoformat(), end.isoformat()),
        payment_date=payment.isoformat(),
        contract=contract,
        schedule=schedule,
        weekly_holiday_hours=0.0 if wage_type == "monthly" else 32.0,
        weekly_allowance_due=True,
        bonus_due=bool(bonus_amount),
        calc_formula=calc_formula,
        calc_item="기본급(일급)" if wage_type == "daily" else "기본급",
        insurance="full",
        transactions=transactions,
        inquiry=(start.isoformat(), (payment + dt.timedelta(days=30)).isoformat()),
    )
    if scheduled_override:
        spec["scheduled_override"] = scheduled_override
    return spec


SPECS = [make_spec(index) for index in range(30)]

