"""Minimal, lossless access to the installed PP-StructureV3 JSON shape."""

import json
from pathlib import Path


def load_result(path):
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(data, dict) or not isinstance(data.get("pages"), list):
        raise ValueError("raw result must be an object containing a pages array")
    return data


def load_run_metadata(path):
    report = json.loads(Path(path).read_text(encoding="utf-8"))
    names = ("pipeline", "paddlepaddle", "paddleocr", "paddlex", "recognition_model", "device")
    missing = [name for name in names if not report.get(name)]
    if missing:
        raise ValueError(f"run metadata is missing: {', '.join(missing)}")
    return {name: report[name] for name in names}


def pages(raw):
    value = raw.get("pages") if isinstance(raw, dict) else None
    if not isinstance(value, list):
        raise ValueError("raw result must contain a pages array")
    return value


def _lines(block, page, method, table_index=None):
    texts = block.get("rec_texts", [])
    if not isinstance(texts, list):
        raise ValueError(f"{method}.rec_texts must be an array")
    values = {}
    for name in ("rec_scores", "rec_boxes", "rec_polys"):
        array = block.get(name)
        if array is None:
            array = [None] * len(texts)
        if not isinstance(array, list) or len(array) != len(texts):
            raise ValueError(f"{method}.{name} length must match rec_texts")
        values[name] = array
    return [
        {
            "page": page,
            "raw_text": text,
            "score": values["rec_scores"][index],
            "bbox": values["rec_boxes"][index],
            "polygon": values["rec_polys"][index],
            "method": method,
            "table_index": table_index,
        }
        for index, text in enumerate(texts)
    ]


def ocr_lines(page, table_first=False):
    page_index = page.get("page_index")
    overall = _lines(page.get("overall_ocr_res", {}), page_index, "overall_ocr_res")
    table = [
        line
        for index, result in enumerate(page.get("table_res_list", []))
        for line in _lines(
            result.get("table_ocr_pred", {}),
            page_index,
            f"table_res_list[{index}].table_ocr_pred",
            index,
        )
    ]
    return table + overall if table_first else overall + table


def tables(page):
    page_index = page.get("page_index")
    return [
        {
            "page": page_index,
            "table_index": index,
            "html": result.get("pred_html"),
            "cell_bboxes": result.get("cell_box_list", []),
            "ocr_lines": _lines(
                result.get("table_ocr_pred", {}),
                page_index,
                f"table_res_list[{index}].table_ocr_pred",
                index,
            ),
        }
        for index, result in enumerate(page.get("table_res_list", []))
    ]


def layout_boxes(page):
    boxes = page.get("layout_det_res", {}).get("boxes", [])
    if not isinstance(boxes, list):
        raise ValueError("layout_det_res.boxes must be an array")
    return boxes


def page_size(page):
    width, height = page.get("width"), page.get("height")
    if not isinstance(width, (int, float)) or not isinstance(height, (int, float)):
        raise ValueError("page width and height must be numbers")
    return width, height


def provenance(*, page, raw_text, method, bbox=None, roi=None, score=None, warning=None):
    if bbox is not None and roi is not None:
        raise ValueError("provenance may contain bbox or ROI, not both")
    return {
        "page": page,
        "bbox": bbox,
        "roi": roi,
        "raw_text": raw_text,
        "method": method,
        "score": score,
        "warning": warning,
    }


def line_provenance(line, warning=None):
    return provenance(
        page=line["page"],
        bbox=line["bbox"],
        raw_text=line["raw_text"],
        method=line["method"],
        score=line["score"],
        warning=warning,
    )
