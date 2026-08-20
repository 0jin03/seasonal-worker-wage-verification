import re

from src.normalization import clean_text, key, korean_dates, money, pay_period
from src.ocr_raw_adapter import ocr_lines, page_size, pages
from src.parsers.checkbox_parser import detect_group, render_first_page


def _texts(page, table_first=True):
    lines = ocr_lines(page, table_first=True)
    table = [(line["raw_text"], "table_ocr") for line in lines if line["table_index"] is not None]
    overall = [(line["raw_text"], "overall_ocr") for line in lines if line["table_index"] is None]
    return table + overall if table_first else overall


def _after(page, *labels):
    label_keys = {key(label) for label in labels}
    for source in ("table_ocr", "overall_ocr"):
        rows = [item for item in _texts(page) if item[1] == source]
        for index, (text, _) in enumerate(rows[:-1]):
            if key(text) in label_keys:
                return rows[index + 1][0], source
    return None, None


def _matching(page, pattern):
    for text, source in _texts(page):
        if re.search(pattern, key(text)):
            return text, source
    return None, None


def _payment_terms(text):
    normalized = key(text)
    timing = re.search(r"(당월|익월|당주|익주)", normalized)
    if not timing:
        return {}
    value = {"timing": timing.group(1), "cycle": "월" if "월" in timing.group(1) else "주"}
    if value["cycle"] == "월":
        day = re.search(r"(\d{1,2})일", normalized)
        if day and 1 <= int(day.group(1)) <= 31:
            value["day"] = int(day.group(1))
    else:
        weekday = re.search(r"([월화수목금토일])요일", normalized)
        if weekday:
            value["weekday"] = f"{weekday.group(1)}요일"
    return value


def _add_line_provenance(page, debug):
    lines = ocr_lines(page, table_first=True)
    for detail in debug.values():
        if detail.get("bbox") is not None or detail.get("roi") is not None or not detail.get("raw_text"):
            continue
        candidates = [line for line in lines if line["raw_text"] == detail["raw_text"]]
        if str(detail.get("method", "")).startswith("table_ocr"):
            candidates = [line for line in candidates if line["table_index"] is not None] or candidates
        elif detail.get("method") == "overall_ocr":
            candidates = [line for line in candidates if line["table_index"] is None] or candidates
        if candidates:
            line = candidates[0]
            detail.update(page=line["page"], bbox=line["bbox"], score=line["score"], raw_method=line["method"])


def _checkbox_debug(detail):
    component = detail.get("selected_component")
    roi = None if not component else [
        component["x"], component["y"],
        component["x"] + component["width"], component["y"] + component["height"],
    ]
    return {
        "page": detail.get("page"),
        "roi": roi,
        "raw_text": detail.get("options_ocr_text"),
        "method": detail.get("method", "visual_checkbox"),
        "score": None,
    }


def parse_contract(raw, pdf_path, field_names):
    page = pages(raw)[0]
    result = {name: None for name in field_names}
    debug = {}
    warnings = []

    def set_raw(field, raw_text, value, method):
        result[field] = value
        debug[field] = {"raw_text": raw_text, "method": method}

    def warn(field, code, message, raw_text=None):
        warnings.append({"field": field, "code": code, "message": message, "raw_text": raw_text})

    for field, labels in (
        ("ct_employer_name", ("사업체명",)),
        ("ct_employee_name", ("근로자성명",)),
    ):
        raw_text, method = _after(page, *labels)
        set_raw(field, raw_text, clean_text(raw_text), method) if raw_text else warn(field, "anchor_missing", "label/value pair not found")

    period, method = _after(page, "신규·재입국자")
    dates = korean_dates(period)
    if len(dates) == 2:
        set_raw("ct_new_or_reentry_start_date", period, dates[0], method)
        set_raw("ct_new_or_reentry_end_date", period, dates[1], method)
    else:
        for field in ("ct_new_or_reentry_start_date", "ct_new_or_reentry_end_date"):
            warn(field, "date_parse_failed", "two contract dates were not found", period)

    change_period, change_method = _after(page, "근무처변경자")

    work_time, method = _after(page, "소정근로시간")
    times = re.findall(r"\b\d{1,2}:\d{2}\b", work_time or "")
    if len(times) == 2:
        set_raw("ct_work_start_time", work_time, times[0], method)
        set_raw("ct_work_end_time", work_time, times[1], method)
    else:
        for field in ("ct_work_start_time", "ct_work_end_time"):
            warn(field, "time_parse_failed", "work start/end time was not found", work_time)

    monthly, method = _after(page, "월소정근로시간")
    match = re.search(r"\d+", monthly or "")
    set_raw("ct_monthly_work_hours", monthly, float(match.group()), method) if match else warn("ct_monthly_work_hours", "number_parse_failed", "monthly hours were not found", monthly)

    break_text, method = _after(page, "1일총휴게시간")
    match = re.search(r"(\d+)\s*시간\s*(\d+)\s*분", break_text or "")
    if match:
        set_raw("ct_break_hours", break_text, float(match.group(1)), method)
        set_raw("ct_break_minutes", break_text, int(match.group(2)), method)
    else:
        for field in ("ct_break_hours", "ct_break_minutes"):
            warn(field, "number_parse_failed", "break hours/minutes were not found", break_text)

    weekdays, method = _after(page, "소정근로요일")
    match = re.search(r"(월|화|수|목|금|토|일)요일\s*[~～-]\s*(월|화|수|목|금|토|일)요일", weekdays or "")
    if match:
        set_raw("ct_work_day_start", weekdays, f"{match.group(1)}요일", method)
        set_raw("ct_work_day_end", weekdays, f"{match.group(2)}요일", method)
    else:
        for field in ("ct_work_day_start", "ct_work_day_end"):
            warn(field, "weekday_parse_failed", "work weekday range was not found", weekdays)

    holiday, method = _after(page, "휴일 부여 방식", "휴일부여방식")
    set_raw("ct_holiday_type", holiday, clean_text(holiday), method) if holiday else warn("ct_holiday_type", "anchor_missing", "holiday text was not found")

    max_hours, method = _after(page, "계절·기상 요인에 따른", "계절·기상요인에 따른")
    match = re.search(r"\d+", max_hours or "")
    set_raw("ct_max_daily_work_hours", max_hours, float(match.group()), method) if match else warn("ct_max_daily_work_hours", "number_parse_failed", "daily maximum hours were not found", max_hours)

    wage, method = _after(page, "임금액")
    set_raw("ct_wage_amount", wage, money(wage), method) if money(wage) is not None else warn("ct_wage_amount", "money_parse_failed", "wage amount was not found", wage)

    bonus, method = _after(page, "상여금·수당")
    bonus_match = re.search(r"상여금\s*([\d,]+)\s*원", bonus or "")
    extra_match = re.search(r"수당\s*([\d,]+)\s*원", bonus or "")
    if bonus_match and extra_match:
        set_raw("ct_bonus_amount", bonus, money(bonus_match.group(1)), method)
        set_raw("ct_extra_pay_amount", bonus, money(extra_match.group(1)), method)
    elif money(bonus) == 0:
        set_raw("ct_bonus_amount", bonus, 0, method + ":combined_zero")
        set_raw("ct_extra_pay_amount", bonus, 0, method + ":combined_zero")
        warn("ct_bonus_amount", "combined_zero", "combined '상여금·수당 0원' deterministically maps both non-negative amounts to zero", bonus)
        warn("ct_extra_pay_amount", "combined_zero", "combined '상여금·수당 0원' deterministically maps both non-negative amounts to zero", bonus)
    else:
        for field in ("ct_bonus_amount", "ct_extra_pay_amount"):
            warn(field, "combined_amount_ambiguous", "combined bonus/allowance amount cannot be split", bonus)

    overtime, method = _after(page, "연장근로시간당임금")
    set_raw("ct_overtime_hourly_pay", overtime, money(overtime), method) if money(overtime) is not None else warn("ct_overtime_hourly_pay", "money_parse_failed", "overtime hourly pay was not found", overtime)

    period_text, method = _after(page, "임금계산기간")
    bounds = pay_period(period_text)
    if bounds:
        set_raw("ct_pay_period_start", period_text, bounds[0], method)
        set_raw("ct_pay_period_end", period_text, bounds[1], method)
    else:
        for field in ("ct_pay_period_start", "ct_pay_period_end"):
            warn(field, "pay_period_ambiguous", "pay-period expression is not an approved v6 form", period_text)

    payout, method = _matching(page, r"(당월|익월|당주|익주)")
    payment = _payment_terms(payout)
    if payment:
        set_raw("ct_pay_timing", payout, payment["timing"], method)
        set_raw("ct_pay_cycle", payout, payment["cycle"], method)
        if payment["cycle"] == "월":
            if "day" in payment:
                set_raw("ct_pay_day", payout, payment["day"], method)
            else:
                warn("ct_pay_day", "payout_parse_failed", "monthly pay day was not found", payout)
            debug["ct_pay_weekday"] = {"raw_text": payout, "method": method, "reason": "monthly pay clause has no weekday"}
            warn("ct_pay_weekday", "not_applicable", "monthly pay clause has no pay weekday", payout)
        else:
            if "weekday" in payment:
                set_raw("ct_pay_weekday", payout, payment["weekday"], method)
            else:
                warn("ct_pay_weekday", "payout_parse_failed", "weekly pay weekday was not found", payout)
            debug["ct_pay_day"] = {"raw_text": payout, "method": method, "reason": "weekly pay clause has no calendar day"}
            warn("ct_pay_day", "not_applicable", "weekly pay clause has no monthly pay day", payout)
    else:
        warn("ct_pay_timing", "payout_parse_failed", "pay timing was not found", payout)
        warn("ct_pay_day", "payout_parse_failed", "pay day was not found", payout)
        warn("ct_pay_cycle", "pay_cycle_parse_failed", "pay cycle was not found", payout)
        warn("ct_pay_weekday", "payout_parse_failed", "pay weekday was not found", payout)

    for field, label in (
        ("ct_housing_cost", "월숙박비근로자부담액"),
        ("ct_meal_cost", "월식비근로자 부담액"),
    ):
        raw_text, method = _after(page, label, label.replace(" ", ""))
        set_raw(field, raw_text, money(raw_text), method) if money(raw_text) is not None else warn(field, "money_parse_failed", "cost was not found", raw_text)

    grayscale = render_first_page(pdf_path, page_size(page)[0])
    checkbox_specs = (
        ("contract_type", "계약구분", ["신규·재입국자", "근무처 변경자"]),
        ("wage_type", "임금형태", ["시급", "일급", "주급", "월급"]),
        ("bonus_paid", "상여금·수당지급여부", ["있음", "없음"]),
        ("weekly_allowance", "주휴수당", ["임금에 포함", "별도 지급"]),
        ("housing", "숙박시설제공", ["제공", "미제공"]),
        ("meal", "식사제공", ["제공", "미제공"]),
    )
    checkboxes = {}
    for group, group_label, choices in checkbox_specs:
        selected, detail = detect_group(page, grayscale, group_label, choices)
        checkboxes[group] = {"selected": selected, **detail}

    contract_type = checkboxes["contract_type"]["selected"]
    if contract_type:
        options_text = checkboxes["contract_type"].get("options_ocr_text")
        set_raw("ct_new_or_reentry_selected", options_text, contract_type == "신규·재입국자", "visual_checkbox")
        set_raw("ct_workplace_change_selected", options_text, contract_type == "근무처 변경자", "visual_checkbox")
        for field in ("ct_new_or_reentry_selected", "ct_workplace_change_selected"):
            debug[field] = _checkbox_debug(checkboxes["contract_type"])
        if contract_type == "근무처 변경자":
            dates = korean_dates(change_period)
            if len(dates) == 2:
                set_raw("ct_workplace_change_start_date", change_period, dates[0], change_method)
                set_raw("ct_workplace_change_end_date", change_period, dates[1], change_method)
            else:
                for field in ("ct_workplace_change_start_date", "ct_workplace_change_end_date"):
                    warn(field, "date_parse_failed", "workplace-change dates were not found", change_period)
        else:
            for field in ("ct_workplace_change_start_date", "ct_workplace_change_end_date"):
                debug[field] = {"raw_text": change_period, "method": change_method, "reason": "workplace change is not selected"}
    else:
        for field in ("ct_new_or_reentry_selected", "ct_workplace_change_selected"):
            warn(field, "checkbox_ambiguous", "contract-type checkbox could not be resolved")

    checkbox_fields = {
        "wage_type": ("ct_wage_type", lambda selected: selected),
        "bonus_paid": ("ct_bonus_extra_pay_paid", lambda selected: selected == "있음"),
        "weekly_allowance": ("ct_weekly_allowance_included", lambda selected: selected == "임금에 포함"),
        "housing": ("ct_housing_provided", lambda selected: selected == "제공"),
        "meal": ("ct_meal_provided", lambda selected: selected == "제공"),
    }
    for group, (field, convert) in checkbox_fields.items():
        selected = checkboxes[group]["selected"]
        if selected is None:
            warn(field, "checkbox_ambiguous", f"{group} checkbox could not be resolved")
        else:
            set_raw(field, checkboxes[group].get("options_ocr_text"), convert(selected), "visual_checkbox")
            debug[field] = _checkbox_debug(checkboxes[group])

    _add_line_provenance(page, debug)
    return result, debug, warnings, checkboxes
