"""Findings model shared by the validator and the CLI."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional

#: Every check this tool can emit, with the level it reports at by default.
CHECKS: Dict[str, Dict[str, str]] = {
    "document-type": {
        "level": "error",
        "title": "Document is a JSON object",
        "help": "A SARIF log must be a single JSON object.",
    },
    "version": {
        "level": "error",
        "title": "version is 2.1.0",
        "help": "GitHub code scanning only accepts SARIF 2.1.0.",
    },
    "runs": {
        "level": "error",
        "title": "runs is a non-empty array",
        "help": "At least one run is required; an empty runs array is rejected on upload.",
    },
    "driver-name": {
        "level": "error",
        "title": "tool.driver.name is set",
        "help": "Every run needs run.tool.driver.name so results can be attributed.",
    },
    "driver-version": {
        "level": "warning",
        "title": "tool.driver.version is set",
        "help": "Code scanning shows the producing tool version; omitting it hides that context.",
    },
    "rules-id": {
        "level": "error",
        "title": "every rule has a non-empty id",
        "help": "Rules are addressed by id; an empty id cannot be referenced.",
    },
    "rules-duplicate": {
        "level": "error",
        "title": "rule ids are unique",
        "help": "Duplicate rule ids make ruleIndex lookups ambiguous.",
    },
    "result-message": {
        "level": "error",
        "title": "every result has message.text",
        "help": "A result without message.text cannot be displayed.",
    },
    "result-rule": {
        "level": "error",
        "title": "result.ruleId resolves to a rule",
        "help": "ruleId must appear in run.tool.driver.rules.",
    },
    "result-rule-index": {
        "level": "error",
        "title": "result.ruleIndex agrees with ruleId",
        "help": "rules[ruleIndex].id must equal ruleId; a mismatch shifts every annotation.",
    },
    "result-level": {
        "level": "error",
        "title": "result.level is a known value",
        "help": "level must be one of none, note, warning, error.",
    },
    "result-location": {
        "level": "warning",
        "title": "every result carries a location",
        "help": "Results without a physical location cannot be annotated inline.",
    },
    "uri-relative": {
        "level": "error",
        "title": "artifactLocation.uri is repository relative",
        "help": "Absolute paths and file:// URIs are rejected by code scanning.",
    },
    "region-lines": {
        "level": "error",
        "title": "region line numbers are sane",
        "help": "startLine must be >= 1 and endLine must not precede startLine.",
    },
    "column-kind": {
        "level": "error",
        "title": "columnKind is known",
        "help": "columnKind must be utf16CodeUnits or unicodeCodePoints.",
    },
}


@dataclass
class Finding:
    """One validation finding."""

    level: str
    code: str
    path: str
    message: str

    def to_dict(self) -> Dict[str, object]:
        return {
            "level": self.level,
            "code": self.code,
            "path": self.path,
            "message": self.message,
        }


@dataclass
class Report:
    """Validation result for one SARIF document."""

    source: str = ""
    findings: List[Finding] = field(default_factory=list)

    def add(self, code: str, path: str, message: str,
            level: Optional[str] = None) -> None:
        self.findings.append(
            Finding(level=level or CHECKS[code]["level"], code=code,
                    path=path, message=message)
        )

    @property
    def errors(self) -> List[Finding]:
        return [f for f in self.findings if f.level == "error"]

    @property
    def warnings(self) -> List[Finding]:
        return [f for f in self.findings if f.level == "warning"]

    @property
    def ok(self) -> bool:
        return not self.errors

    def stats(self) -> Dict[str, int]:
        return {"errors": len(self.errors), "warnings": len(self.warnings)}

    def to_dict(self) -> Dict[str, object]:
        return {
            "source": self.source,
            "ok": self.ok,
            "summary": self.stats(),
            "findings": [f.to_dict() for f in self.findings],
        }
