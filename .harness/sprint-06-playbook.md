# Sprint 06 Orchestrator Playbook — Subagent Reliability Strategy

**Purpose:** Sprint 6 (S4 — Council Autorun + Andon Protocol + Verification Spot-Check) is `estimated_complexity: high` per [sprints.json](sprints.json) — the largest sprint in the plan. This playbook documents the operational adjustments the orchestrator should apply to mitigate the subagent stop-before-write pattern observed across sprints 3–5 (most severely in sprint 5, which forced a documented main-thread fallback eval).

**Status:** Pre-Sprint-6 advisory. Not part of the harness contract; not graded by any sprint. Orchestrator-internal runbook only.

---

## The pattern we are mitigating

Across sprints 3, 4, and 5, forked subagents (Generator and Evaluator) repeatedly executed all analysis steps but stopped **before** invoking the final `Write`/`Edit`/`commit` tool call. Counts:

| Sprint | Contract review | Implementation eval | Generator commit |
|---|---|---|---|
| 3 | 1 retry | 0 | 0 |
| 4 | 1 retry | 0 | 0 |
| 5 | 2 retries | **3 retries → forced main-thread fallback** | 1 (orchestrator committed) |

The pattern intensifies as the contract / implementation grows. Sprint 6 has 11 deliverable items (more than any prior sprint) and is the highest-risk sprint for this failure mode.

---

## Tactical adjustments for Sprint 6

### A. Split implementation into 3–4 narrower dispatches

Sprint 6's 11 deliverables form natural clusters. Do **not** spawn a single Generator for the whole sprint. Suggested split:

1. **Pass A — Verification spot-check infrastructure**
   - `scripts/run-verification.py` (allowlist enforcement, 10s timeout, project-root CWD, pre-invocation string check)
   - `tests/scripts/test-run-verification.py`
   - Single-purpose Python sprint; fast feedback.

2. **Pass B — Andon protocol enrichment**
   - `instructions/andon-protocol.md` extension (full implementation per §7.0.1, A10)
   - Dynamic autonomy floor logic (distinct-originator corroboration, pull-rate tracking)
   - Markdown-only; should land cleanly in one dispatch.

3. **Pass C — `skills/council-autorun/SKILL.md` (Steps 1A through 1I)**
   - The heaviest single deliverable. ~9 named steps in the spec.
   - May itself need to be split into Step 1A–1D and Step 1E–1I if the first attempt times out.

4. **Pass D — Dummy-project fixture + end-to-end acceptance test**
   - `tests/fixtures/dummy-project/` (minimal trine-eval baseline)
   - End-to-end S4 acceptance test against §15.5 assertions 1–6
   - Integration-test work; spawn last so it can exercise A/B/C deliverables.

### B. Write-first prompting for every Generator/Evaluator dispatch

Every subagent prompt must lead with the deliverable, not the rationale:

> "Your single non-negotiable task: write `<exact path>` to disk via the `Write` tool. Do not stop until you have verified the file exists via `ls <path>`. Skip any analysis that doesn't directly contribute to that write."

Then provide context. Avoid the "read these inputs, analyze them, and produce a contract" framing that worked in earlier sprints — the subagent now consistently exhausts itself on the analysis half.

### C. Pre-resolve findings on retry

When a subagent stops mid-stream and is re-spawned, **brief the next instance on what's already established** so it doesn't re-investigate:

> "Round-1 findings: B1 closed (weights now 100%), B2 closed (regex fixed); only check whether the new criterion overlaps existing ones."

Pre-resolution worked in sprints 4 and 5 — it cut a 4–6-iteration cycle down to one.

### D. Eval fallback budget: 2 retries, then main-thread on 3rd

If two forked-Evaluator dispatches stop before writing, **fall back to main-thread eval authoring on the third attempt** without further retries. Each retry burns context and time; the harness explicitly permits the fallback path with a `## Process Note`. Sprint 5 paid for 3 retries before falling back; Sprint 6 should fall back faster.

### E. Generator stages, orchestrator commits

For implementation passes, instruct the Generator:
> "Stage your changes via `git add` but do NOT commit. The orchestrator will commit after self-review."

This is what effectively happened on Sprint 5's final commit (Generator stopped before committing, orchestrator committed). Make it the explicit pattern. The Generator's audit chain is preserved via the staged file list; the orchestrator's commit message attributes the work back to the Generator.

### F. Contract criteria designed for incremental verification

Sprint 6's contract should favor SCs that can be verified against partial implementation. If `skills/council-autorun/SKILL.md` ships with Steps 1A–1F but not 1G–1I, an SC like "SKILL.md mentions all 9 steps" fails atomically; an SC like "each named step section exists" can fail per-step and pass-partial. Write contracts that support partial credit so retry rounds have somewhere to go.

---

## What we have already done in advance of Sprint 6

| Item | Status | Commit |
|---|---|---|
| `.gitignore` for subagent scratch | Done | `cc97a86` |
| Canonical spec + design docs committed | Done | `fd9960c` |
| `hooks/session-stopped-marker` format aligned to progress.md | Done | `49e50a8` |
| `plugin.json` license corrected to Apache-2.0 | Done | `49e50a8` |

These eliminate four sources of cross-sprint noise that Sprint 6's Gate 6 (scope-drift) would otherwise have to filter around.

---

## Out of scope for this playbook

- **Root-causing the subagent stop-before-write pattern** — that requires platform-level investigation (token budget, internal stopping criterion). The mitigations above are operational, not architectural.
- **Modifying the harness skill itself** — the `/trine-eval:harness-sprint` flow is owned by the trine-eval plugin. Strategy here adapts the orchestrator's behavior within that flow.
- **Changing the eval rubric** — we accept the `code_quality` 5→4 penalty when the fallback fires; that signal is the rubric working as designed.
