from __future__ import annotations

import json
import os
import re
import struct
import sys
import tempfile
import traceback
import uuid
from io import BytesIO
from email.parser import BytesParser
from email.policy import default
from http import HTTPStatus
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

from .io import case_from_payload
from .legal import build_legal_explanation
from .pipeline import VitaminPipeline


PROJECT_ROOT = Path(__file__).resolve().parents[2]
UI_ROOT = PROJECT_ROOT / "ui-prototype"
OCR_ROOT = PROJECT_ROOT / "ocr_module"
SCHEMA_PATH = PROJECT_ROOT / "references" / "R00-R11_최종_JSON_Schema_v6.json"
OCR_OUTPUT_ROOT = PROJECT_ROOT / "outputs" / "ocr"
DEMO_REVIEW_ROOT = PROJECT_ROOT / "examples" / "review_demo"
# Paddle의 Windows C++ 추론 엔진은 한글 경로에서 모델 파일을 열지 못한다.
# 영문으로만 구성된 Windows 임시 경로에 전용 캐시를 둔다.
PADDLEX_CACHE_ROOT = Path(tempfile.gettempdir()) / "vitamin-paddlex-cache"
ROLES = ("contract", "timesheet", "payslip", "bank_statement")
OCR_ASSET_PATH = re.compile(r"/api/ocr-asset/(UI-[0-9a-f]{12})/(contract|timesheet|payslip|bank_statement)/(\d+)$")
DEMO_ASSET_PATH = re.compile(r"/api/demo-asset/(contract|timesheet|payslip|bank_statement)/(\d+)$")

_ocr_runner = None


def _json_bytes(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, indent=2, default=str).encode("utf-8")


def _load_ocr_boundary():
    global _ocr_runner
    # 사용자 홈 캐시는 실행 계정에 따라 접근이 막힐 수 있으므로 프로젝트 전용
    # 캐시를 사용한다. PaddleX를 import하기 전에 설정해야 적용된다.
    os.environ["PADDLE_PDX_CACHE_HOME"] = str(PADDLEX_CACHE_ROOT)
    if str(OCR_ROOT) not in sys.path:
        sys.path.insert(0, str(OCR_ROOT))
    from src.ocr_pipeline import OCRPipeline, file_sha256, process_sample

    if _ocr_runner is None:
        device = os.getenv("VITAMIN_OCR_DEVICE", "cpu")
        _ocr_runner = OCRPipeline(device=device)
    return _ocr_runner, file_sha256, process_sample


def _review_assets(sample_id: str) -> dict[str, list[dict[str, Any]]]:
    assets = {}
    for role in ROLES:
        raw_path = OCR_OUTPUT_ROOT / sample_id / "raw" / role / "raw_result.json"
        raw = json.loads(raw_path.read_text(encoding="utf-8"))
        assets[role] = [
            {
                "page": int(page["page_index"]),
                "width": int(page["width"]),
                "height": int(page["height"]),
                "image": f"/api/ocr-asset/{sample_id}/{role}/{int(page['page_index'])}",
            }
            for page in raw["pages"]
        ]
    return assets


def _demo_review_assets() -> dict[str, list[dict[str, Any]]]:
    assets = {}
    for role in ROLES:
        path = DEMO_REVIEW_ROOT / f"{role}_0.png"
        with path.open("rb") as image:
            image.seek(16)
            width, height = struct.unpack(">II", image.read(8))
        assets[role] = [{"page": 0, "width": width, "height": height, "image": f"/api/demo-asset/{role}/0"}]
    return assets


def run_ocr(files: dict[str, tuple[str, bytes]]) -> dict[str, Any]:
    missing = sorted(set(ROLES) - set(files))
    if missing:
        raise ValueError(f"필수 PDF가 없습니다: {', '.join(missing)}")
    runner, file_sha256, process_sample = _load_ocr_boundary()
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    sample_id = f"UI-{uuid.uuid4().hex[:12]}"
    with tempfile.TemporaryDirectory(prefix="vitamin-upload-") as folder:
        upload_root = Path(folder)
        documents = {}
        for role in ROLES:
            filename, content = files[role]
            path = upload_root / f"{role}.pdf"
            path.write_bytes(content)
            documents[role] = {
                "path": path,
                "source_path": filename,
                "sha256": file_sha256(path),
            }
        report = process_sample(
            sample_id,
            documents,
            schema,
            OCR_OUTPUT_ROOT,
            runner,
        )
    canonical_path = OCR_OUTPUT_ROOT / sample_id / "parsed" / "canonical.json"
    provenance_path = OCR_OUTPUT_ROOT / sample_id / "parsed" / "provenance.json"
    if report["status"] != "success" or not canonical_path.exists():
        raise RuntimeError(f"OCR 처리 실패: {report}")
    return {
        "sample_id": sample_id,
        "canonical": json.loads(canonical_path.read_text(encoding="utf-8")),
        "provenance": json.loads(provenance_path.read_text(encoding="utf-8")),
        "review_assets": _review_assets(sample_id),
        "report": report,
    }


class VitaminHandler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(UI_ROOT), **kwargs)

    def end_headers(self):
        # 개발 중 변경된 UI가 브라우저의 이전 HTML/JS 캐시에 가려지지 않게 한다.
        if not self.path.startswith("/api/"):
            self.send_header("Cache-Control", "no-store, no-cache, must-revalidate")
            self.send_header("Pragma", "no-cache")
            self.send_header("Expires", "0")
        super().end_headers()

    def _send_json(self, value: Any, status: int = HTTPStatus.OK):
        body = _json_bytes(value)
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def _send_png(self, path: Path):
        if not path.is_file():
            return self._send_json({"error": "문서 이미지를 찾을 수 없습니다."}, HTTPStatus.NOT_FOUND)
        self._send_png_bytes(path.read_bytes())

    def _send_png_bytes(self, body: bytes):
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", "image/png")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "private, no-store")
        self.end_headers()
        self.wfile.write(body)

    def _send_review_png(self, path: Path, width: int, height: int):
        if not path.is_file():
            return self._send_json({"error": "문서 이미지를 찾을 수 없습니다."}, HTTPStatus.NOT_FOUND)
        from PIL import Image

        output = BytesIO()
        with Image.open(path) as image:
            image.crop((0, 0, width, height)).save(output, "PNG")
        self._send_png_bytes(output.getvalue())

    def _read_json(self) -> dict[str, Any]:
        length = int(self.headers.get("Content-Length", "0"))
        return json.loads(self.rfile.read(length).decode("utf-8"))

    def _read_multipart(self) -> dict[str, tuple[str, bytes]]:
        length = int(self.headers.get("Content-Length", "0"))
        raw = self.rfile.read(length)
        header = f"Content-Type: {self.headers['Content-Type']}\r\nMIME-Version: 1.0\r\n\r\n".encode()
        message = BytesParser(policy=default).parsebytes(header + raw)
        files = {}
        for part in message.iter_parts():
            name = part.get_param("name", header="content-disposition")
            filename = part.get_filename()
            if name and filename:
                files[name] = (filename, part.get_payload(decode=True) or b"")
        return files

    def do_GET(self):
        if self.path == "/api/health":
            return self._send_json({
                "status": "ok",
                "schema": "v6",
                "ocr_device": os.getenv("VITAMIN_OCR_DEVICE", "cpu"),
                "paddlex_cache": str(PADDLEX_CACHE_ROOT),
            })
        if self.path == "/api/demo":
            canonical = json.loads((DEMO_REVIEW_ROOT / "canonical.json").read_text(encoding="utf-8"))
            provenance = json.loads((DEMO_REVIEW_ROOT / "provenance.json").read_text(encoding="utf-8"))
            return self._send_json({"canonical": canonical, "provenance": provenance, "review_assets": _demo_review_assets()})
        demo_asset = DEMO_ASSET_PATH.fullmatch(self.path)
        if demo_asset:
            role, page_text = demo_asset.groups()
            return self._send_png(DEMO_REVIEW_ROOT / f"{role}_{int(page_text)}.png")
        asset = OCR_ASSET_PATH.fullmatch(self.path)
        if asset:
            sample_id, role, page_text = asset.groups()
            page = int(page_text)
            folder = OCR_OUTPUT_ROOT / sample_id / "paddle_viz" / role / f"page_{page + 1:03d}"
            raw = json.loads((OCR_OUTPUT_ROOT / sample_id / "raw" / role / "raw_result.json").read_text(encoding="utf-8"))
            page_info = next(item for item in raw["pages"] if int(item["page_index"]) == page)
            return self._send_review_png(
                folder / f"{role}_{page}_preprocessed_img.png",
                int(page_info["width"]),
                int(page_info["height"]),
            )
        return super().do_GET()

    def do_POST(self):
        try:
            if self.path == "/api/ocr":
                if "multipart/form-data" not in self.headers.get("Content-Type", ""):
                    return self._send_json({"error": "multipart/form-data가 필요합니다."}, HTTPStatus.BAD_REQUEST)
                return self._send_json(run_ocr(self._read_multipart()))
            if self.path == "/api/evaluate":
                payload = self._read_json()
                report = VitaminPipeline(require_review=False).run(
                    case_from_payload(payload, payload.get("case_id"))
                )
                response = report.to_dict()
                if report.v6_result is not None:
                    response["legal_explanation"] = build_legal_explanation(
                        response["result"], report.case_id, payload.get("ui_language", "ko")
                    )
                return self._send_json(response)
            return self._send_json({"error": "지원하지 않는 API입니다."}, HTTPStatus.NOT_FOUND)
        except Exception as exc:
            traceback.print_exc()
            return self._send_json(
                {"error": str(exc), "type": type(exc).__name__},
                HTTPStatus.INTERNAL_SERVER_ERROR,
            )


def main() -> None:
    host = os.getenv("VITAMIN_HOST", "127.0.0.1")
    port = int(os.getenv("VITAMIN_PORT", "8000"))
    server = ThreadingHTTPServer((host, port), VitaminHandler)
    print(f"Vitamin UI + API: http://{host}:{port}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
