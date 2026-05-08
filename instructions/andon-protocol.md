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

---

## Pull-Rate Tracking Reference

The orchestrator tracks pull-rate (andon signal frequency) per agent in
`audit-log.jsonl`. Each `PostToolUse` hook entry records the agent ID and
signal type when an `andon_signal` is present in the agent's output.

- **Normal pull-rate:** informational.
- **Anomalous pull-rate:** same agent issuing three or more consecutive
  `stop` signals without resolution is flagged as `quality-defect-anomaly`
  Henkaten (not a floor-drop trigger per §2.4.3 corroboration requirement).
- **Floor-drop trigger:** three `stop` signals from **at least 2 distinct
  originator agents** (see §2.4.3 for the full dynamic-autonomy-floor rules).

Pull-rate anomalies do not suppress the agent's future signals — they are
logged and surfaced to the user as a pattern observation during the next
retrospective.

---

## Summary Checklist for Orchestrator

When any `andon_signal` arrives:

- [ ] Write thank-the-puller acknowledgment ("Thank you for stopping the line…")
      verbatim BEFORE any other response.
- [ ] For `stop`: halt immediately, present halt evidence, wait for user.
- [ ] For `alert`: dispatch swarm (parallel, ≤4 agents, takt-bounded 10 min).
- [ ] Do NOT filter, defer, or second-guess any signal.
- [ ] Log pull-rate entry in audit-log.
- [ ] If `alert` times out: escalate to `stop`.
