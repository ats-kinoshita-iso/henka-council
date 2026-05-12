# Discovery Gate — Design Proposal

**Status:** Draft for review
**Date:** 2026-05-08
**Author:** Discovery-gate design pass against the Sprint 1+2 baseline of `claude/vibrant-chandrasekhar-cfc3f8`
**Scope:** Defines an upstream gated phase — Spec Construction, Constraint Extraction, Acceptance-Criteria Definition — that runs *before* architecting and implementation begin on any new initiative. Output is a design document only; no production paths are touched.

---

## 1. Purpose and Frame

The henka-council currently engages *during* sprint execution. `/council-kickoff` ([skills/council-kickoff/SKILL.md:24-34](skills/council-kickoff/SKILL.md)) bootstraps `.council/` state and delegates to `/trine-eval:harness-kickoff`, which produces `.harness/spec.md`, `features.json`, and `sprints.json`. From there `/council-autorun` enters the per-sprint loop ([.harness/spec.md §3.1](.harness/spec.md)). The council reviews **execution**; nothing reviews the **planning artifacts**.

That is a missing station on the line. Jidoka (自働化) means the line stops on abnormality at every station — yet if the spec, constraints, or criteria are themselves defective, the defect propagates into architecture and implementation before any agent has authority to halt. The first agent that *could* halt is several stations downstream of where the defect originated.

This document proposes a **Discovery Gate**: an upstream station that classifies the *planning package* (spec + constraint catalog + acceptance criteria) as fit-to-pass, fit-with-notes, requires-revision, or human-escalate. The council enters at the *end* of the three discovery activities — not during them — to assess whether the package is ready to advance. The activities are operator-led: humans drive them, optionally assisted by upstream **producer agents** (e.g. a Spec Exploration interview agent) whose role is to help the human author the artifacts. Producer agents are out of scope for this document; the gate reviews the package they hand off, regardless of which mix of human and agent authorship produced it.

The gate makes three things explicit that are currently implicit: what the council knows about the work before it begins; what re-review is owed when planning changes mid-flight ([instructions/human-approval.md:36-40](instructions/human-approval.md) currently flags such edits as Henkaten but has no path to re-validate the package); and what "passing" looks like at the package level (the seven pillars apply to package-level review naturally — spec is genbutsu, constraints are poka-yoke, criteria are jidoka stop-conditions in operational form). It is a natural extension of the existing pattern, not a parallel system.

---

## 3. Council Composition for the Gate

**Decision: a specialised variant of henka-council, reusing the existing orchestrator framework with gate-specific reviewer agents.**

Reusing the four default agents as-is is rejected: their evidence priorities are tuned for sprint-cycle review (coherence drift, feature-integrity, change classification), and forcing spec-package framings onto them weakens both the gate and the existing per-sprint review. Composing a parallel council is rejected: the pattern (Level 4 orchestrator + Level 1–2 workers + dispatch envelope + andon + nemawashi) is reusable, and duplicating it produces protocol drift. The specialised-variant choice keeps the same orchestrator and the same andon and evidence rules ([agents/orchestrator.md:64-95](agents/orchestrator.md), [instructions/andon-protocol.md](instructions/andon-protocol.md), [instructions/evidence-first.md](instructions/evidence-first.md)) and changes only the worker roster and the artifact under review.

### Proposed roster

The gate council is composed of **reviewers**, distinct from the **producer agents** that may have helped author the package upstream (§1). A producer agent (e.g. Spec Exploration) writes drafts with the human; a reviewer reads the resulting package and judges fitness. The same human or a different one may be in the loop for both, but the obligations differ — producers operate under interview discipline (one question at a time, surface assumptions, defer where possible), reviewers operate under the council's standing obligations (andon authority, genchi-genbutsu verification, nemawashi for synthesis). No agent occupies both roles in a single gate run; that would collapse the steelman/adversary tension the gate depends on.

The gate council assembles:

| Agent | Level | Context | Role | New or Reused |
|---|---|---|---|---|
| `gate-orchestrator` | 4 | inherit | Same six obligations as the autorun orchestrator ([agents/orchestrator.md:64-156](agents/orchestrator.md)). Differs only in dispatch roster and the artifact under review. | New file, thin shim over `orchestrator.md` |
| `spec-specialist` | 2 | fork | Steelmans the spec. Reads it as the genbutsu — the actual thing — and asserts it is precise enough for downstream stations to act on without ambiguity. | New |
| `constraint-extractor` | 2 | fork | Adversary framing. Enumerates regulatory, organizational, architectural, philosophical, and resource constraints. Surfaces any constraint that would make a candidate architecture infeasible. | New |
| `criteria-architect` | 2 | fork | Adjudicator framing. Translates spec into observable acceptance signals; rejects criteria that are not measurable or observable. | New |
| `henkaten-detector` (gate mode) | 1 | fork | Reused. Projects what might change after the gate passes — inputs the gate cannot fix, only flag. Uses 4M lens ([.harness/spec.md §6](.harness/spec.md)). | Reused with mode flag |
| `architect` (gate mode) | 2 | fork | Reused. Coherence rating across the *three artifacts together* — does the spec, constraint catalog, and criteria set form an internally consistent package? Drafts the nemawashi position paper at gate-pass. | Reused with mode flag |

Five workers exceeds the routine fan-out cap of four ([agents/orchestrator.md:172-173](agents/orchestrator.md)), so the gate runs in **two waves**: wave 1 = `spec-specialist`, `constraint-extractor`, `criteria-architect`, `henkaten-detector`; wave 2 = `architect` synthesizes wave-1 outputs. The two-wave pattern preserves the bounded-fan-out invariant and gives `architect` a coherent set of evidence to synthesize from rather than asking five agents to vote on each other's territory.

The retrospective agent is *not* in the gate roster. The gate is forward-looking; retrospective work belongs to `/council-retro` after sprints have produced data ([.harness/spec.md §3.1](.harness/spec.md)).

---

## 4. Review Framings × TPS Mapping

Each gate reviewer has a distinct framing tied to a TPS pillar. The mapping is structural — the framing defines what evidence the reviewer collects and what failure modes it watches for.

| Reviewer | Framing | TPS Pillar | What this reviewer must produce |
|---|---|---|---|
| `spec-specialist` | **Steelman** — read the spec as if you wrote it; the strongest possible interpretation. | Pillar 3 — **Genchi genbutsu**. The spec is the genbutsu; every spec claim must trace to a re-runnable observation (an interview note path, a domain document, a measurement) using the verification syntax allowlist ([.harness/spec.md §4.5](.harness/spec.md)). | A `spec-coherence-rating: 1–5` with drift indicators per ambiguous passage; for each ambiguity, a `verification` command producing the source quote. |
| `constraint-extractor` | **Adversary** — enumerate every way the work could fail to respect the boundaries; assume nothing. | Pillar 5 — **Poka-yoke**. Constraints are design-time error elimination. A constraint surfaced before architecting prevents architecture from being proposed inside an infeasible space. | A constraint catalog (see §7) with `category: regulatory \| organizational \| architectural \| philosophical \| resource`, `source` (cited), `binding` (hard\|soft), `verification`. |
| `criteria-architect` | **Adjudicator** — define what "done and good" looks like in observable form. | Pillar 2 — **Jidoka**. Acceptance criteria are the conditions under which the line should *not* stop; their negation is the stop-condition. Criteria that are not measurable or observable cannot be jidoka triggers. | An acceptance-criteria set with `id`, `criterion`, `measurement_or_observation` (re-runnable command or stable observation procedure), `weight`, `binding` flag. |
| `henkaten-detector` (gate mode) | **Forecaster** — project change-points the gate cannot fix. | Pillar 1 — **DETECT**. Active-vs-passive distinction ([supplement R1](docs/phase-0-proposal-supplement.md)) is critical here: at gate-time, *every* identified change-point is `change_origin: passive` (it has not yet happened); the question is which axis (Man / Machine / Material / Method) is most exposed. | A pre-emptive Henkaten projection: 4M-classified open risks the gate package cannot resolve, each with an `early-warning` re-entry trigger (see §6). |
| `architect` (gate mode) | **Synthesizer** — coherence across the package; drafter of the nemawashi position paper. | Pillar 4 — **Nemawashi**. The package itself is a position paper; the gate-pass walkthrough *is* nemawashi for the entire planning artifact, not for a single decision. | The position paper at `.council/proposed/GATE-{NNNN}.md`, framed as the canonical four-stage walkthrough ([instructions/human-approval.md §44-114](instructions/human-approval.md)). |

Two framings deliberately conflict: `spec-specialist` is a steelman; `constraint-extractor` is an adversary. The gate expects them to disagree, and surfaces the disagreement to the architect for synthesis. This conflict is by design; consensus that emerges *through* disagreement is the nemawashi pattern, not the absence of it.

---

## 5. Decision States and Outputs

The gate produces one of four decision states. Each state has a defined output artifact and a defined trigger.

| State | Trigger | Output | Downstream effect |
|---|---|---|---|
| **PASS** | Architect synthesis: package is coherent; all hard constraints have evidence; every criterion is measurable or observable; no `andon_signal: stop` from any reviewer; coherence rating ≥ 4. | Position paper ratified ([instructions/human-approval.md §95-110](instructions/human-approval.md)) and archived to `.council/proposed/archive/GATE-{NNNN}.md`. Decision-log entry with `decision_type: "gate-pass"` and `nemawashi_walkthrough_version: N`. | Architecting and implementation may proceed. `/council-kickoff` is unblocked for trine-eval delegation. |
| **PASS WITH NOTES** | All hard constraints satisfied; coherence rating 3 *and* every criticism comes from a single reviewer (the `architect`'s synthesis judges the issues as non-blocking). Or: coherence rating ≥ 4 but `henkaten-detector` flagged ≥ 1 high-impact passive change-point that the user accepts as known-and-watched. | Same as PASS, plus a `notes` block on the decision-log entry listing the flagged items as `pre-architecture-watchlist` Henkaten records (`change_origin: passive`, status `open`). | Architecting may proceed; the watchlist items are surfaced at every subsequent sprint's pre-flight ([.harness/spec.md §3.2 Step 1A](.harness/spec.md)) and at the next gate re-entry. |
| **REJECT (revisions required)** | Any hard constraint without evidence; any non-measurable critical criterion; coherence rating ≤ 2; or `andon_signal: alert` from a reviewer that does not resolve within the takt-time bound ([instructions/andon-protocol.md:55-79](instructions/andon-protocol.md)). | Position paper kept at `.council/proposed/GATE-{NNNN}.md` with `status: revisions-required`. Decision-log entry with `decision_type: "gate-reject"`, `revisions_required: [array of specific items]`. | Discovery activities re-run for the named items only; the gate re-enters at the *partial* re-entry policy (see §6) once the revisions are claimed complete. |
| **ESCALATE TO HUMAN** | `andon_signal: stop` from any reviewer; or two consecutive REJECT cycles on the same package; or any reviewer reports a constraint that cannot be evidenced by the team (e.g. regulatory question that needs counsel). | Position paper kept; decision-log entry with `decision_type: "gate-escalate"`, `escalation_reason`, `human_required` flag set. The gate-orchestrator presents the halt to the user verbatim per the andon protocol; sprint planning does not proceed. | Human reviews; may override (logged), revise (returns to discovery), or kill the initiative (logged as project-cancellation Henkaten). |

The four states reuse `decision-log-entry` ([schemas/decision-log-entry.schema.json](schemas/decision-log-entry.schema.json)) with a new `decision_type` enum extension (`gate-pass`, `gate-pass-with-notes`, `gate-reject`, `gate-escalate`). Adding values to an existing schema is preferable to a parallel schema; the audit trail then has uniform shape across gate and sprint decisions.

The PASS-WITH-NOTES state exists because reality sits between PASS and REJECT more often than either. Forcing every borderline package into REJECT creates rework for cases that were 95% ready; allowing every borderline package as PASS suppresses signal. Notes carry forward as watchlist items so the signal is not lost.

---

## 6. Henkaten Coupling and Re-Entry Policy

Once the gate passes and architecting begins, *any* change to spec, constraints, or criteria is a change point that should re-enter the gate. The policy below is intended to read as a directly-implementable rule.

### 6.1 Trigger detection

A re-entry trigger fires when any of the three gate artifacts changes after gate-pass. Three detection points:

1. **Pre-sprint check** ([.harness/spec.md §3.2 Step 1A](.harness/spec.md)). Henkaten-detector reads `git log` since last sprint; commits touching gate artifacts fire as `gate-artifact-change` Henkaten. New 4M sub-types ([supplement R8](docs/phase-0-proposal-supplement.md)): **Material → `spec-document-change`**, **Material → `constraint-catalog-change`**, **Method → `acceptance-criterion-change`**.
2. **PreToolUse hook** ([.harness/spec.md §4.4](.harness/spec.md)). Extend `enforce-append-only` to also fire on writes to the three gate-artifact paths and emit a `gate-artifact-change` audit entry. Mechanism, not discipline ([supplement Q13](docs/phase-0-proposal-supplement.md)).
3. **Manual `/council-detect`** ([.harness/spec.md §3.1](.harness/spec.md)). Scans for diffs against the last archived gate package.

### 6.2 Re-entry severity ladder

Severity is classified by *which* artifact and *what kind* of change:

| Severity | Trigger | Re-entry |
|---|---|---|
| **Editorial** | Whitespace, typo, comment-only change in any of the three artifacts. Confirmed by `git diff` showing no semantic change (verification: `git diff --word-diff=plain` produces no `[-…-]/{+…+}` of code-bearing tokens beyond punctuation). | None. Henkaten record logged, `change_origin: passive`, impact `informational`, no walkthrough. |
| **Local** | Single-criterion measurement form revised; single constraint's `verification` command updated; single ambiguity in spec resolved with no scope change. | **Partial re-entry**: `criteria-architect` only (or the relevant single specialist) re-reviews the affected lines. Single-prompt approval if the specialist returns `coherence-rating: 5` and no `andon_signal`. |
| **Structural** | Spec scope change; constraint added or removed; criterion added, removed, or reweighted >10%. | **Full re-entry**: gate-orchestrator dispatches the same wave-1/wave-2 pattern. Nemawashi walkthrough as for the original gate-pass. |
| **Foundational** | Multiple structural changes within one sprint cycle; or any change introducing a new hard constraint not present at original gate-pass. | **Full re-entry with halt**: orchestrator drops effective autonomy to Level 1 for the affected sprint ([supplement R10](docs/phase-0-proposal-supplement.md)) until the re-entry resolves. The dynamic-floor schema's `trigger_history` ([schemas/effective-autonomy.schema.json](schemas/effective-autonomy.schema.json)) records `foundational-gate-reentry` as the trigger. |

### 6.3 Evidence required for re-approval

1. **The diff** in unified form. Verification: `git diff <pre-gate-tag>..HEAD -- <gate-artifact-path>`. Mandatory for every severity above editorial.
2. **The original position paper** at `.council/proposed/archive/GATE-{NNNN}.md`. The re-entry paper begins as a `-rev{N}` of this paper.
3. **Yokoten records** ([supplement R6](docs/phase-0-proposal-supplement.md)) from prior closed Henkaten where the change was foreseen — fast-tracks if PASS-WITH-NOTES had flagged this change.
4. **Foundational re-entry only:** evidence that the new hard constraint was not knowable at original gate-time. Without this, the original gate is itself defective; a `quality-defect-anomaly` Henkaten opens against the gate process.

### 6.4 Re-entry artifact

`GATE-{NNNN}-rev{M}.md` mirrors the original paper plus a `Changes Since Gate-Pass` section enumerating the diff and per-change council response. Decision-log entry: `nemawashi_walkthrough_version: M`, `linked_henka_id: HK-{NNNN}`. The policy is parameterized only by severity and diff size; it requires no new infrastructure beyond three new Henkaten sub-types and four new decision-log enum values.

---

## 7. Hexagonal Integration: Ports and Adapters

`grep -i hexagonal` matches only [henka-council.txt:1394, 1410-1412](henka-council.txt) and [docs/phase-0-proposal.md:1153](docs/phase-0-proposal.md), both describing *target-project* patterns the council governs — not the council's own structure. **The council is not formally hexagonal**, but it has clean port-shaped boundaries that map to ports/adapters terminology directly. This section places the gate within those boundaries without retroactively claiming the rest of the codebase as hexagonal.

### 7.1 The gate's domain core

The gate domain is the rule "the planning package must be assessed before architecture begins." This rule is independent of any specific tool, file format, or runtime. Its components:

- **Gate-package value object** — `{spec, constraint_catalog, acceptance_criteria}` with content-addressed identity (SHA-256 of canonical concatenation).
- **Gate-decision aggregate** — `{state, ratified_position_paper_path, watchlist[], reviewers_consulted[], evidence_index}`.
- **Re-entry trigger** — pure rule mapping `(diff, severity)` → `re-entry mode`.
- **Constraint** — value object with `category`, `source`, `binding`, `verification`.

These four are pure domain — no I/O, no Bash, no tool access.

### 7.2 Inbound ports (driving)

- **`/council-gate` skill** — new `skills/council-gate/SKILL.md`, procedural document analogous to `council-kickoff`. Primary port.
- **Pre-sprint hook entry** — when henkaten-detector reports a `gate-artifact-change`, council-autorun conditionally re-invokes the gate via Task. Secondary port.
- **`/council-detect --gate-coverage`** — re-runs the gate's coherence checks without producing a new position paper, for read-only audit.

### 7.3 Outbound ports (driven)

- **Position-paper writer** — `.council/proposed/GATE-{NNNN}.md`; default adapter is filesystem `Write`; future adapters could target a wiki or tracker.
- **Decision-log appender** — `scripts/append-decision.py` ([.harness/spec.md §4.4](.harness/spec.md)). Canonical existing port-adapter pair.
- **Henkaten emitter** — `scripts/append-henka.py`. Same shape.
- **Verification runner** — `scripts/run-verification.py` ([.harness/spec.md §4.5](.harness/spec.md)). Allowlist enforcement is the adapter's responsibility, not the domain's.

### 7.4 Where the gate lives in the file tree

```
agents/
  gate-orchestrator.md         # NEW — Level 4, thin specialisation of orchestrator.md
  spec-specialist.md           # NEW — Level 2, fork
  constraint-extractor.md      # NEW — Level 2, fork
  criteria-architect.md        # NEW — Level 2, fork
  architect.md                 # MODIFIED — adds "gate mode" section
  henkaten-detector.md         # MODIFIED — adds "gate mode" section
skills/
  council-gate/SKILL.md        # NEW — invocation procedure for the gate
templates/
  gate-position-paper.md       # NEW — extends nemawashi-position-paper.md with package-shape fields
schemas/
  spec-package.schema.json     # NEW — value-object schema for the gate-package
  constraint-catalog.schema.json # NEW
  acceptance-criteria.schema.json # NEW
.council/                      # runtime state (created by gate at first use)
  gate/                        # NEW — versioned gate artifacts
    spec/v{N}.md
    constraints/v{N}.json
    criteria/v{N}.json
```

The `.council/gate/` subdirectory keeps the discovery artifacts versioned next to the running governance state, making them addressable by the same Henkaten and decision-log machinery as everything else.

The gate's domain core lives in `agents/` (the role definitions) plus the schemas; the adapters are the existing scripts and hooks. The gate is therefore a first-class domain concept, not a script bolted on the side — it composes from the same primitives every other council activity does.

---

## 8. Artifacts and Storage

### 8.1 The three discovery artifacts

| Artifact | Path | Format | Versioning |
|---|---|---|---|
| **Spec** | `.council/gate/spec/v{N}.md` | Markdown with YAML frontmatter (`version`, `gate_id`, `superseded_by`). Each section MUST be linkable by stable anchor for `verification` references. | Monotonic integer; `v{N+1}` written on every structural change. Editorial changes are committed in-place with no version bump. |
| **Constraint catalog** | `.council/gate/constraints/v{N}.json` | Array of constraint objects per `schemas/constraint-catalog.schema.json` (see §8.2). | Same. |
| **Acceptance criteria** | `.council/gate/criteria/v{N}.json` | Array of criterion objects per `schemas/acceptance-criteria.schema.json` (see §8.3). | Same. |

The three artifacts are referenced together by gate-id (`GATE-{NNNN}`) and by their content-addressed package hash. The position paper at `.council/proposed/archive/GATE-{NNNN}.md` is the authoritative pointer.

### 8.2 Constraint-catalog schema (sketch)

```json
{
  "constraint_id": "C-{NNNN}",
  "category": "regulatory|organizational|architectural|philosophical|resource",
  "binding": "hard|soft",
  "statement": "string — what the constraint is, in declarative form",
  "source": "string — file:line, contract section, or external citation",
  "verification": "string — re-runnable command per §4.5 allowlist",
  "rationale": "string — why this constraint applies",
  "added_at_gate": "GATE-{NNNN}",
  "status": "active|superseded|relaxed-with-approval"
}
```

Hard constraints block PASS unless evidenced. Soft constraints become PASS-WITH-NOTES watchlist items if not fully addressed.

### 8.3 Acceptance-criteria schema (sketch)

```json
{
  "criterion_id": "AC-{NNNN}",
  "criterion": "string — what 'done and good' looks like",
  "measurement_or_observation": "string — re-runnable command OR stable observation procedure",
  "binding": "must|should",
  "weight": "0.0–1.0",
  "linked_constraints": ["C-{NNNN}", "..."],
  "linked_spec_section": "spec/v{N}.md#anchor",
  "status": "active|met|deferred"
}
```

Criteria are the seed for the eval rubric the trine-eval generator will read at sprint contract time. The schema is intentionally compatible with the existing `tests/schemas/` fixture pattern so the same `scripts/validate-*.py` machinery works.

### 8.4 Versioning and read paths

Versions are gate-internal: structural changes bump the integer; editorial changes are in-place commits logged to `audit-log.jsonl` only. Old versions persist as `v1.md`, `v2.md`; the `superseded_by` frontmatter points at the successor. Downstream agents reference the gate-id, resolving through the archived position paper's frontmatter to the current active version — sprint contracts can pin a specific version (`GATE-0001@v2`) if needed.

---

## 9. Failure Modes — Including the Gate's Own

The gate prevents some failure modes. It introduces others. Both classes need Andon-style visibility.

### 9.1 Failure modes the gate prevents

- **Defective spec propagated to architecture** — `spec-specialist` rejects on coherence ≤ 2.
- **Hidden constraint surfaced post-architecture** — `constraint-extractor` enumerates before architecture begins.
- **Unmeasurable acceptance** — `criteria-architect` rejects criteria without `measurement_or_observation`.

### 9.2 Failure modes the gate introduces

A gate is a constraint; constraints have failure modes.

| Failure | What goes wrong | Andon visibility |
|---|---|---|
| **Council deadlock** | Reviewers disagree; nemawashi Stage 3 does not converge after two revisions ([instructions/human-approval.md §83-91](instructions/human-approval.md)). | Existing escalate-to-user path. For the gate: maps to ESCALATE-TO-HUMAN with `deadlock` reason. |
| **Reviewer agent failure** | A reviewer returns `status: error` from tool or model regression. | Existing graceful-degradation ([agents/orchestrator.md:196-204](agents/orchestrator.md)). Gate extension: coverage gap on any reviewer downgrades nominal PASS to PASS-WITH-NOTES until the gap is closed. |
| **Human override** | User bypasses a REJECT. | Permitted but logged: `decision_type: "gate-override"` with mandatory `override_reason` and `override_authority`. Creates an informational `agent-capability-change` Henkaten ([supplement R8 Man axis](docs/phase-0-proposal-supplement.md)); recurring overrides (same reason ≥ 3 times) surface in `/council-retro`. |
| **Legitimate emergency bypass** | Production incident requires immediate work. | `--emergency-bypass <incident-id>` flag on `/council-gate`. Emits `andon_signal: alert` on invocation, opens a 7-day-tracked watchlist Henkaten, and *requires* post-hoc gate review within seven calendar days. |
| **Illegitimate bypass** | User edits `.harness/spec.md` directly without invoking `/council-gate`. | Pre-sprint check (§6.1) detects the artifact change; absence of a corresponding gate decision within 24h fires a high-impact `quality-defect-anomaly`. Audit trail makes it visible whether or not announced. |
| **Type-I (over-rejection)** | Adversary framing produces false positives. | Pull-rate tracking ([instructions/andon-protocol.md:118-133](instructions/andon-protocol.md)) extends to per-reviewer REJECT rates; anomalies surface in retrospective. |
| **Type-II (under-rejection)** | Steelman framing produces false negatives — only detectable when sprints fail downstream on issues the gate missed. | Retrospective `pdca` mode gains a "trace this failure to the originating gate decision" prompt; recurring traces surface the gate itself as the defect station. |
| **Gate becomes ritualistic** | Over time, gate-pass turns into a rubber-stamp. | Slowest failure mode; hardest to detect mechanically. Jishuken cadence ([.harness/spec.md §3.1](.harness/spec.md)) takes the gate as a per-period topic, reviewing it *as a process*, not as a sequence of decisions. |

The first five are mechanical. The last three are statistical, visible only through patterns. Naming both classes prevents the implementation from pretending the gate is failure-proof.

---

## 10. Migration Path

### 10.1 New initiatives

After Sprints S1–S6 ship v0.1 ([.harness/sprints.json](.harness/sprints.json)), the gate ships in a proposed S7 contract (sized similar to S5 in complexity). New initiatives invoked via `/council-gate` go through the gate before any `/council-kickoff` delegation.

### 10.2 Retroactive application

henka-council itself is mid-flight (D1–D2 shipped, S1–S6 pending). Retroactive application treats existing `.harness/spec.md`, its embedded constraints (§4), and per-sprint Success Criteria (`.harness/spec.md §5`) as a candidate gate package. Three outcomes:

1. **PASS** — `GATE-0001` assigned retrospectively; downstream sprints re-tagged with `linked_gate_id`.
2. **PASS WITH NOTES** — same, plus the watchlist becomes input to the S6 retrospective.
3. **REJECT** — continue current sprints to completion under their existing contracts; treat the rejection as a Henkaten driving v0.2 plan revision. Do not halt mid-sprint on a retroactive failure; incomplete deliverables are a worse failure than continuing with a flawed spec.

Retroactive runs do not block the current pipeline — retrofitting the upstream station cannot itself disrupt downstream stations already running.

### 10.3 Sequencing

S7: ship gate agents, schemas, and skill (forward use only). S8: retroactive run on henka-council's own spec. v0.2: mandate gate before kickoff for new consumer projects; existing projects opt in.

---

## 11. Open Questions

Each needs a human decision before implementation. Recommendations given are overridable.

1. **Composition cap.** 5-worker waved vs. 4-worker (architect merged into spec-specialist). *Rec:* 5 in two waves — preserves bounded-fan-out, keeps roles clean. *Trade-off:* extra latency.
2. **Schema extension vs. new schema.** Extend `decision-log-entry` enum vs. new `gate-decision-entry`. *Rec:* extend — uniform audit trail. *Trade-off:* consumers must handle new enum values.
3. **Re-entry severity classifier.** Heuristic rule table vs. LLM-judged. *Rec:* heuristic for v0.1 (mirrors reversibility classifier). *Trade-off:* edge-case mis-classification; LLM is harder to verify deterministically.
4. **Emergency-bypass authority.** Any user vs. designated authorised user. *Rec:* any user, with logging — visibility regardless. *Trade-off:* relies on retrospective discovery.
5. **Sub-project granularity.** One gate per project, or per coherent deliverable? *Rec:* per coherent deliverable (independently reviewable spec/constraints/criteria). Needs user framing.
6. **ID series.** `GATE-{NNNN}` vs. mirroring `DEC-{NNNN}`. *Rec:* `GATE-{NNNN}` — mnemonic, no confusion with decisions.
7. **trine-eval coupling.** Does trine-eval need to know about the gate? *Rec:* invisible — gate writes `gate_id` into the existing `governance` block ([.harness/config.json](.harness/config.json)); trine-eval reads it like any governance signal. Aligns with [docs/phase-0-proposal.md §14 Q3](docs/phase-0-proposal.md).
8. **PASS-WITH-NOTES ratification.** Auto-pass with watchlist, or require user ratification? *Rec:* require ratification — the watchlist is a non-trivial commitment. *Trade-off:* friction on borderline-but-ready packages.
9. **Producer-agent coverage for Activities 2 and 3.** A Spec Exploration producer (§1, §3) covers Activity 1. Activities 2 (Constraint Extraction) and 3 (Acceptance Criteria) have no defined producer. Options: (a) sibling Constraint Exploration and Criteria Exploration agents; (b) expand Spec Exploration into a Discovery Exploration Agent covering all three; (c) leave Activities 2 and 3 as human-only and let the gate's `constraint-extractor` and `criteria-architect` reviewers carry the load. *Rec:* (b) — single agent, single artifact stream, consistent authorship attribution. *Trade-off:* longer interview; risks blurring the three activities rather than producing three structured outputs.

---

*End of Discovery Gate design proposal.*
