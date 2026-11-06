#!/usr/bin/env python3
"""Redaction rules for the recorded transcript fixtures (henka-council is public).

A fixture keeps exactly what the session-lifetime deriver reads, unchanged: entry
types and order, parentUuid links, isSidechain, timestamps, usage numbers and every
cost-state number. Everything else is removed or replaced consistently across a
probe's main transcripts, subagent files and hook-time snapshots:

- session ids, entry uuids, requestIds, tool_use ids, prompt ids, agent ids and
  workflow ids become deterministic placeholders;
- model ids become model-a, model-b, ... (message.model and cost-state modelUsage
  keys alike); the literal '<synthetic>' is kept;
- MCP tool names mcp__<server>__<tool> become mcp__srv1__tool1 style placeholders;
- prompt, response, thinking and tool-result text become canary strings that the
  tests assert never reach an event, numbered by text so equal text gets the same
  canary in every file of a probe (a hook-time snapshot stays a byte prefix of its
  final file); tool inputs become {"canary": ...};
- a last-prompt entry keeps its leafUuid and a compact boundary its
  logicalParentUuid, through the uuid placeholders;
- a user command echo keeps only '<command-name>/clear</command-name>' (the deriver
  recognises a /clear-opened session by it); other markup becomes '<redacted/>';
- cwd, paths, URLs, titles, attachments, queued text and every other field are dropped;
- with ``keep_size`` each line also records its original byte length as ``_size`` (a
  number only), so a test can pad the skeleton back to the real file's size.

Used by the scratch build that produced tests/fixtures/transcripts/*; kept here so
the rules can be audited and re-applied after a Claude Code format change.
Stdlib only.
"""
from __future__ import annotations

import json
from typing import Any, Dict, List, Optional, Tuple

Json = Dict[str, Any]
CLEAR = "<command-name>/clear</command-name>"
USAGE_KEYS = ("input_tokens", "output_tokens", "cache_read_input_tokens", "cache_creation_input_tokens")
MODEL_USAGE_KEYS = ("inputTokens", "outputTokens", "cacheReadInputTokens", "cacheCreationInputTokens", "costUSD")
COST_KEYS = ("totalCostUSD", "totalDuration", "totalAPIDuration", "startTime")
KEEP_FLAGS = ("isSidechain", "isMeta", "isCompactSummary", "isApiErrorMessage", "turnOrigin", "promptSource")


class Redactor:
    """One instance per probe, so placeholders stay consistent across its files."""

    def __init__(self, keep_size: bool = False) -> None:
        self.maps: Dict[str, Dict[str, str]] = {}
        self.counters: Dict[str, int] = {}
        self.canaries: Dict[Tuple[str, str], int] = {}
        self.keep_size = keep_size

    def placeholder(self, kind: str, value: str) -> str:
        table = self.maps.setdefault(kind, {})
        if value not in table:
            n = self.counters[kind] = self.counters.get(kind, 0) + 1
            table[value] = {
                "session": f"00000000-0000-4000-8000-{n:012d}",
                "uuid": f"e{n:07d}-0000-4000-8000-000000000000",
                "request": f"req_{n:06d}",
                "tool": f"toolu_{n:06d}",
                "prompt": f"p{n:07d}-0000-4000-8000-000000000000",
                "agent": f"a{n:05d}",
                "workflow": f"wf_{n:04d}",
                "branch": f"branch-{n}",
                "pid": str(1000 + n),
            }[kind]
        return table[value]

    def model(self, value: str) -> str:
        if value == "<synthetic>":
            return value
        table = self.maps.setdefault("model", {})
        if value not in table:
            table[value] = "model-" + "abcdefghijklmnopqrstuvwxyz"[len(table)]
        return table[value]

    def tool_name(self, name: str) -> str:
        if not name.startswith("mcp__"):
            return name
        parts = name.split("__")
        server = parts[1] if len(parts) > 1 else ""
        tool = "__".join(parts[2:]) if len(parts) > 2 else ""
        servers = self.maps.setdefault("mcp_server", {})
        if server not in servers:
            servers[server] = f"srv{len(servers) + 1}"
        tools = self.maps.setdefault("mcp_tool", {})
        key = f"{server}__{tool}"
        if key not in tools:
            tools[key] = f"tool{len(tools) + 1}"
        return f"mcp__{servers[server]}__{tools[key]}"

    def canary(self, kind: str, text: str = "") -> str:
        key = (kind, text)
        if key not in self.canaries:
            self.canaries[key] = len(self.canaries) + 1
        return f"{kind}-CANARY-{self.canaries[key]}"

    # ------------------------------------------------------------------------------

    def _ids(self, entry: Json, out: Json) -> None:
        for key, kind in (("uuid", "uuid"), ("parentUuid", "uuid"), ("requestId", "request"), ("promptId", "prompt")):
            value = entry.get(key)
            if isinstance(value, str) and value:
                out[key] = self.placeholder(kind, value)
            elif key == "parentUuid" and key in entry:
                out[key] = None
        for key in ("logicalParentUuid", "leafUuid"):
            value = entry.get(key)
            if isinstance(value, str) and value:
                out[key] = self.placeholder("uuid", value)
        session = entry.get("sessionId")
        if isinstance(session, str) and session:
            out["sessionId"] = self.placeholder("session", session)

    def _user_text(self, text: str) -> str:
        stripped = text.lstrip()
        if CLEAR in text:
            return CLEAR
        if stripped.startswith("<"):
            return "<redacted/>"
        if stripped.startswith("Caveat:"):
            return "Caveat: redacted"
        if stripped.startswith("[Request interrupted"):
            return "[Request interrupted]"
        return self.canary("PROMPT", text)

    def _blocks(self, blocks: List[Any], role: str) -> List[Json]:
        out: List[Json] = []
        for block in blocks:
            if not isinstance(block, dict):
                continue
            kind = block.get("type")
            if kind == "tool_use":
                item: Json = {"type": "tool_use", "name": self.tool_name(str(block.get("name") or "unknown"))}
                if isinstance(block.get("id"), str):
                    item["id"] = self.placeholder("tool", block["id"])
                item["input"] = {"canary": "TOOL-INPUT-CANARY"}
                out.append(item)
            elif kind == "tool_result":
                item = {"type": "tool_result", "content": self.canary("TOOL-OUTPUT", json.dumps(block.get("content"), sort_keys=True))}
                if isinstance(block.get("tool_use_id"), str):
                    item["tool_use_id"] = self.placeholder("tool", block["tool_use_id"])
                if isinstance(block.get("is_error"), bool):
                    item["is_error"] = block["is_error"]
                out.append(item)
            elif kind == "text":
                text = str(block.get("text", ""))
                out.append({"type": "text", "text": self._user_text(text) if role == "user" else self.canary("RESPONSE", text)})
            elif kind in ("thinking", "redacted_thinking"):
                out.append({"type": "thinking", "thinking": self.canary("THINKING", str(block.get("thinking") or block.get("data") or ""))})
            else:
                out.append({"type": str(kind)})
        return out

    def entry(self, entry: Json) -> Json:
        kind = entry.get("type")
        out: Json = {"type": kind}
        if kind == "cost-state":
            for key in COST_KEYS:
                if key in entry:
                    out[key] = entry[key]
            usage = entry.get("modelUsage")
            if isinstance(usage, dict):
                out["modelUsage"] = {
                    self.model(model): {k: v[k] for k in MODEL_USAGE_KEYS if isinstance(v, dict) and k in v}
                    for model, v in usage.items()
                }
            if isinstance(entry.get("sessionId"), str):
                out["sessionId"] = self.placeholder("session", entry["sessionId"])
            return out
        self._ids(entry, out)
        if isinstance(entry.get("timestamp"), str):
            out["timestamp"] = entry["timestamp"]
        for key in KEEP_FLAGS:
            if key in entry and isinstance(entry[key], (bool, str)):
                out[key] = entry[key]
        for key in ("version", "entrypoint"):
            if isinstance(entry.get(key), str):
                out[key] = entry[key]
        if isinstance(entry.get("gitBranch"), str) and entry["gitBranch"]:
            out["gitBranch"] = self.placeholder("branch", entry["gitBranch"])
        if kind == "queue-operation":
            if isinstance(entry.get("operation"), str):
                out["operation"] = entry["operation"]
        elif kind == "system":
            for key in ("subtype", "retryAttempt", "maxRetries"):
                if key in entry:
                    out[key] = entry[key]
        elif kind == "assistant":
            message = entry["message"] if isinstance(entry.get("message"), dict) else {}
            redacted: Json = {}
            if isinstance(message.get("model"), str):
                redacted["model"] = self.model(message["model"])
            usage = message.get("usage")
            if isinstance(usage, dict):
                redacted["usage"] = {k: usage[k] for k in USAGE_KEYS if k in usage}
            content = message.get("content")
            if isinstance(content, list):
                redacted["content"] = self._blocks(content, "assistant")
            out["message"] = redacted
            for key in ("effort", "thinkingDurationMs"):
                if key in entry:
                    out[key] = entry[key]
        elif kind == "user":
            message = entry["message"] if isinstance(entry.get("message"), dict) else {}
            content = message.get("content")
            if isinstance(content, str):
                out["message"] = {"content": self._user_text(content)}
            elif isinstance(content, list):
                out["message"] = {"content": self._blocks(content, "user")}
            origin = entry.get("origin")
            if isinstance(origin, dict) and isinstance(origin.get("kind"), str):
                out["origin"] = {"kind": origin["kind"]}
            decision = entry.get("permissionDecision")
            if isinstance(decision, dict):
                out["permissionDecision"] = {k: decision[k] for k in ("decision", "source", "reasonType") if k in decision}
            elif isinstance(decision, str):
                out["permissionDecision"] = decision
            if isinstance(entry.get("toolDenialKind"), str):
                out["toolDenialKind"] = entry["toolDenialKind"]
        return out

    def line(self, raw: bytes) -> Optional[bytes]:
        """One redacted JSONL line (compact separators, as Claude Code writes them)."""
        try:
            entry = json.loads(raw)
        except ValueError:
            return None
        if not isinstance(entry, dict):
            return None
        out = self.entry(entry)
        if self.keep_size:
            out["_size"] = len(raw.rstrip(b"\n")) + 1
        return json.dumps(out, ensure_ascii=False, separators=(",", ":")).encode("utf-8") + b"\n"

    def report(self) -> Json:
        """Counts of what was mapped (never the original values)."""
        report: Json = {kind: len(table) for kind, table in sorted(self.maps.items())}
        report["canary"] = len(self.canaries)
        return report
