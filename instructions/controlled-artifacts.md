# Controlled Artifacts — Behavioral Instructions

This instruction defines which files are controlled artifacts, what
"controlled" means in terms of permitted write operations, and how agents
must behave when their task would require modifying a controlled artifact.

---

## What Is a Controlled Artifact?

A **controlled artifact** is any file whose modification has governance
implications — either because it affects the sprint plan, defines system
behavior, records decisions, or enforces process integrity. Controlled
artifacts are protected by hook enforcement (Sprint 3 deliverable) and by
the agents' own behavioral constraints.

---

## Category 1 — Sacred (Level 5 Only, No Exceptions)

These files define what is being built. Modifying them changes the project's
goals, not its implementation. Agents MUST NOT propose modifications to these
files except in response to an explicit user request. Even then, the proposal
must go through the major nemawashi walkthrough path (see `@instructions/human-approval.md`).

| File | Why Sacred |
|---|---|
| `.harness/features.json` | Canonical feature list — defines what counts as "done" |
| `.harness/spec.md` | Product specification — the authoritative requirements |
| `.harness/sprints.json` | Sprint plan — defines the ordered delivery sequence |
| `.harness/config.json` | Project configuration — owned by trine-eval |

**Agent prohibition:** No agent may remove, rename, reinterpret, or reorder
entries in `features.json` without Level 5 approval. Feature status updates
(`pending` → `done`) are the only auto-applicable change, and only at Level 3+.

---

## Category 2 — Append-Only (Structured Logs)

These files record the governance audit trail. They must never be edited in-place.
The PreToolUse hook (Sprint 3) blocks `Write` and `Edit` operations on these paths.
The only sanctioned write path is the validated append scripts (Sprint 4).

| File | Append Script |
|---|---|
| `.council/henka-register.jsonl` | `scripts/append-henka.py` (validates schema before appending) |
| `.council/decision-log.jsonl` | `scripts/append-decision.py` (validates schema before appending) |
| `.council/audit-log.jsonl` | PostToolUse hook only (`hooks/log-tool-call.*` over `scripts/log-tool-call.py`) |
| `.council/diagnostics.jsonl` | SessionEnd hook (`hooks/session-diagnostics.*` over `scripts/session-diagnostics.py`), its backfill command (`scripts/session-diagnostics.py --backfill`) and `scripts/measure-projection-cost.py --emit-event` |

**Diagnostics log (`diagnostics.jsonl`):** one `kind: session` event (schema 1.1)
per settled process lifetime (cloud-catcher ADR-0006 amendment A1, Stage 1), plus
`projection-cost` events from `scripts/measure-projection-cost.py --emit-event`.
It never contains prompt or response text, tool inputs or tool outputs.

- *A lifetime* is one Claude Code process's tenure on one session id, from its start
  (startup, resume, fork or `/clear`) to the `cost-state` entry that process writes
  when it exits. It is recorded once that closing `cost-state` exists, and only when
  it made a request, a tool call or a compaction or spent anything.
- *Every measure is a delta over the lifetime.* Tokens by model are counted once per
  requestId over its span of the transcript and of the session's subagent files
  (`<session_id>/subagents/**/agent-*.jsonl`) in its time window, with entries a fork
  copied from its parent left out. `cost_usd` is the closing `cost-state` minus the
  one restored at start (`cost_source: claude-code-estimate`);
  `cost_state_usage_by_model` is the same delta of `modelUsage`, including calls no
  transcript shows. `lifetime.cost_lineage`, `cum_cost_start_usd` and
  `cum_cost_end_usd` are anchors and are never summed. A session's total is the sum
  of its events, never its latest event. A lifetime whose own entries span two or
  more UTC days carries `lifetime.days` (requests, tokens and cost per UTC day, each
  request on the day of its first entry), which day, month and window sums use in
  place of `ts` (A1 D1.11).
- *Identity.* `event_id` is UUIDv5 in namespace `5f0c2b8e-2a7d-4d38-9a51-1c2f1d6e2006`
  over `session-lifetime|<session_id>|cs:<startTime>:<totalDuration>` of the closing
  `cost-state`, and `ts` is the lifetime's latest entry, never the hook's clock, so
  every writer mints the same `event_id` for a lifetime; copies differ only in
  `recovered` and the observed context, and readers keep one per id.
- *Which process wrote what.* Two processes can append to one transcript at once. A
  `cost-state` belongs to the process named by the `leafUuid` of the `last-prompt`
  entry written before it, else to the open lifetime whose tokens fit under its
  per-model delta. A tool result that carries its turn's `promptId` continues that
  turn, so a branch beside it with another prompt (the `interrupted` repair of a
  concurrent resume) is another process; `entrypoint` and the `cost-state`
  lineage's start time separate two processes at a turn boundary. The base is the
  `cost-state` of the same lineage the process could have restored, never one of
  another lineage. Entries a process writes after its own `cost-state` (SIGTERM
  during a tool call) stay in its lifetime.
- *Writers.* One deriver (`scripts/session_lifetimes.py`) computes every event. The
  `SessionEnd` hook calls it for the lifetime that just closed; for a `/clear`
  predecessor, whose closing `cost-state` is written only after its own hook
  returned, the hook leaves a note keyed by `CLAUDE_PID` (with the process start
  time, so a reused pid is not taken for the same process) in `.council/state/run/`
  (a directory that ignores itself in git), and the successor's `SessionEnd` in the
  same process settles it. A lifetime still open at a `SessionEnd` (a concurrent
  process) gets a pending note there too. A note settled by another process's
  `SessionEnd` is labelled `recovered: sweep`. The hook looks for the governed root
  (the nearest directory holding `.council/`) from the session's directory upward,
  within its git repo. `scripts/session-diagnostics.py --backfill <transcript.jsonl>`
  derives every settled lifetime of a transcript afterwards (`--print` only prints).
- *Append protocol.* Events are validated against `schemas/diagnostic-event.schema.json`
  (with `jsonschema` when installed, otherwise with structural checks). The hook
  first writes them to `.council/state/run/spool-<event_id>.json`, then removes the
  notes they came from, then appends under an exclusive lock file
  (`.council/state/run/diagnostics.lock`; a lock older than 5 s is broken): an
  `event_id` already in the ledger or in its newest rotated archive is skipped, and
  each event is one LF-terminated UTF-8 line. An event whose append failed (lock
  held, time up) stays in the spool and the next `SessionEnd` of the project
  appends it. The backfill command, `measure-projection-cost.py --emit-event` and
  `rotate-audit-log.py` (for this file) take the same lock.
- *Time budget.* The hook does about 1.0 s of work (`DIAGNOSTICS_BUDGET_MS`), then waits
  up to 0.3 s for the lock; work that would take longer is left as a pending note that
  a later `SessionEnd` of the same project settles, oldest note first. A note whose
  transcript is larger than 64 MB is not retried by the hook (such a file does not
  parse within the budget; Stage 1 parses the whole transcript): record it with the
  backfill command. A note still unsettled after 30 days, or whose transcript is
  gone, is dropped. Claude Code ignores a `timeout` declared for a plugin's
  `SessionEnd` hook; `CLAUDE_CODE_SESSIONEND_HOOKS_TIMEOUT_MS` in the settings `env`
  raises its budget (seen in `claude -p` probes). The opt-in live canary
  `tests/live/test-sessionend-budget-canary.sh` checks that the installed Claude Code
  still lets a SessionEnd hook of 1.0 s + 0.3 s + 0.1 s finish and cancels a 1.7 s one.
- *Crew guard.* With `AUTOMATE_RUN` set, the SessionEnd, PostToolUse and Stop hooks
  write nothing. auto-mate does not set it for its crews and gates yet (P2-AM-2), so
  the guard takes effect once it does.
- *Stage 1 limits* (no `SessionStart` hook yet): a SIGKILLed lifetime gets no event
  of its own and its tokens land in the next event as `lifetime.coverage.shortfall`;
  a `/clear` predecessor is settled only at its successor's `SessionEnd` in the same
  process; a fork's base comes from cost lineage (the same-lineage parent transcript),
  and a fork whose parent is not found has `cost_usd: null` and
  `coverage.fork_parent: not-found` (its copied entries are then found by the fork's
  first queue-operation, or for an interactive fork by the time gap at the fork
  point); a lost line comes back only through a backfill. Nothing on disk tells a
  process that resumed from another, still running, process's tool call from one
  that resumed after a kill, so at the resumer's own `SessionEnd` the other's
  in-flight request is counted in the resumer's event (and shows as shortfall);
  a later derivation, once the other process wrote its tool result, separates them.
- *Schema.* `schemas/diagnostic-event.schema.json` is a byte-identical copy of the
  schema owned by the cloud-catcher meta-repo (ADR-0006 there);
  `tests/test-diagnostic-schema-drift.py` pins the upstream commit and SHA-256.

Rotate the log with `scripts/rotate-audit-log.py --file .council/diagnostics.jsonl`.
The audit logger (`hooks/log-tool-call.*` over `scripts/log-tool-call.py`) follows the
same wrapper pattern, so bash and PowerShell share one implementation.

**Append semantics for `henka-register.jsonl`:** to update a record, append a
new entry with the same `henka_id` and updated `status`. Do NOT modify the
original entry. On read, the latest entry for a given `henka_id` wins.

---

## Category 3 — Council-Owned Working Files

These files may be written by the orchestrator as part of normal governance
operations, but all writes are logged and reversible.

| Path Pattern | Writer | Notes |
|---|---|---|
| `.council/course-corrections/after-sprint-{NN}.md` | Orchestrator | One per sprint boundary; may overwrite within same sprint |
| `.council/proposed/DEC-{NNNN}.md` | Orchestrator | Nemawashi position papers |
| `.council/proposed/archive/*.md` | Orchestrator | After ratification; append-style (no overwrites) |
| `.council/retrospectives/*.md` | Orchestrator (persists agent output) | Per-sprint and per-cycle |
| `.council/jishuken/*.md` | Orchestrator | Per-period reflection workshops |
| `.council/sessions/*.md` | Orchestrator | Compacted session notes |
| `.council/state/effective-autonomy.json` | `scripts/update-effective-autonomy.py` only | Not direct Write |
| `.council/standard-work.json` | Orchestrator after Level 5 approval | Retrospective proposes; user approves |

---

## Agent Constraints

**All Level 1–2 agents (architect, scope-guardian, henkaten-detector,
retrospective, qa-regression, rag-source):**

- MUST NOT write to any file.
- MUST NOT call `scripts/append-henka.py` or `scripts/append-decision.py`.
- Output is returned as the agent's response text; the orchestrator decides
  whether and what to persist.

**Orchestrator (Level 4):**

- May write to `.council/` working files.
- MUST use `scripts/append-henka.py` for henka-register entries and
  `scripts/append-decision.py` for decision-log entries.
- MUST NOT write to `.harness/` files except the `governance` key in
  `.harness/config.json` at kickoff.
- MUST NOT modify `features.json`, `spec.md`, or `sprints.json` without
  explicit Level 5 approval via the nemawashi walkthrough.

---

## Graceful Degradation When Reading Controlled Artifacts

If a controlled artifact is missing:

- `features.json` missing → scope-guardian returns `status: error` (cannot
  function without the canonical feature list).
- `spec.md` missing → architect and scope-guardian assess coherence against
  contracts only; note reduced confidence in `coverage` section.
- `sprints.json` missing → skip dependency checks; note in `coverage`.
- `henka-register.jsonl` missing → henkaten-detector treats this as a first
  run; no prior records to avoid duplicating.
- `decision-log.jsonl` missing → treat as first run; no linked decisions.

Agents MUST NOT hallucinate the contents of missing files.

---

## Summary

- Sacred files (`features.json`, `spec.md`, `sprints.json`): read-only to
  all agents; Level 5 approval required for any modification.
- Append-only logs: use only the validated append scripts; hooks block all
  other write paths.
- Council working files: orchestrator may write; all writes are logged and
  reversible via git.
- No Level 1–2 agent may write to any file under any circumstance.
