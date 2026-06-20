---
name: council-charter
description: >
  Use this skill to author or update a work charter at the start of a unit of
  work (a sprint and/or a branch), declaring the strategic anchor it must stay
  aligned with, the workstreams it touches, and its exploration_mode
  (mainline | parallel-exploration | competitive). The charter is the
  single source of truth the work-start direction gate reads — it makes
  intentional parallel/"competitive" work legitimate WHEN declared, and flags
  divergent work that is silent. Writes .council/charters/sprint-NN.json via
  scripts/append-charter.py and runs the Layer A direction check.
version: "0.1.0"
tools:
  - Read
  - Glob
  - Grep
  - Bash
  - Write
invocation: /henkaten-council:council-charter [--sprint NN] [--mode mainline|parallel-exploration|competitive]
---

# council-charter — Declare the direction of a unit of work

## When to use

At **work-start**: before a sprint contract is approved, or when opening a
branch that diverges from the sanctioned mainline. This is the deliberate
"flag when work starts" step. A charter authored here is consumed by:

- the in-session council gate (`council-autorun` Step 1A.7 → `direction-guardian`),
- the branch-charter git hook (`hooks/enforce-branch-charter.sh`),
- the GitHub direction-check Action and any auto-opened draft PR,
- the trine-eval seam (`harness-sprint` Step 0.4), which reads the written verdict.

## Procedure

1. **Resolve config.** Read `.council/config.json` → `direction_check`
   (`anchor_path`, `locked_decisions`, `killed_workstreams`, `mainline_branch`).
   If `direction_check` is absent or `enabled: false`, tell the user the gate is
   off and offer to enable it; do not fabricate an anchor.
2. **Read the strategic anchor** at `anchor_path` so the charter cites a real
   section / decision, not a placeholder.
3. **Elicit the charter fields** (ask the user only for what cannot be inferred):
   - `sprint_context` and/or `branch` (default branch = `git branch --show-current`).
   - `workstream_scope` — the workstreams this work touches.
   - `exploration_mode`:
     - **mainline** — work on the sanctioned direction. Any anchor drift here is
       undeclared and will BLOCK.
     - **parallel-exploration** — a deliberate side-track / spike that may diverge.
     - **competitive** — an intentional competing implementation benchmarked
       against mainline ("competitive code development").
   - `divergence_justification` — **required** when mode ≠ mainline. Capture the
     competing hypothesis being tested.
   - `anchor_alignment` (optional) — per-workstream aligned/diverges notes.
4. **Write the charter** with `scripts/append-charter.py` (schema-validated
   against `schemas/work-charter.schema.json`; this is a council-owned working
   file — mutable, NOT append-only, so re-running updates it in place):
   ```
   python scripts/append-charter.py --file <charter.json>
   ```
5. **Run the Layer A direction check** and surface the verdict to the user:
   ```
   python scripts/direction-check.py --config .council/config.json \
     --charter .council/charters/sprint-{NN}.json \
     --spec .harness/spec.md --contract .harness/contracts/sprint-{NN}.md \
     --branch "$(git branch --show-current)"
   ```
   - **BLOCK** → do not proceed; reconcile the work with the anchor or declare
     the correct exploration_mode + justification.
   - **WARN** → proceed with the flag recorded; if on GitHub, label the PR by mode.
   - **PASS** → proceed.

## Notes

- The charter does not replace the contract; it declares the *direction* the
  contract must honor. The semantic check (Layer B) happens in `council-autorun`
  Step 1A.7 via the `direction-guardian` agent.
- Keep `killed_workstreams` keywords specific in config (e.g. "cmpx writer", not
  "writer") so the gate does not false-positive on sanctioned work.
