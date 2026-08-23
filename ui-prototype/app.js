const screens = [...document.querySelectorAll('[data-screen]')];
const appShell = document.querySelector('.app-shell');
const authOnly = [...document.querySelectorAll('.auth-only')];
const progressButtons = [...document.querySelectorAll('.progress-nav button')];
const stepOrder = ['upload', 'review', 'transactions', 'confirm', 'result'];
const documentLabels = { contract: '근로계약서', timesheet: '근무기록부', payslip: '임금명세서', bank_statement: '입금내역서' };
const fieldLabels = {
  ct_bonus_amount: '상여금', ct_bonus_extra_pay_paid: '상여금·수당 지급 여부', ct_break_hours: '휴게시간(시간)',
  ct_break_minutes: '휴게시간(분)', ct_employee_name: '근로자 이름', ct_employer_name: '사업장명',
  ct_extra_pay_amount: '기타 수당', ct_holiday_type: '주휴일·약정휴일', ct_housing_cost: '숙박비',
  ct_housing_provided: '숙소 제공 여부', ct_max_daily_work_hours: '1일 최대 근로시간', ct_meal_cost: '식비',
  ct_meal_provided: '식사 제공 여부', ct_monthly_work_hours: '월 소정근로시간',
  ct_new_or_reentry_end_date: '신규·재입국 근로 종료일', ct_new_or_reentry_selected: '신규·재입국자 여부',
  ct_new_or_reentry_start_date: '신규·재입국 근로 시작일', ct_overtime_hourly_pay: '연장근로 시급',
  ct_pay_cycle: '임금 지급 주기', ct_pay_day: '임금 지급일', ct_pay_period_end: '임금 산정 종료일',
  ct_pay_period_start: '임금 산정 시작일', ct_pay_timing: '임금 지급 시점', ct_pay_weekday: '임금 지급 요일',
  ct_wage_amount: '계약 임금', ct_wage_type: '임금 형태', ct_weekly_allowance_included: '주휴수당 포함 여부',
  ct_work_day_end: '근무 종료 요일', ct_work_day_start: '근무 시작 요일', ct_work_end_time: '퇴근 시각',
  ct_work_start_time: '출근 시각', ct_workplace_change_end_date: '근무처 변경 종료일',
  ct_workplace_change_selected: '근무처 변경 여부', ct_workplace_change_start_date: '근무처 변경 시작일',
  ts_employee_name: '근로자 이름', ts_record_available: '근무기록 보유 여부', ts_worker_confirmed: '근로자 확인 여부',
  ts_work_date: '근무일', ts_work_start_time: '출근 시각', ts_work_end_time: '퇴근 시각',
  ts_break_minutes: '휴게시간(분)', ts_holiday_worked: '휴일근로 여부', ts_work_note: '비고',
  ps_base_pay: '기본급', ps_bonus_amount: '상여금', ps_calculated_amount: '계산 금액',
  ps_calculation_formula: '임금 계산식', ps_calculation_item: '계산 항목', ps_employee_name: '근로자 이름',
  ps_employer_name: '사업장명', ps_employment_insurance: '고용보험료', ps_gross_pay: '지급액 합계',
  ps_health_insurance: '건강보험료', ps_holiday_work_pay: '휴일근로수당', ps_housing_deduction: '숙박비 공제',
  ps_income_tax: '소득세', ps_local_income_tax: '지방소득세', ps_long_term_care_insurance: '장기요양보험료',
  ps_meal_deduction: '식비 공제', ps_national_pension: '국민연금', ps_net_pay: '실수령액',
  ps_night_work_pay: '야간근로수당', ps_ordinary_hourly_wage: '적용 시급', ps_other_allowance: '기타 수당',
  ps_other_deduction: '기타 공제', ps_overtime_pay: '연장근로수당', ps_paid_holiday_hours: '휴일근로시간',
  ps_paid_night_hours: '야간근로시간', ps_paid_overtime_hours: '연장근로시간', ps_paid_regular_hours: '기본근로시간',
  ps_paid_work_days: '출근일수', ps_pay_period_end: '급여 산정 종료일', ps_pay_period_start: '급여 산정 시작일',
  ps_payment_date: '급여 지급일', ps_total_deduction: '공제액 합계', ps_wage_type: '임금 형태',
  ps_weekly_allowance: '주휴수당', ps_weekly_holiday_hours: '주휴시간', bk_account_holder: '예금주',
  bk_inquiry_end_date: '조회 종료일', bk_inquiry_start_date: '조회 시작일', bk_deposit_amount: '입금액',
  bk_transaction_content: '거래 내용', bk_transaction_datetime: '거래 일시', bk_transaction_record: '거래 기록',
  bk_transfer_memo: '입금 메모', lines: '일별 근무내역', ps_pay_lines: '지급항목 내역',
  transactions: '입금 거래내역', item_name: '지급항목', amount: '금액', mapped_to: '연결된 검증 항목'
};
let signedIn = false;
let canonical = null;
let latestReport = null;

function showScreen(name) {
  screens.forEach(screen => screen.classList.toggle('active', screen.dataset.screen === name));
  const isAuth = name === 'login';
  appShell.classList.toggle('hidden', isAuth);
  authOnly.forEach(item => item.classList.toggle('hidden', isAuth));
  if (!isAuth) signedIn = true;
  const current = stepOrder.indexOf(name);
  progressButtons.forEach(button => {
    const index = stepOrder.indexOf(button.dataset.step);
    button.classList.toggle('current', index === current || (name === 'processing' && index === 0));
    button.classList.toggle('complete', current > index);
  });
  window.scrollTo({ top: 0, behavior: 'smooth' });
}

async function api(path, options = {}) {
  const response = await fetch(path, options);
  const data = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(data.error || `서버 오류 (${response.status})`);
  return data;
}

document.querySelectorAll('[data-go]').forEach(button => button.addEventListener('click', () => {
  if (button.dataset.go === 'login') signedIn = false;
  showScreen(button.dataset.go);
}));
document.querySelectorAll('[data-back]').forEach(button => button.addEventListener('click', () => showScreen(button.dataset.back)));

const authTabs = [...document.querySelectorAll('[data-auth-tab]')];
authTabs.forEach(tab => tab.addEventListener('click', () => {
  authTabs.forEach(item => item.classList.toggle('active', item === tab));
  document.querySelector('#signin-form').classList.toggle('active', tab.dataset.authTab === 'signin');
  document.querySelector('#signup-form').classList.toggle('active', tab.dataset.authTab === 'signup');
}));
function submitAuth(event) {
  event.preventDefault();
  if (!event.currentTarget.checkValidity()) return event.currentTarget.reportValidity();
  signedIn = true;
  showScreen('upload');
}
document.querySelector('#signin-form').addEventListener('submit', submitAuth);
document.querySelector('#signup-form').addEventListener('submit', submitAuth);
document.querySelector('#demo-login').addEventListener('click', () => { signedIn = true; showScreen('upload'); });
document.querySelector('#logout').addEventListener('click', () => { signedIn = false; showScreen('login'); });

const uploadCards = [...document.querySelectorAll('.upload-card')];
const uploadCount = document.querySelector('#upload-count');
const startAnalysis = document.querySelector('#start-analysis');
function updateUploads() {
  const done = uploadCards.filter(card => card.querySelector('input').files.length).length;
  uploadCount.textContent = done;
  startAnalysis.disabled = done !== 4;
}
uploadCards.forEach(card => {
  const input = card.querySelector('input');
  card.querySelector('button').addEventListener('click', event => { event.preventDefault(); input.click(); });
  input.addEventListener('change', () => {
    const file = input.files[0];
    card.classList.toggle('done', Boolean(file));
    card.querySelector('output').textContent = file ? `선택 완료 · ${file.name}` : '업로드 전';
    updateUploads();
  });
});

function scalarEntries(object) {
  return Object.entries(object || {}).filter(([, value]) => !Array.isArray(value) && (value === null || typeof value !== 'object'));
}
function parseInput(value, original) {
  if (value.trim() === '') return null;
  if (typeof original === 'boolean') return value === 'true';
  if (typeof original === 'number') return Number(value.replaceAll(',', ''));
  return value;
}
function fieldLabel(field) { return fieldLabels[field] || field; }
function notApplicableReason(role, field, doc) {
  if (role !== 'contract') return null;
  if (field === 'ct_pay_weekday' && (doc.ct_pay_cycle === '월' || doc.ct_pay_day != null)) return '매월 지급일이 정해져 있어 지급 요일은 사용하지 않습니다.';
  if (['ct_workplace_change_start_date', 'ct_workplace_change_end_date'].includes(field) && doc.ct_workplace_change_selected === false) return '근무처 변경 대상이 아니므로 날짜가 필요하지 않습니다.';
  if (['ct_new_or_reentry_start_date', 'ct_new_or_reentry_end_date'].includes(field) && doc.ct_new_or_reentry_selected === false) return '신규·재입국 대상이 아니므로 날짜가 필요하지 않습니다.';
  if (field === 'ct_housing_cost' && doc.ct_housing_provided === false) return '숙소를 제공하지 않으므로 숙박비가 필요하지 않습니다.';
  if (field === 'ct_meal_cost' && doc.ct_meal_provided === false) return '식사를 제공하지 않으므로 식비가 필요하지 않습니다.';
  return null;
}
function renderReview() {
  const host = document.querySelector('#review-fields');
  host.innerHTML = '';
  Object.entries(canonical.documents).forEach(([role, doc]) => {
    const group = document.createElement('div');
    group.className = 'field-group';
    group.innerHTML = `<h2>${documentLabels[role]}</h2>`;
    scalarEntries(doc).forEach(([field, value]) => {
      const label = document.createElement('label');
      const notApplicable = value === null ? notApplicableReason(role, field, doc) : null;
      if (value === null && !notApplicable) label.classList.add('attention');
      if (notApplicable) label.classList.add('not-applicable-field');
      const safeValue = value === null || value === undefined ? '' : String(value).replaceAll('&', '&amp;').replaceAll('"', '&quot;');
      const control = notApplicable
        ? `<div class="not-applicable-value">해당 없음<small>${notApplicable}</small></div>`
        : typeof value === 'boolean'
        ? `<select data-role="${role}" data-field="${field}"><option value="true" ${value ? 'selected' : ''}>예</option><option value="false" ${!value ? 'selected' : ''}>아니오</option></select>`
        : `<input data-role="${role}" data-field="${field}" value="${safeValue}">`;
      const status = notApplicable ? '입력 불필요' : value === null ? '확인 필요' : 'OCR 인식값';
      label.innerHTML = `<span>${fieldLabel(field)} <b>${status}</b></span>${control}`;
      group.appendChild(label);
    });
    Object.entries(doc).filter(([, value]) => Array.isArray(value)).forEach(([field, rows]) => {
      const details = document.createElement('details');
      details.innerHTML = `<summary>${fieldLabel(field)} (${rows.length}건) 확인</summary>`;
      rows.forEach((row, index) => {
        const rowGroup = document.createElement('div');
        rowGroup.className = 'field-group';
        rowGroup.innerHTML = `<h3>${index + 1}번째 행</h3>`;
        scalarEntries(row).forEach(([name, value]) => {
          const label = document.createElement('label');
          const safeValue = value === null || value === undefined ? '' : String(value).replaceAll('&', '&amp;').replaceAll('"', '&quot;');
          label.innerHTML = `<span>${fieldLabel(name)}</span><input data-role="${role}" data-array="${field}" data-index="${index}" data-field="${name}" value="${safeValue}">`;
          rowGroup.appendChild(label);
        });
        details.appendChild(rowGroup);
      });
      group.appendChild(details);
    });
    host.appendChild(group);
  });
}
function applyReviewEdits() {
  document.querySelectorAll('#review-fields [data-role]').forEach(input => {
    const role = input.dataset.role;
    const field = input.dataset.field;
    if (input.dataset.array) {
      const row = canonical.documents[role][input.dataset.array][Number(input.dataset.index)];
      row[field] = parseInput(input.value, row[field]);
    } else {
      canonical.documents[role][field] = parseInput(input.value, canonical.documents[role][field]);
    }
  });
}

startAnalysis.addEventListener('click', async () => {
  showScreen('processing');
  const form = new FormData();
  uploadCards.forEach(card => form.append(card.dataset.role, card.querySelector('input').files[0]));
  try {
    const data = await api('/api/ocr', { method: 'POST', body: form });
    canonical = data.canonical;
    renderReview();
    showScreen('review');
  } catch (error) {
    alert(`OCR 처리에 실패했습니다.\n${error.message}`);
    showScreen('upload');
  }
});

document.querySelector('#fill-demo').addEventListener('click', async () => {
  try {
    const data = await api('/api/demo');
    canonical = data.canonical;
    renderReview();
    showScreen('review');
  } catch (error) {
    alert(error.message);
  }
});

const reviewConfirmed = document.querySelector('#review-confirmed');
const reviewNext = document.querySelector('#review-next');
reviewConfirmed.addEventListener('change', () => { reviewNext.disabled = !reviewConfirmed.checked; });
reviewNext.addEventListener('click', () => { applyReviewEdits(); renderTransactions(); showScreen('transactions'); });

function money(value) { return Number(value || 0).toLocaleString('ko-KR') + '원'; }
function renderTransactions() {
  const transactions = canonical.documents.bank_statement.transactions || [];
  const host = document.querySelector('#transaction-list');
  host.innerHTML = '<div class="transaction head"><span></span><span>입금일</span><span>보낸 사람·메모</span><span>입금액</span></div>';
  transactions.forEach((item, index) => {
    const row = document.createElement('label');
    row.className = 'transaction';
    row.innerHTML = `<input class="salary-check" type="checkbox" data-index="${index}" value="${item.bk_deposit_amount || 0}"><span>${item.bk_transaction_datetime || '-'}</span><span><b>${item.bk_transaction_record || '-'}</b><small>${item.bk_transfer_memo || item.bk_transaction_content || ''}</small></span><strong>${money(item.bk_deposit_amount)}</strong>`;
    host.appendChild(row);
  });
  host.querySelectorAll('.salary-check').forEach(item => item.addEventListener('change', updateSalaryTotal));
  document.querySelector('#net-pay-total').textContent = money(canonical.documents.payslip.ps_net_pay);
  updateSalaryTotal();
}
function updateSalaryTotal() {
  const selected = [...document.querySelectorAll('.salary-check')].filter(item => item.checked);
  const total = selected.reduce((sum, item) => sum + Number(item.value), 0);
  const netPay = Number(canonical?.documents?.payslip?.ps_net_pay || 0);
  document.querySelector('#selected-total').textContent = money(total);
  const status = document.querySelector('#amount-status');
  status.textContent = selected.length ? (total === netPay ? '금액이 일치합니다' : '금액이 일치하지 않습니다') : '거래를 선택해주세요';
  status.classList.toggle('mismatch', selected.length > 0 && total !== netPay);
  document.querySelector('#transaction-next').disabled = selected.length === 0;
}

const ruleTitles = {
  R00: '문서의 근로자·기간 일치', R01: '계약 임금과 명세서 시급 비교', R02: '근무시간과 지급시간 비교',
  R03: '수당 지급 여부 확인', R04: '숙박비·식비 공제 확인', R05: '총지급액 계산 확인',
  R06: '총공제액 계산 확인', R07: '실수령액 계산 확인', R08: '급여 입금액 확인',
  R09: '급여 지급일 확인', R10: '근무기록 변경·상한 확인', R11: '최저임금 준수 확인'
};
const statusLabels = { PASS: '이상 없음', MISMATCH: '불일치', REVIEW: '확인 필요', REVIEW_HIGH: '중요 확인', NOT_CHECKABLE: '판정 불가' };
const evidenceFields = {
  R00: ['cmp_worker_match', 'cmp_employer_match', 'cmp_period_match'],
  R01: ['calc_contract_hourly_wage', 'calc_payslip_hourly_wage', 'cmp_hourly_wage_gap', 'param_wage_tolerance'],
  R02: ['ts_period_actual_hours', 'ps_actual_hours_equiv', 'cmp_actual_hours_gap', 'ts_period_coverage'],
  R03: ['cmp_bonus_gap', 'cmp_extra_pay_gap', 'cmp_overtime_pay_gap', 'cmp_unmatched_pay_items'],
  R04: ['calc_expected_housing_deduction', 'cmp_housing_deduction_gap', 'calc_expected_meal_deduction', 'cmp_meal_deduction_gap'],
  R05: ['calc_gross_pay', 'cmp_gross_pay_gap', 'param_gross_tolerance'],
  R06: ['calc_total_deduction', 'cmp_total_deduction_gap', 'cmp_tolerance_deduction_won'],
  R07: ['calc_net_pay', 'cmp_net_pay_gap', 'cmp_tolerance_net_pay_won'],
  R08: ['calc_salary_deposit_count', 'calc_salary_deposit_total', 'cmp_deposit_gap'],
  R09: ['calc_scheduled_payment_date', 'calc_actual_payment_completion_date', 'cmp_payment_date_gap_days'],
  R10: ['ts_monthly_actual_hours', 'cmp_contract_actual_hours_gap', 'cond_daily_limit_exceeded', 'cond_change_reason_available', 'cond_worker_confirmed'],
  R11: ['ref_minimum_hourly_wage', 'cmp_contract_minimum_wage_gap', 'cmp_payslip_minimum_wage_gap', 'cond_any_below_minimum_wage']
};
const evidenceLabels = {
  cmp_worker_match: '문서별 근로자 이름', cmp_employer_match: '문서별 사업장명', cmp_period_match: '문서별 대상 기간',
  calc_contract_hourly_wage: '계약서 기준 시급', calc_payslip_hourly_wage: '명세서 적용 시급',
  cmp_hourly_wage_gap: '시급 차이', param_wage_tolerance: '허용 차이', ts_period_actual_hours: '근무기록 시간',
  ps_actual_hours_equiv: '명세서 지급시간', cmp_actual_hours_gap: '시간 차이', ts_period_coverage: '근무기록 포함 비율',
  cmp_bonus_gap: '상여금 차이', cmp_extra_pay_gap: '기타 수당 차이', cmp_overtime_pay_gap: '연장근로수당 차이',
  cmp_unmatched_pay_items: '계약 근거를 찾지 못한 지급항목', calc_expected_housing_deduction: '계약상 숙박비',
  cmp_housing_deduction_gap: '숙박비 공제 차이', calc_expected_meal_deduction: '계약상 식비',
  cmp_meal_deduction_gap: '식비 공제 차이', calc_gross_pay: '항목을 더한 지급액', cmp_gross_pay_gap: '인쇄된 총지급액과 차이',
  param_gross_tolerance: '허용 차이', calc_total_deduction: '항목을 더한 공제액', cmp_total_deduction_gap: '인쇄된 총공제액과 차이',
  cmp_tolerance_deduction_won: '허용 차이', calc_net_pay: '계산한 실수령액', cmp_net_pay_gap: '인쇄된 실수령액과 차이',
  cmp_tolerance_net_pay_won: '허용 차이', calc_salary_deposit_count: '선택한 입금 건수',
  calc_salary_deposit_total: '선택한 입금 합계', cmp_deposit_gap: '실수령액과 입금액 차이',
  calc_scheduled_payment_date: '계약상 지급 예정일', calc_actual_payment_completion_date: '실제 전액 지급일',
  cmp_payment_date_gap_days: '지급일 차이', ts_monthly_actual_hours: '월 실제 근로시간',
  cmp_contract_actual_hours_gap: '계약시간과 실제시간 차이', cond_daily_limit_exceeded: '1일 상한 초과',
  cond_change_reason_available: '근무시간 변경 사유 기록', cond_worker_confirmed: '근로자 확인',
  ref_minimum_hourly_wage: '적용 최저시급', cmp_contract_minimum_wage_gap: '계약 시급과 최저시급 차이',
  cmp_payslip_minimum_wage_gap: '명세서 시급과 최저시급 차이', cond_any_below_minimum_wage: '최저임금 미달'
};
function evidenceValue(field, value) {
  if (typeof value === 'boolean') {
    if (field.startsWith('cmp_') && field.endsWith('_match')) return value ? '일치' : '불일치';
    return value ? '예' : '아니오';
  }
  if (Array.isArray(value)) return value.length ? value.join(', ') : '없음';
  if (field === 'ts_period_coverage') return `${(Number(value) * 100).toFixed(1)}%`;
  if (field.endsWith('_days')) return `${value}일`;
  if (field.includes('hours') || field.includes('_hours_')) return `${value}시간`;
  if (field.includes('count')) return `${value}건`;
  if (field.includes('wage') || field.includes('pay') || field.includes('deduction') || field.includes('deposit') || field.includes('tolerance') || field.endsWith('_gap')) return money(value);
  return String(value);
}
function readableEvidence(id, derived) {
  const rows = (evidenceFields[id] || []).filter(field => derived?.[field] !== null && derived?.[field] !== undefined);
  if (!rows.length) return '';
  return `<details><summary>왜 이렇게 판정했나요?</summary><dl class="evidence-list">${rows.map(field => `<div><dt>${evidenceLabels[field] || field}</dt><dd>${evidenceValue(field, derived[field])}</dd></div>`).join('')}</dl></details>`;
}
function legalGuidance(section) {
  if (!section) return '';
  const explanations = (section['해석'] || []).map(line => `<p>${line}</p>`).join('');
  const actions = (section['대응'] || []).map(line => `<li>${line}</li>`).join('');
  const checks = (section['확인사항'] || []).map(line => `<li>${line}</li>`).join('');
  const questions = (section['질문'] || []).map(line => `<li>${line}</li>`).join('');
  const laws = [
    ...(section['계약서근거'] || []).filter(item => item['역할'] === 'primary').map(item => item['인용']),
    ...(section['근거조항'] || []).map(item => item['인용']),
    ...(section['참고조항'] || []).map(item => item['인용']),
    ...(section['참고자료'] || []).map(item => `${item['발행처']} ${item['명칭']}`)
  ];
  return `<div class="legal-guidance"><h3>이 결과는 이런 뜻이에요</h3>${explanations}
    ${checks ? `<h4>추가로 확인할 내용</h4><ul>${checks}</ul>` : ''}
    ${questions ? `<h4>확인을 위한 질문</h4><ul>${questions}</ul>` : ''}
    ${actions ? `<h4>다음에 할 수 있는 일</h4><ol>${actions}</ol>` : ''}
    ${laws.length ? `<details><summary>관련 공식 기준 확인하기</summary><ul>${laws.map(line => `<li>${line}</li>`).join('')}</ul></details>` : ''}</div>`;
}

function employerSummary() {
  if (!latestReport) return '';
  const contract = latestReport.result.documents.contract || {};
  const payslip = latestReport.result.documents.payslip || {};
  const lines = [
    '임금 확인 결과 요약',
    `근로자: ${contract.ct_employee_name || '-'}`,
    `사업장: ${contract.ct_employer_name || '-'}`,
    `급여기간: ${payslip.ps_pay_period_start || '-'} ~ ${payslip.ps_pay_period_end || '-'}`,
    '', '확인이 필요한 항목'
  ];
  let count = 0;
  Object.entries(latestReport.result.rule_results || {}).forEach(([id, value]) => {
    const status = value[`${id.toLowerCase()}_result`];
    if (status === 'PASS') return;
    count += 1;
    lines.push(`${count}. [${id}] ${ruleTitles[id] || id}`);
    lines.push(`   ${value[`${id.toLowerCase()}_reason`] || ''}`);
  });
  if (!count) lines.push('문서 간 불일치가 발견되지 않았습니다.');
  lines.push('', '※ 본 결과는 문서 간 차이를 확인하는 참고자료이며 법률 판단을 대신하지 않습니다.');
  return lines.join('\n');
}

function downloadText(filename, content) {
  const url = URL.createObjectURL(new Blob([content], { type: 'text/plain;charset=utf-8' }));
  const link = document.createElement('a');
  link.href = url;
  link.download = filename;
  link.click();
  URL.revokeObjectURL(url);
}

document.querySelector('#save-result-pdf').addEventListener('click', () => window.print());
document.querySelector('#show-employer-summary').addEventListener('click', () => {
  document.querySelector('#employer-summary-text').textContent = employerSummary();
  document.querySelector('#employer-summary-dialog').showModal();
});
document.querySelector('#copy-employer-summary').addEventListener('click', async event => {
  await navigator.clipboard.writeText(employerSummary());
  event.currentTarget.textContent = '복사 완료';
});
document.querySelector('#download-employer-summary').addEventListener('click', () => downloadText('임금확인_사업주용_요약.txt', employerSummary()));
document.querySelector('#show-consultation').addEventListener('click', () => document.querySelector('#consultation-dialog').showModal());
document.querySelector('#transaction-next').addEventListener('click', () => {
  const checks = [...document.querySelectorAll('.salary-check')];
  if (!checks.some(item => item.checked)) return;
  canonical.derived = canonical.derived || {};
  canonical.derived.R08 = canonical.derived.R08 || {};
  canonical.derived.R08.usr_salary_transaction_selected = checks.map(item => item.checked);
  const contract = canonical.documents.contract;
  const payslip = canonical.documents.payslip;
  const selected = checks.filter(item => item.checked);
  document.querySelector('#confirm-summary').innerHTML = `
    <div class="summary-section"><div class="summary-title"><h2>근로자·계약 정보</h2></div><dl>
      <div><dt>근로자명</dt><dd>${contract.ct_employee_name || '-'}</dd></div>
      <div><dt>사업장명</dt><dd>${contract.ct_employer_name || '-'}</dd></div>
      <div><dt>급여 산정기간</dt><dd>${payslip.ps_pay_period_start || '-'} ~ ${payslip.ps_pay_period_end || '-'}</dd></div>
    </dl></div>
    <div class="summary-section"><div class="summary-title"><h2>임금 정보</h2></div><dl>
      <div><dt>계약 임금</dt><dd>${contract.ct_wage_type || '-'} ${money(contract.ct_wage_amount)}</dd></div>
      <div><dt>명세서 적용 시급</dt><dd>${money(payslip.ps_ordinary_hourly_wage)}</dd></div>
      <div><dt>실수령액</dt><dd>${money(payslip.ps_net_pay)}</dd></div>
    </dl></div>
    <div class="summary-section"><div class="summary-title"><h2>선택한 급여 입금</h2></div><dl>
      <div><dt>선택 거래</dt><dd>${selected.length}건</dd></div>
      <div><dt>입금 합계</dt><dd>${money(selected.reduce((sum, item) => sum + Number(item.value), 0))}</dd></div>
    </dl></div>`;
  showScreen('confirm');
});

function renderResult(report) {
  const groups = Object.entries(report.result.rule_results);
  const legalByRule = Object.fromEntries((report.legal_explanation?.['불일치'] || []).map(section => [section.rule_id, section]));
  const counts = { MISMATCH: 0, REVIEW: 0, REVIEW_HIGH: 0, PASS: 0, NOT_CHECKABLE: 0 };
  groups.forEach(([id, value]) => { const status = value[`${id.toLowerCase()}_result`]; counts[status] = (counts[status] || 0) + 1; });
  const attention = counts.MISMATCH + counts.REVIEW + counts.REVIEW_HIGH + counts.NOT_CHECKABLE;
  document.querySelector('#result-hero').innerHTML = `<div><span class="${attention ? 'danger-label' : 'success-label'}">${attention ? '확인 필요' : '검증 완료'}</span><h1>${attention ? `확인할 내용이 ${attention}개 있습니다` : '문서 간 불일치가 없습니다'}</h1><p>R00~R11 분석 결과</p></div><div class="risk"><strong>${counts.REVIEW_HIGH ? '높음' : counts.MISMATCH ? '주의' : '낮음'}</strong><span>위험도</span></div>`;
  document.querySelector('#result-counts').innerHTML = `<div><span>불일치</span><strong>${counts.MISMATCH}</strong></div><div><span>확인 필요</span><strong>${counts.REVIEW + counts.REVIEW_HIGH}</strong></div><div><span>이상 없음</span><strong>${counts.PASS}</strong></div><div><span>기록 부족</span><strong>${counts.NOT_CHECKABLE}</strong></div>`;
  const host = document.querySelector('#issue-list');
  host.innerHTML = '';
  groups.forEach(([id, value]) => {
    const prefix = id.toLowerCase();
    const status = value[`${prefix}_result`];
    const article = document.createElement('article');
    article.className = `issue ${status === 'MISMATCH' || status === 'REVIEW_HIGH' ? 'danger' : status === 'PASS' ? 'info' : 'warning'}`;
    article.innerHTML = `<div><span>${statusLabels[status] || status}</span><small>${id}</small></div><section><h2>${ruleTitles[id] || id}</h2><p>${value[`${prefix}_reason`]}</p>${legalGuidance(legalByRule[id])}${readableEvidence(id, report.result.derived[id])}</section>`;
    host.appendChild(article);
  });
}

document.querySelector('#run-rules').addEventListener('click', async event => {
  const button = event.currentTarget;
  button.textContent = 'R00~R11 검증 중…';
  button.disabled = true;
  try {
    latestReport = await api('/api/evaluate', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ ...canonical, ui_language: window.vitaminI18n?.language || 'ko' }) });
    renderResult(latestReport);
    showScreen('result');
  } catch (error) {
    alert(`룰 검증에 실패했습니다.\n${error.message}`);
  } finally {
    button.textContent = 'R00~R11 검증 시작';
    button.disabled = false;
  }
});

progressButtons.forEach(button => button.addEventListener('click', () => {
  if (!signedIn) return;
  const current = stepOrder.findIndex(name => document.querySelector(`[data-screen="${name}"]`)?.classList.contains('active'));
  const target = stepOrder.indexOf(button.dataset.step);
  if (target <= Math.max(current, 0)) showScreen(button.dataset.step);
}));
