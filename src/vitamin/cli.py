from __future__ import annotations

import argparse
import json

from .io import load_case, write_json
from .pipeline import VitaminPipeline


def main() -> int:
    parser = argparse.ArgumentParser(description="4종 문서 OCR JSON을 R00~R11로 검증합니다.")
    parser.add_argument("input", help="통합 OCR JSON 경로")
    parser.add_argument("-o", "--output", help="결과 JSON 경로")
    parser.add_argument("--allow-pending-review", action="store_true", help="사용자 미확정 핵심값도 검증")
    args = parser.parse_args()

    report = VitaminPipeline(require_review=not args.allow_pending_review).run(load_case(args.input))
    result = report.to_dict()
    if args.output:
        write_json(args.output, result)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 2 if result["review_required"] else 0


if __name__ == "__main__":
    raise SystemExit(main())

