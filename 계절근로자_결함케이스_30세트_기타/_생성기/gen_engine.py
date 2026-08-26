# -*- coding: utf-8 -*-
"""계절근로자 급여검증 합성 케이스 생성기 — R00-R11 v3.2 스키마

문서(계약서/근무기록/임금명세서/입금내역서) 원본피처를 먼저 만들고,
R00~R11 규칙 엔진으로 derived / rule_results를 산출한다.
판정은 손으로 적지 않고 전부 엔진이 계산한다.
"""
import json, re, datetime as dt
from collections import OrderedDict

MIN_WAGE = {2026: 10320, 2027: 10850}

# ---------------- 팀 파라미터 (기존 10세트와 동일 기준) ----------------
PARAM_WAGE_TOL = 10          # 원
PARAM_GROSS_TOL = 10         # 원
PARAM_HOURS_TOL = 8.0        # 시간 (월 단위)
COVERAGE_THRESHOLD = 0.9     # 소정근로일 대비 기록일 비율


# ---------------- 유틸 ----------------
def h(s):
    a, b = s.split(':')
    return int(a) + int(b) / 60


def day_hours(start, end, brk_min):
    s, e = h(start), h(end)
    if e <= s:
        e += 24
    return round(e - s - brk_min / 60, 2)


def night_hours(start, end):
    """야간(22:00~06:00) 근로시간"""
    s, e = h(start), h(end)
    if e <= s:
        e += 24
    tot = 0.0
    for a, b in [(0, 6), (22, 30)]:
        tot += max(0.0, min(e, b) - max(s, a))
    return round(tot, 2)


def norm(name):
    return re.sub(r'[^A-Z0-9가-힣]', '', (name or '').upper())


def D(s):
    return dt.date.fromisoformat(s)


def won(n):
    return f"{round(n):,}"


def hr(x):
    return f"{x:g}"


def r2(x):
    return round(x + 1e-9, 2)


def add_month(d, n):
    y, m = d.year, d.month + n
    y += (m - 1) // 12
    m = (m - 1) % 12 + 1
    return y, m


def clamp_day(y, m, day):
    import calendar
    return dt.date(y, m, min(day, calendar.monthrange(y, m)[1]))


# ---------------- 근무기록 생성 ----------------
def build_lines(spec):
    """spec['schedule'] 로부터 근무기록 lines 생성"""
    sc = spec['schedule']
    p0, p1 = D(spec['period'][0]), D(spec['period'][1])
    wdays = sc['weekdays']                    # 0=월
    start, end, brk = sc['start'], sc['end'], sc['break']
    overrides = sc.get('overrides', {})       # date -> (start, end, break, holiday, note)
    absent = set(sc.get('absent', []))
    extra = sc.get('extra', {})               # date -> (start, end, break, holiday, note)
    only = sc.get('only_dates')               # 기록이 이 날짜에만 존재 (커버리지 결함)

    lines = []
    d = p0
    while d <= p1:
        ds = d.isoformat()
        if ds not in absent and d.weekday() in wdays and (only is None or ds in only):
            s, e, b, hol, note = overrides.get(ds, (start, end, brk, False, None))
            lines.append(dict(ts_work_date=ds, ts_work_start_time=s, ts_work_end_time=e,
                              ts_break_minutes=b, ts_holiday_worked=hol, ts_work_note=note))
        d += dt.timedelta(days=1)
    for ds, (s, e, b, hol, note) in sorted(extra.items()):
        lines.append(dict(ts_work_date=ds, ts_work_start_time=s, ts_work_end_time=e,
                          ts_break_minutes=b, ts_holiday_worked=hol, ts_work_note=note))
    lines.sort(key=lambda x: x['ts_work_date'])
    # 스키마 키 순서
    order = ['ts_break_minutes', 'ts_holiday_worked', 'ts_work_date',
             'ts_work_end_time', 'ts_work_note', 'ts_work_start_time']
    return [OrderedDict((k, ln[k]) for k in order) for ln in lines]


def scheduled_work_days(spec):
    """급여 산정기간 내 소정근로일 수"""
    sc = spec['schedule']
    p0, p1 = D(spec['period'][0]), D(spec['period'][1])
    n, d = 0, p0
    while d <= p1:
        if d.weekday() in sc['weekdays']:
            n += 1
        d += dt.timedelta(days=1)
    return n


# ---------------- 케이스 조립 ----------------
def build_case(spec):
    ct = dict(spec['contract'])
    period_start, period_end = spec['period']
    stageA = spec.get('stageA', {})   # 항목 단위 결함 (총액 재계산 전)
    stageB = spec.get('stageB', {})   # 인쇄 총액·입금·날짜 결함 (재계산 후)

    # ---- 근무기록 ----
    lines = build_lines(spec)
    daily = [day_hours(l['ts_work_start_time'], l['ts_work_end_time'], l['ts_break_minutes'])
             for l in lines]
    ct_break_total_minutes = int(round((ct['ct_break_hours'] or 0) * 60 + (ct['ct_break_minutes'] or 0)))
    _cs, _ce = h(ct['ct_work_start_time']), h(ct['ct_work_end_time'])
    if _ce <= _cs:
        _ce += 24          # 야간교대 등 자정을 넘기는 소정근로
    contract_daily_hours = r2(_ce - _cs - ct_break_total_minutes / 60)

    ts_period_actual = r2(sum(daily))
    ts_overtime = r2(sum(max(0.0, x - contract_daily_hours) for x in daily))
    ts_holiday = r2(sum(x for x, l in zip(daily, lines) if l['ts_holiday_worked']))
    ts_night = r2(sum(night_hours(l['ts_work_start_time'], l['ts_work_end_time']) for l in lines))
    ts_workdays = len(lines)

    timesheet = OrderedDict([
        ('ts_employee_name', spec.get('ts_name', spec['name'])),
        ('ts_record_available', spec.get('record_available', True)),
        ('ts_worker_confirmed', spec.get('worker_confirmed', True)),
        ('lines', lines),
    ])

    # ---- 계약 환산 시급 ----
    if ct['ct_wage_type'] == 'hourly':
        contract_hourly = float(ct['ct_wage_amount'])
    elif ct['ct_wage_type'] == 'monthly':
        contract_hourly = round(ct['ct_wage_amount'] / ct['ct_monthly_work_hours'], 2)
    elif ct['ct_wage_type'] == 'daily':
        contract_hourly = round(ct['ct_wage_amount'] / contract_daily_hours, 2)
    else:
        contract_hourly = None

    # ---- 임금명세서 지급항목 ----
    ph = dict(regular=r2(ts_period_actual - ts_overtime - ts_holiday),
              overtime=ts_overtime, holiday=ts_holiday, night=ts_night,
              weekly=spec.get('weekly_holiday_hours', 0.0),
              workdays=ts_workdays)
    ph.update(stageA.get('hours', {}))

    applied_hourly = stageA.get('applied_hourly', round(contract_hourly))
    ot_rate = ct['ct_overtime_hourly_pay']

    if ct['ct_wage_type'] == 'monthly':
        base = ct['ct_wage_amount']
    elif ct['ct_wage_type'] == 'daily':
        base = round(ct['ct_wage_amount'] * ph['workdays'])
    else:
        base = round(applied_hourly * ph['regular'])
    base = stageA.get('base_pay', base)

    weekly_allow = 0 if ct['ct_weekly_allowance_included'] else round(applied_hourly * ph['weekly'])
    pay = dict(
        base_pay=base,
        weekly_allowance=stageA.get('weekly_allowance', weekly_allow),
        overtime_pay=stageA.get('overtime_pay', round(ot_rate * ph['overtime'])),
        night_work_pay=stageA.get('night_work_pay', round(applied_hourly * 0.5 * ph['night'])),
        holiday_work_pay=stageA.get('holiday_work_pay', round(applied_hourly * 1.5 * ph['holiday'])),
        bonus_amount=stageA.get('bonus_amount', ct['ct_bonus_amount'] if spec.get('bonus_due') else 0),
        other_allowance=stageA.get('other_allowance', ct['ct_extra_pay_amount']),
    )
    gross_calc = sum(v for v in pay.values() if v is not None)

    # ---- 공제항목 ----
    ins = spec.get('insurance', 'full')       # full / employment_only / none
    if ins == 'full':
        national_pension = round(gross_calc * 0.045 / 10) * 10
        health = round(gross_calc * 0.03545 / 10) * 10
        care = round(health * 0.1295 / 10) * 10
        employment = round(gross_calc * 0.009 / 10) * 10
    elif ins == 'employment_only':
        national_pension = 0
        health = 0
        care = 0
        employment = round(gross_calc * 0.009 / 10) * 10
    else:
        national_pension = health = care = employment = 0
    income_tax = spec.get('income_tax', round(gross_calc * 0.01 / 10) * 10)
    ded = dict(
        income_tax=income_tax,
        local_income_tax=round(income_tax * 0.1 / 10) * 10,
        national_pension=national_pension,
        health_insurance=health,
        employment_insurance=employment,
        long_term_care_insurance=care,
        housing_deduction=(ct['ct_housing_cost'] if ct['ct_housing_provided'] else 0),
        meal_deduction=(ct['ct_meal_cost'] if ct['ct_meal_provided'] else 0),
        other_deduction=spec.get('other_deduction', 0),
    )
    ded.update(stageA.get('deduction', {}))
    ded_calc = sum(v for v in ded.values() if v is not None)
    net_calc = gross_calc - ded_calc

    payslip = OrderedDict([
        ('ps_base_pay', pay['base_pay']),
        ('ps_bonus_amount', pay['bonus_amount']),
        ('ps_calculated_amount', stageA.get('calculated_amount', pay['base_pay'])),
        ('ps_calculation_formula', spec['calc_formula']),
        ('ps_calculation_item', spec.get('calc_item', '기본급')),
        ('ps_employee_name', spec.get('ps_name', spec['name'])),
        ('ps_employer_name', spec.get('ps_employer', spec['employer'])),
        ('ps_employment_insurance', ded['employment_insurance']),
        ('ps_gross_pay', gross_calc + stageB.get('gross_print_delta', 0)),
        ('ps_health_insurance', ded['health_insurance']),
        ('ps_holiday_work_pay', pay['holiday_work_pay']),
        ('ps_housing_deduction', ded['housing_deduction']),
        ('ps_income_tax', ded['income_tax']),
        ('ps_local_income_tax', ded['local_income_tax']),
        ('ps_long_term_care_insurance', ded['long_term_care_insurance']),
        ('ps_meal_deduction', ded['meal_deduction']),
        ('ps_national_pension', ded['national_pension']),
        ('ps_net_pay', net_calc + stageB.get('net_print_delta', 0)),
        ('ps_night_work_pay', pay['night_work_pay']),
        ('ps_ordinary_hourly_wage', applied_hourly),
        ('ps_other_allowance', pay['other_allowance']),
        ('ps_other_deduction', ded['other_deduction']),
        ('ps_overtime_pay', pay['overtime_pay']),
        ('ps_paid_holiday_hours', ph['holiday']),
        ('ps_paid_night_hours', ph['night']),
        ('ps_paid_overtime_hours', ph['overtime']),
        ('ps_paid_regular_hours', ph['regular']),
        ('ps_paid_work_days', ph['workdays']),
        ('ps_pay_lines', None),
        ('ps_pay_period_end', period_end),
        ('ps_pay_period_start', period_start),
        ('ps_payment_date', spec['payment_date']),
        ('ps_total_deduction', ded_calc + stageB.get('deduction_print_delta', 0)),
        ('ps_wage_type', stageA.get('ps_wage_type', ct['ct_wage_type'])),
        ('ps_weekly_allowance', pay['weekly_allowance']),
        ('ps_weekly_holiday_hours', ph['weekly']),
    ])
    lines_pay = [
        ('기본급', pay['base_pay'], 'ps_base_pay'),
        ('주휴수당', pay['weekly_allowance'], 'ps_weekly_allowance'),
        ('연장근로수당', pay['overtime_pay'], 'ps_overtime_pay'),
        ('야간근로수당', pay['night_work_pay'], 'ps_night_work_pay'),
        ('휴일근로수당', pay['holiday_work_pay'], 'ps_holiday_work_pay'),
        ('상여금', pay['bonus_amount'], 'ps_bonus_amount'),
        ('기타수당', pay['other_allowance'], 'ps_other_allowance'),
    ]
    for nm, amt in spec.get('unmatched_items', []):
        lines_pay.append((nm, amt, None))
    payslip['ps_pay_lines'] = [OrderedDict([('item_name', a), ('amount', b), ('mapped_to', c)])
                               for a, b, c in lines_pay]

    # ---- 입금내역서 ----
    # 금액을 실수령액 기준으로 해석 (net_delta / net_ratio / net_rest)
    resolved, used = [], 0
    for t in spec['transactions']:
        if 'amount' in t:
            amt = t['amount']
        elif 'net_ratio' in t:
            amt = round(net_calc * t['net_ratio'] / 10) * 10
        elif 'net_rest' in t:
            amt = net_calc + t.get('net_delta', 0) - used
        else:
            amt = net_calc + t.get('net_delta', 0)
        if t.get('salary'):
            used += amt
        resolved.append(amt)

    txs = []
    for t, amt in zip(spec['transactions'], resolved):
        txs.append(OrderedDict([
            ('bk_deposit_amount', amt),
            ('bk_transaction_content', t.get('content', '타행이체')),
            ('bk_transaction_datetime', t['datetime']),
            ('bk_transaction_record', t['record']),
            ('bk_transfer_memo', t.get('memo')),
        ]))
    salary_flags = [bool(t.get('salary')) for t in spec['transactions']]
    bank = OrderedDict([
        ('bk_account_holder', spec.get('account_holder', spec['name'])),
        ('bk_inquiry_end_date', spec['inquiry'][1]),
        ('bk_inquiry_start_date', spec['inquiry'][0]),
        ('transactions', txs),
    ])

    contract = OrderedDict(sorted(ct.items()))
    documents = OrderedDict([('contract', contract), ('timesheet', timesheet),
                             ('payslip', payslip), ('bank_statement', bank)])

    ctx = dict(spec=spec, ct=ct, ts=timesheet, ps=payslip, bk=bank, daily=daily,
               contract_hourly=contract_hourly, contract_daily_hours=contract_daily_hours,
               ct_break_total_minutes=ct_break_total_minutes,
               ts_period_actual=ts_period_actual, ts_overtime=ts_overtime,
               ts_holiday=ts_holiday, ts_night=ts_night, ts_workdays=ts_workdays,
               gross_calc=gross_calc, ded_calc=ded_calc, net_calc=net_calc,
               salary_flags=salary_flags, ded=ded)
    return documents, ctx


# ---------------- 규칙 엔진 ----------------
def run_rules(documents, ctx):
    spec, ct, ps, bk = ctx['spec'], ctx['ct'], ctx['ps'], ctx['bk']
    ts = ctx['ts']
    period_start, period_end = spec['period']
    derived, rr = OrderedDict(), OrderedDict()

    def put(rule, result, reason):
        rr[rule] = OrderedDict([(rule.lower() + '_result', result),
                                (rule.lower() + '_reason', reason)])

    derived['common'] = {'ct_break_total_minutes': ctx['ct_break_total_minutes']}

    # ===== R00 =====
    ct_n, ts_n = norm(ct['ct_employee_name']), norm(ts['ts_employee_name'])
    ps_n, bk_n = norm(ps['ps_employee_name']), norm(bk['bk_account_holder'])
    name_match = (ct_n == ts_n == ps_n)
    holder_match = (bk_n == ct_n)
    employer_match = (norm(ct['ct_employer_name']) == norm(ps['ps_employer_name']))
    if ct['ct_workplace_change_selected']:
        c_start, c_end = ct['ct_workplace_change_start_date'], ct['ct_workplace_change_end_date']
    else:
        c_start, c_end = ct['ct_new_or_reentry_start_date'], ct['ct_new_or_reentry_end_date']
    contract_period_match = D(c_start) <= D(period_start) and D(period_end) <= D(c_end)
    work_period_match = all(D(period_start) <= D(l['ts_work_date']) <= D(period_end)
                            for l in ts['lines']) if ts['lines'] else None
    worker_match = bool(name_match and holder_match and employer_match)
    period_match = bool(contract_period_match if work_period_match is None
                        else (contract_period_match and work_period_match))
    derived['R00'] = {
        'bk_account_holder_norm': bk_n, 'cmp_account_holder_match': holder_match,
        'cmp_contract_period_match': contract_period_match,
        'cmp_employee_name_match': name_match, 'cmp_employer_match': employer_match,
        'cmp_period_match': period_match, 'cmp_work_period_match': work_period_match,
        'cmp_worker_match': worker_match, 'ct_employee_name_norm': ct_n,
        'ct_selected_contract_end': c_end, 'ct_selected_contract_start': c_start,
        'ps_employee_name_norm': ps_n, 'sys_case_id': spec['id'], 'ts_employee_name_norm': ts_n,
    }
    if worker_match and period_match:
        put('R00', 'PASS', '근로자명·예금주명·사업장명이 일치하고 급여 산정기간과 근무일이 계약기간에 포함됨')
    else:
        bad = []
        if not name_match:
            bad.append('근로자명 불일치')
        if not holder_match:
            bad.append(f"예금주명 불일치(계좌 {bk['bk_account_holder']})")
        if not employer_match:
            bad.append('사업장명 불일치')
        if not contract_period_match:
            bad.append(f'급여 산정기간이 계약기간({c_start}~{c_end}) 밖')
        if work_period_match is False:
            bad.append('산정기간 밖 근무일 존재')
        put('R00', 'REVIEW', ', '.join(bad) + ' — 동일 근로자·동일 사례 여부 사람 확인 필요')

    # ===== R01 =====
    contract_hourly = ctx['contract_hourly']
    payslip_hourly = ps['ps_ordinary_hourly_wage']
    if payslip_hourly is None and ps['ps_paid_regular_hours']:
        payslip_hourly = round(ps['ps_base_pay'] / ps['ps_paid_regular_hours'], 2)
    wage_type_match = (ct['ct_wage_type'] == ps['ps_wage_type']) if (ct['ct_wage_type'] and ps['ps_wage_type']) else None
    gap = None if (payslip_hourly is None or contract_hourly is None) else round(payslip_hourly - contract_hourly, 2)
    import calendar as _cal
    full_month = (D(period_start).day == 1 and D(period_end).day ==
                  _cal.monthrange(D(period_end).year, D(period_end).month)[1] and
                  D(period_start).month == D(period_end).month)
    partial = bool(ct['ct_wage_type'] == 'monthly' and not full_month)
    derived['R01'] = {
        'calc_contract_daily_hours': ctx['contract_daily_hours'],
        'calc_contract_hourly_wage': contract_hourly, 'calc_payslip_hourly_wage': payslip_hourly,
        'cmp_hourly_wage_gap': gap, 'cmp_wage_type_match': wage_type_match,
        'cond_partial_period': partial, 'param_wage_tolerance': PARAM_WAGE_TOL,
    }
    if contract_hourly is None or payslip_hourly is None:
        put('R01', 'NOT_CHECKABLE', '계약 임금액 또는 명세서 적용시급을 확인할 수 없어 시급 비교 불가')
    elif wage_type_match is False:
        put('R01', 'MISMATCH', f"임금형태 불일치 — 계약 {ct['ct_wage_type']}, 명세서 {ps['ps_wage_type']}")
    elif abs(gap) > PARAM_WAGE_TOL:
        put('R01', 'MISMATCH', f"계약 환산시급 {won(contract_hourly)}원, 명세서 적용시급 {won(payslip_hourly)}원 — 차이 {gap:+,.2f}원 (허용 {PARAM_WAGE_TOL}원)")
    elif partial:
        put('R01', 'REVIEW', f"월급제 일부기간 정산({period_start}~{period_end}) — 월 소정근로시간 기준 환산값 확인 필요")
    else:
        put('R01', 'PASS', '임금형태 동일, 계약 환산시급과 명세서 적용시급 차이가 허용범위 이내')

    # ===== R02 =====
    sched_days = scheduled_work_days(spec)
    cal_days = (D(period_end) - D(period_start)).days + 1
    coverage = round(ctx['ts_workdays'] / cal_days, 3)
    sched_cov = ctx['ts_workdays'] / sched_days if sched_days else 0
    tol_h = max(0.5, min(round(ctx['ts_workdays'] / 12, 2), round(ctx['ts_period_actual'] * 0.03, 2)))
    tol_h = round(tol_h, 2)
    ps_equiv = r2((ps['ps_paid_regular_hours'] or 0) + (ps['ps_paid_overtime_hours'] or 0)
                  + (ps['ps_paid_holiday_hours'] or 0))
    gap_h = r2(ctx['ts_period_actual'] - ps_equiv)
    gap_ot = r2(ctx['ts_overtime'] - (ps['ps_paid_overtime_hours'] or 0))
    tol_ot = max(0.5, round(sum(1 for x in ctx['daily'] if x > ctx['contract_daily_hours']) / 12, 2))
    brk_source = spec.get('break_source', 'input')
    derived['R02'] = {
        'cmp_actual_hours_gap': gap_h, 'cmp_overtime_hours_gap': gap_ot,
        'cmp_tolerance_hours': tol_h, 'cmp_work_days_gap': ctx['ts_workdays'] - (ps['ps_paid_work_days'] or 0),
        'ps_actual_hours_equiv': ps_equiv, 'ts_break_source': brk_source,
        'ts_daily_actual_hours': ctx['daily'], 'ts_period_actual_hours': ctx['ts_period_actual'],
        'ts_period_coverage': coverage, 'ts_period_holiday_hours': ctx['ts_holiday'],
        'ts_period_night_hours': ctx['ts_night'], 'ts_period_overtime_hours': ctx['ts_overtime'],
        'ts_period_work_days': ctx['ts_workdays'],
    }
    if not ts['ts_record_available'] or not ts['lines']:
        put('R02', 'NOT_EVALUABLE', '근무기록부가 제출되지 않아 실근로시간을 산출할 수 없음')
    elif sched_cov < COVERAGE_THRESHOLD:
        put('R02', 'NOT_EVALUABLE', f"근무기록 커버리지 {sched_cov*100:.0f}% (소정근로일 {sched_days}일 중 {ctx['ts_workdays']}일, 기간 커버리지 {coverage}) — 임계값 90% 미달")
    elif abs(gap_h) > tol_h:
        put('R02', 'MISMATCH', f"실근로시간 {hr(ctx['ts_period_actual'])}시간, 명세서 환산 {hr(ps_equiv)}시간 — 차이 {gap_h:+g}시간 (허용 {tol_h}시간)")
    elif abs(gap_ot) > tol_ot:
        put('R02', 'MISMATCH', f"연장시간 차이 {gap_ot:+g}시간 (근무기록 {hr(ctx['ts_overtime'])}시간, 명세서 {hr(ps['ps_paid_overtime_hours'])}시간, 허용 {tol_ot}시간)")
    elif brk_source == 'contract':
        put('R02', 'REVIEW', '근무기록에 휴게시간이 없어 계약 휴게시간으로 대체 계산 — 실제 휴게 확인 필요')
    else:
        put('R02', 'PASS', f"주휴시간·야간시간 분리 후 실근로시간 차이 {gap_h:+g}시간, 연장시간 차이 {gap_ot:+g}시간")

    # ===== R03 =====
    exp_ot = round((ct['ct_overtime_hourly_pay'] or 0) * (ps['ps_paid_overtime_hours'] or 0))
    bonus_due = bool(spec.get('bonus_due'))
    tol_won = round(10 + 3 * ctx['ts_overtime'])
    gap_bonus = (ps['ps_bonus_amount'] or 0) - (ct['ct_bonus_amount'] or 0) if bonus_due else 0
    gap_extra = (ps['ps_other_allowance'] or 0) - (ct['ct_extra_pay_amount'] or 0)
    gap_ot_pay = (ps['ps_overtime_pay'] or 0) - exp_ot
    unmatched = [nm for nm, _ in spec.get('unmatched_items', [])]
    evidence = 'timesheet' if ts['ts_record_available'] and ts['lines'] else (
        'payslip' if ps['ps_paid_overtime_hours'] is not None else 'none')
    derived['R03'] = {
        'calc_expected_overtime_pay': exp_ot, 'cmp_bonus_gap': gap_bonus,
        'cmp_extra_pay_gap': gap_extra, 'cmp_overtime_pay_gap': gap_ot_pay,
        'cmp_tolerance_won': tol_won, 'cmp_unmatched_pay_items': unmatched,
        'cond_allowance_type': OrderedDict([('bonus_amount', 'fixed'), ('other_allowance', 'fixed'),
                                            ('overtime_pay', 'rate'), ('night_work_pay', 'rate'),
                                            ('holiday_work_pay', 'rate')]),
        'cond_bonus_due': bonus_due, 'cond_evidence_source': evidence,
        'cond_holiday_occurred': (ps['ps_paid_holiday_hours'] or 0) > 0,
        'cond_night_occurred': (ps['ps_paid_night_hours'] or 0) > 0,
        'cond_overtime_occurred': (ps['ps_paid_overtime_hours'] or 0) > 0,
        'cond_weekly_allowance_due': bool(spec.get('weekly_allowance_due', True)),
    }
    if evidence == 'none':
        put('R03', 'NOT_EVALUABLE', '연장·야간·휴일 근로 발생 여부를 확인할 근거 문서가 없어 수당 검증 불가')
    else:
        msg = []
        if abs(gap_bonus) > tol_won:
            msg.append(f"상여금 차이 {gap_bonus:+,}원 (계약 {won(ct['ct_bonus_amount'])}원, 명세서 {won(ps['ps_bonus_amount'])}원)")
        if abs(gap_extra) > tol_won:
            msg.append(f"수당 차이 {gap_extra:+,}원 (계약 {won(ct['ct_extra_pay_amount'])}원, 명세서 {won(ps['ps_other_allowance'])}원)")
        if abs(gap_ot_pay) > tol_won:
            msg.append(f"연장수당 차이 {gap_ot_pay:+,}원 (예상 {won(exp_ot)}원, 명세서 {won(ps['ps_overtime_pay'])}원)")
        if msg:
            put('R03', 'MISMATCH', ', '.join(msg) + f" — 허용 {won(tol_won)}원")
        elif unmatched:
            put('R03', 'REVIEW', f"계약 근거가 없는 지급항목 {len(unmatched)}건({', '.join(unmatched)}) — 지급 근거 확인 필요")
        else:
            put('R03', 'PASS', '정액형·단가형 차이가 모두 허용범위 이내, 미매칭 지급항목 없음')

    # ===== R04 =====
    exp_house = ct['ct_housing_cost'] if ct['ct_housing_provided'] else 0
    exp_meal = ct['ct_meal_cost'] if ct['ct_meal_provided'] else 0
    gap_house = (ps['ps_housing_deduction'] or 0) - (exp_house or 0)
    gap_meal = (ps['ps_meal_deduction'] or 0) - (exp_meal or 0)
    derived['R04'] = {
        'calc_expected_housing_deduction': exp_house, 'calc_expected_meal_deduction': exp_meal,
        'cmp_housing_deduction_gap': gap_house, 'cmp_meal_deduction_gap': gap_meal,
    }
    if ct['ct_housing_provided'] is None or ct['ct_meal_provided'] is None:
        put('R04', 'NOT_CHECKABLE', '계약서의 숙식 제공 여부를 확인할 수 없어 공제 적정성 판단 불가')
    else:
        m = []
        if gap_house != 0:
            m.append(f"숙박비 {won(ps['ps_housing_deduction'])}원 공제 (계약 {won(exp_house)}원, 차이 {gap_house:+,}원)")
        if gap_meal != 0:
            m.append(f"식비 {won(ps['ps_meal_deduction'])}원 공제 (계약 {won(exp_meal)}원, 차이 {gap_meal:+,}원)")
        put('R04', 'MISMATCH' if m else 'PASS',
            ', '.join(m) if m else '숙박비·식비 공제액이 계약 부담액과 일치')

    # ===== R05 =====
    pay_items = ['ps_base_pay', 'ps_weekly_allowance', 'ps_overtime_pay', 'ps_night_work_pay',
                 'ps_holiday_work_pay', 'ps_bonus_amount', 'ps_other_allowance']
    calc_gross = sum((ps[k] or 0) for k in pay_items)
    gap_gross = calc_gross - (ps['ps_gross_pay'] or 0)
    derived['R05'] = {'calc_gross_pay': calc_gross, 'cmp_gross_pay_gap': gap_gross,
                      'param_gross_tolerance': PARAM_GROSS_TOL}
    if abs(gap_gross) > PARAM_GROSS_TOL:
        put('R05', 'MISMATCH', f"지급항목 {len(pay_items)}종 합계 {won(calc_gross)}원, 명세서 총지급액 {won(ps['ps_gross_pay'])}원 — 차이 {gap_gross:+,}원")
    else:
        put('R05', 'PASS', f"지급항목 {len(pay_items)}종 합계와 총지급액 차이 {gap_gross:+,}원")

    # ===== R06 =====
    ded_items = ['ps_income_tax', 'ps_local_income_tax', 'ps_national_pension', 'ps_health_insurance',
                 'ps_employment_insurance', 'ps_long_term_care_insurance', 'ps_housing_deduction',
                 'ps_meal_deduction', 'ps_other_deduction']
    complete = all(ps[k] is not None for k in ded_items)
    calc_ded = sum((ps[k] or 0) for k in ded_items)
    gap_ded = (ps['ps_total_deduction'] or 0) - calc_ded
    derived['R06'] = {'calc_total_deduction': calc_ded, 'cmp_total_deduction_gap': gap_ded,
                      'cond_deduction_components_complete': complete}
    if not complete:
        miss = [k for k in ded_items if ps[k] is None]
        put('R06', 'NOT_CHECKABLE', f"공제항목 추출 실패({', '.join(miss)}) — OCR 실패를 0원으로 계산할 수 없어 검산 불가")
    elif abs(gap_ded) > PARAM_GROSS_TOL:
        put('R06', 'MISMATCH', f"세부 공제항목 합계 {won(calc_ded)}원, 명세서 총공제액 {won(ps['ps_total_deduction'])}원 — 차이 {gap_ded:+,}원")
    else:
        put('R06', 'PASS', f"공제항목 {len(ded_items)}종 합계와 총공제액 차이 {gap_ded:+,}원")

    # ===== R07 =====
    calc_net = calc_gross - calc_ded
    gap_net = (ps['ps_net_pay'] or 0) - calc_net
    derived['R07'] = {'calc_net_pay': calc_net, 'cmp_net_pay_gap': gap_net,
                      'cond_net_pay_nonpositive': calc_net <= 0}
    if calc_net <= 0:
        put('R07', 'REVIEW_HIGH', f"재계산 실수령액 {won(calc_net)}원으로 0 이하 — 공제 과다 여부 즉시 확인 필요")
    elif abs(gap_net) > PARAM_GROSS_TOL:
        put('R07', 'MISMATCH', f"지급 {won(calc_gross)} - 공제 {won(calc_ded)} = {won(calc_net)}원, 명세서 실수령액 {won(ps['ps_net_pay'])}원 — 차이 {gap_net:+,}원")
    else:
        put('R07', 'PASS', '총지급-총공제 재계산 결과가 명세서 실수령액과 일치')

    # ===== R08 =====
    txs = bk['transactions']
    cand = []
    for t in txs:
        c = ((t['bk_deposit_amount'] or 0) >= 300000 and
             (norm(t['bk_transaction_record']) == norm(ct['ct_employer_name']) or
              (t['bk_transaction_content'] in ('급여', '급여이체'))))
        cand.append(bool(c))
    selected = ctx['salary_flags']
    dep_total = sum((t['bk_deposit_amount'] or 0) for t, s in zip(txs, selected) if s)
    dep_cnt = sum(1 for s in selected if s)
    gap_dep = dep_total - calc_net
    derived['R08'] = {'calc_salary_deposit_count': dep_cnt, 'calc_salary_deposit_total': dep_total,
                      'cmp_deposit_gap': gap_dep, 'cond_salary_candidate': cand,
                      'usr_salary_transaction_selected': selected}
    if dep_cnt == 0:
        put('R08', 'NOT_CHECKABLE', '급여로 확정된 입금 거래가 없어 실제 지급액을 확인할 수 없음')
    elif abs(gap_dep) > PARAM_GROSS_TOL:
        put('R08', 'MISMATCH', f"재계산 실수령액 {won(calc_net)}원, 급여 입금 합계 {won(dep_total)}원({dep_cnt}건) — 차이 {gap_dep:+,}원")
    else:
        put('R08', 'PASS', f"사용자 확정 급여 입금 {dep_cnt}건 합계가 재계산 실수령액과 일치")

    # ===== R09 =====
    pe = D(period_end)
    if ct['ct_pay_timing'] == 'next_month':
        y, m = add_month(pe, 1)
    elif ct['ct_pay_timing'] == 'same_month':
        y, m = pe.year, pe.month
    else:
        y, m = add_month(pe, 1)
    sched = clamp_day(y, m, ct['ct_pay_day']).isoformat() if ct['ct_pay_day'] else None
    sched = spec.get('scheduled_override', sched)
    cum, run, done = [], 0, None
    for t, s in sorted(zip(txs, selected), key=lambda x: x[0]['bk_transaction_datetime']):
        if not s:
            continue
        run += t['bk_deposit_amount'] or 0
        d0 = t['bk_transaction_datetime'][:10]
        cum.append(OrderedDict([('date', d0), ('cumulative', run)]))
        if done is None and run >= calc_net:
            done = d0
    gap_days = (D(done) - D(sched)).days if (done and sched) else None
    derived['R09'] = {'calc_actual_payment_completion_date': done,
                      'calc_cumulative_salary_deposit': cum,
                      'calc_scheduled_payment_date': sched,
                      'cmp_payment_date_gap_days': gap_days,
                      'ref_public_holiday': spec.get('ref_public_holiday')}
    if done is None:
        put('R09', 'NOT_CHECKABLE', '급여 입금 누적액이 재계산 실수령액에 도달하지 않아 전액 지급 완료일을 확정할 수 없음')
    elif gap_days > 0:
        put('R09', 'MISMATCH', f"약정 지급일 {sched}, 전액 지급 완료일 {done} — {gap_days}일 지연" +
            (f" (분할 입금 {len(cum)}회)" if len(cum) > 1 else ""))
    else:
        put('R09', 'PASS', f"약정 지급일 {sched} 이전({done})에 누적 입금이 실수령액에 도달")

    # ===== R10 =====
    monthly_hours = spec.get('monthly_actual_hours_override', ctx['ts_period_actual'])
    if monthly_hours is None or not ct['ct_monthly_work_hours']:
        gap_m = rate = None
    else:
        gap_m = r2(monthly_hours - ct['ct_monthly_work_hours'])
        rate = round(gap_m / ct['ct_monthly_work_hours'] * 100, 2)
    over = any(x > (ct['ct_max_daily_work_hours'] or 99) for x in ctx['daily'])
    reason_avail = any(l['ts_work_note'] for l in ts['lines'])
    derived['R10'] = {
        'cmp_contract_actual_hours_gap': gap_m, 'cmp_contract_actual_hours_gap_rate': rate,
        'cond_change_reason_available': reason_avail, 'cond_daily_limit_exceeded': over,
        'cond_worker_confirmed': bool(ts['ts_worker_confirmed']),
        'param_hours_tolerance': PARAM_HOURS_TOL, 'ts_monthly_actual_hours': monthly_hours,
    }
    if not ts['ts_record_available'] or not ts['lines']:
        put('R10', 'NOT_CHECKABLE', '근무기록부가 없어 계약 소정근로시간과 실제 근로시간을 비교할 수 없음')
    elif not ts['ts_worker_confirmed']:
        put('R10', 'REVIEW', f"근무기록에 근로자 확인 서명이 없음 — 계약 {hr(ct['ct_monthly_work_hours'])}시간 대비 실제 {hr(monthly_hours)}시간")
    elif gap_m is None:
        put('R10', 'NOT_CHECKABLE', '계약 월 소정근로시간 또는 월 총근로시간을 확인할 수 없어 비교 불가')
    elif abs(gap_m) > PARAM_HOURS_TOL or over:
        why = []
        if abs(gap_m) > PARAM_HOURS_TOL:
            why.append(f"계약 {hr(ct['ct_monthly_work_hours'])}시간 대비 실제 {hr(monthly_hours)}시간 — 차이 {gap_m:+g}시간 ({rate:+.2f}%)")
        if over:
            mx = max(ctx['daily'])
            why.append(f"1일 상한 {hr(ct['ct_max_daily_work_hours'])}시간 초과일 존재(최대 {hr(mx)}시간)")
        put('R10', 'REVIEW', ', '.join(why) + ('' if reason_avail else ' — 근무기록에 변경사유 기재 없음'))
    else:
        put('R10', 'PASS', f"계약 월 소정근로시간 대비 차이 {gap_m:+g}시간, 일일 변경 상한 이내")

    # ===== R11 =====
    y0, y1 = D(period_start).year, D(period_end).year
    year = y1 if y0 == y1 else None
    ref = MIN_WAGE.get(year) if year else None
    gap_c = round(contract_hourly - ref, 2) if (ref and contract_hourly is not None) else None
    gap_p = round(payslip_hourly - ref, 2) if (ref and payslip_hourly is not None) else None
    below = bool((gap_c is not None and gap_c < 0) or (gap_p is not None and gap_p < 0))
    derived['R11'] = {'calc_applicable_year': year, 'cmp_contract_minimum_wage_gap': gap_c,
                      'cmp_payslip_minimum_wage_gap': gap_p, 'cond_any_below_minimum_wage': below,
                      'ref_minimum_hourly_wage': ref}
    if year is None:
        put('R11', 'REVIEW', f"급여 산정기간이 {y0}년과 {y1}년에 걸쳐 있어 적용 최저임금 연도를 확정할 수 없음 ({MIN_WAGE[y0]:,}원 / {MIN_WAGE[y1]:,}원)")
    elif ref is None:
        put('R11', 'NOT_CHECKABLE', '적용연도 최저시급 기준값이 없어 판단 불가')
    elif below:
        who = []
        if gap_c is not None and gap_c < 0:
            who.append(f"계약 환산시급 {won(contract_hourly)}원")
        if gap_p is not None and gap_p < 0:
            who.append(f"명세서 적용시급 {won(payslip_hourly)}원")
        put('R11', 'REVIEW_HIGH', f"{', '.join(who)}이 {year}년 최저시급 {ref:,}원 미만 — 법 위반 확정이 아닌 우선 확인 대상")
    else:
        put('R11', 'PASS', f"계약·명세서 환산시급 모두 {year}년 최저시급 {ref:,}원 이상")

    order = ['common'] + [f'R{i:02d}' for i in range(12)]
    derived = OrderedDict((k, OrderedDict(sorted(derived[k].items()))) for k in order)
    rule_results = OrderedDict((f'R{i:02d}', rr[f'R{i:02d}']) for i in range(12))
    return derived, rule_results


def make(spec):
    documents, ctx = build_case(spec)
    derived, rule_results = run_rules(documents, ctx)
    return OrderedDict([('documents', documents), ('derived', derived),
                        ('rule_results', rule_results)]), ctx
