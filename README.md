# Vitamin v6 OCR → R00~R11 → UI 파이프라인

4종 PDF를 OCR한 뒤 사용자가 값을 확인하고 급여 거래를 선택하면, v6 피처정의서의 재사용 흐름에 따라 R00~R11을 실행합니다.

```text
계약서 ─┐
근무기록 ├─ 문서별 OCR/parser ─ 사용자 확인·수정 ─ 표준 JSON ─ R00~R11 ─ 결과 JSON
명세서 ─┤
입금내역 ┘
```

## UI와 백엔드 실행

룰 테스트와 예시 UI는 Python 기본 기능만으로 실행됩니다. 실제 PDF OCR까지 사용할 때는 아래의 Python 3.11 가상환경을 사용합니다.

```powershell
cd "seasonal-worker-wage-verification"
$env:PYTHONPATH = "src"
.\.venv\Scripts\python.exe -m vitamin.server
```

브라우저에서 `http://127.0.0.1:8000`을 엽니다. `index.html`을 직접 더블클릭하면 API를 호출할 수 없으므로 반드시 서버 주소로 접속합니다.

## 실제 PDF OCR 준비

OCR은 GitHub `feature/ocr-v6` 모듈을 `ocr_module/`에 연결했습니다. PaddlePaddle 3.3.0의 공식 Windows wheel은 Python 3.13까지만 제공되므로, 이 프로젝트의 OCR 런타임은 검증된 Python 3.11을 사용합니다. 프로젝트 내부 가상환경을 새로 만드는 경우 다음과 같이 설치합니다.

```powershell
uv python install 3.11
uv venv --python 3.11 .venv
uv pip install --python .venv\Scripts\python.exe -r ocr_module\requirements-ocr.txt
$env:VITAMIN_OCR_DEVICE = "cpu"
```

`paddleocr[doc-parser]` extra는 `PPStructureV3`의 레이아웃·표 분석에 필요한 공식 선택 의존성을 함께 설치합니다. 최초 OCR 실행 시 공식 모델 파일을 내려받기 때문에 시간이 걸리며, 이후 실행은 로컬 모델 캐시를 재사용합니다.

GPU 설치는 `ocr_module`의 PaddleOCR 안내에 맞춰 별도로 설정합니다. OCR 결과와 provenance는 `outputs/ocr/<sample_id>/`에 저장됩니다.

## CLI 실행

외부 패키지 없이 Python 3.11 이상에서 실행할 수 있습니다.

```powershell
$env:PYTHONPATH = "src"
python -m vitamin.cli examples/case_pass.json -o report.json
```

CLI 결과의 `result`가 v6의 `documents`, `derived`, `rule_results` 구조입니다.

## OCR 팀과 연결하는 방법

문서별 parser는 v6 `documents`에 피처정의서의 접두어를 그대로 사용합니다.

- 계약서: `ct_*`
- 근무기록: `ts_*`, 반복 행은 `rows`
- 임금명세서: `ps_*`
- 입금내역: `bk_*`, 반복 거래는 `transactions`

`_ocr.confirmed_fields`에는 UI에서 사용자가 확인한 핵심 필드를 넣습니다. 수정된 값은 OCR 원본 대신 `fields`에 최종값을 넣고 `_ocr.corrected_fields`에 필드명을 기록합니다.

UI의 복수 선택 결과는 `derived.R08.usr_salary_transaction_selected[]`에 저장됩니다. R08·R09는 이 사용자 선택값만 사용합니다.

## 구현 범위와 확장 지점

- `ocr.py`: OCR 공급자별 어댑터 추가 위치
- `normalization.py`: 이름·날짜·금액·임금형태 정규화
- `pipeline.py`: 사용자 확인 게이트
- `rules.py`: R00~R11 및 파생피처 재사용
- `io.py`: 통합 OCR JSON 입출력

RAG는 룰 결과의 `rule_id`, `status`, `reason`, `comparisons`를 입력으로 받도록 후속 계층에서 연결하면 됩니다.

## R09 공휴일 API 설정

공공데이터포털의 한국천문연구원 특일 정보 API에서 **일반 인증키(Decoding)** 를 발급받아 프로젝트 루트의 `.env`에 넣습니다.

```dotenv
KASI_HOLIDAY_API_KEY=발급받은_일반_인증키_Decoding
```

약정 지급일이 주말·공휴일이면 **직전 영업일**을 정상 지급일로 사용합니다.

API 키 누락·통신 실패·응답 오류는 파이프라인을 중단하지 않고 R09 `REVIEW`로 반환합니다. 월별 API 응답은 실행 중 메모리에 캐시됩니다.
