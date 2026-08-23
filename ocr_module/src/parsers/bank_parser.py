import re

from src.normalization import clean_text, dotted_dates, key, money
from src.ocr_raw_adapter import ocr_lines, pages, tables


HEADERS = {
    "거래일시": "bk_transaction_datetime",
    "내용": "bk_transaction_content",
    "입금액원": "bk_deposit_amount",
    "거래기록": "bk_transaction_record",
    "메모": "bk_transfer_memo",
    "거래기록/메모": "combined_record_memo",
    "거래기록메모": "combined_record_memo",
}
IGNORED_HEADERS = {"거래구분", "출금액원"}
DATETIME = re.compile(r"\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}(?::\d{2})?")
TRANSACTION_FIELDS = (
    "bk_deposit_amount", "bk_transaction_content", "bk_transaction_datetime",
    "bk_transaction_record", "bk_transfer_memo",
)


def _center(box):
    return ((box[0] + box[2]) / 2, (box[1] + box[3]) / 2)


def _source_lines(page):
    table_lines = [line for table in tables(page) for line in table["ocr_lines"]]
    return table_lines or [line for line in ocr_lines(page) if line["table_index"] is None]


def _provenance(line, method):
    return {
        "page": line["page"], "bbox": line["bbox"], "raw_text": line["raw_text"],
        "method": method, "score": line["score"],
    }


def _label_value(lines, label):
    labels = [line for line in lines if key(line["raw_text"]) == key(label)]
    for anchor in labels:
        ax, ay = _center(anchor["bbox"])
        candidates = [
            line for line in lines
            if line is not anchor and _center(line["bbox"])[0] > ax
            and abs(_center(line["bbox"])[1] - ay) <= max(12, (anchor["bbox"][3] - anchor["bbox"][1]))
        ]
        if candidates:
            return min(candidates, key=lambda line: _center(line["bbox"])[0])
    return None


def _row_cells(lines, date_line, header_lines):
    _, row_y = _center(date_line["bbox"])
    same_row = [line for line in lines if abs(_center(line["bbox"])[1] - row_y) <= 13]
    columns = sorted(header_lines, key=lambda item: _center(item["bbox"])[0])
    cells = {}
    for line in same_row:
        if line in header_lines:
            continue
        nearest = min(columns, key=lambda header: abs(_center(header["bbox"])[0] - _center(line["bbox"])[0]))
        name = HEADERS.get(key(nearest["raw_text"]))
        if name and name not in cells:
            cells[name] = line
    return cells


def parse_bank(raw, field_names):
    result = {name: None for name in field_names}
    debug = {}
    warnings = []
    transactions = []
    transaction_debug = []

    first_page_lines = _source_lines(pages(raw)[0])
    holder = _label_value(first_page_lines, "예금주")
    if holder:
        result["bk_account_holder"] = clean_text(holder["raw_text"])
        debug["bk_account_holder"] = _provenance(holder, "table_label_bbox")
    else:
        warnings.append({"field": "bk_account_holder", "code": "anchor_missing", "message": "account holder was not found"})

    inquiry = _label_value(first_page_lines, "조회기간")
    dates = dotted_dates(inquiry["raw_text"] if inquiry else None)
    if len(dates) == 2:
        result["bk_inquiry_start_date"], result["bk_inquiry_end_date"] = dates
        for field in ("bk_inquiry_start_date", "bk_inquiry_end_date"):
            debug[field] = _provenance(inquiry, "table_label_bbox")
    else:
        for field in ("bk_inquiry_start_date", "bk_inquiry_end_date"):
            warnings.append({"field": field, "code": "date_parse_failed", "message": "two inquiry dates were not found", "raw_text": inquiry["raw_text"] if inquiry else None})

    header_seen = False
    for page in pages(raw):
        lines = _source_lines(page)
        header_lines = [line for line in lines if key(line["raw_text"]) in set(HEADERS) | IGNORED_HEADERS]
        if not any(key(line["raw_text"]) == "거래일시" for line in header_lines):
            continue
        header_seen = True
        header_y = min(_center(line["bbox"])[1] for line in header_lines)
        for date_line in sorted(
            (line for line in lines if _center(line["bbox"])[1] > header_y and DATETIME.fullmatch(clean_text(line["raw_text"]))),
            key=lambda line: _center(line["bbox"])[1],
        ):
            cells = _row_cells(lines, date_line, header_lines)
            cells["bk_transaction_datetime"] = date_line
            transaction = {name: None for name in TRANSACTION_FIELDS}
            row_debug = {}
            for field in transaction:
                line = cells.get(field)
                if line:
                    transaction[field] = money(line["raw_text"]) if field == "bk_deposit_amount" else clean_text(line["raw_text"])
                    row_debug[field] = _provenance(line, "table_ocr_header_bbox")

            combined = cells.get("combined_record_memo")
            if combined:
                parts = [clean_text(part) for part in combined["raw_text"].split("/")]
                if len(parts) == 2 and all(parts):
                    transaction["bk_transaction_record"], transaction["bk_transfer_memo"] = parts
                    for field in ("bk_transaction_record", "bk_transfer_memo"):
                        row_debug[field] = _provenance(combined, "table_ocr_explicit_delimiter")
                else:
                    for field in ("bk_transaction_record", "bk_transfer_memo"):
                        row_debug[field] = _provenance(combined, "table_ocr_combined_ambiguous")
                        warnings.append({"field": f"transactions[{len(transactions)}].{field}", "code": "combined_cell_ambiguous", "message": "combined record/memo cell has no single explicit delimiter", "raw_text": combined["raw_text"]})

            for field, value in transaction.items():
                if value is None:
                    warnings.append({"field": f"transactions[{len(transactions)}].{field}", "code": "cell_parse_failed", "message": "transaction cell is missing or invalid", "raw_text": row_debug.get(field, {}).get("raw_text")})
            transactions.append(transaction)
            transaction_debug.append(row_debug)

    if not header_seen:
        warnings.append({"field": "transactions", "code": "header_missing", "message": "semantic transaction header was not found"})
        result["transactions"] = None
    else:
        result["transactions"] = transactions
        if not transactions:
            warnings.append({"field": "transactions", "code": "rows_missing", "message": "transaction header exists but no transaction row was parsed"})
    debug["transactions"] = {"method": "table_ocr_header_bbox", "rows": transaction_debug}
    return result, debug, warnings
