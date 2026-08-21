"""규칙별 표시 항목·해석 문구·대응 방안.

LLM 없이 법령 근거에 기반한 설명을 만드는 데 필요한 결정적 지식이다.
판정 성격(법적기준/문서정합성/산술검산/시스템규칙)이 해석 수위를 결정하고,
규칙별 대응 방안이 '그래서 무엇을 하면 되는가'를 채운다.
"""

from __future__ import annotations

# 규칙별로 리포트에 보여줄 비교 항목. 순서가 곧 표시 순서다.
SHOW: dict[str, tuple[str, ...]] = {
    "R00": ("cmp_employee_name_match", "cmp_employer_match", "cmp_worker_match",
            "cmp_period_match", "cmp_contract_period_match", "cmp_work_period_match",
            "cmp_account_holder_match",
            "ct_employee_name_norm", "ts_employee_name_norm", "ps_employee_name_norm",
            "bk_account_holder_norm"),
    "R01": ("cmp_wage_type_match", "calc_contract_hourly_wage", "calc_payslip_hourly_wage",
            "cmp_hourly_wage_gap", "param_wage_tolerance"),
    # 근무일수 차이(근무기록 ↔ 명세서)는 기록이 온전한지 보여주는 값이라 함께 낸다.
    # 커버리지만 보면 공휴일 때문에 줄어든 것인지 기록이 빠진 것인지 구분되지 않는다.
    "R02": ("ts_period_actual_hours", "ps_actual_hours_equiv", "cmp_actual_hours_gap",
            "cmp_overtime_hours_gap", "cmp_tolerance_hours",
            "ts_period_work_days", "cmp_work_days_gap", "ts_period_coverage"),
    "R03": ("cmp_bonus_gap", "cmp_extra_pay_gap", "cmp_overtime_pay_gap",
            "cmp_unmatched_pay_items", "cmp_tolerance_won",
            "cond_overtime_occurred", "cond_night_occurred",
            "cond_holiday_occurred", "cond_weekly_allowance_due"),
    "R04": ("calc_expected_housing_deduction", "calc_expected_meal_deduction",
            "cmp_housing_deduction_gap", "cmp_meal_deduction_gap"),
    "R05": ("calc_gross_pay", "cmp_gross_pay_gap", "param_gross_tolerance"),
    "R06": ("calc_total_deduction", "cmp_total_deduction_gap",
            "cond_deduction_components_complete"),
    "R07": ("calc_net_pay", "cmp_net_pay_gap", "cond_net_pay_nonpositive"),
    "R08": ("calc_net_pay", "calc_salary_deposit_total", "cmp_deposit_gap",
            "calc_salary_deposit_count"),
    "R09": ("calc_scheduled_payment_date", "calc_actual_payment_completion_date",
            "cmp_payment_date_gap_days", "ref_public_holiday"),
    "R10": ("ts_monthly_actual_hours", "cmp_contract_actual_hours_gap",
            "cmp_contract_actual_hours_gap_rate", "param_hours_tolerance",
            "cond_daily_limit_exceeded", "cond_worker_confirmed",
            "cond_change_reason_available"),
    "R11": ("ref_minimum_hourly_wage", "calc_applicable_year",
            "cmp_contract_minimum_wage_gap", "cmp_payslip_minimum_wage_gap",
            "cond_any_below_minimum_wage"),
}

# 계약서에서 함께 보여줄 원본값. 비교의 반대편을 드러낸다.
CONTRACT_CONTEXT: dict[str, tuple[str, ...]] = {
    # '사업장명 불일치'만으로는 무엇이 어떻게 다른지 알 수 없다.
    # 두 이름을 나란히 보여야 상호와 법인명의 차이인지 판단할 수 있다.
    "R00": ("ct_employer_name", "ct_employee_name"),
    "R01": ("ct_wage_type", "ct_wage_amount", "ct_monthly_work_hours"),
    "R02": ("ct_monthly_work_hours", "ct_break_hours", "ct_break_minutes"),
    "R03": ("ct_bonus_amount", "ct_extra_pay_amount", "ct_overtime_hourly_pay",
            "ct_weekly_allowance_included"),
    "R04": ("ct_housing_provided", "ct_housing_cost", "ct_meal_provided", "ct_meal_cost"),
    "R08": ("ct_pay_day",),
    "R09": ("ct_pay_day", "ct_pay_timing"),
    "R10": ("ct_monthly_work_hours", "ct_max_daily_work_hours"),
    "R11": ("ct_wage_type", "ct_wage_amount"),
}

# 명세서·입금내역에서 함께 보여줄 원본값.
DOCUMENT_CONTEXT: dict[str, tuple[str, ...]] = {
    "R00": ("ps_employer_name", "ps_employee_name", "bk_account_holder"),
    "R01": ("ps_ordinary_hourly_wage",),
    # 차이 금액만 보이면 무엇과 무엇을 비교했는지 표에서 확인할 수 없다.
    # 계약 약정액(CONTRACT_CONTEXT)과 나란히 놓아야 비교가 성립한다.
    "R03": ("ps_bonus_amount", "ps_other_allowance", "ps_overtime_pay"),
    "R04": ("ps_housing_deduction", "ps_meal_deduction"),
    "R05": ("ps_gross_pay",),
    "R06": ("ps_total_deduction",),
    "R07": ("ps_net_pay",),
    "R08": ("ps_net_pay",),
}


# 판정 성격이 결론 수위를 정한다. 근거 조항이 붙어 있다고 법 위반이 되는 것이 아니다.
BY_NATURE: dict[str, str] = {
    "법적기준": "법령이 직접 정한 의무와 관련된 항목입니다. 다만 이 결과만으로 위반이 확정되는 것은 아니며, "
                "사실관계 확인이 필요합니다.",
    "문서정합성": "문서에 적힌 값이 서로 다르다는 뜻입니다. 값이 다르다는 사실 자체가 법 위반은 아닙니다. "
                 "어느 쪽이 맞는지 확인하는 것이 먼저입니다.",
    "산술검산": "임금명세서 안에서 항목별 금액과 합계가 맞는지 계산해 본 결과입니다. "
               "법령이 이 계산식을 직접 정한 것은 아니므로, 작성 또는 계산 내용을 확인할 필요가 있다는 의미입니다.",
    "시스템규칙": "네 가지 문서가 같은 근로자·같은 기간의 자료인지 확인하는 절차입니다. "
                "법적 판단을 하는 항목이 아닙니다.",
}

# NOT_CHECKABLE 은 값이 아예 없는 경우와, 값은 있으나 그것만으로 판정을 끝낼 수 없는
# 경우를 모두 포함한다. 어느 쪽에도 맞도록 범용적으로 쓴다.
BY_STATUS: dict[str, str] = {
    "MISMATCH": "두 값이 허용 범위를 넘어 다릅니다.",
    "REVIEW": "바로 판단하기 어려워 사람이 확인해야 하는 상태입니다.",
    "REVIEW_HIGH": "우선 확인이 필요한 항목입니다. 법 위반이 확정된 것은 아닙니다.",
    "NOT_CHECKABLE": "현재 확인된 자료만으로는 판정을 완료할 수 없습니다.",
    "NOT_EVALUABLE": "현재 확인된 자료만으로는 판정할 수 없습니다.",
}


def interpretation(성격: str, status: str) -> list[str]:
    """판정 성격과 결과에 맞는 해석 문구."""
    lines = []
    if status in BY_STATUS:
        lines.append(BY_STATUS[status])
    if 성격 in BY_NATURE:
        lines.append(BY_NATURE[성격])
    return lines


# 규칙별 대응 방안. 근로자가 실제로 할 수 있는 행동만 적는다.
ACTIONS: dict[str, tuple[str, ...]] = {
    "R00": ("네 문서에 적힌 이름·여권번호·기간이 같은 사람의 같은 기간 자료인지 확인하세요.",
            "이름 철자가 문서마다 다르게 적힌 것이라면 사업주에게 정정을 요청하세요.",
            "다른 사람 또는 다른 기간의 문서가 섞였다면 해당 문서를 다시 받으세요."),
    "R01": ("근로계약서의 임금 형태(시급·일급·월급)와 금액을 확인하세요.",
            "임금명세서에 적용된 단가가 계약서와 같은지 비교하세요.",
            "계약 후 임금을 바꾸기로 합의했다면 변경 계약서나 합의서를 확인하세요.",
            "차이가 설명되지 않으면 사업주에게 계산 근거를 요청하세요."),
    "R02": ("근무기록부에 적힌 근무일과 시간이 실제와 맞는지 확인하세요.",
            "임금명세서에 적힌 근로시간 계산방법을 확인하세요.",
            "휴게시간이 실제로 쉰 시간으로 기록됐는지 확인하세요.",
            "차이가 계속 설명되지 않으면 근무기록 사본을 보관하고 상담을 받으세요."),
    "R03": ("근로계약서에 약정된 상여금·수당 항목과 금액을 확인하세요.",
            "임금명세서의 수당 항목별 금액과 계산방법을 비교하세요.",
            "연장·야간·휴일근로가 실제로 있었는지 근무기록으로 확인하세요.",
            "계약에 없는 항목이 지급됐다면 어떤 명목인지 사업주에게 확인하세요."),
    "R04": ("근로계약서의 숙박비·식비 근로자 부담액을 확인하세요.",
            "임금명세서에서 실제로 공제된 금액과 비교하세요.",
            "계약서와 다른 금액이 공제됐다면 별도 합의서나 공제동의서가 있는지 확인하세요.",
            "동의 없이 공제됐다면 관련 자료를 모아 상담을 받으세요."),
    "R05": ("임금명세서의 지급항목별 금액을 하나씩 더해 보세요.",
            "합계가 명세서의 총지급액과 맞는지 확인하세요.",
            "맞지 않으면 사업주에게 명세서 작성 내용의 확인을 요청하세요."),
    "R06": ("임금명세서의 공제항목별 금액을 하나씩 더해 보세요.",
            "합계가 명세서의 총공제액과 맞는지 확인하세요.",
            "공제 항목 중 무엇 때문에 공제됐는지 알 수 없는 항목이 있으면 설명을 요청하세요."),
    "R07": ("총지급액에서 총공제액을 뺀 금액이 실수령액과 같은지 확인하세요.",
            "맞지 않으면 사업주에게 명세서 작성 내용의 확인을 요청하세요."),
    "R08": ("임금명세서의 실수령액과 통장에 실제로 들어온 금액을 비교하세요.",
            "급여가 여러 번에 나누어 입금됐다면 해당 거래를 모두 합쳐 보세요.",
            "실제 입금액이 더 적다면 통장 거래내역과 명세서를 함께 보관하세요.",
            "차액이 설명되지 않으면 상담을 받으세요."),
    "R09": ("근로계약서에 적힌 임금 지급일을 확인하세요.",
            "통장에서 급여 전액이 들어온 날짜를 확인하세요.",
            "지급일이 공휴일이면 그 전날 지급하기로 되어 있는지 계약서를 확인하세요.",
            "지급일보다 늦게 지급됐다면 통장 내역을 보관하세요."),
    "R10": ("근로계약서의 소정근로시간과 1일 변경 상한시간을 확인하세요.",
            "실제 근무시간이 계약과 다른 이유가 무엇인지 확인하세요.",
            "근무시간을 바꿀 때 서로 확인하거나 합의했는지 확인하세요."),
    "R11": ("임금을 시간당 금액으로 환산한 값을 확인하세요.",
            "해당 연도의 최저시급과 비교하세요.",
            "최저임금에 포함되는 임금과 포함되지 않는 임금이 구분됐는지 확인하세요.",
            "최저임금보다 낮을 가능성이 있으면 계약서·명세서·통장 내역을 모아 상담을 받으세요."),
}


# NOT_CHECKABLE 은 세 가지를 모두 포함한다.
#   (1) 값 자체가 없는 경우
#   (2) 문서가 흐리거나 일부만 찍혀 값을 읽지 못한 경우
#   (3) 값은 있으나 그것만으로 판정을 끝낼 수 없는 경우
#       (예: R09 — 확인된 입금 누적액이 실수령액에 못 미쳐 전액 지급 완료일을 확정 못 함)
# 규칙별로 분기하지 않고 세 경우에 모두 맞는 문구 하나로 안내한다.
MISSING_DATA_ACTIONS = (
    "현재 자료만으로 확인하기 어려운 부분이 있습니다. 관련 정보나 추가 자료가 있는지 확인해 주세요.",
    "문서에 누락된 내용이 있거나 내용이 잘 보이지 않는 경우에는 다시 확인하거나 촬영해 주세요.",
)

# 확인 필요 항목이 하나도 없을 때. 본문이 비어 정상 판정의 뜻이 드러나지 않는 것을 막는다.
ALL_PASS = "R00~R11 검사 결과 현재 자료에서 확인이 필요한 항목이 발견되지 않았습니다."

# NOT_CHECKABLE·NOT_EVALUABLE 인데 추가 확인사항이 비어 있을 때의 기본 문구.
# 무엇이 부족한지 LLM 이 밝히지 못한 경우에도 근로자가 다음에 할 일은 알 수 있어야 한다.
MISSING_INFO = (
    "현재 제출된 자료만으로는 판정을 마칠 수 없습니다. "
    "판정에 필요한 항목이 가려지거나 빠지지 않았는지 확인하고 해당 문서를 다시 제출해 주세요.",
)

# REVIEW_HIGH 일 때 추가할 행동.
HIGH_RISK_ACTIONS = (
    "계약서·임금명세서·근무기록·통장 내역을 모두 사진으로 보관하세요.",
    "가까운 고용노동지청 또는 외국인노동자지원센터에 상담을 요청할 수 있습니다.",
)


def actions(rule_id: str, status: str) -> list[str]:
    """대응 방안. 판정 결과에 따라 항목을 더한다."""
    items = list(ACTIONS.get(rule_id.upper(), ()))
    if status in ("NOT_CHECKABLE", "NOT_EVALUABLE"):
        items = list(MISSING_DATA_ACTIONS) + items
    if status == "REVIEW_HIGH":
        items += list(HIGH_RISK_ACTIONS)
    return items


# --- 확인 질문 -------------------------------------------------------
# 규칙마다 고정 문구 하나를 둔다. 어느 항목이 어긋났든 답할 수 있도록 범용으로 쓴다.
# R08 은 '금액', R09 는 '지급일'을 본다. R08 이 PASS 여도 R09 만 걸릴 수 있으므로
# R09 질문을 비워 두지 않고, 지급일과 전액 수령일을 함께 묻는 문구를 둔다.

QUESTIONS: dict[str, tuple[str, ...]] = {
    "R00": ("네 문서가 모두 본인의 자료이고, 같은 근무기간·같은 사업장의 자료가 맞나요?",),
    "R01": ("계약서를 작성한 뒤 임금 금액이나 형태를 바꾸기로 합의한 적이 있나요?",),
    "R02": ("근무기록에 적힌 휴게시간은 실제로 쉬었던 시간인가요?",),
    "R03": ("계약서를 작성한 뒤 수당 금액을 변경하기로 새로 합의한 적이 있나요?",),
    "R04": ("실제 숙박비나 식비 부담액에 대해 계약서 외에 별도로 합의한 내용이 있나요?",),
    "R08": ("이번 급여에 해당하는 입금 거래가 모두 선택되었는지 다시 확인해 주세요. "
            "추가 거래가 있다면 함께 선택해 주세요.",),
    "R09": ("계약서에 적힌 급여 지급일과 실제로 급여를 전액 받은 날짜를 확인할 수 있나요?",),
    "R10": ("계약서와 다르게 근무시간이 변경될 때 변경 내용을 서로 확인하거나 합의했나요?",),
    "R11": ("임금 외에 매달 정기적으로 받는 다른 돈이 있나요?",),
}


def questions(rule_id: str, status: str) -> list[str]:
    """확인 질문. PASS 에는 만들지 않는다."""
    if status == "PASS":
        return []
    return list(QUESTIONS.get(rule_id.upper(), ()))
