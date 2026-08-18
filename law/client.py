"""국가법령정보 Open API 클라이언트.

환경변수 LAW_OC에 발급받은 OC를 넣고 사용한다.
"""

from __future__ import annotations

import json
import os
import ssl
import time
import urllib.error
import urllib.parse
import urllib.request

BASE = "https://www.law.go.kr/DRF"
TIMEOUT = 30
RETRY = 3
RETRY_WAIT = 2.0

# 연속 호출이 잦으면 서버가 IP 단위로 연결을 리셋한다(Errno 54).
# 한 번 걸리면 수십 분 풀리지 않으므로 호출 간격을 강제한다.
MIN_INTERVAL = 1.2
_last_call = 0.0


class LawApiError(RuntimeError):
    """API가 오류 응답을 돌려준 경우."""


def _ssl_context() -> ssl.SSLContext:
    """CA 번들을 명시적으로 지정한 SSL 컨텍스트.

    python.org 설치본은 'Install Certificates.command'를 실행하지 않으면
    cert.pem이 없어 모든 HTTPS 검증이 실패한다. certifi 번들로 우회한다.
    """
    try:
        import certifi

        return ssl.create_default_context(cafile=certifi.where())
    except ImportError:
        return ssl.create_default_context()


def get_oc() -> str:
    oc = os.environ.get("LAW_OC")
    if not oc:
        raise LawApiError('LAW_OC 환경변수가 없습니다. export LAW_OC="발급받은OC"')
    return oc


def _throttle() -> None:
    global _last_call
    wait = MIN_INTERVAL - (time.monotonic() - _last_call)
    if wait > 0:
        time.sleep(wait)
    _last_call = time.monotonic()


def call(endpoint: str, **params: str) -> dict:
    """DRF API를 JSON으로 호출한다. 일시적 오류는 재시도한다."""
    params.setdefault("type", "JSON")
    params.setdefault("OC", get_oc())
    url = f"{BASE}/{endpoint}?{urllib.parse.urlencode(params)}"
    request = urllib.request.Request(url, headers={"User-Agent": "vitamin-nlp/1.0"})
    _throttle()

    last: Exception | None = None
    for attempt in range(RETRY):
        try:
            with urllib.request.urlopen(request, timeout=TIMEOUT, context=_ssl_context()) as response:
                raw = response.read().decode("utf-8")
            break
        except (urllib.error.URLError, TimeoutError) as exc:
            last = exc
            if attempt < RETRY - 1:
                time.sleep(RETRY_WAIT * (attempt + 1))
    else:
        raise LawApiError(f"{endpoint} 호출 실패: {last}")

    try:
        payload = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise LawApiError(f"JSON 응답이 아닙니다.\n응답 앞부분: {raw[:200]}") from exc

    # OC가 틀리거나 IP가 등록되지 않으면 HTTP 200에 오류 JSON이 실려 온다.
    if isinstance(payload, dict) and "result" in payload:
        raise LawApiError(f"{payload['result']} {payload.get('msg', '')}".strip())
    return payload


def search_law(query: str) -> list[dict]:
    """법령명으로 검색해 목록을 반환한다."""
    laws = call("lawSearch.do", target="law", query=query).get("LawSearch", {}).get("law", [])
    return laws if isinstance(laws, list) else [laws]


def fetch_law(mst: str) -> dict:
    """법령 일련번호(MST)로 본문 전체를 반환한다."""
    return call("lawService.do", target="law", MST=mst).get("법령", {})


def search_admrul(query: str) -> list[dict]:
    """행정규칙(고시·훈령·예규)을 검색한다."""
    rows = call("lawSearch.do", target="admrul", query=query).get("AdmRulSearch", {}).get("admrul", [])
    return rows if isinstance(rows, list) else [rows]


def fetch_admrul(rule_id: str) -> dict:
    """행정규칙 일련번호로 본문을 반환한다.

    주의: 고시는 본문이 조문 형태가 아니라 첨부파일(HWP)에만 담긴 경우가 있다.
    이때 '조문내용'은 빈 객체로 돌아온다.
    """
    return call("lawService.do", target="admrul", ID=rule_id).get("AdmRulService", {})
