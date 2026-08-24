import fs from 'node:fs';
import vm from 'node:vm';

const app = fs.readFileSync(new URL('../ui-prototype/app.js', import.meta.url), 'utf8');
const helpers = app.slice(app.indexOf('const ruleTitles'), app.indexOf('function employerSummary'));
const sandbox = {};
vm.runInNewContext(`
  const money = value => value == null ? '-' : Number(value).toLocaleString('ko-KR') + '원';
  ${helpers}
  globalThis.resultView = { escapeHtml, ruleVisual, renderRuleCard, payrollFlow };
`, sandbox);

const result = {
  documents: {
    payslip: { ps_gross_pay: 1000, ps_total_deduction: 100, ps_net_pay: 900 },
    bank_statement: { transactions: [] }
  },
  derived: Object.fromEntries(Array.from({ length: 12 }, (_, index) => [`R${String(index).padStart(2, '0')}`, {}]))
};
result.derived.R05.calc_gross_pay = 1000;
result.derived.R06.calc_total_deduction = 100;
result.derived.R07.calc_net_pay = 900;

for (let index = 0; index < 12; index += 1) {
  const id = `R${String(index).padStart(2, '0')}`;
  const card = sandbox.resultView.renderRuleCard(id, { [`${id.toLowerCase()}_result`]: 'PASS', [`${id.toLowerCase()}_reason`]: '정상' }, result);
  if (!card.includes(`id="result-${id}"`) || card.includes('undefined')) throw new Error(`${id} 카드 렌더링 실패`);
}
for (const status of ['PASS', 'MISMATCH', 'REVIEW', 'REVIEW_HIGH', 'NOT_CHECKABLE']) {
  if (!sandbox.resultView.renderRuleCard('R00', { r00_result: status, r00_reason: '상태 확인' }, result).includes(status)) throw new Error(`${status} 상태 렌더링 실패`);
}
if (!sandbox.resultView.ruleVisual('R09', {}, result).includes('확인할 수 없습니다')) throw new Error('null 안내 렌더링 실패');
if (!sandbox.resultView.escapeHtml('<script>').includes('&lt;script&gt;')) throw new Error('HTML escaping 실패');
if (!sandbox.resultView.payrollFlow(result).includes('1,000원')) throw new Error('급여 흐름 렌더링 실패');
result.documents.bank_statement.transactions = Array.from({ length: 8 }, (_, index) => ({ bk_transaction_datetime: `2026-01-${index + 1}`, bk_transaction_record: index ? '급여' : '<b>급여</b>', bk_deposit_amount: 100 }));
result.derived.R08 = { usr_salary_transaction_selected: Array(8).fill(true), calc_salary_deposit_total: 800 };
const deposits = sandbox.resultView.ruleVisual('R08', result.derived.R08, result);
if (!deposits.includes('외 2건') || !deposits.includes('&lt;b&gt;급여&lt;/b&gt;')) throw new Error('가변 거래행 렌더링 실패');

if (process.argv.includes('--live')) {
  const demo = await fetch('http://127.0.0.1:8000/api/demo').then(response => response.json());
  const report = await fetch('http://127.0.0.1:8000/api/evaluate', {
    method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(demo.canonical)
  }).then(response => response.json());
  const cards = Object.entries(report.result.rule_results).map(([id, value]) => sandbox.resultView.renderRuleCard(id, value, report.result));
  if (cards.length !== 12 || cards.some(card => card.includes('undefined'))) throw new Error('실제 API 응답 렌더링 실패');
}

console.log('result dashboard smoke: ok');
