# OCR 검증 기준선

## 범위

이 수치는 2026-08-19에 고정된 v4.1 regression split 36건, PDF 144개에서 측정한 기준선입니다. v6의 문서 field 구조는 v4.1과 동일하지만, 이 결과를 v6 전체 정확도나 실제 문서 정확도로 확대 해석하지 않습니다.

실행 환경:

```text
Python 3.11.9
paddlepaddle-gpu 3.3.0
PaddleOCR 3.7.0
PaddleX 3.7.2
RTX 3070 / gpu:0
korean_PP-OCRv5_mobile_rec
```

실행 결과:

- 36/36 case 완료
- OCR 144/144 PDF 성공
- parser 144/144 document 성공
- OCR 소유 `documents` Schema validation 36/36 통과
- holdout 미사용

## 문서별 non-null field 기준선

| 문서 | 일치/평가 가능 | 기준선 |
|---|---:|---:|
| contract | 1,062 / 1,067 | 99.53% |
| timesheet | 3,959 / 3,964 | 99.87% |
| payslip | 1,758 / 1,764 | 99.66% |
| bank_statement | 278 / 288 | 96.53% |

Null correctness는 contract 108/108, timesheet 758/758이었습니다. 서로 의미가 다른 문서·행·null 지표를 하나의 전체 정확도로 합산하지 않았습니다.

## 반복행 기준선

| 문서 | GT/예측/매칭 행 | recall | precision |
|---|---|---:|---:|
| timesheet | 771 / 769 / 769 | 99.74% | 100% |
| payslip | 252 / 252 / 252 | 100% | 100% |
| bank_statement | 37 / 42 / 36 | 97.30% | 85.71% |

## 알려진 문제

- 은행 거래행 중복: V4P056, V4P064, V4P068, V4P084, V4P106, V4P133
- 은행 거래행 누락: V4P096
- 근무기록 행 누락: V4P161, V4P178
- 근무기록 특이사항 손실: V4P146의 4개 cell
- 근로자 확인 체크박스 미판정: V4P125
- 주급 지급 문구 parser gap: V4P172
- 계약서 인접 cell anchor 오류: V4P178
- 이름·계산식 OCR 문자/공백 오류 및 날짜 구두점 normalization 오류가 일부 존재

GT 제외 300건과 REVIEW_REQUIRED 1건은 정확도 분모에 넣지 않았습니다. Legacy GT로 OCR 결과를 보정하지 않았습니다.
