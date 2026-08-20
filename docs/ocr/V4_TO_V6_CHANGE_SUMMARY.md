# 표준피처 정의서·JSON Schema v4 → v6 셀 변경사항

이 문서는 **값이 바뀐 셀과 추가된 셀/행만** 빠르게 확인하기 위한 전달용 요약이다. v6는 v4.1을 기반으로 만들었고 v4/v4.1 원본은 수정하지 않았다.

## 1. v4 → v4.1에서 반영된 변경

| 시트 / 셀·행 | v4 | v6에 유지된 값 |
|---|---|---|
| `01_전체_피처사전!I96` | `YYYY-MM-DD 날짜 포맷 외 일수(1~31), '말일'/'LAST_DAY' 등 키워드 표현 수용` | `canonical: null, 정수 1~31, LAST_DAY 또는 유효한 YYYY-MM-DD. '말일' 등 원문 표현은 parser에서 정규화하고 provenance에 보존` |
| `01_전체_피처사전!I97` | `YYYY-MM-DD 날짜 포맷 외 일수(1~31), '매월 1일' 등 키워드 표현 수용` | `canonical: null, 정수 1~31 또는 유효한 YYYY-MM-DD. 원문 표현은 parser에서 정규화하고 provenance에 보존` |
| `02_규칙별_피처!H43` | `단순 날짜 외 반복기간 키워드(매월 1일, 말일 등) 허용` | `canonical: null, 정수 1~31, LAST_DAY 또는 유효한 YYYY-MM-DD. '말일' 등 원문 표현은 parser에서 정규화하고 provenance에 보존` |
| `02_규칙별_피처!H44` | `단순 날짜 외 반복기간 키워드(매월 1일, 말일 등) 허용` | `canonical: null, 정수 1~31 또는 유효한 YYYY-MM-DD. 원문 표현은 parser에서 정규화하고 provenance에 보존` |
| `07_문서별_원본피처!F24` | `단순 날짜 외 반복기간 키워드(매월 1일, 말일 등) 허용` | `canonical: null, 정수 1~31, LAST_DAY 또는 유효한 YYYY-MM-DD. '말일' 등 원문 표현은 parser에서 정규화하고 provenance에 보존` |
| `07_문서별_원본피처!F25` | `단순 날짜 외 반복기간 키워드(매월 1일, 말일 등) 허용` | `canonical: null, 정수 1~31 또는 유효한 YYYY-MM-DD. 원문 표현은 parser에서 정규화하고 provenance에 보존` |
| `06_검토사항!A9:D9` | `R00 생년월일` 보조 보관 | 행 삭제; 생년월일 미수집 |

## 2. 팀원 v5 수정 11개 셀 — 문구 그대로 반영

`02_규칙별_피처`는 v6에서 R02 허용오차 2행을 추가해 원래 107행 이후 주소가 2행 내려갔다.

| # | v4/v4.1 셀 | v6 셀 | v4 값 | v6 값 |
|---:|---|---|---|---|
| 1 | `01_전체_피처사전!H158` | 동일 | `PASS / MISMATCH / REVIEW / NOT_EVALUABLE` | `PASS / MISMATCH / REVIEW / NOT_CHECKABLE` |
| 2 | `01_전체_피처사전!H160` | 동일 | `PASS / MISMATCH / REVIEW / NOT_EVALUABLE` | `PASS / MISMATCH / REVIEW / NOT_CHECKABLE` |
| 3 | `01_전체_피처사전!H188` | 동일 | `입력 날짜 수 ÷ 계산기간 일수` | `근무기록 일수 ÷ 소정근로일수` |
| 4 | `01_전체_피처사전!I188` | 동일 | `임계값 미만이면 NOT_EVALUABLE` | `임계값 미만이면 NOT_CHECKABLE` |
| 5 | `01_전체_피처사전!I193` | 동일 | `false면 NOT_EVALUABLE` | `false면 NOT_CHECKABLE` |
| 6 | `02_규칙별_피처!H89` | 동일 | `false면 NOT_EVALUABLE` | `false면 NOT_CHECKABLE` |
| 7 | `02_규칙별_피처!G101` | 동일 | `입력 날짜 수 ÷ 계산기간 일수` | `근무기록 일수 ÷ 소정근로일수` |
| 8 | `02_규칙별_피처!H101` | 동일 | `임계값 미만이면 NOT_EVALUABLE` | `임계값 미만이면 NOT_CHECKABLE` |
| 9 | `02_규칙별_피처!G108` | `G110` | `PASS / MISMATCH / REVIEW / NOT_EVALUABLE` | `PASS / MISMATCH / REVIEW / NOT_CHECKABLE` |
| 10 | `02_규칙별_피처!G146` | `G148` | `PASS / MISMATCH / REVIEW / NOT_EVALUABLE` | `PASS / MISMATCH / REVIEW / NOT_CHECKABLE` |
| 11 | `07_문서별_원본피처!F41` | 동일 | `false면 NOT_EVALUABLE` | `false면 NOT_CHECKABLE` |

## 3. 허용오차 관련 기존 셀 변경

| 시트 / v6 셀 | field | v6 값·산식 |
|---|---|---|
| `01_전체_피처사전!H50:I50`, `02_규칙별_피처!G106:H106` | `cmp_tolerance_hours` | `clamp(근무일수×0.083, 0.5, ps_actual_hours_equiv×0.03)` |
| `01_전체_피처사전!H51:I51`, `02_규칙별_피처!G146:H146` | `cmp_tolerance_won` | 정액형 `10원`, 단가형 `10 + 3×해당 항목 시간수` |
| `01_전체_피처사전!H112:I112`, `02_규칙별_피처!G177:H177` | `param_gross_tolerance` | `0원` |
| `01_전체_피처사전!H113:I113`, `02_규칙별_피처!G278:H278` | `param_hours_tolerance` | 별도 수치 미적용, JSON 값 `null` |
| `01_전체_피처사전!H114:I114`, `02_규칙별_피처!G65:H65` | `param_wage_tolerance` | 환산 비교 `±10원`; 동일 임금형태 직접 비교 `0원` |

## 4. 새로 추가된 4개 피처

| 전체 사전 셀 | 규칙별 피처 셀 | field | 산식 |
|---|---|---|---|
| `01_전체_피처사전!A199:I199` | `02_규칙별_피처!A107:H107` | `cmp_tolerance_overtime_hours` | `max(0.5, 연장발생일수 × 0.083)` |
| `01_전체_피처사전!A200:I200` | `02_규칙별_피처!A108:H108` | `cmp_tolerance_work_days` | `0` |
| `01_전체_피처사전!A201:I201` | `02_규칙별_피처!A196:H196` | `cmp_tolerance_deduction_won` | `60 + (2 × ps_actual_hours_equiv)` |
| `01_전체_피처사전!A202:I202` | `02_규칙별_피처!A218:H218` | `cmp_tolerance_net_pay_won` | `70 + (5 × ps_actual_hours_equiv)` |

표준피처 수는 `194 → 198`이다.

## 5. 요약·검토 시트 변경

| 시트 / 셀 | 변경 |
|---|---|
| `00_한눈에보기!A39:E56` | R00~R11 허용오차·예외처리 표 추가 |
| `05_최종피처_판정!C6`, `F4:F15` | 새 비교 피처, 사용자 확정값, 규칙별 허용오차·예외처리 반영 |
| `06_검토사항!B4:D4` | 판정 불가 상태를 `NOT_CHECKABLE`로 확정 |
| `06_검토사항!B6:D6` | 허용오차 정책 확정 및 한눈에보기 표 참조 |
| `06_검토사항!B8:D9` | R09 공휴일 별도 예외, R10 월 수치 허용오차 미적용으로 갱신 |
| `01_전체_피처사전!I174`, `02_규칙별_피처!H280` | R10 판정 설명 동기화 |

## 6. R05 null 문구 후속 최소 수정

| 위치 | 기존 문구 | 수정 문구 |
|---|---|---|
| `01_전체_피처사전!I22` | `null은 0으로 전처리` | `OCR null은 0으로 대체하지 않음. 사용자 확인 후 0원으로 확정된 경우에만 0으로 합산` |
| `02_규칙별_피처!H175` | `null은 0으로 전처리` | 위와 동일 |
| `04_이름변경_매핑!F75` | `null은 0으로 전처리` | 위와 동일 |
| `06_검토사항!B5:D5` | R05 null 처리 미확정 | 사용자 검토·룰베이스 처리로 방향 확정 |
| Schema `properties.derived.properties.R05.properties.calc_gross_pay.x-note` | `null은 0으로 전처리` | 위와 동일 |
| Schema `x-open-issues` | `R05 null 처리` 포함 | 처리 방향이 확정되어 해당 항목 제거 |

이 변경은 설명 문구만 명확히 한 것이며 field, type, required, 허용오차 및 룰 판정 구조는 변경하지 않았다.

## 7. JSON Schema v4 → v6 변경 경로

| JSON path | 변경 |
|---|---|
| `title`, `description`, `x-source-of-truth`, `x-standard-version` | v6로 갱신 |
| `properties.documents...ps_pay_lines.items.description`, `properties.derived...calc_cumulative_salary_deposit.items.description` | 내부 기준 버전 표기 `v4.1 → v6` |
| `x-standard-feature-count` | `194 → 198` |
| `properties.documents.properties.timesheet.properties.ts_record_available.x-note` | `false면 NOT_CHECKABLE` |
| `properties.derived.properties.R02.properties.ts_period_coverage` | 팀원 v5 계산식·상태 문구 그대로 반영 |
| `properties.derived.properties.R02.properties` / `required` | R02 허용오차 2개 추가 |
| `properties.derived.properties.R06.properties` / `required` | `cmp_tolerance_deduction_won` 추가 |
| `properties.derived.properties.R07.properties` / `required` | `cmp_tolerance_net_pay_won` 추가 |
| `properties.derived.properties.R01/R02/R03/R05/R10` | 승인된 허용오차 method/note 반영 |
| `properties.rule_results.properties.R02/R03` | `NOT_EVALUABLE → NOT_CHECKABLE` |
| `x-open-issues` | 해결된 상태값·허용오차·R10 항목 제거; 미해결 3종만 유지 |

## 8. 자동 검증 결과

- XLSX 고유 field: **198개**
- Schema 고유 field: **198개**
- XLSX/Schema field 집합: **일치**
- `NOT_EVALUABLE` 잔존: **0건**
- JSON parsing: **PASS**
- JSON Schema 메타 검증: **PASS (stdlib 구조 검증; jsonschema 미설치)**
- v4/v4.1 원본 SHA-256 보존: **True**
