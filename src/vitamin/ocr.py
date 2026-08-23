from __future__ import annotations

from typing import Any, Protocol

from .models import DocumentData, OcrValue, ReviewState


class OcrAdapter(Protocol):
    """문서 파일을 표준 필드로 변환하는 OCR 어댑터 계약."""

    def extract(self, source: str, document_type: str) -> DocumentData: ...


class JsonOcrAdapter:
    """OCR 팀 parser가 만든 JSON을 파이프라인 입력으로 바꾸는 기본 어댑터."""

    def from_dict(
        self,
        payload: dict[str, Any],
        document_type: str,
        *,
        row_key: str | None = None,
        canonical: bool = False,
    ) -> DocumentData:
        metadata = payload.get("_ocr", {})
        confidences = metadata.get("confidence", {})
        raw_text = metadata.get("raw_text", {})
        confirmed = set(metadata.get("confirmed_fields", []))
        corrected = set(metadata.get("corrected_fields", []))

        row_keys = {"rows", "lines", "transactions"}
        fields: dict[str, OcrValue] = {}
        for name, value in payload.get("fields", payload).items():
            if name.startswith("_") or name in row_keys:
                continue
            state = ReviewState.CONFIRMED if canonical else ReviewState.PENDING
            if name in confirmed:
                state = ReviewState.CONFIRMED
            if name in corrected:
                state = ReviewState.CORRECTED
            fields[name] = OcrValue(value, confidences.get(name), raw_text.get(name), state)

        rows = []
        source_rows = payload.get(row_key or "rows", payload.get("rows", []))
        for row in source_rows:
            converted = {
                name: OcrValue(value, review_state=ReviewState.CONFIRMED)
                for name, value in row.items()
            }
            # 합성데이터에는 사용자 선택 UI가 없으므로 포함된 거래를 확정 거래로 취급한다.
            rows.append(converted)
        return DocumentData(document_type, fields, rows, payload.get("_source_id"))


def apply_user_review(document: DocumentData, corrections: dict[str, Any]) -> None:
    """UI에서 확정하거나 수정한 값을 canonical 값으로 반영한다."""
    for name, value in corrections.items():
        if name not in document.fields:
            document.fields[name] = OcrValue(value=value, review_state=ReviewState.CORRECTED)
            continue
        item = document.fields[name]
        if value == item.value:
            item.review_state = ReviewState.CONFIRMED
        else:
            item.value = value
            item.review_state = ReviewState.CORRECTED
