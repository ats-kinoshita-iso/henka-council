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

Invoke `scripts/classify-plan-intent.py`:

```bash
python ${CLAUDE_PLUGIN_ROOT}/scripts/classify-plan-intent.py
```

The script inspects `.harness/` and `.council/` and emits a single JSON
object on stdout:

```json
{"route": "<route>", "sprint": <int|null>, "reason": "<short reason>"}
```

Routes (evaluated in this order so that a course-correction signal
overrides an otherwise-pending sprint):

- `bootstrap` — `.harness/` does not exist (or exists without
  `.council/`, indicating an incomplete kickoff).
- `course-correction` — `.council/henka-register.jsonl` contains an
  open `change_origin: active` record flagged `impact_level:
  high-risk` (status not in `{responded, closed}`); OR the most recent
  sprint entry in `sprint-state.json` is `FAIL`.
- `pre-sprint` — both `.harness/` and `.council/` exist;
  `current_sprint` is an integer N and
  `.harness/contracts/sprint-NN.md` is absent.
- `ambiguous` (exit 2) — none of the above fires. The Orchestrator
  asks the user which route applies; the user's choice is passed
  explicitly to `--route` on `scripts/persist-plan.py`.

Capture the `route` and `sprint` fields; both feed Step 3.

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

Append a single entry to `.council/decision-log.jsonl` via
`scripts/append-decision.py`. Build the entry as a JSON object and
either write it to a temp file (`--file`) or pipe it on stdin:

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

`decision_type` is a free-form string in
`schemas/decision-log-entry.schema.json`; `plan-bridge` is listed in
the description's example set so the type is documented for auditors.
Sourcing the `plan_sha256` from the persisted file's frontmatter
(rather than recomputing it) keeps Step 3 and Step 5 in chain.

### Step 6 — Dispatch

Once persisted and logged, hand off to the appropriate downstream skill
via `Task`. Each route is wired sprint-by-sprint:

- `bootstrap` (Sprint 2, wired) → `/trine-eval:harness-kickoff`
  (Planner reads the staged prompt from
  `.council/proposed/from-plan-bootstrap.md`), then
  `/henkaten-council:council-kickoff`. The Orchestrator passes the
  persisted path as the prompt source; no further argument plumbing is
  needed because the kickoff skills already discover state from
  `.council/proposed/`.

- `pre-sprint` (Sprint 3, wired) → `/trine-eval:harness-sprint NN`.
  The Orchestrator's `Task` invocation MUST surface the contract-seed
  path in the prompt body, because `harness-sprint` does not take a
  seed argument — its contract negotiator reads the seed by path. The
  expected envelope:

  ```
  Task: /trine-eval:harness-sprint NN

  Contract seed for this sprint was staged via /henkaten-council:from-plan.
  Path: .council/proposed/sprint-NN-contract-seed.md
  Treat the body of that file as a NON-BINDING seed for contract
  negotiation. The Evaluator retains its standard review authority
  and may reject any criterion that does not pass the testability
  checks in /trine-eval:sprint-contract.
  ```

  The seed is non-binding by design — trine-eval's Evaluator still
  applies its full contract-review pass; the seed only provides a
  starting draft. If the seed file is absent at dispatch time, the
  Orchestrator falls back to standard `harness-sprint` invocation and
  logs a `change_origin: passive` henka record citing the missing
  expected artifact.

- `course-correction` (Sprint 4) →
  `/henkaten-council:council-review --consider <persisted-path>`.

In the current sprint, the `bootstrap` and `pre-sprint` arms
dispatch. If classification returns `course-correction`, the
Orchestrator persists and logs as usual but stops short of dispatch,
surfacing the persisted path to the user with a note that the
downstream skill arrives in Sprint 4.

---

## Sprint Status

Wired:

- Step 1 (locate body) — manual via `--plan-body` argument.
- Step 2 (classify) — `scripts/classify-plan-intent.py` (Sprint 2).
- Step 3 (persist) — `scripts/persist-plan.py`.
- Step 4 (hook self-check) — same procedure as `council-kickoff` §1d.
- Step 5 (decision-log) — `scripts/append-decision.py` with
  `decision_type: plan-bridge` (Sprint 2).
- Step 6 (dispatch) — `bootstrap` arm (Sprint 2) and `pre-sprint`
  arm (Sprint 3) wired.

Not wired yet:

- Step 6 `course-correction` arm — Sprint 4.

Sprint 1 demo: with an empty repo, invoke
`/henkaten-council:from-plan --route bootstrap --plan-body <path>` →
`.council/proposed/from-plan-bootstrap.md` is created with valid
frontmatter and `plan_sha256` matches the body's sha256.

Sprint 2 demo: from any repo state, run
`python scripts/classify-plan-intent.py` to see the inferred route on
stdout; then run `persist-plan.py` with that `--route`; then build the
`plan-bridge` decision-log entry and feed it to
`scripts/append-decision.py`. The full chain produces a persisted
artifact, a validated `decision-log.jsonl` entry citing the plan's
sha256, and (for `bootstrap`) a dispatch hand-off to
`/trine-eval:harness-kickoff` + `/henkaten-council:council-kickoff`.

Sprint 3 demo: in a project where `.harness/sprint-state.json` names
an integer `current_sprint` N and `contracts/sprint-NN.md` is absent,
the classifier returns `pre-sprint`. Persist with `--route pre-sprint
--sprint N`; the seed lands at `.council/proposed/sprint-NN-
contract-seed.md`. The Orchestrator then issues
`Task: /trine-eval:harness-sprint NN` with the seed path embedded in
the prompt body (see Step 6 envelope). The integration test
`tests/scripts/test-from-plan-pre-sprint-chain.py` covers everything
up to but not including the `Task` dispatch.

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
