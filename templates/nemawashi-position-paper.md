# Nemawashi Position Paper — Template

<!-- Metadata block (machine-readable) -->
```yaml
decision_id: DEC-{NNNN}
proposed_at: {ISO-8601 UTC timestamp}
triggered_by: {agent_id that surfaced the need, e.g., "architect", "henkaten-detector"}
proposed_by_agent: orchestrator
sprint_context: {NN}
proposed_change_type: major | irreversible-action
reversibility: reversible | irreversible
status: draft | revised-rev{N} | ratified | rejected | deferred
nemawashi_walkthrough_version: {N}  # 0 if no Stage 3 revisions; ≥1 after Stage 3 cycles
```

**Document ID:** DEC-{NNNN}
**Date:** {ISO-8601 date}
**Sprint Context:** Sprint {NN}
**Proposed Change Type:** major | irreversible-action
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

## Stage 1 — Position Statement

*Purpose: The Orchestrator writes the full proposal and consensus chain BEFORE
presenting anything to the user. The position paper is the orchestrator's
complete analysis, with every agent's perspective and evidence chain, organized
so the user can form an independent judgment.*

*Instructions: Fill in every field below. Do NOT present this to the user until
the entire Stage 1 section is complete. Write the position paper first, then
begin Stage 2.*

### Title of Proposed Change

> {Concise title — e.g., "Add --strict flag to scripts/run-verification.py"}

### Proposed Change

> {One paragraph describing the proposed change clearly and specifically.
> What would be different after this change is applied? Which files are
> affected? What is the scope?}

### Trigger / Motivation

> {What triggered this proposal? Which agent's analysis surfaced the need?
> Reference the relevant Henkaten record (HK-NNNN) or sprint eval finding.
> What would happen if the change is NOT made?}

### Reversibility Assessment

- **Classification:** reversible | irreversible
- **Basis:** {Explanation — which row in the reversibility table in
  `skills/council-autorun/SKILL.md` Step 1D.1 applies, and why.}
- **Auto-escalation note:** {If irreversible: "This action is irreversible.
  Per §2.4.2 R9, it auto-escalates to mandatory nemawashi regardless of
  nominal scope. Level 5 (human) approval via Stage 4 is required."}

### Expected Scope of Impact

- **Files affected:** {list of relative file paths}
- **Agents affected:** {list of agent IDs whose behavior or context changes}
- **State affected:** {which `.council/` state files, decision-log entries,
  Henkaten records, or effective-autonomy state is touched}

### Agent Perspectives with Evidence

For each agent that contributed analysis to this decision:

#### Agent: architect
- **Finding:** {What did architect observe or infer?}
- **Evidence chain:**
  - `evidence_class: observed | inferred | speculative`
  - `confidence: 1–5`
  - `verification: {conformant verification command per §7.0.2 allowlist}`
- **Perspective on the proposed change:** {architect's view — does the
  evidence support the change? What caveats?}

#### Agent: scope-guardian
- **Finding:** {What did scope-guardian observe or infer?}
- **Evidence chain:**
  - `evidence_class: observed | inferred | speculative`
  - `confidence: 1–5`
  - `verification: {conformant verification command}`
- **Perspective on the proposed change:** {scope-guardian's view}

#### Agent: henkaten-detector
- **Finding:** {What did henkaten-detector observe or infer?}
- **Evidence chain:**
  - `evidence_class: observed | inferred | speculative`
  - `confidence: 1–5`
  - `verification: {conformant verification command}`
- **Perspective on the proposed change:** {henkaten-detector's view;
  include `change_origin: active | passive` and `fourM_axis` classification}

#### Agent: retrospective
- **Finding:** {What did retrospective observe or infer?}
- **Evidence chain:**
  - `evidence_class: observed | inferred | speculative`
  - `confidence: 1–5`
  - `verification: {conformant verification command}`
- **Perspective on the proposed change:** {retrospective's view — any
  yokoten or pattern connection to prior sprints?}

*(Add sections for any other active agents, e.g., qa-regression, rag-source)*

### Consensus Chain

> {Walk through how the individual agent perspectives converge on (or diverge
> from) the proposed change. Where do they agree? Where do they differ? What
> is the residual uncertainty? Which agents support? Which have caveats or
> reservations?}

### Affected Artifacts

| File | Change Type | Reversibility |
|---|---|---|
| {path/to/file} | {add / modify / delete} | {reversible / irreversible} |

---

## Stage 2 — Per-Agent Presentation

*Purpose: Walk the user through each agent's perspective one at a time,
giving them three handles to respond with: yes, refine, or disagree.
Build shared understanding incrementally. Do not rush to Stage 4.*

**Opening presentation script (Orchestrator says):**

> *"I've drafted a proposal at `.council/proposed/DEC-{NNNN}.md`. May I walk
> you through each agent's perspective before asking for approval? (yes/no)"*

If the user says `no`, halt and log `user_intervention_requested`.

**For each agent perspective, present in this order:**
1. architect → 2. scope-guardian → 3. henkaten-detector → 4. retrospective
→ (additional agents from council-manifest, if active)

**Per-agent presentation script (Orchestrator says for each):**

> *"[Agent Name] reviewed the sprint results and found: [brief summary of
> finding, evidence_class, confidence level]. [Agent Name]'s view is that
> [perspective on the proposed change, including any caveats or conditions].*
>
> *Does [Agent Name]'s framing match your understanding? (yes / refine / disagree)"*

**Three-handle responses and how to proceed:**

| Handle | Meaning | Orchestrator action |
|---|---|---|
| `yes` | User accepts this agent's perspective as stated | Record `{agent}: yes`. Present next agent. |
| `refine` | User has a specific modification to the agent's framing | Record the refinement. Re-present with refinement: *"Updated framing: [refined version]. Does that match? (yes / refine / disagree)"* If `yes`, record `{agent}: yes after refine`. |
| `disagree` | User disputes this agent's perspective fundamentally | Record `{agent}: disagree — [user's stated reason]`. Continue to next agent. Bring to Stage 3. |

All three-handle responses are logged to `.council/audit-log.jsonl` with:
`{ dec_id, agent_id, stage: 2, handle, reason_if_refine_or_disagree, timestamp }`

**Stage 2 completion record:**

| Agent | Handle | Notes |
|---|---|---|
| architect | yes \| yes after refine \| disagree | {reason if disagree or refine} |
| scope-guardian | yes \| yes after refine \| disagree | {reason if disagree or refine} |
| henkaten-detector | yes \| yes after refine \| disagree | {reason if disagree or refine} |
| retrospective | yes \| yes after refine \| disagree | {reason if disagree or refine} |

**Stage 2 aggregate result:**

- All `yes` (or `yes after refine`) → advance directly to Stage 4 (skip Stage 3).
- Any `disagree` → advance to Stage 3 regardless of other agents' handles.

---

## Stage 3 — Alignment / Revision History

*Purpose: Surface disagreements recorded in Stage 2, revise the position
paper to incorporate the user's framing, and confirm alignment before
asking for ratification.*

**Skip condition:** If all Stage 2 responses were `yes` (or `yes after refine`),
skip directly to Stage 4. Do not create any rev file.

**If any `disagree` handle was recorded in Stage 2:**

1. Summarize all `disagree` handles from Stage 2 (and any unresolved `refine`
   handles) — list each agent and the user's stated reason.
2. Revise the position paper to address all disagreements in a single pass.
3. **Save the revised paper as a new file** using the `-rev{N}` suffix naming
   convention:
   - First revision: `.council/proposed/DEC-{NNNN}-rev1.md`
   - Second revision: `.council/proposed/DEC-{NNNN}-rev2.md`
   - Each revision is a separate file in `.council/proposed/`; all versions
     are preserved for the audit chain.
4. Return to Stage 2 with the revised paper. Re-present ALL agents' perspectives.
5. If alignment is reached (all agents `yes` or `yes after refine`): proceed
   to Stage 4.
6. **Escalation-to-halt:** If alignment is not reached after 2 revision cycles
   (default; configurable in `.council/config.json`), log
   `status: escalated-to-user`, present remaining disagreements to the user,
   and HALT. Do not proceed to Stage 4 automatically.

**Track which agent's `disagree` or `refine` motivated each revision.**

**Stage 3 revision log:**

| Revision | File | Date | Motivated by | Changes Made | Stage 2 Re-run Outcome |
|---|---|---|---|---|---|
| rev1 | DEC-{NNNN}-rev1.md | {date} | {agent}: disagree — {reason} | {what changed in the paper} | {aligned / disagree continues} |
| rev2 | DEC-{NNNN}-rev2.md | {date} | {agent}: disagree — {reason} | {what changed} | {aligned / escalated-to-user} |

---

## Stage 4 — Ratify Prompt + Final Decision

*Purpose: Once all perspectives are aligned (no outstanding `disagree` handles),
the formal approval prompt is a confirmation, not a decision. The groundwork has
been laid; Stage 4 is the moment of commitment.*

*Precondition: All agents returned `yes` or `yes after refine` in Stage 2 (or
Stage 3's repeated Stage 2). If any `disagree` remains unresolved, return to
Stage 3 and do not proceed to Stage 4.*

**Final position statement (after all revisions):**

> {One paragraph summarizing the final state of the proposed change after
> incorporating all Stage 2 and Stage 3 refinements. This is the definitive
> description of what will be applied if ratified.}

**Ratification prompt (Orchestrator says — Level-5 step, user must type yes/no):**

> *"All perspectives are aligned on DEC-{NNNN}. To confirm:*
>
> ***Proposed change:** {one-sentence summary of final position}*
> ***Affected files:** {comma-separated list}*
> ***Reversibility:** {reversible / irreversible}*
>
> *Apply DEC-{NNNN}? (yes/no)"*

**Decision outcome:** ratified | rejected | deferred

---

**On `yes` (ratified):**

1. Apply the change immediately.
2. Commit with message: `DEC-{NNNN}: {description}`.
3. **Move** this file from `.council/proposed/` to
   `.council/proposed/archive/DEC-{NNNN}.md` — the original is moved (not
   copied, not deleted) so the audit chain is preserved. Per v2.1 amendment A4:
   the `decision-log.jsonl` `nemawashi_walkthrough_version` path must remain
   resolvable at this archive location.
4. Append audit-log entry: *"DEC-{NNNN} position paper archived at
   `.council/proposed/archive/DEC-{NNNN}.md`"*
5. Emit DEC entry via `scripts/append-decision.py`:

```yaml
decision_type: course-correction-major
dec_id: DEC-{NNNN}
nemawashi_walkthrough_version: {N}  # 0 if no Stage 3 revisions; ≥1 after cycles
reversibility: {reversible | irreversible}
status: ratified
applied_at: {ISO-8601 timestamp}
applied_automatically: false
user_approval_required: true
council_agents_involved: [architect, scope-guardian, henkaten-detector, retrospective]
evidence_cited: [{evidence_class, verification, summary}]
linked_henka_id: {HK-NNNN if applicable}
sprint_context: {NN}
```

**Archive path:** `.council/proposed/archive/DEC-{NNNN}.md`

---

**On `no` (rejected):**

1. Log `status: rejected`. Do NOT apply the change.
2. This file remains in `.council/proposed/` for reference.
3. Emit DEC entry via `scripts/append-decision.py`:

```yaml
decision_type: course-correction-major
dec_id: DEC-{NNNN}
nemawashi_walkthrough_version: {N}
reversibility: {reversible | irreversible}
status: rejected
applied_automatically: false
user_approval_required: true
```

---

## Appendix: Evidence Summary

| Agent | Claim | evidence_class | confidence | verification |
|---|---|---|---|---|
| {agent} | {claim} | {class} | {level} | {command} |

*(One row per evidence item cited in the decision)*
