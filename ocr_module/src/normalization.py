import re
from datetime import date


def clean_text(value):
    return re.sub(r"\s+", " ", value or "").strip()


def money(value):
    match = re.search(r"-?[\d,]+", value or "")
    return int(match.group().replace(",", "")) if match else None


def korean_dates(value):
    return [
        f"{int(year):04d}-{int(month):02d}-{int(day):02d}"
        for year, month, day in re.findall(
            r"(\d{4})\s*년\s*(\d{1,2})\s*월\s*(\d{1,2})\s*일", value or ""
        )
    ]


def dotted_dates(value):
    return [
        f"{int(year):04d}-{int(month):02d}-{int(day):02d}"
        for year, month, day in re.findall(
            r"(\d{4})\s*[.]\s*(\d{1,2})\s*[.]\s*(\d{1,2})\s*[.]?", value or ""
        )
    ]


def pay_period(value):
    """Return the v6 recurring/fixed canonical bounds, or None if ambiguous."""
    text = clean_text(value)
    match = re.search(
        r"매월\s*(\d{1,2})\s*일\s*[~～∼–—-]\s*"
        r"(?:(\d{1,2})\s*일|(말일|마지막\s*(?:날|일)))",
        text,
    )
    if match:
        start = int(match.group(1))
        end = int(match.group(2)) if match.group(2) else "LAST_DAY"
        return (start, end) if 1 <= start <= 31 and (end == "LAST_DAY" or 1 <= end <= 31) else None

    parts = re.findall(r"(\d{4})\s*[./-]\s*(\d{1,2})\s*[./-]\s*(\d{1,2})", text)
    if len(parts) != 2:
        return None
    try:
        return tuple(date(*map(int, part)).isoformat() for part in parts)
    except ValueError:
        return None


def key(value):
    return re.sub(r"[\s·.()\-_]", "", value or "")
