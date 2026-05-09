# Sprint {NN} Mini Retrospective

<!-- Metadata block (machine-readable) -->
```yaml
sprint: {NN}
title: "{Sprint title from contract}"
date: "{ISO-8601 UTC date, e.g. 2026-05-09}"
result: PASS | PARTIAL | FAIL
cadence: mini
generated_by: council-retro-mini
```

**Sprint:** {NN}
**Title:** {Sprint title from `.harness/contracts/sprint-{NN}.md`}
**Date:** {UTC ISO-8601 date}
**Result:** PASS | PARTIAL | FAIL

---

## Learning Points

*What worked, what was harder than expected, what surprised the team.
Sprint-scope only — no cross-sprint synthesis here (that belongs to pdca mode).
Keep to 3–7 bullet points to fit the 30s time budget.*

- {Learning point 1}
- {Learning point 2}
- {Learning point 3}

---

## Pattern Observations

*Early signals of recurring patterns. Label as `inferred` if based on fewer
than 2 sprints of evidence — ≥2 sprints are required to confirm a pattern.*

- {Pattern observation 1} (evidence_class: inferred | observed)
- {Pattern observation 2}

*If no patterns observed: "No pattern observations — insufficient cross-sprint
evidence at this sprint boundary."*

---

## Henkaten Records Closed This Sprint

*List all HK-NNNN records resolved (closed) during this sprint.*

| Record ID | Type | Summary | Closed At |
|---|---|---|---|
| HK-{NNNN} | {change_type} | {one-line summary} | {ISO-8601 UTC} |

*If no records closed: "No Henkaten records were closed in this sprint."*

---

## Yokoten Propagation

*Populated for each Henkaten record closed above. The Orchestrator reads these
fields during Step 1A.5 (Yokoten Review) of subsequent sprints.*

### HK-{NNNN}

```yaml
yokoten:
  applicable_to_subsequent_sprints: [NN+1, NN+2]   # or ["all"] for universal lessons
  adaptation_notes: >
    {Concise starting point for the adaptation prompt at future sprints.
    The user drafts the actual adaptation during Step 1A.5 — this field is
    the agent's suggested starting point only.}
```

**`applicable_to_subsequent_sprints`** — list of future sprint numbers that
should receive this learning as an adaptation prompt, or `["all"]` for
universal lessons. The ratify-once shortcut (v2.1 A9) applies when the value
is `["all"]` or contains ≥3 sprint numbers.

**`adaptation_notes`** — the agent-suggested starting point for the
adaptation. The user finalizes the adaptation text during council-autorun
Step 1A.5.

*If no Henkaten records were closed, this section is omitted.*

---

## Coverage

*Files and data sources read during this retrospective. Note anything
unavailable within the 30s time budget.*

- `.harness/sprint-state.json` — available | unavailable
- `.harness/contracts/sprint-{NN}.md` — available | unavailable
- `.harness/evals/sprint-{NN}-r{R}.md` — available | unavailable
- `.council/henka-register.jsonl` — available | unavailable

---

*Note: No standard-work proposals are included in this mini retrospective.
Mini mode is capture-only. Findings that suggest process changes are deferred
to the next pdca cycle (`/henkaten-council:council-retro`).*
