import fs from 'node:fs';
import vm from 'node:vm';

const app = fs.readFileSync(new URL('../ui-prototype/app.js', import.meta.url), 'utf8');
const css = fs.readFileSync(new URL('../ui-prototype/styles.css', import.meta.url), 'utf8');
const server = fs.readFileSync(new URL('../src/vitamin/server.py', import.meta.url), 'utf8');
const helpers = app.slice(app.indexOf('function scalarEntries'), app.indexOf('function renderReviewImage'));
const sandbox = {};
vm.runInNewContext(`
  const fieldLabels = {};
  let reviewProvenance = { documents: { contract: { fields: {
    first: { page: 0, bbox: [10, 20, 30, 40], raw_text: '같은 위치' },
    second: { page: 0, bbox: [10, 20, 30, 40], raw_text: '같은 위치' },
    lines: { rows: [{ value: { page: 1, bbox: [50, 60, 80, 90], raw_text: '행 값' } }] }
  } } } };
  const escapeHtml = value => String(value ?? '').replace(/[&<>"']/g, char => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' })[char]);
  ${helpers}
  globalThis.reviewView = { reviewSourceIndex, reviewField, setProvenance: value => { reviewProvenance = value; } };
`, sandbox);

const doc = { first: 'A', second: 'B', lines: [{ value: 'C' }] };
const index = sandbox.reviewView.reviewSourceIndex('contract', doc);
if (index.markers.length !== 2) throw new Error('동일 bbox 번호 병합 실패');
if (index.byLocator.get('first').number !== index.byLocator.get('second').number) throw new Error('동일 bbox 번호 불일치');
if (index.byLocator.get('lines.0.value').page !== 1) throw new Error('다중 페이지 provenance 연결 실패');
if (!sandbox.reviewView.reviewField('contract', 'first', '<값>', index.byLocator.get('first')).includes('&lt;값&gt;')) throw new Error('필드/번호 렌더링 실패');
if (!css.includes('.source-marker>span{') || !css.includes('display:none') || !css.includes('.source-marker.active-source>span{display:grid}')) throw new Error('선택 전 bbox 번호 숨김 실패');
if (!css.includes('.document-image-scroll{overflow:visible') || css.includes('.document-image-stage{position:relative;width:max(')) throw new Error('문서 전체 이미지 맞춤 실패');
if (!server.includes('_preprocessed_img.png') || server.includes('return self._send_png(folder / f"{role}_{page}_layout_det_res.png")')) throw new Error('깨끗한 원본 이미지 경로 전환 실패');

if (process.argv.includes('--live')) {
  const demo = await fetch('http://127.0.0.1:8000/api/demo').then(response => response.json());
  sandbox.reviewView.setProvenance(demo.provenance);
  for (const [role, document] of Object.entries(demo.canonical.documents)) {
    const sources = sandbox.reviewView.reviewSourceIndex(role, document);
    if (!sources.markers.length || !demo.review_assets[role]?.length) throw new Error(`${role} 실제 provenance 연결 실패`);
  }
}

console.log('review flow smoke: ok');
