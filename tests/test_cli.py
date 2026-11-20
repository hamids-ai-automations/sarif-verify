"""End-to-end tests for the sarif-verify CLI."""
from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"


class CliTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.dir = Path(self.tmp.name)

    def run_cli(self, *args: str, stdin: str = "") -> subprocess.CompletedProcess:
        env = os.environ.copy()
        env["PYTHONPATH"] = str(SRC) + os.pathsep + env.get("PYTHONPATH", "")
        return subprocess.run(
            [sys.executable, "-m", "sarif_verify", *args],
            cwd=self.dir,
            env=env,
            input=stdin,
            capture_output=True,
            text=True,
            check=False,
        )

    def write(self, name: str, payload: str) -> Path:
        path = self.dir / name
        path.write_text(payload, encoding="utf-8")
        return path

    def test_good_fixture_passes(self) -> None:
        result = self.run_cli("check", str(ROOT / "fixtures" / "good.sarif"))
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("OK", result.stdout)

    def test_broken_document_fails_with_exit_one(self) -> None:
        broken = json.loads((ROOT / "fixtures" / "good.sarif").read_text(encoding="utf-8"))
        broken["runs"][0]["results"][0]["ruleIndex"] = 1
        self.write("broken.sarif", json.dumps(broken))
        result = self.run_cli("check", "broken.sarif")
        self.assertEqual(result.returncode, 1)
        self.assertIn("result-rule-index", result.stdout)
        self.assertIn("FAIL", result.stdout)

    def test_json_output_shape(self) -> None:
        broken = {"version": "2.0.0", "runs": []}
        self.write("bad.sarif", json.dumps(broken))
        result = self.run_cli("check", "--json", "bad.sarif")
        self.assertEqual(result.returncode, 1)
        payload = json.loads(result.stdout)
        self.assertFalse(payload["ok"])
        self.assertGreaterEqual(payload["summary"]["errors"], 2)
        codes = {finding["code"] for finding in payload["findings"]}
        self.assertIn("version", codes)
        self.assertIn("runs", codes)

    def test_strict_promotes_warnings(self) -> None:
        document = json.loads((ROOT / "fixtures" / "good.sarif").read_text(encoding="utf-8"))
        document["runs"][0]["results"][1].pop("locations")
        self.write("warn.sarif", json.dumps(document))
        lenient = self.run_cli("check", "warn.sarif")
        strict = self.run_cli("check", "--strict", "warn.sarif")
        self.assertEqual(lenient.returncode, 0)
        self.assertEqual(strict.returncode, 1)
        self.assertIn("WARN", lenient.stdout)

    def test_invalid_json_exit_two(self) -> None:
        self.write("notjson.sarif", "{nope")
        result = self.run_cli("check", "notjson.sarif")
        self.assertEqual(result.returncode, 2)
        self.assertIn("invalid JSON", result.stderr)

    def test_missing_file_exit_two(self) -> None:
        result = self.run_cli("check", "nope.sarif")
        self.assertEqual(result.returncode, 2)
        self.assertIn("not found", result.stderr)

    def test_stdin_input(self) -> None:
        payload = (ROOT / "fixtures" / "good.sarif").read_text(encoding="utf-8")
        result = self.run_cli("check", "-", stdin=payload)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("OK", result.stdout)

    def test_checks_command_lists_every_check(self) -> None:
        result = self.run_cli("checks")
        self.assertEqual(result.returncode, 0)
        for code in ("version", "runs", "driver-name", "result-rule-index", "uri-relative"):
            self.assertIn(code, result.stdout)

    def test_version(self) -> None:
        version = self.run_cli("version")
        self.assertEqual(version.returncode, 0)
        self.assertRegex(version.stdout.strip(), r"^\d+\.\d+\.\d+$")

    def test_demo_entry_point_exits_one(self) -> None:
        env = os.environ.copy()
        env["PYTHONPATH"] = str(SRC)
        result = subprocess.run(
            [sys.executable, "-m", "sarif_verify.demo"],
            cwd=self.dir,
            env=env,
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(result.returncode, 1)
        self.assertIn("result-rule-index", result.stdout)
        self.assertIn("uri-relative", result.stdout)
        self.assertIn("exit code 1 as expected", result.stdout)


if __name__ == "__main__":
    unittest.main()
