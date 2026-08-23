from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .models import CaseBundle, OcrValue, ReviewState
from .ocr import JsonOcrAdapter


def case_from_payload(payload: dict[str, Any], case_id: str | None = None) -> CaseBundle:
    """사용자 확인이 끝난 v6 JSON 또는 OCR ``documents`` 조각을 불러온다."""
    if "documents" not in payload:
        payload = {"documents": payload}
    adapter = JsonOcrAdapter()
    docs = payload["documents"]
    required_documents = {"contract", "timesheet", "payslip", "bank_statement"}
    missing = sorted(required_documents - set(docs))
    if missing:
        raise ValueError(f"v6 표준 JSON 필수 문서가 없습니다: {', '.join(missing)}")
    bank = adapter.from_dict(
        docs["bank_statement"],
        "bank",
        row_key="transactions",
        canonical=True,
    )
    # v6 스키마: 사용자 최종 선택은 거래 배열과 1:1 대응하는 derived.R08 배열이다.
    selections = payload.get("derived", {}).get("R08", {}).get("usr_salary_transaction_selected")
    if isinstance(selections, list):
        for index, row in enumerate(bank.rows):
            selected = selections[index] if index < len(selections) else None
            row["usr_salary_transaction_selected"] = OcrValue(
                value=selected,
                review_state=ReviewState.CONFIRMED,
            )
    return CaseBundle(
        contract=adapter.from_dict(docs["contract"], "contract", canonical=True),
        timesheet=adapter.from_dict(
            docs["timesheet"],
            "timesheet",
            row_key="lines",
            canonical=True,
        ),
        payslip=adapter.from_dict(docs["payslip"], "payslip", canonical=True),
        bank=bank,
        case_id=case_id or payload.get("case_id"),
        canonical_documents=docs,
    )


def load_case(path: str | Path) -> CaseBundle:
    path = Path(path)
    payload = json.loads(path.read_text(encoding="utf-8"))
    return case_from_payload(payload, payload.get("case_id", path.stem))


def write_json(path: str | Path, data: dict[str, Any]) -> None:
    Path(path).write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
