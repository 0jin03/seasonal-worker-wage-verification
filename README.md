# 외국인 계절근로자 임금 검증 프로젝트

표준근로계약서, 근무기록부, 임금명세서, 입금내역서를 OCR로 구조화하고 R00~R11 검증 규칙에 연결하는 프로젝트입니다.

## 구성

- `src/`, `scripts/run_ocr.py`: PP-StructureV3 기반 OCR 및 4종 문서 parser
- `references/`: 최종 표준피처정의서와 JSON Schema v6
- `docs/ocr/`: OCR 설치, 실행, 검증 결과, v4→v6 변경사항
- `examples/`: canonical JSON과 provenance 예시
- `tests/`: 데이터셋 없이 실행 가능한 최소 회귀검사

OCR 모듈의 입력·출력 및 실행 방법은 [docs/ocr/README.md](docs/ocr/README.md)를 참고하세요.

## 브랜치

- `main`: 프로젝트 통합 코드와 문서
- `data`: 합성데이터
- `rag`: 법령 RAG 모듈

대용량 OCR raw 결과, Paddle 시각화, 가상환경 및 모델 캐시는 Git으로 관리하지 않습니다.
