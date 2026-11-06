#!/usr/bin/env python3
"""Cross-platform tests for the session diagnostics (cloud-catcher ADR-0006 A1, Stage 1).

Runs on Linux and Windows CI with Python 3.10+ (the bash and PowerShell wrappers have
their own tests). Every fixture under tests/fixtures/transcripts is a recorded Claude
Code 2.1.316/2.1.318 transcript, redacted by tests/fixtures/transcripts/redact.py (two
are reorderings of the recorded P11 lines, see the fixtures README); the expected
values below come from each fixture's own cost-state entries (cost = closing
totalCostUSD - restored totalCostUSD; anchor = closing startTime and totalDuration) and
from requestId-deduplicated sums over each lifetime's span, never from the deriver.

Covered: one event per settled non-empty lifetime for resume, continue, /compact, /clear
(-p and interactive), -p and interactive forks, a fork of a compacted session, SIGKILL
then resume (Stage 1 shortfall), SIGTERM mid-request and mid-tool, stream-json,
concurrent resumes (one leaf, one process resuming from another's open leaf mid-tool,
one starting a new lineage, and reorderings of the cost-states), a resume from another
directory and the real cloud session (A1's five values, day bins across UTC midnight);
per-lineage sums; the UUIDv5 ids; idempotence; settled-only; the crew guard; hook-time
snapshots (byte prefixes of their final files) against final files; the /clear hand-off
(-p and interactive); the spool when the ledger lock is held; stale locks and notes;
pid reuse; a governed root above the session's directory; privacy; the measurement
fixes C03, C08, C16, C17, C18, C19, C34, C35, C36, C37; validation with and without
jsonschema; the SessionEnd budget on a size-restored copy of the heaviest fixture.

Not covered for lack of a recording: two forks of one parent from the same point where
the sibling fork also fits as a parent (the tie-break by restored cost), and a fork that
only the command-line hint identifies (its own entries end within a second of its
cost-state's restored time).
"""
from __future__ import annotations

import contextlib
import gzip
import io
import json
import os
import pathlib
import shutil
import subprocess
import sys
import tempfile
import time
import uuid
from typing import Any, Dict, List, Optional, Tuple

ROOT = pathlib.Path(__file__).resolve().parents[2]
SCRIPTS = ROOT / "scripts"
HOOK = SCRIPTS / "session-diagnostics.py"
PROJECTION = SCRIPTS / "measure-projection-cost.py"
ROTATE = SCRIPTS / "rotate-audit-log.py"
FIXTURES = ROOT / "tests" / "fixtures" / "transcripts"
SCHEMA_DIR = ROOT / "tests" / "schemas" / "diagnostic-event"
sys.path.insert(0, str(SCRIPTS))
import _diaglib as dl  # noqa: E402
import session_lifetimes as sl  # noqa: E402

# ADR-0006 A1 D1.5, restated here so the test does not trust the module's constant.
NAMESPACE = uuid.UUID("5f0c2b8e-2a7d-4d38-9a51-1c2f1d6e2006")
CANARIES = ("CANARY", "redacted", "Caveat", "command-name", "Request interrupted")
# Claude Code 2.1.318's default SessionEnd hook budget (A1 Verification, budget canary).
CLAUDE_CODE_SESSIONEND_BUDGET_S = 1.5

failures: List[str] = []
checks = 0


def check(cond: bool, msg: str) -> None:
    global checks
    checks += 1
    print(("PASS: " if cond else "FAIL: ") + msg)
    if not cond:
        failures.append(msg)


def sid(n: int) -> str:
    return f"00000000-0000-4000-8000-{n:012d}"


def close(a: Optional[float], b: Optional[float]) -> bool:
    if a is None or b is None:
        return a is None and b is None
    return abs(a - b) < 5e-10


# ---------------------------------------------------------------------------------
# Expected events, per fixture and session (sessions numbered by first entry time)
# ---------------------------------------------------------------------------------


def E(start: str, *, end: float, base: Optional[float], anchor: Tuple[int, int], usage: Tuple[int, ...],
      side: Tuple[int, ...] = (0, 0, 0, 0), ts: Optional[str] = None, **extra: Any) -> Dict[str, Any]:
    return dict(start=start, end=end, base=base, anchor=anchor, usage=usage, side=side, ts=ts, **extra)


SHORT_ALL = ["model-a:cache_creation_input_tokens", "model-a:cache_read_input_tokens",
             "model-a:input_tokens", "model-a:output_tokens"]

EXPECTED: Dict[str, Dict[int, List[Dict[str, Any]]]] = {
    # P1: startup, --resume, --continue, --resume '/compact', --resume '/clear' (a lifetime of
    # queue entries only: no event), a fork of the compacted session, and the session /clear
    # created (its own first lifetime is empty; its --continue lifetime is an event).
    "p01-resume-compact-clear-fork": {
        1: [
            E("startup", end=0.00144132, base=0.0, anchor=(1793824985010, 2984), usage=(2, 5, 11382, 6624),
              ts="2026-11-04T20:43:07.978Z", turns=1, duration=2984, branch="branch-1"),
            E("resume", end=0.00231726, base=0.00144132, anchor=(1793824985010, 4698), usage=(2, 5, 14424, 3645),
              ts="2026-11-04T20:43:37.353Z", duration=1714),
            E("resume", end=0.00252218, base=0.00231726, anchor=(1793824985010, 6443), usage=(2, 5, 18022, 110),
              ts="2026-11-04T20:43:40.294Z"),
            E("resume", end=0.004103805, base=0.00252218, anchor=(1793824985010, 15732), usage=(0, 0, 0, 0),
              ts="2026-11-04T20:44:08.072Z", compactions=1, turns=0, duration=9289),
        ],
        2: [
            E("fork", end=0.005351845, base=0.004103805, anchor=(1793824985010, 16787), usage=(2, 5, 13954, 5529),
              ts="2026-11-04T20:44:10.189Z", copies=12, fork_parent="found", forked_from=1, compactions=0),
        ],
        3: [
            E("resume", end=0.00097794, base=0.0, anchor=(1793825242298, 1828), usage=(2, 6, 13954, 4176),
              ts="2026-11-04T20:47:28.422Z"),
        ],
    },
    # P2: -p fork of an uncompacted session (26 copied entries).
    "p02-fork": {
        1: [
            E("startup", end=0.00080429, base=0.0, anchor=(1793825184195, 2858), usage=(4, 83, 7859, 3419),
              ts="2026-11-04T20:46:27.036Z", tools={"Bash": 1}),
            E("resume", end=0.00445579, base=0.00080429, anchor=(1793825184195, 4305), usage=(2, 47, 0, 18139),
              ts="2026-11-04T20:46:29.827Z"),
        ],
        2: [
            E("fork", end=0.00466108, base=0.00445579, anchor=(1793825184195, 6460), usage=(2, 5, 18139, 106),
              ts="2026-11-04T20:46:32.988Z", copies=26, fork_parent="found", forked_from=1, tools={}),
        ],
    },
    # P3: interactive startup, /clear, a turn in the new session, /exit; a later resume of the
    # first session with no turn wrote two equal-total cost-states: re-writes, no event.
    "p03-clear-interactive": {
        1: [
            E("startup", end=0.00198328, base=0.0, anchor=(1793825307473, 29482), usage=(2, 5, 25998, 7983),
              ts="2026-11-04T20:48:49.718Z"),
        ],
        2: [
            E("clear", end=0.00150472, base=0.0, anchor=(1793825336955, 33807), usage=(2, 5, 28652, 5450),
              ts="2026-11-04T20:49:15.849Z"),
        ],
    },
    # P4: a lifetime SIGKILLed mid-session (no cost-state) and the resume after it. Stage 1:
    # one event for both; its tokens exceed the cost-state delta (4/578/38815/1219) on every key.
    "p04-sigkill-resume": {
        1: [
            E("startup", end=0.00144132, base=0.0, anchor=(1793825405227, 2295), usage=(2, 5, 11382, 6624),
              ts="2026-11-04T20:50:07.506Z"),
            E("resume", end=0.00236267, base=0.00144132, anchor=(1793825405227, 7557), usage=(10, 1102, 90101, 5889),
              ts="2026-11-04T20:50:41.308Z", tools={"Bash": 2, "Read": 1}, failures={"Bash": 1}, turns=2,
              shortfall=SHORT_ALL, cost_state=(4, 578, 38815, 1219)),
        ],
    },
    # P5: a background subagent in the parent's first lifetime, a fork, then a resume of the parent.
    "p05-fork-subagent": {
        1: [
            E("startup", end=0.003403745, base=0.0, anchor=(1793825684600, 5630), usage=(8, 162, 48112, 17992),
              side=(2, 5, 0, 10101), ts="2026-11-04T20:54:50.216Z", tools={"Agent": 1}, subagents=1, files=1),
            E("resume", end=0.003617475, base=0.003403745, anchor=(1793825684600, 6908), usage=(2, 5, 19243, 93),
              ts="2026-11-04T20:55:04.349Z", subagents=0, files=0),
        ],
        2: [
            E("fork", end=0.003617475, base=0.003403745, anchor=(1793825684600, 7664), usage=(2, 5, 19243, 93),
              ts="2026-11-04T20:55:01.728Z", copies=23, fork_parent="found", forked_from=1, subagents=0),
        ],
    },
    # P6: created in project A, resumed from project B; both lifetimes live in A's transcript.
    "p06-resume-other-dir": {
        1: [
            E("startup", end=0.00144092, base=0.0, anchor=(1793825714403, 2034), usage=(2, 5, 11382, 6622),
              ts="2026-11-04T20:55:16.420Z"),
            E("resume", end=0.00234765, base=0.00144092, anchor=(1793825714403, 3607), usage=(2, 5, 14423, 3799),
              ts="2026-11-04T20:55:19.319Z"),
        ],
    },
    # P7: SIGTERM mid-request. The second lifetime has a cost-state but no request and no
    # spend (the streamed reply is in neither file): no event.
    "p07-sigterm": {
        1: [
            E("startup", end=0.00144132, base=0.0, anchor=(1793825758384, 5054), usage=(2, 5, 11382, 6624),
              ts="2026-11-04T20:56:03.415Z"),
        ],
    },
    # P8: stream-json, two turns ended by EOF, then two turns ended by SIGTERM.
    "p08-stream-json-sigterm": {
        1: [
            E("startup", end=0.0023193, base=0.0, anchor=(1793825794959, 4812), usage=(4, 10, 25810, 10279),
              ts="2026-11-04T20:56:38.758Z", turns=2),
            E("resume", end=0.00273391, base=0.0023193, anchor=(1793825794959, 9014), usage=(4, 10, 36121, 240),
              ts="2026-11-04T20:56:52.428Z", turns=2),
        ],
    },
    # P9: -p fork (the probe that read the fork's command line).
    "p09-fork-cmdline": {
        1: [
            E("startup", end=0.00144132, base=0.0, anchor=(1793825916944, 5135), usage=(2, 5, 11382, 6624),
              ts="2026-11-04T20:58:42.051Z"),
        ],
        2: [
            E("fork", end=0.00231726, base=0.00144132, anchor=(1793825916944, 6073), usage=(2, 5, 14424, 3645),
              ts="2026-11-04T20:58:47.211Z", copies=14, fork_parent="found", forked_from=1),
        ],
    },
    # P10: startup, resume, '-p /clear' (empty lifetimes on both sides), then an interactive
    # resume with a turn ended by /clear: its cost-state was written after SessionEnd(clear).
    "p10-clear-after-resume": {
        1: [
            E("startup", end=0.00144132, base=0.0, anchor=(1793825971922, 4514), usage=(2, 5, 11382, 6624),
              ts="2026-11-04T20:59:36.398Z"),
            E("resume", end=0.00231726, base=0.00144132, anchor=(1793825971922, 5375), usage=(2, 5, 14424, 3645),
              ts="2026-11-04T20:59:41.567Z"),
            E("resume", end=0.00575458, base=0.00231726, anchor=(1793825971922, 11733), usage=(2, 61, 18022, 16132),
              ts="2026-11-04T21:00:05.192Z"),
        ],
        2: [],
        3: [],
    },
    # P11: two -p processes resumed the session at the same time from the same leaf. Each
    # restored 0.00144132, and each final cost-state leaves out the other's spend.
    "p11-concurrent-resumes": {
        1: [
            E("startup", end=0.00144132, base=0.0, anchor=(1793826271952, 5525), usage=(2, 5, 11382, 6624),
              ts="2026-11-04T21:04:37.460Z", concurrent=False),
            E("resume", end=0.00241266, base=0.00144132, anchor=(1793826271952, 8005), usage=(2, 193, 14424, 3652),
              ts="2026-11-04T21:04:41.383Z", concurrent=True, cost_state=(2, 193, 14424, 3652)),
            E("resume", end=0.00243496, base=0.00144132, anchor=(1793826271952, 7939), usage=(2, 236, 14424, 3656),
              ts="2026-11-04T21:04:41.443Z", concurrent=True, cost_state=(2, 236, 14424, 3656)),
        ],
    },
    # Interactive fork (no queue-operation entries; 18 copies) of a -p parent.
    "if-interactive-fork": {
        1: [
            E("startup", end=0.00172288, base=0.0, anchor=(1793833347901, 7715), usage=(4, 127, 29398, 6825),
              ts="2026-11-04T23:02:35.588Z", tools={"Read": 1}),
        ],
        2: [
            E("fork", end=0.00513955, base=0.00172288, anchor=(1793833347901, 24158), usage=(2, 32, 18207, 16092),
              ts="2026-11-04T23:02:53.893Z", copies=18, fork_parent="found", forked_from=1),
        ],
    },
    # Live review session 5f4c3152 (2.1.318): process A resumes and runs a 20 s Bash call;
    # process B resumes from A's tool_use while it runs (its first entry repairs the
    # dangling call with an 'interrupted' result), takes a turn and exits; then A's real
    # tool result arrives and A exits. Each process's own delta; B's closing comes first.
    "l01-concurrent-mid-tool": {
        1: [
            E("startup", end=0.00095423, base=0.0, anchor=(1793993315909, 1618), usage=(2, 4, 13943, 4063),
              ts="2026-11-06T19:28:37.511Z"),
            E("resume", end=0.0011847, base=0.00095423, anchor=(1793993315909, 2525), usage=(2, 6, 18107, 231),
              ts="2026-11-06T19:28:57.148Z", tools={}, failures={}, denials=0, turns=1, cost_state=(2, 6, 18107, 231)),
            E("resume", end=0.0021025, base=0.00095423, anchor=(1793993315909, 24069), usage=(4, 105, 32537, 3850),
              ts="2026-11-06T19:29:16.116Z", tools={"Bash": 1}, failures={}, denials=0, turns=1, concurrent=True,
              cost_state=(4, 105, 32537, 3850)),
        ],
    },
    # Live review session a70ab782: interactive A (startup) takes a turn and idles; -p B
    # resumes from A's leaf before A wrote any cost-state, so B restores nothing and starts
    # a lineage of its own; then A takes a second turn and exits (/exit: a re-write).
    "l02-concurrent-new-lineage": {
        1: [
            E("resume", end=0.00131309, base=0.0, anchor=(1793993587463, 1931), usage=(2, 4, 29129, 5098),
              ts="2026-11-06T19:33:09.383Z", turns=1, cost_state=(2, 4, 29129, 5098)),
            E("startup", end=0.00319151, base=0.0, anchor=(1793993577357, 46838), usage=(4, 10, 57770, 10220),
              ts="2026-11-06T19:33:11.757Z", turns=2, concurrent=True),
        ],
    },
    # Live review session 7c85a1a3: SIGTERM during an allowed Bash call (the cost-state is
    # written first, then the cancelled tool result and its attachments: still that
    # lifetime's); a resume SIGKILLed during another Bash call; a resume whose first entry
    # repairs that call with an 'interrupted' result (neither a denial nor a failure).
    "l03-sigterm-mid-tool-then-sigkill": {
        1: [
            E("startup", end=0.00100933, base=0.0, anchor=(1793993194339, 2620), usage=(2, 99, 13943, 4101),
              ts="2026-11-06T19:26:36.973Z", tools={"Bash": 1}, failures={"Bash": 1}, denials=0),
            E("resume", end=0.00124329, base=0.00100933, anchor=(1793993194339, 3880), usage=(4, 107, 36360, 505),
              ts="2026-11-06T19:27:18.920Z", tools={"Bash": 1}, failures={}, denials=0, turns=2,
              shortfall=SHORT_ALL, cost_state=(2, 8, 18316, 233), started="2026-11-06T19:27:07.695Z"),
        ],
    },
    # Review probes. C03: a foreground subagent (its Read and its tokens count). C08: a config
    # and a hook denial (a denial, not a failure). C18: only retried API errors (no request, no
    # spend: no event). C36: an all-failure session (no event) and a mixed one ('<synthetic>' never
    # becomes a model).
    "r-c03-subagent": {
        1: [
            E("startup", end=0.002689595, base=0.0, anchor=(1793774440290, 10704), usage=(10, 724, 17327, 11162),
              side=(4, 511, 2638, 2837), tools={"Agent": 1, "Read": 1}, subagents=1, files=1,
              cost_state=(1252, 743, 17327, 11162)),
        ],
    },
    "r-c08-config-denial": {
        1: [
            E("startup", end=0.00061538, base=0.0, anchor=(1793774623205, 6355), usage=(4, 144, 9038, 1614),
              tools={"Bash": 1}, failures={}, denials=1),
        ],
    },
    "r-c08-hook-denial": {
        1: [
            E("startup", end=0.00054704, base=0.0, anchor=(1793774676061, 5158), usage=(4, 83, 9044, 1432),
              tools={"Bash": 1}, failures={}, denials=1),
        ],
    },
    "r-c18-api-retries": {1: []},
    "r-c36-synthetic": {
        1: [],
        2: [
            E("startup", end=0.00060929, base=0.0, anchor=(1793775881173, 1325), usage=(2, 4, 649, 3003)),
        ],
    },
}
# The recorded P11 lines in two other orders the recording's millisecond race allows: B's
# reply before A's cost-state, and (b) B's last-prompt before it too, plus an equal-total
# re-write of each cost-state. Same three events.
EXPECTED["p11a-concurrent-reordered"] = EXPECTED["p11-concurrent-resumes"]
EXPECTED["p11b-concurrent-rewrites"] = EXPECTED["p11-concurrent-resumes"]

# The real cloud session (2026-10-31 to 2026-11-05), skeleton cut after its sixth closing
# point. A1's Verification: cut after the fifth, five events of these values.
REAL_A1 = [7.1773923, 27.49865245, 0.9899525, 152.047308, 62.2513088]
REAL_LINEAGE = 1793461284021
REAL_EXPECTED = [
    E("startup", end=7.1773923, base=0.0, anchor=(REAL_LINEAGE, 1037985), usage=(164, 44792, 1242782, 231240),
      ts="2026-10-31T15:53:43.230Z", turns=1, models=["model-a"], api_duration=624187, effort="max",
      branch="branch-1", thinking=507317),
    E("resume", end=34.67604475, base=7.1773923, anchor=(REAL_LINEAGE, 5586241),
      usage=(1170, 255479, 22532037, 413208), ts="2026-10-31T17:42:03.345Z", turns=5, models=["model-a"]),
    E("resume", end=35.66599725, base=34.67604475, anchor=(REAL_LINEAGE, 6182477), usage=(66, 1072, 2120194, 10942),
      ts="2026-10-31T18:32:05.426Z", turns=0, models=["model-a"]),
    E("resume", end=187.71330525, base=35.66599725, anchor=(REAL_LINEAGE, 23216712),
      usage=(3198, 2451387, 327128414, 6696884), side=(3168, 2330206, 318690497, 5390340),
      ts="2026-11-04T08:35:18.838Z", files=20, subagents=20, denials=5, turns=1, models=["model-c"]),
    E("resume", end=249.96461405, base=187.71330525, anchor=(REAL_LINEAGE, 29608298),
      usage=(872, 1011231, 126972005, 2791213), side=(816, 936195, 106180520, 1959940),
      ts="2026-11-04T22:20:42.265Z", files=5, subagents=5, turns=1, models=["model-c"]),
    E("resume", end=299.46748825, base=249.96461405, anchor=(REAL_LINEAGE, 35833781),
      usage=(780, 849813, 96541332, 2305947), side=(682, 779754, 85494810, 1939113),
      ts="2026-11-05T00:00:23.912Z", files=6, subagents=6, compactions=1, turns=0, models=["model-c"],
      days={"2026-11-04": (387, (778, 847560, 96277408, 2302216), 49.368856086),
            "2026-11-05": (1, (2, 2253, 263924, 3731), 0.134018114)}),
]
REAL_CUT_LINE = 1122  # the fifth closing point's cost-state (0-based line index)
REAL_CUT_TS = "2026-11-04T22:21:02.066Z"  # the sixth lifetime's first entry

# Hook-time snapshots: how many events a SessionEnd at that point settles, and whether
# they equal the final files' events number for number. l01's second snapshot is process
# B's SessionEnd: A's first request is merged into B's lifetime there (shortfall shows it),
# because nothing on disk yet tells a still-running A from a killed one; the final files do.
SNAPSHOTS: Dict[str, List[Tuple[int, bool]]] = {
    "l01-concurrent-mid-tool": [(1, True), (1, False), (1, True)],
    "l02-concurrent-new-lineage": [(1, True), (1, True)],
    "l03-sigterm-mid-tool-then-sigkill": [(1, True), (1, True)],
    "p01-resume-compact-clear-fork": [(1, True)] * 5 + [(1, True), (0, True), (1, True)],
    "p02-fork": [(1, True)] * 3,
    "p03-clear-interactive": [(0, True), (1, True), (1, True)],
    "p04-sigkill-resume": [(1, True)] * 2,
    "p05-fork-subagent": [(1, True)] * 3,
    "p06-resume-other-dir": [(1, True)] * 2,
    "p07-sigterm": [(1, True), (0, True)],
    "p08-stream-json-sigterm": [(1, True)] * 2,
    "p11-concurrent-resumes": [(1, True)] * 3,
}


# ---------------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------------


def materialize(name: str, into: pathlib.Path) -> pathlib.Path:
    """Copy a fixture into a scratch dir, decompressing *.gz files (stdlib gzip)."""
    target = into / name
    shutil.copytree(FIXTURES / name, target)
    for packed in sorted(target.rglob("*.gz")):
        with gzip.open(packed, "rb") as handle:
            packed.with_suffix("").write_bytes(handle.read())
        packed.unlink()
    return target


def transcript(fixture: pathlib.Path, n: int) -> pathlib.Path:
    return next(fixture.glob(f"projects/*/{sid(n)}.jsonl"))


def events_of(path: pathlib.Path, context: Optional[sl.Context] = None, **kwargs: Any) -> List[Dict[str, Any]]:
    context = context or sl.Context(project="fixture")
    return sl.lifetimes_to_events(sl.derive(path, **kwargs), context)


def schema_problem(event: Dict[str, Any]) -> Optional[str]:
    return dl.validate_event(event, prefer_jsonschema=True) or dl.structural_problem(event)


def compare(label: str, event: Dict[str, Any], exp: Dict[str, Any], session: str) -> None:
    life, counts, cov = event["lifetime"], event["counts"], event["lifetime"]["coverage"]
    anchor = f"cs:{exp['anchor'][0]}:{exp['anchor'][1]}"
    expected_id = str(uuid.uuid5(NAMESPACE, f"session-lifetime|{session}|{anchor}"))
    check(event["event_id"] == expected_id and life["anchor"] == anchor, f"{label}: UUIDv5 id over {anchor}")
    check(life["start_source"] == exp["start"], f"{label}: start_source {exp['start']} (got {life['start_source']})")
    cost = None if exp["base"] is None else round(exp["end"] - exp["base"], 10)
    check(close(event["cost_usd"], cost), f"{label}: cost_usd {cost} = {exp['end']} - {exp['base']} (got {event['cost_usd']})")
    check(close(life["cum_cost_end_usd"], exp["end"]) and close(life["cum_cost_start_usd"], exp["base"]),
          f"{label}: anchors cum_cost_start/end = {exp['base']}/{exp['end']}")
    check(life["cost_lineage"] == str(exp["anchor"][0]), f"{label}: cost_lineage {exp['anchor'][0]}")
    usage = tuple(event["usage"][k] for k in sl.USAGE_KEYS)
    check(usage == exp["usage"], f"{label}: usage {exp['usage']} (got {usage})")
    side = tuple(event["sidechain_usage"][k] for k in sl.USAGE_KEYS)
    check(side == exp["side"], f"{label}: sidechain_usage {exp['side']} (got {side})")
    by_model = tuple(sum(u[k] for u in event["usage_by_model"].values()) for k in sl.USAGE_KEYS)
    check(by_model == usage and sl.SYNTHETIC_MODEL not in event["usage_by_model"],
          f"{label}: usage_by_model sums to usage from the transcript, no '<synthetic>' (C16, C36)")
    models = exp.get("models", ["model-a"] if any(exp["usage"]) else [])
    check(sorted(event["usage_by_model"]) == models and event["model"] == (models[0] if models else None),
          f"{label}: usage_by_model keys and model {models} (got {sorted(event['usage_by_model'])}, {event['model']})")
    if exp.get("ts"):
        check(event["ts"] == exp["ts"] == life["ended_at"], f"{label}: ts {exp['ts']} from the entries (got {event['ts']})")
    simple = (("tools", counts["tool_calls_by_tool"]), ("failures", counts["tool_failures_by_tool"]),
              ("denials", counts["permission_denials"]), ("compactions", counts["compactions"]),
              ("subagents", counts["subagents"]), ("turns", event["num_turns"]),
              ("files", cov["subagent_files"]), ("copies", cov["copied_entries_excluded"]),
              ("fork_parent", cov["fork_parent"]), ("duration", event["duration_ms"]),
              ("api_duration", event["api_duration_ms"]), ("effort", event["effort"]),
              ("branch", event["git_branch"]), ("thinking", event["thinking_duration_ms"]),
              ("started", life["started_at"]))
    for key, actual in simple:
        if key in exp:
            check(actual == exp[key], f"{label}: {key} {exp[key]!r} (got {actual!r})")
    check(cov["shortfall"] == exp.get("shortfall", []), f"{label}: shortfall {exp.get('shortfall', [])} (got {cov['shortfall']})")
    if "concurrent" in exp:
        check(life["concurrent"] is exp["concurrent"], f"{label}: concurrent {exp['concurrent']}")
    check(cov["subagent_launches_without_file"] == 0, f"{label}: every Agent or Task launch has its agent file")
    if "forked_from" in exp:
        check(life["forked_from_session_id"] == sid(exp["forked_from"]), f"{label}: forked_from_session_id")
    if "cost_state" in exp:
        delta = tuple(sum(u[k] for u in event["cost_state_usage_by_model"].values()) for k in sl.USAGE_KEYS)
        check(delta == exp["cost_state"], f"{label}: cost_state_usage_by_model is the cost-state delta {exp['cost_state']}")
    if event["cost_usd"] is not None:
        per_model = sum(u["cost_usd"] for u in event["cost_state_usage_by_model"].values())
        check(close(per_model, event["cost_usd"]), f"{label}: per-model cost-state deltas add up to cost_usd")
    if "days" in exp:
        days = life.get("days", {})
        got = {d: (v["requests"], tuple(v["usage"][k] for k in sl.USAGE_KEYS), v["cost_usd"]) for d, v in days.items()}
        check(sorted(got) == sorted(exp["days"]) and all(
            got[d][0] == exp["days"][d][0] and got[d][1] == exp["days"][d][1] and close(got[d][2], exp["days"][d][2])
            for d in exp["days"]), f"{label}: lifetime.days bins by UTC day {exp['days']} (got {got})")
        sums = tuple(sum(v[1][i] for v in got.values()) for i in range(4))
        check(sums == usage and close(round(sum(v[2] for v in got.values()), 10), event["cost_usd"]),
              f"{label}: the day bins add up to usage and cost_usd")
    elif life["started_at"][:10] == life["ended_at"][:10]:
        check("days" not in life, f"{label}: no lifetime.days within one UTC day")
    check(sum(counts["tool_calls_by_tool"].values()) == counts["tool_calls"], f"{label}: tool_calls is the sum by tool")
    check(not any(k in event.get("labels", {}) for k in ("permission_mode", "end_reason", "hook_event")),
          f"{label}: no permission_mode or payload labels (C37)")
    problem = schema_problem(event)
    check(problem is None, f"{label}: validates against schema 1.1" + (f" ({problem})" if problem else ""))
    blob = json.dumps(event)
    check(not any(c in blob for c in CANARIES), f"{label}: no prompt, response or tool text in the event")


def run_hook(payload: Dict[str, Any], env_extra: Optional[Dict[str, str]] = None,
             raw: Optional[bytes] = None) -> "subprocess.CompletedProcess[bytes]":
    env = {k: v for k, v in os.environ.items()
           if k not in ("CLAUDE_PROJECT_DIR", "DIAGNOSTICS_LOG_PATH", "AUTOMATE_RUN", "CLAUDE_PID",
                        "DIAGNOSTICS_BUDGET_MS", "DIAGNOSTICS_NO_JSONSCHEMA")}
    env.update(env_extra or {})
    data = raw if raw is not None else json.dumps(payload).encode("utf-8")
    completed = subprocess.run([sys.executable, str(HOOK)], input=data, check=False, capture_output=True, env=env,
                               timeout=120)
    if completed.stdout:
        check(False, f"the hook prints nothing to stdout (got {completed.stdout[:120]!r})")
    return completed


def make_project(base: pathlib.Path, name: str = "proj", *, council: bool = True,
                 sprint: Any = 9, phase: Any = 2) -> pathlib.Path:
    proj = base / name
    (proj / ".git").mkdir(parents=True)
    (proj / ".harness").mkdir()
    (proj / ".harness" / "sprint-state.json").write_text(
        json.dumps({"current_sprint": sprint, "current_phase": phase}), encoding="utf-8")
    if council:
        (proj / ".council").mkdir()
    return proj


def ledger_events(proj: pathlib.Path) -> List[Dict[str, Any]]:
    log = proj / ".council" / "diagnostics.jsonl"
    if not log.exists():
        return []
    return [json.loads(line) for line in log.read_text(encoding="utf-8").splitlines() if line.strip()]


def run_files(proj: pathlib.Path, pattern: str = "*.json") -> List[str]:
    folder = proj / ".council" / "state" / "run"
    return sorted(p.name for p in folder.glob(pattern)) if folder.is_dir() else []


def end_payload(path: pathlib.Path, session: str, cwd: pathlib.Path, reason: str = "other",
                prompt_id: Optional[str] = None) -> Dict[str, Any]:
    payload: Dict[str, Any] = {"session_id": session, "transcript_path": str(path), "cwd": str(cwd),
                               "hook_event_name": "SessionEnd", "reason": reason}
    if prompt_id:
        payload["prompt_id"] = prompt_id
    return payload


def tree_state(path: pathlib.Path) -> Dict[str, bytes]:
    return {p.relative_to(path).as_posix(): (p.read_bytes() if p.is_file() else b"<dir>")
            for p in sorted(path.rglob("*"))}


def numbers(event: Dict[str, Any]) -> Dict[str, Any]:
    """The part of an event every observer must agree on: id, ts and numbers."""
    keep = ("event_id", "ts", "model", "effort", "git_branch", "usage", "usage_by_model", "sidechain_usage",
            "cost_state_usage_by_model", "cost_usd", "duration_ms", "api_duration_ms", "thinking_duration_ms",
            "num_turns", "counts")
    life = event["lifetime"]
    return {**{k: event.get(k) for k in keep},
            "lifetime": {k: life.get(k) for k in ("anchor", "start_source", "started_at", "ended_at", "cost_lineage",
                                                   "cum_cost_start_usd", "cum_cost_end_usd", "forked_from_session_id",
                                                   "concurrent", "days")},
            "coverage": {k: life["coverage"][k] for k in ("subagent_files", "subagent_launches_without_file",
                                                           "copied_entries_excluded", "fork_parent", "shortfall")}}


def final_numbers(*paths: pathlib.Path) -> Dict[str, Dict[str, Any]]:
    """The events derived from the final files, by id (what a backfill would mint)."""
    out: Dict[str, Dict[str, Any]] = {}
    for path in paths:
        for event in events_of(path):
            out[event["event_id"]] = numbers(event)
    return out


def check_ledger_numbers(label: str, proj: pathlib.Path, expected: Dict[str, Dict[str, Any]]) -> None:
    """Every ledger event equals the final files' event of the same id, number for number
    (ts and ended_at included: A1 D1.5, never the hook's clock)."""
    events = ledger_events(proj)
    bad = [e["event_id"][:8] for e in events if e["event_id"] not in expected or numbers(e) != expected[e["event_id"]]]
    check(bool(events) and not bad, f"{label}: the ledger's events equal the final files' events, number for number {bad}")


# ---------------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------------


def test_fixtures(tmp: pathlib.Path) -> None:
    """Every recorded fixture: one event per non-empty settled lifetime, values from its cost-states."""
    for name, sessions in EXPECTED.items():
        fixture = materialize(name, tmp)
        lineage_costs: Dict[str, float] = {}
        for n, expected in sessions.items():
            events = events_of(transcript(fixture, n))
            check(len(events) == len(expected), f"{name}/{n}: {len(expected)} event(s) (got {len(events)})")
            for i, (event, exp) in enumerate(zip(events, expected, strict=False)):
                compare(f"{name}/{n}#{i + 1}", event, exp, sid(n))
                lineage_costs[event["lifetime"]["cost_lineage"]] = lineage_costs.get(
                    event["lifetime"]["cost_lineage"], 0.0) + (event["cost_usd"] or 0.0)
        if name == "p01-resume-compact-clear-fork":
            # parent's last cost-state + the fork's own spend; the /clear session is its own lineage
            check(close(lineage_costs["1793824985010"], 0.004103805 + (0.005351845 - 0.004103805)),
                  "p01: lineage sum = parent's last cost-state + fork's own spend")
            check(close(lineage_costs["1793825242298"], 0.00097794), "p01: the /clear session's lineage sums to its last cost-state")
        if name == "p02-fork":
            check(close(lineage_costs["1793825184195"], 0.00445579 + (0.00466108 - 0.00445579)),
                  "p02: lineage sum = parent's last cost-state + fork's own spend")
        if name == "p05-fork-subagent":
            check(close(lineage_costs["1793825684600"], 0.003617475 + (0.003617475 - 0.003403745)),
                  "p05: lineage sum = parent's last cost-state + fork's own spend")
        if name.startswith("p11"):
            total = lineage_costs["1793826271952"]
            check(close(total, 0.0034063) and total > 0.00243496,
                  f"{name}: concurrent resumes sum to 0.0034063, more than the last cost-state (each left out the other)")
        if name == "l01-concurrent-mid-tool":
            check(close(lineage_costs["1793993315909"], 0.00095423 + 0.00023047 + 0.00114827),
                  "l01: each process's own delta; the sum exceeds the last cost-state by the delta it left out")
        if name == "l02-concurrent-new-lineage":
            check(close(lineage_costs["1793993577357"], 0.00319151) and close(lineage_costs["1793993587463"], 0.00131309),
                  "l02: per lineage, the events sum to that lineage's last cost-state (no base from another lineage)")
        shutil.rmtree(fixture)


def test_real_session(tmp: pathlib.Path) -> None:
    """A1's real-session reconciliation, day bins, and stability when a sixth lifetime is appended."""
    fixture = materialize("real-session", tmp)
    full_path = transcript(fixture, 1)
    full = events_of(full_path)
    check(len(full) == 6, f"real session skeleton: six settled lifetimes (got {len(full)})")
    for i, (event, exp) in enumerate(zip(full, REAL_EXPECTED, strict=False)):
        compare(f"real/{i + 1}", event, exp, sid(1))
    day_sums: Dict[str, float] = {}
    for event in full:
        bins = event["lifetime"].get("days")
        for day, value in (bins.items() if bins else [(event["ts"][:10], {"cost_usd": event["cost_usd"]})]):
            day_sums[day] = day_sums.get(day, 0.0) + value["cost_usd"]
    check(close(day_sums.get("2026-10-31"), 35.66599725)
          and close(day_sums.get("2026-11-04"), 152.047308 + 62.2513088 + 49.368856086)
          and close(day_sums.get("2026-11-05"), 0.134018114),
          f"day sums use the sixth lifetime's bins: 263.667472886 USD on 2026-11-04, 0.134018114 on 2026-11-05 "
          f"(by ts alone 214.2986168 and 49.5028742) (got {day_sums})")

    # The files as they stood when the fifth closing cost-state was written.
    cut = tmp / "real-cut"
    shutil.copytree(fixture, cut)
    cut_path = transcript(cut, 1)
    lines = cut_path.read_bytes().splitlines(keepends=True)
    cut_path.write_bytes(b"".join(lines[: REAL_CUT_LINE + 1]))
    for agent in cut_path.parent.joinpath(sid(1), "subagents").rglob("agent-*.jsonl"):
        kept = [line for line in agent.read_bytes().splitlines(keepends=True)
                if json.loads(line).get("timestamp", "") < REAL_CUT_TS]
        if kept:
            agent.write_bytes(b"".join(kept))
        else:
            agent.unlink()
    events = events_of(cut_path)
    costs = [e["cost_usd"] for e in events]
    check(len(events) == 5 and all(close(a, b) for a, b in zip(costs, REAL_A1, strict=False)),
          f"A1: five events of {REAL_A1} (got {costs})")
    check(close(sum(costs), 249.96461405), f"A1: they sum to 249.96461405, the last cost-state (got {sum(costs)})")
    check(events[-1]["ts"] == "2026-11-04T22:20:42.265Z",
          "A1: the fifth event's ts is its last subagent entry 22:20:42.265Z, not the main transcript's 21:39:41")
    by_day: Dict[str, float] = {}
    for event in events:
        by_day[event["ts"][:10]] = by_day.get(event["ts"][:10], 0.0) + event["cost_usd"]
    check(round(by_day.get("2026-10-31", 0), 2) == 35.67 and round(by_day.get("2026-11-04", 0), 2) == 214.30,
          f"A1: by ts, 35.67 USD on 2026-10-31 and 214.30 USD on 2026-11-04 (got {by_day})")
    check([numbers(e) for e in events] == [numbers(e) for e in full[:5]],
          "the five events are unchanged, id for id and number for number, once a sixth lifetime is appended")
    try:
        sl.derive(full_path, deadline=time.monotonic() - 1.0)
        check(False, "a passed deadline raises DeadlineExceeded")
    except sl.DeadlineExceeded:
        check(True, "a passed deadline raises DeadlineExceeded, never a partial result")


def test_snapshots(tmp: pathlib.Path) -> None:
    """Hook-time snapshots are byte prefixes of their final files, and the events derived
    from them equal those derived from the final files (counts recorded per snapshot)."""
    manifests = sorted(FIXTURES.glob("*/snapshots/manifest.json"))
    check(sorted(m.parent.parent.name for m in manifests) == sorted(SNAPSHOTS),
          "every fixture with snapshots has its expected counts")
    for manifest in manifests:
        name = manifest.parent.parent.name
        fixture = materialize(name, tmp / "snap")
        final_events: Dict[str, Dict[str, Any]] = {}
        for path in fixture.glob("projects/*/*.jsonl"):
            for event in events_of(path):
                final_events[event["event_id"]] = event
        entries = json.loads(manifest.read_text(encoding="utf-8"))
        expected = SNAPSHOTS.get(name, [])
        check(len(entries) == len(expected), f"{name}: {len(expected)} snapshot expectations (got {len(entries)})")
        for entry, (count, matches) in zip(entries, expected, strict=False):
            target = fixture / entry["transcript"]
            original = target.read_bytes()
            snapshot = (fixture / entry["snapshot"]).read_bytes()
            label = f"{name} {entry['snapshot']} ({entry['reason']})"
            check(original.startswith(snapshot) and len(snapshot.splitlines()) == entry["lines"],
                  f"{label}: a byte prefix of the final file ({entry['lines']} lines)")
            target.write_bytes(snapshot)
            selection = sl.Selection("last_before", target.stat().st_size, entry["prompt_id"])
            live = events_of(target, selection=selection)
            target.write_bytes(original)
            check(len(live) == count, f"{label}: {count} event(s) at hook time (got {len(live)})")
            if entry["reason"] == "clear":
                check(all(e["event_id"] in final_events for e in live) and not any(
                    e["lifetime"]["anchor"] in {f["lifetime"]["anchor"] for f in final_events.values()
                                                if f["session_id"] == entry["session_id"] and f not in live}
                    for e in live), f"{label}: the clearing lifetime is still open at SessionEnd(clear)")
                continue
            ok = all(e["event_id"] in final_events and numbers(e) == numbers(final_events[e["event_id"]]) for e in live)
            check(ok is matches, f"{label}: hook-time event(s) {[e['event_id'][:8] for e in live]} "
                                 f"{'match' if matches else 'differ from'} the final files")
        shutil.rmtree(tmp / "snap")


def test_hook_flow(tmp: pathlib.Path) -> None:
    """SessionEnd through the real entry point: one event, observed context, idempotence."""
    fixture = materialize("p05-fork-subagent", tmp)
    proj = make_project(tmp / "a")
    path = transcript(fixture, 1)
    expected = final_numbers(path)
    completed = run_hook(end_payload(path, sid(1), proj / "sub"), {"CLAUDE_PID": "4101"})
    check(completed.returncode == 0, f"hook exits 0 ({completed.stderr.decode()[:200]})")
    events = ledger_events(proj)
    check(len(events) == 1, f"SessionEnd appends the closing lifetime only (got {len(events)})")
    check_ledger_numbers("p05 resume", proj, expected)
    event = events[0] if events else {}
    life = event.get("lifetime", {})
    check(event.get("ts") == "2026-11-04T20:55:04.349Z", "ts is the lifetime's latest entry, not the hook's clock")
    check(event.get("sprint") == 9 and event.get("phase") == 2, "sprint and phase from sprint-state.json (C35)")
    check(life.get("recovered") == "none" and life.get("end_reason") == "other"
          and life.get("coverage", {}).get("context") == "observed", "live event: recovered none, end_reason, observed context")
    check(life.get("sprint_at_start") is None and life.get("phase_at_start") is None,
          "no start context for a resume in Stage 1 (only a /clear note observes a start)")
    check(event.get("project") == "proj" and close(event.get("cost_usd"), 0.003617475 - 0.003403745),
          "project from the root, cost the resume's delta")
    raw = (proj / ".council" / "diagnostics.jsonl").read_bytes()
    check(raw.endswith(b"\n") and raw.count(b"\n") == 1 and b"\r" not in raw, "one LF-terminated line")
    ignore = proj / ".council" / "state" / "run" / ".gitignore"
    check(ignore.is_file() and "*" in ignore.read_text(encoding="utf-8"), ".council/state/run/ ignores itself")
    check(run_files(proj) == [], f"nothing left in the spool or as a note ({run_files(proj)})")
    run_hook(end_payload(path, sid(1), proj), {"CLAUDE_PID": "4101"})
    check((proj / ".council" / "diagnostics.jsonl").read_bytes() == raw, "a second firing on the same state appends nothing")

    # the newest rotated archive counts as recorded
    rotated = proj / ".council" / "diagnostics.2026-11-06T00-00-00Z.jsonl.gz"
    with gzip.open(rotated, "wb") as handle:
        handle.write(raw)
    (proj / ".council" / "diagnostics.jsonl").write_bytes(b"")
    run_hook(end_payload(path, sid(1), proj), {"CLAUDE_PID": "4101"})
    check((proj / ".council" / "diagnostics.jsonl").read_bytes() == b"",
          "an event_id in the newest rotated archive is not appended again")

    # backfill of the same transcript adds the first lifetime only
    out = subprocess.run([sys.executable, str(HOOK), "--backfill", str(path), "--root", str(proj)],
                         check=False, capture_output=True, text=True, timeout=120)
    added = ledger_events(proj)
    check(out.returncode == 0 and len(added) == 1 and added[0]["lifetime"]["recovered"] == "backfill"
          and added[0]["lifetime"]["start_source"] == "startup" and added[0]["lifetime"]["coverage"]["context"] == "unknown",
          f"backfill adds the missing lifetime with recovered: backfill ({out.stdout.strip()[:120]})")
    check_ledger_numbers("p05 backfill", proj, expected)

    # a session started in a subdirectory of the governed repo (CLAUDE_PROJECT_DIR is that directory)
    proj2 = make_project(tmp / "sub", "repo")
    (proj2 / "pkg" / "deep").mkdir(parents=True)
    run_hook(end_payload(path, sid(1), proj2 / "pkg" / "deep"),
             {"CLAUDE_PID": "4102", "CLAUDE_PROJECT_DIR": str(proj2 / "pkg" / "deep")})
    check(len(ledger_events(proj2)) == 1 and ledger_events(proj2)[0]["project"] == "repo"
          and not (proj2 / "pkg" / "deep" / ".council").exists(),
          "a session started in a subdirectory records into the governed root above it, creating nothing")
    outside = tmp / "outside"
    (outside / "inner" / ".git").mkdir(parents=True)
    (outside / ".council").mkdir()
    run_hook(end_payload(path, sid(1), outside / "inner"), {"CLAUDE_PROJECT_DIR": str(outside / "inner")})
    check(not (outside / ".council" / "diagnostics.jsonl").exists(),
          "the walk up stops at the session's git root: a .council/ outside the repo is not used")


def test_clear_handoff(tmp: pathlib.Path) -> None:
    """/clear: nothing at SessionEnd(clear); the successor's SessionEnd in the same process
    settles the predecessor (its cost-state is written after SessionEnd(clear) returns)."""
    fixture = materialize("p03-clear-interactive", tmp)
    proj = make_project(tmp / "c")
    manifest = json.loads((fixture / "snapshots" / "manifest.json").read_text(encoding="utf-8"))
    old, new = transcript(fixture, 1), transcript(fixture, 2)
    final_old, final_new = old.read_bytes(), new.read_bytes()
    old.write_bytes(b"".join(final_old.splitlines(keepends=True)[:34]))
    new.write_bytes(final_new)
    expected = final_numbers(old, new)
    old.write_bytes((fixture / manifest[0]["snapshot"]).read_bytes())  # as SessionEnd(clear) saw it
    new.unlink()
    env = {"CLAUDE_PID": "4242"}
    run_hook(end_payload(old, sid(1), proj, "clear", manifest[0]["prompt_id"]), env)
    notes = run_files(proj)
    check(ledger_events(proj) == [] and notes == ["clear-4242.json"],
          f"SessionEnd(clear): no event yet, a note keyed by CLAUDE_PID ({notes})")
    # the closing cost-state lands after the hook returned; the new session runs and exits
    old.write_bytes(b"".join(final_old.splitlines(keepends=True)[:34]))
    new.write_bytes((fixture / manifest[1]["snapshot"]).read_bytes())
    run_hook(end_payload(new, sid(2), proj, "prompt_input_exit", manifest[1]["prompt_id"]), env)
    events = {e["session_id"]: e for e in ledger_events(proj)}
    pre, own = events.get(sid(1), {}), events.get(sid(2), {})
    check(len(events) == 2, f"the successor's SessionEnd writes both lifetimes (got {len(events)})")
    check_ledger_numbers("p03 hand-off", proj, expected)
    check(pre.get("lifetime", {}).get("end_reason") == "clear" and pre.get("lifetime", {}).get("recovered") == "none"
          and close(pre.get("cost_usd"), 0.00198328), "the predecessor: end_reason clear, written by its own process")
    check(own.get("lifetime", {}).get("start_source") == "clear"
          and own.get("lifetime", {}).get("cleared_from_session_id") == sid(1)
          and own.get("lifetime", {}).get("sprint_at_start") == 9 and own.get("lifetime", {}).get("phase_at_start") == 2
          and close(own.get("cost_usd"), 0.00150472),
          "the successor: start_source clear, cleared_from_session_id, sprint and phase at its start from the note")
    check(run_files(proj) == [], "the /clear note is removed")
    before = (proj / ".council" / "diagnostics.jsonl").read_bytes()
    run_hook(end_payload(new, sid(2), proj, "prompt_input_exit"), env)
    check((proj / ".council" / "diagnostics.jsonl").read_bytes() == before, "firing again appends nothing")

    # P10: the cleared lifetime is not the file's first: the note's byte offset picks it
    fixture = materialize("p10-clear-after-resume", tmp / "p10")
    proj = make_project(tmp / "c10")
    first, third = transcript(fixture, 1), transcript(fixture, 3)
    final_first = first.read_bytes()
    expected = final_numbers(first, third)
    first.write_bytes(b"".join(final_first.splitlines(keepends=True)[:56]))  # SessionEnd(clear) saw 56 lines
    run_hook(end_payload(first, sid(1), proj, "clear"), {"CLAUDE_PID": "8392"})
    first.write_bytes(final_first)
    run_hook(end_payload(third, sid(3), proj, "prompt_input_exit"), {"CLAUDE_PID": "8392"})
    events = ledger_events(proj)
    check(len(events) == 1 and events[0]["lifetime"]["anchor"] == "cs:1793825971922:11733"
          and close(events[0]["cost_usd"], 0.00575458 - 0.00231726)
          and events[0]["lifetime"]["end_reason"] == "clear" and events[0]["lifetime"]["recovered"] == "none",
          f"p10: the hand-off settles the resumed lifetime /clear ended, not the file's first "
          f"({[(e['lifetime']['anchor'], e['cost_usd']) for e in events]})")
    check_ledger_numbers("p10 hand-off", proj, expected)
    check(run_files(proj) == [], f"p10: no note remains ({run_files(proj)})")

    # P1 snapshots 06 -> 07: '-p /clear' (an empty lifetime on both sides): the note is consumed
    fixture = materialize("p01-resume-compact-clear-fork", tmp / "p01")
    proj = make_project(tmp / "c01")
    manifest = json.loads((fixture / "snapshots" / "manifest.json").read_text(encoding="utf-8"))
    one, three = transcript(fixture, 1), transcript(fixture, 3)
    final_one, final_three = one.read_bytes(), three.read_bytes()
    one.write_bytes((fixture / manifest[5]["snapshot"]).read_bytes())
    three.unlink()
    run_hook(end_payload(one, sid(1), proj, "clear", manifest[5]["prompt_id"]), {"CLAUDE_PID": "8336"})
    one.write_bytes(final_one)
    three.write_bytes((fixture / manifest[6]["snapshot"]).read_bytes())
    run_hook(end_payload(three, sid(3), proj, "other"), {"CLAUDE_PID": "8336"})
    check(ledger_events(proj) == [] and run_files(proj) == [],
          f"p01: the -p /clear hand-off settles the empty predecessor, writes nothing and leaves no note ({run_files(proj)})")
    three.write_bytes(final_three)


def test_pending_and_budget(tmp: pathlib.Path) -> None:
    """Work past the budget becomes a pending note that a later SessionEnd settles."""
    fixture = materialize("p02-fork", tmp)
    proj = make_project(tmp / "b")
    expected = final_numbers(transcript(fixture, 1), transcript(fixture, 2))
    run_hook(end_payload(transcript(fixture, 2), sid(2), proj), {"CLAUDE_PID": "5001", "DIAGNOSTICS_BUDGET_MS": "0"})
    notes = run_files(proj, "pending-*.json")
    check(ledger_events(proj) == [] and len(notes) == 1, "over budget: no partial event, one pending note")
    run_hook(end_payload(transcript(fixture, 1), sid(1), proj), {"CLAUDE_PID": "5002"})
    events = {e["session_id"]: e for e in ledger_events(proj)}
    fork = events.get(sid(2), {})
    check(len(events) == 2 and fork.get("lifetime", {}).get("recovered") == "sweep"
          and fork.get("lifetime", {}).get("end_reason") == "other"
          and fork.get("lifetime", {}).get("coverage", {}).get("context") == "observed"
          and close(fork.get("cost_usd"), 0.00466108 - 0.00445579),
          "another process's SessionEnd settles the pending lifetime (recovered: sweep, observed context)")
    check_ledger_numbers("p02 pending", proj, expected)
    check(not run_files(proj, "pending-*.json"), "the pending note is removed")

    # a stale pending note whose transcript still exists is settled, not dropped
    proj = make_project(tmp / "stale")
    run_hook(end_payload(transcript(fixture, 2), sid(2), proj), {"CLAUDE_PID": "5003", "DIAGNOSTICS_BUDGET_MS": "0"})
    note_path = proj / ".council" / "state" / "run" / run_files(proj, "pending-*.json")[0]
    note = json.loads(note_path.read_text(encoding="utf-8"))
    note["created_epoch"] = time.time() - 31 * 86400
    note_path.write_text(json.dumps(note), encoding="utf-8")
    run_hook(end_payload(transcript(fixture, 1), sid(1), proj), {"CLAUDE_PID": "5004"})
    check(sid(2) in {e["session_id"] for e in ledger_events(proj)} and not run_files(proj, "pending-*.json"),
          "a 31-day-old pending note is settled before it is dropped")
    # ... and one whose transcript is gone is dropped
    dl.write_note(proj / ".council" / "diagnostics.jsonl", "pending-gone.json",
                  dict(note, transcript_path=str(tmp / "missing.jsonl"), created_epoch=time.time()))
    run_hook(end_payload(transcript(fixture, 1), sid(1), proj), {"CLAUDE_PID": "5005"})
    check(not run_files(proj, "pending-*.json"), "a pending note whose transcript is gone is dropped")
    # ... a fresh note for a lifetime still open is kept; once 30 days old it is dropped
    open_note = dict(note, mode="holding", uuid="never-settled", created_epoch=time.time())
    dl.write_note(proj / ".council" / "diagnostics.jsonl", "pending-open.json", open_note)
    run_hook(end_payload(transcript(fixture, 1), sid(1), proj), {"CLAUDE_PID": "5006"})
    kept = run_files(proj, "pending-*.json") == ["pending-open.json"]
    dl.write_note(proj / ".council" / "diagnostics.jsonl", "pending-open.json",
                  dict(open_note, created_epoch=time.time() - 31 * 86400))
    run_hook(end_payload(transcript(fixture, 1), sid(1), proj), {"CLAUDE_PID": "5007"})
    check(kept and not run_files(proj, "pending-*.json"),
          "a note for a lifetime still open is retried, and dropped once 30 days old (left to --backfill)")

    # an open tail at SessionEnd (here: a killed lifetime with nothing after it) is never recorded
    fixture = materialize("p04-sigkill-resume", tmp / "k")
    path = transcript(fixture, 1)
    path.write_bytes(b"".join(path.read_bytes().splitlines(keepends=True)[:57]))
    proj = make_project(tmp / "k2")
    run_hook(end_payload(path, sid(1), proj), {"CLAUDE_PID": "5003"})
    settled = ledger_events(proj)
    check(len(settled) == 1 and settled[0]["lifetime"]["start_source"] == "startup",
          "settled only: the open killed lifetime gets no event")
    check(len(run_files(proj, "pending-*.json")) == 1,
          "activity after the last cost-state leaves a pending note for a later SessionEnd")
    printed = subprocess.run([sys.executable, str(HOOK), "--backfill", str(path), "--print", "--root", str(proj)],
                             check=False, capture_output=True, text=True, timeout=120)
    check(printed.returncode == 0 and len(printed.stdout.splitlines()) == 1,
          "backfill over a transcript whose last lifetime is open emits nothing for it")

    # p11 at process A's SessionEnd: B is still open after the last cost-state
    fixture = materialize("p11-concurrent-resumes", tmp / "p11")
    path = transcript(fixture, 1)
    final = path.read_bytes()
    manifest = json.loads((fixture / "snapshots" / "manifest.json").read_text(encoding="utf-8"))
    proj = make_project(tmp / "p11p")
    expected = final_numbers(path)
    path.write_bytes((fixture / manifest[1]["snapshot"]).read_bytes())
    run_hook(end_payload(path, sid(1), proj, prompt_id=manifest[1]["prompt_id"]), {"CLAUDE_PID": "5101"})
    check(len(ledger_events(proj)) == 1 and len(run_files(proj, "pending-*.json")) == 1,
          "p11: A's SessionEnd settles A's lifetime and leaves a pending note for B's, still open")
    path.write_bytes(final)
    run_hook(end_payload(path, sid(1), proj, prompt_id=manifest[2]["prompt_id"]), {"CLAUDE_PID": "5102"})
    check(len(ledger_events(proj)) == 2 and not run_files(proj, "pending-*.json"),
          "p11: B's SessionEnd settles B's lifetime and the note")
    check_ledger_numbers("p11 concurrent", proj, expected)


def test_lock_and_spool(tmp: pathlib.Path) -> None:
    """A held ledger lock never loses an event: it waits in the spool for the next SessionEnd."""
    fixture = materialize("p05-fork-subagent", tmp)
    path = transcript(fixture, 1)
    expected = final_numbers(path, transcript(fixture, 2))
    proj = make_project(tmp / "l")
    lock = proj / ".council" / "state" / "run" / dl.LOCK_NAME
    lock.parent.mkdir(parents=True)
    lock.write_text("999999 0\n", encoding="ascii")
    started = time.monotonic()
    completed = run_hook(end_payload(path, sid(1), proj), {"CLAUDE_PID": "6101"})
    elapsed = time.monotonic() - started
    spooled = run_files(proj, "spool-*.json")
    check(ledger_events(proj) == [] and len(spooled) == 1,
          f"lock held by another writer: nothing appended, the event spooled ({spooled})")
    check(b"kept in .council/state/run/" in completed.stderr,
          f"the log line says where the event waits ({completed.stderr.decode().strip()[:160]})")
    check(elapsed < CLAUDE_CODE_SESSIONEND_BUDGET_S + 0.5, f"the hook gives up on the lock in time ({elapsed:.2f} s)")
    lock.unlink()
    run_hook(end_payload(transcript(fixture, 2), sid(2), proj), {"CLAUDE_PID": "6102"})
    check(len(ledger_events(proj)) == 2 and not run_files(proj, "spool-*.json"),
          "the next SessionEnd of the project appends the spooled event, then its own")
    check_ledger_numbers("p05 spool", proj, expected)

    # a lock older than LOCK_STALE_S was left by a killed writer and is broken
    proj = make_project(tmp / "stale")
    lock = proj / ".council" / "state" / "run" / dl.LOCK_NAME
    lock.parent.mkdir(parents=True)
    lock.write_text("999999 0\n", encoding="ascii")
    old = time.time() - dl.LOCK_STALE_S - 5
    os.utime(lock, (old, old))
    run_hook(end_payload(path, sid(1), proj), {"CLAUDE_PID": "6103"})
    check(len(ledger_events(proj)) == 1 and not lock.exists(), "a stale lock is broken and the event appended")

    # a ledger without its final newline gets one before the new line
    proj = make_project(tmp / "nl")
    ledger = proj / ".council" / "diagnostics.jsonl"
    ledger.write_bytes(b'{"partial": true}')
    run_hook(end_payload(path, sid(1), proj), {"CLAUDE_PID": "6104"})
    data = ledger.read_bytes()
    check(data.startswith(b'{"partial": true}\n{') and data.endswith(b"\n") and data.count(b"\n") == 2,
          "a missing final newline is repaired before appending")

    # concurrent writers: no malformed line, no event_id twice
    proj = make_project(tmp / "many")
    ledger = proj / ".council" / "diagnostics.jsonl"
    events = events_of(transcript(fixture, 1)) + events_of(transcript(fixture, 2))
    batch = tmp / "events.json"
    batch.write_text(json.dumps(events), encoding="utf-8")
    code = ("import json, sys; sys.path.insert(0, sys.argv[1]); import _diaglib as dl; "
            "dl.append_events(__import__('pathlib').Path(sys.argv[2]), json.loads(open(sys.argv[3]).read()))")
    procs = [subprocess.Popen([sys.executable, "-c", code, str(SCRIPTS), str(ledger), str(batch)]) for _ in range(6)]
    for proc in procs:
        proc.wait(timeout=60)
    lines = ledger.read_text(encoding="utf-8").splitlines()
    parsed = [json.loads(line) for line in lines]
    check(len(lines) == len(events) and len({e["event_id"] for e in parsed}) == len(events),
          f"six concurrent writers of the same {len(events)} events leave {len(events)} well-formed lines (got {len(lines)})")


def test_notes(tmp: pathlib.Path) -> None:
    """/clear notes of other processes: orphaned ones are swept, a reused pid is not this process."""
    fixture = materialize("p03-clear-interactive", tmp)
    old = transcript(fixture, 1)
    final_old = old.read_bytes()
    old.write_bytes(b"".join(final_old.splitlines(keepends=True)[:34]))
    proj = make_project(tmp / "o")
    ledger = proj / ".council" / "diagnostics.jsonl"
    snapshot_size = len((fixture / "snapshots" / "01-session-end.jsonl").read_bytes())
    base_note = {"kind": "clear", "session_id": sid(1), "transcript_path": str(old), "mode": "first_after",
                 "offset": snapshot_size, "end_reason": "clear", "context": {"sprint": 3, "phase": 1, "head": None},
                 "cleared_from_session_id": None, "at_start": None}
    # a note from another pid, two days old: its successor never ended; another process sweeps it
    dl.write_note(ledger, "clear-7777.json", dict(base_note, pid="7777", pid_start="x:1", created_epoch=time.time() - 2 * 86400))
    p08 = materialize("p08-stream-json-sigterm", tmp / "x")
    run_hook(end_payload(transcript(p08, 1), sid(1), proj), {"CLAUDE_PID": "7001"})
    swept = [e for e in ledger_events(proj) if e["lifetime"]["anchor"] == "cs:1793825307473:29482"]
    check(len(swept) == 1 and swept[0]["lifetime"]["recovered"] == "sweep" and swept[0]["lifetime"]["end_reason"] == "clear"
          and not run_files(proj, "clear-*.json"),
          "an orphaned /clear note is settled by another process's SessionEnd (recovered: sweep)")

    # the same pid but another process start (a reused pid): not this process's /clear
    proj = make_project(tmp / "reuse")
    ledger = proj / ".council" / "diagnostics.jsonl"
    me = str(os.getpid())  # a live process, so its start time is known
    dl.write_note(ledger, f"clear-{me}.json", dict(base_note, pid=me, pid_start="another-boot:1",
                                                   created_epoch=time.time() - 60))
    new = transcript(fixture, 2)
    run_hook(end_payload(new, sid(2), proj, "prompt_input_exit"), {"CLAUDE_PID": me})
    events = {e["session_id"]: e for e in ledger_events(proj)}
    pre, own = events.get(sid(1), {}), events.get(sid(2), {})
    if sys.platform.startswith("linux") or sys.platform == "darwin":
        check(pre.get("lifetime", {}).get("recovered") == "sweep" and own.get("lifetime", {}).get("sprint_at_start") is None
              and own.get("lifetime", {}).get("cleared_from_session_id") is None,
              "a /clear note under a reused pid is settled as another process's (sweep), and gives no start context")
    else:
        print("SKIP: process start time (Linux and macOS only)")
    check(dl.process_start(str(os.getpid())) is not None or not sys.platform.startswith("linux"),
          "the process start identity is read on Linux")


def test_crew_guard(tmp: pathlib.Path) -> None:
    fixture = materialize("p01-resume-compact-clear-fork", tmp)
    proj = make_project(tmp / "g")
    (proj / ".council" / "diagnostics.jsonl").write_text("", encoding="utf-8")
    before = tree_state(proj)
    env = {"AUTOMATE_RUN": "1", "CLAUDE_PID": "6001"}
    run_hook(end_payload(transcript(fixture, 1), sid(1), proj), env)
    run_hook(end_payload(transcript(fixture, 1), sid(1), proj, "clear"), env)
    check(tree_state(proj) == before, "crew guard: with AUTOMATE_RUN set nothing under the project or .council/ changes")


def test_forks_without_parent(tmp: pathlib.Path) -> None:
    """A fork whose parent is not found: cost_usd null, coverage.fork_parent not-found."""
    cases = (("p02-fork", 2, 26, (2, 5, 18139, 106)), ("p01-resume-compact-clear-fork", 2, 12, (2, 5, 13954, 5529)),
             ("if-interactive-fork", 2, 18, (2, 32, 18207, 16092)))
    for name, n, copies, own in cases:
        fixture = materialize(name, tmp / "nf")
        lone = tmp / "lone" / "projects" / "-work-lone"
        lone.mkdir(parents=True)
        path = lone / transcript(fixture, n).name
        shutil.copy(transcript(fixture, n), path)
        events = events_of(path)
        event = events[0] if events else {}
        cov = event.get("lifetime", {}).get("coverage", {})
        check(len(events) == 1 and event["cost_usd"] is None and cov.get("fork_parent") == "not-found"
              and event["lifetime"]["cum_cost_start_usd"] is None and event["lifetime"]["start_source"] == "fork"
              and "cost_state_usage_by_model" not in event and schema_problem(event) is None,
              f"{name}: fork without its parent has no cost and fork_parent not-found")
        usage = tuple(event.get("usage", {}).get(k) for k in sl.USAGE_KEYS)
        check(cov.get("copied_entries_excluded") == copies and usage == own,
              f"{name}: the {copies} copies are left out without the parent (queue-operation marker, or the time gap "
              f"at the fork point for an interactive fork): own usage {own} (got {cov.get('copied_entries_excluded')}, {usage})")
        shutil.rmtree(tmp / "nf")
        shutil.rmtree(tmp / "lone")
    # the parent in another project directory is still found (cost lineage across dirs)
    fixture = materialize("p09-fork-cmdline", tmp)
    parent = transcript(fixture, 1)
    moved = fixture / "projects" / "-work-elsewhere" / parent.name
    moved.parent.mkdir()
    parent.rename(moved)
    events = events_of(transcript(fixture, 2))
    check(len(events) == 1 and events[0]["lifetime"]["coverage"]["fork_parent"] == "found"
          and close(events[0]["cost_usd"], 0.00231726 - 0.00144132), "a fork's parent in another project dir is found")
    if sys.platform.startswith("linux"):
        child = subprocess.Popen(
            [sys.executable, "-c", "import sys, time; print('ready', flush=True); time.sleep(60)",
             "--resume", sid(1), "--fork-session"], stdout=subprocess.PIPE)
        try:
            ready = child.stdout.readline() if child.stdout else b""
            hint = dl.fork_hint(str(child.pid))
        finally:
            child.kill()
            child.wait()
            if child.stdout:
                child.stdout.close()
        check(ready.strip() == b"ready" and hint.fork and hint.fork_parent_ids == (sid(1),),
              "the process command line gives the fork hint and parent id")
    else:
        print("SKIP: /proc command-line fork hint (Linux only)")


def test_concurrency_and_other_dir(tmp: pathlib.Path) -> None:
    fixture = materialize("p11-concurrent-resumes", tmp)
    path = transcript(fixture, 1)
    manifest = json.loads((fixture / "snapshots" / "manifest.json").read_text(encoding="utf-8"))
    final = events_of(path)
    racing = events_of(path, selection=sl.Selection("last_before", path.stat().st_size, manifest[1]["prompt_id"]))
    check(len(racing) == 1 and racing[0]["event_id"] == final[1]["event_id"],
          "the payload's prompt_id picks the process's own lifetime when another process wrote the last cost-state")

    # the reordered P11: A's cost-state written after B's reply; A's SessionEnd sees up to its own
    fixture = materialize("p11b-concurrent-rewrites", tmp)
    path = transcript(fixture, 1)
    lines = path.read_bytes().splitlines(keepends=True)
    final_ids = [e["event_id"] for e in events_of(path)]
    proj = make_project(tmp / "r")
    expected = final_numbers(path)
    full = path.read_bytes()
    a_close = next(i for i, line in enumerate(lines) if b'"totalDuration":8005' in line)
    path.write_bytes(b"".join(lines[: a_close + 1]))
    run_hook(end_payload(path, sid(1), proj), {"CLAUDE_PID": "7301"})
    path.write_bytes(full)
    run_hook(end_payload(path, sid(1), proj), {"CLAUDE_PID": "7302"})
    got = [e["event_id"] for e in ledger_events(proj)]
    check(sorted(got) == sorted(final_ids[1:]) and len(got) == 2,
          "p11b: each process's SessionEnd settles its own lifetime, whatever the order of the cost-states")
    check_ledger_numbers("p11b", proj, expected)

    fixture = materialize("p06-resume-other-dir", tmp)
    proj_b = make_project(tmp / "other", "proj-b")
    expected = final_numbers(transcript(fixture, 1))
    run_hook(end_payload(transcript(fixture, 1), sid(1), proj_b), {"CLAUDE_PID": "7001", "CLAUDE_PROJECT_DIR": str(proj_b)})
    events = ledger_events(proj_b)
    check(len(events) == 1 and events[0]["project"] == "proj-b" and events[0]["lifetime"]["start_source"] == "resume"
          and close(events[0]["cost_usd"], 0.00234765 - 0.00144092),
          "a resume from another directory is recorded where it ran, from the original transcript")
    check_ledger_numbers("p06", proj_b, expected)


def test_payload_and_validation(tmp: pathlib.Path) -> None:
    fixture = materialize("p07-sigterm", tmp)
    proj = make_project(tmp / "t")
    run_hook(end_payload(transcript(fixture, 1), sid(1), proj))
    check(ledger_events(proj) == [], "SIGTERM mid-request: the last lifetime has no request and no spend, so no event")
    fixture = materialize("p08-stream-json-sigterm", tmp)
    path = transcript(fixture, 1)
    expected = final_numbers(path)
    # C34: raw UTF-8 bytes on stdin under a non-UTF-8 locale, non-ASCII root
    proj = make_project(tmp / "u", "木下-proj")
    raw = json.dumps(end_payload(path, sid(1), proj), ensure_ascii=False).encode("utf-8")
    run_hook({}, {"PYTHONIOENCODING": "cp1252", "PYTHONUTF8": "0"}, raw=raw)
    events = ledger_events(proj)
    check(len(events) == 1 and events[0]["project"] == "木下-proj", "stdin is decoded as UTF-8 whatever the locale (C34)")
    check_ledger_numbers("p08", proj, expected)
    # without jsonschema the structural checks still validate
    proj = make_project(tmp / "s")
    run_hook(end_payload(path, sid(1), proj), {"DIAGNOSTICS_NO_JSONSCHEMA": "1"})
    check(len(ledger_events(proj)) == 1, "without jsonschema the event is checked structurally and written")
    valid = sorted((SCHEMA_DIR / "valid").glob("*.json"))
    invalid = sorted((SCHEMA_DIR / "invalid").glob("*.json"))
    bad_valid = [p.name for p in valid if dl.structural_problem(json.loads(p.read_text(encoding="utf-8")))]
    passed_invalid = [p.name for p in invalid if not dl.structural_problem(json.loads(p.read_text(encoding="utf-8")))]
    check(not bad_valid, f"structural checks accept every valid schema fixture {bad_valid}")
    check(not passed_invalid, f"structural checks reject every invalid schema fixture {passed_invalid}")
    # the append protocol validates every event, with jsonschema and without it
    good = events_of(path)[0]
    for label, flag in (("jsonschema", None), ("structural checks", "1")):
        bad = json.loads(json.dumps(good))
        bad["event_id"] = str(uuid.uuid5(NAMESPACE, "a rejected event"))
        bad["schema_version"] = "1.0"
        stale_cost = json.loads(json.dumps(good))
        stale_cost["event_id"] = str(uuid.uuid5(NAMESPACE, "another rejected event"))
        stale_cost["cost_usd"] = None
        ledger = tmp / f"validate-{label[:4]}" / ".council" / "diagnostics.jsonl"
        ledger.parent.mkdir(parents=True)
        stderr = io.StringIO()
        saved = os.environ.pop("DIAGNOSTICS_NO_JSONSCHEMA", None)
        if flag:
            os.environ["DIAGNOSTICS_NO_JSONSCHEMA"] = flag
        try:
            with contextlib.redirect_stderr(stderr):
                appended = dl.append_events(ledger, [good, bad, stale_cost])
        finally:
            os.environ.pop("DIAGNOSTICS_NO_JSONSCHEMA", None)
            if saved is not None:
                os.environ["DIAGNOSTICS_NO_JSONSCHEMA"] = saved
        lines = ledger.read_text(encoding="utf-8").splitlines()
        check(appended == [good["event_id"]] and len(lines) == 1 and bad["event_id"] in stderr.getvalue()
              and stale_cost["event_id"] in stderr.getvalue(),
              f"with {label}, an event that breaks the schema is rejected by id and the valid one appended")
    # no .council: nothing written, nothing created
    proj = make_project(tmp / "n", council=False)
    run_hook(end_payload(path, sid(1), proj))
    check(not (proj / ".council").exists(), "without .council nothing is written and nothing is created")
    empty = run_hook({}, raw=b"")
    check(empty.returncode == 0, "an empty payload exits 0")
    other = run_hook({"hook_event_name": "Stop", "session_id": sid(1), "transcript_path": str(path), "cwd": str(proj)})
    check(other.returncode == 0 and not (proj / ".council").exists(), "other hook events are ignored in Stage 1")
    override = tmp / "elsewhere" / "diag.jsonl"
    override.parent.mkdir()
    run_hook(end_payload(path, sid(1), proj), {"DIAGNOSTICS_LOG_PATH": str(override)})
    check(override.exists() and len(override.read_text(encoding="utf-8").splitlines()) == 1,
          "DIAGNOSTICS_LOG_PATH override honoured")


def test_measurement_rules(tmp: pathlib.Path) -> None:
    """Counting rules on recorded entries that produce no event of their own."""
    fixture = materialize("r-c18-api-retries", tmp)
    rows = sl.load_rows(transcript(fixture, 1))
    measure = sl._Measure()
    for row in rows:
        measure.feed(row.entry, row.ts, sidechain=False, main=True)
    check(measure.retries == 2 and not measure.requests,
          "api_error entries with retryAttempt are retries (C18); a '<synthetic>' reply is no request (C36)")
    unretried = sl._Measure()
    for row in rows:
        entry = {k: v for k, v in row.entry.items() if k != "retryAttempt"}
        unretried.feed(entry, row.ts, sidechain=False, main=True)
    check(unretried.retries == 0, "an api_error without retryAttempt is not a retry")
    fixture = materialize("r-c08-config-denial", tmp / "d")
    denied = next(row.entry for row in sl.load_rows(transcript(fixture, 1))
                  if isinstance(row.entry.get("permissionDecision"), dict)
                  and row.entry["permissionDecision"].get("decision") == "reject")
    by_decision = {k: v for k, v in denied.items() if k != "toolDenialKind"}
    by_kind = {k: v for k, v in denied.items() if k != "permissionDecision"}
    accepted = dict(by_decision, permissionDecision={"decision": "accept", "source": "config"})
    check(sl._is_denial(by_decision) and sl._is_denial(by_kind) and not sl._is_denial(accepted),
          "a denial is a permissionDecision 'reject' object or a toolDenialKind, each on its own (C08)")
    kinds = {kind: sl._is_denial(dict(by_kind, toolDenialKind=kind))
             for kind in ("user-rejected", "permission-rule", "automode-blocked", "interrupted")}
    check(kinds == {"user-rejected": True, "permission-rule": True, "automode-blocked": True, "interrupted": False},
          f"denial kinds are user-rejected, permission-rule and automode-*; 'interrupted' is not a denial ({kinds})")
    fixture = materialize("l03-sigterm-mid-tool-then-sigkill", tmp / "i")
    repair = next(row.entry for row in sl.load_rows(transcript(fixture, 1))
                  if row.entry.get("toolDenialKind") == "interrupted")
    cut = sl._Measure()
    cut.feed(repair, None, sidechain=False, main=True)
    check(not cut.denial_ids and not cut.failures,
          "a call cut off by an exit, a kill or a concurrent resume ('interrupted') is neither a denial nor a failure")
    fixture = materialize("p01-resume-compact-clear-fork", tmp / "m")
    compact = events_of(transcript(fixture, 1))[3]
    check(compact["counts"]["compactions"] == 1 and compact["num_turns"] == 0,
          "one /compact: one compaction (boundary only) and no turn from its summary or command echo (C17, C19)")


def test_entryless_lifetime(tmp: pathlib.Path) -> None:
    """Spend with no dated entry of its own still gets an event, placed at the dated entry
    nearest before its closing cost-state (A1 D1.2 exempts only lifetimes without cost)."""
    fixture = materialize("p07-sigterm", tmp)
    path = transcript(fixture, 1)
    lines = path.read_bytes().splitlines(keepends=True)
    last = json.loads(next(line for line in reversed(lines) if b'"cost-state"' in line))
    more = dict(last, totalCostUSD=round(last["totalCostUSD"] + 0.0005, 10),
                totalDuration=last["totalDuration"] + 3000)
    more["modelUsage"] = {m: dict(u, inputTokens=u["inputTokens"] + 400, costUSD=round(u["costUSD"] + 0.0005, 10))
                          for m, u in last["modelUsage"].items()}
    path.write_bytes(b"".join(lines) + b'{"type":"ai-title"}\n' + json.dumps(more).encode() + b"\n")
    dated = [json.loads(line)["timestamp"] for line in lines if b'"timestamp"' in line]
    events = events_of(path)
    extra = events[-1] if len(events) == 2 else {}
    check(len(events) == 2 and close(extra.get("cost_usd"), 0.0005) and extra.get("usage", {}).get("input_tokens") == 0
          and extra.get("ts") == dated[-1] == extra.get("lifetime", {}).get("started_at")
          and schema_problem(extra) is None,
          f"an entry-less lifetime with spend: one event, cost 0.0005, ts of the nearest dated entry ({extra.get('ts')})")


def _pad(path: pathlib.Path) -> None:
    """Restore a redacted file to its original size: each line gets back the bytes
    redaction removed (its _size), as a list of short strings."""
    out: List[bytes] = []
    for raw in path.read_bytes().splitlines():
        entry = json.loads(raw)
        size = entry.pop("_size", None)
        line = json.dumps(entry, separators=(",", ":")).encode()
        missing = (size or 0) - len(line) - 1 - len(b',"_pad":[]')
        if missing > 0:
            chunks = ["x" * 61] * (missing // 64)
            entry["_pad"] = chunks
            line = json.dumps(entry, separators=(",", ":")).encode()
        out.append(line)
    path.write_bytes(b"\n".join(out) + b"\n")


def test_budget_canary(tmp: pathlib.Path) -> None:
    """The deterministic half of A1's budget canary: SessionEnd on the heaviest recorded
    fixture, restored to the real files' sizes, through the hook's entry point."""
    fixture = materialize("real-session", tmp)
    main = transcript(fixture, 1)
    lifetime_start = sl.parse_ts(REAL_CUT_TS) or 0.0
    _pad(main)
    for agent in main.parent.joinpath(sid(1), "subagents").rglob("agent-*.jsonl"):
        last = json.loads(agent.read_bytes().splitlines()[-1]).get("timestamp")
        if (sl.parse_ts(last) or 0.0) + sl.SUBAGENT_RANGE_SLACK_S >= lifetime_start:
            _pad(agent)  # the files the last lifetime's window parses
    size_mb = main.stat().st_size / 1e6
    proj = make_project(tmp / "heavy")
    started = time.monotonic()
    run_hook(end_payload(main, sid(1), proj), {"CLAUDE_PID": "9101"})
    elapsed = time.monotonic() - started
    events = ledger_events(proj)
    check(len(events) == 1 and close(events[0]["cost_usd"], 49.5028742) and size_mb > 7.0,
          f"the hook settles the sixth lifetime from the size-restored skeleton ({size_mb:.1f} MB main transcript)")
    check(elapsed < CLAUDE_CODE_SESSIONEND_BUDGET_S,
          f"SessionEnd through the entry point fits Claude Code's {CLAUDE_CODE_SESSIONEND_BUDGET_S} s budget "
          f"({elapsed * 1000:.0f} ms, Python startup and imports included)")


def test_projection_event(tmp: pathlib.Path) -> None:
    plugin_root = tmp / "plugin"
    (plugin_root / ".council").mkdir(parents=True)
    (plugin_root / ".claude-plugin").mkdir()
    (plugin_root / "CLAUDE.md").write_text("# plugin\n\nsome words here\n", encoding="utf-8")
    (plugin_root / ".claude-plugin" / "plugin.json").write_text(json.dumps({"name": "x", "skills": [], "agents": []}), encoding="utf-8")
    log = plugin_root / ".council" / "diagnostics.jsonl"
    log.write_bytes(b'{"partial": true}')
    proc = subprocess.run([sys.executable, str(PROJECTION), "--repo-root", str(plugin_root), "--emit-event", "--json"],
                          check=False, capture_output=True, text=True, timeout=60)
    lines = log.read_text(encoding="utf-8").splitlines() if log.exists() else []
    event = json.loads(lines[1]) if len(lines) > 1 else {}
    check(proc.returncode == 0 and len(lines) == 2 and event.get("kind") == "projection-cost"
          and event.get("labels", {}).get("budget") == "8000" and schema_problem(event) is None,
          f"projection-cost --emit-event appends one schema-valid event with the ledger protocol (rc={proc.returncode})")
    plugin2 = tmp / "plugin2"
    (plugin2 / ".claude-plugin").mkdir(parents=True)
    (plugin2 / "CLAUDE.md").write_text("# p\n", encoding="utf-8")
    (plugin2 / ".claude-plugin" / "plugin.json").write_text(json.dumps({"name": "y", "skills": [], "agents": []}), encoding="utf-8")
    proc2 = subprocess.run([sys.executable, str(PROJECTION), "--repo-root", str(plugin2), "--emit-event"],
                           check=False, capture_output=True, text=True, timeout=60)
    check(proc2.returncode == 0 and not (plugin2 / ".council").exists(), "projection-cost --emit-event creates nothing without .council")


def test_rotation_lock(tmp: pathlib.Path) -> None:
    """Rotating the diagnostics ledger takes the writers' lock, so no append falls between."""
    proj = make_project(tmp / "rot")
    ledger = proj / ".council" / "diagnostics.jsonl"
    ledger.write_text('{"event_id": "x"}\n' * 4, encoding="utf-8")
    lock = proj / ".council" / "state" / "run" / dl.LOCK_NAME
    lock.parent.mkdir(parents=True)
    lock.write_text("999999 0\n", encoding="ascii")
    args = [sys.executable, str(ROTATE), "--file", str(ledger), "--threshold-bytes", "1",
            "--decision-output", str(proj / ".council" / "decision-log.jsonl"), "--lock-timeout", "0.3"]
    held = subprocess.run(args, check=False, capture_output=True, text=True, timeout=60)
    check(held.returncode == 1 and ledger.stat().st_size > 0 and not list(proj.glob(".council/*.gz")),
          "with the ledger lock held, rotation waits, gives up and leaves the ledger intact")
    lock.unlink()
    free = subprocess.run(args, check=False, capture_output=True, text=True, timeout=60)
    try:
        import jsonschema  # noqa: F401  (append-decision.py validates the DEC entry with it)
        decision_ok = free.returncode == 0
    except ImportError:
        decision_ok = True
    check(decision_ok and ledger.stat().st_size == 0 and len(list(proj.glob(".council/*.gz"))) == 1
          and not lock.exists(), f"with the lock free, rotation archives and releases it ({free.stderr.strip()[:120]})")


def main() -> int:
    tests = (test_fixtures, test_real_session, test_snapshots, test_hook_flow, test_clear_handoff,
             test_pending_and_budget, test_lock_and_spool, test_notes, test_crew_guard, test_forks_without_parent,
             test_concurrency_and_other_dir, test_payload_and_validation, test_measurement_rules,
             test_entryless_lifetime, test_budget_canary, test_projection_event, test_rotation_lock)
    for test in tests:
        print(f"\n== {test.__name__}")
        with tempfile.TemporaryDirectory() as tmpdir:
            try:
                test(pathlib.Path(tmpdir))
            except Exception as exc:  # a crash is a failure, and the other tests still run
                check(False, f"{test.__name__} raised {type(exc).__name__}: {exc}")
    print()
    if failures:
        print(f"{len(failures)} of {checks} CHECK(S) FAILED")
        return 1
    print(f"ALL {checks} CHECKS PASSED")
    return 0


if __name__ == "__main__":
    sys.exit(main())
