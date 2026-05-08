# Dispatch Envelope — Agent Dispatch Template

This template is the **single source of truth** for all agent dispatches in
the henka-council system. Every time the Orchestrator invokes a council agent
via `Task`, the dispatch MUST follow this structure.

---

## Dispatch Rules

### Rule 1 — Orchestrator Only

Only the Orchestrator may call `Task` to dispatch agents. No skill may call
another skill via `Task`. No worker agent (architect, scope-guardian,
henkaten-detector, retrospective, qa-regression, rag-source) may call `Task`
to invoke another agent. This rule implements Rule 4 (Bounded Self-Organization).

The orchestrator dispatches; all others return text output.

### Rule 2 — File Paths and Constraints Only

The Orchestrator passes ONLY file paths and structured constraints to
subagents. The Orchestrator MUST NOT pass:
- Its own internal reasoning or conclusions
- Summaries of previous agents' outputs (let each agent read files directly)
- Pre-analyzed findings (agents perform their own analysis)
- Hints about what classification to reach

Each agent reads the source files independently. This is the genchi-genbutsu
(現地現物) principle applied to agent dispatch: the agent goes to the source
directly, not through the orchestrator's interpretation.

### Rule 3 — Inherited Obligations

Every dispatched agent inherits andon authority and genchi-genbutsu obligations
via these instruction cross-references:

- `instructions/andon-protocol.md` — the agent may issue `andon_signal: alert`
  or `andon_signal: stop` at any time; the orchestrator MUST honor both
- `instructions/evidence-first.md` — every `observed` claim requires a
  conformant `verification` command; `evidence_class` and `confidence` are
  required on every claim

These obligations are NOT optional. The Orchestrator will reject agent outputs
that omit them.

---

## Dispatch Template

```
Task(
    subagent_type="henka-council:<agent-name>",
    description="<Agent Role> review for sprint {NN}",
    prompt="""You are the <Agent Name> agent. <One-line role summary>.

Inputs (read-only):
- <list of file paths the agent should read>

Task:
<Structured description of the specific task — what to analyze, what to
produce, what scope to cover. Written as file paths and structured constraints,
not conclusions or pre-analysis.>

Output format:
<Describe the expected output sections — e.g., Coherence Rating, Drift
Indicators, etc. Reference the agent's contract file for full output spec.>

Common obligations (inherited):
- DO NOT modify any files.
- DO NOT invoke other agents directly.
- Cite specific evidence for every claim (observed / inferred / speculative).
- For every `observed` claim, include a re-runnable `verification` command
  conforming to the allowlist in instructions/evidence-first.md.
- Include `evidence_class` and `confidence` on every claim.
- You MAY issue an `andon_signal: alert | stop` if you detect a blocking
  condition; include `swarm_request` if relevant other agents should swarm.
  See instructions/andon-protocol.md for the required signal structure.
- Include a `coverage` section listing files read, files missing, and any
  verification commands not executed.
"""
)
```

---

## Concrete Example — Architect Dispatch

```
Task(
    subagent_type="henka-council:architect",
    description="Architect coherence review for sprint 02",
    prompt="""You are the Architect agent. Coherence and drift reviewer.

Inputs (read-only):
- .harness/sprint-state.json
- .harness/evals/sprint-02-r1.md
- .harness/contracts/sprint-02.md
- .harness/spec.md
- .harness/features.json
- .harness/sprints.json
- agents/ directory (last-touched source structure)

Task:
Assess coherence between the Sprint 02 contract and what was delivered.
Identify drift indicators with verification commands. Check dependency health
for Sprint 03. Flag any blocking conditions.

Output format:
Coherence Rating (1-5), Drift Indicators (with verification), Dependency
Health, Proposed Amendments, Risk Flags. See agents/architect.md for full spec.

Common obligations (inherited):
- DO NOT modify any files.
- DO NOT invoke other agents directly.
- Cite specific evidence for every claim (observed / inferred / speculative).
- For every `observed` claim, include a re-runnable `verification` command
  conforming to the allowlist in instructions/evidence-first.md.
- Include `evidence_class` and `confidence` on every claim.
- You MAY issue an `andon_signal: alert | stop` if you detect a blocking
  condition; include `swarm_request` if relevant agents should swarm.
  See instructions/andon-protocol.md for the required signal structure.
- Include a `coverage` section listing files read, files missing, and any
  verification commands not executed.
"""
)
```

---

## Swarm Dispatch Variant

When an `andon_signal: alert` triggers the swarming protocol, swarm dispatches
use the same template but are issued as **parallel `Task` calls**:

- All swarm agents are dispatched simultaneously (regardless of `dispatch_mode`
  for routine fan-out).
- The swarm includes: the originating agent + any agents named in
  `swarm_request` (total ≤4 agents).
- The dispatch prompt includes the originating agent's `andon_signal` as
  a structured constraint (not as the Orchestrator's analysis).
- Resolution window: 10 minutes wall-clock (`andon_takt_seconds`).

Example swarm constraint to include:

```
Swarm context:
- Triggered by: andon_signal: alert from architect agent
- Reason: [verbatim reason from the signal]
- Evidence: [verbatim evidence references from the signal]
- Your task: independently assess this condition and recommend resolution.
```

---

## Dispatch Checklist

Before every `Task` call:

- [ ] Only the Orchestrator is calling `Task` (not a worker agent or skill).
- [ ] The prompt contains ONLY file paths and structured constraints.
- [ ] No internal reasoning, pre-analysis, or hints about expected output.
- [ ] The common obligations block is included verbatim.
- [ ] References to `instructions/andon-protocol.md` and
      `instructions/evidence-first.md` are present in the prompt.
- [ ] `subagent_type` matches the agent's contract file name.
