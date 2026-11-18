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

How a transcript splits into lifetimes (``_Segmenter``): each process appends a
chain of entries linked by ``parentUuid`` and closes with a ``cost-state``. A
process that resumes the session chains its first entry to the leaf it loaded.
Two processes can write the same file at once, so the deriver tells them apart
by structure, never by recency alone:

- a cost-state belongs to the process named by the ``leafUuid`` of the latest
  ``last-prompt`` entry since the previous cost-state (a process writes one as a
  turn ends and as it exits) when that lifetime's tokens fit under the
  cost-state's per-model delta; otherwise to the open lifetime whose tokens fit,
  else to the latest activity; an equal-total cost-state that names a closed
  lifetime, or follows one with no activity between, is a re-write;
- a branch inside a lifetime is the same process when it is the next content
  block of the same API response (parallel tool calls); a tool result that
  carries the turn's ``promptId`` continues that turn, so a sibling branch with
  another prompt (for example the ``interrupted`` repair a concurrent resume
  writes) is another process; different ``entrypoint`` values separate two
  processes at a turn boundary; a cost-state whose lineage started after the
  lifetime's first entry closes only the part its process wrote; a second
  cost-state that names a closed lifetime splits it at the branch point;
- entries a process writes after its own cost-state (SIGTERM during a tool call:
  the cancelled tool result and its attachments) stay in that lifetime;
- the base a process restored is the last cost-state of the closing lineage
  written before its resume point gained its first child.

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
# toolDenialKind values Claude Code 2.1.318 writes for a denied tool call. It also
# writes "interrupted" on the result of a call cut off by an exit, a kill, a turn
# abort or a concurrent resume's repair: that is neither a denial nor a failure.
DENIAL_KINDS = frozenset({"user-rejected", "permission-rule"})
DENIAL_KIND_PREFIXES: Tuple[str, ...] = ("automode-",)
INTERRUPTED_KIND = "interrupted"
EFFORT_LEVELS = frozenset({"low", "medium", "high", "xhigh", "max"})
CLEAR_COMMAND = "<command-name>/clear</command-name>"
# A first lifetime whose own entries run past startTime + totalDuration restored
# cost from before its file existed: a fork (probes: forks +1.8 s to +48 s, every
# other first lifetime -4 ms or less).
RESTORED_SLACK_MS = 1000
# A lifetime's entries may carry timestamps slightly before its lineage's startTime
# (a /clear session's first entry: 149 ms before).
LINEAGE_SLACK_MS = 1000
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


def utc_date(seconds: float) -> str:
    return time.strftime("%Y-%m-%d", time.gmtime(seconds))


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


def _content_blocks(entry: Json) -> List[Json]:
    message = entry.get("message")
    content = message.get("content") if isinstance(message, dict) else None
    return [block for block in content if isinstance(block, dict)] if isinstance(content, list) else []


def _has_tool_result(entry: Json) -> bool:
    return entry.get("type") == "user" and any(b.get("type") == "tool_result" for b in _content_blocks(entry))


def _is_turn(entry: Json) -> bool:
    """A human or SDK prompt; never a tool result, notification, command echo,
    meta entry or compaction summary."""
    if entry.get("type") != "user":
        return False
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


# --------------------------------------------------------------------------------------
# Lifetimes inside one transcript
# --------------------------------------------------------------------------------------


@dataclass(eq=False)
class Region:
    """One process lifetime's share of a transcript. Compared by identity."""

    index: int = -1  # position among the transcript's lifetimes, in closing order
    rows: List[int] = field(default_factory=list)  # own activity rows (chain and loose)
    closing: List[int] = field(default_factory=list)  # closing point first, then re-writes
    leaf: Optional[str] = None  # the last-prompt leafUuid that named the closing cost-state
    trailing: Set[int] = field(default_factory=set)  # rows written after the closing cost-state
    last_activity: int = -1

    @property
    def settled(self) -> bool:
        return bool(self.closing)


def _cost_totals(entry: Json) -> Tuple[Any, ...]:
    model_usage = entry.get("modelUsage")
    per_model: List[Tuple[str, Tuple[Optional[int], ...]]] = []
    if isinstance(model_usage, dict):
        for model in sorted(model_usage):
            usage = model_usage[model]
            if isinstance(usage, dict):
                per_model.append((model, tuple(int_value(usage.get(k)) for k in MODEL_USAGE_KEYS)))
    return int_value(entry.get("startTime")), num_value(entry.get("totalCostUSD")), tuple(per_model)


JOIN = "join"
SPLIT = "split"
NEW = "new"


class _Segmenter:
    """Splits one transcript's rows into process lifetimes (see the module docstring)."""

    def __init__(self, rows: Sequence[Row]) -> None:
        self.rows = rows
        self.cost_rows = [i for i, row in enumerate(rows) if row.kind == COST]
        self.regions: List[Region] = []
        self.region_of: Dict[int, Region] = {}
        self.owner: Dict[str, Region] = {}
        self.row_of: Dict[str, int] = {}
        self.parent_of: Dict[str, Optional[str]] = {}
        self.children: Dict[str, List[int]] = {}
        self.prompt_of: Dict[str, Optional[str]] = {}
        self.entrypoint_of: Dict[str, Optional[str]] = {}
        self.pending: List[int] = []
        self.latest: Optional[Region] = None
        self.last_cs: Optional[int] = None
        self.last_closed: Optional[Region] = None
        self.leaf: Optional[str] = None  # leafUuid of the latest last-prompt since the last cost-state

    # driver -----------------------------------------------------------------------

    def run(self) -> List[Region]:
        for i, row in enumerate(self.rows):
            if row.kind == COST:
                self._cost(i)
            elif row.kind == LOOSE:
                self._loose(i)
            elif row.kind == CHAIN:
                self._chain(i)
            elif row.entry.get("type") == "last-prompt":
                leaf = row.entry.get("leafUuid")
                if isinstance(leaf, str) and leaf:
                    self.leaf = leaf
        regions = [r for r in self.regions if r.rows or r.closing]
        regions.sort(key=lambda r: r.closing[0] if r.closing else min(r.rows, default=len(self.rows)))
        for number, region in enumerate(regions):
            region.index = number
            region.rows.sort()
        self.regions = regions
        return regions

    # placement --------------------------------------------------------------------

    def _open(self) -> Region:
        region = Region()
        self.regions.append(region)
        return region

    def _add(self, region: Region, i: int) -> None:
        region.rows.append(i)
        self.region_of[i] = region
        region.last_activity = max(region.last_activity, i)

    def _loose(self, i: int) -> None:
        if self.latest is not None and not self.latest.settled:
            self._add(self.latest, i)
        else:
            self.pending.append(i)
            self.latest = None

    def _chain(self, i: int) -> None:
        entry = self.rows[i].entry
        uid = entry["uuid"]
        if uid in self.row_of:  # a repeated uuid stays with its first entry's lifetime
            region = self.owner.get(uid)
            if region is not None:
                self._add(region, i)
            return
        parent_raw = entry.get("parentUuid")
        parent = parent_raw if isinstance(parent_raw, str) and parent_raw else None
        logical_raw = entry.get("logicalParentUuid")
        logical = logical_raw if parent is None and isinstance(logical_raw, str) and logical_raw else None
        before = parent or logical
        self.row_of[uid] = i
        self.parent_of[uid] = parent
        prompt = entry.get("promptId") if entry.get("type") == "user" else None
        self.prompt_of[uid] = prompt if isinstance(prompt, str) and prompt else self.prompt_of.get(before or "")
        entrypoint = entry.get("entrypoint")
        self.entrypoint_of[uid] = (
            entrypoint if isinstance(entrypoint, str) and entrypoint else self.entrypoint_of.get(before or "")
        )
        if parent is not None:
            self.children.setdefault(parent, []).append(i)
        region, trailing = self._place(i, parent, logical)
        if self.pending and not trailing:
            for j in self.pending:
                self._add(region, j)
            self.pending = []
        self._add(region, i)
        if trailing:
            region.trailing.add(i)
        self.owner[uid] = region
        self.latest = region

    def _place(self, i: int, parent: Optional[str], logical: Optional[str]) -> Tuple[Region, bool]:
        if parent is not None and parent in self.owner:
            region = self.owner[parent]
            earlier = [c for c in self.children[parent][:-1] if self.region_of.get(c) is region]
            if not region.settled:
                if not earlier:
                    return region, False
                decision, others = self._branch(i, parent, earlier, region)
                if decision == SPLIT:
                    self._split_branch(region, parent, others, i, closed=False)
                    return region, False
                return (region if decision == JOIN else self._open()), False
            decision, others = self._branch(i, parent, earlier, region) if earlier else (JOIN, [])
            if decision == SPLIT:
                if self._split_branch(region, parent, others, i, closed=True) is not None:
                    return region, False  # the closing went with the other process: reopened
                decision = JOIN
            if decision == JOIN and self._trailing(i, parent, region):
                return region, True
            return self._open(), False
        # a parentless entry (a root, a compact boundary) or one whose parent is not here
        if logical is not None and logical in self.owner and not self.owner[logical].settled:
            return self.owner[logical], False
        if self.latest is not None and not self.latest.settled:
            return self.latest, False
        return self._open(), False

    def _same_request(self, j: int, parent: str) -> bool:
        request = self.rows[self.row_of[parent]].entry.get("requestId")
        entry = self.rows[j].entry
        return bool(isinstance(request, str) and request and entry.get("type") == "assistant"
                    and entry.get("requestId") == request)

    def _continues(self, j: int, parent: str) -> bool:
        """A real tool result of the turn in progress at ``parent``."""
        turn = self.prompt_of.get(parent)
        entry = self.rows[j].entry
        return bool(turn is not None and _has_tool_result(entry) and entry.get("promptId") == turn
                    and entry.get("toolDenialKind") != INTERRUPTED_KIND)

    def _branch(self, i: int, parent: str, earlier: List[int], region: Region) -> Tuple[str, List[int]]:
        """Entry ``i`` is a second child of ``parent`` inside ``region``: the same process
        (JOIN), the parent's process continuing while the earlier branch is another
        process (SPLIT), or another process (NEW)."""
        if self._same_request(i, parent):
            return JOIN, []
        others = [c for c in earlier if not self._same_request(c, parent)]
        if not others:
            return JOIN, []  # the next tool_use block of the same response: parallel tool calls
        mine = self._continues(i, parent)
        theirs = any(self._continues(c, parent) for c in others)
        if mine and not theirs:
            return SPLIT, others
        if theirs and not mine:
            return NEW, []
        if not mine:
            trunk = self.entrypoint_of.get(parent)
            own = self.rows[i].entry.get("entrypoint")
            other = self.rows[others[0]].entry.get("entrypoint")
            if isinstance(trunk, str) and isinstance(own, str) and isinstance(other, str):
                if own == trunk != other:
                    return SPLIT, others
                if other == trunk != own:
                    return NEW, []
        # No evidence: inside an open lifetime a rewind; after its close a later process.
        return (JOIN if not region.settled else NEW), []

    def _trailing(self, i: int, parent: str, region: Region) -> bool:
        """An entry the closed lifetime's own process wrote after its cost-state: the
        result of a tool call SIGTERM cancelled, then that result's attachments."""
        if self._continues(i, parent):
            return True
        entry_type = self.rows[i].entry.get("type")
        return self.row_of[parent] in region.trailing and not self.pending and entry_type in ("attachment", "system")

    # splitting --------------------------------------------------------------------

    def _subtree(self, roots: Iterable[int], region: Region) -> Set[int]:
        found: Set[int] = set()
        stack = [r for r in roots if self.region_of.get(r) is region]
        while stack:
            row = stack.pop()
            if row in found:
                continue
            found.add(row)
            uid = self.rows[row].entry.get("uuid")
            for child in self.children.get(uid, []) if isinstance(uid, str) else []:
                if self.region_of.get(child) is region and child not in found:
                    stack.append(child)
        return found

    def _loose_with(self, region: Region, chain: Set[int]) -> Set[int]:
        """The region's loose rows whose next chain row is in ``chain``: a process writes
        its queue-operation and api-request entries just before its own entries."""
        ordered = sorted(region.rows)
        out: Set[int] = set()
        waiting: List[int] = []
        for row in ordered:
            if self.rows[row].kind == LOOSE:
                waiting.append(row)
            elif self.rows[row].kind == CHAIN:
                if row in chain:
                    out.update(waiting)
                waiting = []
        return out

    def _move(self, region: Region, moved: Set[int]) -> Region:
        new = self._open()
        for row in sorted(moved):
            self.region_of[row] = new
            new.rows.append(row)
            uid = self.rows[row].entry.get("uuid")
            if isinstance(uid, str) and self.owner.get(uid) is region:
                self.owner[uid] = new
            if row in region.trailing:
                region.trailing.discard(row)
                new.trailing.add(row)
        region.rows = [row for row in region.rows if row not in moved]
        region.last_activity = max(region.rows, default=-1)
        new.last_activity = max(new.rows, default=-1)
        return new

    def _close_tip(self, region: Region) -> Optional[int]:
        limit = region.closing[0] if region.closing else len(self.rows)
        chain = [r for r in region.rows if self.rows[r].kind == CHAIN and r < limit]
        return max(chain) if chain else None

    def _closer_row(self, region: Region) -> Optional[int]:
        """The chain row that names the process that wrote the region's closing."""
        if region.leaf is not None and region.leaf in self.row_of:
            return self.row_of[region.leaf]
        return self._close_tip(region)

    def _split_branch(
        self, region: Region, parent: str, others: List[int], i: int, *, closed: bool
    ) -> Optional[Region]:
        """Move the branches ``others`` under ``parent`` out of ``region``: another
        process wrote them. A closed region's closing goes with them, and the region
        reopens, when they hold the entry that named it; otherwise nothing moves."""
        chain = self._subtree(others, region)
        if closed and self._closer_row(region) not in chain:
            return None
        moved = chain | self._loose_with(region, chain)
        moved = {row for row in moved if row < i}
        new = self._move(region, moved)
        if closed:
            new.closing, new.leaf = region.closing, region.leaf
            region.closing, region.leaf = [], None
            if self.last_closed is region:
                self.last_closed = new
        return new

    # cost-states ------------------------------------------------------------------

    def _same_totals(self, a: int, b: int) -> bool:
        return _cost_totals(self.rows[a].entry) == _cost_totals(self.rows[b].entry)

    def _cost(self, i: int) -> None:
        leaf, self.leaf = self.leaf, None
        named = self.owner.get(leaf) if leaf else None
        target: Optional[Region] = None
        if named is not None and named.settled:
            if self._same_totals(named.closing[0], i):
                named.closing.append(i)  # a re-write by the process that closed it
                self.last_cs = i
                return
            target = self._split_closed(named, leaf or "", i)
            named = None
        if target is None and named is not None:
            target = named
            if not self._fits(named.rows, i):
                fitting = [r for r in self._open_regions() if r is not named and self._fits(r.rows, i)]
                if fitting:
                    target = max(fitting, key=lambda r: r.last_activity)
        if target is None:
            since = self.last_cs if self.last_cs is not None else -1
            open_regions = self._open_regions()
            active = [r for r in open_regions if r.last_activity > since]
            if (
                not active
                and not self.pending
                and self.last_closed is not None
                and self.last_cs is not None
                and self._same_totals(self.last_cs, i)
            ):
                self.last_closed.closing.append(i)
                self.last_cs = i
                return
            if self.pending and not active:
                target = self._open()
                for j in self.pending:
                    self._add(target, j)
                self.pending = []
                self.latest = None
            else:
                pool = active or open_regions
                fitting = [r for r in pool if self._fits(r.rows, i)]
                choice = fitting or pool
                target = max(choice, key=lambda r: r.last_activity) if choice else self._open()
        if not target.settled and target.rows:
            target = self._lineage_split(target, leaf, i) or target
        target.closing.append(i)
        target.leaf = leaf if leaf is not None and self.owner.get(leaf) is target else None
        self.last_closed = target
        self.last_cs = i

    def _open_regions(self) -> List[Region]:
        return [r for r in self.regions if not r.settled and r.rows]

    def _lineage_split(self, region: Region, leaf: Optional[str], cs_row: int) -> Optional[Region]:
        """A cost-state whose lineage started after the region's first entry cannot
        close all of it: its process resumed from a leaf of another, still running,
        process and restored nothing. Its own part starts at the first prompt it
        wrote; a part that starts with a repair is left merged (a killed process)."""
        start = int_value(self.rows[cs_row].entry.get("startTime"))
        dated = stamps(self.rows, [r for r in region.rows if self.rows[r].kind == CHAIN])
        if start is None or not dated or start <= min(dated) * 1000.0 + LINEAGE_SLACK_MS:
            return None
        threshold = (start - LINEAGE_SLACK_MS) / 1000.0
        node: Optional[int] = self.row_of.get(leaf) if leaf and self.owner.get(leaf) is region else self._close_tip(region)
        top: Optional[int] = None
        while node is not None and self.region_of.get(node) is region:
            ts = self.rows[node].ts
            if ts is not None and ts < threshold:
                break
            top = node
            parent = self.parent_of.get(self.rows[node].entry["uuid"])
            node = self.row_of.get(parent) if parent else None
        if top is None or node is None or self.region_of.get(node) is not region:
            return None
        if not _is_turn(self.rows[top].entry):
            return None
        chain = self._subtree([top], region)
        return self._move(region, chain | self._loose_with(region, chain))

    def _split_closed(self, region: Region, leaf: str, cs_row: int) -> Optional[Region]:
        """A cost-state that names a closed region with other totals: two processes'
        entries were merged there. Split at the branch point between the two named
        leaves; the trunk stays with the side whose tokens fit its cost-state."""
        closer = self._closer_row(region)
        if closer is None or leaf not in self.row_of:
            return None
        closer_uuid = self.rows[closer].entry["uuid"]
        path: List[str] = []
        node: Optional[str] = closer_uuid
        while node is not None and self.owner.get(node) is region:
            path.append(node)
            node = self.parent_of.get(node)
        ancestors = set(path)
        child: Optional[str] = None
        node = leaf
        while node is not None and self.owner.get(node) is region and node not in ancestors:
            child = node
            node = self.parent_of.get(node)
        if node is None or node not in ancestors or child is None or node == closer_uuid:
            return None  # a stale leaf: an ancestor or a later entry of the closing's own branch
        branch_point = node
        if self._same_request(self.row_of[child], branch_point):
            return None
        theirs = path[path.index(branch_point) - 1] if path.index(branch_point) > 0 else None
        mine_chain = self._subtree([self.row_of[child]], region)
        new = self._move(region, mine_chain | self._loose_with(region, mine_chain))
        if theirs is not None and not self._fits(region.rows, region.closing[0]):
            their_chain = self._subtree([self.row_of[theirs]], region)
            their_rows = their_chain | self._loose_with(region, their_chain)
            trunk = [r for r in region.rows if r not in their_rows]
            if self._fits(sorted(their_rows), region.closing[0]) and self._fits(sorted(set(new.rows) | set(trunk)), cs_row):
                for row in trunk:
                    self.region_of[row] = new
                    new.rows.append(row)
                    uid = self.rows[row].entry.get("uuid")
                    if isinstance(uid, str) and self.owner.get(uid) is region:
                        self.owner[uid] = new
                region.rows = sorted(their_rows)
                region.last_activity = max(region.rows, default=-1)
                new.last_activity = max(new.rows, default=-1)
        return new

    # bases and token fit ------------------------------------------------------------

    def base_row(self, region_rows: Sequence[int], lineage: Optional[int], limit: int) -> Optional[int]:
        """The cost-state a process restored: the last one of the closing lineage
        written before its first row and before its resume point gained a child."""
        bound = min(region_rows) if region_rows else limit
        chain = [r for r in region_rows if self.rows[r].kind == CHAIN]
        if chain:
            parent = self.parent_of.get(self.rows[min(chain)].entry["uuid"])
            if parent is not None and self.children.get(parent):
                bound = min(bound, min(self.children[parent]))
        bound = min(bound, limit)
        best: Optional[int] = None
        for row in self.cost_rows:
            if row >= bound:
                break
            if int_value(self.rows[row].entry.get("startTime")) == lineage:
                best = row
        return best

    def _main_usage(self, region_rows: Iterable[int]) -> Dict[str, Usage]:
        requests: Dict[str, Usage] = {}
        model_of: Dict[str, str] = {}
        for row in region_rows:
            entry = self.rows[row].entry
            if entry.get("type") != "assistant":
                continue
            message = _dict(entry.get("message"))
            model = message.get("model")
            request_id = entry.get("requestId")
            usage = message.get("usage")
            if model == SYNTHETIC_MODEL or not isinstance(request_id, str) or not isinstance(usage, dict):
                continue
            current = requests.setdefault(request_id, zero_usage())
            for key in USAGE_KEYS:
                value = int_value(usage.get(key))
                if value is not None and value > current[key]:
                    current[key] = value
            if isinstance(model, str) and model:
                model_of[request_id] = model
        out: Dict[str, Usage] = {}
        for request_id, usage in requests.items():
            add_usage(out.setdefault(model_of.get(request_id, "unknown"), zero_usage()), usage)
        return out

    def _fits(self, region_rows: Sequence[int], cs_row: int) -> bool:
        """The region's main-transcript tokens fit under the cost-state's per-model
        delta from the base its process restored."""
        usage = self._main_usage(region_rows)
        if not usage:
            return True
        end = self.rows[cs_row].entry
        base_row = self.base_row(region_rows, int_value(end.get("startTime")), cs_row)
        base = self.rows[base_row].entry if base_row is not None else {}
        end_usage, base_usage = _dict(end.get("modelUsage")), _dict(base.get("modelUsage"))
        for model, counts in usage.items():
            high, low = _dict(end_usage.get(model)), _dict(base_usage.get(model))
            for camel, snake in MODEL_USAGE_KEYS.items():
                if counts[snake] > (int_value(high.get(camel)) or 0) - (int_value(low.get(camel)) or 0):
                    return False
        return True


def segment(rows: Sequence[Row]) -> List[Region]:
    """The transcript's lifetimes, in closing order (open ones by their first row)."""
    return _Segmenter(rows).run()


def _concurrent(region: Region, regions: Sequence[Region]) -> bool:
    if len(region.rows) < 2:
        return False
    first, last = region.rows[0], region.rows[-1]
    for other in regions:
        if other is region:
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


def _gap_copies(rows: Sequence[Row], region: Region, closing: Json) -> List[int]:
    """Without the parent and without a queue-operation marker (an interactive fork),
    the copies are the chain entries before the fork point, found by time. Copies
    keep the parent's timestamps, and the time between the parent's exit and the
    fork's start is in no totalDuration, so the fork point is a gap between two
    chain entries of at least (last entry - startTime) - totalDuration; the largest
    such gap is taken. [] when no gap qualifies."""
    start, duration = int_value(closing.get("startTime")), int_value(closing.get("totalDuration"))
    chain = [i for i in region.rows if rows[i].kind == CHAIN and rows[i].ts is not None]
    dated = stamps(rows, region.rows)
    if start is None or duration is None or len(chain) < 2 or not dated:
        return []
    needed = max(dated) * 1000.0 - start - duration
    best: Optional[Tuple[float, int]] = None
    for position in range(1, len(chain)):
        before, after = rows[chain[position - 1]].ts, rows[chain[position]].ts
        if before is None or after is None:
            continue
        gap = (after - before) * 1000.0
        if gap >= needed and (best is None or gap > best[0]):
            best = (gap, position)
    if best is None:
        return []
    cut = chain[best[1]]
    return [i for i in region.rows if rows[i].kind == CHAIN and i < cut]


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
    Without a parent the copies are found by the queue-operation marker of a -p
    fork, else by the time gap at the fork point.
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
    copies = _queue_marker_copies(rows, region) or _gap_copies(rows, region, closing)
    return ForkInfo(copies, None, None)


# --------------------------------------------------------------------------------------
# Measuring one lifetime
# --------------------------------------------------------------------------------------


def _effort_of(entry: Json) -> Optional[str]:
    effort = entry.get("effort")
    if isinstance(effort, dict):
        effort = effort.get("level")
    return effort if isinstance(effort, str) and effort else None


def _is_denial(entry: Json) -> bool:
    """A tool call the permission system refused: a permissionDecision of reject or
    deny, or a toolDenialKind of a denial (user-rejected, permission-rule,
    automode-*). 'interrupted' is never a denial."""
    decision = entry.get("permissionDecision")
    if isinstance(decision, dict):
        decision = decision.get("decision")
    if isinstance(decision, str) and decision.lower() in DENIAL_DECISIONS:
        return True
    kind = entry.get("toolDenialKind")
    return isinstance(kind, str) and (kind in DENIAL_KINDS or kind.startswith(DENIAL_KIND_PREFIXES))


def _is_interrupted(entry: Json) -> bool:
    return entry.get("toolDenialKind") == INTERRUPTED_KIND


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
        self.request_ts: Dict[str, float] = {}
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
        self.dates: Set[str] = set()
        self.versions: Set[str] = set()
        self.entrypoints: Set[str] = set()
        self.git_branch: Optional[str] = None

    def stamp(self, ts: Optional[float], raw: Any) -> None:
        if ts is None or not isinstance(raw, str):
            return
        self.dates.add(utc_date(ts))
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
            self._assistant(entry, ts, sidechain=sidechain, main=main)
        elif kind == "user":
            self._user(entry, main=main)
        elif kind == "system":
            subtype = entry.get("subtype")
            if subtype == "compact_boundary":
                self.compactions += 1
            elif subtype == "api_error" and entry.get("retryAttempt") is not None:
                self.retries += 1

    def _assistant(self, entry: Json, ts: Optional[float], *, sidechain: bool, main: bool) -> None:
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
            if ts is not None and (request_id not in self.request_ts or ts < self.request_ts[request_id]):
                self.request_ts[request_id] = ts
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
        elif not _is_interrupted(entry):  # a cut-off call is neither a denial nor a failure
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

    def days(self, cost_usd: Optional[float], cost_by_model: Optional[Dict[str, Json]]) -> Optional[Json]:
        """lifetime.days (A1 D1.11) for a lifetime whose own entries span two or more
        UTC dates: requests and tokens binned by each request's first entry; each
        model's cost-state cost split by that model's tokens per day, a model with no
        transcript request by all models' tokens (all on the last day when there are
        none). Day costs add up to cost_usd exactly; null when cost_usd is null."""
        if len(self.dates) < 2:
            return None
        dates = sorted(self.dates)
        usage: Dict[str, Usage] = {day: zero_usage() for day in dates}
        requests: Counter[str] = Counter()
        tokens: Counter[Tuple[str, str]] = Counter()
        for request_id, counts in self.requests.items():
            ts = self.request_ts.get(request_id)
            day = utc_date(ts) if ts is not None else dates[-1]
            add_usage(usage.setdefault(day, zero_usage()), counts)
            requests[day] += 1
            tokens[(self.request_model.get(request_id, "unknown"), day)] += sum(counts[k] for k in USAGE_KEYS)
        days = sorted(usage)
        out: Json = {day: {"requests": requests[day], "usage": usage[day], "cost_usd": None} for day in days}
        if cost_usd is None:
            return out
        every = {day: sum(n for (_, d), n in tokens.items() if d == day) for day in days}
        raw = {day: 0.0 for day in days}
        for model, item in sorted((cost_by_model or {}).items()):
            cost = num_value(item.get("cost_usd")) or 0.0
            if not cost:
                continue
            own = {day: tokens.get((model, day), 0) for day in days}
            weights = own if sum(own.values()) else every
            denominator = sum(weights.values())
            if not denominator:
                raw[days[-1]] += cost
                continue
            for day in days:
                raw[day] += cost * weights[day] / denominator
        total = sum(raw.values())
        if total <= 0:
            raw = {day: (1.0 if day == days[-1] else 0.0) for day in days}
            total = 1.0
        assigned = 0.0
        for day in days[:-1]:
            share = _round_cost(cost_usd * raw[day] / total)
            out[day]["cost_usd"] = share
            assigned += share
        out[days[-1]]["cost_usd"] = max(0.0, _round_cost(cost_usd - assigned))
        return out


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
    days: Optional[Json] = None

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
    after its SessionEnd returned). holding: the lifetime that holds the entry
    ``uuid`` once it has settled (a lifetime that was still open at a SessionEnd).
    """

    mode: str = "all"
    offset: int = 0
    prompt_id: Optional[str] = None
    uuid: Optional[str] = None


def _selected(rows: Sequence[Row], regions: Sequence[Region], selection: Selection) -> List[Region]:
    settled = [r for r in regions if r.settled]
    if selection.mode == "all":
        return settled
    if selection.mode == "holding":
        held = next((r for r in settled if any(rows[i].entry.get("uuid") == selection.uuid for i in r.rows)), None)
        return [held] if held is not None and selection.uuid else []
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

    lifetimes: List[Lifetime]  # settled, non-empty, in closing order
    selected: int  # settled lifetimes the selection named, empty ones included
    open_after: Optional[int]  # offset of the first open activity after the last cost-state
    # Lifetimes still open whose activity runs past the start of the selected ones (a
    # concurrent writer, a process not yet exited): their first entry's uuid, or None
    # with the offset of their first row when they have no chain entry.
    open_tails: List[Tuple[Optional[str], int]] = field(default_factory=list)


def derive(
    path: Path,
    *,
    selection: Optional[Selection] = None,
    hints: Optional[Hints] = None,
    projects_root: Optional[Path] = None,
    deadline: Optional[float] = None,
) -> List[Lifetime]:
    """The settled, non-empty lifetimes of one transcript, in closing order."""
    return derive_detail(
        path, selection=selection, hints=hints, projects_root=projects_root, deadline=deadline
    ).lifetimes


def _open_after(rows: Sequence[Row], segmenter: _Segmenter) -> Optional[int]:
    """Offset of the first row after the last cost-state that belongs to no settled
    lifetime (a lifetime still open), else None."""
    cs_rows = segmenter.cost_rows
    after = cs_rows[-1] + 1 if cs_rows else 0
    for i in range(after, len(rows)):
        if rows[i].kind not in (CHAIN, LOOSE):
            continue
        region = segmenter.region_of.get(i)
        if region is None or not region.settled:
            return rows[i].offset
    return None


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
    segmenter = _Segmenter(rows)
    regions = segmenter.run()
    open_after = _open_after(rows, segmenter)
    targets = _selected(rows, regions, selection)
    if not targets:
        return Derivation([], 0, open_after)
    since = min((min(r.rows) for r in targets if r.rows), default=targets[0].closing[0])
    open_tails: List[Tuple[Optional[str], int]] = []
    for region in regions:
        if region.settled or not region.rows or max(region.rows) <= since:
            continue
        chain = [i for i in region.rows if rows[i].kind == CHAIN]
        open_tails.append((rows[chain[0]].entry["uuid"] if chain else None, rows[min(region.rows)].offset))
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
            segmenter=segmenter,
            region=region,
            measure=measures[region.index],
            files=len(files_used[region.index]),
            first=first,
            fork=fork if first else None,
            copied=copied if first else set(),
        )
        if lifetime is not None and not lifetime.empty:
            lifetimes.append(lifetime)
    return Derivation(lifetimes, len(targets), open_after, open_tails)


def _nearest_dated(rows: Sequence[Row], index: int) -> Optional[str]:
    """The raw timestamp of the dated row nearest before ``index``, else after it."""
    for i in list(range(index - 1, -1, -1)) + list(range(index + 1, len(rows))):
        raw = rows[i].entry.get("timestamp")
        if rows[i].ts is not None and isinstance(raw, str):
            return raw
    return None


def _lifetime(
    *,
    session_id: str,
    rows: Sequence[Row],
    segmenter: _Segmenter,
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
    if measure.first is not None and measure.last is not None:
        started_at, ended_at = measure.first[1], measure.last[1]
    else:
        # Spend with no dated entry of its own (calls only cost-state shows): placed at
        # the dated entry nearest before its closing cost-state.
        placed = _nearest_dated(rows, region.closing[0])
        if placed is None:
            return None
        started_at = ended_at = placed
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
        base_row = segmenter.base_row(region.rows, start_time, region.closing[0])
        base = rows[base_row].entry if base_row is not None else None
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
    per_model = delta[3] if delta else None
    return Lifetime(
        session_id=session_id,
        event_id=event_id_for(session_id, anchor),
        anchor=anchor,
        start_source=start_source,
        started_at=started_at,
        ended_at=ended_at,
        closing_offset=rows[region.closing[0]].offset,
        cost_lineage=str(start_time),
        cum_cost_start_usd=cum_start,
        cum_cost_end_usd=num_value(closing.get("totalCostUSD")),
        cost_usd=cost,
        duration_ms=delta[1] if delta else None,
        api_duration_ms=delta[2] if delta else None,
        cost_state_usage_by_model=per_model,
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
        concurrent=_concurrent(region, segmenter.regions),
        subagent_files=files,
        subagent_launches_without_file=max(0, measure.launches - files),
        copied_entries_excluded=len(copied),
        fork_parent=("found" if fork.base is not None else "not-found") if fork else None,
        shortfall=sorted(shortfall),
        days=measure.days(cost, per_model),
    )


@dataclass
class Context:
    """What the caller adds: the project, what a hook observed, and how the event was
    produced. Nothing here changes event_id or any measured number. The at-start
    fields and cleared_from_session_id come from a /clear predecessor's note, so
    they apply only to a lifetime that /clear opened."""

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
    cleared = lifetime.start_source == "clear"
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
        "cleared_from_session_id": context.cleared_from_session_id if cleared else None,
        "sprint_at_start": context.sprint_at_start if cleared else None,
        "phase_at_start": context.phase_at_start if cleared else None,
        "head_at_start": context.head_at_start if cleared else None,
        "concurrent": lifetime.concurrent,
        "recovered": context.recovered,
    }
    if lifetime.days is not None:
        lifetime_block["days"] = lifetime.days
    lifetime_block["coverage"] = {
        "subagent_files": lifetime.subagent_files,
        "subagent_launches_without_file": lifetime.subagent_launches_without_file,
        "copied_entries_excluded": lifetime.copied_entries_excluded,
        "fork_parent": lifetime.fork_parent,
        "context": "observed" if context.observed else "unknown",
        "shortfall": lifetime.shortfall,
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
