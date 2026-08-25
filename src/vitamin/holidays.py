from __future__ import annotations

import json
import os
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from datetime import date, datetime, timedelta
from pathlib import Path


API_URL = (
    "https://apis.data.go.kr/B090041/openapi/service/"
    "SpcdeInfoService/getRestDeInfo"
)
PROJECT_ROOT = Path(__file__).resolve().parents[2]
HOLIDAY_SNAPSHOT_PATH = PROJECT_ROOT / "references" / "public_holidays_2026.json"


def env_value(name: str) -> str | None:
    """운영체제 환경변수를 우선하고 프로젝트 주변의 .env를 보조로 읽는다."""
    value = os.getenv(name)
    if value:
        return value
    env_paths = (Path.cwd() / ".env", PROJECT_ROOT / ".env", PROJECT_ROOT.parent / ".env")
    for env_path in dict.fromkeys(path.resolve() for path in env_paths):
        if not env_path.is_file():
            continue
        for raw_line in env_path.read_text(encoding="utf-8-sig").splitlines():
            line = raw_line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, candidate = line.split("=", 1)
            if key.strip() == name:
                return candidate.strip().strip('"').strip("'") or None
    return None


class HolidayAPIError(RuntimeError):
    """공휴일 API를 정상적으로 조회하지 못한 경우."""


class PublicHolidayClient:
    """한국천문연구원 공휴일 API 클라이언트.

    API 키가 없거나 조회에 실패하면 룰 엔진이 오류를 내지 않고 R09를
    REVIEW로 돌릴 수 있도록 예외를 명확하게 전달한다.
    """

    def __init__(self, service_key: str | None = None, timeout: float = 10.0) -> None:
        raw_key = service_key or env_value("KASI_HOLIDAY_API_KEY")
        # 포털의 Encoding 키와 Decoding 키를 모두 허용하고 요청 시 한 번만 인코딩한다.
        self.service_key = urllib.parse.unquote(raw_key) if raw_key else None
        self.timeout = timeout
        self._cache: dict[tuple[int, int], set[date]] = {}

    def _snapshot(self, year: int, month: int) -> set[date] | None:
        """API 장애 때만 사용하는, 공식 API에서 미리 수집한 연도별 스냅샷."""
        if not HOLIDAY_SNAPSHOT_PATH.is_file():
            return None
        payload = json.loads(HOLIDAY_SNAPSHOT_PATH.read_text(encoding="utf-8"))
        if int(payload.get("year", 0)) != year:
            return None
        return {
            parsed for raw in payload.get("dates", [])
            if (parsed := date.fromisoformat(raw)).month == month
        }

    @property
    def configured(self) -> bool:
        return bool(self.service_key)

    def holidays(self, year: int, month: int) -> set[date]:
        cache_key = (year, month)
        if cache_key in self._cache:
            return self._cache[cache_key]
        if not self.service_key:
            raise HolidayAPIError("KASI_HOLIDAY_API_KEY가 설정되지 않았습니다.")

        query = urllib.parse.urlencode({
            "serviceKey": self.service_key,
            "solYear": f"{year:04d}",
            "solMonth": f"{month:02d}",
            "numOfRows": 100,
            "pageNo": 1,
        })
        request = urllib.request.Request(
            f"{API_URL}?{query}",
            headers={"User-Agent": "vitamin-rule-engine/0.1"},
        )
        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                payload = response.read()
            root = ET.fromstring(payload)
        except Exception as exc:
            snapshot = self._snapshot(year, month)
            if snapshot is None:
                raise HolidayAPIError(f"공휴일 API 호출 실패: {exc}") from exc
            self._cache[cache_key] = snapshot
            return snapshot

        result_code = root.findtext(".//resultCode")
        if result_code != "00":
            message = root.findtext(".//resultMsg") or "알 수 없는 오류"
            raise HolidayAPIError(f"공휴일 API 오류: {result_code} {message}")

        result = {
            datetime.strptime(value, "%Y%m%d").date()
            for item in root.findall(".//item")
            if item.findtext("isHoliday") == "Y"
            if (value := item.findtext("locdate"))
        }
        self._cache[cache_key] = result
        return result

    def is_holiday(self, target: date) -> bool:
        return target in self.holidays(target.year, target.month)

    def adjusted_business_day(self, target: date, policy: str) -> date:
        """주말·공휴일인 지급일을 팀이 확정한 정책으로 이동한다."""
        if policy not in {"previous_business_day", "next_business_day"}:
            raise ValueError("공휴일 지급정책은 previous_business_day 또는 next_business_day여야 합니다.")
        step = -1 if policy == "previous_business_day" else 1
        adjusted = target
        while adjusted.weekday() >= 5 or self.is_holiday(adjusted):
            adjusted += timedelta(days=step)
        return adjusted

    def adjacent_business_days(self, target: date) -> set[date]:
        """약정일이 휴일이면 직전·다음 영업일, 평일이면 약정일만 반환한다."""
        if target.weekday() < 5 and not self.is_holiday(target):
            return {target}
        return {
            self.adjusted_business_day(target, "previous_business_day"),
            self.adjusted_business_day(target, "next_business_day"),
        }
