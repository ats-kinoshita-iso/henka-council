# henka-council — Phase 0 Proposal Supplement
## Henkaten Management as Design Backbone

**Status:** **APPROVED 2026-05-07** — all ten redesigns (R1–R10) accepted; Q13–Q20 resolved with the supplement's recommended defaults. Folded into [`docs/phase-0-proposal-v2.md`](./phase-0-proposal-v2.md). This document is preserved as historical lineage; v2 is the authoritative kickoff input.
**Date:** 2026-05-07
**Companion to:** [`docs/phase-0-proposal.md`](./phase-0-proposal.md) (v1) — superseded by [v2](./phase-0-proposal-v2.md)
**Triggered by:** User request for deeper research into Henkaten management as the "backbone" of the project, with explicit authorization to redesign rather than transcribe the original VSCode implementation.

---

## How This Document Relates To the v1 Proposal

The v1 proposal answered "**what does the henka-council plugin contain and how does it integrate with trine-eval?**" — file tree, schemas, agent contracts, autonomy levels, the 12 Henkaten categories, the 12 governance rules. Those decisions are still correct.

This supplement answers a deeper question that v1 took as given: "**what is the change-management philosophy this system encodes, and is the v1 design faithful to it?**" Reading the canonical literature on henkaten management — and adjacent Toyota Production System concepts (jidoka, andon, nemawashi, yokoten, genchi genbutsu, poka-yoke, kaizen, jishuken) plus modern autonomy-levels frameworks for agentic AI — surfaces several places where the v1 proposal *implements something henkaten-shaped* without being grounded in the canonical principles. Some of those gaps are structural; closing them changes how the council should be designed, not just configured.

**Recommendation:** This supplement does not supplant v1. It *re-founds* v1. The v1 file tree, schemas, and agent contracts remain valid as the implementation surface. This supplement defines the seven design principles that the implementation must honor, and proposes ten concrete revisions to v1 that bring the implementation into alignment. After the user approves the principles in this supplement and the revisions in §6, the v1 proposal should be revised in place (or merged into a v2 unified document) before sprint planning.

---

## 1. What I Read

The canonical literature on henkaten and the surrounding TPS concepts is sparse in English but coherent. The core sources I drew on:

### Toyota Production System / lean canon
- **Henkaten (変化点):** [Toyota Change Point Management — AllAboutLean](https://www.allaboutlean.com/henkaten/) — the most thorough English-language treatment, including the linguistic distinction between *henkaten* (passive, "just happened") and *henkoten* (active, "you actively change something"), the three visualization patterns (list-based boards, machine-mapping boards, rush-job visualization), and the framing of every change as a *fluctuation (muda)* that risks safety, quality, speed, or cost.
- **Jidoka:** [Lean Enterprise Institute — Jidoka](https://www.lean.org/lexicon-terms/jidoka/), [Toyota UK — Andon](https://mag.toyota.co.uk/andon-toyota-production-system/) — the two halves: machines stop themselves on abnormality, AND humans retain authority to stop. Origins in Sakichi Toyoda's 1900s loom that stopped automatically on broken thread.
- **Andon cord:** [Psych Safety — The Andon Cord](https://psychsafety.com/psychological-safety-79-the-andon-cord/), [Toyota UK — Andon](https://mag.toyota.co.uk/andon-toyota-production-system/) — the *distributed authority* pattern: any worker can pull, any worker is *obliged* to pull, swarming response, and the cultural practice of thanking the puller before any troubleshooting begins. NUMMI as the case study.
- **Nemawashi:** [Lean Enterprise Institute on yokoten/nemawashi](https://www.allaboutlean.com/yokoten-nemawashi-et-al/), [Toyota UK — Nemawashi](https://mag.toyota.co.uk/nemawashi-toyota-production-system/), [Changebase — Nemawashi](https://www.changebase.app/blog/nemawashi-japanese-change-management-tool) — consensus-building *before* the formal decision: by the time the proposal reaches the meeting, everyone has already shaped it, the formal decision is just ratification.
- **Yokoten:** [LEI — Yokoten](https://www.lean.org/the-lean-post/articles/yokoten-capturing-and-sharing-best-practices/) — horizontal deployment of learning. Critically: *adapt, don't blindly copy*. "Improvement is not complete until horizontal deployment is confirmed."
- **Genchi genbutsu:** [Toyota UK — Genchi Genbutsu](https://mag.toyota.co.uk/genchi-genbutsu/), [Six Sigma — Genchi Genbutsu](https://www.6sigma.us/lean-six-sigma-articles/genchi-genbutsu/) — go to the *genba* (actual place), observe the *genbutsu* (actual thing), gather *genjitsu* (actual facts). Taiichi Ohno had managers stand inside a chalk circle on the factory floor for hours.
- **Poka-yoke:** [Toyota UK — Poka-yoke](https://mag.toyota.co.uk/poka-yoke/), [Wikipedia](https://en.wikipedia.org/wiki/Poka-yoke) — *design the mistake out* rather than relying on attention. Three detection methods: contact (physical attribute check), fixed-value (count check), motion-step (sequence check).
- **Kaizen + PDCA:** [Wikipedia — PDCA](https://en.wikipedia.org/wiki/PDCA), [Lean Enterprise Institute](https://www.lean.org/lexicon-terms/toyota-production-system/) — Plan-Do-Check-Act as the iterative learning spine. Originally Shewhart 1920s, transmitted to Toyota via Deming post-WWII.
- **Jishuken:** [Gemba Academy — What is Jishuken](https://blog.gembaacademy.com/2006/08/27/what_is_jishuken/) — "self-study" group: 5–7 managers selecting their own problem on the gemba, focused on *reflection and learning* over *target achievement*.

### Autonomy levels frameworks for agentic AI
- **CSA — Levels of Autonomy for Agentic AI:** [CSA Blog 2026](https://cloudsecurityalliance.org/blog/2026/01/28/levels-of-autonomy) — six-level framework (L0 No Autonomy → L5 Full Autonomy) with the strongest convergent recommendation: "**autonomy boundaries must be technically enforced, not just policy-documented.**"
- **Knight First Amendment Institute — Levels of Autonomy for AI Agents:** [Knight Columbia](https://knightcolumbia.org/content/levels-of-autonomy-for-ai-agents-1) — five-level framework keyed to user role (operator → collaborator → consultant → approver → observer). Argues "a system of entirely L1 agents is not ideal; entirely L5 is hard to debug and audit; **a mix of agents at different autonomy levels is more likely to result in a useful multi-agent system**." Explicitly poses but does not answer: "*If the user requests a change that triggers a cascade of other changes, how should the agent handle that?*"
- **AWS — Agentic AI Security Scoping Matrix:** [AWS Security Blog](https://aws.amazon.com/blogs/security/the-agentic-ai-security-scoping-matrix-a-framework-for-securing-autonomous-ai-systems/) — "a single agent breach can propagate through connected systems and downstream services and data stores."

### Context for the autonomous-agentic dimension
- **Multi-agent systems:** [Wikipedia — MAS](https://en.wikipedia.org/wiki/Multi-agent_system) — the orchestration layer is the control plane; SharedState mechanisms enable cross-stage propagation without modifying message-flow topology.

The bibliography is in §10.

---

## 2. The Seven Pillars of Henkaten Management

Henkaten in the canonical Toyota literature is not a single technique. It sits inside a constellation of practices that *together* solve the problem of "how does change propagate through an autonomous system without compounding into defects?" Distilling the canon, seven pillars emerge. Each maps cleanly to a property of an autonomous agent system. The v1 proposal implements three of them clearly, three of them partially, and one barely at all. Section 5 audits the v1 proposal against this framework.

### Pillar 1 — DETECT (henkaten + 4M lens, ambient + visual)

Toyota detects change through three mechanisms running in parallel:
1. **The 4M (or 6M) lens** — every change is classified along Man / Machine / Material / Method (and optionally Measurement / Mother nature). The lens is *primary*; the 12-category taxonomy in v1 is a *derived* refinement of these.
2. **Visual management** — boards on the shop floor with color-coded magnets. Operators glance at them constantly. Detection is *ambient*, not periodic.
3. **The henkaten / henkoten distinction** — *active* changes (a new operator starts, a supplier switches) are planned and pre-flagged. *Passive* changes (it's hot today, an operator is fatigued, a tool is wearing out) emerge unbidden. The detection burden is asymmetric: passive changes need a different watching posture than active ones.

> "Toyota's henkaten is a method for how to deal with not-actively-initiated changes but also includes changes that are actively initiated." [AllAboutLean](https://www.allaboutlean.com/henkaten/)

**Property of a well-built agent system:** *State changes are observable continuously, classified along a small number of structural axes, and the system distinguishes between changes it initiated and changes it is responding to.*

### Pillar 2 — HALT (jidoka + andon, distributed authority + swarming)

Halt has two distinct halves:

1. **Jidoka — automation that stops itself on abnormality.** The 1900s Toyoda loom: when a thread broke, the loom stopped, *without human intervention*. Modern equipment "distinguishes good parts from bad autonomously, without being monitored." [LEI](https://www.lean.org/lexicon-terms/jidoka/)

2. **Andon — distributed human authority to halt.** Any worker can pull the cord. Workers are *obliged* to pull when they see something out of standard. After the pull, coworkers swarm and the first thing they do is *thank the puller* — because "the interpersonal consequences of stopping the line and asking for help are significant." Crucially, the pull is an **alert**, not always a stop: the team leader has a takt-time window to resolve before the line halts. [Psych Safety](https://psychsafety.com/psychological-safety-79-the-andon-cord/), [Toyota UK](https://mag.toyota.co.uk/andon-toyota-production-system/)

> "At Toyota plants, the cord may be pulled around 50 times in a single eight-hour shift — over 1,500 times monthly — demonstrating the normalized, frequent nature of the practice." [Psych Safety](https://psychsafety.com/psychological-safety-79-the-andon-cord/)

**Property of a well-built agent system:** *Halt authority is distributed to every agent, halting an alert (recoverable) and a stop (committed) are distinguished, and the social cost of halting is structurally reduced (no penalty for false halts; first response is acknowledgment, not investigation).*

### Pillar 3 — DIAGNOSE (genchi genbutsu, firsthand observation)

> "Going to the source to find the facts to make correct decisions, build consensus, and achieve goals. To make informed decisions and know how to appropriately solve problems, one must first experience the situation at hand." [Toyota UK](https://mag.toyota.co.uk/genchi-genbutsu/)

Three specific things to gather:
- **Genba** — the actual place where the work is done
- **Genbutsu** — the actual thing being worked on
- **Genjitsu** — the actual facts

Taiichi Ohno's drawn-circle exercise — having managers stand inside a chalk circle on the factory floor for hours, observing — is the canonical instantiation. *Decisions made from the desk are deficient.*

**Property of a well-built agent system:** *Every claim is grounded in a re-runnable observation, not in a previous agent's report. The audit trail is "what was observed and how" rather than "what was concluded".*

### Pillar 4 — DECIDE (nemawashi, consensus-before-decision)

> "Make decisions slowly by consensus, thoroughly considering all options; implement rapidly." [Toyota Way Principle 13](https://www.actioglobal.com/en/principle-13-toyota-way/)

Nemawashi — literally "going around the roots" — is the practice of conducting one-on-one conversations across stakeholders *before* the formal decision meeting. By the time the meeting happens, everyone has already shaped the proposal, identified objections, and felt ownership. The "decision" is a ratification of consensus already achieved. The implementation phase is then fast because there are no surprises and no roadblocks.

> "Change doesn't flow down from the top of a hierarchy as efficiently as it spreads through a social network." [Changebase](https://www.changebase.app/blog/nemawashi-japanese-change-management-tool)

**Property of a well-built agent system:** *Significant decisions are reached by walking the user through each agent's perspective sequentially, building shared understanding incrementally, before a single approve/reject prompt is posed. The decision is "you and I have already agreed; this is just confirming"*, not "*here is a finished proposal, accept or reject.*"

### Pillar 5 — PREVENT (poka-yoke, structural error elimination)

> "Designed to prevent human errors. The aim is to design the process so that mistakes can be detected and corrected immediately, eliminating defects at the source." [Wikipedia](https://en.wikipedia.org/wiki/Poka-yoke)

Three detection methods:
- **Contact** — physical attribute check (shape, size, color)
- **Fixed-value** — count check (was the right number of motions performed?)
- **Motion-step** — sequence check (were the prescribed steps followed in order?)

Poka-yoke is *structural* — the mistake can't happen because the process makes it impossible. This is qualitatively different from "the operator is told not to make the mistake." A USB-C plug that fits any way is a poka-yoke; a label saying "insert with the logo facing up" is discipline.

**Property of a well-built agent system:** *Every governance rule is enforced by mechanism (hooks, permission systems, schema validation, type constraints) wherever possible; agent discipline is the last line of defense, not the first.*

### Pillar 6 — PROPAGATE (yokoten, horizontal deployment of learning)

> "Improvement is not complete until horizontal deployment (yokoten) is confirmed and the learning is shared with others." [LEI](https://www.lean.org/the-lean-post/articles/yokoten-capturing-and-sharing-best-practices/)

Yokoten — "horizontal expansion" — is the practice of taking a learning from one place (a sprint, a team, a plant) and deliberately spreading it to other places. Critically: **adapt, don't copy**. Toyota leaders "encourage reflection and adaptation" rather than enforcing replication.

This is distinct from kaizen. Kaizen is "improve here." Yokoten is "now spread that improvement, with adaptation, to everywhere it could apply."

**Property of a well-built agent system:** *When a learning is captured (a failure pattern, a successful approach, a new evaluation criterion), the system has an explicit step to propagate the learning to subsequent sprints — adapted to each sprint's context, not blindly copied. The propagation is observable in subsequent sprints' contracts, not just in a "lessons learned" log.*

### Pillar 7 — IMPROVE (kaizen + PDCA + jishuken, iterative learning at multiple cadences)

Three nested cadences:

1. **Per-action: jidoka response.** When jidoka stops the line, immediately diagnose and fix. Tightest loop.
2. **Per-day: PDCA.** Plan → Do → Check → Act. The Shewhart-Deming-Toyota cycle. Iteration is the principle: "once a hypothesis is confirmed (or negated), executing the cycle again will extend the knowledge further." [Wikipedia — PDCA](https://en.wikipedia.org/wiki/PDCA)
3. **Per-period: jishuken.** Self-study workshops where managers select their own problem on the gemba, focused on *reflection and learning* over *target achievement*. "In kaizen the target is given by management; in jishuken the team is asked to select it; the focus of jishuken is reflection." [Gemba Academy](https://blog.gembaacademy.com/2006/08/27/what_is_jishuken/)

These are not interchangeable. They serve different time scales and different purposes. A henkaten council that has only one of them — e.g., per-sprint retrospective — is missing two of the three rhythms.

**Property of a well-built agent system:** *Improvement is enacted at multiple cadences (per-action, per-cycle, per-period) with explicit and distinct mechanisms for each. Reflection and learning are valued separately from target achievement.*

---

## 3. Mapping the Pillars to Autonomous Agent Systems

The seven pillars apply to autonomous agent systems with surprising directness. Each pillar specifies a property the system must have; the implementation approach is what the council needs to build.

| Pillar | Property | Concrete Mechanism in Claude Code |
|---|---|---|
| 1. DETECT | Continuous, structural, asymmetric (active vs passive) | (a) The 4M lens as the primary classifier with the 12-category taxonomy as a refined sub-types layer; (b) henkaten-detector runs *both* on a periodic schedule (post-sprint) AND on file-system events via Claude Code hooks (SessionStart, PostToolUse) for ambient detection; (c) explicit `change_origin: active | passive` field in the henka record schema |
| 2. HALT | Distributed authority, alert-vs-stop distinction, low social cost | (a) Every council agent — not just the orchestrator — can return `escalate: halt` in its output and the orchestrator MUST halt; (b) two halt levels: `alert` (sprint pauses, swarms; can resume) vs. `stop` (sprint reset, requires user); (c) "thanking the puller" as a council convention — the orchestrator's halt-acknowledgment message thanks the agent that escalated, before any analysis |
| 3. DIAGNOSE | Firsthand observation, re-runnable evidence | (a) Every claim in every agent output carries a `verification` field with a re-runnable command (extends trine-eval Phase 2 `verified_via_command`); (b) the `genchi-genbutsu` rule: agents must read source files directly, not summaries from prior agents; (c) the orchestrator spot-checks one random claim per fan-in by re-running its verification |
| 4. DECIDE | Sequential consensus-building, shared understanding before approval | (a) `/council-review` and `/council-autorun` Step 1D present agent findings *one at a time* in a guided walkthrough, not a single bulk approve/reject prompt; (b) "approval" splits into "**align**" (per-agent acknowledgment) and "**ratify**" (final cross-agent decision); (c) when major correction is proposed, the orchestrator first writes a *position paper* to `.council/proposed/<DEC-NNNN>.md` summarizing the consensus chain |
| 5. PREVENT | Mechanism over discipline | (a) Every governance rule that *can* be enforced by hook is enforced by hook (PreToolUse for protected files, PostToolUse for audit log, Stop for session-marker); (b) `.claude/settings.json` deny rules for irreversible Bash commands; (c) JSON Schema validation runs on every state-file write via `scripts/append-*.py`; (d) the council's own development sprints contain a Should-NOT gate per sprint ensuring no rule is downgraded to discipline-only |
| 6. PROPAGATE | Adapt-don't-copy horizontal deployment | (a) Every Henkaten record with `status: closed` produces a `yokoten_action` field naming subsequent sprints where the learning may apply; (b) on the next sprint's pre-flight, the orchestrator surfaces relevant `yokoten_action` records as **adaptation prompts** (not copy-paste suggestions); (c) the standard-work template evolves through yokoten — additions are observable as schema diffs in `standard-work.json` |
| 7. IMPROVE | Multiple cadences, reflection separate from achievement | (a) Per-sprint mini-retrospective (15–30s, automatic, no user input) — the existing v1 retrospective agent is downgraded to this cadence; (b) per-cycle PDCA review — `/council-review` runs at every N-th sprint with explicit Plan/Do/Check/Act sections; (c) per-period `/council-jishuken` — a new skill for user-invoked deep-dive workshops, distinct from `/council-retro`, that selects its own problem and focuses on reflection rather than action items |

---

## 4. Where the v1 Proposal Captures the Pillars Correctly

To the v1 proposal's credit, several pillars are well-captured:

| Pillar | v1 Status | Citation |
|---|---|---|
| 5. PREVENT | **Strong.** §9 "Autonomy and Enforcement in Claude Code" already lays out frontmatter `tools:` lists, `.claude/settings.json` permission tiers, PreToolUse hooks for append-only enforcement, JSON Schema validation. The poka-yoke shift is well-articulated. | v1 §9.1–9.6 |
| 7. IMPROVE (per-cycle slice) | **Solid.** PDCA-shaped retrospective + standard-work evolution at every sprint boundary is implemented. | v1 §7.5, §8.4 |
| 1. DETECT (taxonomy axis) | **Solid.** 12 categories with confidence-calibration table. The henkaten-detector agent contract is clear. | v1 §6, §7.4 |
| Multi-agent governance | **Solid.** v1 §2.4 carries forward the 6-level autonomy model; §10 specifies the read-only/write-disjoint state ownership. The split between trine-eval (sprint engine) and henka-council (governance) is the right architectural cut. | v1 §2.4, §10 |

These should be preserved as-is. The supplement does not modify them.

---

## 5. Where the v1 Proposal Lost Something or Under-Specified

Eight gaps emerge when the v1 proposal is audited against the seven pillars:

### Gap 5.1 — Active vs. passive change distinction is collapsed
The v1 proposal uses "Henkaten" generically for all changes and never instantiates the henkaten/henkoten linguistic split. This matters for detection: passive changes (drift, fatigue, environmental shift) need a different *watching posture* than active changes (sprint reorder, feature add). v1 §6's confidence-calibration table addresses signal quality but not change origin. **The henka-record schema does not have a `change_origin` field.**

### Gap 5.2 — Halt authority is not distributed
v1 §8.2 Step 1F lists halt conditions enforced by the orchestrator. No agent has the authority to halt the loop on its own initiative. This is *not* the andon model. In the andon model, any worker has the authority *and obligation* to pull the cord. **An agent that detects a blocking condition can only return a recommendation; the orchestrator decides whether to halt.** This concentrates halt authority in a single role, which creates a single point of failure and contradicts the principle.

### Gap 5.3 — No alert-vs-stop distinction
v1 has only `halt`. Andon has `alert` (line continues, team swarms, resolution within takt time) and `stop` (line halts, full investigation). The two are operationally distinct and have different costs. v1's `propose-to-user` response type is closest to alert but doesn't match the kinematics — it doesn't trigger swarming, it doesn't have a takt-time resolution window, and it doesn't preserve sprint flow.

### Gap 5.4 — Genchi genbutsu enforcement is underweighted
v1 §11 Rule 1 (Evidence-First) and Rule 12 (Evidence Classification Required) are good but stop short of the canonical principle. **The principle isn't "cite evidence"; it's "go see for yourself."** v1's evidence model accepts `observed | inferred | speculative` classifications but doesn't require that `observed` evidence carry a re-runnable verification command. Without that, "observed" can degrade to "I read another agent's report and trusted it" — exactly the failure mode genchi genbutsu was developed to prevent.

### Gap 5.5 — Decision-making is approve/reject, not nemawashi-shaped
v1 §8.2 Step 1D presents major corrections to the user as a single approve/reject prompt with bullet-pointed evidence. This is the *opposite* of nemawashi. By the time the user sees the prompt, four agents have already concluded; the user is being asked to ratify a finished proposal *or* reject it whole. The user has no intermediate handles to refine, redirect, or build understanding incrementally. **Nemawashi suggests a sequential walkthrough — agent by agent, perspective by perspective, with the option to pause and adjust at each stage.**

### Gap 5.6 — Yokoten propagation is missing
v1 §11 Rule 7 ("retry is targeted") and the standard-work-evolution loop touch on cross-sprint learning, but **there is no explicit yokoten step**. A learning from sprint N is not deliberately propagated to sprints N+1, N+2, ... in adapted form. The standard-work.json gets updated, but adaptation to subsequent contexts is implicit — agents reading standard-work.json may or may not apply the lesson. The v1 design captures kaizen (improve here) but not yokoten (now spread that improvement, adapted, to everywhere it could apply).

### Gap 5.7 — Only one improvement cadence is named
v1 §8.4 `/council-retro` is the per-cycle PDCA. There is no per-action loop (jidoka response — when an agent escalates, what's the immediate response shape?) and no per-period jishuken (a separate cadence focused on reflection-over-action-items). The three cadences collapse to one, which loses signal.

### Gap 5.8 — The 4M lens is not explicit
v1 §6 lists 12 categories but doesn't ground them in the canonical 4M (Man / Machine / Material / Method) framework. The categories are useful but they're a flat list, not a structured taxonomy. **A 4M-rooted taxonomy makes the mapping to non-software contexts (when this council is applied to other project types) cleaner**, and it makes the categories easier for agents to apply because each one has a structural parent.

---

## 6. Ten Concrete Redesign Proposals

Each proposal points at a specific section of the v1 proposal that should change, with the proposed new content. These are mechanical revisions to v1; they preserve the v1 file tree and schemas but adjust their semantics.

### Redesign R1 — Add `change_origin` to the henka-record schema
**Targets:** v1 §11.3 (henka-record schema), §6 (taxonomy)

Add a required field to every henka-record:
```json
"change_origin": {
  "enum": ["active", "passive"],
  "description": "active = the change was deliberately initiated (henkoten 変更点); passive = the change emerged unbidden (henkaten 変化点 in the strict sense)"
}
```
Active changes get a different detection cadence (pre-flagged by the user or trine-eval) than passive changes (detected by ambient observation). Henkaten-detector's prompt is updated to require classification. Confidence-calibration is extended: passive changes default to lower impact unless corroborated by a second signal, mirroring the principle that the detection burden is asymmetric.

### Redesign R2 — Distribute halt authority to every agent
**Targets:** v1 §7 (per-agent contracts), §8.2 Step 1F (halt conditions)

Every agent gets the right to return a special structured signal in its output:
```json
{
  "andon_signal": {
    "type": "alert" | "stop",
    "reason": "...",
    "evidence": ["..."],
    "swarm_request": ["agent_id_1", "agent_id_2"]   // optional: agents whose perspective is needed
  }
}
```
The orchestrator MUST honor any `andon_signal: stop`. `andon_signal: alert` triggers the swarming protocol (R3). The first response in the orchestrator's reply is a *thank you* to the escalating agent — borrowed verbatim from Toyota practice. This is enforced by template; the orchestrator skill has an "andon acknowledgment" section that runs before any analytical response. The social-cost reduction is structural, not exhortative.

### Redesign R3 — Add the alert-vs-stop distinction with swarming protocol
**Targets:** v1 §6.2 (impact levels and response types), §8.2 Step 1C (fan-out)

Replace v1's flat `halt` with two operationally distinct signals:

- **`alert`**: Sprint flow pauses. The orchestrator dispatches a *swarm* — the originating agent plus any agents named in `swarm_request` — to a focused review under a takt-time bound (default 5 minutes wall-clock; configurable per sprint complexity). If the swarm resolves within the bound, sprint resumes with a logged decision. If it doesn't, the alert escalates to `stop`.
- **`stop`**: Sprint flow halts. Full investigation. User must resume.

The takt-time bound is a meaningful poka-yoke: it prevents alerts from silently transmuting into indefinite halts.

### Redesign R4 — Strengthen evidence-first into genchi-genbutsu enforcement
**Targets:** v1 §2.5 (Rule 1 + Rule 12), §11.9 (evidence-index schema)

Tighten Rule 1 from "cite evidence" to:

> **Rule 1 (revised): Genchi genbutsu evidence.** Every claim flagged `observed` must carry a `verification` field containing a re-runnable command (Bash, Python, grep, git diff) that another agent or the user can execute and observe directly. Claims flagged `inferred` must explicitly cite the chain of observed claims they derive from. Claims flagged `speculative` cannot be the basis for `propose-to-user` or `escalate` actions; only `log-only` is permitted.

Add a corresponding verification step in the orchestrator's fan-in: pick one random `observed` claim per agent output, re-run its `verification` command, log the result. If a verification re-run produces a different result than the agent reported, that is itself a Henkaten — `quality-defect-anomaly` with high impact — and the orchestrator surfaces it.

This extends trine-eval Phase 2's `verified_via_command` channel from "did a command run?" to "what command, and would re-running it produce the same result?"

### Redesign R5 — Reshape major-decision presentation around nemawashi
**Targets:** v1 §8.2 Step 1D (course correction)

Replace the current single-prompt approval flow with a four-stage walkthrough:

1. **Stage 1 — Present.** The orchestrator writes a `position paper` to `.council/proposed/<DEC-NNNN>.md` containing the consensus chain agent-by-agent. Surface to user: "I've drafted a proposal at `.council/proposed/DEC-NNNN.md`. May I walk you through it?"
2. **Stage 2 — Walk.** Sequential walkthrough, one agent's perspective at a time. After each: "Does this agent's framing match your understanding? (yes / refine / disagree)" — three handles, not two.
3. **Stage 3 — Align.** Surface any disagreements; revise the position paper; repeat Stage 2 if needed.
4. **Stage 4 — Ratify.** Once all agent perspectives are aligned with the user's framing, the formal approve/reject prompt is a confirmation, not a decision.

The "implement rapidly" half of nemawashi is preserved: once Stage 4 ratifies, the application is immediate and observable in a single git commit.

### Redesign R6 — Add explicit yokoten propagation
**Targets:** v1 §11.3 (henka-record schema), v1 §8.2 Step 1A (pre-sprint check)

Extend the henka-record schema with a `yokoten` block:
```json
"yokoten": {
  "applicable_to_subsequent_sprints": ["sprint-NN", "sprint-MM"],
  "adaptation_notes": "string — guidance for how this learning translates to those sprints; NOT a verbatim copy",
  "deployed_to": [{"sprint": "sprint-NN", "applied_at": "ISO 8601", "decision_id": "DEC-NNNN", "adaptation_taken": "string"}]
}
```

In v1 §8.2 Step 1A (pre-sprint check), add a substep:

> **Step 1A.5 — Yokoten review.** Read all closed Henkaten records with non-empty `yokoten.applicable_to_subsequent_sprints`. For any record naming this sprint: the orchestrator surfaces it to the user as an "adaptation prompt" — *not* a copy-paste suggestion. The user (or a designated agent) decides how to adapt the learning to this sprint's context; the adaptation is logged as `yokoten.deployed_to`. This makes propagation observable in evidence rather than hoping it's implicit in standard-work.json.

### Redesign R7 — Three improvement cadences as separate skills
**Targets:** v1 §8 (skills), v1 §7.5 (retrospective agent)

Replace v1's single-cadence retrospective with three cadences:

1. **`/council-retro-mini` (per-sprint, automatic, ≤30s).** Inline at the end of each sprint review. The retrospective agent runs in capture-mode only — Learning Points and Pattern Observations, no Standard Work Proposals. Output is appended to `.council/retrospectives/sprint-{NN}-mini.md`.
2. **`/council-retro` (per-cycle, every-N-sprints by default 5, PDCA-shaped).** The current v1 §8.4 retrospective. Has Plan/Do/Check/Act sections explicitly; standard-work proposals only emerge here.
3. **`/council-jishuken` (per-period, user-invoked).** Self-study workshop. The user picks the topic; the council convenes a guided reflection focused on *learning* rather than *fixing*. Output is `.council/jishuken/<topic>-<date>.md` and is *explicitly excluded* from standard-work proposals — it's reflection, not corrective action.

The three skills have distinct invocation patterns and distinct output kinds. No collapse.

### Redesign R8 — Promote 4M as the primary lens with 12 categories as derived
**Targets:** v1 §6 (12 Henkaten categories)

Re-root the taxonomy:
- **Man** — applicable analogues for an agentic system: agent capability changes (model upgrades), prompt-template revisions, evaluator behavior changes, who is reviewing.
- **Machine** — Claude Code version, plugin versions, MCP server availability, runtime characteristics.
- **Material** — source documents, datasets, configuration values, dependencies, the project's own source code.
- **Method** — contract templates, evaluation rubrics, retry logic, sprint methodology, governance rules.

Each of the 12 v1 categories becomes a *sub-type* of one of the four:
| 4M Lens | v1 Sub-types |
|---|---|
| **Man** | (none currently — *new sub-types may be needed: agent-capability-change, evaluator-bias-change*) |
| **Machine** | tool-environment-change, dependency-change |
| **Material** | source-material-change, requirement-change |
| **Method** | scope-change, method-process-change, measurement-criteria-change, schedule-priority-change, risk-compliance-change, quality-defect-anomaly, retrospective-improvement, architectural-discovery |

This re-rooting reveals that **the v1 12-category list under-represents the Man axis** — there are no agent-capability-change or model-version-change sub-types, despite both being live concerns in an autonomous-agent system. That's a real gap surfaced by the 4M lens; the proposal should add at least two Man-axis sub-types.

### Redesign R9 — Reversibility axis added to autonomy enforcement
**Targets:** v1 §9 (Autonomy and Enforcement in Claude Code)

The CSA framework recommends that autonomy boundaries account for reversibility. v1's autonomy levels are 1-dimensional (Level 0 → Level 5). Extend to a 2-dimensional model: (level × reversibility). A reversible Level 3 action is fine; an irreversible Level 3 action is denied automatically.

| Autonomy Level | Reversible Action | Irreversible Action |
|---|---|---|
| L1–L2 (propose) | Allowed | Allowed (proposal is itself reversible — drafts only) |
| L3 (auto-apply minor) | Allowed | **Denied — escalates to L5** |
| L4 (coordinate) | Allowed | **Denied — escalates to L5** |
| L5 (human-only) | Allowed (with approval) | Allowed (with approval) |

Reversibility is determined by the action's nature:
- File writes to `.council/working/` — reversible (git revert)
- File writes to append-only logs — reversible-with-caveat (the entry remains, but a counter-entry can supersede)
- File writes to `.harness/features.json` — reversible (git revert)
- `git push` — **irreversible** (remote state changes)
- `git reset --hard` — **irreversible** (loses uncommitted work)
- Public release / deployment — **irreversible**

The reversibility classifier lives in the orchestrator skill as a hard-coded rule table for v0.1; future versions could derive it from action metadata.

### Redesign R10 — Dynamic autonomy floor on consecutive failures
**Targets:** v1 §9 (autonomy), v1 §8.2 Step 1F (halt conditions)

Add a dynamic autonomy mechanism: when consecutive failures or escalations exceed a threshold, the orchestrator **temporarily drops** all council agents to a lower autonomy level until a stability checkpoint is reached.

Rules:
- 2 consecutive sprint FAILs → orchestrator drops from L4 to L3, requires user confirmation per sprint until 1 PASS resets it.
- 3 consecutive `andon_signal: stop` → all Level 2 agents drop to Level 1 (recommend-only); requires `/council-jishuken` to reset.
- Any `change_origin: active` Henkaten flagged `high-risk` → automatic drop to L1 across all agents until the user explicitly re-enables.

This is the agentic-system analogue of "drop the line until we understand what's happening." It makes autonomy adaptive rather than static, matching the CSA-framework recommendation that "autonomy might automatically drop to Level 1 if anomalies are detected."

---

## 7. New Open Questions Surfaced by This Research

These supplement v1's §14 questions. Numbered Q13+ to extend the v1 list.

### Q13 — How aggressive should mechanism-over-discipline be?

R5 (poka-yoke) and v1 §9.4 (PreToolUse hook for append-only) are both mechanism-based. But mechanism has costs: hooks are platform-specific (Bash; cross-platform burden), they fail open if the hook system is disabled, they require operators to install them. Discipline scales further (an agent's prompt is portable). **Where on the mechanism ↔ discipline spectrum should each rule sit?**

**Recommendation:** Mechanism for the four rules whose violation has high blast radius (append-only logs, features.json modification, irreversible git commands, schema validation on append). Discipline for everything else, with retrospective-flagged escalation if discipline-only rules are violated.

### Q14 — How much do we trust agent-issued andon signals?

R2 distributes halt authority. But agents might issue spurious halts (false alarms), or — worse — fail to issue halts when warranted. Toyota addresses this socially (pull-rate of ~50/shift is normal; never punishing false alarms). The agent equivalent isn't fully clear. **Should the orchestrator second-guess andon signals, or honor them strictly?**

**Recommendation:** Strictly honor, but track pull-rates per agent in the audit log. If an agent's pull-rate is anomalously high, that's itself a signal (potentially a bug in the agent's prompt) that surfaces as a `quality-defect-anomaly` Henkaten. Do not introduce orchestrator-side filtering; the social cost of filtering (reducing the agent's willingness to escalate) outweighs the cost of the occasional false alarm.

### Q15 — Does nemawashi-shaped decision-making slow the loop too much?

R5 turns single-prompt approve/reject into a four-stage walkthrough. This adds friction. **Is this acceptable, or does it make the user-experience too heavyweight for routine sprints?**

**Recommendation:** Apply nemawashi-shaped decisions only to *major* corrections (the v1 §8.2 Step 1D Major list — sprint reordering, features.json, spec.md amendments, weight changes >10%, new sprints). *Minor* corrections retain the v1 single-step auto-apply model. Nemawashi is for genuine decisions; minor corrections aren't decisions.

### Q16 — Are jishuken outputs supposed to feed back into the system, or stay as standalone artifacts?

R7 introduces `/council-jishuken` as reflection-without-action. But Toyota's actual practice is that jishuken *does* eventually inform standard-work — just on a longer cadence. **Should henka-council have an explicit "jishuken-to-standard-work" promotion path, or is it deliberately decoupled?**

**Recommendation:** Decoupled in v0.1. Jishuken output is reflection; promotion to standard-work happens through the next `/council-retro` cycle (which can read jishuken artifacts). Direct jishuken-to-standard-work promotion is a v0.2 enhancement if the indirect path proves too slow.

### Q17 — Should yokoten adaptations be subagent-authored or human-authored?

R6 surfaces yokoten records as "adaptation prompts." But the adaptation itself — applying the learning to a new sprint's context — could be done by an agent (faster, automated) or by the user (slower, more thoughtful). **Which?**

**Recommendation:** Default to user, with agent assistance via dispatch. The agent (likely retrospective or architect) drafts an adaptation; the user reviews and ratifies. This honors nemawashi (R5) — the agent's draft becomes a starting position for joint refinement, not a finished proposal.

### Q18 — How does the 4M Man axis apply to Claude Code agentic systems specifically?

R8 surfaces that v1's 12 categories under-represent the Man axis. Possible new sub-types:
- `agent-capability-change` — model upgrade, prompt-template revision, agent definition revision
- `evaluator-bias-change` — evaluator's grading patterns shift across sprints
- `human-reviewer-change` — different user reviewing this sprint vs. prior

**Open:** which of these to add in v0.1, what their detection signals are, what their default impact level is.

**Recommendation:** Add `agent-capability-change` (high-confidence: detectable via plugin version diff, agent file diff, model version diff). Defer `evaluator-bias-change` to v0.2 (requires statistical comparison of evaluator output distributions across sprints — non-trivial). `human-reviewer-change` is captured by trine-eval transcripts already if multiple humans review; tag as informational, no new type needed.

### Q19 — Should reversibility classification be per-action or per-tool?

R9 introduces the reversibility axis. Classification could be:
- Per-tool: `git push` is always irreversible regardless of context.
- Per-action: `git push to main` is irreversible; `git push to a personal feature branch` is recoverable.

**Recommendation:** Per-tool in v0.1 (simpler, conservative). Per-action in v0.2 if v0.1 proves over-restrictive.

### Q20 — When the orchestrator drops autonomy levels (R10), how do other plugins observe?

R10 introduces dynamic autonomy. If an external observer (a separate plugin, a CI system, the user's terminal) needs to know the current autonomy state, **how does it discover it?**

**Recommendation:** The current effective autonomy state is written to `.council/state/effective-autonomy.json` on every change. Other systems poll this file. The schema is small (`{level: 1-5, last_change: ISO 8601, reason: "string", restored_when: "string"}`). This makes the autonomy floor observable rather than purely internal.

---

## 8. Verdict — Supplement, Not Supplant

I considered writing a unified v2 proposal that absorbs this supplement into v1. The reasons not to:

1. **v1's structural decisions are still correct.** The plugin layout, 10 schemas, agent contracts, trine-eval integration, file-tree are all valid. Nothing in the seven-pillar analysis above invalidates them.
2. **The supplement is conceptually load-bearing in a different register than v1.** v1 is "what to build"; this is "what design philosophy to honor while building it." Mixing them would dilute both.
3. **The user's review effort is bounded.** Asking the user to re-read a 1300-line v1 just to find ten changes wastes review time. Surfacing the changes as ten enumerated redesigns (§6) lets the user evaluate each independently and decide which to accept.

**Therefore:** This supplement adds to v1; both documents stand. After user review:

- For each redesign R1–R10 the user accepts: the corresponding v1 section is revised in place. The revisions produce v1.1.
- For redesigns the user defers or rejects: noted in the v1.1 changelog as "considered, deferred" with rationale.
- For new open questions Q13–Q20: each gets a decision before sprint planning, same as v1's Q1–Q12.

The combined `v1.1 + this supplement` becomes the input to `/trine-eval:harness-kickoff`.

---

## 9. Updated Sign-off Checklist

Append to v1 §17. Before proceeding to kickoff, the user has reviewed and decided on:

- [ ] §6 R1 — `change_origin` field added to henka-record schema
- [ ] §6 R2 — Distributed andon authority via per-agent `andon_signal`
- [ ] §6 R3 — Alert-vs-stop distinction with takt-time-bounded swarming
- [ ] §6 R4 — Genchi-genbutsu evidence: re-runnable verification on every observed claim
- [ ] §6 R5 — Nemawashi-shaped major-decision walkthrough
- [ ] §6 R6 — Yokoten propagation as explicit pre-sprint substep
- [ ] §6 R7 — Three improvement cadences as separate skills (mini, retro, jishuken)
- [ ] §6 R8 — 4M as primary lens; 12 categories as sub-types; new Man-axis sub-types
- [ ] §6 R9 — Reversibility axis added to autonomy enforcement
- [ ] §6 R10 — Dynamic autonomy floor on consecutive failures
- [ ] §7 Q13 — Mechanism vs. discipline boundaries
- [ ] §7 Q14 — Trust posture for agent-issued andon
- [ ] §7 Q15 — Nemawashi scope (major-only vs. all decisions)
- [ ] §7 Q16 — Jishuken-to-standard-work coupling
- [ ] §7 Q17 — Yokoten adaptation authorship
- [ ] §7 Q18 — 4M Man axis sub-types in v0.1
- [ ] §7 Q19 — Reversibility classification granularity
- [ ] §7 Q20 — Effective-autonomy observability

After the user signs off, I'll either revise v1 in place to produce a unified v1.1, or hold v1 + this supplement as the kickoff inputs side-by-side — operator's choice.

---

## 10. Bibliography

### Toyota Production System / lean canon
- AllAboutLean — [Toyota Change Point Management: Henkaten](https://www.allaboutlean.com/henkaten/)
- AllAboutLean — [The Soft Power of TPS: Yokoten, Nemawashi, et al.](https://www.allaboutlean.com/yokoten-nemawashi-et-al/)
- Lean Enterprise Institute — [Jidoka](https://www.lean.org/lexicon-terms/jidoka/)
- Lean Enterprise Institute — [Yokoten: Capturing and Sharing Best Practices](https://www.lean.org/the-lean-post/articles/yokoten-capturing-and-sharing-best-practices/)
- Toyota UK — [Andon — Toyota Production System guide](https://mag.toyota.co.uk/andon-toyota-production-system/)
- Toyota UK — [What is Genchi Genbutsu?](https://mag.toyota.co.uk/genchi-genbutsu/)
- Toyota UK — [What is Nemawashi?](https://mag.toyota.co.uk/nemawashi-toyota-production-system/)
- Toyota UK — [Poka-yoke](https://mag.toyota.co.uk/poka-yoke/)
- Toyota Motor Corporation — [Toyota Production System | Vision & Philosophy](https://global.toyota/en/company/vision-and-philosophy/production-system/)
- Psych Safety — [Psychological Safety #79: The Andon Cord](https://psychsafety.com/psychological-safety-79-the-andon-cord/)
- Wikipedia — [Poka-yoke](https://en.wikipedia.org/wiki/Poka-yoke)
- Wikipedia — [PDCA](https://en.wikipedia.org/wiki/PDCA)
- Wikipedia — [Toyota Production System](https://en.wikipedia.org/wiki/Toyota_Production_System)
- Changebase — [Nemawashi: The Lost Japanese Change Management Tool from Toyota](https://www.changebase.app/blog/nemawashi-japanese-change-management-tool)
- Gemba Academy — [What is Jishuken?](https://blog.gembaacademy.com/2006/08/27/what_is_jishuken/)
- ActioGlobal — [Toyota Way Principle 13: Make Decisions Slowly by Consensus](https://www.actioglobal.com/en/principle-13-toyota-way/)
- Six Sigma — [Genchi Genbutsu: A Way to First-Hand Process Observation](https://www.6sigma.us/lean-six-sigma-articles/genchi-genbutsu/)

### Autonomy levels frameworks for agentic AI
- Cloud Security Alliance — [Levels of Autonomy for Agentic AI (Jan 2026)](https://cloudsecurityalliance.org/blog/2026/01/28/levels-of-autonomy)
- Knight First Amendment Institute — [Levels of Autonomy for AI Agents](https://knightcolumbia.org/content/levels-of-autonomy-for-ai-agents-1)
- Amazon Web Services — [The Agentic AI Security Scoping Matrix](https://aws.amazon.com/blogs/security/the-agentic-ai-security-scoping-matrix-a-framework-for-securing-autonomous-ai-systems/)
- McKinsey — [Trust in the age of agents (governance for autonomous systems)](https://www.mckinsey.com/capabilities/risk-and-resilience/our-insights/trust-in-the-age-of-agents)

### Multi-agent systems and orchestration
- Wikipedia — [Multi-agent system](https://en.wikipedia.org/wiki/Multi-agent_system)

---

*End of Phase 0 Proposal Supplement.*
