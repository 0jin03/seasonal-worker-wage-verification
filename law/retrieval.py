"""법령 코퍼스 조회.

두 경로를 제공한다.

    resolve(rule_id)   매핑 테이블이 지정한 근거 조항을 그대로 가져온다. 1차 경로.
    search(query)      BM25 키워드 검색. 매핑에 없는 상황·보조 근거용 2차 경로.

임베딩을 쓰지 않는 이유: 규칙이 R00~R11로 고정된 폐쇄 도메인이라 매핑이 더 정확하고
비용도 들지 않는다. 필요해지면 search()의 시그니처를 유지한 채 내부만 교체하면 된다.
"""

from __future__ import annotations

import json
import math
import re
from collections import Counter
from dataclasses import dataclass
from functools import cached_property
from pathlib import Path

from law import contract, notice
from law.mapping import Law, spec

CORPUS_PATH = Path("법령데이터/corpus.jsonl")

# BM25 파라미터. k1은 용어빈도 포화도, b는 문서길이 정규화 강도.
K1 = 1.5
B = 0.75

# 바이그램은 어절 변형을 잡는 보조 신호일 뿐이다. 가중치를 낮추지 않으면
# '임금'·'근로' 같은 흔한 조각이 점수를 지배해 정작 특징적인 어절이 묻힌다.
BIGRAM_PREFIX = "~"
BIGRAM_WEIGHT = 0.3

WORD = re.compile(r"[가-힣]+|[a-zA-Z]+|\d+")
HANGUL = re.compile(r"^[가-힣]+$")


def tokenize(text: str) -> list[str]:
    """형태소 분석기 없이 한국어를 색인 가능한 토큰으로 자른다.

    한글은 조사·어미 변형이 심해 어절 단위 매칭이 잘 안 된다.
    2글자 이상 어절은 문자 바이그램으로도 펼쳐 부분 일치를 잡되,
    바이그램은 BIGRAM_PREFIX로 구분해 낮은 가중치를 적용한다.
    """
    tokens: list[str] = []
    for word in WORD.findall(text):
        tokens.append(word.lower())
        if HANGUL.match(word) and len(word) > 1:
            tokens.extend(BIGRAM_PREFIX + word[i : i + 2] for i in range(len(word) - 1))
    return tokens


@dataclass
class Citation:
    """근거 한 건. 그대로 출력 JSON에 실을 수 있는 형태."""

    doc_id: str
    인용: str
    본문: str
    법령명: str
    시행일자: str
    역할: str = "primary"
    사유: str = ""
    적용조건: str = ""
    점수: float | None = None

    def to_dict(self) -> dict:
        data = {
            "doc_id": self.doc_id,
            "인용": self.인용,
            "본문": self.본문,
            "법령명": self.법령명,
            "시행일자": self.시행일자,
            "역할": self.역할,
        }
        if self.사유:
            data["사유"] = self.사유
        if self.적용조건:
            data["적용조건"] = self.적용조건
        if self.점수 is not None:
            data["점수"] = round(self.점수, 3)
        return data


class Corpus:
    def __init__(self, records: list[dict]):
        self.records = records
        self._by_key: dict[tuple, dict] = {}
        for record in records:
            key = (
                record["법령명"],
                record["조문번호"],
                record["조문가지번호"],
                record["항번호"],
            )
            self._by_key[key] = record

    @classmethod
    def load(cls, path: Path | str = CORPUS_PATH) -> "Corpus":
        path = Path(path)
        if not path.exists():
            raise FileNotFoundError(
                f"코퍼스가 없습니다: {path}\n먼저 실행하세요: python -m law.collect"
            )
        with path.open(encoding="utf-8") as handle:
            return cls([json.loads(line) for line in handle if line.strip()])

    # --- 1차 경로: 매핑 기반 조회 ---------------------------------------

    def lookup(self, law: Law) -> Citation | None:
        """Law가 가리키는 조·항·호를 실제 본문으로 채운다."""
        record = self._by_key.get(
            (law.법령명, law.조문번호, law.조문가지번호, law.항번호)
        )
        if record is None:
            return None

        인용, 본문 = record["인용"], record["본문"]

        if law.호번호:
            item = next(
                (h for h in record.get("호", []) if h["호번호"] == law.호번호), None
            )
            if item is None:
                return None
            인용 = f"{인용} 제{law.호번호}호"
            본문 = item["본문"]

        return Citation(
            doc_id=record["doc_id"] + (f"|{law.호번호}호" if law.호번호 else ""),
            인용=인용,
            본문=본문,
            법령명=record["법령명"],
            시행일자=record["시행일자"],
            역할=law.역할,
            사유=law.사유,
            적용조건=law.적용조건,
        )

    def resolve(self, rule_id: str) -> list[Citation]:
        """규칙의 법령 근거를 매핑 테이블에서 가져온다."""
        found: list[Citation] = []
        for law in spec(rule_id).법령:
            citation = self.lookup(law)
            if citation is None:
                raise LookupError(
                    f"{rule_id} 매핑이 가리키는 조항을 코퍼스에서 찾지 못했습니다: "
                    f"{law.법령명} 제{law.조문번호}조"
                    + (f" 제{law.항번호}항" if law.항번호 else "")
                    + (f" 제{law.호번호}호" if law.호번호 else "")
                )
            found.append(citation)
        return found

    # --- 2차 경로: BM25 키워드 검색 --------------------------------------

    @cached_property
    def _index(self) -> tuple[list[dict], list[Counter], list[int], dict[str, int], float]:
        """검색 대상 문서에 대한 역색인.

        항이 있는 조는 항 단위로 색인한다(조 레코드는 항의 중복이므로 제외).
        항이 없는 단일 문단 조문은 조 레코드가 유일한 본문이므로 반드시 포함한다.
        """
        docs = [
            r
            for r in self.records
            if r["level"] == "항" or (r["level"] == "조" and not r.get("항개수"))
        ] or self.records
        tfs = [Counter(tokenize(d["본문"])) for d in docs]
        lengths = [sum(tf.values()) for tf in tfs]
        df: dict[str, int] = Counter()
        for tf in tfs:
            df.update(tf.keys())
        avg = sum(lengths) / len(lengths) if lengths else 0.0
        return docs, tfs, lengths, df, avg

    def search(self, query: str, top_k: int = 5, 법령명: str | None = None) -> list[Citation]:
        """BM25로 관련 조항을 찾는다."""
        docs, tfs, lengths, df, avg = self._index
        total = len(docs)
        terms = tokenize(query)
        if not terms or not total:
            return []

        scores: list[tuple[float, int]] = []
        for i, (doc, tf, length) in enumerate(zip(docs, tfs, lengths)):
            if 법령명 and doc["법령명"] != 법령명:
                continue
            score = 0.0
            for term in terms:
                freq = tf.get(term)
                if not freq:
                    continue
                weight = BIGRAM_WEIGHT if term.startswith(BIGRAM_PREFIX) else 1.0
                idf = math.log(1 + (total - df[term] + 0.5) / (df[term] + 0.5))
                score += weight * idf * (freq * (K1 + 1)) / (
                    freq + K1 * (1 - B + B * length / avg)
                )
            if score > 0:
                scores.append((score, i))

        scores.sort(key=lambda pair: -pair[0])
        return [
            Citation(
                doc_id=docs[i]["doc_id"],
                인용=docs[i]["인용"],
                본문=docs[i]["본문"],
                법령명=docs[i]["법령명"],
                시행일자=docs[i]["시행일자"],
                역할="검색",
                점수=score,
            )
            for score, i in scores[:top_k]
        ]


def _reference(ref, 연도: int | str | None) -> dict:
    """참고자료 한 건. 수집키가 있으면 실제 수집값으로 채운다."""
    item = {
        "발행처": ref.발행처,
        "명칭": ref.명칭,
        "사유": ref.사유,
        "역할": ref.역할,
        **({"식별자": ref.식별자} if ref.식별자 else {}),
        **({"주의": ref.주의} if ref.주의 else {}),
    }
    if ref.수집키 != "최저임금고시":
        return item

    if 연도 is None:
        item["주의"] = "적용 연도를 알 수 없어 고시 금액을 확정하지 못했습니다."
        return item

    고시 = notice.minimum_wage(연도)
    if 고시 is None:
        item["주의"] = (
            f"{연도}년 최저임금 고시를 수집하지 못했습니다. "
            "python -m law.notice 로 먼저 수집하세요."
        )
        return item

    item["명칭"] = 고시["행정규칙명"]
    item["식별자"] = 고시["고시번호"]
    item["사유"] = f"{연도}년 시간급 최저임금액 {고시['시간급']:,}원"
    item["기준값"] = {
        "시간급": 고시["시간급"],
        "월환산액": 고시["월환산액"],
        "월환산기준시간수": 고시["월환산기준시간수"],
        "적용기간": f"{고시['적용시작']} ~ {고시['적용종료']}",
    }
    return item


def evidence(corpus: Corpus, rule_id: str, 서식: str = "합성", 연도: int | str | None = None) -> dict:
    """한 규칙의 근거 일체.

    LLM 입력(4단계)과 출력 JSON(5단계)에 그대로 실을 수 있는 형태로 만든다.
    법령·표준계약서·참고자료를 역할별로 나누고, 판정 성격과 설명 제약을 함께 싣는다.

    연도는 최저임금 고시처럼 해마다 바뀌는 근거를 확정하는 데 쓴다(R11).
    """
    rule_id = rule_id.upper()
    rule = spec(rule_id)
    citations = corpus.resolve(rule_id)

    def pick(role: str) -> list[dict]:
        return [c.to_dict() for c in citations if c.역할 == role]

    계약서 = []
    for cc in rule.계약서:
        clause = contract.clause(cc.key)
        계약서.append(
            {
                "인용": contract.cite(cc.key, 서식),
                "공식인용": contract.cite(cc.key, "공식"),
                "확인내용": clause.확인내용,
                "계약필드": list(clause.계약필드),
                "역할": cc.역할,
                "사유": cc.사유,
                "출처": contract.SOURCE,
            }
        )

    참고자료 = [_reference(r, 연도) for r in rule.참고자료]

    return {
        "rule_id": rule_id,
        "검사내용": rule.검사내용,
        "성격": rule.성격,
        "설명방향": rule.설명방향,
        "근거조항": pick("primary"),
        "참고조항": pick("supporting"),
        "조건부조항": pick("conditional"),
        "계약서근거": 계약서,
        "참고자료": 참고자료,
        "금지표현": list(rule.금지표현),
        "검토필요": rule.검토필요,
    }
