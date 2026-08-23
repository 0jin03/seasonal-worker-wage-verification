#!/usr/bin/env python3
"""Run the four-document v6 OCR/parser boundary from a normalized manifest."""

import argparse
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.ocr_pipeline import DEFAULT_MODEL, ROLES, OCRPipeline, package_versions, process_sample  # noqa: E402


def load(path):
    return json.loads(path.read_text(encoding="utf-8"))


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    target = parser.add_mutually_exclusive_group(required=True)
    target.add_argument("--sample-id", action="append", help="Manifest sample ID; repeatable.")
    target.add_argument("--split", choices=("development", "regression", "holdout"), help="Process one manifest split in sample order.")
    parser.add_argument("--manifest", type=Path, required=True, help="Repository-relative or absolute dataset manifest path.")
    parser.add_argument("--schema", type=Path, default=Path("references/R00-R11_최종_JSON_Schema_v6.json"))
    parser.add_argument("--output-dir", type=Path, default=Path("outputs/ocr"))
    parser.add_argument("--device", required=True, help="Explicit Paddle device, for example gpu:0 or cpu.")
    parser.add_argument("--recognition-model", default=DEFAULT_MODEL)
    parser.add_argument("--allow-holdout", action="store_true")
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args(argv)

    manifest_path = args.manifest if args.manifest.is_absolute() else ROOT / args.manifest
    schema_path = args.schema if args.schema.is_absolute() else ROOT / args.schema
    output_root = args.output_dir if args.output_dir.is_absolute() else ROOT / args.output_dir
    manifest, schema = load(manifest_path), load(schema_path)
    if tuple(manifest.get("ocr_scope", [])) != ROLES:
        parser.error(f"manifest ocr_scope must be {ROLES}")
    samples = {sample["sample_id"]: sample for sample in manifest["samples"]}

    selected = []
    sample_ids = args.sample_id or [sample["sample_id"] for sample in manifest["samples"] if sample["split"] == args.split]
    for sample_id in sample_ids:
        sample = samples.get(sample_id)
        if sample is None:
            parser.error(f"unknown sample ID: {sample_id}")
        if sample["split"] == "holdout" and not args.allow_holdout:
            parser.error(f"sealed holdout requires --allow-holdout: {sample_id}")
        documents = {}
        for role in ROLES:
            item = sample["documents"].get(role)
            if not item or item.get("ocr_input") is not True:
                parser.error(f"{sample_id}:{role} is not an approved OCR input")
            path = ROOT / item["path"]
            documents[role] = {"path": path, "source_path": item["path"], "sha256": item["sha256"]}
        selected.append((sample_id, documents))

    print(json.dumps({"device": args.device, "recognition_model": args.recognition_model, **package_versions(args.device)}, ensure_ascii=False))
    runner = OCRPipeline(args.device, args.recognition_model)
    reports = []
    try:
        for sample_id, documents in selected:
            report = process_sample(sample_id, documents, schema, output_root, runner, force=args.force)
            reports.append(report)
            print(json.dumps({"sample_id": sample_id, "status": report["status"], "documents": report["documents"], "parsers": report["parsers"]}, ensure_ascii=False))
    finally:
        runner.close()
    return 0 if all(report["status"] == "success" for report in reports) else 1


if __name__ == "__main__":
    raise SystemExit(main())
