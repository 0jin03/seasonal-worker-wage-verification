import re

from src.normalization import clean_text, dotted_dates, key
from src.ocr_raw_adapter import ocr_lines, page_size, pages, tables
from src.parsers.checkbox_parser import detect_group, render_first_page


DATE = re.compile(r"\d{4}[.]\d{2}[.]\d{2}")
TIME = re.compile(r"\d{1,2}:\d{2}")
LINE_FIELDS = (
    "ts_break_minutes", "ts_holiday_worked", "ts_work_date",
    "ts_work_end_time", "ts_work_note", "ts_work_start_time",
)
HEADER_FIELDS = {
    "근무일": "ts_work_date",
    "시작시각": "ts_work_start_time",
    "종료시각": "ts_work_end_time",
    "휴게분": "ts_break_minutes",
    "휴일근무": "ts_holiday_worked",
    "특이사항": "ts_work_note",
}
IGNORED_HEADERS = {"No", "요일", "실근로시간"}


def _center(box):
    return ((box[0] + box[2]) / 2, (box[1] + box[3]) / 2)


def _provenance(line, method="table_ocr_header_bbox", warning=None):
    return {
        "page": line["page"], "bbox": line["bbox"], "raw_text": line["raw_text"],
        "method": method, "score": line["score"], "warning": warning,
    }


def _table_lines(page):
    lines = [line for table in tables(page) for line in table["ocr_lines"]]
    return lines or [line for line in ocr_lines(page) if line["table_index"] is None]


def _label_value(lines, label):
    for anchor in (line for line in lines if key(line["raw_text"]) == key(label)):
        ax, ay = _center(anchor["bbox"])
        candidates = [line for line in lines if line is not anchor and _center(line["bbox"])[0] > ax and abs(_center(line["bbox"])[1] - ay) <= 13]
        if candidates:
            return min(candidates, key=lambda line: _center(line["bbox"])[0])
    return None


def _parse_row(lines, date_line, headers, row_index, warnings):
    row_y = _center(date_line["bbox"])[1]
    same_row = [line for line in lines if abs(_center(line["bbox"])[1] - row_y) <= 13]
    ordered_headers = sorted(headers, key=lambda line: _center(line["bbox"])[0])
    cells = {}
    for line in same_row:
        nearest = min(ordered_headers, key=lambda header: abs(_center(header["bbox"])[0] - _center(line["bbox"])[0]))
        field = HEADER_FIELDS.get(key(nearest["raw_text"]))
        if field and field not in cells:
            cells[field] = line
    cells["ts_work_date"] = date_line

    row = {field: None for field in LINE_FIELDS}
    debug = {}
    for field in LINE_FIELDS:
        line = cells.get(field)
        raw_text = clean_text(line["raw_text"]) if line else None
        if field == "ts_work_date":
            dates = dotted_dates(raw_text)
            value = dates[0] if len(dates) == 1 else None
        elif field in ("ts_work_start_time", "ts_work_end_time"):
            match = TIME.fullmatch(raw_text or "")
            value = f"{int(match.group().split(':')[0]):02d}:{match.group().split(':')[1]}" if match else None
        elif field == "ts_break_minutes":
            value = int(raw_text) if (raw_text or "").isdigit() else None
        elif field == "ts_holiday_worked":
            value = {"예": True, "예맞음": True, "아니오": False}.get(key(raw_text))
        else:
            value = raw_text or None
        row[field] = value
        if line:
            debug[field] = _provenance(line, warning=None if value is not None else "cell_parse_failed")
        if value is None:
            code = "source_blank" if line is None and field == "ts_work_note" else "cell_parse_failed"
            warnings.append({"field": f"lines[{row_index}].{field}", "code": code, "message": "timesheet cell is blank or invalid", "raw_text": raw_text})
    return row, debug


def parse_timesheet(raw, pdf_path, field_names, line_field_names):
    result = {name: None for name in field_names}
    debug = {}
    warnings = []
    first_page = pages(raw)[0]
    first_lines = _table_lines(first_page)

    employee = _label_value(first_lines, "근로자성명")
    if employee:
        result["ts_employee_name"] = clean_text(employee["raw_text"])
        debug["ts_employee_name"] = _provenance(employee, "table_label_bbox")
    else:
        warnings.append({"field": "ts_employee_name", "code": "anchor_missing", "message": "employee name was not found"})

    grayscale = render_first_page(pdf_path, page_size(first_page)[0])
    selected, checkbox = detect_group(first_page, grayscale, "기록보유여부", ["보유", "미보유"])
    if selected:
        result["ts_record_available"] = selected == "보유"
        component = checkbox["selected_component"]
        debug["ts_record_available"] = {
            "page": checkbox.get("page"),
            "roi": [component["x"], component["y"], component["x"] + component["width"], component["y"] + component["height"]],
            "raw_text": checkbox.get("options_ocr_text"), "method": checkbox["method"], "score": None,
        }
    else:
        warnings.append({"field": "ts_record_available", "code": "checkbox_ambiguous", "message": checkbox.get("reason", "record checkbox could not be resolved")})

    overall = [line for line in ocr_lines(first_page) if line["table_index"] is None]
    missing = next((line for line in overall if "서명없음" in key(line["raw_text"])), None)
    signed = next((line for line in overall if "근로자" in line["raw_text"] and "서명" in line["raw_text"] and "없음" not in line["raw_text"]), None)
    confirmation = missing or signed
    if confirmation:
        result["ts_worker_confirmed"] = missing is None
        debug["ts_worker_confirmed"] = _provenance(confirmation, "overall_ocr_explicit_confirmation")
    else:
        warnings.append({"field": "ts_worker_confirmed", "code": "confirmation_ambiguous", "message": "explicit signature presence/absence text was not found"})

    parsed_lines = []
    line_debug = []
    for page in pages(raw):
        lines = _table_lines(page)
        headers = [line for line in lines if key(line["raw_text"]) in set(HEADER_FIELDS) | IGNORED_HEADERS]
        if set(HEADER_FIELDS.values()) - {HEADER_FIELDS[key(line["raw_text"])] for line in headers if key(line["raw_text"]) in HEADER_FIELDS}:
            warnings.append({"field": "lines", "code": "header_missing", "message": f"timesheet semantic headers are incomplete on page {page.get('page_index')}"})
            continue
        header_y = min(_center(line["bbox"])[1] for line in headers)
        dates = sorted(
            (line for line in lines if _center(line["bbox"])[1] > header_y and DATE.fullmatch(clean_text(line["raw_text"]))),
            key=lambda line: _center(line["bbox"])[1],
        )
        for date_line in dates:
            row, row_debug = _parse_row(lines, date_line, headers, len(parsed_lines), warnings)
            parsed_lines.append(row)
            line_debug.append(row_debug)

    result["lines"] = parsed_lines
    debug["lines"] = {"method": "table_ocr_header_bbox", "rows": line_debug}
    if result["ts_record_available"] is False and parsed_lines:
        warnings.append({"field": "lines", "code": "record_state_conflict", "message": "record checkbox says unavailable but dated rows were parsed"})
    if tuple(line_field_names) != LINE_FIELDS:
        raise ValueError("timesheet Schema line fields differ from the parser contract")
    return result, debug, warnings, {"record_available": checkbox}
