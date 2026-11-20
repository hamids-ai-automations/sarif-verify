"""Self-contained demo: build a deliberately broken SARIF log and validate it.

Run ``python -m sarif_verify.demo`` (or ``make demo``) to see the validator
reject a document with the four mistakes that break code-scanning uploads:
a wrong ruleIndex, an unknown ruleId, an absolute artifact URI and an
impossible line range.
"""
from __future__ import annotations

import sys

from .validator import validate

BROKEN = {
    "version": "2.1.0",
    "runs": [
        {
            "tool": {
                "driver": {
                    "name": "demo-scanner",
                    "version": "0.1.0",
                    "rules": [
                        {"id": "missing-key"},
                        {"id": "empty-value"},
                    ],
                }
            },
            "columnKind": "utf16CodeUnits",
            "results": [
                {
                    "ruleId": "empty-value",
                    "ruleIndex": 0,
                    "level": "error",
                    "message": {"text": "key API_TOKEN has an empty value"},
                    "locations": [
                        {
                            "physicalLocation": {
                                "artifactLocation": {"uri": "C:/repo/.env"},
                                "region": {"startLine": 0},
                            }
                        }
                    ],
                },
                {
                    "ruleId": "not-a-rule",
                    "level": "warning",
                    "message": {"text": "key DEBUG is set but undocumented"},
                },
            ],
        }
    ],
}


def main() -> int:
    report = validate(BROKEN, "<demo>")
    print("sarif-verify demo: validating a deliberately broken log")
    for finding in report.findings:
        print(f"  {finding.level.upper():5} {finding.code}: {finding.message}")
    print(f"result: {len(report.errors)} error(s), {len(report.warnings)} warning(s)")
    if report.ok:
        print("unexpected: the demo document should not validate")
        return 1
    print("exit code 1 as expected - a CI job would stop here before uploading")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
