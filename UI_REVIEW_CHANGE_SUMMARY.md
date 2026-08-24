# OCR 검수·결과 대시보드 개선 안내

기준 브랜치 `rule_test`의 OCR·룰 파이프라인은 유지하고, 사용자가 OCR 추출값과 R00~R11 결과를 쉽게 검수할 수 있도록 UI를 개선했다.

## 주요 변경

### 문서 내용 확인

- 근로계약서 → 근무기록부 → 임금명세서 → 입금내역서 순서로 한 문서씩 확인한다.
- 왼쪽에는 전체 원본 문서, 오른쪽에는 해당 문서의 canonical field를 표시한다.
- 오른쪽 field 번호 또는 왼쪽 OCR 위치를 선택하면 해당 bbox와 번호 하나만 원문 위에 표시한다.
- Paddle layout 분류명(`header`, `figure`, `paragraph`, `text`)과 점수는 사용자 화면에 표시하지 않는다.
- 각 문서를 확인 완료해야 다음 문서로 이동하며, 4개 문서 확인 후 급여 거래 선택으로 이동한다.

### 결과 보기

- R00~R11 상태 분포, 영역별 바로가기, 상태 필터를 추가했다.
- 불일치·검토 필요 결과를 우선 표시하고 PASS 결과는 접을 수 있게 정리했다.
- 금액·시간 비교, 급여 계산 흐름, 입금 거래와 지급일을 카드와 막대 형태로 시각화했다.
- `null`은 0으로 바꾸지 않고 `확인하지 못함`으로 표시한다.
- 인쇄/PDF 저장, 사업주용 요약, 상담기관 안내 기능을 유지한다.

### LLM 쉬운 설명

- 기존 `OPENAI_API_KEY` 기반 쉬운 설명 생성 기능을 제거하지 않았다.
- 백엔드의 `build_legal_explanation()` 결과를 각 규칙 카드의 법적 근거·쉬운 설명 영역에서 그대로 사용한다.
- API key가 없으면 기존 고정문구 fallback을 사용한다. 룰 판정 결과 자체는 LLM이 변경하지 않는다.

## 호환성과 수정 범위

- OCR parser, canonical JSON 구조, v6 Schema, R00~R11 룰 정책은 변경하지 않았다.
- UI가 반환된 `canonical`, `provenance`, `review_assets`, `legal_explanation`을 보여주는 방식만 개선했다.
- UI 경로는 repository 내부 상대경로를 사용하므로 사용자 PC 절대경로나 junction이 필요하지 않다.
- 데모 문서는 기존 합성 OCR 결과를 재사용하며 OCR을 다시 실행하지 않는다.

주요 파일:

- `ui-prototype/index.html`
- `ui-prototype/app.js`
- `ui-prototype/styles.css`
- `ui-prototype/i18n.js`
- `src/vitamin/server.py`
- `examples/review_demo/`
- `tests/result_dashboard_smoke.mjs`
- `tests/review_flow_smoke.mjs`

## 실행

```powershell
$env:PYTHONPATH = "src"
.\.venv\Scripts\python.exe -m vitamin.server
```

브라우저에서 `http://127.0.0.1:8000`을 열고 `예시 문서로 체험`으로 OCR 검수 화면과 결과 화면을 확인한다. 실제 PDF OCR은 README의 OCR 환경 설치 안내를 따른다.

## 검증 결과

- JavaScript syntax PASS
- 결과 대시보드 smoke PASS
- 문서 검수 flow mock/live smoke PASS
- Python syntax PASS
- Python pipeline unittest 5/5 PASS
- `/`, `/api/demo`, 데모 이미지 4종, 실제 OCR review image 응답 PASS

## 팀원 확인 항목

1. 문서별 이전/다음 이동과 확인 완료 제한이 의도대로 동작하는지
2. 오른쪽 field 번호를 눌렀을 때 왼쪽의 올바른 bbox 하나만 표시되는지
3. 급여 거래 선택 후 R00~R11 결과 화면으로 정상 이동하는지
4. `OPENAI_API_KEY` 설정 환경에서 쉬운 설명이 각 규칙 카드에 유지되는지
