"""국가법령정보 Open API 연결 점검.

환경변수 LAW_OC에 발급받은 OC(이메일 앞부분)를 넣고 실행합니다.

    export LAW_OC="rladudwls12"
    python check_law_api.py                    # 근로기준법
    python check_law_api.py 최저임금법 근로기준법   # 여러 건
"""

from __future__ import annotations

import json
import os
import ssl
import sys
import urllib.error
import urllib.parse
import urllib.request

BASE = "https://www.law.go.kr/DRF"
TIMEOUT = 30
DEFAULT_QUERIES = ["근로기준법"]


def ssl_context() -> ssl.SSLContext:
    """CA 번들을 명시적으로 지정한 SSL 컨텍스트.

    python.org 설치본은 'Install Certificates.command'를 실행하지 않으면
    cert.pem이 없어 모든 HTTPS 검증이 실패한다. certifi 번들로 우회한다.
    """
    try:
        import certifi

        return ssl.create_default_context(cafile=certifi.where())
    except ImportError:
        return ssl.create_default_context()


def call(endpoint: str, **params: str) -> dict:
    """DRF API를 JSON으로 호출한다."""
    params.setdefault("type", "JSON")
    url = f"{BASE}/{endpoint}?{urllib.parse.urlencode(params)}"
    request = urllib.request.Request(url, headers={"User-Agent": "vitamin-nlp/1.0"})
    with urllib.request.urlopen(request, timeout=TIMEOUT, context=ssl_context()) as response:
        raw = response.read().decode("utf-8")

    try:
        payload = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"JSON 응답이 아닙니다.\n응답 앞부분: {raw[:200]}") from exc

    # OC가 틀리거나 IP가 등록되지 않으면 HTTP 200에 오류 JSON이 실려 온다.
    if isinstance(payload, dict) and "result" in payload:
        raise RuntimeError(f"{payload['result']} {payload.get('msg', '')}".strip())
    return payload


def search(oc: str, query: str) -> list[dict]:
    """법령명으로 검색해 목록을 반환한다."""
    payload = call("lawSearch.do", OC=oc, target="law", query=query)
    laws = payload.get("LawSearch", {}).get("law", [])
    return laws if isinstance(laws, list) else [laws]


def article_text(article: dict) -> str:
    """조문 본문을 뽑는다.

    항이 여러 개인 조는 조문내용에 제목만 있고 실제 내용은 항 배열에 들어간다.
    """
    parts = [str(article.get("조문내용", ""))]
    hangs = article.get("항") or []
    parts.extend(str(h.get("항내용", "")) for h in (hangs if isinstance(hangs, list) else [hangs]))
    return " ".join(" ".join(parts).split())


def fetch_articles(oc: str, mst: str) -> tuple[str, list[dict]]:
    """법령 일련번호로 본문을 받아 (법령명, 조문 목록)을 반환한다."""
    law = call("lawService.do", OC=oc, target="law", MST=mst).get("법령", {})
    name = law.get("기본정보", {}).get("법령명_한글", "")
    articles = law.get("조문", {}).get("조문단위", [])
    return name, articles if isinstance(articles, list) else [articles]


def main() -> int:
    oc = os.environ.get("LAW_OC")
    if not oc:
        print("LAW_OC 환경변수가 없습니다.", file=sys.stderr)
        print('  export LAW_OC="발급받은OC"', file=sys.stderr)
        return 1

    queries = sys.argv[1:] or DEFAULT_QUERIES
    print(f"OC: {oc}")

    failed = False
    for query in queries:
        print(f"\n{'=' * 60}\n검색어: {query}\n{'=' * 60}")
        try:
            laws = search(oc, query)
        except (urllib.error.URLError, RuntimeError) as exc:
            print(f"  검색 실패: {exc}", file=sys.stderr)
            failed = True
            continue

        if not laws:
            print("  검색 결과 없음")
            failed = True
            continue

        for law in laws[:5]:
            print(
                f"  [{law.get('법령구분명', ''):6}] {law.get('법령명한글', '')} "
                f"| 시행 {law.get('시행일자', '')} | {law.get('소관부처명', '')} "
                f"| MST={law.get('법령일련번호', '')}"
            )
        if len(laws) > 5:
            print(f"  ... 외 {len(laws) - 5}건")

        # 첫 결과의 본문까지 실제로 받아본다.
        mst = laws[0].get("법령일련번호")
        try:
            name, articles = fetch_articles(oc, mst)
        except (urllib.error.URLError, RuntimeError) as exc:
            print(f"  본문 조회 실패: {exc}", file=sys.stderr)
            failed = True
            continue

        titled = [a for a in articles if a.get("조문제목")]
        print(f"\n  본문 조회: {name} — 조문 {len(articles)}개 (제목 있는 조 {len(titled)}개)")
        for article in titled[:3]:
            print(f"    제{article.get('조문번호')}조({article.get('조문제목')}) {article_text(article)[:70]}")

    print(f"\n{'=' * 60}")
    print("점검 실패" if failed else "점검 통과")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
