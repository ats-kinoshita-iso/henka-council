"""Session lifetimes: the one deriver of ``kind: session`` diagnostic events.

cloud-catcher ADR-0006 amendment A1 (decision D1) defines a session event as one
settled *process lifetime*: one Claude Code process's tenure on one session id,
from its start (startup, resume, fork or ``/clear``) to the ``cost-state`` entry
that process writes when it exits. Every measure is a delta over that lifetime.
This module computes those events from the files on disk and nothing else:

- the session transcript ``<session_id>.jsonl``;
- the session's subagent files ``<session_id>/subagents/**/agent-*.jsonl``, read
  only when their time range overlaps a lifetime being measured;
- for a fork, the parent's transcript, found by cost lineage.

It never writes, never reads the clock (except to honour a caller's deadline,
which aborts and never changes a result) and never reads the environment. The
SessionEnd hook and the backfill command (``scripts/session-diagnostics.py``) only
decide when to call it, which lifetimes to select and what context to attach, so
every observer of a lifetime mints the same ``event_id`` and the same numbers.

Stage 1 (SessionEnd only) behaviour, as A1's Verification states it:

- an open lifetime (no closing ``cost-state`` yet) is never recorded;
- a SIGKILLed lifetime gets no event of its own: its entries fall into the next
  lifetime of the same session and show as ``coverage.shortfall``;
- a fork's base comes from cost lineage; a fork whose parent is not found has
  ``cost_usd: null`` and ``coverage.fork_parent: not-found``.

Stdlib only; runs on Python 3.10.
"""
from __future__ import annotations

import calendar
import json
import re
import time
import uuid
from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Set, Tuple

SPEC = "session-lifetime/1"
NAMESPACE = uuid.UUID("5f0c2b8e-2a7d-4d38-9a51-1c2f1d6e2006")
USAGE_KEYS: Tuple[str, ...] = (
    "input_tokens",
    "output_tokens",
    "cache_read_input_tokens",
    "cache_creation_input_tokens",
)
MODEL_USAGE_KEYS: Dict[str, str] = {
    "inputTokens": "input_tokens",
    "outputTokens": "output_tokens",
    "cacheReadInputTokens": "cache_read_input_tokens",
    "cacheCreationInputTokens": "cache_creation_input_tokens",
}
SYNTHETIC_MODEL = "<synthetic>"
SUBAGENT_TOOLS = frozenset({"Agent", "Task"})
TURN_ORIGINS = frozenset({"human", "sdk"})
DENIAL_DECISIONS = frozenset({"reject", "rejected", "deny", "denied", "blocked"})
EFFORT_LEVELS = frozenset({"low", "medium", "high", "xhigh", "max"})
CLEAR_COMMAND = "<command-name>/clear</command-name>"
# A first lifetime whose own entries run past startTime + totalDuration restored
# cost from before its file existed: a fork (probes: forks +1.8 s to +48 s, every
# other first lifetime -4 ms or less).
RESTORED_SLACK_MS = 1000
# Subagent files whose first or last entry is this far outside a window are skipped
# without parsing them; entries are still filtered one by one.
SUBAGENT_RANGE_SLACK_S = 3600.0
COST_DECIMALS = 10
SESSION_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9-]{0,127}$")
TS_RE = re.compile(
    r"^(\d{4})-(\d{2})-(\d{2})T(\d{2}):(\d{2}):(\d{2})(?:\.(\d+))?(Z|[+-]\d{2}:?\d{2})?$"
)

Json = Dict[str, Any]
Usage = Dict[str, int]


class DeadlineExceeded(Exception):
    """Raised when the caller's deadline passes; no partial result is ever returned."""


# --------------------------------------------------------------------------------------
# Small value helpers
# --------------------------------------------------------------------------------------


def _check(deadline: Optional[float]) -> None:
    if deadline is not None and time.monotonic() > deadline:
        raise DeadlineExceeded()


def parse_ts(value: Any) -> Optional[float]:
    """Epoch seconds of an ISO-8601 timestamp such as 2026-11-04T22:20:42.265Z."""
    if not isinstance(value, str):
        return None
    match = TS_RE.match(value.strip())
    if not match:
        return None
    year, month, day, hour, minute, second, frac, tz = match.groups()
    try:
        base = calendar.timegm(
            (int(year), int(month), int(day), int(hour), int(minute), int(second), 0, 0, 0)
        )
        datetime(int(year), int(month), int(day))  # rejects impossible dates
    except (ValueError, OverflowError):
        return None
    seconds = float(base) + (float("0." + frac) if frac else 0.0)
    if tz and tz != "Z":
        sign = 1 if tz[0] == "+" else -1
        digits = tz[1:].replace(":", "")
        seconds -= sign * (int(digits[:2]) * 3600 + int(digits[2:]) * 60)
    return seconds


def int_value(value: Any) -> Optional[int]:
    """An integer, or an integral float, as int; anything else is None."""
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, float) and value.is_integer():
        return int(value)
    return None


def num_value(value: Any) -> Optional[float]:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    return float(value)


def zero_usage() -> Usage:
    return {key: 0 for key in USAGE_KEYS}


def add_usage(into: Usage, usage: Usage) -> None:
    for key in USAGE_KEYS:
        into[key] += usage.get(key, 0)


def event_id_for(session_id: str, anchor: str) -> str:
    """UUIDv5 in A1's namespace over 'session-lifetime|<session_id>|<anchor>'."""
    return str(uuid.uuid5(NAMESPACE, f"session-lifetime|{session_id}|{anchor}"))


def _round_cost(value: float) -> float:
    return round(value, COST_DECIMALS)


# --------------------------------------------------------------------------------------
# Reading transcripts
# --------------------------------------------------------------------------------------

CHAIN = "chain"  # carries a uuid: part of a parentUuid chain
LOOSE = "loose"  # no uuid but a timestamp: queue-operation, api-request, ...
COST = "cost"  # a cost-state entry
BOOK = "book"  # bookkeeping without a timestamp: last-prompt, mode, ai-title, ...


@dataclass
class Row:
    offset: int
    entry: Json
    kind: str
    ts: Optional[float]


def _classify(entry: Json) -> str:
    if entry.get("type") == "cost-state":
        return COST
    uid = entry.get("uuid")
    if isinstance(uid, str) and uid:
        return CHAIN
    if isinstance(entry.get("timestamp"), str):
        return LOOSE
    return BOOK


def parse_rows(data: bytes, deadline: Optional[float] = None) -> List[Row]:
    """Rows of a JSONL transcript. A last line without its newline is still being
    written and is ignored; unparseable lines are skipped."""
    rows: List[Row] = []
    pos = 0
    size = len(data)
    seen = 0
    while pos < size:
        end = data.find(b"\n", pos)
        if end < 0:
            break
        start, line = pos, data[pos:end]
        pos = end + 1
        if not line.strip():
            continue
        seen += 1
        if seen % 512 == 0:
            _check(deadline)
        try:
            entry = json.loads(line)
        except ValueError:
            continue
        if isinstance(entry, dict):
            rows.append(Row(start, entry, _classify(entry), parse_ts(entry.get("timestamp"))))
    return rows


def load_rows(path: Path, deadline: Optional[float] = None) -> List[Row]:
    return parse_rows(path.read_bytes(), deadline)


def stamps(rows: Sequence[Row], indices: Iterable[int], skip: Optional[Set[int]] = None) -> List[float]:
    """The timestamps of the given rows that have one, skipping ``skip``."""
    out: List[float] = []
    for i in indices:
        ts = rows[i].ts
        if ts is not None and (skip is None or i not in skip):
            out.append(ts)
    return out


def _dict(value: Any) -> Json:
    return value if isinstance(value, dict) else {}


# --------------------------------------------------------------------------------------
# Lifetimes inside one transcript (parentUuid regions)
# --------------------------------------------------------------------------------------


@dataclass
class Region:
    """One process lifetime's share of a transcript."""

    index: int
    base: Optional[int]  # row index of the cost-state restored at start; None: nothing
    rows: List[int] = field(default_factory=list)  # activity rows (chain and loose)
    closing: List[int] = field(default_factory=list)  # closing point first, then re-writes
    last_activity: int = -1

    @property
    def settled(self) -> bool:
        return bool(self.closing)


def _cost_totals(entry: Json) -> Tuple[Optional[float], Tuple[Tuple[str, Tuple[Optional[int], ...]], ...]]:
    model_usage = entry.get("modelUsage")
    per_model: List[Tuple[str, Tuple[Optional[int], ...]]] = []
    if isinstance(model_usage, dict):
        for model in sorted(model_usage):
            usage = model_usage[model]
            if isinstance(usage, dict):
                per_model.append((model, tuple(int_value(usage.get(k)) for k in MODEL_USAGE_KEYS)))
    return num_value(entry.get("totalCostUSD")), tuple(per_model)


def segment(rows: Sequence[Row]) -> List[Region]:
    """Split a transcript into lifetimes.

    - A chain entry joins the open lifetime that owns its parent. A parent in a
      closed lifetime means a process resumed after that lifetime ended: a new
      lifetime opens. A parentless entry (a root, a compact boundary) joins the
      open lifetime restored from the same cost-state, else opens one.
    - A loose entry joins the lifetime of the latest activity when that lifetime is
      open; otherwise it waits for the next lifetime (a process's queue-operation
      precedes its first chain entry).
    - A cost-state closes the open lifetime that wrote the latest activity. With no
      activity since the previous cost-state it is a re-write when its totals equal
      the previous one's, else it closes a lifetime of its own (spend without
      entries). Pending loose entries before a cost-state form a lifetime of their own.
    - A lifetime killed before writing its cost-state stays open, and the resume that
      chains to it closes it (Stage 1: its tokens show as shortfall).
    """
    regions: List[Region] = []
    owner: Dict[str, int] = {}
    pending: List[int] = []
    latest: Optional[int] = None  # region of the latest activity; None while pending
    last_cs: Optional[int] = None
    last_closed: Optional[int] = None

    def open_region() -> Region:
        region = Region(index=len(regions), base=last_cs)
        regions.append(region)
        return region

    for i, row in enumerate(rows):
        if row.kind == COST:
            target: Optional[Region] = None
            if pending:
                target = open_region()
                target.rows.extend(pending)
                target.last_activity = pending[-1]
                pending = []
            elif latest is not None:
                candidate = regions[latest]
                since = last_cs if last_cs is not None else -1
                if not candidate.closing and candidate.last_activity > since:
                    target = candidate
            if target is not None:
                target.closing.append(i)
                last_closed = target.index
            elif (
                last_closed is not None
                and last_cs is not None
                and _cost_totals(rows[last_cs].entry) == _cost_totals(row.entry)
            ):
                regions[last_closed].closing.append(i)
            else:
                target = open_region()
                target.closing.append(i)
                last_closed = target.index
            last_cs = i
        elif row.kind == LOOSE:
            if latest is not None and not regions[latest].closing:
                regions[latest].rows.append(i)
                regions[latest].last_activity = i
            else:
                pending.append(i)
                latest = None
        elif row.kind == CHAIN:
            parent = row.entry.get("parentUuid")
            joined: Optional[Region] = None
            if isinstance(parent, str) and parent in owner:
                parent_region = regions[owner[parent]]
                if not parent_region.closing:
                    joined = parent_region
            else:
                for region in reversed(regions):
                    if not region.closing and region.base == last_cs:
                        joined = region
                        break
            if joined is None:
                joined = open_region()
            if pending:
                joined.rows.extend(pending)
                pending = []
            joined.rows.append(i)
            joined.last_activity = i
            owner[row.entry["uuid"]] = joined.index
            latest = joined.index
    for region in regions:
        region.rows.sort()
    return regions


def _concurrent(region: Region, regions: Sequence[Region]) -> bool:
    if len(region.rows) < 2:
        return False
    first, last = region.rows[0], region.rows[-1]
    for other in regions:
        if other.index == region.index:
            continue
        if any(first < i < last for i in other.rows):
            return True
    return False


# --------------------------------------------------------------------------------------
# Forks: cost lineage and the copied prefix
# --------------------------------------------------------------------------------------


@dataclass
class Hints:
    """What a hook saw that is not on disk. Only ever narrows where to look; the
    numbers still come from files."""

    fork: bool = False  # the process command line says --fork-session
    fork_parent_ids: Tuple[str, ...] = ()  # the --resume argument of that command line


@dataclass
class ForkInfo:
    copies: List[int]
    parent_session_id: Optional[str]
    base: Optional[Json]  # the parent's cost-state at the fork; None: not found


def _base_at(parent_rows: Sequence[Row], fork_start: float) -> Optional[Json]:
    """The cost-state a process starting at fork_start restored from the parent: the
    last one before the first parent activity entry written after that instant."""
    last: Optional[Json] = None
    for row in parent_rows:
        if row.kind == COST:
            last = row.entry
        elif row.kind in (CHAIN, LOOSE) and row.ts is not None and row.ts > fork_start:
            break
    return last


def _cost_le(base: Json, end: Json) -> bool:
    base_total, end_total = num_value(base.get("totalCostUSD")), num_value(end.get("totalCostUSD"))
    if base_total is None or end_total is None or base_total > end_total + 1e-9:
        return False
    base_usage, end_usage = base.get("modelUsage"), end.get("modelUsage")
    if not isinstance(base_usage, dict):
        return True
    end_usage = end_usage if isinstance(end_usage, dict) else {}
    for model, usage in base_usage.items():
        if not isinstance(usage, dict):
            continue
        other = end_usage.get(model)
        for key in MODEL_USAGE_KEYS:
            low = int_value(usage.get(key)) or 0
            high = int_value(other.get(key)) if isinstance(other, dict) else 0
            if low > (high or 0):
                return False
    return True


def _fork_candidates(path: Path, hints: Hints, projects_root: Optional[Path]) -> Tuple[List[Path], List[Path]]:
    own = path.resolve()
    near: List[Path] = []
    if projects_root is not None:
        for parent_id in hints.fork_parent_ids:
            if SESSION_ID_RE.match(parent_id):
                near.extend(sorted(projects_root.glob(f"*/{parent_id}.jsonl")))
    near.extend(sorted(path.parent.glob("*.jsonl")))
    seen: Set[Path] = set()
    first: List[Path] = []
    for candidate in near:
        resolved = candidate.resolve()
        if resolved != own and resolved not in seen:
            seen.add(resolved)
            first.append(candidate)
    rest: List[Path] = []
    if projects_root is not None:
        for candidate in sorted(projects_root.glob("*/*.jsonl")):
            resolved = candidate.resolve()
            if resolved != own and resolved not in seen:
                seen.add(resolved)
                rest.append(candidate)
    return first, rest


def _try_parent(
    candidate: Path,
    *,
    rows: Sequence[Row],
    region: Region,
    closing: Json,
    needles: Tuple[bytes, bytes],
    deadline: Optional[float],
) -> Optional[ForkInfo]:
    try:
        data = candidate.read_bytes()
    except OSError:
        return None
    if any(needle not in data for needle in needles):
        return None
    parent_rows = parse_rows(data, deadline)
    parent_uuids = {row.entry["uuid"] for row in parent_rows if row.kind == CHAIN}
    chain = [i for i in region.rows if rows[i].kind == CHAIN]
    copies: List[int] = []
    for i in chain:
        if rows[i].entry["uuid"] not in parent_uuids:
            break
        copies.append(i)
    if not copies:
        return None
    own_chain = chain[len(copies):]
    if own_chain:
        fork_point = rows[own_chain[0]].entry.get("parentUuid")
        if isinstance(fork_point, str) and fork_point not in parent_uuids:
            return None
    own_ts = stamps(rows, region.rows, set(copies))
    copy_ts = stamps(rows, copies)
    fork_start = min(own_ts) if own_ts else (max(copy_ts) if copy_ts else None)
    if fork_start is None:
        return None
    base = _base_at(parent_rows, fork_start)
    if base is None or int_value(base.get("startTime")) != int_value(closing.get("startTime")):
        return None
    if not _cost_le(base, closing):
        return None
    return ForkInfo(copies, candidate.stem, base)


def _queue_marker_copies(rows: Sequence[Row], region: Region) -> List[int]:
    """Without the parent, a -p fork's copies are the chain entries older than the
    fork's own first queue-operation, which precedes them in the file."""
    chain_rows = [i for i in region.rows if rows[i].kind == CHAIN]
    if not chain_rows:
        return []
    first_chain = chain_rows[0]
    marker: Optional[float] = None
    for i in region.rows:
        if i >= first_chain:
            break
        entry = rows[i].entry
        if entry.get("type") == "queue-operation" and rows[i].ts is not None:
            marker = rows[i].ts
            break
    if marker is None:
        return []
    copies: List[int] = []
    for i in chain_rows:
        ts = rows[i].ts
        if ts is None or ts >= marker:
            break
        copies.append(i)
    return copies


def _restored(rows: Sequence[Row], region: Region, closing: Json) -> bool:
    start, duration = int_value(closing.get("startTime")), int_value(closing.get("totalDuration"))
    dated = stamps(rows, region.rows)
    if start is None or duration is None or not dated:
        return False
    return max(dated) * 1000.0 > start + duration + RESTORED_SLACK_MS


def detect_fork(
    path: Path,
    *,
    rows: Sequence[Row],
    region: Region,
    hints: Hints,
    projects_root: Optional[Path],
    deadline: Optional[float],
) -> Optional[ForkInfo]:
    """ForkInfo when the file's first lifetime is a fork, else None.

    A fork is recognised by its cost-state carrying time from before its own entries
    (or by the caller's command-line hint). Its parent is the same-lineage transcript
    that holds the copied entries and the fork point, looked for in the hinted file
    and the same project directory first, then in the other project directories.
    Among parents that fit, the longest copied prefix wins, then the lowest restored
    cost (a sibling fork restores more than the true parent), then the smallest id.
    """
    if not region.settled:
        return None
    closing = rows[region.closing[0]].entry
    if not (hints.fork or _restored(rows, region, closing)):
        return None
    chain = [i for i in region.rows if rows[i].kind == CHAIN]
    lineage = int_value(closing.get("startTime"))
    if chain and lineage is not None:
        first_uuid = rows[chain[0]].entry["uuid"]
        needles = (b'"uuid":"' + first_uuid.encode("utf-8") + b'"', b'"startTime":' + str(lineage).encode())
        for scope in _fork_candidates(path, hints, projects_root):
            found: List[Tuple[Tuple[int, float, str], ForkInfo]] = []
            for candidate in scope:
                _check(deadline)
                info = _try_parent(
                    candidate, rows=rows, region=region, closing=closing, needles=needles, deadline=deadline
                )
                if info is not None and info.base is not None:
                    restored = num_value(info.base.get("totalCostUSD")) or 0.0
                    found.append(((-len(info.copies), restored, candidate.stem), info))
            if found:
                return min(found, key=lambda item: item[0])[1]
    return ForkInfo(_queue_marker_copies(rows, region), None, None)


# --------------------------------------------------------------------------------------
# Measuring one lifetime
# --------------------------------------------------------------------------------------


def _content_blocks(entry: Json) -> List[Json]:
    message = entry.get("message")
    content = message.get("content") if isinstance(message, dict) else None
    return [block for block in content if isinstance(block, dict)] if isinstance(content, list) else []


def _effort_of(entry: Json) -> Optional[str]:
    effort = entry.get("effort")
    if isinstance(effort, dict):
        effort = effort.get("level")
    return effort if isinstance(effort, str) and effort else None


def _is_denial(entry: Json) -> bool:
    decision = entry.get("permissionDecision")
    if isinstance(decision, dict):
        decision = decision.get("decision")
    if isinstance(decision, str) and decision.lower() in DENIAL_DECISIONS:
        return True
    kind = entry.get("toolDenialKind")
    return isinstance(kind, str) and bool(kind)


def _is_turn(entry: Json) -> bool:
    """A human or SDK prompt; never a tool result, notification, command echo,
    meta entry or compaction summary."""
    if entry.get("isMeta") is True or entry.get("isCompactSummary") is True:
        return False
    if any(block.get("type") == "tool_result" for block in _content_blocks(entry)):
        return False
    origin = entry.get("turnOrigin")
    if isinstance(origin, str):
        return origin in TURN_ORIGINS
    source = entry.get("origin")
    if isinstance(source, dict) and isinstance(source.get("kind"), str):
        return bool(source.get("kind") == "human")
    prompt_source = entry.get("promptSource")
    if isinstance(prompt_source, str):
        return prompt_source in ("typed", "sdk")
    message = entry.get("message")
    content = message.get("content") if isinstance(message, dict) else None
    if isinstance(content, list):
        content = " ".join(
            str(block.get("text", "")) for block in _content_blocks(entry) if block.get("type") == "text"
        )
    text = content.lstrip() if isinstance(content, str) else ""
    return bool(text) and not text.startswith(("<", "Caveat:", "[Request interrupted"))


def _is_clear_command(entry: Json) -> bool:
    if entry.get("type") != "user":
        return False
    message = entry.get("message")
    content = message.get("content") if isinstance(message, dict) else None
    return isinstance(content, str) and CLEAR_COMMAND in content


class _Measure:
    """Accumulates one lifetime's measures over main-transcript and subagent entries."""

    def __init__(self) -> None:
        self.requests: Dict[str, Usage] = {}
        self.request_model: Dict[str, str] = {}
        self.sidechain: Set[str] = set()
        self.main_requests: Set[str] = set()
        self.request_effort: Dict[str, str] = {}
        self.thinking: Dict[str, int] = {}
        self.tool_ids: Set[str] = set()
        self.tools: Counter[str] = Counter()
        self.tool_names: Dict[str, str] = {}
        self.failure_ids: Set[str] = set()
        self.failures: Counter[str] = Counter()
        self.denial_ids: Set[str] = set()
        self.compactions = 0
        self.retries = 0
        self.turns = 0
        self.launches = 0
        self.first: Optional[Tuple[float, str]] = None
        self.last: Optional[Tuple[float, str]] = None
        self.versions: Set[str] = set()
        self.entrypoints: Set[str] = set()
        self.git_branch: Optional[str] = None

    def stamp(self, ts: Optional[float], raw: Any) -> None:
        if ts is None or not isinstance(raw, str):
            return
        if self.first is None or ts < self.first[0]:
            self.first = (ts, raw)
        if self.last is None or ts >= self.last[0]:
            self.last = (ts, raw)

    def feed(self, entry: Json, ts: Optional[float], *, sidechain: bool, main: bool) -> None:
        self.stamp(ts, entry.get("timestamp"))
        kind = entry.get("type")
        if main and isinstance(entry.get("uuid"), str):
            for key, bucket in (("version", self.versions), ("entrypoint", self.entrypoints)):
                value = entry.get(key)
                if isinstance(value, str) and value:
                    bucket.add(value)
            branch = entry.get("gitBranch")
            if isinstance(branch, str) and branch:
                self.git_branch = branch
        if kind == "assistant":
            self._assistant(entry, sidechain=sidechain, main=main)
        elif kind == "user":
            self._user(entry, main=main)
        elif kind == "system":
            subtype = entry.get("subtype")
            if subtype == "compact_boundary":
                self.compactions += 1
            elif subtype == "api_error" and entry.get("retryAttempt") is not None:
                self.retries += 1

    def _assistant(self, entry: Json, *, sidechain: bool, main: bool) -> None:
        message = _dict(entry.get("message"))
        model = message.get("model")
        synthetic = model == SYNTHETIC_MODEL or entry.get("isApiErrorMessage") is True
        request_id = entry.get("requestId") or entry.get("uuid")
        usage = message.get("usage")
        if not synthetic and isinstance(request_id, str) and isinstance(usage, dict):
            current = self.requests.setdefault(request_id, zero_usage())
            for key in USAGE_KEYS:
                value = int_value(usage.get(key))
                if value is not None and value > current[key]:
                    current[key] = value
            if isinstance(model, str) and model:
                self.request_model[request_id] = model
            if sidechain or entry.get("isSidechain") is True:
                self.sidechain.add(request_id)
            if main:
                self.main_requests.add(request_id)
            effort = _effort_of(entry)
            if effort:
                self.request_effort[request_id] = effort
            thinking = int_value(entry.get("thinkingDurationMs"))
            if thinking is not None and thinking > self.thinking.get(request_id, 0):
                self.thinking[request_id] = thinking
        for position, block in enumerate(_content_blocks(entry)):
            if block.get("type") != "tool_use":
                continue
            block_id = block.get("id")
            if not isinstance(block_id, str) or not block_id:
                block_id = f"{entry.get('uuid')}#{position}"
            if block_id in self.tool_ids:
                continue
            self.tool_ids.add(block_id)
            name = str(block.get("name") or "unknown")
            self.tools[name] += 1
            self.tool_names[block_id] = name
            if name in SUBAGENT_TOOLS:
                self.launches += 1

    def _user(self, entry: Json, *, main: bool) -> None:
        results = [block for block in _content_blocks(entry) if block.get("type") == "tool_result"]
        if _is_denial(entry):
            key = next((str(b.get("tool_use_id")) for b in results if b.get("tool_use_id")), None)
            self.denial_ids.add(key or f"entry:{entry.get('uuid')}")
        else:
            for block in results:
                if block.get("is_error") is not True:
                    continue
                tool_id = block.get("tool_use_id")
                key = tool_id if isinstance(tool_id, str) and tool_id else f"entry:{entry.get('uuid')}"
                if key in self.failure_ids:
                    continue
                self.failure_ids.add(key)
                self.failures[self.tool_names.get(key, "unknown")] += 1
        if main and _is_turn(entry):
            self.turns += 1

    # results -------------------------------------------------------------------

    def usage(self, only: Optional[Set[str]] = None) -> Usage:
        total = zero_usage()
        for request_id, usage in self.requests.items():
            if only is None or request_id in only:
                add_usage(total, usage)
        return total

    def usage_by_model(self) -> Dict[str, Usage]:
        out: Dict[str, Usage] = {}
        for request_id, usage in self.requests.items():
            add_usage(out.setdefault(self.request_model.get(request_id, "unknown"), zero_usage()), usage)
        return {model: out[model] for model in sorted(out)}

    def model(self) -> Optional[str]:
        pool = [r for r in self.requests if r in self.main_requests] or list(self.requests)
        output: Counter[str] = Counter()
        for request_id in pool:
            output[self.request_model.get(request_id, "unknown")] += self.requests[request_id]["output_tokens"]
        if not output:
            return None
        return sorted(output.items(), key=lambda item: (-item[1], item[0]))[0][0]

    def effort_levels(self) -> Tuple[Optional[str], List[str]]:
        main = [self.request_effort[r] for r in self.request_effort if r in self.main_requests]
        pool = main or list(self.request_effort.values())
        if not pool:
            return None, []
        counts = Counter(pool)
        chosen = sorted(counts.items(), key=lambda item: (-item[1], item[0]))[0][0]
        return (chosen if chosen in EFFORT_LEVELS else None), sorted(set(self.request_effort.values()))


# --------------------------------------------------------------------------------------
# Subagent files
# --------------------------------------------------------------------------------------


def subagent_files(path: Path, session_id: str) -> List[Path]:
    base = path.parent / session_id / "subagents"
    if not base.is_dir():
        return []
    return sorted(base.rglob("agent-*.jsonl"), key=lambda p: p.relative_to(base).as_posix())


def _edge_stamps(path: Path) -> Tuple[Optional[float], Optional[float]]:
    """Timestamps of the first and the last complete line, read without parsing the file."""
    try:
        with path.open("rb") as handle:
            head = handle.read(65536)
            handle.seek(0, 2)
            size = handle.tell()
            handle.seek(max(0, size - 65536))
            tail = handle.read()
    except OSError:
        return None, None

    def stamp(line: bytes) -> Optional[float]:
        try:
            entry = json.loads(line)
        except ValueError:
            return None
        return parse_ts(entry.get("timestamp")) if isinstance(entry, dict) else None

    first = stamp(head.split(b"\n", 1)[0]) if b"\n" in head else None
    lines = [line for line in tail.split(b"\n")[:-1] if line.strip()]
    last = stamp(lines[-1]) if lines else None
    return first, last


# --------------------------------------------------------------------------------------
# The lifetime record and the event
# --------------------------------------------------------------------------------------


@dataclass
class Lifetime:
    """Everything about one settled lifetime that comes from the files."""

    session_id: str
    event_id: str
    anchor: str
    start_source: str
    started_at: str
    ended_at: str
    closing_offset: int
    cost_lineage: Optional[str]
    cum_cost_start_usd: Optional[float]
    cum_cost_end_usd: Optional[float]
    cost_usd: Optional[float]
    duration_ms: Optional[int]
    api_duration_ms: Optional[int]
    cost_state_usage_by_model: Optional[Dict[str, Json]]
    usage: Usage
    usage_by_model: Dict[str, Usage]
    sidechain_usage: Usage
    requests: int
    model: Optional[str]
    effort: Optional[str]
    effort_levels: List[str]
    thinking_duration_ms: int
    num_turns: int
    counts: Json
    git_branch: Optional[str]
    versions: List[str]
    entrypoints: List[str]
    forked_from_session_id: Optional[str]
    concurrent: bool
    subagent_files: int
    subagent_launches_without_file: int
    copied_entries_excluded: int
    fork_parent: Optional[str]
    shortfall: List[str]

    @property
    def empty(self) -> bool:
        """No requests, tool calls or compactions and no cost: no event (A1 D1.2)."""
        return (
            self.requests == 0
            and self.counts.get("tool_calls", 0) == 0
            and self.counts.get("compactions", 0) == 0
            and not self.cost_usd
        )


@dataclass
class Selection:
    """Which settled lifetimes to measure.

    all: every one. last_before: the lifetime whose closing block holds the last
    cost-state line that starts before ``offset`` (a SessionEnd's own lifetime, with
    ``offset`` the file size the hook saw); ``prompt_id`` moves the choice to the
    lifetime that holds that prompt when the last cost-state belongs to a concurrent
    writer. first_after: the lifetime whose closing block holds the first cost-state
    line at or after ``offset`` (a /clear predecessor, whose cost-state is written
    after its SessionEnd returned).
    """

    mode: str = "all"
    offset: int = 0
    prompt_id: Optional[str] = None


def _selected(rows: Sequence[Row], regions: Sequence[Region], selection: Selection) -> List[Region]:
    settled = [r for r in regions if r.settled]
    if selection.mode == "all":
        return settled
    cs_rows = [i for i, row in enumerate(rows) if row.kind == COST]
    if selection.mode == "last_before":
        before = [i for i in cs_rows if rows[i].offset < selection.offset]
        target = before[-1] if before else None
    elif selection.mode == "first_after":
        after = [i for i in cs_rows if rows[i].offset >= selection.offset]
        target = after[0] if after else None
    else:
        raise ValueError(f"unknown selection mode {selection.mode!r}")
    if target is None:
        return []
    chosen = next((r for r in settled if target in r.closing), None)
    if chosen is not None and selection.mode == "last_before" and selection.prompt_id:
        holders = [
            r
            for r in settled
            if rows[r.closing[0]].offset < selection.offset
            and any(rows[i].entry.get("promptId") == selection.prompt_id for i in r.rows)
        ]
        if len(holders) == 1 and holders[0] is not chosen and not any(
            rows[i].entry.get("promptId") == selection.prompt_id for i in chosen.rows
        ):
            chosen = holders[0]
    return [chosen] if chosen is not None else []


def _cost_delta(end: Json, base: Optional[Json]) -> Optional[Tuple[float, Optional[int], Optional[int], Dict[str, Json]]]:
    """(cost, duration, api duration, per-model delta), or None when the base does not
    fit under the closing cost-state."""
    base = base or {}
    end_total, base_total = num_value(end.get("totalCostUSD")), num_value(base.get("totalCostUSD")) or 0.0
    if end_total is None:
        return None
    cost = _round_cost(end_total - base_total)
    if cost < 0:
        return None

    def delta(key: str) -> Optional[int]:
        high, low = int_value(end.get(key)), int_value(base.get(key)) if base else 0
        if high is None or low is None or high < low:
            return None
        return high - low

    end_usage = _dict(end.get("modelUsage"))
    base_usage = _dict(base.get("modelUsage"))
    per_model: Dict[str, Json] = {}
    for model in sorted(set(end_usage) | set(base_usage)):
        high = _dict(end_usage.get(model))
        low = _dict(base_usage.get(model))
        item: Json = {}
        for camel, snake in MODEL_USAGE_KEYS.items():
            value = (int_value(high.get(camel)) or 0) - (int_value(low.get(camel)) or 0)
            if value < 0:
                return None
            item[snake] = value
        model_cost = _round_cost((num_value(high.get("costUSD")) or 0.0) - (num_value(low.get("costUSD")) or 0.0))
        if model_cost < 0:
            return None
        item["cost_usd"] = model_cost
        if any(item[key] for key in USAGE_KEYS) or model_cost:
            per_model[model] = item
    return cost, delta("totalDuration"), delta("totalAPIDuration"), per_model


@dataclass
class Derivation:
    """The result of one derive() call."""

    lifetimes: List[Lifetime]  # settled, non-empty, in file order
    selected: int  # settled lifetimes the selection named, empty ones included
    open_after: Optional[int]  # offset after the last cost-state line when activity follows it


def derive(
    path: Path,
    *,
    selection: Optional[Selection] = None,
    hints: Optional[Hints] = None,
    projects_root: Optional[Path] = None,
    deadline: Optional[float] = None,
) -> List[Lifetime]:
    """The settled, non-empty lifetimes of one transcript, in file order."""
    return derive_detail(
        path, selection=selection, hints=hints, projects_root=projects_root, deadline=deadline
    ).lifetimes


def derive_detail(
    path: Path,
    *,
    selection: Optional[Selection] = None,
    hints: Optional[Hints] = None,
    projects_root: Optional[Path] = None,
    deadline: Optional[float] = None,
) -> Derivation:
    """Derive the selected settled lifetimes of one transcript.

    ``projects_root`` defaults to the transcript's grandparent when that directory is
    named ``projects`` (Claude Code's ``<config>/projects/<slug>/<id>.jsonl``); a fork's
    parent is looked for in the same project directory first, then under it.
    Raises DeadlineExceeded when ``deadline`` (time.monotonic()) passes.
    """
    selection = selection or Selection()
    hints = hints or Hints()
    if projects_root is None and path.parent.parent.name == "projects":
        projects_root = path.parent.parent
    session_id = path.stem
    rows = load_rows(path, deadline)
    regions = segment(rows)
    cs_rows = [i for i, row in enumerate(rows) if row.kind == COST]
    open_after: Optional[int] = None
    if cs_rows and any(row.kind in (CHAIN, LOOSE) for row in rows[cs_rows[-1] + 1:]):
        after = rows[cs_rows[-1] + 1].offset if cs_rows[-1] + 1 < len(rows) else None
        open_after = after
    elif not cs_rows and any(row.kind in (CHAIN, LOOSE) for row in rows):
        open_after = 0
    targets = _selected(rows, regions, selection)
    if not targets:
        return Derivation([], 0, open_after)
    chain_rows = [i for i, row in enumerate(rows) if row.kind == CHAIN]
    first_region = next((r for r in regions if chain_rows and chain_rows[0] in r.rows), None)

    fork: Optional[ForkInfo] = None
    if first_region is not None and any(r is first_region for r in targets):
        fork = detect_fork(
            path, rows=rows, region=first_region, hints=hints, projects_root=projects_root, deadline=deadline
        )
    copied: Set[int] = set(fork.copies) if fork else set()

    # Windows: from a lifetime's first own entry to the next lifetime's first own entry.
    starts: List[Tuple[float, int]] = []
    for region in regions:
        dated = stamps(rows, region.rows, copied)
        if dated:
            starts.append((min(dated), region.index))
    starts.sort()
    windows: Dict[int, Tuple[float, float]] = {}
    for position, (start, index) in enumerate(starts):
        later = [s for s, _ in starts[position + 1:] if s > start]
        windows[index] = (start, later[0] if later else float("inf"))

    measures: Dict[int, _Measure] = {}
    for region in targets:
        measure = _Measure()
        for i in region.rows:
            if i not in copied:
                measure.feed(rows[i].entry, rows[i].ts, sidechain=False, main=True)
        measures[region.index] = measure

    files_used: Dict[int, Set[str]] = {region.index: set() for region in targets}
    wanted = [(windows[r.index], r.index) for r in targets if r.index in windows]
    if wanted:
        for file_path in subagent_files(path, session_id):
            _check(deadline)
            first, last = _edge_stamps(file_path)
            if first is not None and last is not None:
                low, high = min(first, last) - SUBAGENT_RANGE_SLACK_S, max(first, last) + SUBAGENT_RANGE_SLACK_S
                if not any(low < end and high >= start for (start, end), _ in wanted):
                    continue
            for row in load_rows(file_path, deadline):
                if row.ts is None:
                    continue
                for (start, end), index in wanted:
                    if start <= row.ts < end:
                        measures[index].feed(row.entry, row.ts, sidechain=True, main=False)
                        files_used[index].add(file_path.as_posix())
                        break

    lifetimes: List[Lifetime] = []
    for region in targets:
        first = region is first_region
        lifetime = _lifetime(
            session_id=session_id,
            rows=rows,
            regions=regions,
            region=region,
            measure=measures[region.index],
            files=len(files_used[region.index]),
            first=first,
            fork=fork if first else None,
            copied=copied if first else set(),
        )
        if lifetime is not None and not lifetime.empty:
            lifetimes.append(lifetime)
    return Derivation(lifetimes, len(targets), open_after)


def _lifetime(
    *,
    session_id: str,
    rows: Sequence[Row],
    regions: Sequence[Region],
    region: Region,
    measure: _Measure,
    files: int,
    first: bool,
    fork: Optional[ForkInfo],
    copied: Set[int],
) -> Optional[Lifetime]:
    closing = rows[region.closing[0]].entry
    start_time, total_duration = int_value(closing.get("startTime")), int_value(closing.get("totalDuration"))
    if start_time is None or total_duration is None or start_time < 0 or total_duration < 0:
        return None  # no stable anchor: such a cost-state cannot name an event
    if measure.first is None or measure.last is None:
        return None  # no dated entry: the lifetime cannot be placed in time
    anchor = f"cs:{start_time}:{total_duration}"

    if fork is not None:
        start_source = "fork"
    elif first:
        opening = [rows[i].entry for i in region.rows if rows[i].kind == CHAIN][:12]
        start_source = "clear" if any(_is_clear_command(entry) for entry in opening) else "startup"
    else:
        start_source = "resume"

    if fork is not None:
        base: Optional[Json] = fork.base
        base_known = fork.base is not None
    else:
        base = rows[region.base].entry if region.base is not None else None
        base_known = True
    delta = _cost_delta(closing, base) if base_known else None
    cost = delta[0] if delta else None
    cum_start: Optional[float] = None
    if delta is not None:
        cum_start = (num_value(base.get("totalCostUSD")) or 0.0) if base else 0.0

    usage_by_model = measure.usage_by_model()
    shortfall: List[str] = []
    if delta is not None:
        for model, usage in usage_by_model.items():
            billed = delta[3].get(model, {})
            for key in USAGE_KEYS:
                if usage[key] > int(billed.get(key, 0)):
                    shortfall.append(f"{model}:{key}"[:120])
    effort, effort_levels = measure.effort_levels()
    tool_calls = int(sum(measure.tools.values()))
    counts: Json = {
        "tool_calls": tool_calls,
        "tool_calls_by_tool": {name: measure.tools[name] for name in sorted(measure.tools)},
        "tool_failures": int(sum(measure.failures.values())),
        "tool_failures_by_tool": {name: measure.failures[name] for name in sorted(measure.failures)},
        "subagents": max(files, measure.launches),
        "compactions": measure.compactions,
        "api_retries": measure.retries,
        "permission_denials": len(measure.denial_ids),
    }
    lineage = str(start_time)
    return Lifetime(
        session_id=session_id,
        event_id=event_id_for(session_id, anchor),
        anchor=anchor,
        start_source=start_source,
        started_at=measure.first[1],
        ended_at=measure.last[1],
        closing_offset=rows[region.closing[0]].offset,
        cost_lineage=lineage,
        cum_cost_start_usd=cum_start,
        cum_cost_end_usd=num_value(closing.get("totalCostUSD")),
        cost_usd=cost,
        duration_ms=delta[1] if delta else None,
        api_duration_ms=delta[2] if delta else None,
        cost_state_usage_by_model=delta[3] if delta else None,
        usage=measure.usage(),
        usage_by_model=usage_by_model,
        sidechain_usage=measure.usage(measure.sidechain),
        requests=len(measure.requests),
        model=measure.model(),
        effort=effort,
        effort_levels=effort_levels,
        thinking_duration_ms=int(sum(measure.thinking.values())),
        num_turns=measure.turns,
        counts=counts,
        git_branch=measure.git_branch,
        versions=sorted(measure.versions),
        entrypoints=sorted(measure.entrypoints),
        forked_from_session_id=fork.parent_session_id if fork else None,
        concurrent=_concurrent(region, regions),
        subagent_files=files,
        subagent_launches_without_file=max(0, measure.launches - files),
        copied_entries_excluded=len(copied),
        fork_parent=("found" if fork.base is not None else "not-found") if fork else None,
        shortfall=sorted(shortfall),
    )


@dataclass
class Context:
    """What the caller adds: the project, what a hook observed, and how the event was
    produced. Nothing here changes event_id or any measured number."""

    project: str
    recovered: str = "backfill"  # none: the hook of the process that held the lifetime
    end_reason: Optional[str] = None
    sprint: Any = None
    phase: Optional[int] = None
    head: Optional[str] = None
    observed: bool = False  # sprint, phase and head were observed by a hook
    cleared_from_session_id: Optional[str] = None
    sprint_at_start: Any = None
    phase_at_start: Optional[int] = None
    head_at_start: Optional[str] = None


def build_event(lifetime: Lifetime, context: Context) -> Json:
    """The schema 1.1 kind=session event for one settled lifetime."""
    labels: Dict[str, str] = {}
    for key, values in (
        ("claude_code_version", lifetime.versions),
        ("entrypoint", lifetime.entrypoints),
        ("effort_levels", lifetime.effort_levels if len(lifetime.effort_levels) > 1 else []),
    ):
        if values:
            labels[key] = ",".join(values)[:80]
    lifetime_block: Json = {
        "spec": SPEC,
        "anchor": lifetime.anchor,
        "start_source": lifetime.start_source,
        "end_reason": context.end_reason[:40] if isinstance(context.end_reason, str) else None,
        "started_at": lifetime.started_at,
        "ended_at": lifetime.ended_at,
        "cost_lineage": lifetime.cost_lineage,
        "cum_cost_start_usd": lifetime.cum_cost_start_usd,
        "cum_cost_end_usd": lifetime.cum_cost_end_usd,
        "forked_from_session_id": lifetime.forked_from_session_id,
        "cleared_from_session_id": context.cleared_from_session_id if lifetime.start_source == "clear" else None,
        "sprint_at_start": context.sprint_at_start,
        "phase_at_start": context.phase_at_start,
        "head_at_start": context.head_at_start,
        "concurrent": lifetime.concurrent,
        "recovered": context.recovered,
        "coverage": {
            "subagent_files": lifetime.subagent_files,
            "subagent_launches_without_file": lifetime.subagent_launches_without_file,
            "copied_entries_excluded": lifetime.copied_entries_excluded,
            "fork_parent": lifetime.fork_parent,
            "context": "observed" if context.observed else "unknown",
            "shortfall": lifetime.shortfall,
        },
    }
    event: Json = {
        "schema_version": "1.1",
        "event_id": lifetime.event_id,
        "ts": lifetime.ended_at,
        "source": "claude-code-session",
        "kind": "session",
        "project": context.project,
        "session_id": lifetime.session_id,
        "sprint": context.sprint,
        "phase": context.phase,
        "git_branch": lifetime.git_branch,
        "head": context.head,
        "model": lifetime.model,
        "effort": lifetime.effort,
        "usage": lifetime.usage,
        "usage_by_model": lifetime.usage_by_model,
        "sidechain_usage": lifetime.sidechain_usage,
    }
    if lifetime.cost_usd is not None and lifetime.cost_state_usage_by_model is not None:
        event["cost_state_usage_by_model"] = lifetime.cost_state_usage_by_model
    event.update(
        {
            "cost_usd": lifetime.cost_usd,
            "cost_source": "claude-code-estimate" if lifetime.cost_usd is not None else None,
            "duration_ms": lifetime.duration_ms,
            "api_duration_ms": lifetime.api_duration_ms,
            "thinking_duration_ms": lifetime.thinking_duration_ms,
            "num_turns": lifetime.num_turns,
            "counts": lifetime.counts,
            "outcome": "ended",
            "lifetime": lifetime_block,
            "labels": labels,
        }
    )
    return event


def lifetimes_to_events(lifetimes: Iterable[Lifetime], context: Context) -> List[Json]:
    return [build_event(lifetime, context) for lifetime in lifetimes]
