# PDCA Retrospective — Cycle {cycle_id}

<!-- Metadata block (machine-readable) -->
```yaml
cycle_id: "{cycle identifier, e.g. cycle-02}"
sprints_covered: [{NN}, {NN+1}, {NN+2}]   # sprint numbers in this cycle
date: "{ISO-8601 UTC date, e.g. 2026-05-09}"
cadence: pdca
generated_by: council-retro
cycle_results:
  pass: {N}
  partial: {N}
  fail: {N}
standard_work_proposals_count: {N}   # 0 if no Act proposals
```

**Cycle:** {cycle_id}
**Sprints:** {NN} — {NN + cycle_length - 1}
**Date:** {UTC ISO-8601 date}
**Cycle Results:** {N} PASS / {N} PARTIAL / {N} FAIL

---

## Plan

*What was intended for this cycle. Links to sprint contracts and active
standard work. What improvement hypotheses were being tested?*

### Active Standard Work This Cycle

Link to `.council/standard-work.json` — what process rules were in effect
at the start of this cycle?

| Practice | Since | Notes |
|---|---|---|
| {practice description} | Sprint {NN} | {context} |

### Sprint Contracts (This Cycle)

| Sprint | Contract | Key SC Changes from Prior Cycle |
|---|---|---|
| {NN} | `.harness/contracts/sprint-{NN}.md` | {changes from cycle boundary} |

### Improvement Hypotheses Under Test

*What hypotheses from the last pdca cycle's Act section were being tested?*

- {Hypothesis 1: description + expected signal if confirmed}
- {Hypothesis 2}

*If first cycle: "No prior pdca cycle — no hypotheses under test."*

---

## Do

*What was actually built and executed. Where did execution diverge from Plan?*

### Sprint Outcomes

| Sprint | Result | Eval Score | Notes |
|---|---|---|---|
| {NN} | PASS \| PARTIAL \| FAIL | {score} | {brief} |

### Execution Divergences from Plan

*Where did actual sprint execution differ from the standard work or the Plan
above? Each divergence links to the relevant Henkaten record (HK-NNNN) or
decision entry (DEC-NNNN).*

- {Divergence 1 — HK-NNNN or DEC-NNNN}
- {Divergence 2}

*If no divergences: "Execution matched Plan within expected variance."*

### Decisions Made This Cycle

*Summary of DEC entries from `.council/decision-log.jsonl` during this cycle.*

| DEC ID | Type | Outcome | Notes |
|---|---|---|---|
| DEC-{NNNN} | {type} | ratified \| rejected | {brief} |

---

## Check

*Evidence-driven analysis. Every pattern claim requires ≥2 sprints of evidence.
Read `.harness/summary.md` (if available) and `regression.json` (note absence
if not present).*

### Cross-Sprint Patterns

*Recurring issues, successes, or surprising behaviors appearing in ≥2 sprints.
Label evidence_class accurately.*

| Pattern | Sprints | Evidence Class | Confidence | Notes |
|---|---|---|---|---|
| {pattern description} | {NN, NN+1} | observed \| inferred | 1–5 | {evidence} |

### Improvement Hypothesis Results

*For each hypothesis from the Plan section: confirmed, refuted, or inconclusive?*

| Hypothesis | Result | Evidence | Confidence |
|---|---|---|---|
| {hypothesis} | confirmed \| refuted \| inconclusive | {evidence} | {1–5} |

### Cross-Sprint Summary Reference

- `.harness/summary.md` — available | unavailable (note if unavailable)
- `regression.json` — available | unavailable (note if unavailable)
- Autonomy floor history (`.council/state/effective-autonomy.json`) — {summary}

### Jishuken Artifacts Reviewed

*Any `.council/jishuken/*.md` artifacts created during this cycle that inform
the Check analysis.*

- {topic}-{date}.md — {relevance to Check findings}

---

## Act

*Process improvement proposals grounded in the Check findings. These are
CANDIDATES — not applied changes. Each proposal that the team wants to advance
MUST be routed through the nemawashi walkthrough (council-autorun Step 1D) for
Level 5 (user) approval. Standard-work.json is NOT modified directly from
this section.*

### Standard-Work Proposal Candidates

*Each proposal must be grounded in ≥2 sprints of evidence (or 1 sprint with
strong deterministic evidence and explicit justification). Proposals MAY
target any of the standard-work arrays: `procedures[]`, `failure_patterns[]`,
`evaluation_improvements[]`, `workflow_notes[]`, or `loop_shapes[]` (the
last documented in its own subsection below).*

| Proposal | Pattern Type | Grounding Evidence | Priority | Action |
|---|---|---|---|---|
| {description of proposed change} | procedure \| failure-pattern \| evaluation-improvement \| workflow-note \| loop-shape | {sprint evidence, ≥2 sprints} | high \| medium \| low | advance via nemawashi \| defer |

**How to advance a proposal:**
1. Invoke council-autorun Step 1D (nemawashi walkthrough) for each proposal
   the team wants to ratify. Set `pattern_type` in the nemawashi position
   paper front-matter to declare which standard-work array the proposal
   targets.
2. The walkthrough produces a DEC entry and, after Stage 4 ratification,
   updates `standard-work.json`.
3. `standard-work.json` is NEVER modified directly from this template or the
   Act section — all changes require explicit Level 5 ratification.

### Loop-Shape Candidates

*OPTIONAL — fill in only when the PDCA cycle surfaced a reusable structural
pattern for HOW loops are organized (e.g. "Plan-Then-Execute Loop", "Probe
Campaign"). Loop-shapes use the pattern-language form, distinct from
procedure step lists. See ADR-0005 for the design rationale.*

For each candidate, document the pattern-language fields the schema requires
(`schemas/standard-work.schema.json` `loop_shapes[]` entries):

#### Candidate: {shape_id}

- **Name:** {human-readable name}
- **Problem:** {the recurring problem this shape addresses}
- **Forces:** {the competing forces / tradeoffs the shape balances}
- **Solution:** {the structural solution}
- **Consequences:** {what the shape costs and gains}
- **When not to use:** {conditions where this shape is the wrong choice} (OPTIONAL)
- **Evidence sprints:** [{sprint numbers where this pattern was observed}]
- **Status:** candidate

Loop-shape candidates ratify through the same 4-stage nemawashi walkthrough
as procedure candidates. The position paper's front-matter sets
`pattern_type: loop-shape` so the Stage 4 ratification updates
`loop_shapes[]` rather than `procedures[]`.

### Deferred Candidates

*Proposals not ready for advancement (insufficient evidence, low priority, or
needs more jishuken study).*

- {Proposal}: deferred to cycle {cycle_id+1} — reason: {evidence gap}

### Open Items for Next Cycle's Plan

*Hypotheses to carry into the next cycle's Plan section.*

- {New hypothesis for testing in the next N sprints}

---

## Yokoten Propagation

*Populated for each Henkaten record closed during this PDCA cycle. The
Orchestrator reads these fields during Step 1A.5 of subsequent sprints.*

### HK-{NNNN} (if closed during this cycle)

```yaml
yokoten:
  applicable_to_subsequent_sprints: [NN+1, NN+2]   # or ["all"]
  adaptation_notes: >
    {Starting point for the adaptation prompt. User finalizes during Step 1A.5.}
```

*If no Henkaten records were closed during this cycle, this section is omitted.*

---

## Coverage

*Data sources read for this retrospective.*

| Source | Available | Notes |
|---|---|---|
| `.harness/summary.md` | yes \| no | {notes} |
| `regression.json` | yes \| no | {notes} |
| `.harness/evals/sprint-{NN}-r{R}.md` (all) | yes \| partial | {notes} |
| `.council/henka-register.jsonl` | yes \| no | {notes} |
| `.council/decision-log.jsonl` | yes \| no | {notes} |
| Prior retrospectives | yes \| partial \| none | {notes} |
| Jishuken artifacts | yes \| none | {count} artifacts reviewed |
