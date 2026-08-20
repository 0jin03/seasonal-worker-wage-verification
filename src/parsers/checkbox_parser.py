from pathlib import Path

import cv2
import numpy as np
import pypdfium2 as pdfium

from src.normalization import key
from src.ocr_raw_adapter import ocr_lines, page_size


def render_first_page(pdf_path, target_width):
    """Render pixels only; no PDF text-layer API is used."""
    pdf = pdfium.PdfDocument(Path(pdf_path))
    try:
        page = pdf[0]
        scale = target_width / page.get_width()
        return np.asarray(page.render(scale=scale).to_pil().convert("L"))
    finally:
        pdf.close()


def detect_group(page, grayscale, group_label, choices):
    lines = [line for line in ocr_lines(page) if line["table_index"] is None]
    labels = [index for index, line in enumerate(lines) if key(line["raw_text"]) == key(group_label)]
    if len(labels) != 1 or labels[0] + 1 >= len(lines):
        return None, {"reason": "checkbox group label is not unique", "matches": len(labels)}

    option_index = labels[0] + 1
    raw_options_text = lines[option_index]["raw_text"]
    box = lines[option_index]["bbox"]
    left, top, right, bottom = box
    crop_left = max(0, left - 5)
    crop = grayscale[max(0, top - 4) : bottom + 4, crop_left : right + 5]
    binary = (crop < 128).astype("uint8")
    _, _, stats, _ = cv2.connectedComponentsWithStats(binary, 8)
    filled = []
    for x, y, width, height, area in stats[1:]:
        density = area / (width * height)
        if 9 <= width <= 15 and 9 <= height <= 15 and density >= 0.85:
            filled.append(
                {
                    "x": int(x + crop_left),
                    "y": int(y + max(0, top - 4)),
                    "width": int(width),
                    "height": int(height),
                    "ink_density": round(float(density), 3),
                }
            )
    if len(filled) != 1:
        return None, {"reason": "filled checkbox is not unique", "candidates": filled}

    center_x = filled[0]["x"] + filled[0]["width"] / 2
    relative_x = (center_x - left) / max(1, right - left)
    choice_index = min(len(choices) - 1, max(0, int(relative_x * len(choices))))
    return choices[choice_index], {
        "method": "rendered_pdf_ink_density",
        "page": page.get("page_index"),
        "group_label": group_label,
        "options_ocr_text": raw_options_text,
        "options_ocr_box": box,
        "selected_component": filled[0],
        "relative_x": round(relative_x, 3),
        "choice_index": choice_index,
    }
