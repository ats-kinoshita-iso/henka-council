# Plan Handoff Frontmatter — Reference

This template documents the frontmatter envelope that
`/henkaten-council:from-plan` writes when it persists a plan-mode artifact.
The frontmatter is serialised as JSON inside YAML-style `---` fences (JSON
is a valid YAML subset). The body of the file follows the second `---`
fence as verbatim plan-mode prose.

Authoritative schema: `schemas/plan-handoff.schema.json`. The frontmatter
MUST validate against that schema; `scripts/persist-plan.py` enforces
validation at write time.

## Layout

```
---
{
  "intent": "<bootstrap | pre-sprint | course-correction>",
  "sprint_target": <integer or omitted for bootstrap>,
  "generated_at": "<ISO 8601 UTC, suffix Z>",
  "plan_mode_session_id": "<session id or omitted>",
  "plan_sha256": "<64-char lowercase hex>",
  "governance_state_at_capture": {
    "effective_autonomy": <0..5>,
    "open_henka_count": <integer >= 0>
  }
}
---

<plan body verbatim>
```

## Field Semantics

| Field | Purpose | Required |
|---|---|---|
| `intent` | Routes the dispatch — see `skills/from-plan/SKILL.md` Step 6. | Always |
| `sprint_target` | Sprint this plan targets (per-sprint contract seed or position paper). | When `intent` is `pre-sprint` or `course-correction` |
| `generated_at` | Audit timestamp; the moment `/from-plan` persisted the artifact. | Always |
| `plan_mode_session_id` | Claude Code session id at plan-approval time, when the runtime surfaces it. | Optional |
| `plan_sha256` | Hex digest of the canonicalised body (UTF-8, normalised to a single trailing newline). Cited as evidence in the `plan-bridge` `decision-log` entry. | Always |
| `governance_state_at_capture.effective_autonomy` | Floor value at capture (4 in bootstrap when `.council/` absent). | Always |
| `governance_state_at_capture.open_henka_count` | Count of henka register lines at capture (0 in bootstrap). | Always |

## Why a state snapshot?

The snapshot is for **audit only**. Downstream skills MUST re-read live
state (`state/effective-autonomy.json`, `henka-register.jsonl`) before
acting; the snapshot exists so a later reviewer can compare "what the
world looked like at capture" against "what the world looked like at
dispatch" and detect drift between the two.

The snapshot is also intentionally minimal — it does not duplicate
governance configuration (`config.json`, `council-manifest.json`). Those
files live in `.council/` and are version-controlled; the audit trail can
follow git history to reconstruct any other state value.

## Filename Convention

Set by `scripts/persist-plan.py` (`route_to_path`):

| `intent` | Path |
|---|---|
| `bootstrap` | `.council/proposed/from-plan-bootstrap.md` |
| `pre-sprint` | `.council/proposed/sprint-NN-contract-seed.md` |
| `course-correction` | `.council/proposed/position-paper-sprint-NN-<ts>.md` |

The bootstrap path is fixed (one per project lifetime). The pre-sprint
path keys on the sprint number — at most one contract seed per sprint
slot. The course-correction path includes a UTC timestamp because a
single sprint may receive multiple position papers across its life
(initial draft, revision after nemawashi feedback, etc.).

## Body Canonicalisation

Before the sha256 is computed, the body is normalised to end with exactly
one trailing newline (`\n`). This makes the audit chain externally
verifiable: any reader can strip the frontmatter fence with the regex
`^---\n.*?\n---\n\n` and re-hash the remaining UTF-8 bytes to obtain
the same digest stored in `plan_sha256`.

## Idempotency

A re-invocation of `persist-plan.py` with the same body (same sha256)
is a no-op: the script prints
`OK: identical plan already at <path> (sha256 match) — no write` and
exits 0. A different body for the same route overwrites the file in
place; the older content remains visible in git history.
