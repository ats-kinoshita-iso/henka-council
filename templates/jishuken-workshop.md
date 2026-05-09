# Jishuken Workshop — {topic}

<!-- Metadata block (machine-readable) -->
```yaml
topic: "{user-supplied topic slug, e.g. autonomy-floor-volatility}"
date: "{ISO-8601 UTC date, e.g. 2026-05-09}"
cadence: jishuken
generated_by: council-jishuken
invoked_by: user
agents_used: [retrospective, architect]
```

**Topic:** {topic}
**Date:** {UTC ISO-8601 date}
**Invoked by:** user

---

## Reflection Notes

*Evidence-grounded observations about the chosen topic. What does the record
show? What patterns or anomalies are visible? What has changed over time?
Each claim carries an evidence_class label.*

### What the Evidence Shows

- {Observation 1 — evidence_class: observed | inferred | speculative}
- {Observation 2}
- {Observation 3}

### Historical Context

*How has this topic evolved across the sprints reviewed?*

| Sprint / Period | State | Notable Events | Source |
|---|---|---|---|
| Sprint {NN} | {state of topic} | {event if any} | {eval report or decision} |

### Anomalies and Surprises

*What in the evidence was unexpected or contradicted prior assumptions?*

- {Anomaly 1}
- {Anomaly 2}

*If nothing was surprising: "Evidence consistent with prior working model —
no anomalies detected."*

---

## Open Questions

*Questions raised by the evidence that cannot yet be answered. Genuine
unresolved items — not rhetorical. Each question identifies what additional
evidence would resolve the ambiguity.*

### Unanswered Questions

1. {Question 1}
   - What evidence would resolve this: {evidence type needed}
   - Why it matters: {brief}

2. {Question 2}
   - What evidence would resolve this: {evidence type needed}
   - Why it matters: {brief}

### Assumption Audit

*What assumptions are embedded in the current standard work or agent behavior
related to this topic? Which assumptions are most at risk of being wrong?*

| Assumption | Basis | Confidence | Risk if Wrong |
|---|---|---|---|
| {assumption} | {where it comes from} | high \| medium \| low | {consequence} |

---

## Hypotheses

*Tentative theories about underlying dynamics. Each hypothesis is labeled by
testability and linked to the evidence from Reflection Notes. These are
candidates for future pdca cycle investigation — NOT action items.*

### Hypothesis Candidates

**H1: {Hypothesis title}**
- Theory: {one-sentence description of the causal mechanism}
- Supporting evidence: {evidence from Reflection Notes}
- Contradicting evidence: {if any}
- How to test: {what would need to happen in a future sprint for this to be
  confirmed or refuted}
- Testable in: {next pdca cycle | requires ≥N more sprints | requires
  specific condition}

**H2: {Hypothesis title}**
- Theory: {description}
- Supporting evidence: {evidence}
- Contradicting evidence: {if any}
- How to test: {test condition}
- Testable in: {timeline}

### Hypothesis Priority

*Which hypotheses are most actionable if confirmed?*

| Hypothesis | Priority | Next Step |
|---|---|---|
| H1: {title} | high \| medium \| low | Raise in next pdca cycle as improvement candidate |
| H2: {title} | high \| medium \| low | Gather ≥2 sprints evidence first |

---

## Evidence Summary

*All sources consulted during this jishuken workshop.*

| Source | Relevant To | Notes |
|---|---|---|
| `.council/henka-register.jsonl` | {sections} | {N records reviewed} |
| `.council/decision-log.jsonl` | {sections} | {N entries reviewed} |
| `.harness/evals/sprint-{NN}-r{R}.md` | {sections} | {sprints reviewed} |
| Prior retrospectives | {sections} | {N files reviewed} |
| Prior jishuken artifacts | {sections} | {N files reviewed, or "none"} |

---

*Note: This jishuken workshop is reflection-only. No standard-work proposals
are included. Hypotheses that suggest a standard-work change must be re-raised
by the user in a future PDCA pass via `/henkaten-council:council-retro`.
This is the mechanism for converting a jishuken finding into a ratified
process change. This workshop does not initiate that transition.*
