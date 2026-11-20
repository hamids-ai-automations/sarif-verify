"""Validator tests: every check gets a failing case and the happy path stays quiet."""
from __future__ import annotations

import copy
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from sarif_verify.validator import validate  # noqa: E402

GOOD = {
    "version": "2.1.0",
    "runs": [
        {
            "tool": {
                "driver": {
                    "name": "envscope",
                    "version": "0.1.1",
                    "rules": [{"id": "missing"}, {"id": "extra"}],
                }
            },
            "columnKind": "utf16CodeUnits",
            "results": [
                {
                    "ruleId": "missing",
                    "ruleIndex": 0,
                    "level": "error",
                    "message": {"text": "missing key API_TOKEN"},
                    "locations": [
                        {
                            "physicalLocation": {
                                "artifactLocation": {"uri": ".env"},
                                "region": {"startLine": 4},
                            }
                        }
                    ],
                },
                {
                    "ruleId": "extra",
                    "ruleIndex": 1,
                    "level": "warning",
                    "message": {"text": "key EXTRA_FLAG is undocumented"},
                    "locations": [
                        {
                            "physicalLocation": {
                                "artifactLocation": {"uri": "config/.env"},
                                "region": {"startLine": 5, "endLine": 5},
                            }
                        }
                    ],
                },
            ],
        }
    ],
}


def with_change(mutator):
    document = copy.deepcopy(GOOD)
    mutator(document)
    return validate(document)


def codes(report):
    return {finding.code for finding in report.findings}


class CleanDocumentTests(unittest.TestCase):
    def test_good_document_has_no_findings(self) -> None:
        report = validate(copy.deepcopy(GOOD))
        self.assertTrue(report.ok)
        self.assertEqual(report.findings, [])
        self.assertEqual(report.stats(), {"errors": 0, "warnings": 0})

    def test_fixture_matches_inline_example(self) -> None:
        import json

        fixture = json.loads((ROOT / "fixtures" / "good.sarif").read_text(encoding="utf-8"))
        self.assertTrue(validate(fixture).ok)


class DocumentTests(unittest.TestCase):
    def test_non_object_document(self) -> None:
        report = validate([1, 2, 3])
        self.assertFalse(report.ok)
        self.assertIn("document-type", codes(report))

    def test_wrong_version(self) -> None:
        report = with_change(lambda d: d.update({"version": "2.0.0"}))
        self.assertIn("version", codes(report))
        self.assertFalse(report.ok)

    def test_missing_version(self) -> None:
        report = with_change(lambda d: d.pop("version"))
        self.assertIn("version", codes(report))

    def test_empty_runs(self) -> None:
        report = with_change(lambda d: d.update({"runs": []}))
        self.assertIn("runs", codes(report))

    def test_runs_not_a_list(self) -> None:
        report = with_change(lambda d: d.update({"runs": {"run": 1}}))
        self.assertIn("runs", codes(report))


class RunTests(unittest.TestCase):
    def test_driver_name_missing(self) -> None:
        report = with_change(lambda d: d["runs"][0]["tool"]["driver"].pop("name"))
        self.assertIn("driver-name", codes(report))

    def test_driver_version_missing_is_a_warning(self) -> None:
        report = with_change(lambda d: d["runs"][0]["tool"]["driver"].pop("version"))
        self.assertTrue(report.ok)
        self.assertEqual(codes(report), {"driver-version"})
        self.assertEqual(report.warnings[0].level, "warning")

    def test_rule_without_id(self) -> None:
        report = with_change(lambda d: d["runs"][0]["tool"]["driver"]["rules"].append({}))
        self.assertIn("rules-id", codes(report))

    def test_duplicate_rule_ids(self) -> None:
        report = with_change(
            lambda d: d["runs"][0]["tool"]["driver"]["rules"].append({"id": "missing"})
        )
        self.assertIn("rules-duplicate", codes(report))

    def test_unknown_column_kind(self) -> None:
        report = with_change(lambda d: d["runs"][0].update({"columnKind": "bytes"}))
        self.assertIn("column-kind", codes(report))


class ResultTests(unittest.TestCase):
    def test_result_without_message(self) -> None:
        report = with_change(lambda d: d["runs"][0]["results"][0].pop("message"))
        self.assertIn("result-message", codes(report))

    def test_empty_message_text(self) -> None:
        report = with_change(lambda d: d["runs"][0]["results"][0].update({"message": {"text": " "}}))
        self.assertIn("result-message", codes(report))

    def test_unknown_rule_id(self) -> None:
        report = with_change(lambda d: d["runs"][0]["results"][0].update({"ruleId": "nope"}))
        self.assertIn("result-rule", codes(report))

    def test_rule_index_mismatch(self) -> None:
        report = with_change(lambda d: d["runs"][0]["results"][0].update({"ruleIndex": 1}))
        self.assertIn("result-rule-index", codes(report))

    def test_rule_index_out_of_range(self) -> None:
        report = with_change(lambda d: d["runs"][0]["results"][0].update({"ruleIndex": 9}))
        self.assertIn("result-rule-index", codes(report))

    def test_unknown_level(self) -> None:
        report = with_change(lambda d: d["runs"][0]["results"][0].update({"level": "fatal"}))
        self.assertIn("result-level", codes(report))

    def test_missing_location_is_a_warning(self) -> None:
        report = with_change(lambda d: d["runs"][0]["results"][1].pop("locations"))
        self.assertTrue(report.ok)
        self.assertEqual(codes(report), {"result-location"})

    def test_missing_uri(self) -> None:
        report = with_change(
            lambda d: d["runs"][0]["results"][0]["locations"][0]["physicalLocation"].pop(
                "artifactLocation"
            )
        )
        self.assertIn("result-location", codes(report))

    def test_absolute_uri(self) -> None:
        for uri in ("/home/runner/work/app/.env", "C:/repo/.env", "file:///tmp/a.sarif"):
            with self.subTest(uri=uri):
                report = with_change(
                    lambda d: d["runs"][0]["results"][0]["locations"][0]["physicalLocation"][
                        "artifactLocation"
                    ].update({"uri": uri})
                )
                self.assertIn("uri-relative", codes(report))

    def test_parent_traversal_uri(self) -> None:
        report = with_change(
            lambda d: d["runs"][0]["results"][0]["locations"][0]["physicalLocation"][
                "artifactLocation"
            ].update({"uri": "../../etc/passwd"})
        )
        self.assertIn("uri-relative", codes(report))

    def test_zero_start_line(self) -> None:
        report = with_change(
            lambda d: d["runs"][0]["results"][0]["locations"][0]["physicalLocation"]["region"].update(
                {"startLine": 0}
            )
        )
        self.assertIn("region-lines", codes(report))

    def test_end_before_start(self) -> None:
        report = with_change(
            lambda d: d["runs"][0]["results"][0]["locations"][0]["physicalLocation"]["region"].update(
                {"startLine": 9, "endLine": 3}
            )
        )
        self.assertIn("region-lines", codes(report))


if __name__ == "__main__":
    unittest.main()
