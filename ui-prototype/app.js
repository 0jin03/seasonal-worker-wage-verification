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
const reviewRoles = ['contract', 'timesheet', 'payslip', 'bank_statement'];
let reviewProvenance = { documents: {} };
let reviewAssets = {};
let reviewRoleIndex = 0;
let reviewPageByRole = {};
let activeReviewSourceNumber = null;
const reviewConfirmedRoles = new Set();
let currentReviewSources = { markers: [], byNumber: new Map(), byLocator: new Map() };

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
function reviewSourceIndex(role, doc) {
  const fields = reviewProvenance.documents?.[role]?.fields || {};
  const byLocator = new Map();
  const byBox = new Map();
  const markers = [];
  const add = (locator, detail) => {
    const box = detail?.bbox || detail?.roi;
    if (!Array.isArray(box) || box.length !== 4) return;
    const page = Number(detail.page || 0);
    const key = `${page}:${box.map(Number).join(',')}`;
    let source = byBox.get(key);
    if (!source) {
      source = { number: markers.length + 1, page, box: box.map(Number), rawText: detail.raw_text || '', method: detail.method || '' };
      byBox.set(key, source);
      markers.push(source);
    }
    byLocator.set(locator, source);
  };
  scalarEntries(doc).forEach(([field]) => add(field, fields[field]));
  Object.entries(doc).filter(([, value]) => Array.isArray(value)).forEach(([field, rows]) => {
    rows.forEach((row, index) => scalarEntries(row).forEach(([name]) => add(`${field}.${index}.${name}`, fields[field]?.rows?.[index]?.[name])));
  });
  return { markers, byNumber: new Map(markers.map(source => [source.number, source])), byLocator };
}
function reviewSourceBadge(source) {
  return source
    ? `<button type="button" class="source-link" data-source-number="${source.number}" aria-label="문서 위치 ${source.number}번">${source.number}</button>`
    : '<span class="source-unavailable" title="추출 위치 정보 없음">—</span>';
}
function reviewField(role, field, value, source, options = {}) {
  const notApplicable = options.notApplicable || null;
  const status = notApplicable ? '입력 불필요' : value === null ? '확인 필요' : 'OCR 인식값';
  const safeValue = value === null || value === undefined ? '' : escapeHtml(value);
  const control = notApplicable
    ? `<div class="not-applicable-value">해당 없음<small>${escapeHtml(notApplicable)}</small></div>`
    : typeof value === 'boolean'
    ? `<select data-role="${role}" ${options.array ? `data-array="${options.array}" data-index="${options.index}"` : ''} data-field="${field}"><option value="true" ${value ? 'selected' : ''}>예</option><option value="false" ${!value ? 'selected' : ''}>아니오</option></select>`
    : `<input data-role="${role}" ${options.array ? `data-array="${options.array}" data-index="${options.index}"` : ''} data-field="${field}" value="${safeValue}">`;
  return `<div class="review-field ${value === null && !notApplicable ? 'attention' : ''} ${notApplicable ? 'not-applicable-field' : ''}" ${source ? `data-source-number="${source.number}"` : ''}>${reviewSourceBadge(source)}<label><span>${escapeHtml(fieldLabel(field))} <b>${status}</b></span>${control}</label></div>`;
}
function renderReviewImage() {
  const role = reviewRoles[reviewRoleIndex];
  const pages = reviewAssets[role] || [];
  const requested = reviewPageByRole[role] ?? pages[0]?.page ?? 0;
  const asset = pages.find(item => item.page === requested) || pages[0];
  const stage = document.querySelector('#review-image-stage');
  const pageNav = document.querySelector('#review-page-nav');
  pageNav.innerHTML = pages.length > 1 ? pages.map(item => `<button type="button" class="${item.page === asset?.page ? 'active' : ''}" data-review-page="${item.page}">${item.page + 1}쪽</button>`).join('') : '';
  if (!asset) {
    stage.innerHTML = '<div class="document-image-empty"><b>문서 이미지 근거가 없습니다.</b><span>예시 데이터에는 OCR provenance 이미지가 포함되지 않습니다. 실제 PDF를 업로드하면 번호 상자가 표시됩니다.</span></div>';
    return;
  }
  reviewPageByRole[role] = asset.page;
  const markers = currentReviewSources.markers.filter(source => source.page === asset.page).map(source => {
    const [x1, y1, x2, y2] = source.box;
    const left = Math.max(0, x1 / asset.width * 100);
    const top = Math.max(0, y1 / asset.height * 100);
    const width = Math.max(.4, (x2 - x1) / asset.width * 100);
    const height = Math.max(.4, (y2 - y1) / asset.height * 100);
    return `<button type="button" class="source-marker ${source.number === activeReviewSourceNumber ? 'active-source' : ''}" data-source-number="${source.number}" style="left:${left}%;top:${top}%;width:${width}%;height:${height}%" aria-label="${source.number}번 추출 위치: ${escapeHtml(source.rawText)}"><span>${source.number}</span></button>`;
  }).join('');
  stage.innerHTML = `<img src="${escapeHtml(asset.image)}" alt="${escapeHtml(documentLabels[role])} ${asset.page + 1}쪽 OCR 위치 이미지"><div class="source-overlay">${markers}</div>`;
  pageNav.querySelectorAll('[data-review-page]').forEach(button => button.addEventListener('click', () => {
    activeReviewSourceNumber = null;
    reviewPageByRole[role] = Number(button.dataset.reviewPage);
    document.querySelectorAll('.source-link,.review-field').forEach(item => item.classList.remove('active-source'));
    renderReviewImage();
  }));
}
function activateReviewSource(number, fromMarker = false) {
  const source = currentReviewSources.byNumber.get(Number(number));
  if (!source) return;
  activeReviewSourceNumber = source.number;
  const role = reviewRoles[reviewRoleIndex];
  if (reviewPageByRole[role] !== source.page) {
    reviewPageByRole[role] = source.page;
    renderReviewImage();
  }
  document.querySelectorAll('.source-marker,.source-link,.review-field').forEach(item => item.classList.toggle('active-source', Number(item.dataset.sourceNumber) === source.number));
  if (fromMarker) {
    const field = document.querySelector(`.review-field[data-source-number="${source.number}"]`);
    if (field) {
      const details = field.closest('details');
      if (details) details.open = true;
      field.scrollIntoView({ behavior: 'smooth', block: 'center' });
    }
  }
}
function renderReviewProgress() {
  const host = document.querySelector('#review-document-progress');
  host.innerHTML = reviewRoles.map((role, index) => `<span class="${index === reviewRoleIndex ? 'current' : reviewConfirmedRoles.has(role) ? 'complete' : ''}"><i>${reviewConfirmedRoles.has(role) ? '✓' : index + 1}</i><b>${documentLabels[role]}</b></span>`).join('');
}
function renderReview() {
  const role = reviewRoles[reviewRoleIndex];
  const doc = canonical.documents[role];
  activeReviewSourceNumber = null;
  currentReviewSources = reviewSourceIndex(role, doc);
  document.querySelector('#review-document-heading').textContent = `${documentLabels[role]}에서 추출한 내용입니다.`;
  document.querySelector('#review-document-title').textContent = documentLabels[role];
  document.querySelector('#review-fields-title').textContent = `${documentLabels[role]} 필드`;
  document.querySelector('#review-document-count').textContent = `${reviewRoleIndex + 1} / ${reviewRoles.length}`;
  renderReviewProgress();
  renderReviewImage();

  const host = document.querySelector('#review-fields');
  const group = document.createElement('div');
  group.className = 'field-group active-document-fields';
  scalarEntries(doc).forEach(([field, value]) => {
    const source = currentReviewSources.byLocator.get(field);
    group.insertAdjacentHTML('beforeend', reviewField(role, field, value, source, { notApplicable: value === null ? notApplicableReason(role, field, doc) : null }));
  });
  Object.entries(doc).filter(([, value]) => Array.isArray(value)).forEach(([field, rows]) => {
    const details = document.createElement('details');
    details.innerHTML = `<summary>${escapeHtml(fieldLabel(field))} (${rows.length}건) 확인</summary>`;
    rows.forEach((row, index) => {
      const rowGroup = document.createElement('div');
      rowGroup.className = 'review-array-row';
      rowGroup.innerHTML = `<h3>${index + 1}번째 행</h3>${scalarEntries(row).map(([name, value]) => reviewField(role, name, value, currentReviewSources.byLocator.get(`${field}.${index}.${name}`), { array: field, index })).join('')}`;
      details.appendChild(rowGroup);
    });
    group.appendChild(details);
  });
  host.replaceChildren(group);

  const confirmed = reviewConfirmedRoles.has(role);
  document.querySelector('#review-confirmed').checked = confirmed;
  document.querySelector('#review-next').disabled = !confirmed;
  document.querySelector('#review-next').textContent = reviewRoleIndex === reviewRoles.length - 1 ? '급여 선택으로 이동' : '다음 문서';
  const warning = document.querySelector('#review-warning');
  warning.textContent = confirmed ? '확인 완료' : '사용자 확인 필요';
  warning.className = confirmed ? 'success-label' : 'warning-label';
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
    reviewProvenance = data.provenance || { documents: {} };
    reviewAssets = data.review_assets || {};
    reviewRoleIndex = 0;
    reviewPageByRole = {};
    reviewConfirmedRoles.clear();
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
    reviewProvenance = data.provenance || { documents: {} };
    reviewAssets = data.review_assets || {};
    reviewRoleIndex = 0;
    reviewPageByRole = {};
    reviewConfirmedRoles.clear();
    renderReview();
    showScreen('review');
  } catch (error) {
    alert(error.message);
  }
});

const reviewConfirmed = document.querySelector('#review-confirmed');
const reviewNext = document.querySelector('#review-next');
reviewConfirmed.addEventListener('change', () => {
  const role = reviewRoles[reviewRoleIndex];
  if (reviewConfirmed.checked) reviewConfirmedRoles.add(role); else reviewConfirmedRoles.delete(role);
  reviewNext.disabled = !reviewConfirmed.checked;
  const warning = document.querySelector('#review-warning');
  warning.textContent = reviewConfirmed.checked ? '확인 완료' : '사용자 확인 필요';
  warning.className = reviewConfirmed.checked ? 'success-label' : 'warning-label';
  renderReviewProgress();
});
document.querySelector('#review-previous').addEventListener('click', () => {
  applyReviewEdits();
  if (reviewRoleIndex === 0) return showScreen('upload');
  reviewRoleIndex -= 1;
  renderReview();
  window.scrollTo({ top: 0, behavior: 'smooth' });
});
reviewNext.addEventListener('click', () => {
  if (!reviewConfirmed.checked) return;
  applyReviewEdits();
  if (reviewRoleIndex === reviewRoles.length - 1) {
    renderTransactions();
    return showScreen('transactions');
  }
  reviewRoleIndex += 1;
  renderReview();
  window.scrollTo({ top: 0, behavior: 'smooth' });
});
document.querySelector('#review-fields').addEventListener('click', event => {
  const target = event.target.closest('[data-source-number]');
  if (target) activateReviewSource(target.dataset.sourceNumber);
});
document.querySelector('#review-image-stage').addEventListener('click', event => {
  const marker = event.target.closest('.source-marker');
  if (marker) activateReviewSource(marker.dataset.sourceNumber, true);
});

function finiteNumber(value) {
  if (value === null || value === undefined || value === '') return null;
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : null;
}
function money(value) {
  const parsed = finiteNumber(value);
  return parsed === null ? '확인할 수 없음' : parsed.toLocaleString('ko-KR') + '원';
}
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
const statusMeta = {
  REVIEW_HIGH: { icon: '!!', rank: 0, tone: 'danger' },
  MISMATCH: { icon: '!', rank: 1, tone: 'danger' },
  REVIEW: { icon: '?', rank: 2, tone: 'warning' },
  NOT_CHECKABLE: { icon: '—', rank: 3, tone: 'muted' },
  PASS: { icon: '✓', rank: 4, tone: 'pass' }
};
const ruleDomains = [
  { label: '문서 연결', ids: ['R00'] },
  { label: '임금·근로조건', ids: ['R01', 'R02', 'R03', 'R04', 'R10', 'R11'] },
  { label: '급여 계산', ids: ['R05', 'R06', 'R07'] },
  { label: '입금·지급일', ids: ['R08', 'R09'] }
];
function verifyResultViewConfig() {
  const ids = ruleDomains.flatMap(domain => domain.ids);
  const expected = Array.from({ length: 12 }, (_, index) => `R${String(index).padStart(2, '0')}`);
  if (new Set(ids).size !== 12 || expected.some(id => !ids.includes(id) || !ruleTitles[id])) throw new Error('결과 화면 R00~R11 구성이 올바르지 않습니다.');
}
verifyResultViewConfig();
const evidenceFields = {
  R00: ['cmp_worker_match', 'cmp_employer_match', 'cmp_period_match'],
  R01: ['calc_contract_hourly_wage', 'calc_payslip_hourly_wage', 'cmp_hourly_wage_gap', 'param_wage_tolerance'],
  R02: ['ts_period_actual_hours', 'ps_actual_hours_equiv', 'cmp_actual_hours_gap', 'cmp_tolerance_hours', 'ts_period_coverage'],
  R03: ['ct_bonus_amount', 'ps_bonus_amount', 'ct_extra_pay_amount', 'ps_other_allowance', 'ps_overtime_pay', 'ps_night_work_pay', 'ps_holiday_work_pay', 'cmp_bonus_gap', 'cmp_extra_pay_gap', 'cmp_overtime_pay_gap', 'cmp_unmatched_pay_items'],
  R04: ['calc_expected_housing_deduction', 'cmp_housing_deduction_gap', 'calc_expected_meal_deduction', 'cmp_meal_deduction_gap'],
  R05: ['calc_gross_pay', 'cmp_gross_pay_gap', 'param_gross_tolerance'],
  R06: ['calc_total_deduction', 'cmp_total_deduction_gap', 'cmp_tolerance_deduction_won'],
  R07: ['calc_net_pay', 'cmp_net_pay_gap', 'cmp_tolerance_net_pay_won'],
  R08: ['calc_salary_deposit_count', 'calc_salary_deposit_total', 'cmp_deposit_gap'],
  R09: ['calc_scheduled_payment_date', 'calc_adjusted_scheduled_payment_date', 'calc_actual_payment_completion_date', 'cmp_payment_date_gap_days'],
  R10: ['ts_monthly_actual_hours', 'cmp_contract_actual_hours_gap', 'cond_daily_limit_exceeded', 'cond_change_reason_available', 'cond_worker_confirmed'],
  R11: ['ref_minimum_hourly_wage', 'cmp_contract_minimum_wage_gap', 'cmp_payslip_minimum_wage_gap', 'cond_any_below_minimum_wage']
};
const evidenceLabels = {
  cmp_worker_match: '문서별 근로자 이름', cmp_employer_match: '문서별 사업장명', cmp_period_match: '문서별 대상 기간',
  calc_contract_hourly_wage: '계약서 기준 시급', calc_payslip_hourly_wage: '명세서 적용 시급',
  cmp_hourly_wage_gap: '시급 차이', param_wage_tolerance: '허용 차이', ts_period_actual_hours: '근무기록 시간',
  ps_actual_hours_equiv: '명세서 지급시간', cmp_actual_hours_gap: '시간 차이', cmp_tolerance_hours: '허용 차이', ts_period_coverage: '근무기록 포함 비율',
  ct_bonus_amount: '계약서 상여금', ps_bonus_amount: '명세서 상여금',
  ct_extra_pay_amount: '계약서 기타 수당', ps_other_allowance: '명세서 기타 수당',
  ps_overtime_pay: '명세서 연장근로수당', ps_night_work_pay: '명세서 야간근로수당', ps_holiday_work_pay: '명세서 휴일근로수당',
  cmp_bonus_gap: '상여금 차이', cmp_extra_pay_gap: '기타 수당 차이', cmp_overtime_pay_gap: '연장근로수당 차이',
  cmp_unmatched_pay_items: '계약 근거를 찾지 못한 지급항목', calc_expected_housing_deduction: '계약상 숙박비',
  cmp_housing_deduction_gap: '숙박비 공제 차이', calc_expected_meal_deduction: '계약상 식비',
  cmp_meal_deduction_gap: '식비 공제 차이', calc_gross_pay: '항목을 더한 지급액', cmp_gross_pay_gap: '인쇄된 총지급액과 차이',
  param_gross_tolerance: '허용 차이', calc_total_deduction: '항목을 더한 공제액', cmp_total_deduction_gap: '인쇄된 총공제액과 차이',
  cmp_tolerance_deduction_won: '허용 차이', calc_net_pay: '계산한 실수령액', cmp_net_pay_gap: '인쇄된 실수령액과 차이',
  cmp_tolerance_net_pay_won: '허용 차이', calc_salary_deposit_count: '선택한 입금 건수',
  calc_salary_deposit_total: '선택한 입금 합계', cmp_deposit_gap: '실수령액과 입금액 차이',
  calc_scheduled_payment_date: '계약서에 적힌 지급일', calc_adjusted_scheduled_payment_date: '주말·공휴일 조정 후 지급일', calc_actual_payment_completion_date: '실제 전액 지급일',
  cmp_payment_date_gap_days: '지급일 차이', ts_monthly_actual_hours: '월 실제 근로시간',
  cmp_contract_actual_hours_gap: '계약시간과 실제시간 차이', cond_daily_limit_exceeded: '1일 상한 초과',
  cond_change_reason_available: '근무시간 변경 사유 기록', cond_worker_confirmed: '근로자 확인',
  ref_minimum_hourly_wage: '적용 최저시급', cmp_contract_minimum_wage_gap: '계약 시급과 최저시급 차이',
  cmp_payslip_minimum_wage_gap: '명세서 시급과 최저시급 차이', cond_any_below_minimum_wage: '최저임금 미달'
};
function escapeHtml(value) {
  return String(value ?? '').replace(/[&<>"']/g, char => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' })[char]);
}
function numberOrNull(value) {
  if (value === null || value === undefined || value === '') return null;
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : null;
}
function displayValue(value, kind = 'text') {
  if (value === null || value === undefined || value === '') return '<span class="unknown-value">확인되지 않음</span>';
  if (kind === 'money') return escapeHtml(money(value));
  if (kind === 'hours') return `${escapeHtml(value)}시간`;
  if (kind === 'days') return `${escapeHtml(value)}일`;
  if (kind === 'percent') return numberOrNull(value) === null ? '<span class="unknown-value">확인되지 않음</span>' : `${(Number(value) * 100).toFixed(1)}%`;
  return escapeHtml(value);
}
function evidenceValue(field, value) {
  if (value === null || value === undefined || (typeof value === 'number' && !Number.isFinite(value))) return '확인할 수 없음';
  if (typeof value === 'boolean') {
    if (field.startsWith('cmp_') && field.endsWith('_match')) return value ? '일치' : '불일치';
    return value ? '예' : '아니오';
  }
  if (Array.isArray(value)) return value.length ? value.map(escapeHtml).join(', ') : '없음';
  if (field === 'ts_period_coverage') {
    const parsed = finiteNumber(value);
    return parsed === null ? '확인할 수 없음' : `${(parsed * 100).toFixed(1)}%`;
  }
  if (field.includes('_date')) return escapeHtml(value);
  if (field.endsWith('_days')) return `${value}일`;
  if (field.includes('hours') || field.includes('_hours_')) return `${value}시간`;
  if (field.includes('count')) return `${value}건`;
  if (field.includes('wage') || field.includes('pay') || field.includes('deduction') || field.includes('deposit') || field.includes('tolerance') || field.endsWith('_gap')) return money(value);
  return escapeHtml(value);
}
function readableEvidence(id, derived) {
  const rows = (evidenceFields[id] || []).filter(field => {
    const value = derived?.[field];
    return value !== null && value !== undefined && !(typeof value === 'number' && !Number.isFinite(value));
  });
  if (!rows.length) return '';
  return `<details class="rule-details"><summary>상세 계산 근거</summary><dl class="evidence-list">${rows.map(field => `<div><dt>${escapeHtml(evidenceLabels[field] || field)}</dt><dd>${evidenceValue(field, derived[field])}</dd></div>`).join('')}</dl></details>`;
}
function legalGuidance(section) {
  if (!section) return '';
  const explanations = (section['해석'] || []).map(line => `<p>${escapeHtml(line)}</p>`).join('');
  const actions = (section['대응'] || []).map(line => `<li>${escapeHtml(line)}</li>`).join('');
  const checks = (section['확인사항'] || []).map(line => `<li>${escapeHtml(line)}</li>`).join('');
  const questions = (section['질문'] || []).map(line => `<li>${escapeHtml(line)}</li>`).join('');
  const fixedLawItems = [
    ...(section['근거조항'] || []), ...(section['참고조항'] || []),
    ...(section['조건부조항'] || [])
  ];
  const searchItems = section['검색조항'] || [];
  const laws = [
    ...(section['근거미발견'] ? ['<li><strong>근거 조문을 찾지 못했습니다.</strong><p>확인되지 않은 법령을 임의로 안내하지 않습니다.</p></li>'] : []),
    ...(section['계약서근거'] || []).filter(item => item['역할'] === 'primary').map(item => `<li><strong>${escapeHtml(item['인용'])}</strong><p>${escapeHtml(item['확인내용'])}</p></li>`),
    ...fixedLawItems.map(item => `<li><strong>${escapeHtml(item['인용'])}</strong>${item['시행일자'] ? `<small>시행일 ${escapeHtml(item['시행일자'])}</small>` : ''}${item['수집일'] ? `<small>자료 수집일 ${escapeHtml(item['수집일'])}</small>` : ''}<p>${escapeHtml(item['본문'] || '')}</p>${item['출처'] ? `<a href="${escapeHtml(item['출처'])}" target="_blank" rel="noopener noreferrer">국가법령정보센터에서 보기</a>` : ''}</li>`),
    ...searchItems.map(item => `<li><strong>상황 키워드 보조검색 · ${escapeHtml(item['인용'])}</strong>${item['시행일자'] ? `<small>시행일 ${escapeHtml(item['시행일자'])}</small>` : ''}${item['수집일'] ? `<small>자료 수집일 ${escapeHtml(item['수집일'])}</small>` : ''}<p>${escapeHtml(item['본문'] || '')}</p>${item['출처'] ? `<a href="${escapeHtml(item['출처'])}" target="_blank" rel="noopener noreferrer">국가법령정보센터에서 보기</a>` : ''}</li>`),
    ...(section['참고자료'] || []).map(item => `<li><strong>${escapeHtml(item['발행처'])} ${escapeHtml(item['명칭'])}</strong></li>`)
  ];
  return `<details class="rule-details legal-details"><summary>법령 및 대응 안내</summary><div class="legal-guidance"><p class="result-nature">판정 성격: <strong>${escapeHtml(section['성격'] || '확인')}</strong></p><h3>이 결과는 이런 뜻이에요</h3>${explanations}
    ${checks ? `<h4>추가로 확인할 내용</h4><ul>${checks}</ul>` : ''}
    ${questions ? `<h4>확인을 위한 질문</h4><ul>${questions}</ul>` : ''}
    ${actions ? `<h4>다음에 할 수 있는 일</h4><ol>${actions}</ol>` : ''}
    ${laws.length ? `<details><summary>관련 공식 기준 확인하기</summary><ul>${laws.join('')}</ul></details>` : ''}</div></details>`;
}

function emptyVisual(message) {
  return `<div class="visual-empty"><span aria-hidden="true">—</span><p>${escapeHtml(message)}</p></div>`;
}
function fact(label, value, tone = '') {
  return `<div class="visual-fact ${tone}"><span>${escapeHtml(label)}</span><strong>${value}</strong></div>`;
}
function booleanFact(label, value, positiveWhenTrue = true) {
  if (value === null || value === undefined) return fact(label, '<span class="unknown-value">확인되지 않음</span>', 'unknown');
  const good = positiveWhenTrue ? value === true : value === false;
  return fact(label, `<span class="fact-state"><i aria-hidden="true">${good ? '✓' : '!'}</i>${value ? '예' : '아니오'}</span>`, good ? 'good' : 'bad');
}
function comparisonVisual(rows, gap = null, tolerance = null) {
  const known = rows.map(row => numberOrNull(row.value)).filter(value => value !== null);
  if (!known.length) return emptyVisual('비교할 값이 확인되지 않았습니다.');
  const maximum = Math.max(...known.map(Math.abs), 1);
  const bars = rows.map(row => {
    const numeric = numberOrNull(row.value);
    const width = numeric === null ? 0 : Math.max(2, Math.min(100, Math.abs(numeric) / maximum * 100));
    return `<div class="comparison-row"><div><span>${escapeHtml(row.label)}</span><strong>${displayValue(row.value, row.kind)}</strong></div><div class="comparison-track" aria-hidden="true"><i style="width:${width.toFixed(1)}%"></i></div></div>`;
  }).join('');
  const footer = gap === null && tolerance === null ? '' : `<div class="comparison-summary">${fact('차이', displayValue(gap, rows[0]?.kind || 'text'))}${fact('허용오차', displayValue(tolerance, rows[0]?.kind || 'text'))}</div>`;
  return `<div class="comparison-visual">${bars}${footer}</div>`;
}
function listVisual(items, emptyMessage) {
  if (!items?.length) return emptyVisual(emptyMessage);
  return `<ul class="compact-list">${items.map(item => `<li>${escapeHtml(item)}</li>`).join('')}</ul>`;
}
function ruleVisual(id, derived = {}, result = {}) {
  const allDerived = result.derived || {};
  const documents = result.documents || {};
  if (id === 'R00') {
    return `<div class="match-board">
      ${booleanFact('근로자 이름', derived.cmp_worker_match)}
      ${booleanFact('사업장명', derived.cmp_employer_match)}
      ${booleanFact('대상 기간', derived.cmp_period_match)}
    </div>`;
  }
  if (id === 'R01') return comparisonVisual([
    { label: '계약서 환산 시급', value: derived.calc_contract_hourly_wage, kind: 'money' },
    { label: '명세서 적용 시급', value: derived.calc_payslip_hourly_wage, kind: 'money' }
  ], derived.cmp_hourly_wage_gap, derived.param_wage_tolerance ?? 10);
  if (id === 'R02') return `${comparisonVisual([
    { label: '근무기록 시간', value: derived.ts_period_actual_hours, kind: 'hours' },
    { label: '명세서 지급시간', value: derived.ps_actual_hours_equiv, kind: 'hours' }
  ], derived.cmp_actual_hours_gap, derived.cmp_tolerance_hours)}<div class="inline-facts">${fact('근무기록 포함률', displayValue(derived.ts_period_coverage, 'percent'))}</div>`;
  if (id === 'R03') {
    const gaps = [
      ['상여금 차이', derived.cmp_bonus_gap], ['기타 수당 차이', derived.cmp_extra_pay_gap], ['연장근로수당 차이', derived.cmp_overtime_pay_gap]
    ].filter(([, value]) => value !== null && value !== undefined);
    const unmatched = Array.isArray(derived.cmp_unmatched_pay_items) ? derived.cmp_unmatched_pay_items : [];
    if (!gaps.length && !unmatched.length) return emptyVisual('표시할 개별 수당 차이값이 없습니다.');
    return `<div class="inline-facts">${gaps.map(([label, value]) => fact(label, displayValue(value, 'money'))).join('')}</div>${unmatched.length ? `<h4 class="visual-subtitle">계약 근거를 찾지 못한 지급항목</h4>${listVisual(unmatched, '')}` : ''}`;
  }
  if (id === 'R04') return `<div class="deduction-grid">
    <section><h4>숙박비</h4>${fact('계약상 금액', displayValue(derived.calc_expected_housing_deduction ?? documents.contract?.ct_housing_cost, 'money'))}${fact('공제 차이', displayValue(derived.cmp_housing_deduction_gap, 'money'))}</section>
    <section><h4>식비</h4>${fact('계약상 금액', displayValue(derived.calc_expected_meal_deduction ?? documents.contract?.ct_meal_cost, 'money'))}${fact('공제 차이', displayValue(derived.cmp_meal_deduction_gap, 'money'))}</section>
  </div>`;
  if (id === 'R05') return comparisonVisual([
    { label: '항목 합산값', value: derived.calc_gross_pay, kind: 'money' },
    { label: '명세서 총지급액', value: documents.payslip?.ps_gross_pay, kind: 'money' }
  ], derived.cmp_gross_pay_gap, derived.param_gross_tolerance);
  if (id === 'R06') return comparisonVisual([
    { label: '항목 합산값', value: derived.calc_total_deduction, kind: 'money' },
    { label: '명세서 총공제액', value: documents.payslip?.ps_total_deduction, kind: 'money' }
  ], derived.cmp_total_deduction_gap, derived.cmp_tolerance_deduction_won);
  if (id === 'R07') return comparisonVisual([
    { label: '지급액-공제액', value: derived.calc_net_pay, kind: 'money' },
    { label: '명세서 실수령액', value: documents.payslip?.ps_net_pay, kind: 'money' }
  ], derived.cmp_net_pay_gap, derived.cmp_tolerance_net_pay_won);
  if (id === 'R08') {
    const transactions = documents.bank_statement?.transactions || [];
    const selectedFlags = derived.usr_salary_transaction_selected || allDerived.R08?.usr_salary_transaction_selected || [];
    const selected = transactions.filter((_, index) => selectedFlags[index]);
    const target = numberOrNull(allDerived.R07?.calc_net_pay ?? documents.payslip?.ps_net_pay);
    const total = numberOrNull(derived.calc_salary_deposit_total);
    const progress = target && total !== null ? Math.min(100, Math.max(0, total / target * 100)) : 0;
    const rows = selected.slice(0, 6).map(transaction => {
      const date = transaction.bk_transaction_datetime || transaction.transaction_datetime || '-';
      const record = transaction.bk_transaction_record || transaction.transaction_record || transaction.memo || '메모 없음';
      const amount = transaction.bk_deposit_amount ?? transaction.deposit_amount ?? transaction.amount;
      return `<li><span>${escapeHtml(date)}</span><b>${escapeHtml(record)}</b><strong>${displayValue(amount, 'money')}</strong></li>`;
    }).join('');
    return `<div class="deposit-progress"><div><span>선택 입금 합계</span><strong>${displayValue(total, 'money')}</strong><small><span>목표 실수령액</span> ${displayValue(target, 'money')}</small></div><div class="progress-track" aria-label="입금 달성률 ${progress.toFixed(0)}%"><i style="width:${progress}%"></i></div></div>
      ${selected.length ? `<ul class="transaction-mini-list">${rows}${selected.length > 6 ? `<li class="more-row">외 ${selected.length - 6}건</li>` : ''}</ul>` : emptyVisual('선택한 급여 거래가 없습니다.')}`;
  }
  if (id === 'R09') {
    const scheduled = derived.calc_scheduled_payment_date;
    const actual = derived.calc_actual_payment_completion_date;
    if (!scheduled && !actual) return emptyVisual('지급 예정일과 실제 완료일을 확인할 수 없습니다.');
    return `<div class="date-timeline"><div>${fact('계약상 지급 예정일', displayValue(scheduled))}</div><i aria-hidden="true">→</i><div>${fact('실제 전액 지급일', displayValue(actual))}</div></div><div class="inline-facts">${fact('지급일 차이', displayValue(derived.cmp_payment_date_gap_days, 'days'))}</div>`;
  }
  if (id === 'R10') return `<div class="match-board">
    ${fact('월 실제 근로시간', displayValue(derived.ts_monthly_actual_hours, 'hours'))}
    ${fact('계약시간과 차이', displayValue(derived.cmp_contract_actual_hours_gap, 'hours'))}
    ${booleanFact('1일 상한 초과', derived.cond_daily_limit_exceeded, false)}
    ${booleanFact('변경 사유 기록', derived.cond_change_reason_available)}
    ${booleanFact('근로자 확인', derived.cond_worker_confirmed)}
  </div>`;
  if (id === 'R11') {
    const belowMinimum = derived.cond_any_below_minimum_wage ?? [derived.cmp_contract_minimum_wage_gap, derived.cmp_payslip_minimum_wage_gap].some(value => numberOrNull(value) !== null && Number(value) < 0);
    return `${comparisonVisual([
    { label: '기준 최저시급', value: derived.ref_minimum_hourly_wage, kind: 'money' },
    { label: '계약서 환산 시급', value: allDerived.R01?.calc_contract_hourly_wage, kind: 'money' },
    { label: '명세서 적용 시급', value: allDerived.R01?.calc_payslip_hourly_wage, kind: 'money' }
  ])}<div class="inline-facts">${booleanFact('최저임금 미달', belowMinimum, false)}</div>`;
  }
  return emptyVisual('별도 시각화 없이 상세 계산 근거에서 확인할 수 있습니다.');
}

function payrollFlow(result) {
  const payslip = result.documents?.payslip || {};
  const derived = result.derived || {};
  const steps = [
    ['총지급액', derived.R05?.calc_gross_pay, payslip.ps_gross_pay],
    ['총공제액', derived.R06?.calc_total_deduction, payslip.ps_total_deduction],
    ['실수령액', derived.R07?.calc_net_pay, payslip.ps_net_pay]
  ];
  if (steps.every(([, calculated, printed]) => numberOrNull(calculated) === null && numberOrNull(printed) === null)) return '';
  return `<section class="payroll-flow" aria-labelledby="payroll-flow-title"><div class="section-heading"><div><span>급여 계산</span><h2 id="payroll-flow-title">지급액 − 공제액 = 실수령액</h2></div><small>계산값 / 명세서 인쇄값</small></div><div class="flow-steps">${steps.map(([label, calculated, printed], index) => `<div class="flow-step"><span>${escapeHtml(label)}</span><strong>${displayValue(calculated, 'money')}</strong><small>${displayValue(printed, 'money')}</small></div>${index < steps.length - 1 ? `<i aria-hidden="true">${index === 0 ? '−' : '='}</i>` : ''}`).join('')}</div></section>`;
}

function actionForRule(id, status) {
  if (status === 'PASS') return '';
  if (id === 'R00') return '문서별 이름·사업장·대상 기간을 확인하세요.';
  if (id === 'R08') return '실제 급여로 지급된 입금 거래를 선택하세요.';
  if (id === 'R09') return '선택한 급여 거래와 지급 예정일을 확인하세요.';
  if (status === 'NOT_CHECKABLE') return '필요한 기록이 있는지 확인한 뒤 다시 판정하세요.';
  return '원본 문서와 상세 계산 근거를 함께 확인하세요.';
}

function renderRuleCard(id, value, result, legalSection) {
  const prefix = id.toLowerCase();
  const status = value[`${prefix}_result`];
  const meta = statusMeta[status] || { icon: '?', tone: 'muted', rank: 3 };
  const reason = value[`${prefix}_reason`] || '판정 사유가 제공되지 않았습니다.';
  const action = actionForRule(id, status);
  return `<article class="rule-card ${meta.tone}" id="result-${id}" data-status="${escapeHtml(status)}" data-rank="${meta.rank}" tabindex="-1">
    <header><div class="rule-identity"><span class="status-icon" aria-hidden="true">${meta.icon}</span><div><small>${id}</small><h3>${escapeHtml(ruleTitles[id] || id)}</h3></div></div><span class="status-pill">${escapeHtml(statusLabels[status] || status)}</span></header>
    <p class="rule-reason">${escapeHtml(reason)}</p>
    <div class="rule-visual">${ruleVisual(id, result.derived?.[id], result)}</div>
    ${action ? `<div class="rule-action"><b>필요한 조치</b><span>${escapeHtml(action)}</span></div>` : ''}
    <div class="rule-disclosures">${readableEvidence(id, result.derived?.[id])}${legalGuidance(legalSection)}</div>
  </article>`;
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

let printDetailState = [];
window.addEventListener('beforeprint', () => {
  printDetailState = [...document.querySelectorAll('#issue-list details')].map(detail => [detail, detail.open]);
  printDetailState.forEach(([detail]) => { detail.open = true; });
});
window.addEventListener('afterprint', () => {
  printDetailState.forEach(([detail, wasOpen]) => { detail.open = wasOpen; });
  printDetailState = [];
});
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

function filterResultCards(filter) {
  const matches = status => ({
    all: true,
    attention: status !== 'PASS',
    problem: status === 'MISMATCH' || status === 'REVIEW_HIGH',
    notcheckable: status === 'NOT_CHECKABLE',
    pass: status === 'PASS'
  })[filter] ?? true;
  document.querySelectorAll('.result-filter').forEach(button => {
    const active = button.dataset.filter === filter;
    button.classList.toggle('active', active);
    button.setAttribute('aria-pressed', String(active));
  });
  document.querySelectorAll('.rule-card').forEach(card => { card.hidden = !matches(card.dataset.status); });
  const passGroup = document.querySelector('.pass-results');
  if (passGroup && filter === 'attention') {
    passGroup.querySelectorAll('.rule-card').forEach(card => { card.hidden = false; });
    passGroup.open = false;
  }
  document.querySelectorAll('[data-result-section]').forEach(section => {
    const visible = [...section.querySelectorAll('.rule-card')].some(card => !card.hidden);
    section.hidden = !visible;
  });
  if (passGroup && (filter === 'pass' || filter === 'all')) passGroup.open = true;
}

function renderResult(report) {
  const groups = Object.entries(report.result.rule_results || {}).sort(([a], [b]) => a.localeCompare(b));
  const byId = Object.fromEntries(groups);
  const legalByRule = Object.fromEntries((report.legal_explanation?.['불일치'] || []).map(section => [section.rule_id, section]));
  const counts = { MISMATCH: 0, REVIEW: 0, REVIEW_HIGH: 0, PASS: 0, NOT_CHECKABLE: 0 };
  const statusFor = (id, value = byId[id]) => value?.[`${id.toLowerCase()}_result`] || 'NOT_CHECKABLE';
  groups.forEach(([id, value]) => { const status = statusFor(id, value); counts[status] = (counts[status] || 0) + 1; });
  const total = groups.length;
  const urgent = counts.MISMATCH + counts.REVIEW_HIGH;
  const review = counts.REVIEW;
  const attention = urgent + review + counts.NOT_CHECKABLE;
  const checkable = total - counts.NOT_CHECKABLE;
  const coverageDegrees = total ? Math.round(checkable / total * 360) : 0;
  const headline = urgent ? `${urgent}개 항목을 우선 확인해주세요` : review ? `${review}개 항목을 확인해주세요` : counts.NOT_CHECKABLE ? `${counts.NOT_CHECKABLE}개 항목은 판정할 수 없습니다` : '문서 간 불일치가 없습니다';
  const heroLabel = urgent ? '중요 확인' : attention ? '확인 필요' : '검증 완료';
  document.querySelector('#result-hero').innerHTML = `<div><span class="${urgent ? 'danger-label' : attention ? 'review-label' : 'success-label'}">${heroLabel}</span><h1>${headline}</h1><p>R00~R11 분석 결과를 중요도 순서로 정리했습니다.</p></div><div class="coverage-ring" style="--coverage:${coverageDegrees}deg" role="img" aria-label="전체 ${total}개 규칙 중 ${checkable}개 판정 가능"><div><strong>${checkable}/${total}</strong><span>판정 가능</span></div></div>`;

  const strip = [
    ['MISMATCH', counts.MISMATCH + counts.REVIEW_HIGH, '불일치·중요 확인'],
    ['REVIEW', counts.REVIEW, '확인 필요'],
    ['NOT_CHECKABLE', counts.NOT_CHECKABLE, '판정 불가'],
    ['PASS', counts.PASS, '이상 없음']
  ];
  document.querySelector('#result-counts').innerHTML = `<div class="overview-stats">
      ${fact('전체 규칙', total)}${fact('우선 확인', urgent, urgent ? 'bad' : '')}${fact('확인 필요', review, review ? 'review' : '')}${fact('판정 불가', counts.NOT_CHECKABLE, counts.NOT_CHECKABLE ? 'unknown' : '')}${fact('이상 없음', counts.PASS, 'good')}
    </div>
    <section class="status-overview" aria-labelledby="status-overview-title"><div class="section-heading"><div><span>결과 분포</span><h2 id="status-overview-title">${total}개 규칙 상태</h2></div></div>
      <div class="status-strip" role="img" aria-label="${strip.map(([, count, label]) => `${label} ${count}개`).join(', ')}">${strip.filter(([, count]) => count).map(([status, count]) => `<i class="${statusMeta[status]?.tone || 'muted'}" style="width:${total ? count / total * 100 : 0}%"></i>`).join('')}</div>
      <div class="status-legend">${strip.map(([status, count, label]) => `<span><i class="${statusMeta[status]?.tone || 'muted'}"></i>${label}<b>${count}</b></span>`).join('')}</div>
    </section>
    <section class="rule-map" aria-labelledby="rule-map-title"><div class="section-heading"><div><span>전체 규칙</span><h2 id="rule-map-title">영역별 결과 바로가기</h2></div></div>${ruleDomains.map(domain => `<div><strong>${domain.label}</strong><nav>${domain.ids.map(id => { const status = statusFor(id); const meta = statusMeta[status] || statusMeta.NOT_CHECKABLE; return `<button type="button" class="rule-jump ${meta.tone}" data-rule="${id}" title="${escapeHtml(ruleTitles[id])}: ${escapeHtml(statusLabels[status])}"><span>${id}</span><i aria-hidden="true">${meta.icon}</i></button>`; }).join('')}</nav></div>`).join('')}</section>
    <nav class="result-filters" aria-label="결과 필터">
      <button type="button" class="result-filter" data-filter="all">전체 <b>${total}</b></button>
      <button type="button" class="result-filter" data-filter="attention">확인 필요 <b>${attention}</b></button>
      <button type="button" class="result-filter" data-filter="problem">우선 확인 <b>${urgent}</b></button>
      <button type="button" class="result-filter" data-filter="notcheckable">판정 불가 <b>${counts.NOT_CHECKABLE}</b></button>
      <button type="button" class="result-filter" data-filter="pass">이상 없음 <b>${counts.PASS}</b></button>
    </nav>`;

  const prioritized = groups.filter(([id, value]) => statusFor(id, value) !== 'PASS').sort(([idA, valueA], [idB, valueB]) => (statusMeta[statusFor(idA, valueA)]?.rank ?? 3) - (statusMeta[statusFor(idB, valueB)]?.rank ?? 3));
  const passed = groups.filter(([id, value]) => statusFor(id, value) === 'PASS');
  const host = document.querySelector('#issue-list');
  host.innerHTML = `${payrollFlow(report.result)}
    <section class="priority-results" data-result-section><div class="section-heading result-section-heading"><div><span>우선 확인</span><h2>확인이 필요한 항목</h2></div><small>${prioritized.length}개</small></div>
      <div class="rule-card-list">${prioritized.length ? prioritized.map(([id, value]) => renderRuleCard(id, value, report.result, legalByRule[id])).join('') : `<div class="all-clear"><span aria-hidden="true">✓</span><strong>확인이 필요한 항목이 없습니다.</strong></div>`}</div>
    </section>
    <details class="pass-results" data-result-section><summary><span><i aria-hidden="true">✓</i><b>이상 없음 결과</b><small>${passed.length}개 규칙</small></span><em>펼쳐보기</em></summary><div class="rule-card-list">${passed.map(([id, value]) => renderRuleCard(id, value, report.result, legalByRule[id])).join('')}</div></details>`;

  document.querySelectorAll('.result-filter').forEach(button => button.addEventListener('click', () => filterResultCards(button.dataset.filter)));
  document.querySelectorAll('.rule-jump').forEach(button => button.addEventListener('click', () => {
    filterResultCards('all');
    const card = document.querySelector(`#result-${button.dataset.rule}`);
    card?.scrollIntoView({ behavior: 'smooth', block: 'start' });
    card?.focus({ preventScroll: true });
  }));
  filterResultCards(attention ? 'attention' : 'all');
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
