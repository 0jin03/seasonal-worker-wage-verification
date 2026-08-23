from __future__ import annotations

from .models import CaseBundle, EvaluationReport
from .rules import RuleEngine
from .v6 import build_v6_result


CRITICAL_REVIEW_FIELDS = {
    "contract": {"ct_employee_name", "ct_new_or_reentry_start_date", "ct_new_or_reentry_end_date", "ct_pay_day"},
    "timesheet": {"ts_employee_name"},
    "payslip": {"ps_employee_name", "ps_pay_period_start", "ps_pay_period_end", "ps_gross_pay", "ps_total_deduction"},
}


class VitaminPipeline:
    def __init__(self, engine: RuleEngine | None = None, require_review: bool = True) -> None:
        self.engine = engine or RuleEngine()
        self.require_review = require_review

    def run(self, case: CaseBundle) -> EvaluationReport:
        pending = []
        if self.require_review:
            for doc_name, fields in CRITICAL_REVIEW_FIELDS.items():
                document = getattr(case, doc_name)
                for name in fields:
                    item = document.fields.get(name)
                    if item and not item.confirmed:
                        pending.append({"document": doc_name, "field": name, "value": item.value, "confidence": item.confidence})
        if pending:
            return EvaluationReport(case.case_id, {}, [], pending)
        derived, rules = self.engine.evaluate(case)
        result = build_v6_result(case.canonical_documents, derived, rules)
        return EvaluationReport(case.case_id, derived, rules, v6_result=result)
