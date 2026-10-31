"""Shared helpers for the council's hook scripts.

Used by scripts/log-tool-call.py (PostToolUse) and scripts/session-diagnostics.py
(SessionEnd). Stdlib only: hooks run on every tool call and must never fail or
pull in a dependency that is missing on a host.
"""
from __future__ import annotations

import json
import os
import pathlib
import subprocess
import sys
import uuid
from datetime import datetime, timezone
from typing import Any, Optional


def read_payload() -> dict:
    """Return the hook payload from stdin as a dict; {} when absent or malformed."""
    try:
        raw = sys.stdin.read()
    except Exception:
        return {}
    if not raw or not raw.strip():
        return {}
    try:
        data = json.loads(raw)
    except Exception:
        return {}
    return data if isinstance(data, dict) else {}


def resolve_root(cwd: Optional[str]) -> pathlib.Path:
    """Project root for anchoring council paths.

    Priority: CLAUDE_PROJECT_DIR (set by Claude Code at hook-fire time) -> the
    nearest ancestor of the payload cwd that holds a .git marker (dir or file,
    so worktrees count) -> the payload cwd itself. The process cwd is never
    used: resolving against it created phantom .council/ directories
    (HK-0005/HK-0020).
    """
    env_root = os.environ.get("CLAUDE_PROJECT_DIR")
    if env_root:
        return pathlib.Path(env_root.rstrip("/\\"))
    start = pathlib.Path(cwd) if cwd else pathlib.Path.cwd()
    for candidate in (start, *start.parents):
        if (candidate / ".git").exists():
            return candidate
    return start


def council_dir(root: pathlib.Path) -> Optional[pathlib.Path]:
    """<root>/.council when it already exists, else None (never created here)."""
    council = root / ".council"
    return council if council.is_dir() else None


def sprint_context(root: pathlib.Path) -> Any:
    """current_sprint from <root>/.harness/sprint-state.json, or None."""
    path = root / ".harness" / "sprint-state.json"
    try:
        data = json.loads(path.read_text(encoding="utf-8-sig"))
    except Exception:
        return None
    value = data.get("current_sprint") if isinstance(data, dict) else None
    return value if isinstance(value, (int, str)) and not isinstance(value, bool) else None


def now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def new_hex(length: int = 16) -> str:
    return uuid.uuid4().hex[:length]


def git_output(root: pathlib.Path, *args: str) -> Optional[str]:
    try:
        completed = subprocess.run(
            ["git", "-C", str(root), *args],
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        )
    except Exception:
        return None
    if completed.returncode != 0:
        return None
    value = completed.stdout.strip()
    return value or None


def append_jsonl(path: pathlib.Path, record: dict) -> None:
    """Append one compact JSON line (UTF-8, LF). Creates only the parent directory."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8", newline="\n") as handle:
        handle.write(json.dumps(record, ensure_ascii=False) + "\n")


def truncate(value: str, limit: int = 160) -> str:
    return value if len(value) <= limit else value[:limit]
