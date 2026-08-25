import json
import tempfile
import unittest
from unittest.mock import patch
from decimal import Decimal
from datetime import date
from pathlib import Path

from vitamin.io import load_case
from vitamin.pipeline import VitaminPipeline
from vitamin.rules import RuleEngine
from vitamin.holidays import PublicHolidayClient
from vitamin.server import _json_safe
from law import casestudy
from law.explain import explain_section, TEMPERATURE
from law.prompt import PROMPT_VERSION, SYSTEM
from law.retrieval import BM25_MIN_SCORE, Corpus, evidence


REPOSITORY = Path(__file__).parents[1]
WORKSPACE = REPOSITORY.parents[1]
DATA_ROOTS = (
    REPOSITORY / "계절근로자_정상케이스_30세트",
    WORKSPACE / "합성데이터",
)


def first_v4_case() -> Path:
    for data_root in DATA_ROOTS:
        if not data_root.is_dir():
            continue
        for path in data_root.rglob("*.json"):
            payload = json.loads(path.read_text(encoding="utf-8"))
            if set(payload.get("documents", {})) >= {
                "contract", "timesheet", "payslip", "bank_statement"
            }:
                return path
    raise FileNotFoundError("v4 합성데이터를 찾지 못했습니다.")


class PipelineTest(unittest.TestCase):
    def test_json_boundary_keeps_decimal_as_number(self):
        self.assertEqual(_json_safe(Decimal("176")), 176)
        self.assertEqual(_json_safe(Decimal("0.5")), 0.5)

    def test_rag_uses_fixed_mapping_and_bm25_supplement(self):
        result = evidence(Corpus.load(), "R08")
        self.assertTrue(result["근거조항"])
        self.assertFalse(result["근거미발견"])
        self.assertTrue(all(item["역할"] == "검색" for item in result["검색조항"]))
        self.assertTrue(all(item["점수"] >= BM25_MIN_SCORE for item in result["검색조항"]))
        self.assertTrue(all(item["출처"].startswith("https://www.law.go.kr/") for item in result["근거조항"]))
        self.assertTrue(all(item["수집일"] for item in result["근거조항"]))

    def test_latest_prompt_is_external_and_deterministic(self):
        self.assertEqual(PROMPT_VERSION, "2026-08-23-v1")
        self.assertEqual(TEMPERATURE, 0.0)
        self.assertIn("근거 조문을 찾지 못했습니다", SYSTEM)

    def test_missing_mapped_law_is_reported_without_crashing(self):
        corpus = Corpus.load()
        result = evidence(Corpus([], corpus.collected_at), "R08")
        self.assertTrue(result["근거미발견"])
        self.assertTrue(result["미발견근거"])

    def test_irrelevant_low_score_bm25_is_not_exposed(self):
        result = evidence(Corpus.load(), "R04", 상황="숙박비 공제액이 계약과 다릅니다")
        self.assertTrue(all(item["점수"] >= BM25_MIN_SCORE for item in result["검색조항"]))

    def test_not_checkable_has_deterministic_check_item(self):
        payload = json.loads(first_v4_case().read_text(encoding="utf-8"))
        payload["rule_results"]["R00"] = {
            "r00_result": "NOT_CHECKABLE", "r00_reason": "확인 자료가 부족합니다."
        }
        original_label = casestudy.label
        original_source = casestudy.source
        casestudy.label = lambda field: field
        casestudy.source = lambda field: "테스트"
        try:
            report = casestudy.build_case(payload, Corpus.load(), "test")
        finally:
            casestudy.label = original_label
            casestudy.source = original_source
        section = next(item for item in report["불일치"] if item["rule_id"] == "R00")
        self.assertTrue(section["확인사항"])

    def test_llm_empty_checks_are_filled_for_not_checkable(self):
        section = {
            "rule_id": "R00", "검사내용": "문서 연결", "성격": "시스템규칙",
            "판정": "NOT_CHECKABLE", "판정사유": "자료 부족", "비교값": [], "허용오차": [],
            "근거조항": [], "참고조항": [], "조건부조항": [], "검색조항": [],
            "계약서근거": [], "참고자료": [], "검토필요": "", "금지표현": [],
        }
        import law.explain as explain_module
        original = explain_module.call_llm
        explain_module.call_llm = lambda *_: {
            "쉬운설명": ["확인이 필요합니다."], "비교된값": [], "관련공식근거": [],
            "추가확인사항": [], "추가질문": [], "다음행동": ["자료를 확인하세요."],
        }
        try:
            ok, _ = explain_section({"근로자": "", "사업장": "", "산정기간": ""}, section)
        finally:
            explain_module.call_llm = original
        self.assertTrue(ok)
        self.assertTrue(section["확인사항"])

    def test_holiday_business_day_adjustment(self):
        client = PublicHolidayClient("test-key")
        client._cache[(2026, 8)] = {date(2026, 8, 17)}
        self.assertEqual(
            client.adjusted_business_day(date(2026, 8, 15), "next_business_day"),
            date(2026, 8, 18),
        )
        self.assertEqual(
            client.adjusted_business_day(date(2026, 8, 15), "previous_business_day"),
            date(2026, 8, 14),
        )
        self.assertEqual(
            client.adjacent_business_days(date(2026, 8, 15)),
            {date(2026, 8, 14), date(2026, 8, 18)},
        )

    def test_encoded_holiday_api_key_is_decoded_once(self):
        client = PublicHolidayClient("abc%2Bdef%3D")
        self.assertEqual(client.service_key, "abc+def=")

    def test_holiday_api_failure_uses_official_snapshot(self):
        client = PublicHolidayClient("test-key")
        with patch("vitamin.holidays.urllib.request.urlopen", side_effect=OSError("offline")):
            holidays = client.holidays(2026, 7)
        self.assertIn(date(2026, 7, 17), holidays)
        self.assertEqual(
            client.adjusted_business_day(date(2026, 7, 5), "previous_business_day"),
            date(2026, 7, 3),
        )

    def test_v6_compatible_case_runs_all_rules(self):
        report = VitaminPipeline().run(load_case(first_v4_case()))
        self.assertFalse(report.review_required)
        self.assertEqual(
            [item.rule_id for item in report.rules],
            [f"R{i:02d}" for i in range(12)],
        )
        self.assertEqual(set(report.v6_result), {"documents", "derived", "rule_results"})
        self.assertEqual(set(report.v6_result["derived"]), {"common", *(f"R{i:02d}" for i in range(12))})
        self.assertEqual(set(report.v6_result["rule_results"]), {f"R{i:02d}" for i in range(12)})

    def test_only_v6_document_names_are_accepted(self):
        payload = json.loads(first_v4_case().read_text(encoding="utf-8"))
        payload["documents"]["bank"] = payload["documents"].pop("bank_statement")
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "old.json"
            path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "bank_statement"):
                load_case(path)

    def test_confirmed_parameters(self):
        params = RuleEngine.DEFAULT_PARAMETERS
        self.assertEqual(params["param_timesheet_min_coverage"], Decimal("0.90"))
        self.assertEqual(params["param_wage_tolerance"], Decimal("10"))
        self.assertEqual(params["param_gross_base_tolerance"], Decimal("60"))
        self.assertEqual(params["param_gross_hour_tolerance"], Decimal("2"))
        self.assertNotIn("param_hours_tolerance", params)


if __name__ == "__main__":
    unittest.main()
