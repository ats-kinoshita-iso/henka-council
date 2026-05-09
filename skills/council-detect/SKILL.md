---
name: council-detect
description: >
  Use this skill to run on-demand henkaten (change-point) detection against the
  current project state. Classifies detected changes by 4M axis and
  change_origin (active vs passive), applies configurable sensitivity thresholds
  (conservative / balanced / sensitive), and writes detected records to
  .council/henka-register.jsonl via scripts/append-henka.py.
version: "0.1.0"
tools:
  - Read
  - Glob
  - Grep
  - Bash
  - Write
  - Task
invocation: /henkaten-council:council-detect [--sensitivity conservative|balanced|sensitive]
---

# council-detect

On-demand henkaten change-point detection skill for the henkaten-council
governance plugin. User-invoked for targeted inspection of project state
deviations. Complements the automatic detection in council-autorun Step 1A.

**Prerequisite:** `.council/` must already exist in the target project (run
`/henkaten-council:council-kickoff` first).

---

## Purpose

`council-detect` is the on-demand version of the henkaten detection logic
that runs automatically in council-autorun Step 1A. Use it when:
- You want to inspect the current project state for change-points outside the
  normal sprint loop
- You are investigating a specific suspected deviation before a sprint starts
- You want to calibrate detection sensitivity for your project context

The skill dispatches the `henkaten-detector` agent with a user-specified
sensitivity threshold, collects detected change-points, classifies each by
`change_origin` and 4M axis, and writes records to `.council/henka-register.jsonl`
via `scripts/append-henka.py`.

---

## Sensitivity Thresholds

The detection sensitivity controls how aggressively the henkaten-detector
agent flags deviations. Three tiers are available:

### `conservative` — Low False-Positive Mode

Only the most clearly unscheduled and impactful deviations are flagged:
- Changes to files outside all known sprint scopes
- Deletions of controlled artifacts
- Changes to `schemas/` or `hooks/` outside any declared sprint scope
- High-confidence changes with `evidence_class: observed`

**Use when:** running detection mid-sprint when scheduled edits are common
and you only want to catch genuine anomalies.

### `balanced` — Default Detection Mode

Standard detection matching the behavior of council-autorun Step 1A:
- All `conservative` detections plus:
- File modifications to `agents/`, `instructions/`, `templates/`, `skills/`
  outside the active sprint scope
- State drift in `.council/state/` files
- `change_origin: passive` changes from CI or external tooling
- All medium- and high-impact deviations

**Use when:** running detection as a health check before or after a sprint.
This is the default if no `--sensitivity` flag is provided.

### `sensitive` — High-Coverage Mode

All deviations flagged, including low-impact and inferred ones:
- All `balanced` detections plus:
- Any file modified outside the explicit sprint file list (even if plausibly
  in-scope)
- Low-confidence pattern deviations (label as `speculative`)
- Timestamp drift, minor metadata changes
- All `change_origin: active` corrections logged in decision-log but not yet
  reflected in Henkaten records

**Use when:** doing a thorough audit at a cycle boundary, or when
investigating a suspected systematic issue across multiple sprint boundaries.

Default sensitivity: `balanced` (if `--sensitivity` is not provided).

---

## `change_origin` Classification (R1)

Every detected change-point is classified by its origin:

| `change_origin` | Meaning | Examples |
|---|---|---|
| `active` | The council or orchestrator initiated the change | Applied course correction, retroactively updating a state file, council-initiated file write |
| `passive` | The change arrived from outside the council's actions | User edit, CI artifact, trine-eval output, external dependency bump, file restored by build tool |

This classification is mandatory. The henkaten-detector agent MUST assign
`change_origin` to every record. If origin is ambiguous, assign the most
likely origin and set `evidence_class: inferred` with `confidence ≤ 3`.

---

## 4M Axis Classification

Every detected record is also classified on the 4M axis per
`schemas/henka-record.schema.json`:

| Axis | Meaning | Examples |
|---|---|---|
| `Man` | Human-introduced change | User edited a file, operator changed config |
| `Machine` | Tool or automated process change | CI pipeline output, automated script write |
| `Method` | Process or procedure change | Governance rule update, skill instruction change |
| `Material` | Input/output artifact change | Schema update, sprint contract modification |

---

## Step D0 — Parse Arguments

Read the `--sensitivity` flag (default: `balanced`). Validate the value is one
of `conservative`, `balanced`, or `sensitive`. If invalid, surface an error
and halt.

---

## Step D1 — Load Baseline State

Read the reference baseline for detection:
- `.council/henka-register.jsonl` — existing records (to avoid duplicates)
- `.council/decision-log.jsonl` — decisions that may explain active changes
- `.harness/sprints.json` — sprint scope definitions (for scheduled suppression)
- `.harness/contracts/sprint-{NN}.md` — current sprint's declared file scope
- `.council/standard-work.json` — expected standard-work state

Retrieve the last-known clean state via:
```
git diff HEAD -- .claude-plugin/plugin.json
git log --oneline -5
```

---

## Step D2 — Dispatch henkaten-detector Agent

Dispatch `agents/henkaten-detector.md` as a fork-context subagent via `Task`.
Pass:
- Sensitivity tier
- Baseline state (file lists, schema paths)
- The scheduled-suppression rule: edits within the active sprint's declared
  scope are scheduled deliverables and MUST NOT generate Henkaten records
  (per council-autorun Step 1A.4)
- `change_origin` classification requirements (R1)
- 4M axis schema reference: `schemas/henka-record.schema.json`

The henkaten-detector agent returns a list of candidate Henkaten records with
classification fields populated.

---

## Step D3 — Filter, Verify, and Write Records

For each candidate record returned by the henkaten-detector agent:

1. **Scheduled suppression check:** verify the file is not within the active
   sprint's declared scope (per Step 1A.4 of council-autorun). If it is
   scheduled, discard the candidate and log a suppression note.

2. **Duplicate check:** scan `.council/henka-register.jsonl` for an existing
   open record with the same `change_type` and `affected_files`. If a duplicate
   exists, update the existing record's `last_seen` timestamp rather than
   creating a new record.

3. **Evidence validation:** verify `evidence_class`, `confidence`, and
   `change_origin` are all present and valid. If any field is missing, reject
   the record and log a validation warning.

4. **Write to `henka-register.jsonl`:** append validated records via
   `scripts/append-henka.py`. This is the ONLY permitted write path for
   Henkaten records (per the controlled-artifacts append-only rule).

```
python scripts/append-henka.py --record '{...}'
```

`scripts/append-henka.py` performs schema validation against
`schemas/henka-record.schema.json` before appending. If validation fails,
the script returns non-zero and the Orchestrator halts with the error.

---

## Step D4 — Surface Detection Summary

After all records are written (or suppressed), surface a summary to the user:

- Count of new records written
- Count of duplicates updated
- Count of candidates suppressed (scheduled scope)
- Count of candidates rejected (validation failure)
- Severity breakdown: `high` / `medium` / `low` / `informational`
- Any `blocking` or `high-risk` records — these require resolution before
  the next sprint can start (per council-autorun Step 1A.2 halt logic)

---

## What This Skill Does NOT Do

- **Does NOT modify Henkaten records in place** — only appends via
  `scripts/append-henka.py` (append-only rule)
- **Does NOT resolve Henkaten records** — resolution happens during
  retrospectives (council-retro-mini, council-retro) or via council-review
- **Does NOT replace council-autorun Step 1A** — the autorun runs detection
  automatically before every sprint; this skill is for on-demand inspection
- **Does NOT produce standard-work proposals** — detection is classification
  only; prescriptive action belongs to the retrospective cadences

---

## Cross-References

| Dependency | Purpose |
|---|---|
| `agents/henkaten-detector.md` | Change-point classification agent dispatched by this skill |
| `scripts/append-henka.py` | Append-only writer for `.council/henka-register.jsonl` (sprint 4 deliverable) |
| `schemas/henka-record.schema.json` | Schema for henkaten record validation (4M axis enum, change_origin enum) |
| `skills/council-autorun/SKILL.md` Step 1A | Automatic detection in the sprint loop (sister flow to this skill) |
| `.council/henka-register.jsonl` | Destination for detected records |
| `.harness/contracts/sprint-{NN}.md` | Sprint scope for scheduled-suppression check |
