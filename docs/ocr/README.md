# OCR 모듈 v6

## 역할

PP-StructureV3로 다음 네 PDF를 OCR하고, 표준피처정의서/JSON Schema v6의 `documents` 구조로 변환합니다.

- `contract`: 표준근로계약서
- `timesheet`: 근무기록부
- `payslip`: 임금명세서
- `bank_statement`: 입금내역서

인식 모델은 `korean_PP-OCRv5_mobile_rec`입니다. OCR 입력은 PDF뿐이며 legacy 정답 JSON이나 PDF text layer를 읽어 값을 보정하지 않습니다.

## 설치

Python 3.11 가상환경에서 일반 의존성을 설치합니다.

```powershell
python -m pip install -r requirements-ocr.txt
```

CPU로 실행할 PC는 PaddlePaddle CPU 3.3.0도 설치합니다.

```powershell
python -m pip install paddlepaddle==3.3.0
```

GPU Paddle 설치는 환경별 wheel을 확인해야 합니다. 이 프로젝트에서 검증한 Windows/RTX 3070 환경은 [INSTALL_WINDOWS_GPU.md](INSTALL_WINDOWS_GPU.md)를 따릅니다.

## 실행

정규화된 dataset manifest를 명시적으로 전달합니다. manifest의 각 문서는 repository 기준 상대경로, SHA-256, `ocr_input=true`를 가져야 합니다.

```powershell
python scripts/run_ocr.py `
  --manifest path/to/dataset_manifest.json `
  --sample-id V4P001 `
  --device gpu:0
```

split 실행도 지원합니다.

```powershell
python scripts/run_ocr.py `
  --manifest path/to/dataset_manifest.json `
  --split regression `
  --device gpu:0
```

`holdout`은 실수로 열지 않도록 `--allow-holdout`을 추가해야만 실행됩니다. 기존 결과와 입력/설정 hash가 같으면 재사용하고, 다르면 `--force` 없이 덮어쓰지 않습니다.

## 출력

```text
outputs/ocr/<sample_id>/
├─ raw/<role>/raw_result.json
├─ paddle_viz/<role>/...
├─ parsed/canonical.json
├─ parsed/provenance.json
└─ logs/run_*.json
```

- `canonical.json`: 다른 모듈이 사용하는 고정 인터페이스
- `provenance.json`: field별 raw text, bbox/ROI, parser warning을 확인하는 검수 정보
- `raw/`, `paddle_viz/`: OCR 품질 조사용 근거

OCR 모듈은 최종 Schema 중 `documents` fragment만 생성합니다. `derived`와 `rule_results`는 사용자 확인 및 룰베이스 단계에서 병합한 뒤 최종 전체 Schema를 검증해야 합니다.

## Python 통합 경계

팀 코드에서는 `src.ocr_pipeline.OCRPipeline`을 한 번 초기화하여 여러 sample에 재사용하고 `process_sample()`을 호출합니다. `documents` 인자는 역할별로 다음 값을 전달합니다.

```python
documents = {
    "contract": {
        "path": Path("실제 PDF 경로"),
        "source_path": "저장할 상대경로 표시값",
        "sha256": "PDF SHA-256",
    },
    # timesheet, payslip, bank_statement도 같은 구조
}
```

다른 팀 코드는 parser 내부 함수나 raw Paddle key에 의존하지 말고 `canonical.json`의 `documents` 구조만 사용해야 합니다.

## 현재 검토가 필요한 한계

- 은행 거래표에서 OCR table grouping에 따라 중복행 또는 누락행이 생길 수 있습니다.
- 일부 이름·문구의 OCR 철자 및 공백 오류가 남아 있습니다.
- 체크박스는 OCR 문자가 아니라 고정 양식 ROI/ink-density로 판정하므로 새로운 양식은 검토가 필요합니다.
- 알 수 없는 값은 `0`으로 만들지 않고 `null`과 warning으로 보존합니다.
- v6 허용오차와 R00~R11 판정은 parser가 아니라 downstream rule 단계에서 적용합니다.

검증 수치와 구체 사례는 [VALIDATION_BASELINE.md](VALIDATION_BASELINE.md), 표준 변경사항은 [V4_TO_V6_CHANGE_SUMMARY.md](V4_TO_V6_CHANGE_SUMMARY.md)를 참고하세요.
