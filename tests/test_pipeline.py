import json
import tempfile
import unittest
from decimal import Decimal
from datetime import date
from pathlib import Path

from vitamin.io import load_case
from vitamin.pipeline import VitaminPipeline
from vitamin.rules import RuleEngine
from vitamin.holidays import PublicHolidayClient


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
