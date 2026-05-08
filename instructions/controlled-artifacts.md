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
| `.council/audit-log.jsonl` | PostToolUse hook only |

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
