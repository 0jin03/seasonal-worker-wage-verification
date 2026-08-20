"""Minimal PP-StructureV3 parser for the two validated payslip templates."""

import re

from src.normalization import clean_text, dotted_dates, key, money
from src.ocr_raw_adapter import line_provenance, pages, tables


HOUR_FIELDS = {
    "기본근로시간": "ps_paid_regular_hours",
    "연장근로시간": "ps_paid_overtime_hours",
    "야간근로시간": "ps_paid_night_hours",
    "휴일근로시간": "ps_paid_holiday_hours",
    "주휴시간": "ps_weekly_holiday_hours",
    "출근일수": "ps_paid_work_days",
    "통상시급": "ps_ordinary_hourly_wage",
}
PAY_FIELDS = {
    "기본급": "ps_base_pay",
    "주휴수당": "ps_weekly_allowance",
    "연장근로수당": "ps_overtime_pay",
    "야간근로수당": "ps_night_work_pay",
    "휴일근로수당": "ps_holiday_work_pay",
    "상여금": "ps_bonus_amount",
    "기타수당": "ps_other_allowance",
    "식대비과세": "ps_other_allowance",
}
DEDUCTION_FIELDS = {
    "소득세": "ps_income_tax",
    "근로소득세": "ps_income_tax",
    "국민연금": "ps_national_pension",
    "건강보험": "ps_health_insurance",
    "고용보험": "ps_employment_insurance",
    "식비": "ps_meal_deduction",
    "장기요양보험료": "ps_long_term_care_insurance",
    "장기요양보험": "ps_long_term_care_insurance",
    "지방소득세": "ps_local_income_tax",
    "숙박비": "ps_housing_deduction",
    "기타공제": "ps_other_deduction",
}
TOTAL_FIELDS = {
    "지급액계": "ps_gross_pay",
    "공제액계": "ps_total_deduction",
    "실지급액": "ps_net_pay",
    "실수령액": "ps_net_pay",
}


def _center(line):
    box = line["bbox"]
    return ((box[0] + box[2]) / 2, (box[1] + box[3]) / 2)


def _table(page, anchors):
    wanted = {key(anchor) for anchor in anchors}
    candidates = []
    for table in tables(page):
        present = {key(line["raw_text"]) for line in table["ocr_lines"]}
        score = len(wanted & present)
        if score:
            candidates.append((score, -len(table["ocr_lines"]), table))
    return max(candidates, key=lambda item: item[:2])[2] if candidates else None


def _label_value(lines, label):
    for anchor in (line for line in lines if key(line["raw_text"]) == key(label)):
        ax, ay = _center(anchor)
        candidates = [
            line for line in lines
            if line is not anchor and _center(line)[0] > ax and abs(_center(line)[1] - ay) <= 14
        ]
        if candidates:
            return min(candidates, key=lambda line: _center(line)[0])
    return None


def _rows(lines, tolerance=14):
    grouped = []
    for line in sorted(lines, key=lambda item: (_center(item)[1], _center(item)[0])):
        y = _center(line)[1]
        if not grouped or abs(y - grouped[-1][0]) > tolerance:
            grouped.append([y, [line]])
        else:
            grouped[-1][1].append(line)
            grouped[-1][0] = sum(_center(item)[1] for item in grouped[-1][1]) / len(grouped[-1][1])
    return [sorted(row, key=lambda item: _center(item)[0]) for _, row in grouped]


def _number(text):
    match = re.search(r"-?[\d,]+(?:[.]\d+)?", text or "")
    if not match:
        return None
    value = match.group().replace(",", "")
    return float(value) if "." in value else int(value)


def _set(result, debug, warnings, field, value, line, method):
    if result[field] is not None:
        result[field] = None
        debug.pop(field, None)
        warnings.append({
            "field": field, "code": "multiple_source_cells",
            "message": "multiple source cells map to one canonical field; no value was guessed",
        })
        return
    result[field] = value
    debug[field] = line_provenance(line)
    debug[field]["method"] = method


def _metadata(page, result, debug, warnings):
    table = _table(page, ("성명", "지급일", "사업장", "임금계산기간", "급여제도"))
    if not table:
        return
    lines = table["ocr_lines"]
    for label, field in (("성명", "ps_employee_name"), ("사업장", "ps_employer_name")):
        line = _label_value(lines, label)
        if line:
            _set(result, debug, warnings, field, clean_text(line["raw_text"]), line, "table_semantic_label_bbox")
    payment = _label_value(lines, "지급일")
    payment_dates = dotted_dates(payment["raw_text"] if payment else None)
    if len(payment_dates) == 1:
        _set(result, debug, warnings, "ps_payment_date", payment_dates[0], payment, "table_semantic_date_bbox")
    period = _label_value(lines, "임금계산기간")
    period_dates = dotted_dates(period["raw_text"] if period else None)
    if len(period_dates) == 2:
        for field, value in zip(("ps_pay_period_start", "ps_pay_period_end"), period_dates):
            _set(result, debug, warnings, field, value, period, "table_semantic_date_bbox")
    wage = _label_value(lines, "급여제도")
    wage_type = {"시급제": "시급", "월급제": "월급", "일급제": "일급"}.get(key(wage["raw_text"]) if wage else None)
    if wage_type:
        _set(result, debug, warnings, "ps_wage_type", wage_type, wage, "table_semantic_enum_bbox")


def _hours(page, result, debug, warnings):
    table = _table(page, HOUR_FIELDS)
    if not table:
        return
    lines = table["ocr_lines"]
    for label, field in HOUR_FIELDS.items():
        header = next((line for line in lines if key(line["raw_text"]) == key(label)), None)
        if not header:
            continue
        hx, hy = _center(header)
        candidates = [line for line in lines if _center(line)[1] > hy and _center(line)[1] - hy < 75]
        if not candidates:
            continue
        line = min(candidates, key=lambda item: (abs(_center(item)[0] - hx), _center(item)[1] - hy))
        value = _number(line["raw_text"])
        if field == "ps_paid_work_days" and isinstance(value, float) and value.is_integer():
            value = int(value)
        if value is not None:
            _set(result, debug, warnings, field, value, line, "table_semantic_header_bbox")


def _payment_and_deductions(page, result, debug, warnings):
    table = _table(page, ("임금항목", "지급금액(원)", "공제항목", "공제금액(원)"))
    if not table:
        return
    lines = table["ocr_lines"]
    headers = {
        name: next((line for line in lines if key(line["raw_text"]) == key(name)), None)
        for name in ("임금항목", "지급금액(원)", "공제항목", "공제금액(원)")
    }
    if any(line is None for line in headers.values()):
        return
    header_y = sum(_center(line)[1] for line in headers.values()) / 4
    x = {name: _center(line)[0] for name, line in headers.items()}
    pay_lines, pay_debug = [], []
    for row in _rows([line for line in lines if _center(line)[1] > header_y + 12]):
        for label_line in row:
            field = TOTAL_FIELDS.get(key(label_line["raw_text"]))
            amounts = [line for line in row if _center(line)[0] > _center(label_line)[0] and money(line["raw_text"]) is not None]
            if field and amounts:
                amount_line = min(amounts, key=lambda line: _center(line)[0])
                _set(result, debug, warnings, field, money(amount_line["raw_text"]), amount_line, "table_semantic_total_row_bbox")

        cells = {}
        for line in row:
            column = min(x, key=lambda name: abs(_center(line)[0] - x[name]))
            cells.setdefault(column, line)

        pay_label, pay_amount = cells.get("임금항목"), cells.get("지급금액(원)")
        pay_key = key(pay_label["raw_text"]) if pay_label else None
        if pay_label and pay_amount and pay_key not in TOTAL_FIELDS:
            amount = money(pay_amount["raw_text"])
            if amount is not None:
                canonical = PAY_FIELDS.get(pay_key)
                if pay_key and pay_key.startswith("주휴수당"):
                    canonical = "ps_weekly_allowance"
                item = {"item_name": clean_text(pay_label["raw_text"]), "amount": amount, "mapped_to": canonical}
                pay_lines.append(item)
                label_source = line_provenance(pay_label)
                amount_source = line_provenance(pay_amount)
                label_source["method"] = amount_source["method"] = "table_semantic_pay_row_bbox"
                pay_debug.append({"item_name": label_source, "amount": amount_source, "mapped_to": label_source})
                if canonical:
                    _set(result, debug, warnings, canonical, amount, pay_amount, "table_semantic_pay_row_bbox")

        for label_line, amount_line, aliases in (
            (cells.get("공제항목"), cells.get("공제금액(원)"), DEDUCTION_FIELDS),
        ):
            field = aliases.get(key(label_line["raw_text"])) if label_line else None
            amount = money(amount_line["raw_text"]) if amount_line else None
            if field and amount is not None:
                _set(result, debug, warnings, field, amount, amount_line, "table_semantic_amount_bbox")

    result["ps_pay_lines"] = pay_lines
    debug["ps_pay_lines"] = {
        "page": table["page"], "bbox": headers["임금항목"]["bbox"], "roi": None,
        "raw_text": headers["임금항목"]["raw_text"], "method": "table_semantic_pay_rows",
        "score": headers["임금항목"]["score"], "warning": None, "rows": pay_debug,
    }


def _calculation(page, result, debug, warnings):
    table = _table(page, ("계산 방법", "구분", "산출식 또는 산출방법", "지급액(원)"))
    if not table:
        return
    lines = table["ocr_lines"]
    headers = [
        next((line for line in lines if key(line["raw_text"]) == key(name)), None)
        for name in ("구분", "산출식 또는 산출방법", "지급액(원)")
    ]
    if any(line is None for line in headers):
        return
    base = next((line for line in lines if key(line["raw_text"]) == "기본급" and _center(line)[1] > _center(headers[0])[1]), None)
    if not base:
        return
    row = [line for line in lines if abs(_center(line)[1] - _center(base)[1]) <= 14]
    cells = {}
    for line in row:
        column = min(range(3), key=lambda index: abs(_center(line)[0] - _center(headers[index])[0]))
        cells.setdefault(column, line)
    formula, amount = cells.get(1), cells.get(2)
    _set(result, debug, warnings, "ps_calculation_item", clean_text(base["raw_text"]), base, "table_semantic_calculation_bbox")
    if formula:
        _set(result, debug, warnings, "ps_calculation_formula", clean_text(formula["raw_text"]), formula, "table_semantic_calculation_bbox")
    if amount and money(amount["raw_text"]) is not None:
        _set(result, debug, warnings, "ps_calculated_amount", money(amount["raw_text"]), amount, "table_semantic_calculation_bbox")


def parse_payslip(raw, field_names):
    result = {name: None for name in field_names}
    debug, warnings = {}, []
    for page in pages(raw):
        _metadata(page, result, debug, warnings)
        _hours(page, result, debug, warnings)
        _payment_and_deductions(page, result, debug, warnings)
        _calculation(page, result, debug, warnings)
    for field, value in result.items():
        if value is None:
            warnings.append({
                "field": field, "code": "source_not_resolved",
                "message": "payslip field could not be resolved without guessing",
            })
    return result, debug, warnings
