#!/usr/bin/env python3
"""SessionEnd diagnostics: one ``session`` event per Claude Code session.

Reads the native hook payload from stdin (``session_id``, ``transcript_path``,
``cwd``, ``reason``, ``permission_mode``), reads the session transcript, and
appends one event conforming to ``schemas/diagnostic-event.schema.json`` to
``<root>/.council/diagnostics.jsonl`` (ADR-0006 in cloud-catcher).

What is measured, and from where:

- token usage per model from the transcript's assistant entries, **deduplicated
  by ``requestId``**: Claude Code writes one entry per content block and repeats
  the same ``message.usage`` on each, so a naive sum overcounts several times;
- cost from the transcript's last ``cost-state`` entry when present
  (``cost_source: claude-code-estimate``), else no cost (never a guess);
- tool calls by tool, tool failures, subagent launches, compactions, permission
  denials, and andon mentions, from content blocks and system entries;
- sidechain (subagent) usage split, thinking time, turn count, model, effort.

Privacy: no prompt or response text is ever copied into the event.
Invariants: root from ``CLAUDE_PROJECT_DIR`` or the payload cwd; writes only when
``<root>/.council`` exists (``DIAGNOSTICS_LOG_PATH`` overrides for tests);
always exits 0.

Invoked by hooks/session-diagnostics.sh and hooks/win/session-diagnostics.ps1.
"""
from __future__ import annotations

import collections
import json
import os
import pathlib
import sys
import uuid

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from _hooklib import (  # noqa: E402
    append_jsonl,
    council_dir,
    git_output,
    now_iso,
    read_payload,
    resolve_root,
    sprint_context,
)

SCHEMA_PATH = pathlib.Path(__file__).resolve().parent.parent / "schemas" / "diagnostic-event.schema.json"
USAGE_KEYS = ("input_tokens", "output_tokens", "cache_read_input_tokens", "cache_creation_input_tokens")
MODEL_USAGE_MAP = {
    "inputTokens": "input_tokens",
    "outputTokens": "output_tokens",
    "cacheReadInputTokens": "cache_read_input_tokens",
    "cacheCreationInputTokens": "cache_creation_input_tokens",
}
SUBAGENT_TOOLS = {"Agent", "Task"}


def _zero() -> dict:
    return {key: 0 for key in USAGE_KEYS}


def _add(into: dict, usage: dict) -> None:
    for key in USAGE_KEYS:
        value = usage.get(key)
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            into[key] += int(value)


def _iter_entries(path: pathlib.Path):
    with path.open("r", encoding="utf-8", errors="replace") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            try:
                entry = json.loads(line)
            except Exception:
                continue
            if isinstance(entry, dict):
                yield entry


def _content_blocks(entry: dict) -> list:
    message = entry.get("message")
    if not isinstance(message, dict):
        return []
    content = message.get("content")
    return [b for b in content if isinstance(b, dict)] if isinstance(content, list) else []


def _effort_of(entry: dict):
    effort = entry.get("effort")
    if isinstance(effort, dict):
        effort = effort.get("level")
    return effort if isinstance(effort, str) else None


def analyze_transcript(path: pathlib.Path) -> dict:
    """Return the measured facts of one transcript (pure; no I/O beyond reading it)."""
    per_request: dict = {}
    sidechain_requests: set = set()
    model_by_request: dict = {}
    thinking_ms = 0
    efforts: collections.Counter = collections.Counter()
    tool_calls: collections.Counter = collections.Counter()
    tool_failures = 0
    subagents = 0
    compactions = 0
    api_retries = 0
    permission_denials = 0
    andon_signals = 0
    prompts = 0
    cost_state = None
    session_id = None
    git_branch = None
    version = None
    entrypoint = None
    seen_thinking_requests: set = set()

    for entry in _iter_entries(path):
        kind = entry.get("type")
        session_id = session_id or entry.get("sessionId")
        git_branch = entry.get("gitBranch") or git_branch
        version = entry.get("version") or version
        entrypoint = entry.get("entrypoint") or entrypoint

        if kind == "assistant":
            message = entry.get("message") if isinstance(entry.get("message"), dict) else {}
            request_id = entry.get("requestId") or entry.get("uuid")
            usage = message.get("usage")
            if isinstance(usage, dict) and request_id:
                per_request[request_id] = usage  # identical across the request's entries
                model_by_request[request_id] = message.get("model")
                if entry.get("isSidechain"):
                    sidechain_requests.add(request_id)
            effort = _effort_of(entry)
            if effort:
                efforts[effort] += 1
            thinking = entry.get("thinkingDurationMs")
            if isinstance(thinking, (int, float)) and request_id and request_id not in seen_thinking_requests:
                thinking_ms += int(thinking)
                seen_thinking_requests.add(request_id)
            for block in _content_blocks(entry):
                block_type = block.get("type")
                if block_type == "tool_use":
                    name = str(block.get("name") or "unknown")
                    tool_calls[name] += 1
                    if name in SUBAGENT_TOOLS:
                        subagents += 1
                elif block_type == "text" and "andon_signal" in str(block.get("text", "")):
                    andon_signals += 1

        elif kind == "user":
            blocks = _content_blocks(entry)
            results = [b for b in blocks if b.get("type") == "tool_result"]
            tool_failures += sum(1 for b in results if b.get("is_error"))
            if entry.get("permissionDecision") in ("deny", "blocked", "rejected"):
                permission_denials += 1
            if entry.get("isCompactSummary"):
                compactions += 1
            message = entry.get("message") if isinstance(entry.get("message"), dict) else {}
            if not results and not entry.get("isMeta"):
                content = message.get("content")
                if isinstance(content, str) or any(b.get("type") == "text" for b in blocks):
                    prompts += 1

        elif kind == "system":
            subtype = str(entry.get("subtype") or "")
            if "compact" in subtype:
                compactions += 1
            elif subtype == "api_retry":
                api_retries += 1

        elif kind == "cost-state":
            cost_state = entry

    totals = _zero()
    sidechain = _zero()
    by_model: dict = {}
    output_by_model: collections.Counter = collections.Counter()
    for request_id, usage in per_request.items():
        _add(totals, usage)
        model = model_by_request.get(request_id) or "unknown"
        by_model.setdefault(model, _zero())
        _add(by_model[model], usage)
        output_by_model[model] += int(usage.get("output_tokens") or 0)
        if request_id in sidechain_requests:
            _add(sidechain, usage)

    cost_usd = None
    cost_source = None
    duration_ms = None
    api_duration_ms = None
    if isinstance(cost_state, dict):
        total_cost = cost_state.get("totalCostUSD")
        if isinstance(total_cost, (int, float)):
            cost_usd = round(float(total_cost), 6)
            cost_source = "claude-code-estimate"
        for key, target in (("totalDuration", "duration_ms"), ("totalAPIDuration", "api_duration_ms")):
            value = cost_state.get(key)
            if isinstance(value, (int, float)):
                if target == "duration_ms":
                    duration_ms = int(value)
                else:
                    api_duration_ms = int(value)
        model_usage = cost_state.get("modelUsage")
        if isinstance(model_usage, dict) and model_usage:
            # Claude Code's own per-model accounting is authoritative when present.
            by_model = {}
            for model, usage in model_usage.items():
                if not isinstance(usage, dict):
                    continue
                converted = _zero()
                for camel, snake in MODEL_USAGE_MAP.items():
                    value = usage.get(camel)
                    if isinstance(value, (int, float)):
                        converted[snake] = int(value)
                by_model[model] = converted
                output_by_model[model] = max(output_by_model[model], converted["output_tokens"])

    model = output_by_model.most_common(1)[0][0] if output_by_model else None
    effort = efforts.most_common(1)[0][0] if efforts else None

    return {
        "session_id": session_id,
        "git_branch": git_branch,
        "version": version,
        "entrypoint": entrypoint,
        "usage": totals,
        "usage_by_model": by_model,
        "sidechain_usage": sidechain,
        "model": model,
        "effort": effort,
        "effort_levels": sorted(efforts),
        "cost_usd": cost_usd,
        "cost_source": cost_source,
        "duration_ms": duration_ms,
        "api_duration_ms": api_duration_ms,
        "thinking_duration_ms": thinking_ms,
        "num_turns": prompts,
        "counts": {
            "tool_calls": int(sum(tool_calls.values())),
            "tool_calls_by_tool": dict(tool_calls),
            "tool_failures": tool_failures,
            "subagents": subagents,
            "compactions": compactions,
            "api_retries": api_retries,
            "permission_denials": permission_denials,
            "andon_signals": andon_signals,
        },
    }


def build_event(payload: dict, root: pathlib.Path, facts: dict) -> dict:
    labels = {}
    for key, value in (
        ("end_reason", payload.get("reason")),
        ("permission_mode", payload.get("permission_mode")),
        ("claude_code_version", facts.get("version")),
        ("entrypoint", facts.get("entrypoint")),
        ("hook_event", payload.get("hook_event_name")),
    ):
        if isinstance(value, str) and value:
            labels[key] = value[:80]
    if len(facts.get("effort_levels") or []) > 1:
        labels["effort_levels"] = ",".join(facts["effort_levels"])[:80]

    sprint = sprint_context(root)
    event = {
        "schema_version": "1.0",
        "event_id": str(uuid.uuid4()),
        "ts": now_iso(),
        "source": "claude-code-session",
        "kind": "session",
        "project": root.name,
        "session_id": payload.get("session_id") or facts.get("session_id"),
        "sprint": sprint,
        "git_branch": facts.get("git_branch") or git_output(root, "rev-parse", "--abbrev-ref", "HEAD"),
        "head": git_output(root, "rev-parse", "HEAD"),
        "model": facts.get("model"),
        "effort": facts.get("effort") if facts.get("effort") in ("low", "medium", "high", "xhigh", "max") else None,
        "usage": facts["usage"],
        "usage_by_model": facts["usage_by_model"],
        "sidechain_usage": facts["sidechain_usage"],
        "cost_usd": facts.get("cost_usd"),
        "cost_source": facts.get("cost_source"),
        "duration_ms": facts.get("duration_ms"),
        "api_duration_ms": facts.get("api_duration_ms"),
        "thinking_duration_ms": facts.get("thinking_duration_ms"),
        "num_turns": facts.get("num_turns"),
        "counts": facts["counts"],
        "outcome": "ended",
        "labels": labels,
    }
    return event


def validate(event: dict) -> None:
    """Raise if the event violates the schema; silently pass when jsonschema is absent."""
    try:
        import jsonschema  # type: ignore
    except Exception:
        return
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    jsonschema.Draft7Validator(schema).validate(event)


def main() -> int:
    payload = read_payload()
    if not payload:
        return 0
    transcript = payload.get("transcript_path")
    if not isinstance(transcript, str) or not transcript:
        return 0
    transcript_path = pathlib.Path(transcript)
    if not transcript_path.is_file():
        return 0

    override = os.environ.get("DIAGNOSTICS_LOG_PATH")
    root = resolve_root(payload.get("cwd") if isinstance(payload.get("cwd"), str) else None)
    if override:
        target = pathlib.Path(override)
    else:
        council = council_dir(root)
        if council is None:
            return 0  # council not initialized here: record nothing, create nothing
        target = council / "diagnostics.jsonl"

    facts = analyze_transcript(transcript_path)
    event = build_event(payload, root, facts)
    try:
        validate(event)
    except Exception as exc:
        print(f"session-diagnostics: event rejected by schema, nothing written: {exc}", file=sys.stderr)
        return 0
    append_jsonl(target, event)
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as exc:  # diagnostics must never block a session
        print(f"session-diagnostics: {exc}", file=sys.stderr)
        sys.exit(0)
