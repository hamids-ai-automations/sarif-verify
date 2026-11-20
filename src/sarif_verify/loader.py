"""Load SARIF logs from disk or stdin."""
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any, Tuple


class LoadError(Exception):
    """Raised when a file cannot be read or is not valid JSON."""


def load(path: str) -> Tuple[Any, str]:
    """Return ``(document, source_label)`` for *path* (``-`` means stdin)."""
    if path == "-":
        raw = sys.stdin.read()
        source = "<stdin>"
    else:
        p = Path(path)
        if not p.exists():
            raise LoadError(f"file not found: {p}")
        try:
            raw = p.read_text(encoding="utf-8")
        except OSError as exc:
            raise LoadError(f"cannot read {p}: {exc}") from exc
        source = p.as_posix()
    try:
        return json.loads(raw), source
    except json.JSONDecodeError as exc:
        raise LoadError(f"{source}: invalid JSON ({exc.msg} at line {exc.lineno})") from exc
