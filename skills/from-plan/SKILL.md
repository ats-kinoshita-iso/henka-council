---
name: from-plan
description: >
  Use this skill immediately after exiting Claude Code's Plan mode. It persists
  the approved plan-mode artifact into .council/proposed/ with a frontmatter
  envelope and routes the dispatch to either /trine-eval:harness-kickoff +
  /henkaten-council:council-kickoff (bootstrap), /trine-eval:harness-sprint
  (pre-sprint contract seed), or /henkaten-council:council-review (course
  correction) — based on .harness/ and .council/ state, not user choice.
version: "0.1.0"
author: Atsushi Kinoshita
skill_type: bridge
requires_trine_eval: true
agents_used:
  - orchestrator
cross_references:
  - agents/orchestrator.md
  - skills/council-kickoff/SKILL.md
  - schemas/plan-handoff.schema.json
  - scripts/persist-plan.py
  - templates/plan-handoff-frontmatter.md
---

# From-Plan Skill

This skill is the single sanctioned exit ramp from Claude Code's Plan mode
into a council-governed session. It encodes three contracts:

1. The plan-mode artifact is **persisted** with a frontmatter envelope
   before any dispatch occurs, so the handoff is auditable and resumable
   across context compaction.
2. The dispatch route is **derived from live state** — `.harness/` and
   `.council/` are inspected; the user does not choose the route by
   argument (except in Sprint 1, where the classifier is not yet wired).
3. The orchestrator's audit chain is preserved: a `plan-bridge` entry is
   appended to `decision-log.jsonl` citing the plan body's sha256 as
   evidence.

The skill is a procedural document for the Orchestrator. Actual file
writes and dispatches are performed at runtime.

---

## Procedure

### Step 1 — Locate the approved plan body

The plan body is the verbatim content the user approved via `ExitPlanMode`.
Resolution order:

1. **Explicit argument**: if the user invoked
   `/henkaten-council:from-plan <path>`, use `<path>`.
2. **Plan-mode artifact path**: if the runtime surfaces a plan file path
   in the `EnterPlanMode` system message (Claude Code ≥ 0.3.0 convention),
   read that file.
3. **Transcript fallback**: if neither (1) nor (2) is available, scan the
   most recent assistant message for the largest fenced block beginning
   with a level-1 heading. Treat that block as the body. This fallback is
   best-effort; surface the candidate to the user and ask for
   confirmation before persisting.

Validate that the body is non-empty. If empty, abort with a clear message.

### Step 2 — Classify intent

**Sprint 2 deliverable.** `scripts/classify-plan-intent.py` (Sprint 2)
reads `.harness/` and `.council/` state to decide one of:

- `bootstrap` — `.harness/` does not exist.
- `pre-sprint` — both `.harness/` and `.council/` exist;
  `sprint-state.json` has a pending sprint with no negotiated contract.
- `course-correction` — both exist; the most recent sprint entry in
  `sprint-state.json` is `fail`, OR `.council/henka-register.jsonl`
  contains an open `change_origin: active` record flagged `high-risk`.

In Sprint 1 the route is supplied explicitly via `--route` to
`scripts/persist-plan.py`. The Orchestrator asks the user when
classification is ambiguous.

### Step 3 — Persist with frontmatter

Invoke `scripts/persist-plan.py`:

```bash
python ${CLAUDE_PLUGIN_ROOT}/scripts/persist-plan.py \
  --route <bootstrap|pre-sprint|course-correction> \
  [--sprint <NN>] \
  --plan-body <path-to-plan-body>
```

The script:

- Reads the body and computes its sha256.
- Snapshots `governance_state_at_capture` (effective autonomy floor, open
  henka count) — defaults to `4` / `0` when `.council/` is absent.
- Validates the frontmatter against `schemas/plan-handoff.schema.json`.
- Pre-creates `.council/proposed/` if absent (bootstrap path).
- Writes the file to the route's canonical path (see the filename
  convention in `templates/plan-handoff-frontmatter.md`).
- `git add`s the file when the target is on a `.council/` path.
- Prints the canonical path to stdout.

Capture the printed path; it is needed for Steps 5 and 6.

### Step 4 — Hook installation self-check (strict parity)

This skill enforces the same hook gate as `council-kickoff` Step 1d.
Before any dispatch, verify that all four hooks are registered in the
target project's `.claude/settings.local.json`:

- `hooks/enforce-append-only.sh` (`PreToolUse` matcher `Write|Edit`)
- `hooks/enforce-reversibility.sh` (`PreToolUse` matcher `Bash`)
- `hooks/log-tool-call.sh` (`PostToolUse` matcher `*`)
- `hooks/session-stopped-marker.sh` (`Stop`)

On Windows targets, substitute the `hooks/win/<name>.ps1` siblings invoked
via `pwsh -NoLogo -NoProfile -File ...` (parity per v2.1 amendment A7).

If any hook is missing, **STOP**. Surface the registration snippet from
`skills/council-kickoff/SKILL.md` §1d.1 (or §1d.2 on Windows) and
instruct the user to paste it into `.claude/settings.local.json`, then
re-invoke `/henkaten-council:from-plan`. Running the council without
these hooks breaks the append-only audit chain; the bridge must not
degrade governance silently.

This skill **never modifies `.claude/settings.local.json` automatically.**

### Step 5 — Append decision-log entry

**Sprint 2 deliverable.** Append a single entry to
`.council/decision-log.jsonl` via `scripts/append-decision.py`:

```json
{
  "decision_id": "DEC-NNNN",
  "timestamp": "<ISO-8601-now>",
  "decision_type": "plan-bridge",
  "decision_outcome": "applied",
  "council_agents_involved": ["orchestrator"],
  "evidence_cited": [
    { "path": "<persisted-plan-path>", "sha256": "<plan-sha256>" }
  ],
  "applied_automatically": true,
  "user_approval_required": false,
  "affected_files": ["<persisted-plan-path>"],
  "sprint_context": <sprint or 0>,
  "autonomy_level_used": 4,
  "effective_autonomy_at_decision": <observed level>,
  "reversibility": "reversible",
  "nemawashi_walkthrough_version": null,
  "description": "Plan-mode artifact persisted and routed to <route>"
}
```

The `plan-bridge` `decision_type` requires adding an entry to the
`decision-log-entry.schema.json` enum; that schema amendment is part of
Sprint 2.

### Step 6 — Dispatch

**Sprint 2–4 deliverable per route.** Once persisted and logged, hand off
to the appropriate downstream skill via `Task`:

- `bootstrap` → `/trine-eval:harness-kickoff` (Planner reads the staged
  prompt from `.council/proposed/from-plan-bootstrap.md`), then
  `/henkaten-council:council-kickoff`.
- `pre-sprint` → `/trine-eval:harness-sprint NN`, passing the contract
  seed file path as a non-binding seed for contract negotiation.
- `course-correction` →
  `/henkaten-council:council-review --consider <persisted-path>`.

Sprint 1 stops after Step 4. The dispatch step is filled in
sprint-by-sprint as the corresponding routes come online.

---

## Sprint 1 Scope (this delivery)

Wired:

- Step 1 (locate body) — manual via `--plan-body` argument.
- Step 3 (persist) — `scripts/persist-plan.py` complete.
- Step 4 (hook self-check) — same procedure as
  `council-kickoff` §1d.

Not wired yet:

- Step 2 (classify) — Orchestrator asks the user for `--route`.
- Step 5 (decision-log) — deferred (waits on the `plan-bridge` enum
  addition to `decision-log-entry.schema.json`, plus the dispatch
  context).
- Step 6 (dispatch) — deferred to Sprints 2–4.

Sprint 1 demo: with an empty repo, invoke
`/henkaten-council:from-plan --route bootstrap --plan-body <path>` →
`.council/proposed/from-plan-bootstrap.md` is created with valid
frontmatter and `plan_sha256` matches the body's sha256.

---

## Idempotency

`scripts/persist-plan.py` treats a re-invocation with an identical plan
body (same sha256) as a no-op: it logs
`OK: identical plan already at <path> (sha256 match) — no write` and
exits 0. A different body for the same route overwrites the file in
place; older content remains visible in git history — that is the audit
trail for plan revisions.

## Error Handling

| Condition | Behavior |
|---|---|
| `--plan-body` missing or empty | Abort with non-zero exit; surface the error |
| Frontmatter fails schema validation | Abort; print the validator path and message |
| `--sprint` missing for non-bootstrap | Abort with usage error (exit 2) |
| `.council/proposed/` cannot be created | Abort; surface the OSError |
| Hooks missing (Step 4) | Abort; surface the registration snippet |
| Plan body identical to existing file | Skip write; exit 0 with `sha256 match` log |

## Cross-References

- Orchestrator agent contract: `agents/orchestrator.md`
- Council kickoff (hook snippet): `skills/council-kickoff/SKILL.md`
- Plan handoff schema: `schemas/plan-handoff.schema.json`
- Persist plan script: `scripts/persist-plan.py`
- Frontmatter reference: `templates/plan-handoff-frontmatter.md`
