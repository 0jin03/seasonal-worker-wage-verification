"""Minimal production boundary for PP-StructureV3 and the four v6 parsers."""

from __future__ import annotations

import hashlib
import json
import shutil
import tempfile
import time
from datetime import datetime, timezone
from importlib import metadata
from pathlib import Path

from src.parsers.bank_parser import parse_bank
from src.parsers.contract_parser import parse_contract
from src.parsers.payslip_parser import parse_payslip
from src.parsers.timesheet_parser import parse_timesheet
from src.schema_validation import schema_errors


ROLES = ("contract", "timesheet", "payslip", "bank_statement")
DEFAULT_MODEL = "korean_PP-OCRv5_mobile_rec"
PIPELINE_OPTIONS = {
    "enable_mkldnn": False,
    "use_doc_orientation_classify": False,
    "use_doc_unwarping": False,
    "use_textline_orientation": False,
    "use_seal_recognition": False,
    "use_table_recognition": True,
    "use_formula_recognition": False,
    "use_chart_recognition": False,
    "use_region_detection": False,
}


def load_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _json_bytes(value) -> bytes:
    return (json.dumps(value, ensure_ascii=False, indent=2) + "\n").encode("utf-8")


def write_json_once(path: Path, value, *, force: bool = False) -> str:
    content = _json_bytes(value)
    existed = path.exists()
    if existed:
        if path.read_bytes() == content:
            return "unchanged"
        if not force:
            raise FileExistsError(f"refusing to overwrite changed output: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_bytes(content)
    temporary.replace(path)
    return "replaced" if existed else "created"


def summarize_pages(pages):
    return {
        "page_count": len(pages),
        "ocr_line_count": sum(len(page.get("overall_ocr_res", {}).get("rec_texts", [])) for page in pages),
        "table_count": sum(len(page.get("table_res_list", [])) for page in pages),
        "table_cell_count": sum(
            len(table.get("cell_box_list", []))
            for page in pages for table in page.get("table_res_list", [])
        ),
    }


def package_versions(device: str):
    paddle_dist = "paddlepaddle-gpu" if device.startswith("gpu") else "paddlepaddle"
    return {
        "paddlepaddle_distribution": paddle_dist,
        "paddlepaddle": metadata.version(paddle_dist),
        "paddleocr": metadata.version("paddleocr"),
        "paddlex": metadata.version("paddlex"),
    }


def paddle_runtime():
    import paddle

    return {
        "compiled_with_cuda": paddle.is_compiled_with_cuda(),
        "cuda_device_count": paddle.device.cuda.device_count(),
        "active_device": paddle.device.get_device(),
    }


class OCRPipeline:
    """One PP-StructureV3 instance reused for every pending document in a run."""

    def __init__(self, device: str, model: str = DEFAULT_MODEL):
        self.device = device
        self.model = model
        self._pipeline = None
        self.initializations = 0
        self.initialization_seconds = 0.0
        payload = json.dumps(
            {"pipeline": "PPStructureV3", "device": device, "model": model, "options": PIPELINE_OPTIONS},
            sort_keys=True,
        ).encode()
        self.settings_sha256 = hashlib.sha256(payload).hexdigest()

    def _ensure_initialized(self):
        if self._pipeline is not None:
            return
        from paddleocr import PPStructureV3

        started = time.perf_counter()
        self._pipeline = PPStructureV3(
            text_recognition_model_name=self.model,
            device=self.device,
            **PIPELINE_OPTIONS,
        )
        self.initialization_seconds = time.perf_counter() - started
        self.initializations = 1

    def infer(self, pdf_path: Path, raw_path: Path, viz_path: Path, source_path: str, expected_sha256: str, *, force=False):
        try:
            actual_sha256 = file_sha256(pdf_path)
        except OSError as exc:
            return None, {
                "status": "failed", "error_code": "input_unreadable",
                "error": f"{type(exc).__name__}: {exc}",
            }
        if actual_sha256 != expected_sha256:
            return None, {
                "status": "failed", "error_code": "manifest_hash_mismatch",
                "error": "input PDF SHA-256 differs from the manifest", "input_sha256": actual_sha256,
            }

        raw_exists = raw_path.exists()
        viz_exists = viz_path.exists() and any(viz_path.rglob("*.png"))
        if raw_exists or viz_path.exists():
            if raw_exists and viz_exists:
                try:
                    cached = load_json(raw_path)
                    cache_ok = (
                        cached.get("input", {}).get("sha256") == actual_sha256
                        and cached.get("ocr", {}).get("settings_sha256") == self.settings_sha256
                        and summarize_pages(cached.get("pages", []))["ocr_line_count"] > 0
                    )
                except (OSError, json.JSONDecodeError):
                    cache_ok = False
                if cache_ok and not force:
                    return cached, {"status": "reused", "input_sha256": actual_sha256, **summarize_pages(cached["pages"])}
            if not force:
                return None, {
                    "status": "failed", "error_code": "existing_output_conflict",
                    "error": "existing raw/viz is incomplete or does not match input/model settings",
                    "input_sha256": actual_sha256,
                }
            if raw_path.parent.exists():
                shutil.rmtree(raw_path.parent)
            if viz_path.exists():
                shutil.rmtree(viz_path)

        started = time.perf_counter()
        temporary_viz = None
        try:
            self._ensure_initialized()
            results = list(self._pipeline.predict(input=str(pdf_path), use_table_orientation_classify=False))
            pages = [result.json["res"] for result in results]
            summary = summarize_pages(pages)
            if not pages or summary["ocr_line_count"] == 0:
                raise ValueError("PP-StructureV3 returned no OCR text lines")
            viz_path.parent.mkdir(parents=True, exist_ok=True)
            temporary_viz = Path(tempfile.mkdtemp(prefix=f".{viz_path.name}-", dir=viz_path.parent))
            for page_number, result in enumerate(results, 1):
                result.save_to_img(str(temporary_viz / f"page_{page_number:03d}"))
            if not any(temporary_viz.rglob("*.png")):
                raise ValueError("PP-StructureV3 official visualization was not created")
            raw = {
                "raw_result_version": "1.0",
                "input": {"path": source_path, "sha256": actual_sha256},
                "ocr": {
                    "pipeline": "PPStructureV3", "device": self.device,
                    "recognition_model": self.model, "settings_sha256": self.settings_sha256,
                },
                "pages": pages,
            }
            write_json_once(raw_path, raw, force=force)
            temporary_viz.replace(viz_path)
            temporary_viz = None
            return raw, {
                "status": "success", "input_sha256": actual_sha256,
                "elapsed_seconds": round(time.perf_counter() - started, 3), **summary,
            }
        except Exception as exc:
            return None, {
                "status": "failed", "error_code": "ocr_inference_failed",
                "error": f"{type(exc).__name__}: {exc}", "input_sha256": actual_sha256,
                "elapsed_seconds": round(time.perf_counter() - started, 3),
            }
        finally:
            if temporary_viz and temporary_viz.exists():
                shutil.rmtree(temporary_viz)

    def close(self):
        if self._pipeline is not None:
            self._pipeline.close()
            self._pipeline = None


def _missing_provenance(role, value, debug):
    collection = {"timesheet": "lines", "payslip": "ps_pay_lines", "bank_statement": "transactions"}.get(role)
    missing = []
    for name, item in value.items():
        if name == collection or item is None:
            continue
        detail = debug.get(name, {})
        if not (detail.get("bbox") or detail.get("roi")):
            missing.append(name)
    if collection:
        rows = value.get(collection) or []
        debug_rows = debug.get(collection, {}).get("rows", [])
        for index, row in enumerate(rows):
            sources = debug_rows[index] if index < len(debug_rows) else {}
            missing.extend(
                f"{collection}[{index}].{name}"
                for name, item in row.items()
                if item is not None and not (sources.get(name, {}).get("bbox") or sources.get(name, {}).get("roi"))
            )
    return missing


def parse_document(role: str, raw: dict, pdf_path: Path, role_schema: dict):
    fields = tuple(role_schema["properties"])
    extra = {}
    if role == "contract":
        value, debug, warnings, checkboxes = parse_contract(raw, pdf_path, fields)
        extra["checkbox_groups"] = checkboxes
    elif role == "timesheet":
        line_fields = tuple(role_schema["properties"]["lines"]["items"]["properties"])
        value, debug, warnings, checkboxes = parse_timesheet(raw, pdf_path, fields, line_fields)
        extra["checkbox_groups"] = checkboxes
    elif role == "payslip":
        value, debug, warnings = parse_payslip(raw, fields)
    elif role == "bank_statement":
        value, debug, warnings = parse_bank(raw, fields)
    else:
        raise ValueError(f"unsupported OCR document role: {role}")
    if tuple(value) != fields:
        raise ValueError(f"{role} parser fields differ from v6 Schema")
    errors = schema_errors(value, role_schema, f"$.documents.{role}")
    missing = _missing_provenance(role, value, debug)
    if errors or missing:
        raise ValueError(f"schema_errors={errors}; missing_provenance={missing}")
    return value, {"fields": debug, "warnings": warnings, **extra}


def process_sample(sample_id: str, documents: dict, schema: dict, output_root: Path, runner: OCRPipeline, *, force=False):
    started = time.perf_counter()
    sample_root = output_root / sample_id
    role_schemas = schema["properties"]["documents"]["properties"]
    canonical, provenance = {"documents": {}}, {"documents": {}}
    report = {
        "sample_id": sample_id, "generated_at": datetime.now(timezone.utc).isoformat(),
        "device": runner.device, "recognition_model": runner.model,
        "versions": package_versions(runner.device), "paddle_runtime": paddle_runtime(),
        "source_case_json_used": False, "pdf_text_layer_used": False,
        "documents": {}, "parsers": {}, "validation": {},
    }
    for role in ROLES:
        document = documents.get(role)
        if not document:
            report["documents"][role] = {"status": "failed", "error_code": "missing_role_input"}
            report["parsers"][role] = {"status": "not_run"}
            continue
        pdf_path = Path(document["path"])
        raw, ocr_status = runner.infer(
            pdf_path,
            sample_root / "raw" / role / "raw_result.json",
            sample_root / "paddle_viz" / role,
            document["source_path"], document["sha256"], force=force,
        )
        report["documents"][role] = ocr_status
        if raw is None:
            report["parsers"][role] = {"status": "not_run", "reason": "OCR unavailable"}
            continue
        try:
            value, source = parse_document(role, raw, pdf_path, role_schemas[role])
            canonical["documents"][role] = value
            provenance["documents"][role] = source
            report["parsers"][role] = {
                "status": "success", "warning_count": len(source["warnings"]),
                "warning_codes": sorted({warning.get("code", "unknown") for warning in source["warnings"]}),
                "row_count": len(value.get("lines") or value.get("ps_pay_lines") or value.get("transactions") or []),
            }
        except Exception as exc:
            report["parsers"][role] = {"status": "failed", "error": f"{type(exc).__name__}: {exc}"}

    document_errors = schema_errors(canonical["documents"], schema["properties"]["documents"], "$.documents")
    report["validation"] = {
        "ocr_documents_schema_valid": not document_errors,
        "schema_errors": document_errors,
        "top_level_schema_validation": "deferred: derived and rule_results are downstream responsibilities",
    }
    report["status"] = "success" if not document_errors and all(
        report["documents"].get(role, {}).get("status") in {"success", "reused"}
        and report["parsers"].get(role, {}).get("status") == "success"
        for role in ROLES
    ) else "partial_failure"
    try:
        report["outputs"] = {
            "canonical": write_json_once(sample_root / "parsed" / "canonical.json", canonical, force=force),
            "provenance": write_json_once(sample_root / "parsed" / "provenance.json", provenance, force=force),
        }
    except FileExistsError as exc:
        report["status"] = "partial_failure"
        report["output_error"] = str(exc)
    report["pipeline_initializations_so_far"] = runner.initializations
    report["pipeline_initialization_seconds"] = round(runner.initialization_seconds, 3)
    report["elapsed_seconds"] = round(time.perf_counter() - started, 3)
    log_dir = sample_root / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    log_name = datetime.now(timezone.utc).strftime("run_%Y%m%dT%H%M%S_%fZ.json")
    (log_dir / log_name).write_bytes(_json_bytes(report))
    report["log_path"] = (log_dir / log_name).relative_to(output_root).as_posix()
    return report
