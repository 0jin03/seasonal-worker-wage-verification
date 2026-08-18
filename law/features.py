"""표준 피처 사전.

R00-R11_통합_표준피처정의서의 '01_전체_피처사전' 시트를 읽어
필드명(cmp_actual_hours_gap 등)을 사람이 읽는 이름으로 바꾼다.

사전을 손으로 다시 쓰지 않는 이유: 피처정의서가 팀 공통 원본이라
여기서 이름을 따로 관리하면 반드시 어긋난다.
"""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

SPEC_PATH = Path("R00-R11_통합_표준피처정의서_v3.2.xlsx")
SHEET = "01_전체_피처사전"
HEADER_ROW = 3  # 0-based. 위 3줄은 제목·설명·빈 줄.


@dataclass(frozen=True)
class Feature:
    field: str
    한글명: str
    구분: str = ""        # 원본 | 파생
    출처: str = ""        # 계약서 / 근무기록 / 임금명세서 / 입금내역서 / 프로그램 계산
    사용규칙: str = ""
    등급: str = ""
    산출방법: str = ""
    비고: str = ""


@lru_cache(maxsize=1)
def dictionary(path: str | Path = SPEC_PATH) -> dict[str, Feature]:
    import openpyxl

    path = Path(path)
    if not path.exists():
        return {}

    workbook = openpyxl.load_workbook(path, read_only=True, data_only=True)
    sheet = workbook[SHEET]
    features: dict[str, Feature] = {}

    for i, row in enumerate(sheet.iter_rows(values_only=True)):
        if i <= HEADER_ROW:
            continue
        cells = [("" if c is None else str(c).strip()) for c in row]
        cells += [""] * (9 - len(cells))
        field = cells[0]
        if not field or field == "-":
            continue
        features[field] = Feature(
            field=field, 한글명=cells[1], 구분=cells[2], 출처=cells[3],
            사용규칙=cells[5], 등급=cells[6], 산출방법=cells[7], 비고=cells[8],
        )

    workbook.close()
    return features


# 접두어만으로도 출처를 알 수 있다. 사전에 없는 파생 필드의 대비책.
PREFIX_SOURCE = {
    "ct_": "표준근로계약서",
    "ts_": "근무기록부",
    "ps_": "임금명세서",
    "bk_": "입금내역서",
    "calc_": "시스템 계산값",
    "cmp_": "시스템 비교값",
    "cond_": "시스템 조건판정",
    "param_": "팀 기준값",
    "ref_": "외부 기준",
    "usr_": "사용자 확정값",
    "sys_": "시스템 식별자",
}


def label(field: str) -> str:
    """필드명을 한글 항목명으로 바꾼다. 사전에 없으면 필드명을 그대로 돌려준다."""
    feature = dictionary().get(field)
    return feature.한글명 if feature and feature.한글명 else field


def source(field: str) -> str:
    """값이 나온 문서 이름."""
    feature = dictionary().get(field)
    if feature and feature.출처:
        return feature.출처
    for prefix, name in PREFIX_SOURCE.items():
        if field.startswith(prefix):
            return name
    return ""


def describe(field: str) -> Feature | None:
    return dictionary().get(field)
