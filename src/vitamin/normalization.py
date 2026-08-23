from __future__ import annotations

import re
import unicodedata
import calendar
from datetime import date, datetime, time
from decimal import Decimal, InvalidOperation
from typing import Any


def normalize_name(value: Any) -> str | None:
    if value is None:
        return None
    text = unicodedata.normalize("NFKC", str(value)).upper().strip()
    return re.sub(r"[^0-9A-Z가-힣]", "", text) or None


def number(value: Any) -> Decimal | None:
    if value in (None, ""):
        return None
    if isinstance(value, bool):
        return None
    try:
        return Decimal(str(value).replace(",", "").replace("원", "").strip())
    except (InvalidOperation, ValueError):
        return None


def integer(value: Any) -> int | None:
    parsed = number(value)
    return None if parsed is None else int(parsed)


def parse_date(value: Any) -> date | None:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    if not value:
        return None
    text = str(value).strip().replace(".", "-").replace("/", "-")
    try:
        return date.fromisoformat(text[:10])
    except ValueError:
        return None


def resolve_recurring_date(value: Any, reference: date | None, *, end: bool = False) -> date | None:
    """v4 계약기간의 날짜/일자/매월 1일/말일 표현을 실제 날짜로 바꾼다."""
    absolute = parse_date(value)
    if absolute or value is None or reference is None:
        return absolute
    text = unicodedata.normalize("NFKC", str(value)).strip().upper()
    last_day = calendar.monthrange(reference.year, reference.month)[1]
    if text in {"LAST_DAY", "말일", "매월 말일"} or (end and ("말일" in text or text.endswith("말"))):
        return date(reference.year, reference.month, last_day)
    match = re.search(r"(?<!\d)(0?[1-9]|[12]\d|3[01])(?:일)?", text)
    if match:
        day = min(int(match.group(1)), last_day)
        return date(reference.year, reference.month, day)
    if not end and ("초" in text or "시작일" in text):
        return date(reference.year, reference.month, 1)
    return None


def parse_datetime(value: Any) -> datetime | None:
    if isinstance(value, datetime):
        return value
    parsed_date = parse_date(value)
    if parsed_date and len(str(value).strip()) <= 10:
        return datetime.combine(parsed_date, time.min)
    try:
        return datetime.fromisoformat(str(value).strip().replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return None


def parse_time(value: Any) -> time | None:
    if isinstance(value, time):
        return value
    if not value:
        return None
    text = str(value).strip()
    for fmt in ("%H:%M", "%H:%M:%S", "%I:%M %p"):
        try:
            return datetime.strptime(text, fmt).time()
        except ValueError:
            pass
    return None


def normalize_wage_type(value: Any) -> str | None:
    if not value:
        return None
    key = str(value).strip().lower()
    aliases = {
        "시급": "hourly", "시간급": "hourly", "hourly": "hourly",
        "일급": "daily", "daily": "daily",
        "주급": "weekly", "weekly": "weekly",
        "월급": "monthly", "monthly": "monthly",
    }
    return aliases.get(key)


def bool_value(value: Any) -> bool | None:
    if isinstance(value, bool):
        return value
    if value is None:
        return None
    key = str(value).strip().lower()
    if key in {"true", "yes", "y", "1", "예", "유", "제공", "포함"}:
        return True
    if key in {"false", "no", "n", "0", "아니오", "무", "미제공", "미포함"}:
        return False
    return None
