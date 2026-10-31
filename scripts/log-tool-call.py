#!/usr/bin/env python3
"""PostToolUse audit logger: one schema-valid entry per tool call.

Reads the native Claude Code hook payload from stdin (``tool_name``,
``tool_input``, ``tool_response``, ``cwd``, ``session_id``, ``tool_use_id``,
``agent_id``) and appends an ``audit-log-entry`` to
``<root>/.council/audit-log.jsonl``. Legacy ``tool_args`` envelopes are still
accepted so older fixtures and hosts keep working.

Invariants (HKP-0003, auto-mate/docs/handoff/council-native-hooks):

- the repo root comes from ``CLAUDE_PROJECT_DIR`` or the payload's ``cwd``,
  never the process cwd;
- nothing is written, and no directory is created, unless ``<root>/.council``
  already exists (``AUDIT_LOG_PATH`` overrides the target for tests);
- ``tool_input_summary`` always carries a real value (``file_path=...``,
  ``command=...``, ``pattern=...``, else the first scalar input);
- ``andon_pull_count`` is always ``null``: andon is a policy evaluated over
  the log, not a counter incremented while logging;
- the script always exits 0 and swallows its own errors.

Invoked by hooks/log-tool-call.sh and hooks/win/log-tool-call.ps1.
"""
from __future__ import annotations

import json
import os
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from _hooklib import (  # noqa: E402
    append_jsonl,
    council_dir,
    new_hex,
    now_iso,
    read_payload,
    resolve_root,
    sprint_context,
    truncate,
)

SUMMARY_KEYS = (
    "file_path",
    "command",
    "pattern",
    "path",
    "url",
    "notebook_path",
    "prompt",
    "query",
    "description",
)


def summarize_input(tool_input: object) -> str:
    if not isinstance(tool_input, dict):
        return "no-input"
    for key in SUMMARY_KEYS:
        value = tool_input.get(key)
        if isinstance(value, str) and value:
            return f"{key}={truncate(value)}"
    for key, value in tool_input.items():
        if isinstance(value, (str, int, float, bool)) and not isinstance(value, bool):
            return f"{key}={truncate(str(value))}"
        if isinstance(value, bool):
            return f"{key}={value}"
    return "no-input"


def outcome_of(payload: dict) -> str:
    if payload.get("hook_event_name") == "PostToolUseFailure":
        return "error"
    response = payload.get("tool_response")
    if isinstance(response, dict):
        if response.get("is_error") or response.get("error") or response.get("success") is False:
            return "error"
    return "success"


def is_andon(payload: dict) -> bool:
    blob = json.dumps(
        {"i": payload.get("tool_input"), "r": payload.get("tool_response")},
        ensure_ascii=False,
    ).lower()
    return "andon_signal" in blob


def main() -> int:
    payload = read_payload()
    if not payload:
        return 0

    override = os.environ.get("AUDIT_LOG_PATH")
    root = resolve_root(payload.get("cwd") if isinstance(payload.get("cwd"), str) else None)
    if override:
        target = pathlib.Path(override)
    else:
        council = council_dir(root)
        if council is None:
            return 0  # council not initialized here: log nothing, create nothing
        target = council / "audit-log.jsonl"

    tool_input = payload.get("tool_input")
    if tool_input is None:
        tool_input = payload.get("tool_args")  # legacy envelope shape

    sprint = sprint_context(root)
    entry = {
        "entry_id": f"AUD-{new_hex()}",
        "timestamp": now_iso(),
        "event_type": "andon-signal" if is_andon(payload) else "tool-call",
        "agent_id": str(payload.get("agent_id") or payload.get("agent_type") or "session"),
        "sprint_context": sprint if isinstance(sprint, int) else None,
        "tool_name": str(payload.get("tool_name") or "unknown"),
        "tool_input_summary": summarize_input(tool_input),
        "tool_outcome": outcome_of(payload),
        "andon_pull_count": None,
    }
    session_id = payload.get("session_id")
    if isinstance(session_id, str) and session_id:
        entry["session_id"] = session_id
    tool_use_id = payload.get("tool_use_id")
    if isinstance(tool_use_id, str) and tool_use_id:
        entry["tool_use_id"] = tool_use_id

    append_jsonl(target, entry)
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as exc:  # an audit logger must never block a session
        print(f"log-tool-call: {exc}", file=sys.stderr)
        sys.exit(0)
