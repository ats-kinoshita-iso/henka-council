# Andon Protocol — Behavioral Instructions

Every council agent may issue an andon signal in its output. This instruction
file defines the mandatory behaviors that both the issuing agent and the
orchestrator must observe whenever an andon signal is present.

---

## Andon Signal Structure

Every andon signal MUST be a JSON object with the following fields:

```json
{
  "andon_signal": {
    "type": "alert" | "stop",
    "reason": "concise statement of what triggered the signal",
    "evidence": ["file:line or command output references"],
    "swarm_request": ["agent_id_1", "agent_id_2"]
  }
}
```

- `type` — required; either `"alert"` (recoverable) or `"stop"` (committed halt)
- `reason` — required; one-sentence statement of the triggering condition
- `evidence` — required array; at minimum one file:line or re-runnable command reference
- `swarm_request` — optional array of agent IDs whose perspective is needed

An agent that detects a blocking or high-risk condition MUST include an
`andon_signal` in its response. An agent that detects an actionable condition
MAY include an `andon_signal: alert` to request a swarm.

---

## Thank-the-Puller Acknowledgment (mandatory)

When the orchestrator receives any `andon_signal` — whether `type: "alert"` or
`type: "stop"` — it MUST write a thank-the-puller acknowledgment to the
escalating agent **verbatim BEFORE any analytical response**. This step is
non-negotiable and must not be deferred, abbreviated, or skipped.

Required verbatim text:

> "Thank you for stopping the line. Your signal has been received and will be
> honored. No further sprint steps will proceed until this is resolved."

This acknowledgment is logged in the audit trail under the agent's ID.
Pull-rate per agent is tracked in `audit-log.jsonl`; anomalously high
pull-rates (same agent repeatedly issuing stops) are flagged as a
`quality-defect-anomaly` Henkaten — NOT as a valid floor-drop trigger. See
§2.4.3 for the corroboration requirement.

---

## Alert vs Stop

### `andon_signal: alert` — Recoverable Escalation

An `alert` means the detecting agent believes the issue is solvable but needs
corroboration or additional analysis before the sprint can proceed safely.

**Orchestrator behavior on `alert`:**

1. Write the thank-the-puller acknowledgment immediately.
2. **Pause the sprint loop** — do not proceed to the next step.
3. Dispatch the **swarm**:
   - The originating agent is always included.
   - Any agents named in `swarm_request` are added (total capped at **4 agents**).
   - Swarm dispatches are **parallel Task calls** regardless of the
     `dispatch_mode` setting for routine fan-out. Rationale: swarming is the
     latency-sensitive case where parallel dispatch fits within the takt budget.
4. **Resolution window:** default **10 minutes wall-clock** (`andon_takt_seconds`
   in `.council/config.json`; v2.1 default raised from 5 to 10 minutes to fit
   four-agent sequential dispatch budget).
5. **If resolved within the takt bound:** sprint resumes with a logged decision.
   Decision-log entry includes `andon_resolution: {originator, swarm, resolution,
   duration_seconds}`.
6. **If NOT resolved within the takt bound:** the `alert` automatically
   **escalates to `stop`**. Orchestrator jumps to Step 1F (Halt Conditions Check).

### `andon_signal: stop` — Committed Halt

A `stop` means the detecting agent has determined the sprint cannot safely
proceed. This is a committed signal, not a request.

**Orchestrator behavior on `stop`:**

1. Write the thank-the-puller acknowledgment **immediately, before any analysis**.
2. **Immediately halt the sprint loop** — no further fan-out, no course
   correction, no decision-logging beyond the halt entry.
3. Present the halt reason and evidence to the user.
4. Wait for explicit `/council-review` invocation to restart. The sprint does
   not auto-resume.

---

## Andon Stop vs No-Progress vs Resource-Cap (MUST NOT conflate)

Loops in this system can terminate for three structurally distinct reasons,
each of which has its own `response_type` value on the closing henka-record
(`schemas/henka-record.schema.json`). The three MUST NOT be conflated in
audit data, because they encode different things about who decided the loop
should stop and why.

### `andon-stop` — agent-detected safety anomaly

The agent has observed a condition that makes proceeding unsafe — a
contradiction, a corrupted artefact, a verification divergence, a scope
violation, anything that triggers jidoka. This is the case the existing
andon protocol covers above. The agent issues `andon_signal: stop`, the
Orchestrator honors it unconditionally, and the closing henka-record uses
`response_type: "andon-stop"`. The decision to stop is the agent's call;
the trigger is a specific observable defect.

### `no-progress` — agent's own metacognitive judgment

The agent has tried two or three distinct approaches at the same blocker
and observed that none of them advanced the state on the declared
objective. Nothing is unsafe; nothing is contradictory; the agent simply
judges that further attempts are not productive. The closing henka-record
uses `response_type: "no-progress"` and MUST carry a non-empty `attempts`
array enumerating each approach tried and why it did not advance.

`no-progress` is distinct from `andon-stop` because there is no anomaly
being flagged — only the agent's calibrated judgment about its own
forward motion. The Orchestrator does NOT issue the thank-the-puller
acknowledgment on `no-progress`; the acknowledgment is reserved for the
safety-critical andon path. The Orchestrator records the no-progress
henka-record and closes the loop's decision-log entry with
`decision_outcome: "halted"`.

### `resource-cap` — harness-imposed limit

A technical limit has fired regardless of what any agent is judging:
takt-window expiry (`andon_takt_seconds`), nemawashi-revision iteration
cap (default 2 cycles in Stage 3), context-window exhaustion, token
budget, time budget. The Orchestrator on behalf of the harness writes a
henka-record with `response_type: "resource-cap"` and closes the loop's
decision-log entry with `decision_outcome: "halted"`. No agent judgment
is captured here; the cap fired and the loop ended.

If an agent believed it was about to succeed when a resource cap fired,
that is a calibration signal for the cap, not a reason to override it.
Resource caps are the harness's safety net, not its preference.

### Encoded by authorship

The agent-vs-harness distinction is encoded by who writes the record:

- `andon-stop` and `no-progress` are written by **agents** (henkaten-
  detector, architect, scope-guardian, retrospective, etc.) reporting
  their own observations and judgments.
- `resource-cap` is written by the **Orchestrator** on the harness's
  behalf when a technical limit fires.

Audit reviewers reading the henka-register can immediately distinguish
agent decisions from harness-imposed terminations by inspecting both
`response_type` and `detected_by_agent`. Conflating the three types
destroys this signal.

See `@instructions/stop-conditions.md` for the full five-form taxonomy
(success / failure / no-progress / resource-cap / interrupt).

---

## Rule 4 Carve-Out (v2.1 Amendment A10)

**Rule 4 — Bounded Self-Organization** states that agents may flag the need for
another perspective via `swarm_request`, but the **orchestrator decides**
whether to invoke additional agents. No agent invokes another directly.

**However: `andon_signal: stop` is mandatory and bypasses Rule 4.**

- `stop` signals are not suggestions — they are immediate halts.
- The orchestrator **MUST NOT** defer, filter, delay, or second-guess a `stop`
  signal for any reason, including nominal autonomy level or sprint urgency.
- `stop` is a jidoka (自働化) mechanism: the authority to halt is distributed
  to every agent precisely so that no single agent's judgment bottleneck can
  let a defect propagate.

Rule 4 governs `swarm_request` (suggestive — the orchestrator decides the
composition). Rule 4 does **not** govern `stop` (mandatory — the orchestrator
honors it unconditionally). This carve-out is explicit and non-negotiable.

### Rule 4 — Human-Level-5 Arbitration Exception

There is one narrow exception where the orchestrator does **not** execute an
unconditional halt, even when a `stop` signal is present: when the stop signal
**directly contradicts an active Level-5 (human-approved) decision**.

**Definition:** A Level-5 approved decision is any action that has passed the
nemawashi walkthrough and received explicit human approval, creating a record in
`decision-log.jsonl` with `user_approval_required: true` and a non-null
`nemawashi_walkthrough_version`. This approval represents the highest authority
in the council system.

**Conflict detection:** If a `stop` signal's `reason` field identifies the
Level-5 approved decision as the trigger (e.g., "stopping because the approved
correction to `spec.md` violates scope"), the orchestrator MUST NOT auto-halt.
Instead:

1. Write the thank-the-puller acknowledgment verbatim (this step is never
   skipped, even in the arbitration path).
2. Surface the conflict to the human reviewer with the following information:
   - The Level-5 DEC entry that is in conflict (DEC-NNNN, timestamp, outcome)
   - The agent's `andon_signal` reason and evidence verbatim
   - A request for explicit arbitration before any action proceeds
3. Suspend the sprint loop pending the human reviewer's instruction.
4. Log a `DEC` entry with `decision_type: "andon-level5-conflict"` and
   `applied_automatically: false`.

**Rationale:** A single agent must not be able to unilaterally override a human
approval by issuing a `stop` signal. The andon mechanism is for quality
assurance, not for vetoing human decisions. When the two conflict, human
arbitration is required rather than automatic halt.

This exception does NOT apply when the stop signal is about a different concern
than the Level-5 decision. In that case the normal unconditional halt applies.

---

## Pull-Rate Tracking Reference

The orchestrator tracks pull-rate (andon signal frequency) per agent in
`audit-log.jsonl`. Each `PostToolUse` hook entry records the agent ID and
signal type when an `andon_signal` is present in the agent's output.

### Pull-Rate Counting and Weighting

Both signal types count toward an agent's pull-rate, weighted differently:

- `andon_signal: stop` — weight **2** (committed halt; higher cost)
- `andon_signal: alert` — weight **1** (non-blocking escalation; lower cost)

The orchestrator maintains a running weighted score per agent per sprint and
per rolling 60-minute window.

### Anomaly Thresholds

| Threshold | Window | Action |
|---|---|---|
| Weighted score ≥ 3 (raw count) | Single sprint | Flag as `quality-defect-anomaly` Henkaten |
| Weighted score ≥ 5 | Rolling 60 minutes | Flag as `quality-defect-anomaly` Henkaten |

When either threshold is crossed:

1. A Henkaten record is appended with `change_type: "agent-capability-change"`,
   `fourM_axis: "Machine"`, `change_origin: "active"`, and the agent ID.
2. The anomaly is surfaced to the user at the next retrospective.
3. The agent's future signals are **not suppressed** — they continue to be
   honored per normal protocol.

### What Anomalous Pull-Rate Is NOT

An anomalously high pull-rate from a single agent is **not** a floor-drop
trigger. It is tracked as a quality-defect-anomaly for pattern recognition and
human awareness — not as an indication that the autonomy floor should change.

- **Normal pull-rate:** informational; logged to `audit-log.jsonl`.
- **Anomalous pull-rate:** flagged as `quality-defect-anomaly` Henkaten (not
  a floor-drop trigger per §2.4.3 distinct-originator corroboration requirement).
- **Floor-drop trigger:** three `stop` signals from **at least 2 distinct
  originator agents** (see §2.4.3 for the full dynamic-autonomy-floor rules).

Pull-rate anomalies do not suppress the agent's future signals — they are
logged and surfaced to the user as a pattern observation during the next
retrospective.

---

## Distinct-Originator Corroboration (§2.4.3 / v2.1 Amendment A2)

The dynamic autonomy floor drops ONLY when the corroboration requirement is met.
This section cross-references §2.4.3 so that andon-protocol.md is self-contained.

**Corroboration rule:** a floor drop requires **≥2 distinct originator agents**
each independently issuing an `andon_signal: stop` on the same underlying issue
within the current sprint loop.

- "Distinct" means different agent IDs. The same agent issuing two or more
  consecutive stops counts as **one originator**, not two.
- "Same underlying issue" is determined by the orchestrator based on the
  `reason` and `evidence` fields of each stop signal.

**Same-agent repeated stops:** tracked as pull-rate anomaly
(`quality-defect-anomaly` Henkaten, `change_type: agent-capability-change`) —
NOT as a floor-drop trigger.

**Cross-originator corroboration:** when two distinct agents stop on the same
issue, the third distinct stop from any originator within the same sprint loop
triggers the floor drop. The orchestrator calls
`scripts/update-effective-autonomy.py` with the new level and the triggering
stop signals as evidence.

**Example:**
- `henkaten-detector` issues `stop` → 1 originator; no floor change.
- `architect` issues `stop` on the same issue → 2 distinct originators;
  if this is the third `stop` total for the sprint, floor drops.
- `henkaten-detector` issues a second `stop` on the same issue → still 1
  unique originator for `henkaten-detector`; pull-rate anomaly only.

---

## Resolution and Resume

When a `stop` signal is issued, the sprint loop halts completely. It does not
auto-resume. The following steps govern resolution:

### Resolution Sequence

1. **Human reviewer** examines the halt reason and evidence presented by the
   orchestrator.
2. **Swarm (optional):** if the stop signal included a `swarm_request`, the
   orchestrator may dispatch the named agents for analysis after the
   acknowledgment step.
3. **Resolution:** the human reviewer (or swarm consensus with human sign-off)
   determines that the blocking condition is resolved.
4. **Resume signal:** the originating agent must confirm via a follow-up
   signal in its next output:

```json
{
  "andon_signal": {
    "type": "resume",
    "original_stop_reason": "original stop reason here",
    "resolution_summary": "concise statement of how the issue was resolved",
    "confirmed_by": "agent_id"
  }
}
```

5. **Decision-log entry:** the orchestrator appends a record to
   `decision-log.jsonl` (via `scripts/append-decision.py`) with:
   - `decision_type: "andon-resolution"`
   - `decision_outcome: "applied"` (or `"halted"` if unresolved). The
     `andon_resolution` sub-object on the same entry carries the
     resolution-specific outcome: `andon_resolution.resolution` is one of
     `"resumed"`, `"escalated_to_stop"`, or `"user_intervention"` per
     `schemas/decision-log-entry.schema.json`.
   - `council_agents_involved`: [originating agent, any swarm members]
   - `evidence_cited`: the original stop evidence plus resolution evidence
   - `applied_automatically: false`
   - `user_approval_required: true`

6. **Sprint resumes** only after the decision-log entry is written and the
   user has explicitly invoked `/council-review` to restart the loop.

### Unresolved Stops

If a stop cannot be resolved (the blocking condition persists), the decision-log
entry uses `decision_outcome: "halted"` (per `schemas/decision-log-entry.schema.json`)
and the sprint is abandoned. The Orchestrator surfaces the halt evidence in its
final response. A new sprint must be initiated from scratch; the autorun loop
does not retry halted sprints automatically.

---

## Summary Checklist for Orchestrator

When any `andon_signal` arrives:

- [ ] Write thank-the-puller acknowledgment ("Thank you for stopping the line…")
      verbatim BEFORE any other response. This applies to ALL signal types
      (alert, stop, and the Level-5 arbitration path).
- [ ] For `stop`: halt immediately, present halt evidence, wait for user.
      Exception: if stop contradicts an active Level-5 decision, surface
      conflict to human reviewer for arbitration (Rule 4 carve-out) — still
      write acknowledgment first.
- [ ] For `alert`: dispatch swarm (parallel, ≤4 agents, takt-bounded 10 min).
- [ ] Do NOT filter, defer, or second-guess any signal.
- [ ] Increment pull-rate counter in `audit-log.jsonl` for the issuing agent
      (weight 2 for stop, weight 1 for alert). Check anomaly thresholds.
- [ ] If `alert` times out: escalate to `stop`.
- [ ] On resolution: wait for originating agent's `resume` signal, then
      append `andon-resolution` entry to `decision-log.jsonl` via
      `scripts/append-decision.py`.
- [ ] Check distinct-originator count (§2.4.3 / A2): if ≥2 distinct agents
      have stopped on the same issue and total stop count ≥ 3, call
      `scripts/update-effective-autonomy.py` to drop the floor.
