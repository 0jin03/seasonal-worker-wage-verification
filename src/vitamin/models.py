from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import date, datetime
from decimal import Decimal
from enum import StrEnum
from typing import Any


class ReviewState(StrEnum):
    PENDING = "PENDING"
    CONFIRMED = "CONFIRMED"
    CORRECTED = "CORRECTED"


class RuleStatus(StrEnum):
    PASS = "PASS"
    MISMATCH = "MISMATCH"
    REVIEW = "REVIEW"
    REVIEW_HIGH = "REVIEW_HIGH"
    NOT_CHECKABLE = "NOT_CHECKABLE"
    NOT_EVALUABLE = "NOT_EVALUABLE"


@dataclass(slots=True)
class OcrValue:
    value: Any = None
    confidence: float | None = None
    raw_text: str | None = None
    review_state: ReviewState = ReviewState.PENDING

    @property
    def confirmed(self) -> bool:
        return self.review_state in {ReviewState.CONFIRMED, ReviewState.CORRECTED}


@dataclass(slots=True)
class DocumentData:
    document_type: str
    fields: dict[str, OcrValue] = field(default_factory=dict)
    rows: list[dict[str, OcrValue]] = field(default_factory=list)
    source_id: str | None = None

    def value(self, name: str, default: Any = None) -> Any:
        item = self.fields.get(name)
        return default if item is None or item.value is None else item.value


@dataclass(slots=True)
class CaseBundle:
    contract: DocumentData
    timesheet: DocumentData
    payslip: DocumentData
    bank: DocumentData
    case_id: str | None = None
    canonical_documents: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class RuleResult:
    rule_id: str
    status: RuleStatus
    reason: str
    comparisons: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class EvaluationReport:
    case_id: str | None
    derived: dict[str, Any]
    rules: list[RuleResult]
    review_required: list[dict[str, Any]] = field(default_factory=list)
    v6_result: dict[str, Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        def convert(value: Any) -> Any:
            if isinstance(value, (date, datetime)):
                return value.isoformat()
            if isinstance(value, StrEnum):
                return str(value)
            if isinstance(value, Decimal):
                return int(value) if value == value.to_integral_value() else float(value)
            if isinstance(value, dict):
                return {k: convert(v) for k, v in value.items()}
            if isinstance(value, (list, tuple)):
                return [convert(v) for v in value]
            return value

        value = convert(asdict(self))
        if self.v6_result is not None:
            value["result"] = convert(self.v6_result)
        return value
