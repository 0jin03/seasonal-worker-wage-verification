from __future__ import annotations

import calendar
from datetime import date, datetime, timedelta
from decimal import Decimal
from typing import Any, Callable

from .models import CaseBundle, RuleResult, RuleStatus
from .holidays import HolidayAPIError, PublicHolidayClient, env_value
from .normalization import (
    bool_value,
    normalize_name,
    normalize_wage_type,
    number,
    parse_date,
    parse_datetime,
    parse_time,
    resolve_recurring_date,
)

ZERO = Decimal("0")


class RuleEngine:
    """사용자가 확인한 v6 ``documents``를 입력으로 받는 R00~R11 룰 엔진."""

    DEFAULT_PARAMETERS = {
        "param_wage_tolerance": Decimal("10"),
        "param_fixed_allowance_tolerance": Decimal("10"),
        "param_rate_allowance_base_tolerance": Decimal("10"),
        "param_rate_allowance_hour_tolerance": Decimal("3"),
        # 팀 최종 결정: R05는 60 + (2 x 명세서 환산시간), R06은 0원.
        "param_gross_base_tolerance": Decimal("60"),
        "param_gross_hour_tolerance": Decimal("2"),
        "param_net_pay_base_tolerance": Decimal("70"),
        "param_net_pay_hour_tolerance": Decimal("5"),
        "param_minimum_hourly_wage": Decimal("10320"),
        "param_timesheet_min_coverage": Decimal("0.90"),
    }

    def __init__(
        self,
        parameters: dict[str, Any] | None = None,
        holiday_client: PublicHolidayClient | None = None,
    ) -> None:
        self.parameters = dict(self.DEFAULT_PARAMETERS)
        if parameters:
            self.parameters.update(parameters)
        self.derived: dict[str, Any] = {}
        self.case: CaseBundle | None = None
        self.holiday_client = holiday_client or PublicHolidayClient()
        self.holiday_payday_policy = "previous_business_day"

    def evaluate(self, case: CaseBundle) -> tuple[dict[str, Any], list[RuleResult]]:
        self.case = case
        self.derived = {}
        rules: list[Callable[[], RuleResult]] = [
            self.r00, self.r01, self.r02, self.r03, self.r04, self.r05,
            self.r06, self.r07, self.r08, self.r09, self.r10, self.r11,
        ]
        return self.derived, [rule() for rule in rules]

    @property
    def c(self):
        return self.case.contract  # type: ignore[union-attr]

    @property
    def t(self):
        return self.case.timesheet  # type: ignore[union-attr]

    @property
    def p(self):
        return self.case.payslip  # type: ignore[union-attr]

    @property
    def b(self):
        return self.case.bank  # type: ignore[union-attr]

    def result(self, rule: str, status: RuleStatus, reason: str, **cmp: Any) -> RuleResult:
        return RuleResult(rule, status, reason, cmp)

    def r00(self) -> RuleResult:
        names = [
            normalize_name(self.c.value("ct_employee_name")),
            normalize_name(self.t.value("ts_employee_name")),
            normalize_name(self.p.value("ps_employee_name")),
            normalize_name(self.b.value("bk_account_holder")),
        ]
        period_start = parse_date(self.p.value("ps_pay_period_start"))
        period_end = parse_date(self.p.value("ps_pay_period_end"))
        work_dates = [
            parse_date(row["ts_work_date"].value)
            for row in self.t.rows if row.get("ts_work_date")
        ]
        work_dates = [value for value in work_dates if value]
        name_match = all(names) and len(set(names)) == 1
        employer_match = (
            normalize_name(self.c.value("ct_employer_name"))
            == normalize_name(self.p.value("ps_employer_name"))
        )
        new_selected = bool_value(self.c.value("ct_new_or_reentry_selected")) is True
        change_selected = bool_value(self.c.value("ct_workplace_change_selected")) is True
        selected_start = selected_end = None
        if new_selected != change_selected:
            prefix = "ct_new_or_reentry" if new_selected else "ct_workplace_change"
            selected_start = parse_date(self.c.value(f"{prefix}_start_date"))
            selected_end = parse_date(self.c.value(f"{prefix}_end_date"))
        contract_period_match = bool(
            period_start and period_end and selected_start and selected_end
            and selected_start <= period_start <= period_end <= selected_end
        )
        work_period_match = bool(
            period_start and period_end and work_dates
            and all(period_start <= value <= period_end for value in work_dates)
        )
        self.derived.update(
            cmp_worker_match=name_match,
            cmp_employer_match=employer_match,
            cmp_contract_period_match=contract_period_match,
            cmp_work_period_match=work_period_match,
            cmp_period_match=contract_period_match and work_period_match,
        )
        if not all(names) or not period_start or not period_end:
            return self.result("R00", RuleStatus.NOT_CHECKABLE, "근로자명·예금주 또는 산정기간 정보가 부족합니다.")
        if new_selected == change_selected:
            return self.result("R00", RuleStatus.NOT_CHECKABLE, "적용할 계약유형을 하나로 확정할 수 없습니다.")
        if not name_match or not employer_match or not contract_period_match or (work_dates and not work_period_match):
            return self.result("R00", RuleStatus.REVIEW, "근로자·사업장·계약기간 또는 근무기간 연결을 확인해야 합니다.")
        self.derived["sys_case_id"] = self.case.case_id
        return self.result("R00", RuleStatus.PASS, "근로자와 산정기간이 연결됩니다.")

    def _contract_hourly(self) -> Decimal | None:
        amount = number(self.c.value("ct_wage_amount"))
        wage_type = normalize_wage_type(self.c.value("ct_wage_type"))
        if amount is None or wage_type is None:
            return None
        if wage_type == "hourly":
            return amount
        if wage_type == "monthly":
            hours = number(self.c.value("ct_monthly_work_hours"))
            return amount / hours if hours else None
        start = parse_time(self.c.value("ct_work_start_time"))
        end = parse_time(self.c.value("ct_work_end_time"))
        if wage_type == "daily" and start and end:
            duration = Decimal(str((datetime.combine(date.min, end) - datetime.combine(date.min, start)).seconds / 3600))
            breaks = (number(self.c.value("ct_break_hours")) or ZERO) + (number(self.c.value("ct_break_minutes")) or ZERO) / 60
            return amount / (duration - breaks) if duration > breaks else None
        if wage_type == "weekly":
            hours = number(self.c.value("ct_monthly_work_hours"))
            return amount / (hours / Decimal("4.345")) if hours else None
        return None

    def _contract_daily_hours(self) -> Decimal | None:
        start = parse_time(self.c.value("ct_work_start_time"))
        end = parse_time(self.c.value("ct_work_end_time"))
        if not start or not end:
            return None
        duration = Decimal(str((datetime.combine(date.min, end) - datetime.combine(date.min, start)).seconds / 3600))
        breaks = (number(self.c.value("ct_break_hours")) or ZERO) + (number(self.c.value("ct_break_minutes")) or ZERO) / 60
        return duration - breaks if duration > breaks else None

    def r01(self) -> RuleResult:
        contract_hourly = self._contract_hourly()
        payslip_hourly = number(self.p.value("ps_ordinary_hourly_wage"))
        if payslip_hourly is None:
            base = number(self.p.value("ps_base_pay"))
            hours = number(self.p.value("ps_paid_regular_hours"))
            payslip_hourly = base / hours if base is not None and hours else None
        ct_type = normalize_wage_type(self.c.value("ct_wage_type"))
        ps_type = normalize_wage_type(self.p.value("ps_wage_type"))
        self.derived.update(
            calc_contract_hourly_wage=contract_hourly,
            calc_payslip_hourly_wage=payslip_hourly,
            cmp_wage_type_match=ct_type == ps_type,
        )
        if contract_hourly is None or payslip_hourly is None:
            return self.result("R01", RuleStatus.NOT_CHECKABLE, "임금 또는 시급 환산에 필요한 값이 부족합니다.")
        gap = payslip_hourly - contract_hourly
        self.derived["cmp_hourly_wage_gap"] = gap
        period_start = parse_date(self.p.value("ps_pay_period_start"))
        period_end = parse_date(self.p.value("ps_pay_period_end"))
        self.derived.update(
            ct_resolved_pay_period_start=resolve_recurring_date(self.c.value("ct_pay_period_start"), period_start),
            ct_resolved_pay_period_end=resolve_recurring_date(self.c.value("ct_pay_period_end"), period_end, end=True),
        )
        partial = bool(
            ct_type == "monthly" and period_start and period_end
            and (period_start.day != 1 or period_end.day != calendar.monthrange(period_end.year, period_end.month)[1])
        )
        self.derived["cond_partial_period"] = partial
        if partial:
            return self.result("R01", RuleStatus.REVIEW, "월급제 일부기간 정산이므로 환산값 확인이 필요합니다.", gap=gap)
        # 양쪽 모두 시급으로 명시된 경우만 직접 비교(0원)하고, 그 밖에는
        # 시급 환산값끼리 비교하면서 원 단위 환산 오차 10원을 적용한다.
        tolerance = ZERO if ct_type == ps_type == "hourly" else self.parameters["param_wage_tolerance"]
        self.derived["param_wage_tolerance_applied"] = tolerance
        status = RuleStatus.PASS if abs(gap) <= tolerance else RuleStatus.MISMATCH
        return self.result("R01", status, "계약 임금과 명세서 적용단가를 비교했습니다.", gap=gap, tolerance=tolerance)

    def _timesheet_hours(self) -> tuple[Decimal, Decimal, int]:
        total = overtime = monthly_total = ZERO
        days = 0
        daily: list[dict[str, Any]] = []
        period_start = parse_date(self.p.value("ps_pay_period_start"))
        period_end = parse_date(self.p.value("ps_pay_period_end"))
        for row in self.t.rows:
            work_date = parse_date(row["ts_work_date"].value) if row.get("ts_work_date") else None
            explicit = number(row["ts_actual_work_hours"].value) if row.get("ts_actual_work_hours") else None
            start = parse_time(row["ts_work_start_time"].value) if row.get("ts_work_start_time") else None
            end = parse_time(row["ts_work_end_time"].value) if row.get("ts_work_end_time") else None
            hours = explicit
            if hours is None and start and end:
                raw = Decimal(str((datetime.combine(date.min, end) - datetime.combine(date.min, start)).seconds / 3600))
                breaks = number(row["ts_break_minutes"].value) if row.get("ts_break_minutes") else None
                if breaks is None:
                    breaks = (number(self.c.value("ct_break_hours")) or ZERO) * 60 + (number(self.c.value("ct_break_minutes")) or ZERO)
                hours = max(ZERO, raw - breaks / 60)
            if hours is None:
                continue
            note = row["ts_work_note"].value if row.get("ts_work_note") else None
            daily.append({"date": work_date, "hours": hours, "work_note": note})
            in_period = not (period_start and period_end and work_date) or period_start <= work_date <= period_end
            if in_period:
                total += hours
                scheduled_daily = self._contract_daily_hours() or Decimal("8")
                overtime += max(ZERO, hours - scheduled_daily)
                days += 1
            target_month = period_end or work_date
            if work_date and target_month and (work_date.year, work_date.month) == (target_month.year, target_month.month):
                monthly_total += hours
        self.derived.update(
            ts_daily_actual_hours=daily,
            ts_period_actual_hours=total,
            ts_monthly_actual_hours=monthly_total,
            ts_period_work_days=days,
        )
        return total, overtime, days

    def _scheduled_work_dates(self) -> set[date] | None:
        start = parse_date(self.p.value("ps_pay_period_start"))
        end = parse_date(self.p.value("ps_pay_period_end"))
        if not start or not end or end < start:
            return None
        weekday_map = {"MON": 0, "TUE": 1, "WED": 2, "THU": 3, "FRI": 4, "SAT": 5, "SUN": 6}
        first = weekday_map.get(str(self.c.value("ct_work_day_start", "MON")).upper(), 0)
        last = weekday_map.get(str(self.c.value("ct_work_day_end", "FRI")).upper(), 4)
        allowed = set(range(first, last + 1)) if first <= last else set(range(first, 7)) | set(range(0, last + 1))
        dates = {
            start + timedelta(days=offset)
            for offset in range((end - start).days + 1)
            if (start + timedelta(days=offset)).weekday() in allowed
        }
        return dates or None

    def r02(self) -> RuleResult:
        record_available = bool_value(self.t.value("ts_record_available", True))
        if record_available is False or not self.t.rows:
            return self.result("R02", RuleStatus.NOT_CHECKABLE, "근무기록이 없어 실근로시간을 확인할 수 없습니다.")
        actual, overtime, days = self._timesheet_hours()
        scheduled_dates = self._scheduled_work_dates()
        expected_days = Decimal(len(scheduled_dates)) if scheduled_dates else None
        recorded_dates = {
            item["date"] for item in self.derived["ts_daily_actual_hours"]
            if item.get("date") in scheduled_dates
        } if scheduled_dates else set()
        recorded_scheduled_days = Decimal(len(recorded_dates))
        coverage = recorded_scheduled_days / expected_days if expected_days else None
        self.derived.update(
            ts_expected_work_days=expected_days,
            ts_recorded_scheduled_work_days=recorded_scheduled_days,
            ts_period_coverage=coverage,
            param_timesheet_min_coverage=self.parameters["param_timesheet_min_coverage"],
        )
        if coverage is None:
            return self.result("R02", RuleStatus.NOT_CHECKABLE, "소정근로일을 계산할 수 없어 커버리지를 확인할 수 없습니다.")
        if coverage < self.parameters["param_timesheet_min_coverage"]:
            return self.result("R02", RuleStatus.NOT_CHECKABLE, "근무기록 커버리지가 90% 미만입니다.", coverage=coverage)
        paid = sum((number(self.p.value(key)) or ZERO for key in ("ps_paid_regular_hours", "ps_paid_overtime_hours", "ps_paid_holiday_hours")), ZERO)
        paid_overtime = number(self.p.value("ps_paid_overtime_hours")) or ZERO
        total_gap = actual - paid
        overtime_gap = overtime - paid_overtime
        total_tol = min(max(Decimal(days) * Decimal("0.083"), Decimal("0.5")), paid * Decimal("0.03")) if paid else Decimal("0.5")
        scheduled_daily = self._contract_daily_hours() or Decimal("8")
        overtime_days = sum(1 for item in self.derived["ts_daily_actual_hours"] if item["hours"] > scheduled_daily)
        overtime_tol = max(Decimal("0.5"), Decimal(overtime_days) * Decimal("0.083"))
        self.derived.update(
            ps_actual_hours_equiv=paid,
            cmp_actual_hours_gap=total_gap,
            cmp_overtime_hours_gap=overtime_gap,
            cmp_tolerance_hours=total_tol,
            cmp_tolerance_overtime_hours=overtime_tol,
            cmp_tolerance_work_days=ZERO,
        )
        if abs(total_gap) > total_tol or abs(overtime_gap) > overtime_tol:
            return self.result("R02", RuleStatus.MISMATCH, "근무기록과 명세서 계산시간이 허용범위를 벗어납니다.")
        return self.result("R02", RuleStatus.PASS, "근무시간이 허용범위 내에서 일치합니다.")

    def r03(self) -> RuleResult:
        unmatched = [
            line.get("item_name")
            for line in (self.p.value("ps_pay_lines") or [])
            if line.get("mapped_to") is None and (number(line.get("amount")) or ZERO) != ZERO
        ]
        self.derived["cmp_unmatched_pay_items"] = unmatched
        checks = []
        for contract_field, payslip_field, label in (
            ("ct_bonus_amount", "ps_bonus_amount", "상여금"),
            ("ct_extra_pay_amount", "ps_other_allowance", "기타수당"),
        ):
            expected = number(self.c.value(contract_field))
            actual = number(self.p.value(payslip_field))
            if expected is not None:
                checks.append((label, actual or ZERO, expected, self.parameters["param_fixed_allowance_tolerance"]))
        overtime_hours = number(self.p.value("ps_paid_overtime_hours")) or ZERO
        overtime_rate = number(self.c.value("ct_overtime_hourly_pay"))
        if overtime_hours and overtime_rate is not None:
            tolerance = self.parameters["param_rate_allowance_base_tolerance"] + self.parameters["param_rate_allowance_hour_tolerance"] * overtime_hours
            checks.append(("연장수당", number(self.p.value("ps_overtime_pay")) or ZERO, overtime_rate * overtime_hours, tolerance))
        failed = [(label, actual - expected, tolerance) for label, actual, expected, tolerance in checks if abs(actual - expected) > tolerance]
        if failed:
            return self.result("R03", RuleStatus.MISMATCH, "수당 지급액이 계약 기준과 다릅니다.", failed=failed)
        if unmatched:
            return self.result("R03", RuleStatus.REVIEW, "계약 근거가 확인되지 않은 지급항목이 있습니다.", items=unmatched)
        if not checks:
            return self.result("R03", RuleStatus.NOT_CHECKABLE, "비교할 수당 조건이 없습니다.")
        return self.result("R03", RuleStatus.PASS, "수당과 상여금이 허용범위 내에서 일치합니다.")

    def r04(self) -> RuleResult:
        gaps = {}
        for kind in ("housing", "meal"):
            provided = bool_value(self.c.value(f"ct_{kind}_provided"))
            allowed = number(self.c.value(f"ct_{kind}_cost"))
            actual = number(self.p.value(f"ps_{kind}_deduction"))
            if provided is None or allowed is None or actual is None:
                return self.result("R04", RuleStatus.NOT_CHECKABLE, "숙박비·식비 제공 여부 또는 금액이 누락되었습니다.")
            gaps[kind] = actual - (allowed if provided else ZERO)
        self.derived.update(cmp_housing_deduction_gap=gaps["housing"], cmp_meal_deduction_gap=gaps["meal"])
        if any(value != ZERO for value in gaps.values()):
            return self.result("R04", RuleStatus.MISMATCH, "계약상 숙식비 부담액과 명세서 공제액이 다릅니다.", **gaps)
        return self.result("R04", RuleStatus.PASS, "숙박비·식비 공제가 계약과 일치합니다.")

    def r05(self) -> RuleResult:
        fields = ("ps_base_pay", "ps_bonus_amount", "ps_other_allowance", "ps_weekly_allowance", "ps_overtime_pay", "ps_night_work_pay", "ps_holiday_work_pay")
        values = [number(self.p.value(key)) for key in fields]
        unresolved = [field for field, value in zip(fields, values) if value is None]
        if unresolved:
            return self.result(
                "R05", RuleStatus.NOT_CHECKABLE,
                "지급항목에 사용자가 0원 또는 실제 금액으로 확정하지 않은 값이 있습니다.",
                unresolved_fields=unresolved,
            )
        calc = sum(values, ZERO)
        printed = number(self.p.value("ps_gross_pay"))
        self.derived["calc_gross_pay"] = calc
        if printed is None:
            return self.result("R05", RuleStatus.NOT_CHECKABLE, "명세서 총지급액이 없습니다.")
        gap = calc - printed
        hours = self.derived.get("ps_actual_hours_equiv", ZERO)
        tolerance = self.parameters["param_gross_base_tolerance"] + self.parameters["param_gross_hour_tolerance"] * hours
        self.derived.update(cmp_gross_pay_gap=gap, param_gross_tolerance=tolerance)
        status = RuleStatus.PASS if abs(gap) <= tolerance else RuleStatus.MISMATCH
        return self.result("R05", status, "지급항목 합계와 인쇄된 총지급액을 비교했습니다.", gap=gap, tolerance=tolerance)

    def r06(self) -> RuleResult:
        fields = ("ps_national_pension", "ps_health_insurance", "ps_long_term_care_insurance", "ps_employment_insurance", "ps_income_tax", "ps_local_income_tax", "ps_housing_deduction", "ps_meal_deduction", "ps_other_deduction")
        values = [number(self.p.value(key)) for key in fields]
        complete = all(value is not None for value in values)
        calc = sum((value or ZERO for value in values), ZERO)
        printed = number(self.p.value("ps_total_deduction"))
        self.derived.update(calc_total_deduction=calc, cond_deduction_components_complete=complete)
        if not complete or printed is None:
            return self.result("R06", RuleStatus.NOT_CHECKABLE, "공제항목이 누락되어 검산할 수 없습니다.")
        gap = printed - calc
        self.derived.update(cmp_total_deduction_gap=gap, cmp_tolerance_deduction_won=ZERO)
        status = RuleStatus.PASS if gap == ZERO else RuleStatus.MISMATCH
        return self.result("R06", status, "공제항목 합계와 인쇄된 총공제액을 0원 허용오차로 비교했습니다.", gap=gap, tolerance=ZERO)

    def r07(self) -> RuleResult:
        gross = self.derived.get("calc_gross_pay")
        deduction = self.derived.get("calc_total_deduction")
        printed = number(self.p.value("ps_net_pay"))
        if gross is None or deduction is None:
            return self.result("R07", RuleStatus.NOT_CHECKABLE, "총지급액 또는 총공제액이 없습니다.")
        calc = gross - deduction
        self.derived["calc_net_pay"] = calc
        if printed is None:
            return self.result("R07", RuleStatus.REVIEW, "실수령액 인쇄값 확인이 필요합니다.", calculated=calc)
        gap = printed - calc
        hours = self.derived.get("ps_actual_hours_equiv", ZERO)
        tolerance = self.parameters["param_net_pay_base_tolerance"] + self.parameters["param_net_pay_hour_tolerance"] * hours
        self.derived.update(cmp_net_pay_gap=gap, cmp_tolerance_net_pay_won=tolerance)
        if calc <= ZERO:
            return self.result("R07", RuleStatus.REVIEW_HIGH, "재계산 실수령액이 0 이하입니다.", gap=gap)
        status = RuleStatus.PASS if abs(gap) <= tolerance else RuleStatus.MISMATCH
        return self.result("R07", status, "재계산 실수령액과 인쇄값을 비교했습니다.", gap=gap, tolerance=tolerance)

    def _selected_transactions(self) -> list[dict[str, Any]]:
        selected = []
        for row in self.b.rows:
            values = {key: value.value for key, value in row.items()}
            if bool_value(values.get("usr_salary_transaction_selected")) is True:
                selected.append(values)
        return selected

    def r08(self) -> RuleResult:
        target = self.derived.get("calc_net_pay")
        selected = self._selected_transactions()
        inquiry_start = parse_date(self.b.value("bk_inquiry_start_date"))
        inquiry_end = parse_date(self.b.value("bk_inquiry_end_date"))
        payment_date = parse_date(self.p.value("ps_payment_date"))
        total = sum((number(row.get("bk_deposit_amount")) or ZERO for row in selected), ZERO)
        selections = [
            bool_value(row.get("usr_salary_transaction_selected").value) is True
            if row.get("usr_salary_transaction_selected") else False
            for row in self.b.rows
        ]
        self.derived.update(
            calc_salary_deposit_count=len(selected),
            calc_salary_deposit_total=total,
            selected_salary_transactions=selected,
            usr_salary_transaction_selected=selections,
        )
        if not inquiry_start or not inquiry_end or not payment_date or not inquiry_start <= payment_date <= inquiry_end:
            return self.result("R08", RuleStatus.NOT_CHECKABLE, "통장 조회기간이 명세서 지급일을 포함하지 않습니다.")
        if target is None or not selected:
            return self.result("R08", RuleStatus.NOT_CHECKABLE, "사용자가 확정한 급여 입금 거래가 없습니다.")
        gap = total - target
        self.derived.update(cmp_deposit_gap=gap, salary_payment_target=target)
        status = RuleStatus.PASS if gap == ZERO else RuleStatus.MISMATCH
        return self.result("R08", status, "선택한 급여 입금합계와 실수령액을 비교했습니다.", gap=gap)

    def _scheduled_payment_date(self) -> date | None:
        period_end = parse_date(self.p.value("ps_pay_period_end"))
        if not period_end:
            return None
        timing = str(self.c.value("ct_pay_timing", "next_month")).strip().lower()
        cycle = str(self.c.value("ct_pay_cycle", "")).strip().lower()
        if cycle in {"weekly", "주", "주급"}:
            weekday = str(self.c.value("ct_pay_weekday", "FRI")).strip().upper()
            target = {"MON": 0, "월": 0, "월요일": 0, "TUE": 1, "화": 1, "화요일": 1, "WED": 2, "수": 2, "수요일": 2, "THU": 3, "목": 3, "목요일": 3, "FRI": 4, "금": 4, "금요일": 4, "SAT": 5, "토": 5, "토요일": 5, "SUN": 6, "일": 6, "일요일": 6}.get(weekday, 4)
            scheduled = period_end - timedelta(days=period_end.weekday()) + timedelta(days=target)
            return scheduled + timedelta(days=7) if timing in {"next_week", "익주", "다음주"} else scheduled
        add_month = timing not in {"same_month", "당월", "이번달"}
        year, month = period_end.year, period_end.month + (1 if add_month else 0)
        if month == 13:
            year, month = year + 1, 1
        day = number(self.c.value("ct_pay_day"))
        return date(year, month, min(int(day), calendar.monthrange(year, month)[1])) if day is not None else None

    def r09(self) -> RuleResult:
        target = self.derived.get("salary_payment_target", self.derived.get("calc_net_pay"))
        selected = self.derived.get("selected_salary_transactions", self._selected_transactions())
        scheduled = self._scheduled_payment_date()
        if target is None or not selected or scheduled is None or target <= ZERO:
            return self.result("R09", RuleStatus.NOT_CHECKABLE, "전액 지급 완료일을 확정할 수 없습니다.")
        cumulative = ZERO
        cumulative_series = []
        completion = None
        for row in sorted(selected, key=lambda item: parse_datetime(item.get("bk_transaction_datetime")) or datetime.max):
            cumulative += number(row.get("bk_deposit_amount")) or ZERO
            cumulative_series.append({
                "bk_transaction_datetime": row.get("bk_transaction_datetime"),
                "cumulative_amount": cumulative,
            })
            if cumulative >= target:
                parsed = parse_datetime(row.get("bk_transaction_datetime"))
                completion = parsed.date() if parsed else None
                break
        self.derived.update(
            calc_scheduled_payment_date=scheduled,
            calc_actual_payment_completion_date=completion,
            calc_cumulative_salary_deposit=cumulative_series,
        )
        if completion is None:
            return self.result("R09", RuleStatus.NOT_CHECKABLE, "입금 누적액이 실수령액에 도달하지 않았습니다.")
        original_scheduled = scheduled
        holiday_adjustment_error = None
        try:
            scheduled = self.holiday_client.adjusted_business_day(scheduled, "previous_business_day")
        except HolidayAPIError as exc:
            holiday_adjustment_error = str(exc)
        self.derived.update(
            calc_original_scheduled_payment_date=original_scheduled,
            calc_adjusted_scheduled_payment_date=scheduled,
            calc_accepted_payment_dates=[scheduled],
            holiday_payday_policy="previous_business_day",
        )
        gap = (completion - scheduled).days
        self.derived["cmp_payment_date_gap_days"] = gap
        if holiday_adjustment_error:
            return self.result(
                "R09", RuleStatus.REVIEW,
                "공휴일 API를 조회하지 못해 지급일을 사람이 확인해야 합니다.",
                gap_days=gap, api_error=holiday_adjustment_error,
            )
        if gap != 0:
            return self.result("R09", RuleStatus.MISMATCH, "공휴일 조정 지급일과 실제 전액 지급일이 다릅니다.", gap_days=gap)
        return self.result("R09", RuleStatus.PASS, "약정 지급일에 전액 지급되었습니다.", gap_days=gap)

    def r10(self) -> RuleResult:
        actual = self.derived.get("ts_monthly_actual_hours")
        contract = number(self.c.value("ct_monthly_work_hours"))
        if not self.t.rows or actual is None or contract is None:
            return self.result("R10", RuleStatus.NOT_CHECKABLE, "계약시간 또는 근무기록이 없습니다.")
        gap = actual - contract
        daily = self.derived.get("ts_daily_actual_hours", [])
        max_daily = number(self.c.value("ct_max_daily_work_hours"))
        contract_daily = self._contract_daily_hours()
        if max_daily is None or contract_daily is None:
            return self.result("R10", RuleStatus.NOT_CHECKABLE, "계약상 일별 기본시간 또는 변경 가능 상한이 없습니다.", gap=gap)
        exceeded = [item for item in daily if item["hours"] > max_daily]
        changed = [item for item in daily if item["hours"] != contract_daily]
        missing_reason = [item for item in changed if not str(item.get("work_note") or "").strip()]
        confirmed = bool_value(self.t.value("ts_worker_confirmed")) is True
        has_reason = not missing_reason
        self.derived.update(
            calc_contract_daily_hours=contract_daily,
            cmp_contract_actual_hours_gap=gap,
            cmp_contract_actual_hours_gap_rate=(gap / contract * 100 if contract else None),
            cond_daily_limit_exceeded=bool(exceeded),
            cond_change_reason_available=has_reason,
            cond_worker_confirmed=confirmed,
        )
        if exceeded or not confirmed or missing_reason:
            return self.result(
                "R10", RuleStatus.REVIEW,
                "일별 상한·변경 날짜의 사유·근로자 확인을 검토해야 합니다.",
                gap=gap, exceeded_days=exceeded, changed_days_missing_reason=missing_reason,
            )
        return self.result("R10", RuleStatus.PASS, "월시간 차이는 정보로 제공하며 일별 변경 조건을 충족합니다.", gap=gap)

    def r11(self) -> RuleResult:
        period_start = parse_date(self.p.value("ps_pay_period_start"))
        period_end = parse_date(self.p.value("ps_pay_period_end"))
        if period_start and period_end and period_start.year != period_end.year:
            return self.result("R11", RuleStatus.REVIEW, "급여 산정기간이 두 연도에 걸쳐 있습니다.")
        minimum = number(self.parameters["param_minimum_hourly_wage"])
        contract = self.derived.get("calc_contract_hourly_wage")
        payslip = self.derived.get("calc_payslip_hourly_wage")
        if minimum is None or (contract is None and payslip is None):
            return self.result("R11", RuleStatus.NOT_CHECKABLE, "최저임금 비교에 필요한 시급이 없습니다.")
        gaps = {"contract": contract - minimum if contract is not None else None, "payslip": payslip - minimum if payslip is not None else None}
        self.derived.update(
            ref_minimum_hourly_wage=minimum,
            cmp_contract_minimum_wage_gap=gaps["contract"],
            cmp_payslip_minimum_wage_gap=gaps["payslip"],
        )
        if any(value is not None and value < 0 for value in gaps.values()):
            return self.result("R11", RuleStatus.REVIEW_HIGH, "최저임금 미달 가능성이 있어 우선 확인이 필요합니다.", **gaps)
        if contract is None or payslip is None:
            return self.result("R11", RuleStatus.REVIEW, "한쪽 시급만 계산되어 추가 확인이 필요합니다.", **gaps)
        return self.result("R11", RuleStatus.PASS, "계약·명세서 시급이 최저임금 기준 이상입니다.")
