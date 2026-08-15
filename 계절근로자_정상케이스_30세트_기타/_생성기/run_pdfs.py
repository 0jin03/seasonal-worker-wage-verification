# -*- coding: utf-8 -*-
"""정상 케이스 30세트의 4종 PDF를 일괄 생성한다."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
CASE_ROOT = HERE.parent
WORKSPACE = CASE_ROOT.parent
SHARED_GENERATOR = WORKSPACE / "계절근로자_결함케이스_20세트" / "_생성기"
sys.path.insert(0, str(SHARED_GENERATOR))

from pdf_gen import find_cases, generate_case  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="정상 케이스 30세트 PDF 일괄 생성")
    parser.add_argument("--overwrite", action="store_true", help="기존 PDF 덮어쓰기")
    args = parser.parse_args()

    json_paths = find_cases(CASE_ROOT)
    if len(json_paths) != 30:
        raise SystemExit(f"JSON 30개가 필요하지만 {len(json_paths)}개를 찾았습니다.")
    count = 0
    for json_path in json_paths:
        outputs = generate_case(json_path, overwrite=args.overwrite)
        count += len(outputs)
        print(f"OK {json_path.parent.name}: {len(outputs)}개 PDF")
    print(f"완료: {len(json_paths)}개 케이스, PDF {count}개")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

