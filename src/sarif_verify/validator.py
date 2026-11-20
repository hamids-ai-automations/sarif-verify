"""Structural validation of SARIF 2.1.0 logs against the code-scanning contract.

The goal is not to re-implement the full SARIF JSON schema. It is to catch the
mistakes that make an upload fail or produce silently wrong annotations:

* a document or run that does not say it is SARIF 2.1.0,
* results that point at a rule that does not exist, or whose ``ruleIndex`` and
  ``ruleId`` disagree,
* absolute paths or ``file://`` URIs, which code scanning rejects,
* line ranges that cannot be rendered,
* levels and ``columnKind`` values outside the spec's enums.
"""
from __future__ import annotations

import re
from typing import Any, Dict, List

from .report import Report

LEVELS = {"none", "note", "warning", "error"}
COLUMN_KINDS = {"utf16CodeUnits", "unicodeCodePoints"}
_VERSION_RE = re.compile(r"^2\.1\.0$")


def _drive_or_absolute(uri: str) -> bool:
    if uri.startswith("file://"):
        return True
    if uri.startswith("/") or uri.startswith("\\"):
        return True
    if len(uri) > 1 and uri[1] == ":":
        return True
    return ".." in uri.replace("\\", "/").split("/")


def _validate_run(run: Any, index: int, report: Report) -> None:
    where = f"runs[{index}]"
    if not isinstance(run, dict):
        report.add("runs", where, "run is not an object")
        return

    column_kind = run.get("columnKind")
    if column_kind is not None and column_kind not in COLUMN_KINDS:
        report.add("column-kind", f"{where}.columnKind",
                   f"unknown columnKind {column_kind!r}")

    tool = run.get("tool")
    driver = tool.get("driver") if isinstance(tool, dict) else None
    if not isinstance(driver, dict):
        report.add("driver-name", f"{where}.tool.driver",
                   "run.tool.driver is missing")
        driver = {}
    name = driver.get("name")
    if not isinstance(name, str) or not name.strip():
        report.add("driver-name", f"{where}.tool.driver.name",
                   "driver name is empty or missing")
    if not isinstance(driver.get("version"), str) or not driver.get("version"):
        report.add("driver-version", f"{where}.tool.driver.version",
                   "driver version is missing")

    rules = driver.get("rules") or []
    rule_ids: List[str] = []
    if not isinstance(rules, list):
        report.add("rules-id", f"{where}.tool.driver.rules", "rules is not an array")
        rules = []
    for position, rule in enumerate(rules):
        path = f"{where}.tool.driver.rules[{position}]"
        if not isinstance(rule, dict):
            report.add("rules-id", path, "rule is not an object")
            rule_ids.append("")
            continue
        rule_id = rule.get("id")
        if not isinstance(rule_id, str) or not rule_id.strip():
            report.add("rules-id", f"{path}.id", "rule id is empty or missing")
            rule_id = ""
        elif rule_id in rule_ids:
            report.add("rules-duplicate", f"{path}.id",
                       f"duplicate rule id {rule_id!r}")
        rule_ids.append(rule_id)

    results = run.get("results") or []
    if not isinstance(results, list):
        report.add("result-message", f"{where}.results", "results is not an array")
        return
    for position, result in enumerate(results):
        path = f"{where}.results[{position}]"
        if not isinstance(result, dict):
            report.add("result-message", path, "result is not an object")
            continue

        message = result.get("message")
        text = message.get("text") if isinstance(message, dict) else None
        if not isinstance(text, str) or not text.strip():
            report.add("result-message", f"{path}.message.text",
                       "message.text is empty or missing")

        level = result.get("level")
        if level is not None and level not in LEVELS:
            report.add("result-level", f"{path}.level", f"unknown level {level!r}")

        rule_id = result.get("ruleId")
        rule_index = result.get("ruleIndex")
        if rule_index is not None:
            if not isinstance(rule_index, int) or isinstance(rule_index, bool):
                report.add("result-rule-index", f"{path}.ruleIndex",
                           "ruleIndex is not an integer")
            elif rule_index < 0 or rule_index >= len(rule_ids):
                report.add("result-rule-index", f"{path}.ruleIndex",
                           f"ruleIndex {rule_index} is out of range")
            elif rule_id is not None and rule_ids[rule_index] != rule_id:
                report.add(
                    "result-rule-index", f"{path}.ruleIndex",
                    f"ruleIndex {rule_index} points at {rule_ids[rule_index]!r}, "
                    f"not {rule_id!r}",
                )
        if rule_id is not None:
            if not isinstance(rule_id, str) or not rule_id.strip():
                report.add("result-rule", f"{path}.ruleId", "ruleId is not a string")
            elif rule_id not in rule_ids:
                report.add("result-rule", f"{path}.ruleId",
                           f"ruleId {rule_id!r} is not declared in driver.rules")

        locations = result.get("locations")
        if not locations:
            report.add("result-location", path, "result has no locations")
            continue
        if not isinstance(locations, list):
            report.add("result-location", f"{path}.locations", "locations is not an array")
            continue
        for loc_index, location in enumerate(locations):
            loc_path = f"{path}.locations[{loc_index}]"
            physical = location.get("physicalLocation") if isinstance(location, dict) else None
            if not isinstance(physical, dict):
                report.add("result-location", loc_path, "physicalLocation is missing")
                continue
            artifact = physical.get("artifactLocation")
            uri = artifact.get("uri") if isinstance(artifact, dict) else None
            if not isinstance(uri, str) or not uri.strip():
                report.add("result-location", f"{loc_path}.physicalLocation.artifactLocation.uri",
                           "artifactLocation.uri is empty or missing")
            elif _drive_or_absolute(uri):
                report.add("uri-relative", f"{loc_path}.physicalLocation.artifactLocation.uri",
                           f"uri {uri!r} is not repository relative")

            region = physical.get("region")
            if region is None:
                continue
            if not isinstance(region, dict):
                report.add("region-lines", f"{loc_path}.physicalLocation.region",
                           "region is not an object")
                continue
            start = region.get("startLine")
            if not isinstance(start, int) or isinstance(start, bool) or start < 1:
                report.add("region-lines", f"{loc_path}.physicalLocation.region.startLine",
                           f"startLine {start!r} is not a positive integer")
                continue
            end = region.get("endLine")
            if end is not None and (not isinstance(end, int) or isinstance(end, bool)
                                    or end < start):
                report.add("region-lines", f"{loc_path}.physicalLocation.region.endLine",
                           f"endLine {end!r} precedes startLine {start}")


def validate(document: Any, source: str = "<document>") -> Report:
    """Validate a decoded SARIF document and return a :class:`Report`."""
    report = Report(source=source)
    if not isinstance(document, dict):
        report.add("document-type", "", "document is not a JSON object")
        return report

    version = document.get("version")
    if not isinstance(version, str) or not _VERSION_RE.match(version):
        report.add("version", "version", f"version {version!r} is not 2.1.0")

    runs = document.get("runs")
    if not isinstance(runs, list) or not runs:
        report.add("runs", "runs", "runs is missing, empty or not an array")
        return report

    for index, run in enumerate(runs):
        _validate_run(run, index, report)
    return report


def summarise(report: Report) -> Dict[str, int]:
    """Return the counts used by the CLI summary line."""
    stats = report.stats()
    stats["findings"] = len(report.findings)
    return stats
