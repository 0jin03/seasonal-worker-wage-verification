# -*- coding: utf-8 -*-
"""20세트 합성 케이스 명세 — 각기 다른 외국인 근로자 / 서로 다른 결함 조합"""

MON_FRI = [0, 1, 2, 3, 4]
MON_SAT = [0, 1, 2, 3, 4, 5]
TUE_SUN = [1, 2, 3, 4, 5, 6]


def C(**kw):
    """계약서 기본값 + 개별 지정"""
    d = dict(
        ct_bonus_amount=0, ct_bonus_extra_pay_paid=False, ct_break_hours=1, ct_break_minutes=0,
        ct_employee_name=None, ct_employer_name=None, ct_extra_pay_amount=0,
        ct_holiday_type='weekly_sunday', ct_housing_cost=0, ct_housing_provided=False,
        ct_max_daily_work_hours=10.0, ct_meal_cost=0, ct_meal_provided=False,
        ct_monthly_work_hours=176.0,
        ct_new_or_reentry_end_date=None, ct_new_or_reentry_selected=True,
        ct_new_or_reentry_start_date=None, ct_overtime_hourly_pay=0,
        ct_pay_cycle='monthly', ct_pay_day=10, ct_pay_period_end=None, ct_pay_period_start=None,
        ct_pay_timing='next_month', ct_pay_weekday=None, ct_wage_amount=0, ct_wage_type='hourly',
        ct_weekly_allowance_included=False, ct_work_day_end='FRI', ct_work_day_start='MON',
        ct_work_end_time='17:00', ct_work_start_time='08:00',
        ct_workplace_change_end_date=None, ct_workplace_change_selected=False,
        ct_workplace_change_start_date=None,
    )
    d.update(kw)
    return d


SPECS = []


def S(**kw):
    SPECS.append(kw)


# ══════════════════════════════════════════════════════════════
# 3개 규칙 미통과 — 10세트 (CASE-2026-08-0012 ~ CASE-2026-11-0021)
# ══════════════════════════════════════════════════════════════

# 0012 캄보디아 / 월급제 / 숙소 제공 — R00(예금주), R04(숙박비 과다), R06(총공제 인쇄)
S(id='CASE-2026-08-0012', name='SITHA VUTHY', employer='한별농원',
  period=('2026-08-01', '2026-08-31'), payment_date='2026-09-10',
  account_holder='CHEA SOPHAL',            # 동료 명의 계좌 → R00
  contract=C(ct_employee_name='SITHA VUTHY', ct_employer_name='한별농원',
             ct_wage_type='monthly', ct_wage_amount=2300000, ct_monthly_work_hours=176.0,
             ct_overtime_hourly_pay=19602, ct_weekly_allowance_included=True,
             ct_housing_provided=True, ct_housing_cost=150000,
             ct_meal_provided=True, ct_meal_cost=90000,
             ct_new_or_reentry_start_date='2026-04-15', ct_new_or_reentry_end_date='2026-10-31',
             ct_pay_period_start='2026-08-01', ct_pay_period_end='2026-08-31', ct_pay_day=10),
  schedule=dict(weekdays=MON_FRI, start='08:00', end='17:00', **{'break': 60}),
  calc_formula='월급 2,300,000원 (월 소정근로시간 176시간)',
  insurance='full',
  stageA=dict(deduction={'housing_deduction': 250000}),      # R04
  stageB=dict(deduction_print_delta=-70000),                 # R06
  transactions=[
      dict(datetime='2026-09-10 09:12:44', record='한별농원', content='급여',
           memo='한별농원 8월급여', salary=True),
  ],
  inquiry=('2026-08-01', '2026-09-30'))

# 0013 베트남 / 시급제 / 최저임금 미달 — R01, R05, R11
S(id='CASE-2026-08-0013', name='PRUM SAMBATH', employer='새터농장',
  period=('2026-08-01', '2026-08-31'), payment_date='2026-09-05',
  contract=C(ct_employee_name='PRUM SAMBATH', ct_employer_name='새터농장',
             ct_wage_type='hourly', ct_wage_amount=10200, ct_monthly_work_hours=168.0,
             ct_overtime_hourly_pay=15300, ct_max_daily_work_hours=10.0,
             ct_new_or_reentry_start_date='2026-05-01', ct_new_or_reentry_end_date='2026-10-31',
             ct_pay_period_start='2026-08-01', ct_pay_period_end='2026-08-31',
             ct_pay_day=5),
  schedule=dict(weekdays=MON_FRI, start='08:00', end='17:00', **{'break': 60}),
  weekly_holiday_hours=32.0,
  calc_formula='시급 10,000원 × 기본근로 168시간',
  insurance='employment_only',
  stageA=dict(applied_hourly=10000),                          # R01 + R11
  stageB=dict(gross_print_delta=45000),                       # R05
  transactions=[
      dict(datetime='2026-09-05 10:02:11', record='새터농장', content='급여',
           memo='8월분 급여', salary=True),
  ],
  inquiry=('2026-08-01', '2026-09-30'))

# 0014 네팔 / 주6일 / 연장근로 다수 — R02, R03, R10
S(id='CASE-2026-09-0014', name='EM CHANTHOU', employer='청산영농조합법인',
  period=('2026-09-01', '2026-09-30'), payment_date='2026-10-10',
  contract=C(ct_employee_name='EM CHANTHOU', ct_employer_name='청산영농조합법인',
             ct_wage_type='hourly', ct_wage_amount=11500, ct_monthly_work_hours=200.0,
             ct_overtime_hourly_pay=17250, ct_max_daily_work_hours=11.0,
             ct_work_day_end='SAT', ct_holiday_type='weekly_sunday',
             ct_new_or_reentry_start_date='2026-03-20', ct_new_or_reentry_end_date='2026-11-30',
             ct_pay_period_start='2026-09-01', ct_pay_period_end='2026-09-30'),
  schedule=dict(weekdays=MON_SAT, start='07:00', end='16:00', **{'break': 60},
                overrides={d: ('07:00', '18:00', 60, False, '수확 성수기 연장근로')
                           for d in ['2026-09-14', '2026-09-15', '2026-09-16',
                                     '2026-09-17', '2026-09-18', '2026-09-21',
                                     '2026-09-22', '2026-09-23']}),
  weekly_holiday_hours=32.0,
  calc_formula='시급 11,500원 × 기본근로 195시간',
  insurance='full',
  stageA=dict(hours={'regular': 175.0}, overtime_pay=200000),  # R02 + R03
  transactions=[
      dict(datetime='2026-10-09 16:40:03', record='청산영농조합법인', content='급여',
           memo='9월 급여', salary=True),
  ],
  inquiry=('2026-09-01', '2026-10-31'))

# 0015 태국 / 일급제 — R07, R08, R09
S(id='CASE-2026-09-0015', name='KONG SREYNICH', employer='금빛과수원',
  period=('2026-09-01', '2026-09-30'), payment_date='2026-10-05',
  contract=C(ct_employee_name='KONG SREYNICH', ct_employer_name='금빛과수원',
             ct_wage_type='daily', ct_wage_amount=95000, ct_monthly_work_hours=176.0,
             ct_overtime_hourly_pay=17800, ct_break_hours=1, ct_break_minutes=30,
             ct_work_start_time='07:30', ct_work_end_time='17:00',
             ct_meal_provided=True, ct_meal_cost=100000,
             ct_new_or_reentry_start_date='2026-04-01', ct_new_or_reentry_end_date='2026-11-15',
             ct_pay_period_start='2026-09-01', ct_pay_period_end='2026-09-30', ct_pay_day=5),
  schedule=dict(weekdays=MON_FRI, start='07:30', end='17:00', **{'break': 90}),
  weekly_holiday_hours=32.0,
  calc_formula='일급 95,000원 × 근무일수 22일',
  calc_item='기본급(일급)',
  insurance='employment_only',
  stageB=dict(net_print_delta=35000),                          # R07
  transactions=[
      dict(datetime='2026-10-16 11:20:55', record='금빛과수원', content='급여',
           memo='9월 급여 일부', net_delta=-180000, salary=True),   # R08 부족 + R09 지연
  ],
  inquiry=('2026-09-01', '2026-10-31'))

# 0016 우즈베키스탄 / 근무기록 일부만 제출 — R02(NOT_EVALUABLE), R04, R10
S(id='CASE-2026-08-0016', name='HOR CHEATHA', employer='너른들농장',
  period=('2026-08-01', '2026-08-31'), payment_date='2026-09-10',
  contract=C(ct_employee_name='HOR CHEATHA', ct_employer_name='너른들농장',
             ct_wage_type='monthly', ct_wage_amount=2400000, ct_monthly_work_hours=176.0,
             ct_overtime_hourly_pay=20454, ct_weekly_allowance_included=True,
             ct_meal_provided=True, ct_meal_cost=110000,
             ct_new_or_reentry_start_date='2026-06-01', ct_new_or_reentry_end_date='2026-12-15',
             ct_pay_period_start='2026-08-01', ct_pay_period_end='2026-08-31'),
  schedule=dict(weekdays=MON_FRI, start='08:00', end='17:00', **{'break': 60},
                only_dates=['2026-08-03', '2026-08-04', '2026-08-05', '2026-08-06',
                            '2026-08-07', '2026-08-10', '2026-08-11']),
  calc_formula='월급 2,400,000원 (월 소정근로시간 176시간)',
  insurance='full',
  stageA=dict(hours={'regular': 176.0}, deduction={'meal_deduction': 220000}),   # R04
  transactions=[
      dict(datetime='2026-09-10 09:44:02', record='너른들농장', content='급여',
           memo='8월 급여', salary=True),
  ],
  inquiry=('2026-08-01', '2026-09-30'))

# 0017 필리핀 / 야간 선별작업 — R03(미매칭), R06(OCR 실패), R09(분할 지연)
S(id='CASE-2026-09-0017', name='SAM SOPHORN', employer='참빛농산',
  period=('2026-09-01', '2026-09-30'), payment_date='2026-10-10',
  contract=C(ct_employee_name='SAM SOPHORN', ct_employer_name='참빛농산',
             ct_wage_type='hourly', ct_wage_amount=12000, ct_monthly_work_hours=176.0,
             ct_overtime_hourly_pay=18000, ct_work_start_time='20:00', ct_work_end_time='05:00',
             ct_holiday_type='weekly_sunday_and_agreed_holidays',
             ct_housing_provided=True, ct_housing_cost=130000,
             ct_new_or_reentry_start_date='2026-07-01', ct_new_or_reentry_end_date='2026-12-31',
             ct_pay_period_start='2026-09-01', ct_pay_period_end='2026-09-30'),
  schedule=dict(weekdays=MON_FRI, start='20:00', end='05:00', **{'break': 60}),
  weekly_holiday_hours=32.0,
  calc_formula='시급 12,000원 × 기본근로 176시간 (야간 선별작업)',
  insurance='full',
  unmatched_items=[('작업장려금', 150000)],                    # R03 REVIEW
  stageA=dict(deduction={'other_deduction': None}),            # R06 NOT_CHECKABLE
  transactions=[
      dict(datetime='2026-10-10 09:30:12', record='참빛농산', content='급여',
           memo='9월 급여 1차', net_ratio=0.55, salary=True),
      dict(datetime='2026-10-27 18:05:31', record='참빛농산', content='급여',
           memo='9월 급여 잔액', net_rest=True, salary=True),   # R09 지연
  ],
  inquiry=('2026-09-01', '2026-11-15'))

# 0018 몽골 / 근무처 변경 계약 / 월중 정산 — R00, R01(REVIEW), R08
S(id='CASE-2026-10-0018', name='NEANG RAKSMEY', employer='소백산농원',
  period=('2026-10-01', '2026-10-20'), payment_date='2026-11-10',
  contract=C(ct_employee_name='NEANG RAKSMEY', ct_employer_name='소백산농원',
             ct_wage_type='monthly', ct_wage_amount=2250000, ct_monthly_work_hours=176.0,
             ct_overtime_hourly_pay=19176, ct_weekly_allowance_included=True,
             ct_new_or_reentry_selected=False, ct_new_or_reentry_start_date=None,
             ct_new_or_reentry_end_date=None,
             ct_workplace_change_selected=True,
             ct_workplace_change_start_date='2026-10-05',   # 산정기간 시작보다 늦음 → R00
             ct_workplace_change_end_date='2026-12-31',
             ct_pay_period_start='2026-10-01', ct_pay_period_end='2026-10-20'),
  schedule=dict(weekdays=MON_FRI, start='08:00', end='17:00', **{'break': 60}),
  calc_formula='월급 2,250,000원 × 근무일수 14일 / 소정근로일 22일 (일할계산)',
  insurance='full',
  monthly_actual_hours_override=176.0,   # 10월 전체 근로시간 (산정기간 10/01~10/20과 구분)
  stageA=dict(base_pay=1431820),
  transactions=[
      dict(datetime='2026-11-10 13:15:07', record='소백산농원', content='급여',
           memo='10월 정산분', net_delta=210000, salary=True),   # R08 과다 입금
  ],
  inquiry=('2026-10-01', '2026-11-30'))

# 0019 미얀마 / 휴게시간 미기재 — R02(REVIEW), R05, R10(일일상한 초과)
S(id='CASE-2026-10-0019', name='CHHUN VIREAK', employer='물레방아농장',
  period=('2026-10-01', '2026-10-31'), payment_date='2026-11-10',
  contract=C(ct_employee_name='CHHUN VIREAK', ct_employer_name='물레방아농장',
             ct_wage_type='hourly', ct_wage_amount=11000, ct_monthly_work_hours=184.0,
             ct_overtime_hourly_pay=16500, ct_max_daily_work_hours=9.0,
             ct_housing_provided=True, ct_housing_cost=100000,
             ct_new_or_reentry_start_date='2026-05-10', ct_new_or_reentry_end_date='2026-11-30',
             ct_pay_period_start='2026-10-01', ct_pay_period_end='2026-10-31'),
  schedule=dict(weekdays=MON_FRI, start='08:00', end='17:00', **{'break': 60},
                overrides={d: ('06:30', '17:30', 60, False, '서리 대비 조기 수확')
                           for d in ['2026-10-19', '2026-10-20', '2026-10-21']}),
  weekly_holiday_hours=32.0,
  break_source='contract',                                     # R02 REVIEW
  calc_formula='시급 11,000원 × 기본근로 184시간',
  insurance='full',
  stageB=dict(gross_print_delta=-38000),                       # R05
  transactions=[
      dict(datetime='2026-11-10 08:55:19', record='물레방아농장', content='급여',
           memo='10월 급여', salary=True),
  ],
  inquiry=('2026-10-01', '2026-11-30'))

# 0020 라오스 / 주급제 / 상여 미지급 — R03, R08, R09
S(id='CASE-2026-11-0020', name='TAN SOKUNTHEA', employer='다산딸기농원',
  period=('2026-11-01', '2026-11-30'), payment_date='2026-12-04',
  contract=C(ct_employee_name='TAN SOKUNTHEA', ct_employer_name='다산딸기농원',
             ct_wage_type='hourly', ct_wage_amount=11200, ct_monthly_work_hours=176.0,
             ct_overtime_hourly_pay=16800, ct_pay_cycle='weekly', ct_pay_timing='same_month',
             ct_pay_day=None, ct_pay_weekday='FRI',
             ct_bonus_extra_pay_paid=True, ct_bonus_amount=300000,
             ct_extra_pay_amount=50000,
             ct_new_or_reentry_start_date='2026-06-15', ct_new_or_reentry_end_date='2026-12-31',
             ct_pay_period_start='2026-11-01', ct_pay_period_end='2026-11-30'),
  schedule=dict(weekdays=MON_FRI, start='08:30', end='17:30', **{'break': 60}),
  weekly_holiday_hours=32.0,
  bonus_due=True,
  scheduled_override='2026-12-04',
  calc_formula='시급 11,200원 × 기본근로 168시간 (주급 지급, 월 합산 명세)',
  insurance='full',
  stageA=dict(bonus_amount=0),                                 # R03 상여 미지급
  transactions=[
      dict(datetime='2026-12-04 17:22:41', record='다산딸기농원', content='급여',
           memo='11월 주급 합산', net_delta=-95000, salary=True),
      dict(datetime='2026-12-11 17:31:08', record='다산딸기농원', content='급여',
           memo='11월 잔액', amount=35000, salary=True),        # R08 부족 + R09 지연
  ],
  inquiry=('2026-11-01', '2026-12-31'))

# 0021 중국 / 명세서 이름 오기 / 서명 누락 — R00, R05, R10
S(id='CASE-2026-11-0021', name='SRUN CHANLINA', employer='서해뜰영농조합',
  ps_name='SRUN CHANLENA',                                       # R00 이름 불일치
  period=('2026-11-01', '2026-11-30'), payment_date='2026-12-10',
  worker_confirmed=False,                                      # R10 REVIEW
  contract=C(ct_employee_name='SRUN CHANLINA', ct_employer_name='서해뜰영농조합',
             ct_wage_type='monthly', ct_wage_amount=2150000, ct_monthly_work_hours=174.0,
             ct_overtime_hourly_pay=18534, ct_weekly_allowance_included=True,
             ct_housing_provided=True, ct_housing_cost=80000,
             ct_meal_provided=True, ct_meal_cost=80000,
             ct_new_or_reentry_start_date='2026-05-01', ct_new_or_reentry_end_date='2026-12-20',
             ct_pay_period_start='2026-11-01', ct_pay_period_end='2026-11-30'),
  schedule=dict(weekdays=MON_FRI, start='08:00', end='17:00', **{'break': 60}),
  calc_formula='월급 2,150,000원 (월 소정근로시간 174시간)',
  insurance='full',
  stageB=dict(gross_print_delta=52000),                        # R05
  transactions=[
      dict(datetime='2026-12-10 10:10:10', record='서해뜰영농조합', content='급여',
           memo='11월 급여', salary=True),
  ],
  inquiry=('2026-11-01', '2026-12-31'))


# ══════════════════════════════════════════════════════════════
# 4개 규칙 미통과 — 5세트 (0022 ~ 0026)
# ══════════════════════════════════════════════════════════════

# 0022 인도네시아 — R01, R05, R08, R11
S(id='CASE-2026-08-0022', name='VUTH SEREY', employer='초원목장농장',
  period=('2026-08-01', '2026-08-31'), payment_date='2026-09-10',
  contract=C(ct_employee_name='VUTH SEREY', ct_employer_name='초원목장농장',
             ct_wage_type='hourly', ct_wage_amount=10500, ct_monthly_work_hours=176.0,
             ct_overtime_hourly_pay=15750, ct_extra_pay_amount=60000,
             ct_new_or_reentry_start_date='2026-04-20', ct_new_or_reentry_end_date='2026-10-20',
             ct_pay_period_start='2026-08-01', ct_pay_period_end='2026-08-31'),
  schedule=dict(weekdays=MON_FRI, start='08:00', end='17:00', **{'break': 60}),
  weekly_holiday_hours=32.0,
  calc_formula='시급 10,000원 × 기본근로 168시간',
  insurance='full',
  stageA=dict(applied_hourly=10000),                           # R01 + R11
  stageB=dict(gross_print_delta=-72000),                       # R05
  transactions=[
      dict(datetime='2026-09-10 09:00:59', record='초원목장농장', content='급여',
           memo='8월 급여', net_delta=120000, salary=True),     # R08 과다 입금
  ],
  inquiry=('2026-08-01', '2026-09-30'))

# 0023 키르기스스탄 — R02, R03, R04, R06
S(id='CASE-2026-09-0023', name='KAN BUNTHAN', employer='백학농원',
  period=('2026-09-01', '2026-09-30'), payment_date='2026-10-10',
  contract=C(ct_employee_name='KAN BUNTHAN', ct_employer_name='백학농원',
             ct_wage_type='monthly', ct_wage_amount=2500000, ct_monthly_work_hours=208.0,
             ct_overtime_hourly_pay=18029, ct_weekly_allowance_included=True,
             ct_work_day_end='SAT', ct_max_daily_work_hours=10.0,
             ct_housing_provided=True, ct_housing_cost=120000,
             ct_meal_provided=True, ct_meal_cost=100000,
             ct_new_or_reentry_start_date='2026-03-01', ct_new_or_reentry_end_date='2026-11-30',
             ct_pay_period_start='2026-09-01', ct_pay_period_end='2026-09-30'),
  schedule=dict(weekdays=MON_SAT, start='08:00', end='17:00', **{'break': 60},
                overrides={d: ('08:00', '19:00', 60, False, '저장고 입고 작업')
                           for d in ['2026-09-24', '2026-09-25', '2026-09-26']}),
  calc_formula='월급 2,500,000원 (월 소정근로시간 208시간)',
  insurance='full',
  stageA=dict(hours={'regular': 190.0}, overtime_pay=30000,     # R02 + R03
              deduction={'housing_deduction': 200000, 'meal_deduction': 160000}),  # R04
  stageB=dict(deduction_print_delta=45000),                    # R06
  transactions=[
      dict(datetime='2026-10-10 15:02:33', record='백학농원', content='급여',
           memo='9월 급여', salary=True),
  ],
  inquiry=('2026-09-01', '2026-10-31'))

# 0024 베트남 / 임신 단축근로 1일 6시간 — R00, R02, R09, R10
S(id='CASE-2026-09-0024', name='MAO SREYPICH', employer='가온들녘농장',
  period=('2026-09-01', '2026-09-30'), payment_date='2026-10-10',
  account_holder='MAO CHANRA',                                # R00 배우자 계좌
  contract=C(ct_employee_name='MAO SREYPICH', ct_employer_name='가온들녘농장',
             ct_wage_type='hourly', ct_wage_amount=11800, ct_monthly_work_hours=176.0,
             ct_overtime_hourly_pay=17700, ct_max_daily_work_hours=8.0,
             ct_work_start_time='09:00', ct_work_end_time='16:00', ct_break_minutes=0,
             ct_new_or_reentry_start_date='2026-04-01', ct_new_or_reentry_end_date='2026-10-31',
             ct_pay_period_start='2026-09-01', ct_pay_period_end='2026-09-30'),
  schedule=dict(weekdays=MON_FRI, start='09:00', end='16:00', **{'break': 60},
                overrides={'2026-09-16': ('09:00', '18:00', 60, False, '출하 지원 연장근로')}),
  weekly_holiday_hours=30.0,
  calc_formula='시급 11,800원 × 기본근로 132시간 (임신부 단축근로)',
  insurance='full',
  stageA=dict(hours={'overtime': 0.0}),                        # R02 연장시간 불일치
  transactions=[
      dict(datetime='2026-10-19 10:44:12', record='가온들녘농장', content='급여',
           memo='9월 급여', salary=True),                       # R09 지연
  ],
  inquiry=('2026-09-01', '2026-10-31'))

# 0025 방글라데시 / 일급제 — R04, R05, R06, R07
S(id='CASE-2026-10-0025', name='SOEUN CHHAYA', employer='오름농장',
  period=('2026-10-01', '2026-10-31'), payment_date='2026-11-05',
  contract=C(ct_employee_name='SOEUN CHHAYA', ct_employer_name='오름농장',
             ct_wage_type='daily', ct_wage_amount=100000, ct_monthly_work_hours=176.0,
             ct_overtime_hourly_pay=18750, ct_break_hours=1, ct_break_minutes=0,
             ct_work_start_time='08:00', ct_work_end_time='17:00',
             ct_housing_provided=True, ct_housing_cost=150000,
             ct_meal_provided=False, ct_meal_cost=0,
             ct_new_or_reentry_start_date='2026-06-01', ct_new_or_reentry_end_date='2026-11-30',
             ct_pay_period_start='2026-10-01', ct_pay_period_end='2026-10-31', ct_pay_day=5),
  schedule=dict(weekdays=MON_FRI, start='08:00', end='17:00', **{'break': 60}),
  weekly_holiday_hours=32.0,
  calc_formula='일급 100,000원 × 근무일수 22일',
  calc_item='기본급(일급)',
  insurance='employment_only',
  stageA=dict(deduction={'housing_deduction': 150000, 'meal_deduction': 90000}),  # R04 식사 미제공 공제
  stageB=dict(gross_print_delta=60000, deduction_print_delta=-25000,
              net_print_delta=48000),                          # R05, R06, R07
  transactions=[
      dict(datetime='2026-11-05 09:20:00', record='오름농장', content='급여',
           memo='10월 급여', salary=True),
  ],
  inquiry=('2026-10-01', '2026-11-30'))

# 0026 동티모르 / 근무기록부 미제출 — R02, R08, R09, R10
S(id='CASE-2026-10-0026', name='NUON PHIROM', employer='별뜨락농원',
  period=('2026-10-01', '2026-10-31'), payment_date='2026-11-10',
  record_available=False,
  contract=C(ct_employee_name='NUON PHIROM', ct_employer_name='별뜨락농원',
             ct_wage_type='monthly', ct_wage_amount=2300000, ct_monthly_work_hours=176.0,
             ct_overtime_hourly_pay=19602, ct_weekly_allowance_included=True,
             ct_housing_provided=True, ct_housing_cost=100000,
             ct_new_or_reentry_start_date='2026-05-01', ct_new_or_reentry_end_date='2026-12-31',
             ct_pay_period_start='2026-10-01', ct_pay_period_end='2026-10-31'),
  schedule=dict(weekdays=MON_FRI, start='08:00', end='17:00', **{'break': 60}, only_dates=[]),
  calc_formula='월급 2,300,000원 (월 소정근로시간 176시간)',
  insurance='full',
  monthly_actual_hours_override=None,
  stageA=dict(hours={'regular': 176.0, 'workdays': 22}),
  transactions=[
      dict(datetime='2026-11-24 14:03:22', record='별뜨락농원', content='급여',
           memo='10월 급여 일부', net_delta=-330000, salary=True),  # R08 + R09
  ],
  inquiry=('2026-10-01', '2026-12-15'))


# ══════════════════════════════════════════════════════════════
# 5개 규칙 미통과 — 5세트 (0027 ~ 0031)
# ══════════════════════════════════════════════════════════════

# 0027 태국 — R01, R03, R05, R08, R11
S(id='CASE-2026-08-0027', name='KHOEUN MALIS', employer='강마을농산',
  period=('2026-08-01', '2026-08-31'), payment_date='2026-09-10',
  contract=C(ct_employee_name='KHOEUN MALIS', ct_employer_name='강마을농산',
             ct_wage_type='hourly', ct_wage_amount=10400, ct_monthly_work_hours=176.0,
             ct_overtime_hourly_pay=15600, ct_extra_pay_amount=80000,
             ct_bonus_extra_pay_paid=True, ct_bonus_amount=200000,
             ct_new_or_reentry_start_date='2026-04-01', ct_new_or_reentry_end_date='2026-10-31',
             ct_pay_period_start='2026-08-01', ct_pay_period_end='2026-08-31'),
  schedule=dict(weekdays=MON_FRI, start='08:00', end='17:00', **{'break': 60},
                overrides={'2026-08-25': ('08:00', '19:00', 60, False, '태풍 대비 긴급 수확')}),
  weekly_holiday_hours=32.0,
  bonus_due=True,
  calc_formula='시급 10,100원 × 기본근로 168시간',
  insurance='full',
  stageA=dict(applied_hourly=10100, other_allowance=0),        # R01, R11, R03
  stageB=dict(gross_print_delta=90000),                        # R05
  transactions=[
      dict(datetime='2026-09-10 11:11:11', record='강마을농산', content='급여',
           memo='8월 급여', net_delta=150000, salary=True),     # R08 과다 입금
  ],
  inquiry=('2026-08-01', '2026-09-30'))

# 0028 스리랑카 — R02, R04, R06, R07, R09
S(id='CASE-2026-09-0028', name='PRAK SOTHEA', employer='해오름농장',
  period=('2026-09-01', '2026-09-30'), payment_date='2026-10-10',
  contract=C(ct_employee_name='PRAK SOTHEA', ct_employer_name='해오름농장',
             ct_wage_type='monthly', ct_wage_amount=1950000, ct_monthly_work_hours=168.0,
             ct_overtime_hourly_pay=17411, ct_weekly_allowance_included=True,
             ct_housing_provided=True, ct_housing_cost=90000,
             ct_meal_provided=True, ct_meal_cost=120000,
             ct_new_or_reentry_start_date='2026-04-10', ct_new_or_reentry_end_date='2026-11-10',
             ct_pay_period_start='2026-09-01', ct_pay_period_end='2026-09-30'),
  schedule=dict(weekdays=MON_FRI, start='08:00', end='17:00', **{'break': 60},
                absent=['2026-09-08', '2026-09-09'],
                extra={'2026-09-20': ('08:00', '15:00', 30, True, '휴일 특근')}),
  calc_formula='월급 1,950,000원 (월 소정근로시간 168시간)',
  insurance='full',
  stageA=dict(hours={'regular': 168.0},                        # R02
              deduction={'housing_deduction': 190000, 'meal_deduction': 120000}),  # R04
  stageB=dict(deduction_print_delta=-58000, net_print_delta=-40000),   # R06, R07
  transactions=[
      dict(datetime='2026-10-23 16:12:45', record='해오름농장', content='급여',
           memo='9월 급여', salary=True),                       # R09
  ],
  inquiry=('2026-09-01', '2026-11-15'))

# 0029 캄보디아 — R00, R02, R03, R08, R09
S(id='CASE-2026-10-0029', name='CHANTHA SOKUN', employer='솔뫼농원',
  ps_employer='솔뫼영농조합법인',                                # R00 사업장명 불일치
  period=('2026-10-01', '2026-10-31'), payment_date='2026-11-10',
  contract=C(ct_employee_name='CHANTHA SOKUN', ct_employer_name='솔뫼농원',
             ct_wage_type='hourly', ct_wage_amount=11000, ct_monthly_work_hours=176.0,
             ct_overtime_hourly_pay=16500, ct_max_daily_work_hours=10.0,
             ct_extra_pay_amount=40000,
             ct_new_or_reentry_start_date='2026-05-01', ct_new_or_reentry_end_date='2026-11-30',
             ct_pay_period_start='2026-10-01', ct_pay_period_end='2026-10-31'),
  schedule=dict(weekdays=MON_FRI, start='08:00', end='17:00', **{'break': 60},
                overrides={d: ('08:00', '18:00', 60, False, '김장무 출하')
                           for d in ['2026-10-26', '2026-10-27', '2026-10-28', '2026-10-29']}),
  weekly_holiday_hours=32.0,
  calc_formula='시급 11,000원 × 기본근로 176시간',
  insurance='full',
  stageA=dict(hours={'regular': 164.0}, overtime_pay=0),       # R02, R03
  transactions=[
      dict(datetime='2026-11-18 09:05:41', record='솔뫼농원', content='급여',
           memo='10월 급여', net_delta=-260000, salary=True),   # R08, R09
  ],
  inquiry=('2026-10-01', '2026-12-15'))

# 0030 네팔 / 선불금 상환으로 실수령 0 이하 — R04, R07, R08, R09, R10
S(id='CASE-2026-11-0030', name='THOU SAMBO', employer='배꽃마을농장',
  period=('2026-11-01', '2026-11-30'), payment_date='2026-12-10',
  contract=C(ct_employee_name='THOU SAMBO', ct_employer_name='배꽃마을농장',
             ct_wage_type='monthly', ct_wage_amount=2000000, ct_monthly_work_hours=176.0,
             ct_overtime_hourly_pay=17046, ct_weekly_allowance_included=True,
             ct_max_daily_work_hours=9.0,
             ct_housing_provided=True, ct_housing_cost=100000,
             ct_meal_provided=True, ct_meal_cost=100000,
             ct_new_or_reentry_start_date='2026-06-01', ct_new_or_reentry_end_date='2026-12-31',
             ct_pay_period_start='2026-11-01', ct_pay_period_end='2026-11-30'),
  schedule=dict(weekdays=MON_FRI, start='08:00', end='17:00', **{'break': 60},
                overrides={d: ('07:00', '18:00', 60, False, '난방 하우스 야간작업 준비')
                           for d in ['2026-11-09', '2026-11-10']}),
  calc_formula='월급 2,000,000원 (월 소정근로시간 176시간)',
  insurance='full',
  other_deduction=1750000,
  stageA=dict(deduction={'housing_deduction': 300000, 'meal_deduction': 180000}),  # R04
  transactions=[
      dict(datetime='2026-11-14 12:00:00', record='THOU SAMBO', content='타행이체',
           memo='본인 계좌 이체', amount=50000, salary=False),
  ],
  inquiry=('2026-11-01', '2026-12-31'))

# 0031 몽골 / 시설재배 / 연말~연초 걸침 — R02, R05, R06, R09, R11
S(id='CASE-2026-12-0031', name='CHEANG SOPHY', employer='늘봄영농조합',
  period=('2026-12-16', '2027-01-15'), payment_date='2027-01-25',
  contract=C(ct_employee_name='CHEANG SOPHY', ct_employer_name='늘봄영농조합',
             ct_wage_type='hourly', ct_wage_amount=11600, ct_monthly_work_hours=168.0,
             ct_overtime_hourly_pay=17400, ct_max_daily_work_hours=10.0,
             ct_holiday_type='weekly_sunday_and_agreed_holidays',
             ct_housing_provided=True, ct_housing_cost=120000,
             ct_pay_timing='same_month', ct_pay_day=25,
             ct_new_or_reentry_start_date='2026-09-01', ct_new_or_reentry_end_date='2027-02-28',
             ct_pay_period_start='2026-12-16', ct_pay_period_end='2027-01-15'),
  schedule=dict(weekdays=MON_FRI, start='08:30', end='17:30', **{'break': 60},
                absent=['2026-12-25', '2027-01-01']),
  weekly_holiday_hours=32.0,
  scheduled_override='2027-01-25',
  calc_formula='시급 11,600원 × 기본근로 152시간 (시설재배 동절기)',
  insurance='full',
  stageA=dict(hours={'regular': 158.0}),                       # R02
  stageB=dict(gross_print_delta=-47000, deduction_print_delta=33000),  # R05, R06
  transactions=[
      dict(datetime='2027-02-06 10:30:15', record='늘봄영농조합', content='급여',
           memo='12~1월 급여', salary=True),                    # R09
  ],
  inquiry=('2026-12-01', '2027-02-28'))
