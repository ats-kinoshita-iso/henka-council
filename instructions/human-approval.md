# Human Approval Protocol — Behavioral Instructions

This instruction defines when and how the orchestrator requests human approval
for council decisions, distinguishing the **minor single-prompt path** from
the **major nemawashi walkthrough path**. It also documents the reversibility
rule that governs automatic escalation.

---

## Two Approval Paths

### Minor Path — Single-Prompt Approval

Used for small, reversible corrections that do not affect sprint structure,
feature scope, evaluation criteria (beyond ±10% weight), or governance rules.

Examples of minor actions:
- Technical notes additions to the next sprint contract
- Clarifying evaluation criteria (weight change ≤10%)
- Updating `.council/` working files (status, progress notes)
- Noting new dependencies (informational)
- Updating feature status from `pending` to `done`

**Prompt format:**

> "Apply minor correction: [description of change]? (yes/no)"

On `yes`: apply immediately. On `no`: log the decline and continue.

No position paper. No `nemawashi_walkthrough_version` entry in the
decision-log (field is `null` for minor decisions).

### Major Path — Nemawashi Walkthrough

Used for significant decisions: sprint reordering, feature changes, spec
amendments, criteria weight changes >10%, new sprints, architectural pivots,
governance rule changes, and — critically — **any irreversible action**.

The walkthrough proceeds in four stages:

---

## Nemawashi Walkthrough — Four Stages

### Stage 1 — Present the Position Paper

The orchestrator writes a position paper to `.council/proposed/DEC-{NNNN}.md`
using `templates/nemawashi-position-paper.md`. The paper contains:

- The proposed change with full rationale
- Each agent's perspective with evidence and `verification` commands
- The consensus chain showing how perspectives converge
- The reversibility classification of the proposed action

The orchestrator surfaces the paper to the user:

> "I've drafted a proposal at `.council/proposed/DEC-{NNNN}.md`. May I walk
> you through each agent's perspective? (yes/no)"

If the user declines, the walkthrough halts and the decision is left unresolved
(logged as `status: deferred`).

### Stage 2 — Sequential Agent-by-Agent Presentation

The orchestrator presents each agent's perspective one at a time. After each:

> "Does [Agent Name]'s framing match your understanding?
> (yes / refine / disagree)"

**Three handles — not two:**

- `yes` — proceed to the next agent's perspective.
- `refine` — the user wants to adjust the framing. The orchestrator records
  the refinement, updates the position paper section, and re-presents that
  agent's perspective before continuing.
- `disagree` — the user's understanding differs materially from the agent's.
  Record the disagreement and continue to Stage 3 before re-presenting.

This handle structure ensures the user has an incremental path to adjust
framing without restarting the entire walkthrough.

### Stage 3 — Align on Disagreements

If any `disagree` or `refine` responses were recorded in Stage 2:

- Orchestrator revises the position paper (new version with `-rev{N}` suffix:
  e.g., `DEC-0003-rev1.md`).
- Repeat Stage 2 for the revised paper.
- If all perspectives align after revision: proceed to Stage 4.
- If disagreements persist after two revision cycles: HALT. Log as
  `status: escalated-to-user` and present a summary of remaining disagreements.

If Stage 2 produced only `yes` responses: proceed directly to Stage 4.

### Stage 4 — Ratify

Once all agent perspectives are aligned with the user's framing:

> "All perspectives are aligned. Apply DEC-{NNNN}? (yes/no)"

On `yes`:
- Apply the change immediately; commit with `DEC-{NNNN}: {description}`.
- Move the position paper to `.council/proposed/archive/DEC-{NNNN}.md`
  (with an audit-log entry so the decision-log path remains resolvable).
- Write a `decision-log.jsonl` entry with `nemawashi_walkthrough_version: N`.

On `no`:
- Log as `status: rejected`.
- Do NOT apply the change.
- Position paper remains in `proposed/` for reference.

**The "implement rapidly" half of nemawashi** is preserved: once Stage 4
ratifies, the application is immediate and observable in a single git commit.
There is no deferred application, no "pending" state after ratification.

---

## Reversibility Rule — Auto-Escalation to Major

Every proposed action is classified as `reversible | irreversible` before the
minor/major determination is made.

**Irreversible actions automatically escalate to the major path (nemawashi
walkthrough) regardless of their nominal classification.**

The reversibility rule applies even when the orchestrator's nominal autonomy
level (Level 3 or 4) would normally permit auto-application. There is no
exception to this rule for any agent or autonomy level.

### Reversibility Classifier (v0.1)

| Action | Reversibility |
|---|---|
| File writes to `.council/working/`, `course-corrections/`, `proposed/`, `jishuken/`, `retrospectives/`, `sessions/` | Reversible (git revert) |
| Writes to append-only logs (`*.jsonl`) | Reversible-with-caveat (entry remains; counter-entry can supersede) |
| Writes to `.harness/features.json`, `spec.md`, `sprints.json` | Reversible (git revert) but Level 5 by Rule 3/7 |
| `git push`, `git push --force` | **Irreversible** → auto-escalates to major |
| `git reset --hard` | **Irreversible** → auto-escalates to major |
| `git rebase -i`, `git tag -d` (pushed tag) | **Irreversible** → auto-escalates to major |
| Public release / deployment / package publish | **Irreversible** → auto-escalates to major |

---

## Minor vs Major Reference Table

| Characteristic | Minor | Major |
|---|---|---|
| Scope | Localized; no structural change | Sprint structure, features, spec, or governance |
| Reversibility | Reversible (git revert) | Either; irreversible always escalates here |
| Criteria weight change | ≤10% | >10% |
| Approval mechanism | Single-prompt (yes/no) | Nemawashi walkthrough (4 stages) |
| Position paper | None | `DEC-{NNNN}.md` in `.council/proposed/` |
| Decision-log `nemawashi_walkthrough_version` | `null` | N (version integer) |
| Post-ratify archive | N/A | Position paper moved to `proposed/archive/` |

---

## Integration with Autonomy Levels

- **Level 3 (auto-apply minor):** The orchestrator may apply minor, reversible
  corrections without prompting. Irreversible actions block regardless.
- **Level 4 (coordinate sequences):** Same as Level 3 for individual actions.
  Major decisions still require the nemawashi walkthrough.
- **Dynamic floor drop:** If the effective autonomy floor has been lowered
  (see `state/effective-autonomy.json`), the orchestrator respects the lowered
  floor. A Level 4 orchestrator operating at an effective floor of Level 1
  must treat all actions as requiring user approval.

---

## Summary Checklist for Orchestrator

Before applying any correction:

- [ ] Classify action as `reversible` or `irreversible`.
- [ ] If irreversible: escalate to major/nemawashi regardless of nominal class.
- [ ] If minor and reversible: use single-prompt path.
- [ ] If major: initiate four-stage nemawashi walkthrough.
- [ ] Stage 2 must offer three handles: `yes`, `refine`, `disagree`.
- [ ] Stage 4 ratification leads to immediate application + archive + decision-log.
- [ ] Write `nemawashi_walkthrough_version` to decision-log (null for minor).
