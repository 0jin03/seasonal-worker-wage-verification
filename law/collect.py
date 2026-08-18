"""법령 본문을 조·항 단위 코퍼스로 수집한다.

    export LAW_OC="발급받은OC"
    python -m law.collect              # 기본 대상 법령 전체 (API 호출)
    python -m law.collect 근로기준법     # 특정 법령만 (API 호출)
    python -m law.collect --rebuild    # raw/ 원본으로 재파싱 (API 호출 없음)

산출물:
    법령데이터/raw/<법령명>.json   API 원본 응답 (재현·재파싱용)
    법령데이터/corpus.jsonl       조·항 단위 레코드
    법령데이터/index.json         수집한 법령 메타 요약
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Any, Iterator

from law.client import LawApiError, fetch_law, search_law

OUTPUT_DIR = Path("법령데이터")

# 급여검증 R00~R11의 근거가 될 수 있는 법령. 각 항목은 (검색어, 수집할 법종) 이다.
TARGETS: list[tuple[str, tuple[str, ...]]] = [
    ("근로기준법", ("법률", "대통령령", "고용노동부령")),
    ("최저임금법", ("법률", "대통령령", "고용노동부령")),
    ("외국인근로자의 고용 등에 관한 법률", ("법률", "대통령령", "고용노동부령")),
    ("임금채권보장법", ("법률",)),
    ("근로자퇴직급여 보장법", ("법률",)),
]

# 항 앞머리의 원문자(①②③…)와 호 앞머리의 "1." 을 본문에서 제거할 때 쓴다.
CIRCLED = "①②③④⑤⑥⑦⑧⑨⑩⑪⑫⑬⑭⑮⑯⑰⑱⑲⑳"


def squash(value: Any) -> str:
    """공백을 정규화한 문자열로 만든다."""
    return " ".join(str(value or "").split())


def as_list(value: Any) -> list:
    if value is None:
        return []
    return value if isinstance(value, list) else [value]


def strip_marker(text: str) -> str:
    """항의 원문자 또는 호의 번호 접두어를 떼어낸다."""
    text = text.lstrip()
    if text and text[0] in CIRCLED:
        return text[1:].lstrip()
    return re.sub(r"^\d+\.\s*", "", text)


def arabic(number: str, fallback: int) -> str:
    """항번호를 아라비아 숫자로 정규화한다.

    API는 항번호를 원문자(①)로 주기도 하고 '1'로 주기도 한다.
    인용 표기가 '제①항'이 되지 않도록 통일한다.
    """
    number = squash(number).rstrip(".")
    if len(number) == 1 and number in CIRCLED:
        return str(CIRCLED.index(number) + 1)
    return number if number.isdigit() else str(fallback)


def article_label(article: dict) -> str:
    """제43조 / 제43조의2 형태의 조 번호 표기."""
    number = squash(article.get("조문번호"))
    branch = squash(article.get("조문가지번호"))
    return f"제{number}조의{branch}" if branch else f"제{number}조"


def iter_records(law: dict, mst: str) -> Iterator[dict]:
    """법령 본문 JSON을 조·항 단위 레코드로 펼친다."""
    basic = law.get("기본정보", {})
    meta = {
        "법령명": squash(basic.get("법령명_한글")),
        "법령ID": squash(basic.get("법령ID")),
        "MST": mst,
        "법종구분": squash((basic.get("법종구분") or {}).get("content") if isinstance(basic.get("법종구분"), dict) else basic.get("법종구분")),
        "소관부처": squash((basic.get("소관부처") or {}).get("content") if isinstance(basic.get("소관부처"), dict) else basic.get("소관부처")),
        "시행일자": squash(basic.get("시행일자")),
    }

    for article in as_list(law.get("조문", {}).get("조문단위")):
        # '전문'은 제1장 총칙 같은 편장절 머리글이라 규범 내용이 없다.
        if squash(article.get("조문여부")) != "조문":
            continue

        label = article_label(article)
        title = squash(article.get("조문제목"))
        heading = f"{label}({title})" if title else label
        body = squash(article.get("조문내용"))
        # 항이 있는 조는 조문내용에 제목만 담겨 있다. 중복을 피해 떼어낸다.
        lead = body[len(heading):].strip() if body.startswith(heading) else body

        paragraphs = as_list(article.get("항"))
        # 삭제·이동된 조는 조문내용에 번호만 남고 항이 없다. 규범 내용이 없으므로 제외한다.
        if not lead and not paragraphs:
            continue

        parts: list[str] = [lead] if lead else []

        for index, paragraph in enumerate(paragraphs, start=1):
            number = arabic(paragraph.get("항번호"), index)
            text = strip_marker(squash(paragraph.get("항내용")))
            # 항내용이 비고 호만 있는 조가 있다(예: 근로기준법 제63조).
            # 이때 규범을 만드는 '각 호 외의 부분'은 조문내용에 들어 있으므로
            # 항 레코드에 끌어와야 인용이 온전해진다.
            if not text and lead:
                text = lead
            items = [
                {
                    "호번호": squash(item.get("호번호")).rstrip("."),
                    "본문": strip_marker(squash(item.get("호내용"))),
                }
                for item in as_list(paragraph.get("호"))
            ]
            full = " ".join([text, *(f"{i['호번호']}. {i['본문']}" for i in items)]).strip()
            parts.append(full)

            yield {
                **meta,
                "level": "항",
                "doc_id": f"{meta['법령명']}|{label}|{number}",
                "조문번호": squash(article.get("조문번호")),
                "조문가지번호": squash(article.get("조문가지번호")) or None,
                "조문제목": title or None,
                "항번호": number,
                "인용": f"{meta['법령명']} {heading} 제{number}항",
                "본문": full,
                "호": items,
            }

        yield {
            **meta,
            "level": "조",
            "doc_id": f"{meta['법령명']}|{label}",
            "조문번호": squash(article.get("조문번호")),
            "조문가지번호": squash(article.get("조문가지번호")) or None,
            "조문제목": title or None,
            "항번호": None,
            "인용": f"{meta['법령명']} {heading}",
            "본문": " ".join(p for p in parts if p),
            "항개수": len(paragraphs),
        }


def collect(queries: list[str] | None = None) -> None:
    targets = TARGETS if queries is None else [(q, ()) for q in queries]
    raw_dir = OUTPUT_DIR / "raw"
    raw_dir.mkdir(parents=True, exist_ok=True)

    records: list[dict] = []
    index: list[dict] = []

    for query, kinds in targets:
        try:
            hits = search_law(query)
        except LawApiError as exc:
            print(f"  [검색 실패] {query}: {exc}", file=sys.stderr)
            continue

        wanted = [h for h in hits if not kinds or squash(h.get("법령구분명")) in kinds]
        if not wanted:
            print(f"  [결과 없음] {query}")
            continue

        for hit in wanted:
            name = squash(hit.get("법령명한글"))
            mst = squash(hit.get("법령일련번호"))
            try:
                law = fetch_law(mst)
            except LawApiError as exc:
                print(f"  [본문 실패] {name}: {exc}", file=sys.stderr)
                continue

            (raw_dir / f"{name}.json").write_text(
                json.dumps(law, ensure_ascii=False, indent=2), encoding="utf-8"
            )

            new = list(iter_records(law, mst))
            records.extend(new)
            articles = sum(1 for r in new if r["level"] == "조")
            clauses = len(new) - articles
            index.append(
                {
                    "법령명": name,
                    "법령구분": squash(hit.get("법령구분명")),
                    "MST": mst,
                    "시행일자": squash(hit.get("시행일자")),
                    "조": articles,
                    "항": clauses,
                }
            )
            print(f"  {name:<32} 조 {articles:>3} / 항 {clauses:>3} (시행 {squash(hit.get('시행일자'))})")

    write_outputs(records, index)


def write_outputs(records: list[dict], index: list[dict]) -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    corpus_path = OUTPUT_DIR / "corpus.jsonl"
    with corpus_path.open("w", encoding="utf-8") as handle:
        for record in records:
            handle.write(json.dumps(record, ensure_ascii=False) + "\n")

    (OUTPUT_DIR / "index.json").write_text(
        json.dumps(index, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(f"\n법령 {len(index)}건 / 레코드 {len(records)}건 → {corpus_path}")


def rebuild() -> None:
    """API를 호출하지 않고 raw/ 원본만으로 코퍼스를 다시 만든다.

    파서를 고쳤을 때, 또는 API가 IP 차단된 동안 사용한다.
    raw/ 를 보관하는 이유가 바로 이것이다.
    """
    raw_dir = OUTPUT_DIR / "raw"
    files = sorted(raw_dir.glob("*.json"))
    if not files:
        raise SystemExit(f"원본이 없습니다: {raw_dir}\n먼저 실행하세요: python -m law.collect")

    previous = {}
    index_path = OUTPUT_DIR / "index.json"
    if index_path.exists():
        previous = {row["법령명"]: row for row in json.loads(index_path.read_text(encoding="utf-8"))}

    records: list[dict] = []
    index: list[dict] = []
    for path in files:
        law = json.loads(path.read_text(encoding="utf-8"))
        name = path.stem
        mst = previous.get(name, {}).get("MST", "")
        new = list(iter_records(law, mst))
        records.extend(new)
        articles = sum(1 for r in new if r["level"] == "조")
        index.append(
            {
                "법령명": name,
                "법령구분": previous.get(name, {}).get("법령구분", ""),
                "MST": mst,
                "시행일자": squash(law.get("기본정보", {}).get("시행일자")),
                "조": articles,
                "항": len(new) - articles,
            }
        )
        print(f"  {name:<32} 조 {articles:>3} / 항 {len(new) - articles:>3}")

    write_outputs(records, index)


if __name__ == "__main__":
    args = sys.argv[1:]
    if args and args[0] == "--rebuild":
        rebuild()
    else:
        collect(args or None)
