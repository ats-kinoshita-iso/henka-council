# Stop Conditions — Behavioral Instructions

Every council loop terminates for some reason. This instruction defines the
five canonical termination forms, the audit-data encoding for each, and the
non-negotiable rules against conflating them. Cross-references the andon
protocol (`@instructions/andon-protocol.md`) and the henka-record schema
(`schemas/henka-record.schema.json`).

---

## The Five Forms

A loop in this system terminates in exactly one of five forms. Each form has
a distinct audit-data encoding so that a future reviewer can reconstruct who
decided the loop should stop and why.

### 1. Success

The loop's declared success criterion was met. The closing decision-log
entry records `decision_outcome: "applied"` (the work was applied) along
with the affected files and evidence. No special henka-record is required
unless the success path itself generated a change-point worth recording.

### 2. Failure

The loop's declared failure criterion was met, triggering the loop's
rollback step. The closing decision-log entry records
`decision_outcome: "rejected"` or `decision_outcome: "halted"` depending on
whether the failure is recoverable. A henka-record may be appended to
capture the failure mode for later yokoten propagation.

### 3. No-Progress (agent metacognition)

The agent running the loop judges that it cannot advance on the declared
objective after two or three distinct attempts at the same blocker. The
closing henka-record uses `response_type: "no-progress"` and MUST carry a
non-empty `attempts` array enumerating each approach tried and the reason
it did not advance the state. The closing decision-log entry uses
`decision_outcome: "halted"` and links the henka-record via `linked_henka_id`.

`no-progress` is the agent's own metacognitive judgment, not an external
iteration counter. The harness does NOT impose how-many-tries-is-enough as
a policy. The agent's calibration is the leverage; recording the attempts
preserves the calibration for review.

**Distinct from andon-stop:** no-progress signals no defect or anomaly —
only the agent's judgment that further attempts are not productive. No
thank-the-puller acknowledgment is required.

### 4. Resource-Cap (harness-imposed limit)

A technical limit fires regardless of agent judgment. Common limits:

- **Takt-window expiry** — `andon_takt_seconds` (default 600s for alert
  resolution; configurable in `.council/config.json`).
- **Nemawashi iteration cap** — Stage 3 of the nemawashi walkthrough is
  bounded to 2 revision cycles by default; exceeding triggers an
  `escalated-to-user` outcome under the existing walkthrough machinery,
  which is functionally a resource-cap.
- **Context-window exhaustion** — the working context is full; further
  loop progress is impossible.
- **Token budget** or **time budget** — set per-loop or globally.

The Orchestrator on behalf of the harness writes the closing henka-record
with `response_type: "resource-cap"`. The closing decision-log entry uses
`decision_outcome: "halted"`. No agent judgment is captured here — the cap
fired and the loop ended.

**Distinct from no-progress:** the agent is not deciding. The harness is.
If an agent believed it was about to succeed when a resource cap fired,
that is a calibration signal for the cap, not a reason to override it.

### 5. Interrupt (human or system policy)

A human collaborator or an external system policy explicitly stops the
loop. The Orchestrator writes a henka-record with
`response_type: "andon-stop"` (the existing safety-critical halt path —
human intervention is treated as a special case of stop) and a closing
decision-log entry with `decision_outcome: "halted"`. The
`council_agents_involved` field records the human reviewer where
identifiable.

---

## Agent-vs-Harness Encoding via Authorship

The author of the closing henka-record encodes the agent-vs-harness
distinction:

| Termination form | Henka-record `response_type` | Typical author |
|---|---|---|
| Success | (none required) or normal change-point | — |
| Failure | (variable, depending on failure mode) | agent |
| No-progress | `"no-progress"` (with `attempts[]`) | the loop-running agent |
| Resource-cap | `"resource-cap"` | Orchestrator on behalf of harness |
| Interrupt | `"andon-stop"` (or `"escalate"` for soft interrupts) | the agent that detected the interrupt |

A future reviewer reading `henka-register.jsonl` distinguishes agent
decisions from harness-imposed terminations by inspecting both
`response_type` and `detected_by_agent`. Conflating these in audit data
destroys the signal and is a violation of audit-trail discipline.

---

## Why Termination-Reason Lives on Henka-Record

The architectural decision (see `docs/design/adr-0004-stop-conditions.md`):

A termination reason is fundamentally a metacognitive observation about
the loop. Henka-records are the change-point register where observations
live; their `response_type` field already classifies how a change-point
should be handled. Extending `response_type` to include `no-progress` and
`resource-cap` keeps the termination-reason data in the agent-observation
domain where it is generated.

The decision-log entry that closes the loop references the henka-record
via `linked_henka_id` (already present in the decision-log schema). The
decision-log itself uses the broadened `decision_outcome` enum (with
`"halted"` for terminated loops) but does not carry a parallel
termination-reason taxonomy.

This avoids two parallel taxonomies that would inevitably drift apart,
and keeps the audit chain linear: read the closing decision-log entry,
follow `linked_henka_id` to the closing henka-record, read
`response_type` and any `attempts[]` for the precise termination
encoding.

---

## What the Orchestrator MUST Do at Loop Termination

When closing any loop that did not terminate in plain `success`:

1. **Append the closing henka-record** via `scripts/append-henka.py` with
   the correct `response_type` for the termination form, the relevant
   evidence, and (for `no-progress`) the non-empty `attempts[]` array.
2. **Append the closing decision-log entry** via
   `scripts/append-decision.py` with `decision_outcome: "halted"`,
   `linked_henka_id` pointing at the henka-record from step 1, and a
   `description` summarising the cause.
3. **Surface the termination to the user** with the henka-record ID and
   the decision-log entry ID, so the audit chain is immediately
   navigable.

The closing pair (henka-record + decision-log entry) is the audit
artefact for the termination. Without it, the loop is silently abandoned
and the audit trail breaks.

---

## Common Mis-Codings (avoid these)

- **No-progress recorded as andon-stop.** The agent is not flagging a
  safety anomaly; it is reporting calibrated metacognition. Use
  `"no-progress"` with `attempts[]`.
- **Resource-cap recorded as no-progress.** The agent was not the one
  who decided to stop; the harness was. Use `"resource-cap"`.
- **Interrupt recorded as failure.** A human telling the agent to stop
  is not the loop's declared failure criterion firing. Use
  `"andon-stop"` (interrupts are a kind of stop, just one with a
  different originator) and note the human reviewer in
  `council_agents_involved`.
- **Decision-log entry with `decision_outcome: "halted"` and no
  `linked_henka_id`.** A halt without a henka-record describing why is
  an audit-trail break. The two records are written together.

When in doubt, ask: *who decided the loop should stop?*

- Agent observed a defect → `andon-stop`
- Agent judged forward motion was lost → `no-progress`
- Harness ran out of budget → `resource-cap`
- Human or external policy → `andon-stop` (with human reviewer noted)
- Declared success criterion met → no termination henka-record needed
- Declared failure criterion met → loop's own failure handling
