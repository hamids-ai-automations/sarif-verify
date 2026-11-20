"""Command line interface for sarif-verify."""
from __future__ import annotations

import argparse
import json
import sys
from typing import List, Optional

from . import __version__
from .loader import LoadError, load
from .report import CHECKS, Report
from .validator import summarise, validate

_COLORS = {
    "red": "\033[31m",
    "yellow": "\033[33m",
    "green": "\033[32m",
    "dim": "\033[2m",
    "reset": "\033[0m",
}


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="sarif-verify",
        description="Validate SARIF 2.1.0 logs against the GitHub code-scanning contract.",
    )
    parser.add_argument("--version", action="version", version=f"sarif-verify {__version__}")
    sub = parser.add_subparsers(dest="command", required=True)

    check = sub.add_parser("check", help="validate one or more SARIF files ('-' reads stdin)")
    check.add_argument("files", nargs="+", help="SARIF log paths, or - for stdin")
    check.add_argument("--strict", action="store_true", help="treat warnings as errors")
    check.add_argument("--json", action="store_true", help="machine-readable output")
    check.add_argument("--quiet", action="store_true", help="print only the summary")
    check.add_argument("--no-color", action="store_true", help="disable ANSI colours")
    check.set_defaults(func=cmd_check)

    checks = sub.add_parser("checks", help="list the validation checks")
    checks.set_defaults(func=cmd_checks)

    version = sub.add_parser("version", help="print the version")
    version.set_defaults(func=cmd_version)
    return parser


def _color(text: str, name: str, enabled: bool) -> str:
    return f"{_COLORS[name]}{text}{_COLORS['reset']}" if enabled else text


def _print_report(report: Report, strict: bool, no_color: bool, quiet: bool) -> None:
    color = sys.stdout.isatty() and not no_color
    errors = len(report.errors)
    warnings = len(report.warnings)
    if not quiet:
        for finding in report.findings:
            level = finding.level
            if strict and level == "warning":
                level = "error"
            label = "ERROR" if level == "error" else "WARN "
            painted = _color(label, "red" if level == "error" else "yellow", color)
            where = f" [{finding.path}]" if finding.path else ""
            print(f"{painted} {finding.code}: {finding.message}{_color(where, 'dim', color)}")
    failed = errors > 0 or (strict and warnings > 0)
    summary = f"{errors} error(s), {warnings} warning(s)"
    if failed:
        print(_color(f"FAIL {report.source} | {summary}", "red", color))
    else:
        print(_color(f"OK   {report.source} | {summary}", "green", color))


def cmd_check(args: argparse.Namespace) -> int:
    status = 0
    payload = []
    for path in args.files:
        try:
            document, source = load(path)
        except LoadError as exc:
            print(f"sarif-verify: error: {exc}", file=sys.stderr)
            status = 2
            continue
        report = validate(document, source)
        failed = not report.ok or (args.strict and report.warnings)
        if failed and status == 0:
            status = 1
        if args.json:
            entry = report.to_dict()
            entry["summary"] = summarise(report)
            entry["ok"] = not failed
            payload.append(entry)
        else:
            _print_report(report, args.strict, args.no_color, args.quiet)
    if args.json:
        print(json.dumps(payload[0] if len(payload) == 1 else payload, indent=2))
    return status


def cmd_checks(_args: argparse.Namespace) -> int:
    width = max(len(code) for code in CHECKS)
    for code, meta in CHECKS.items():
        print(f"{code.ljust(width)}  {meta['level'].ljust(7)}  {meta['title']}")
        print(f"{' ' * width}  {_COLORS['dim']}{meta['help']}{_COLORS['reset']}")
    return 0


def cmd_version(_args: argparse.Namespace) -> int:
    print(__version__)
    return 0


def main(argv: Optional[List[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return int(args.func(args))
    except BrokenPipeError:  # pragma: no cover - piping into head
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
