import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.normalization import pay_period
from src.ocr_raw_adapter import line_provenance, ocr_lines, pages, tables
from src.parsers.bank_parser import parse_bank
from src.schema_validation import schema_errors


def load(path):
    return json.loads(path.read_text(encoding="utf-8"))


def test_v6_example_schema():
    schema = load(ROOT / "references/R00-R11_최종_JSON_Schema_v6.json")
    example = load(ROOT / "examples/sample_canonical.json")
    errors = schema_errors(example["documents"], schema["properties"]["documents"], "$.documents")
    assert not errors, errors


def test_normalization_policy():
    assert pay_period("매월 1일 ~ 31일") == (1, 31)
    assert pay_period("매월 1일 ~ 말일") == (1, "LAST_DAY")
    assert pay_period("매월 1일 ~ 마지막일") == (1, "LAST_DAY")
    assert pay_period("2026.12.16 ~ 2027.01.15") == ("2026-12-16", "2027-01-15")
    assert pay_period("매월 초일부터 월말까지") is None


def test_raw_adapter_and_semantic_bank_row():
    texts = [
        "예금주", "홍길동", "조회기간", "2026.07.01. ~ 2026.07.31.",
        "거래일시", "내용", "입금액(원)", "거래기록", "메모",
        "2026-07-10 09:30:00", "입금", "1,936,000", "급여", "7월급여",
    ]
    boxes = [
        [10, 10, 60, 25], [80, 10, 140, 25], [10, 40, 70, 55], [90, 40, 260, 55],
        [10, 100, 90, 115], [120, 100, 170, 115], [210, 100, 290, 115],
        [320, 100, 390, 115], [430, 100, 480, 115],
        [10, 130, 150, 145], [120, 130, 170, 145], [210, 130, 290, 145],
        [320, 130, 390, 145], [430, 130, 500, 145],
    ]
    raw = {
        "pages": [{
            "page_index": 0,
            "width": 600,
            "height": 800,
            "overall_ocr_res": {"rec_texts": [], "rec_scores": [], "rec_boxes": [], "rec_polys": []},
            "table_res_list": [{
                "pred_html": "<table></table>",
                "cell_box_list": boxes,
                "table_ocr_pred": {
                    "rec_texts": texts,
                    "rec_scores": [0.99] * len(texts),
                    "rec_boxes": boxes,
                    "rec_polys": [None] * len(texts),
                },
            }],
        }]
    }
    assert len(pages(raw)) == 1
    assert len(tables(raw["pages"][0])) == 1
    assert len(ocr_lines(raw["pages"][0], table_first=True)) == len(texts)

    fields = ("bk_account_holder", "bk_inquiry_end_date", "bk_inquiry_start_date", "transactions")
    value, debug, warnings = parse_bank(raw, fields)
    assert not warnings, warnings
    assert value["bk_account_holder"] == "홍길동"
    assert value["bk_inquiry_start_date"] == "2026-07-01"
    assert value["bk_inquiry_end_date"] == "2026-07-31"
    assert value["transactions"] == [{
        "bk_deposit_amount": 1936000,
        "bk_transaction_content": "입금",
        "bk_transaction_datetime": "2026-07-10 09:30:00",
        "bk_transaction_record": "급여",
        "bk_transfer_memo": "7월급여",
    }]
    assert debug["transactions"]["rows"][0]["bk_deposit_amount"]["bbox"] == boxes[11]

    source = line_provenance(ocr_lines(raw["pages"][0], table_first=True)[0])
    assert source["bbox"] == boxes[0] and source["score"] == 0.99


if __name__ == "__main__":
    tests = (test_v6_example_schema, test_normalization_policy, test_raw_adapter_and_semantic_bank_row)
    for test in tests:
        test()
        print(f"PASS {test.__name__}")
