# Nemawashi Position Paper — Template

**Document ID:** DEC-{NNNN}
**Date:** {ISO-8601 date}
**Sprint Context:** Sprint {NN}
**Proposed Change Type:** minor | major | irreversible-action
**Reversibility:** reversible | irreversible
**Status:** draft | revised-rev{N} | ratified | rejected | deferred

---

## Purpose

This template structures a major decision through the four-stage nemawashi
(根回し) walkthrough. Every major decision and every irreversible action
that reaches the course-correction step of `/council-autorun` or
`/council-review` MUST use this template, producing a position paper at
`.council/proposed/DEC-{NNNN}.md`.

The nemawashi process is about building shared understanding before
committing to action — not just obtaining approval. Each stage is a genuine
exchange, not a formality.

After Stage 4 ratification, the position paper is moved to
`.council/proposed/archive/DEC-{NNNN}.md` (with an audit-log entry)
so the `decision-log.jsonl` `nemawashi_walkthrough_version` path
remains resolvable.

---

## Stage 1 — Position Paper (Write Before Presenting)

*Purpose: The Orchestrator writes the full proposal and consensus chain BEFORE
presenting anything to the user. The position paper is the orchestrator's
complete analysis, with every agent's perspective and evidence chain, organized
so the user can form an independent judgment.*

### Proposed Change

> {One paragraph describing the proposed change clearly and specifically.
> What would be different after this change is applied? Which files are
> affected? What is the scope?}

### Rationale

> {Why is this change being proposed? What evidence drives it? What would
> happen if the change is NOT made?}

### Reversibility Assessment

- **Classification:** reversible | irreversible
- **Basis:** {Explanation — which row in the reversibility table in
  `@instructions/human-approval.md` applies, and why.}
- **Escalation reason:** {If irreversible: explain why this triggers mandatory
  escalation to major path.}

### Agent Perspectives with Evidence

For each agent that contributed analysis to this decision:

#### Agent: {Agent Name}
- **Finding:** {What did this agent observe or infer?}
- **Evidence chain:**
  - `{evidence_class: observed | inferred | speculative}`
  - `confidence: high | medium | low`
  - `verification: {conformant verification command}`
- **Perspective on the proposed change:** {This agent's view — does the
  evidence support the change? What caveats?}

*(Repeat for each contributing agent)*

### Consensus Chain

> {Walk through how the individual agent perspectives converge on (or diverge
> from) the proposed change. Where do they agree? Where do they differ? What
> is the residual uncertainty?}

### Affected Artifacts

| File | Change Type | Reversibility |
|---|---|---|
| {path/to/file} | {add / modify / delete} | {reversible / irreversible} |

---

## Stage 2 — Sequential Agent Presentation

*Purpose: Walk the user through each agent's perspective one at a time,
giving them three handles to respond with: yes, refine, or disagree.
Build shared understanding incrementally. Do not rush to Stage 4.*

**Presentation script (Orchestrator says):**

> "I've drafted a proposal at `.council/proposed/DEC-{NNNN}.md`. May I walk
> you through each agent's perspective before asking for approval? (yes/no)"

**For each agent perspective (in order):**

> "[Agent Name] reviewed the sprint results and found: [brief summary of
> finding and evidence]. [Agent Name]'s view is that [perspective on
> the proposed change]."
>
> "Does [Agent Name]'s framing match your understanding? (yes / refine / disagree)"

**Three-handle responses:**

- `yes` — Record agreement, present the next agent's perspective.
- `refine` — Record the user's refinement. Update this section with the
  refined framing. Re-present the agent's perspective with the refinement.
- `disagree` — Record the disagreement. Continue to the next agent. Bring
  all disagreements together in Stage 3.

**Stage 2 completion note:**

> Record of each agent's Stage 2 outcome:
> - {Agent Name}: yes | refined | disagreement-noted
> *(Repeat for each agent)*

---

## Stage 3 — Alignment

*Purpose: Surface disagreements recorded in Stage 2, revise the position
paper to incorporate the user's framing, and confirm alignment before
asking for ratification.*

**If all Stage 2 responses were `yes`:** Skip directly to Stage 4.

**If disagreements or refinements were recorded:**

1. Summarize all disagreements and refinements.
2. Revise the position paper: save new version as `DEC-{NNNN}-rev{N}.md`.
3. Repeat Stage 2 for the revised paper.
4. If alignment is reached: proceed to Stage 4.
5. If alignment is not reached after 2 revision cycles: log
   `status: escalated-to-user`, present remaining disagreements, HALT.

**Stage 3 revision log:**

| Revision | Date | Changes Made | Outcome |
|---|---|---|---|
| rev1 | {date} | {what changed} | {aligned / unresolved} |

---

## Stage 4 — Ratify

*Purpose: Once all perspectives are aligned, the formal approval prompt is a
confirmation, not a decision. The groundwork has been laid; Stage 4 is the
moment of commitment.*

**Ratification prompt (Orchestrator says):**

> "All perspectives are aligned on DEC-{NNNN}. To confirm:
>
> **Proposed change:** {one-sentence summary}
> **Affected files:** {comma-separated list}
> **Reversibility:** {reversible / irreversible}
>
> Apply DEC-{NNNN}? (yes/no)"

**On `yes`:**

- Apply the change immediately.
- Commit with message: `DEC-{NNNN}: {description}`
- Move this file to `.council/proposed/archive/DEC-{NNNN}.md`
- Write decision-log entry with:
  - `nemawashi_walkthrough_version: {N}` (revision count; 0 if no revisions)
  - `reversibility: {reversible | irreversible}`
  - `status: ratified`
  - `applied_at: {ISO-8601 timestamp}`
- Audit-log entry: position paper archived at path above

**On `no`:**

- Log as `status: rejected`.
- Do NOT apply the change.
- This file remains in `.council/proposed/` for reference.
- Decision-log entry with `status: rejected`, `applied_automatically: false`.

---

## Appendix: Evidence Summary

| Agent | Claim | evidence_class | confidence | verification |
|---|---|---|---|---|
| {agent} | {claim} | {class} | {level} | {command} |

*(One row per evidence item cited in the decision)*
