"""Shared helpers for the council's hook scripts.

Used by scripts/log-tool-call.py (PostToolUse) and scripts/session-diagnostics.py
(SessionEnd). Stdlib only: hooks run on every tool call and must never fail or
pull in a dependency that is missing on a host.

Crew guard (cloud-catcher ADR-0006 A1 D1.9): when AUTOMATE_RUN is set, auto-mate is
running the session as a crew or gate and commits whatever it leaves behind, so the
council's hooks write nothing (see crew_guard()).
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
    """Return the hook payload from stdin as a dict; {} when absent or malformed.

    Claude Code sends raw UTF-8. stdin is read as bytes and decoded as UTF-8, never
    in the locale's code page. hooks/win/session-diagnostics.ps1 passes the raw bytes
    through, so a non-ASCII cwd or path survives there on Windows too;
    hooks/win/log-tool-call.ps1 still reads stdin as text in PowerShell first.
    """
    try:
        stream = getattr(sys.stdin, "buffer", None)
        raw_bytes = stream.read() if stream is not None else sys.stdin.read().encode("utf-8")
    except Exception:
        return {}
    raw = raw_bytes.decode("utf-8", errors="replace").lstrip("\ufeff")
    if not raw.strip():
        return {}
    try:
        data = json.loads(raw)
    except Exception:
        return {}
    return data if isinstance(data, dict) else {}


def crew_guard() -> bool:
    """True when the council's hooks must write nothing (AUTOMATE_RUN is set)."""
    return bool(os.environ.get("AUTOMATE_RUN"))


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


def governed_root(cwd: Optional[str]) -> Optional[pathlib.Path]:
    """The governed project root: the nearest directory at or above CLAUDE_PROJECT_DIR,
    then at or above the payload cwd, that already holds a .council/ directory.

    Claude Code sets CLAUDE_PROJECT_DIR to the directory the session started in,
    which can be a subdirectory of the governed repo. The walk stops at a git root
    (a .git directory or file) and at the filesystem root; the process cwd is never
    used and nothing is created. None when no governed root is found.
    """
    for start in (os.environ.get("CLAUDE_PROJECT_DIR"), cwd):
        if not start:
            continue
        path = pathlib.Path(start.rstrip("/\\") or start)
        for candidate in (path, *path.parents):
            if (candidate / ".council").is_dir():
                return candidate
            if (candidate / ".git").exists():
                break
    return None


def council_dir(root: pathlib.Path) -> Optional[pathlib.Path]:
    """<root>/.council when it already exists, else None (never created here)."""
    council = root / ".council"
    return council if council.is_dir() else None


def sprint_context(root: pathlib.Path) -> Any:
    """current_sprint from <root>/.harness/sprint-state.json, or None."""
    return harness_context(root)[0]


def harness_context(root: pathlib.Path) -> tuple[Any, Optional[int]]:
    """(current_sprint, current_phase) from <root>/.harness/sprint-state.json.

    Phases reuse sprint numbers, so a sprint is only meaningful with its phase.
    The sprint is an int or a string; the phase an int; anything else is None.
    """
    path = root / ".harness" / "sprint-state.json"
    try:
        data = json.loads(path.read_text(encoding="utf-8-sig"))
    except Exception:
        return None, None
    if not isinstance(data, dict):
        return None, None
    sprint = data.get("current_sprint")
    phase = data.get("current_phase")
    sprint = sprint if isinstance(sprint, (int, str)) and not isinstance(sprint, bool) else None
    phase = phase if isinstance(phase, int) and not isinstance(phase, bool) else None
    return sprint, phase


def now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def new_hex(length: int = 16) -> str:
    return uuid.uuid4().hex[:length]


def git_output(root: pathlib.Path, *args: str, timeout: float = 5.0) -> Optional[str]:
    try:
        completed = subprocess.run(
            ["git", "-C", str(root), *args],
            capture_output=True,
            text=True,
            timeout=timeout,
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
