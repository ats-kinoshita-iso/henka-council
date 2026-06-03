# henka-council — Phase 0 Proposal v2 (Unified)

**Status:** Draft for review (authoritative kickoff input)
**Date:** 2026-05-07
**Lineage:** Absorbs [`docs/phase-0-proposal.md`](./phase-0-proposal.md) (v1) + [`docs/phase-0-proposal-supplement.md`](./phase-0-proposal-supplement.md) (approved 2026-05-07). v1 and the supplement are preserved verbatim as historical record; v2 is the single source of truth from this point forward.
**Scope:** Phase 0 design proposal for reimplementing `henkaten-council` as a Claude Code plugin that wraps and extends [trine-eval](https://github.com/ats-kinoshita-iso/trine-eval). No code is produced. This document defines the contracts that subsequent sprints will implement.
**Schema snippets:** the inline JSON Schema fragments below (e.g. the `response_type` and `decision_outcome` enums) are frozen as of kickoff and kept verbatim as the historical contract. The files under `schemas/` are authoritative and may have evolved since; where they differ, the shipped schemas win.

---

## 0. How to Read This Document

v2 is structured so each section is independently reviewable and can be cited verbatim by future sprint contracts. Compared to v1:

- **Section 2.6 is new** — the seven pillars of henkaten management, the design backbone the rest of the document is grounded in.
- **Sections 6, 7, 8, 9, 11 are revised** to apply redesigns R1–R10 from the supplement.
- **Section 14 is extended** with the supplement's Q13–Q20, all resolved with the recommended defaults; the user may override any.
- **Section 15 is the updated sprint plan** reflecting the expanded scope (three retrospective cadences, andon protocol, nemawashi flow, yokoten propagation).
- **Section 18 is the consolidated bibliography**.

A v1→v2 changelog appears in Section 17.

The terminology choices (henka vs henkaten, `.council/` vs `.henka/`), the plugin packaging decision, and other open questions are listed in [Section 14 — Decisions Required Before Sprint Planning](#14-decisions-required-before-sprint-planning). **Reviewing those open questions first** lets you correct any wrong assumptions before reading the rest.

The section numbering deliberately mirrors v1 where the topic is the same, to make cross-reference trivial. Direct quotes from the source spec are marked `[src §N lines A–B]`.

---

## 1. Executive Summary

henka-council is a **governance layer** that wraps a sprint execution engine ([trine-eval](https://github.com/ats-kinoshita-iso/trine-eval)) with change-point detection, multi-agent review, bounded course correction, and approval gates. It encodes the Toyota Production System concept of a *henkaten* (変化点 — "change point"): every moment where conditions shift is a potential source of defects, so changes must be detected, classified, and consciously managed rather than absorbed silently.

v1 answered "**what does the henka-council plugin contain?**" — file tree, schemas, agent contracts, autonomy levels, the 12 categories, the 12 governance rules. The supplement asked "**what change-management philosophy does this system encode, and is the v1 design faithful to it?**" Reading the canonical literature on henkaten and the surrounding TPS practices — jidoka, andon, nemawashi, yokoten, genchi genbutsu, poka-yoke, kaizen, jishuken — plus modern autonomy-levels frameworks for agentic AI surfaced seven design pillars (Section 2.6) and ten concrete redesigns to v1 (now applied throughout v2).

v2 is therefore both **what to build** (file tree, schemas, contracts) and **what design philosophy to honor while building it** (the seven pillars). The two are integrated in a single document so reviewers and subsequent sprint contracts can cite either layer by section.

This proposal:

1. Maps every VSCode primitive in the source spec to a Claude Code equivalent (Section 3)
2. Specifies the henka-council plugin layout — every file the plugin will ship and what it owns (Section 4)
3. Defines the trine-eval integration contract (Section 10)
4. Maps autonomy levels 0–5 to concrete enforcement mechanisms, now extended with reversibility and dynamic-floor mechanisms (Section 9)
5. Carries forward the 12 governance rules, the schemas, and the standard-work template; revises the taxonomy and several rules to match the seven pillars (Sections 2.5, 6, 11)
6. Adds the seven pillars as foundational design principles (Section 2.6)
7. Lists 20 open design questions resolved with recommended defaults (Section 14)
8. Proposes a 2 + 6 = 8-sprint plan for v0.1 (Section 15)

**What this proposal does not do:** it does not produce code, it does not draft sprint contracts, it does not run `/trine-eval:harness-kickoff`. Those happen *after* this proposal is approved (or revised).

---

## 2. Conceptual Model

These elements are platform-agnostic. Sections 2.1–2.5 reproduce v1; Section 2.6 is new in v2.

### 2.1 Three-Layer Architecture

```
+-------------------------------------------------------------------+
|  Council Plugin (Governance Layer)                               |
|  State: .council/                                                 |
|  Owns: change detection, classification, review, correction,     |
|        decision logging, approval gates, standard work evolution, |
|        andon authority, nemawashi-shaped decisions, yokoten     |
|        propagation, three improvement cadences                   |
|  /council-kickoff       -> Bootstrap .council/ + delegate to    |
|                            trine-eval                            |
|  /council-autorun       -> Outer loop per sprint:                 |
|    1. PRE-SPRINT: Henkaten check + yokoten review                 |
|    2. EXECUTE: Sprint loop (trine-eval contract->build->eval)    |
|    3. POST-SPRINT: Council convenes (fan-out -> fan-in)          |
|    4. COURSE CORRECT: minor=auto, major=nemawashi walkthrough   |
|    5. NEXT or HALT (alert vs stop)                                |
+-------------------------------------------------------------------+
              |                              |
              v                              v
    +-------------------+         +------------------------+
    |  trine-eval/      |         |  target-project/       |
    |  (Sprint Engine)  |         |  +-- .harness/         | <- sprint state
    |  Unchanged.       |         |  +-- .council/         | <- governance state
    |  Owns execution.  |         |  +-- src/              | <- project code
    +-------------------+         +------------------------+
```

[src §2 lines 71–104]

**Key invariant:** the council reads `.harness/` state as input but never writes to `.harness/` files without explicit human approval (Level 5 gate). Changes to `.harness/` artifacts go through the approval process — never applied silently.

### 2.2 The Self-Referential Setup

henka-council has a deliberately self-referential structure for its initial development:

- **Sprint engine being used to build henka-council:** trine-eval
- **Target project being built:** henka-council itself (this repo)
- **Project henka-council will eventually govern:** trine-eval (when this council is applied to trine-eval's own development) AND any other consumer project trine-eval is applied to

trine-eval is simultaneously the *engine* that builds henka-council AND a *target* henka-council can govern. The two roles are kept separate — at no point during henka-council's development does henka-council govern its own construction; it is built straight through trine-eval, and only after release does it get pointed at trine-eval as a governance target.

### 2.3 The Henkaten Loop (10 Steps)

[src §7 lines 611–636]

1. **DETECT** change (from sprint results, user input, or environment) — now classified as `change_origin: active | passive` (R1)
2. **CLASSIFY** change (assign to 4M lens + sub-type) (R8)
3. **ASSESS** impact (informational, actionable, blocking, high-risk; alert vs stop) (R3)
4. **ASSEMBLE** or adjust council (minimum viable set of agents)
5. **EXECUTE** bounded response (within autonomy level, accounting for reversibility) (R9)
6. **VERIFY** evidence (every `observed` claim carries a re-runnable `verification` command) (R4)
7. **REQUEST** human approval (single-prompt for minor; nemawashi walkthrough for major) (R5)
8. **UPDATE** artifacts (decisions, corrections, state files)
9. **CAPTURE** learning (per-sprint mini, per-cycle PDCA, per-period jishuken) (R7)
10. **PROPAGATE** learning (yokoten — adapt-don't-copy across subsequent sprints) (R6)

Sprint Lifecycle Integration:

```
Sprint Intake       -> /council-kickoff               (steps 1-5)
Planning            -> /trine-eval:harness-kickoff produces spec/features/sprints
Execution           -> /trine-eval:harness-sprint loop (contract -> build -> eval -> retry)
Inter-Sprint Review -> council convenes               (steps 1-10)
Per-sprint capture  -> /council-retro-mini            (step 9, mini cadence)
Per-cycle PDCA      -> /council-retro                 (step 9, cycle cadence; standard-work evolves here)
Per-period reflection -> /council-jishuken            (step 9, period cadence; reflection-only)
Closure             -> /trine-eval:harness-summary + /council-retro at horizon
```

### 2.4 Autonomy Model (6 Levels × Reversibility Axis × Dynamic Floor)

v1 carried six autonomy levels. v2 extends this in two ways per the supplement:

- **R9 — Reversibility axis.** Each action is classified `reversible | irreversible`. Levels 3–4 may auto-execute reversible actions; irreversible actions automatically escalate to Level 5 regardless of the agent's nominal autonomy.
- **R10 — Dynamic autonomy floor.** Consecutive failures or escalations *temporarily lower* the effective autonomy level until a stability checkpoint is reached.

#### 2.4.1 Six Levels (verbatim from v1)

[src §5 lines 417–471]

| Level | Name | Permits | Prohibits | Used By |
|---|---|---|---|---|
| **0** | Observe only | Read state, eval reports, harness artifacts | Any recommendation, output, modification | (passive monitoring; no agent uses by default) |
| **1** | Classify and recommend | Level 0 + classify changes, write recommendations to agent notes, log observations | Propose changes to controlled artifacts, modify state | henkaten-detector, rag-source |
| **2** | Propose changes (drafts) | Level 1 + create draft course corrections, propose contract amendments, write review reports | Modify `.harness/` files, modify `.council/` state directly, finalize artifacts | architect, scope-guardian, retrospective, qa-regression |
| **3** | Auto-apply minor corrections | Level 2 + update `.council/` working files (decision-log, henka-register), apply minor corrections to upcoming sprint contracts (technical notes, clarifications), update progress.md | Modify features.json, reorder sprints, change spec.md, modify prior eval reports, change criteria weights by >10%, promote drafts to final | orchestrator |
| **4** | Coordinate sequences under supervision | Level 3 + execute multi-step workflows (full council review cycle), invoke multiple agents sequentially, apply approved corrections to `.harness/` files | Operate without user awareness of scope, modify governance rules, change autonomy levels, override halt conditions | orchestrator (during autorun) |
| **5** | Reserved (never autonomous) | Only with explicit prior human approval per action: modify features.json, reorder sprints, amend spec.md, change governance rules, release controlled artifacts, merge branches, push to remote, reset git | Any action without explicit human approval on that specific action | None (human only) |

#### 2.4.2 Reversibility Axis (R9)

Each action is also tagged `reversible | irreversible`. The orchestrator's effective permission grid:

| Autonomy Level | Reversible Action | Irreversible Action |
|---|---|---|
| L1–L2 (propose) | Allowed | Allowed (proposals are themselves reversible — drafts only) |
| L3 (auto-apply minor) | Allowed | **Denied — escalates to L5** |
| L4 (coordinate) | Allowed | **Denied — escalates to L5** |
| L5 (human-only) | Allowed (with approval) | Allowed (with approval) |

Reversibility classifier (per-tool in v0.1; see Q19):

| Action | Reversibility |
|---|---|
| File writes to `.council/working/`, `course-corrections/`, `proposed/`, `jishuken/`, `retrospectives/`, `sessions/` | Reversible (git revert) |
| File writes to append-only logs (`*.jsonl`) | Reversible-with-caveat (the entry remains; a counter-entry can supersede) |
| File writes to `.harness/features.json`, `spec.md`, `sprints.json` | Reversible (git revert) but Level 5 by Rule 3/7 |
| `git push`, `git push --force` | **Irreversible** (remote state changes) |
| `git reset --hard` | **Irreversible** (loses uncommitted work) |
| `git rebase -i`, `git tag -d` (deletion of pushed tag) | **Irreversible** (in shared repos) |
| Public release / deployment / package publish | **Irreversible** |

The classifier lives in the orchestrator skill as a hard-coded rule table for v0.1; future versions could derive it from action metadata. The current effective autonomy state and reversibility classification of pending actions is observable in `.council/state/effective-autonomy.json` (R10/Q20).

#### 2.4.3 Dynamic Autonomy Floor (R10)

The orchestrator monitors operational signals and **temporarily drops** all council agents to a lower effective autonomy level until a stability checkpoint is reached. Rules:

| Trigger | Effect | Reset Condition |
|---|---|---|
| 2 consecutive sprint FAILs | Orchestrator drops from L4 → L3; requires user confirmation per sprint | 1 PASS resets |
| 3 consecutive `andon_signal: stop` events from **at least 2 distinct originator agents** | All Level 2 agents drop to Level 1 (recommend-only) | `/council-review --restore-autonomy` |
| Any `change_origin: active` Henkaten flagged `high-risk` | Automatic drop to L1 across all agents | User explicitly re-enables via `/council-review --restore-autonomy` |

**Corroboration requirement (added v2.1 amendment):** the andon-stop trigger requires distinct-originator corroboration so a single flaky agent cannot lock the council into recommend-only mode. Three consecutive stops from the *same* agent are tracked as `quality-defect-anomaly` Henkaten (per Q14 pull-rate anomaly detection) but do not by themselves drop the floor.

The current effective state is written to `.council/state/effective-autonomy.json` on every change so external observers (CI, other plugins, the user's terminal) can poll. Schema: `{level: 1-5, last_change: ISO 8601, reason: "string", restored_when: "string"}` (Q20).

### 2.5 The 12 Governance Rules

[src §11 lines 1126–1194]

Carried forward verbatim from v1 with two revisions:

1. **Evidence-First Behavior — REVISED per R4 (genchi genbutsu).** Every recommendation cites specific evidence. Every claim flagged `observed` MUST carry a `verification` field containing a re-runnable command (Bash, Python, grep, git diff) that another agent or the user can execute and observe directly. Claims flagged `inferred` must explicitly cite the chain of observed claims they derive from. Claims flagged `speculative` cannot be the basis for `propose-to-user` or `escalate` actions; only `log-only` is permitted. Unsupported claims are rejected by the orchestrator.
2. **Draft Until Approved** — All council-proposed changes to `.harness/` are DRAFTS until explicit user approval. Drafts go to `.council/course-corrections/` (single-step minor) or `.council/proposed/<DEC-NNNN>.md` (nemawashi-shaped major; R5).
3. **features.json Is Sacred** — No agent may remove, rename, or reinterpret features without Level 5 approval. Feature status updates (pending → done) are the only auto-applicable change.
4. **Bounded Self-Organization** — Agents may flag the need for another perspective via `swarm_request` (R2/R3), but the orchestrator decides whether to invoke additional agents. No agent invokes another directly. **Carve-out:** `andon_signal: stop` from any agent is mandatory and must be honored immediately by the orchestrator (§7.0.1) — Rule 4 governs `swarm_request` (suggestive) but not `stop` (mandatory).
5. **Workspace Is Source Of Truth** — All decisions, evidence, classifications, and approvals must be written to structured workspace files. Do not rely on conversation history; it may be compacted.
6. **Halt On Blocking Henkaten** — REVISED per R3 (alert vs stop). If any record is classified as blocking or high-risk, the autorun loop MUST issue at minimum an `andon_signal: alert`. Records flagged `high-risk` issue `andon_signal: stop` and require explicit user resume.
7. **Minor / Major Correction Threshold** — Minor (auto-apply at Level 3 if reversible): technical notes, clarifications, progress updates, status pending→done. Major (Level 5 approval, nemawashi-shaped per R5): sprint reordering, feature changes, spec amendments, weight changes >10%, new sprints, architectural pivots.
8. **Decision Logging Is Mandatory** — Every correction, classification, and review outcome is logged to `decision-log.jsonl` with timestamp, agents, evidence, and outcome.
9. **No Scope Expansion By Agents** — Agents may flag gaps but adding features requires Level 5 approval.
10. **Retry Is Targeted** — Corrections are specific and bounded; no "refactor everything" without explicit user approval.
11. **Graceful Degradation** — When expected input files are missing, agents do not fail silently or hallucinate. Specific behavior per missing file is documented; agents report a `coverage` section listing what was available vs. unavailable.
12. **Evidence Classification Required** — All findings include `evidence_class` (observed | inferred | speculative) and `confidence` (high | medium | low). The orchestrator prioritizes observed > inferred > speculative when resolving conflicts. Per Rule 1 (revised), `observed` requires a re-runnable `verification`.

### 2.6 The Seven Pillars of Henkaten Management

This section is new in v2. It states the design philosophy v1 left implicit. Every subsequent design choice in this document should be traceable to one of these pillars.

| # | Pillar | Distilled From | Property of a Well-Built Agent System |
|---|---|---|---|
| 1 | **DETECT** | henkaten + 4M lens; ambient + visual; active vs passive distinction | State changes are observable continuously, classified along a small number of structural axes, and the system distinguishes between changes it initiated and changes it is responding to. |
| 2 | **HALT** | jidoka + andon; distributed authority; alert vs stop; swarming; thank-the-puller | Halt authority is distributed to every agent; halting an alert (recoverable) and a stop (committed) are distinguished; the social cost of halting is structurally reduced. |
| 3 | **DIAGNOSE** | genchi genbutsu; firsthand observation; re-runnable evidence | Every claim is grounded in a re-runnable observation, not a previous agent's report. The audit trail records "what was observed and how" rather than "what was concluded." |
| 4 | **DECIDE** | nemawashi; consensus-before-decision; implement rapidly | Significant decisions are reached by walking the user through each agent's perspective sequentially, building shared understanding incrementally, before a single approve/reject prompt is posed. |
| 5 | **PREVENT** | poka-yoke; structural error elimination | Every governance rule that *can* be enforced by mechanism (hooks, permission systems, schema validation, type constraints) is enforced that way; agent discipline is the last line of defense, not the first. |
| 6 | **PROPAGATE** | yokoten; horizontal deployment; adapt-don't-copy | When a learning is captured, the system has an explicit step to propagate it to subsequent sprints — adapted to each sprint's context, not blindly copied. The propagation is observable in subsequent sprints' contracts, not just in a "lessons learned" log. |
| 7 | **IMPROVE** | kaizen + PDCA + jishuken; multiple cadences | Improvement is enacted at multiple cadences (per-action, per-cycle, per-period) with explicit and distinct mechanisms for each. Reflection and learning are valued separately from target achievement. |

The complete distillation, source bibliography, and per-pillar mapping to concrete Claude Code mechanisms is the body of the supplement (`docs/phase-0-proposal-supplement.md` §§2–3); not duplicated here. v2's Sections 6, 7, 8, 9, 11, 14, 15 implement those mappings.

---

## 3. Claude Code Environment Mapping

Section 3 is **unchanged from v1**. Reproduced here in summary; full text in v1 §3.

### 3.1 Direct Mappings (Equal or Stronger in Claude Code)

`runSubagent` → `Task` with `subagent_type` and `context: fork`. `.agent.md` → `agents/<name>.md`. `.prompt.md` → `skills/<name>/SKILL.md`. `tools:` declarations → frontmatter `tools:` (using Claude Code tool names). User-invocable concept → skills (user-facing) vs agents (orchestrator-dispatched). Multi-root workspace → worktrees + cross-repo file references. Persistent state → identical (full file access). Append-only logs → Bash `>>` redirect + PreToolUse hook. Schema-validated state → JSON Schema files + Python validation. Context compaction → Claude Code session compaction + structured re-read. MCP for git → direct Bash + `.claude/settings.json` permissions (Option A — see v1 §3.3).

### 3.2 Mappings That Need Care

Subagent isolation depends on prompt construction discipline (mitigation: standardized dispatch envelope template). Plugin cache lag (mitigation: version bump on tool changes). Per-agent tool access control (mitigation: PreToolUse hook). User-invocable vs orchestrator-only skills (mitigation: `_` prefix convention).

### 3.3 The Git MCP Server — Drop or Keep?

**Decision (Option A from v1):** Drop the MCP server, use direct Bash with `.claude/settings.json` permission rules. Simpler, native to the harness. Path to Option B preserved if per-call gating proves needed later.

### 3.4 Claude Code Capabilities the Source Spec Did Not Have

Hooks (PreToolUse / PostToolUse / Stop / SessionStart / SessionEnd), `.claude/settings.json` permission rules, plugin marketplaces with versioned cache, `/compact` and `/clear`, `mcp__ccd_session__spawn_task`, `ScheduleWakeup` / `/loop`, `mcp__ccd_session__mark_chapter`, the `Stop` hook, background agents (`run_in_background: true`). All adopted as documented in v1.

---

## 4. Plugin Layout

Updated from v1 to add the new directories and skills introduced by R5, R6, R7, R10. Additions tagged `[v2]`.

```
henka-council/                                  # the repo + plugin source
├── .claude-plugin/
│   └── plugin.json                              # version, name, author, license
├── .mcp.json                                    # placeholder; empty unless we pick MCP option B for git
├── .claude/
│   └── settings.json                            # tiered Bash allowlist enforcing autonomy levels
├── agents/                                      # six council agents + orchestrator
│   ├── orchestrator.md                          # Level 4, full tools, dispatches the others
│   ├── architect.md                             # Level 2, fork context
│   ├── scope-guardian.md                        # Level 2, fork context
│   ├── henkaten-detector.md                     # Level 1, fork context
│   ├── retrospective.md                         # Level 2, fork context
│   ├── qa-regression.md                         # Level 2, fork context (initially flagged "proposed")
│   └── rag-source.md                            # Level 1, fork context (initially flagged "proposed")
├── skills/                                      # seven user-facing slash commands [v2: was 5]
│   ├── council-kickoff/
│   │   └── SKILL.md                             # bootstraps .council/, calls trine-eval kickoff
│   ├── council-autorun/
│   │   └── SKILL.md                             # outer sprint loop wrapping trine-eval
│   ├── council-review/
│   │   └── SKILL.md                             # manual on-demand fan-out
│   ├── council-retro-mini/                      # [v2/R7] per-sprint, automatic, ≤30s
│   │   └── SKILL.md
│   ├── council-retro/
│   │   └── SKILL.md                             # [v2/R7 revised] per-cycle PDCA-shaped (every-N sprints)
│   ├── council-jishuken/                        # [v2/R7] per-period, user-invoked reflection workshop
│   │   └── SKILL.md
│   └── council-detect/
│       └── SKILL.md                             # on-demand henkaten detection
├── rules/
│   └── council-conventions.md                   # the 12 governance rules (Section 2.5; Rule 1 revised per R4)
├── instructions/                                # behavioral constraints (source §12)
│   ├── controlled-artifacts.md
│   ├── evidence-first.md                        # [v2] revised: re-runnable verification required
│   ├── human-approval.md                        # [v2] revised: nemawashi walkthrough for major
│   ├── andon-protocol.md                        # [v2/R2,R3] thank-the-puller, swarming, alert vs stop
│   └── prompt-injection-defense.md
├── templates/                                   # output templates
│   ├── council-review-report.md
│   ├── course-correction.md
│   ├── retrospective-mini.md                    # [v2/R7]
│   ├── retrospective-pdca.md                    # [v2/R7] Plan/Do/Check/Act sections explicit
│   ├── jishuken-workshop.md                     # [v2/R7]
│   ├── nemawashi-position-paper.md              # [v2/R5]
│   ├── dispatch-envelope.md                     # standardized subagent dispatch template
│   └── contracts-first-standard-work.json
├── schemas/                                     # 11 JSON Schemas [v2: was 10]
│   ├── council-config.schema.json
│   ├── council-manifest.schema.json
│   ├── henka-record.schema.json                 # [v2] adds change_origin, andon_signal, yokoten, verification
│   ├── decision-log-entry.schema.json           # [v2] adds reversibility, effective_autonomy_at_decision
│   ├── standard-work.schema.json
│   ├── audit-log-entry.schema.json
│   ├── human-approval-log-entry.schema.json
│   ├── conflict-resolution-entry.schema.json
│   ├── evidence-index.schema.json
│   ├── integration-signal.schema.json
│   └── effective-autonomy.schema.json           # [v2/R10] effective autonomy state observable to other systems
├── hooks/
│   ├── enforce-append-only.sh                   # PreToolUse: block in-place edit of protected .jsonl files
│   ├── enforce-reversibility.sh                 # [v2/R9] PreToolUse: deny irreversible commands at L<5
│   ├── log-tool-call.sh                         # PostToolUse: append to .council/audit-log.jsonl
│   ├── session-stopped-marker.sh                # Stop: mark uncommitted sprint state
│   └── win/                                     # [v2.1] PowerShell equivalents for Windows
│       ├── enforce-append-only.ps1
│       ├── enforce-reversibility.ps1
│       ├── log-tool-call.ps1
│       └── session-stopped-marker.ps1
├── scripts/                                     # ancillary tooling (Python preferred for cross-platform)
│   ├── validate-council-config.py
│   ├── validate-henka-record.py
│   ├── validate-decision-log.py
│   ├── append-henka.py                          # safe append helper that validates before writing
│   ├── append-decision.py                       # ditto
│   ├── compute-evidence-class.py
│   ├── update-effective-autonomy.py             # [v2/R10] writes .council/state/effective-autonomy.json
│   └── run-verification.py                      # [v2/R4] re-runs an `observed` claim's verification command
├── README.md                                    # user-facing intro + install instructions
├── LICENSE
├── CLAUDE.md                                    # plugin-side CLAUDE.md (loaded when council skills run)
└── docs/
    ├── phase-0-proposal.md                      # v1 (historical)
    ├── phase-0-proposal-supplement.md           # supplement (historical, approved)
    ├── phase-0-proposal-v2.md                   # this document (authoritative)
    └── architecture.md                          # post-Phase-0 derivative diagram (future)
```

**`.council/` runtime state directory** (created by `/council-kickoff`, lives in the *target* project, not the plugin):

```
.council/
├── config.json
├── council-manifest.json
├── henka-register.jsonl                         # append-only
├── decision-log.jsonl                           # append-only
├── audit-log.jsonl                              # append-only (PostToolUse hook)
├── standard-work.json
├── course-corrections/
│   └── after-sprint-{NN}.md                     # one per sprint boundary
├── proposed/                                    # [v2/R5] nemawashi position papers (one per major decision)
│   ├── DEC-{NNNN}.md
│   └── archive/                                 # [v2.1] ratified or superseded position papers (kept for decision-log resolvability)
├── retrospectives/
│   ├── sprint-{NN}-mini.md                      # [v2/R7] per-sprint capture
│   └── full-{date}.md                           # per-cycle PDCA
├── jishuken/                                    # [v2/R7] per-period reflection workshops
│   └── <topic>-<date>.md
├── sessions/                                    # compacted session notes
│   └── <UTC-ISO8601>.md
└── state/                                       # [v2/R10] live state observable by external systems
    └── effective-autonomy.json
```

**Notes on the layout:**

- `agents/` contains seven files (six council agents + the orchestrator). The orchestrator is itself an agent file, dispatched by skills at Level 4.
- `skills/` is the user surface: every slash command corresponds to one skill. No skill calls another skill directly — they all dispatch agents via `Task`.
- `instructions/` are behavioral constraint files referenced from agent and skill files via `@instructions/<file>.md`.
- `templates/` provides the markdown shapes for outputs and the standard-work JSON template.
- `schemas/` holds JSON Schema definitions for every state file.
- `hooks/` and `.claude/settings.json` together implement the autonomy enforcement layer (Section 9).
- `scripts/append-henka.py` and `scripts/append-decision.py` are the **only** sanctioned write paths to the protected jsonl files. They validate before appending and call `git add` so every entry becomes a tracked commit candidate. The PreToolUse hook (Section 9.4) blocks any other write path.

---

## 5. State Model and File Inventory

Updated from v1. Adds: `proposed/` (R5), `jishuken/` (R7), `state/effective-autonomy.json` (R10), per-sprint mini retrospectives (R7).

### 5.1 `.harness/` — Sprint Execution State (Owned by trine-eval; read-only to council)

Unchanged from v1. Council reads only.

| File | Purpose | Council access |
|---|---|---|
| `config.json` | Project configuration | Read-only; council writes the optional `governance` key only at kickoff |
| `spec.md` | Product specification | Read-only |
| `features.json` | Canonical feature list — **SACRED** | Read-only |
| `sprints.json` | Sprint plan with dependencies | Read-only |
| `sprint-state.json` | Current sprint status | Read-only |
| `progress.md` | Human-readable progress | Read-only |
| `contracts/sprint-{NN}.md` | Sprint contracts | Read-only |
| `contracts/sprint-{NN}.tasks.json` | Machine-readable taxonomy (Phase 2) | Read-only |
| `evals/sprint-{NN}-r{R}.md` | Evaluation reports | Read-only |
| `evals/sprint-{NN}-r{R}-t{T}.md` | Trial-loop eval reports (Phase 2) | Read-only |
| `transcripts/sprint-{NN}-r{R}.json` | Structured transcripts (Phase 2) | Read-only |
| `regression/regression.json` | Graduated regression invariants (Phase 2) | Read-only |

### 5.2 `.council/` — Governance State (Owned by henka-council)

| File | Purpose | Write access |
|---|---|---|
| `config.json` | Governance settings | council-kickoff; subsequent changes require Level 5 |
| `council-manifest.json` | Active council composition | council-kickoff and council-autorun |
| `henka-register.jsonl` | **Append-only** log of Henkaten records | `scripts/append-henka.py` only |
| `decision-log.jsonl` | **Append-only** log of all decisions | `scripts/append-decision.py` only |
| `audit-log.jsonl` | **Append-only** action-level trace of all tool calls | PostToolUse hook only |
| `standard-work.json` | Evolving process improvement profile | retrospective proposes; user approves; orchestrator writes |
| `course-corrections/after-sprint-{NN}.md` | One per sprint boundary | orchestrator writes during autorun |
| `proposed/DEC-{NNNN}.md` | **[v2/R5]** Nemawashi position papers — one per major decision under deliberation | orchestrator writes during nemawashi walkthrough |
| `retrospectives/sprint-{NN}-mini.md` | **[v2/R7]** Per-sprint capture (Learning Points + Pattern Observations only) | retrospective agent writes via `Task` output and orchestrator persists |
| `retrospectives/full-{date}.md` | Per-cycle PDCA (every-N sprints by default 5) | retrospective agent writes; orchestrator persists |
| `jishuken/<topic>-<date>.md` | **[v2/R7]** Per-period reflection workshops; reflection-only, no standard-work proposals | retrospective agent writes; orchestrator persists |
| `sessions/<timestamp>.md` | Compacted session notes (≤500 words each) | orchestrator on `/compact` invocation |
| `state/effective-autonomy.json` | **[v2/R10]** Live effective autonomy state observable by external systems | `scripts/update-effective-autonomy.py` only |

### 5.3 Append-Only Enforcement

[src §9 lines 929–935] — unchanged from v1.

- **`henka-register.jsonl`**: never delete or modify existing entries. Status updates are append-only at the entry level — the original entry remains; a new entry with the same `henka_id` and updated `status` is appended (the latest entry wins on read).
- **`decision-log.jsonl`**: append only.
- **`audit-log.jsonl`**: append only.

The PreToolUse hook (Section 9.4) enforces this by blocking `Write` and `Edit` operations against these files. The only sanctioned write path is `scripts/append-*.py` which uses Bash with `>>` redirection.

### 5.4 Ownership Rules

| Path | Owner | Modification Rule |
|---|---|---|
| `.harness/*` | trine-eval | Council reads only; modifications require Level 5 approval and are logged as a course correction |
| `.harness/config.json` `governance` key | henka-council | Council writes once at kickoff; subsequent changes require Level 5 |
| `.council/decision-log.jsonl`, `henka-register.jsonl`, `audit-log.jsonl` | henka-council | Append-only; enforced by hook |
| `.council/course-corrections/`, `retrospectives/`, `jishuken/` | henka-council | Orchestrator writes; no append-only constraint (each file is per-sprint or per-workshop) |
| `.council/proposed/` | henka-council | Orchestrator writes during nemawashi walkthrough; **moved to `proposed/archive/` (with audit-log entry) when DEC ratifies or supersedes** so `decision-log.jsonl` `nemawashi_walkthrough_version` paths remain resolvable |
| `.council/standard-work.json` | henka-council | Retrospective proposes; user approves at Level 5; orchestrator writes |
| `.council/sessions/` | henka-council | Orchestrator writes on compaction |
| `.council/state/effective-autonomy.json` | henka-council | `scripts/update-effective-autonomy.py` only |

---

## 6. Henkaten Taxonomy — 4M Lens with Sub-types (R8)

Per supplement R8, the taxonomy is re-rooted: **4M (Man / Machine / Material / Method) is the primary lens**; the 12 categories inherited from v1 become sub-types. New Man-axis sub-types are added per the recommended Q18 default (`agent-capability-change` in v0.1; `evaluator-bias-change` deferred to v0.2).

### 6.1 The 4M Lens (Primary)

| 4M Axis | Definition for an Agentic System | Sub-types in v0.1 |
|---|---|---|
| **Man** | Capability / behavior of agents and reviewers — model upgrades, prompt-template revisions, evaluator behavior changes, who is reviewing | `agent-capability-change` (NEW v2) |
| **Machine** | Runtime infrastructure — Claude Code version, plugin versions, MCP server availability, runtime characteristics | `tool-environment-change`, `dependency-change` |
| **Material** | Source documents, datasets, configuration values, dependencies, the project's own source code | `source-material-change`, `requirement-change` |
| **Method** | Process — contract templates, evaluation rubrics, retry logic, sprint methodology, governance rules | `scope-change`, `method-process-change`, `measurement-criteria-change`, `schedule-priority-change`, `risk-compliance-change`, `quality-defect-anomaly`, `retrospective-improvement`, `architectural-discovery` |

### 6.2 Thirteen Sub-types (12 from v1 + 1 new Man-axis)

| # | 4M | Sub-type | Description | Detection Signals | Default Impact | Recommended Agents | Human Review |
|---|---|---|---|---|---|---|---|
| 6.2.1 | Man | **`agent-capability-change`** **(NEW)** | A council agent's behavior or capability shifted — model version upgrade, prompt-template revision, agent-file edit, plugin version bump | Plugin manifest diff, agent file diff, model version diff, observable behavior change in subagent output | actionable | henkaten-detector, retrospective | Always for unscheduled changes |
| 6.2.2 | Material | source-material-change | Source documents, specifications, reference material, or data inputs added/modified/superseded | File mtime, git diff on source dirs, version number changes | informational → blocking | architect, scope-guardian | If affects requirements traceability |
| 6.2.3 | Material | requirement-change | A requirement added/modified/removed/reinterpreted since last sprint | features.json diff, spec.md changes, user requests, evaluator finding unstated requirements | actionable → blocking | scope-guardian, architect | Any removal or reinterpretation |
| 6.2.4 | Method | scope-change | Boundary of in/out of project or current sprint shifted | sprints.json diff, contract criteria expanding beyond spec, evaluator flagging out-of-scope work | actionable → blocking | scope-guardian, architect | Any expansion beyond original features.json |
| 6.2.5 | Machine | tool-environment-change | Development tools, runtime, model capabilities, extensions changed | Package version changes, plugin updates, subagent behavior changes, new tool availability | informational; blocking if relied-upon capability removed | architect | If affects reproducibility |
| 6.2.6 | Method | method-process-change | Development process, evaluation criteria, or workflow steps modified | Contract template changes, rubric changes, retry-logic changes, standard-work updates | informational → actionable | retrospective, architect | Yes, for evaluation criteria or governance rule changes |
| 6.2.7 | Method | measurement-criteria-change | How success is measured changed | Contract criteria diverging from spec, evaluator suggesting new criteria, weight rebalancing | actionable | scope-guardian, retrospective | If criteria change affects already-passed sprints |
| 6.2.8 | Method | schedule-priority-change | Sprint ordering, priorities, or timeline expectations shifted | User requesting reorder, dependency conflicts, complexity estimates proven wrong | actionable → blocking | architect, scope-guardian | For sprint reordering or priority changes |
| 6.2.9 | Method | risk-compliance-change | New risk identified or compliance requirement changed | Evaluator security flags, edge cases, regulatory changes | actionable → high-risk | architect, henkaten-detector | Always for compliance |
| 6.2.10 | Method | quality-defect-anomaly | Unexpected failure/regression/anomaly outside normal eval criteria | Evaluator unexpected behaviors, gate criteria failing in novel ways, architectural inconsistencies, **verification re-run divergence (R4)** | actionable → blocking | architect, retrospective | If affects controlled artifacts |
| 6.2.11 | Machine | dependency-change | A sprint dependency changed (depended-upon failed, new dependency discovered) | sprint-state.json showing failed dependency, implementation revealing undocumented coupling | blocking if failed; actionable if new | architect, scope-guardian | If failure requires sprint reordering |
| 6.2.12 | Method | retrospective-improvement | Pattern/learning emerged suggesting process improvement, not defect fix | Recurring failure patterns, evaluator consistently flagging similar issues, efficiency opportunities | informational | retrospective | Before applying to standard work |
| 6.2.13 | Method | architectural-discovery | Implementation revealed architectural constraints/patterns/opportunities not visible during planning | Sprint requiring structural changes, evaluator noting architectural concerns, cross-cutting concerns emerging | actionable → blocking | architect, retrospective | If discovery requires plan-level changes |

### 6.3 Active vs Passive Distinction (R1)

Every henka record carries a `change_origin` field:

- **`active` (henkoten 変更点)** — the change was deliberately initiated. Examples: user-requested sprint reorder, intentional model-version upgrade, scheduled tool environment update. Pre-flagged; detection is targeted.
- **`passive` (henkaten 変化点 in the strict sense)** — the change emerged unbidden. Examples: tool drift, agent capability degradation, source material updated upstream, dependency vulnerability disclosed. Detection is ambient; needs broader watching.

Detection-burden asymmetry: **passive changes default to lower confidence and lower impact unless corroborated by a second signal.** Active changes default to whatever the originating signal (user request, version diff) provides.

### 6.4 Confidence Calibration Table

[src §6 lines 584–596] — unchanged from v1, with one addition for the new Man-axis sub-type.

| Sub-type | High confidence when | Low confidence when |
|---|---|---|
| `agent-capability-change` (NEW) | Plugin manifest diff or agent file diff confirms change | Behavior change observed but no diff confirms |
| `source-material-change` | File diff confirms content change | Only timestamp changed |
| `requirement-change` | Explicit user request or spec edit | Evaluator implied unstated requirement |
| `scope-change` | features/sprints.json modified | Contract criteria expanded ambiguously |
| `tool-environment-change` | Version/capability confirmed | Behavior change without confirmation |
| `quality-defect-anomaly` | Deterministic failure reproduced; or **verification re-run diverges from agent's reported observation (R4)** | Single intermittent failure |
| `dependency-change` | sprint-state shows explicit fail | Suspected but unconfirmed coupling |

Low-confidence detections classify as `impact_level: "informational"` unless corroborated by a second signal.

### 6.5 Impact Levels and Response Types (Revised per R3)

**Impact levels (ordered by severity):**

- `informational`: Noted, no action required. Response: log-only.
- `actionable`: Requires attention but does not block. Response: auto-correct or propose-to-user.
- `blocking`: Cannot proceed until resolved. Response: andon `alert` (swarming, takt-bounded) → escalates to `stop` if unresolved.
- `high-risk`: Safety/compliance/integrity concern. Response: andon `stop` immediately.

**Response types:**

- `log-only`: Record the change-point, no action needed.
- `auto-correct`: Orchestrator applies minor reversible correction (Level 3).
- `propose-to-user`: Write course correction proposal; minor → single-prompt approval; major → nemawashi walkthrough (R5).
- `escalate`: Flag for immediate human review with full evidence.
- **`andon-alert` (NEW, R3)**: Sprint flow pauses. Swarm dispatched. Takt-bounded resolution window (default **10 minutes wall-clock (v2.1: raised from 5)**; configurable per sprint). If swarm resolves within bound, sprint resumes with a logged decision; if not, escalates to `andon-stop`.
- **`andon-stop` (NEW, R3)**: Sprint flow halts. Full investigation. User must resume.

### 6.6 Custom Categories

[src §19 lines 1623–1631] — unchanged from v1. Custom sub-types live in `.council/config.json`:

```json
{
  "custom_henkaten_categories": [
    {
      "category_id": "custom-rag-corpus-drift",
      "fourM_axis": "Material",
      "description": "RAG corpus content drift detected via document hash comparison",
      "detection_signals": ["document hash differs from indexed snapshot"],
      "default_impact_level": "actionable",
      "recommended_agents": ["rag-source", "scope-guardian"]
    }
  ]
}
```

Custom sub-types are considered alongside the 13 built-in sub-types during classification. Each custom sub-type must declare its 4M axis.

### 6.7 Scheduled-vs-Unscheduled Suppression Rule for `agent-capability-change` (NEW v2.1)

During an active sprint, file edits to `agents/`, `instructions/`, `templates/`, `skills/`, `hooks/`, `scripts/`, or `schemas/` that fall **within the active sprint's declared scope** are *scheduled* — they are the deliverables, not change-points, and do NOT generate a Henkaten record. Edits **outside** sprint scope (a stray `agents/` change while the active sprint targets `skills/`) are *unscheduled* and fire normally as `agent-capability-change` Henkaten with `change_origin: passive`.

henkaten-detector determines sprint scope by reading (in priority order):

1. `.harness/contracts/sprint-{NN}.tasks.json` (Phase 2; canonical machine-readable scope)
2. `.harness/contracts/sprint-{NN}.md` `Files in scope` section (parsed heuristically)
3. `.harness/sprints.json` entry for the active sprint (fallback)

If none are available the suppression rule is bypassed (fail-safe — every edit fires) and the agent emits a `coverage` warning. The suppression rule is bypassed entirely outside sprint execution windows (between sprints, during `/council-review`, ambient SessionStart hook detection) — those edits are always unscheduled by definition.

**Rationale:** without this rule, henka-council's own self-build (Sprints D2–S6) would fill the henka-register with hundreds of low-value records describing the very deliverables those sprints produce.

---

## 7. Agent Contracts

For each agent: role, autonomy level, tools, input files, output structure, prohibitions, graceful degradation, dispatch invocation. Revised in v2 to add the **andon authority** (R2) and **genchi-genbutsu evidence** (R4) to every agent.

### 7.0 Capabilities Common to Every Council Agent (NEW in v2)

Every council agent inherits the following capabilities and obligations, inherited via `instructions/andon-protocol.md` and `instructions/evidence-first.md` referenced from each agent file:

#### 7.0.1 Andon authority (R2)

Every council agent — not just the orchestrator — can return a structured andon signal in its output:

```json
{
  "andon_signal": {
    "type": "alert" | "stop",
    "reason": "string — concise statement of what triggered the signal",
    "evidence": ["string — file:line or command output references"],
    "swarm_request": ["agent_id_1", "agent_id_2"]
  }
}
```

The orchestrator MUST honor `andon_signal: stop` immediately. `andon_signal: alert` triggers the swarming protocol (see Section 8.2 Step 1C).

The orchestrator's first response to any andon signal is a **thank-the-puller acknowledgment** to the escalating agent, written verbatim before any analytical response. This is enforced by template — the orchestrator skill has an "andon acknowledgment" section that runs before any analysis. Strictly honored; pull-rate is tracked per agent in the audit log (Q14).

#### 7.0.2 Genchi-genbutsu evidence (R4)

Every claim in every agent output must include `evidence_class`, `confidence`, and — for `observed` claims — a `verification` field containing a re-runnable command:

```json
{
  "claim": "...",
  "evidence_class": "observed" | "inferred" | "speculative",
  "confidence": "high" | "medium" | "low",
  "verification": "bash command, python expression, grep, or git diff that reproduces the observation"
}
```

`inferred` claims must explicitly cite the chain of observed claims they derive from. `speculative` claims cannot be the basis for `propose-to-user` or `escalate` actions; only `log-only` is permitted.

**Verification syntax allowlist (NEW v2.1):** to bound the blast radius of executing agent-authored verification commands, `verification` strings MUST match one of the following allowlisted forms; arbitrary Bash/Python is rejected by `scripts/run-verification.py`:

| Allowed prefix | Purpose | Example |
|---|---|---|
| `git diff …`, `git show …`, `git log …`, `git status`, `git branch …`, `git ls-files …` | Read-only git inspection | `git diff main..HEAD -- features.json` |
| `grep …`, `rg …` (read-only flags only) | Content search | `grep -n "feature_id" .harness/features.json` |
| `cat …`, `head …`, `tail …` | File read | `cat .harness/sprints.json` |
| `jq …` (against an explicit file path; no `-i` in-place) | Structured JSON read | `jq '.sprints | length' .harness/sprints.json` |
| `python -m json.tool …`, `python scripts/validate-*.py …` | Schema validation only | `python scripts/validate-henka-record.py .council/henka-register.jsonl` |
| `test …`, `[ … ]` (POSIX file tests) | File-existence checks | `test -f .council/config.json` |

Disallowed: any command that writes (`>`, `>>`, `tee`, `Write`, `Edit`), any network call (`curl`, `wget`, `gh`, `git push`, `git fetch`), any execution of project source (`bun run`, `uv run …` other than the allowlisted validators), shell redirects, pipe-to-shell, `eval`, `exec`. `scripts/run-verification.py` enforces a per-command timeout (default 10s) and CPU/memory bound, runs with `cwd=<project-root>` only, and rejects non-allowlisted strings before invocation.

The orchestrator's fan-in step (Section 8.2 Step 1C) picks one random `observed` claim per agent output and re-runs its verification via `scripts/run-verification.py`. If the re-run diverges from the agent's report, that divergence is itself a Henkaten — `quality-defect-anomaly` with high impact — and is logged. If the verification string fails the allowlist, the agent's output is rejected and the agent is asked to resubmit with conformant verification — the rejection itself is logged as an `agent-capability-change` Henkaten (informational).

### 7.1 Orchestrator (Henkaten Council Orchestrator)

[src §4.1 lines 135–157]

| Field | Value |
|---|---|
| Autonomy | Level 4 (coordinate sequences under supervision) — subject to dynamic floor (R10) |
| Tools | `Read, Glob, Grep, Bash, Write, Task` |
| Context | `inherit` — the orchestrator is the conductor; it must see what the user typed |
| Sub-agents it dispatches | architect, scope-guardian, henkaten-detector, retrospective, qa-regression (if enabled), rag-source (if enabled), plus any `custom_agents` |
| Defined in | `agents/orchestrator.md` |

**Responsibilities:**

- Routes analytical work to bounded worker agents (never performs analysis itself when a worker should)
- Applies minor *reversible* corrections (Level 3 actions); irreversible actions auto-escalate to L5 (R9)
- Presents major corrections via the **nemawashi-shaped walkthrough** (Section 8.2 Step 1D, per R5)
- Manages `decision-log.jsonl` and `henka-register.jsonl` via `scripts/append-*.py`
- Honors andon signals from any agent; runs the swarming protocol (R3)
- Spot-checks one random `observed` claim per fan-in by re-running its verification (R4)
- Surfaces yokoten records as adaptation prompts during pre-sprint check (R6)
- Maintains the dynamic autonomy floor and writes `state/effective-autonomy.json` (R10)
- Compacts context between sprints (writes to `.council/sessions/<timestamp>.md`)
- Maximum 4 agents per review (the bounded fan-out rule)

**Prohibited:**

- Performing analysis that a worker agent should do
- Modifying `features.json`, `spec.md`, `sprints.json` without Level 5 approval
- Self-approving or fabricating evidence
- Passing internal reasoning to subagents (subagent dispatches use ONLY file paths + structured task)
- Creating unbounded retry loops
- Filtering or second-guessing andon signals from agents (Q14)
- Auto-applying any irreversible action regardless of nominal autonomy (R9)

**Dispatch invocation pattern (from a skill, using `templates/dispatch-envelope.md`):**

```python
Task(
    subagent_type="henka-council:architect",
    description="Architect review for sprint NN",
    prompt="""You are the Architect agent. Review sprint {NN} against spec/plan coherence.

Inputs (read-only):
- .harness/sprint-state.json
- .harness/evals/sprint-{NN}-r{R}.md
- .harness/contracts/sprint-{NN}.md
- .harness/spec.md
- .harness/features.json
- .harness/sprints.json
- Project source code structure (limit to last touched paths)

Output: Coherence Rating, Drift Indicators, Dependency Health, Proposed Amendments, Risk Flags.
Format per templates/architect-output.md.

Common obligations (inherited from instructions/andon-protocol.md and instructions/evidence-first.md):
- DO NOT modify any files. DO NOT invoke other agents directly.
- DO NOT propose adding features not in features.json.
- Cite specific evidence for every claim. Classify confidence (observed/inferred/speculative).
- For every `observed` claim, include a re-runnable `verification` command.
- You may issue an `andon_signal: alert | stop` if you detect a blocking condition; include `swarm_request` if needed.
"""
)
```

The orchestrator passes ONLY file paths + structured constraints; never internal reasoning.

### 7.2 Architect

[src §4.2 lines 160–193]

| Field | Value |
|---|---|
| Autonomy | Level 2 (propose only) |
| Tools | `Read, Glob, Grep` |
| Context | `fork` |
| Defined in | `agents/architect.md` |

**Inputs (read-only):** `.harness/sprint-state.json`, `evals/sprint-{NN}-r{R}.md`, `contracts/sprint-{NN}.md`, `spec.md`, `features.json`, `sprints.json`, project source structure.

**Outputs:** Coherence Rating (1–5), Drift Indicators (specific divergences with `verification` commands), Dependency Health, Proposed Amendments (bounded, evidence-cited), Risk Flags. Optional `andon_signal`.

**Invoked:** After every sprint completion, before next sprint begins.

**Prohibited:** Modify any files. Approve own recommendations. Invoke other agents. Propose adding features not in original `features.json`. Make claims without `verification` commands when claiming `observed`.

**Graceful degradation:** Missing `spec.md` → assess coherence against contracts only, note reduced confidence. Missing `sprints.json` → skip dependency check, note in `missing_evidence`. Missing eval reports → status: `partial`. Missing source code → skip structural assessment.

### 7.3 Scope Guardian

[src §4.3 lines 196–225]

| Field | Value |
|---|---|
| Autonomy | Level 2 |
| Tools | `Read, Glob, Grep` |
| Context | `fork` |
| Defined in | `agents/scope-guardian.md` |

**Inputs:** `features.json` (current vs original), contracts, evals, sprints.json, spec.md, `henka-register.jsonl`.

**Outputs:** Feature Integrity Check, Scope Drift Detection, Unauthorized Changes, Feature Status Assessment, Correction Proposals with `verification` commands. Optional `andon_signal`.

**Invoked:** After every sprint completion. Also if `features.json` modification detected.

**Prohibited:** Modify `features.json` (MOST CRITICAL constraint). Modify any files. Interpret "close enough" as acceptable — exact string matching required. Recommend adding features (only flag gaps for human decision).

**Graceful degradation:** Missing `features.json` → status: `error` (cannot function). Missing `sprints.json` → skip dependency-based drift. Missing eval → feature-list-only check.

### 7.4 Henkaten Detector

[src §4.4 lines 228–256]

| Field | Value |
|---|---|
| Autonomy | Level 1 |
| Tools | `Read, Glob, Grep` |
| Context | `fork` |
| Defined in | `agents/henkaten-detector.md` |

**Inputs:** evals, contracts, sprint-state.json, sprints.json, henka-register (avoid duplicates), decision-log, **Phase 2 trine-eval transcripts (`transcripts/sprint-{NN}-r{R}.json`)**, plugin manifest, agent files (for `agent-capability-change` detection per R8/Q18).

**Outputs:** New Change Points (henka_id, **`change_origin: active | passive`** (R1), 4M axis, sub-type, impact_level, description, affected_artifacts, response_type, evidence with `verification`, optional `swarm_request`), Pattern Observations across sprint history, Escalation Flags. Optional `andon_signal`.

**Invoked:** After every sprint completion. Pre-sprint optional. On-demand via `/council-detect`. Also fires on Claude Code hooks `SessionStart` and `PostToolUse` for ambient passive-change detection.

**Prohibited:** Modify any files. Determine the response (only classify). Duplicate existing records. Classify ambiguous observations as `blocking` without strong evidence. Conservative impact assessment (err toward lower).

**Graceful degradation:** Missing eval → status: `partial`. Missing henka-register → first run. Missing sprint-state.json → skip cross-sprint pattern detection.

### 7.5 Retrospective

[src §4.5 lines 259–289] — significantly revised in v2 to support three cadences (R7).

| Field | Value |
|---|---|
| Autonomy | Level 2 |
| Tools | `Read, Glob, Grep` |
| Context | `fork` |
| Defined in | `agents/retrospective.md` |

**Inputs:** All evals, sprint-state, all contracts, henka-register, decision-log, standard-work.json, prior retrospectives, **Phase 2 trine-eval `summary.md` cross-sprint metrics**.

**Three modes (selected by skill that dispatches):**

| Mode | Dispatched By | Output | Standard-Work Proposals? |
|---|---|---|---|
| **Mini** | `/council-retro-mini` (per-sprint, ≤30s) | Learning Points, Pattern Observations only | **No** — capture-only |
| **PDCA** | `/council-retro` (per-cycle, every-N sprints) | Plan / Do / Check / Act sections, Standard Work Proposals, Kaizen Recommendation | Yes |
| **Jishuken** | `/council-jishuken` (per-period, user-invoked) | Reflection Notes, Open Questions, Hypotheses for Future Investigation | **No** — reflection-only (Q16; v0.2 may add an explicit promotion path if needed) |

**Yokoten (R6, all modes):** When closing a Henkaten record, the retrospective agent populates the new `yokoten` block of the henka-record schema (Section 11) — `applicable_to_subsequent_sprints`, `adaptation_notes`. Each subsequent sprint's pre-flight surfaces these to the user as adaptation prompts (Q17: default to user-authored adaptation, with agent-drafted starting point).

**Prohibited:** Modify `standard-work.json` directly (only propose). Modify any files. Recommend process changes without 2+ sprints of evidence (or 1 with strong deterministic evidence). Recommend expanding scope or adding features. Must distinguish product issues (Generator's concern) from process issues. In `mini` mode, may NOT emit standard-work proposals.

**Graceful degradation:** Missing evals → status: `partial`. Missing standard-work → blank profile. Only 1 sprint complete → learning points only, defer pattern analysis.

### 7.6 QA Regression

[src §4.6 lines 292–322]

| Field | Value |
|---|---|
| Autonomy | Level 2 |
| Tools | `Read, Glob, Grep` |
| Context | `fork` |
| Defined in | `agents/qa-regression.md` |
| Status | **Initially `proposed` (CC-001 from source spec)**; agent file ships but is not in default fan-out (Q4 default) |

**Inputs:** ALL evaluation reports (historical comparison is primary), all contracts, sprint-state, features, spec, sprints.json, henka-register, project source, **Phase 2 trine-eval `regression.json` graduated invariants**.

**Outputs:** Regression Detection (with `verification` per R4), Consistency Check, Integration Assessment, Criteria Drift Analysis, Accumulation Issues, Recommended Regression Tests. Optional `andon_signal`.

**Prohibited:** Modify any files. Re-run or override evaluator grades. Distinguish actual regressions from incomplete features. Every regression claim must cite eval report section from sprint A vs sprint B and include a `verification` command.

### 7.7 RAG Source

[src §4.7 lines 326–357]

| Field | Value |
|---|---|
| Autonomy | Level 1 |
| Tools | `Read, Glob, Grep` |
| Context | `fork` |
| Defined in | `agents/rag-source.md` |
| Status | **Initially `proposed` (CC-001 from source spec)**; agent file ships but is not in default fan-out (Q4 default) |

**Inputs:** spec, features, config.json, source material directories, henka-register, decision-log, other agents' outputs (when invoked for verification).

**Outputs:** Source Inventory, Traceability Check, Citation Verification (confirmed/unsupported/missing/partial), Source Change Detection, Relevant Context Surfaced. Optional `andon_signal`.

**Three functions:** Retrieval, Verification, Change detection.

**Prohibited:** Modify any files. Interpret requirements (only verify traceability). Fabricate citations. Assume missing source means requirement is invalid.

### 7.8 Archaeologist (Pre-Project Utility — Out of Council Loop)

[src §4.8 lines 361–386] — deferred to v0.2 per Q11 default.

### 7.9 Prompt Forge (Pre-Processing Utility — Out of Council Loop)

[src §4.9 lines 389–415] — deferred to v0.2 per Q11 default.

---

## 8. Workflow Contracts (Skills)

Seven skills in v2 (was five in v1). Each skill is a `skills/<name>/SKILL.md` file with a body that documents the step-by-step procedure. Skills dispatch agents via `Task`. Skills do not call other skills directly.

### 8.1 `/council-kickoff` — Bootstrap Governance

[src §8.1 lines 641–688] — unchanged from v1.

| Field | Value |
|---|---|
| Defined in | `skills/council-kickoff/SKILL.md` |
| Frontmatter `allowed-tools` | `Read, Glob, Grep, Bash, Write, Task` |
| Invoked as | `/henka-council:council-kickoff` |

**Procedure:**

1. Check for existing state (re-bootstrap option, layer on existing `.harness/`, manual review)
2. Gather project context. Identify project type. Ask 1–2 clarifying questions.
3. Create `.council/config.json` with `project_type`, `council_agents`, `autonomy_levels`, `review_frequency`, `halt_conditions`, `correction_thresholds`, `henkaten_taxonomy_version: "2.0"`, `andon_takt_seconds: 600` (v2.1: raised from 300 to fit the four-agent sequential-dispatch swarm budget), `dynamic_autonomy_thresholds: {andon_stop_distinct_originators_required: 2, andon_stop_consecutive_count: 3, ...}`.
4. Create `.council/council-manifest.json` with `council_id: "COUNCIL-0001"`, list 4 (or 6 if CC-001 approved) core agents, `trigger_type: "kickoff"`, `status: "assembled"`.
5. Initialize remaining state: empty `henka-register.jsonl`, `decision-log.jsonl` with first entry, initial `standard-work.json`, directories for `course-corrections/`, `proposed/`, `retrospectives/`, `jishuken/`, `audit-log.jsonl`, `sessions/`, `state/effective-autonomy.json` initialized to `{level: 4, last_change: now, reason: "initial", restored_when: null}`.
5B. Git baseline: `git init` if needed; `git checkout -b project-{name}`; commit `.harness/` + `.council/` baseline. Message: `council-kickoff: baseline state (DEC-0001)`.
6. **Delegate to trine-eval planning** via `/trine-eval:harness-kickoff`. Detect contracts-first methodology. trine-eval creates `.harness/`.
6B. Write governance signal to `.harness/config.json`: `{governance: {enabled: true, plugin: "henka-council", council_state_path: ".council/", review_frequency: "every-sprint"}}`.
7. Present governance plan to user. Offer to start `/council-autorun`.

### 8.2 `/council-autorun` — Sprint Loop with Governance

[src §8.2 lines 691–842] — significantly revised in v2 to add yokoten review (R6), swarming protocol (R3), nemawashi walkthrough (R5), dynamic autonomy update (R10).

| Field | Value |
|---|---|
| Defined in | `skills/council-autorun/SKILL.md` |
| Frontmatter `allowed-tools` | `Read, Glob, Grep, Bash, Write, Task` |
| Invoked as | `/henka-council:council-autorun` |

**Procedure:**

**Step 0 — Load state.** Read `.harness/`, `.council/`, and `.council/state/effective-autonomy.json`. Determine starting sprint. If `.council/` missing → instruct user to run `/council-kickoff` first.

**FOR EACH SPRINT in `.harness/sprints.json`:**

**Step 1A — Pre-Sprint Henkaten Check.**

- Create sprint branch: `git checkout -b sprint-{NN}` if git available.
- `git diff` between main and current state for observed evidence.
- Check `.harness/` state changes (mtime vs last decision-log entry).
- Check for unresolved Henkaten records (status not `closed`).
- Check for user-modified project files outside governance.
- Plugin manifest diff (for `agent-capability-change` detection per R8).
- **Routing:**
  - Blocking/high-risk records exist → `andon_signal: stop` issued; HALT (Step 1F).
  - State changes detected → invoke henkaten-detector, classify findings (with `change_origin` per R1).
  - Actionable/informational records only → attach as context notes.
  - No changes → proceed normally.

**Step 1A.5 — Yokoten Review (NEW, R6).**

- Read all closed Henkaten records with non-empty `yokoten.applicable_to_subsequent_sprints`.
- For any record naming this sprint: surface to user as an "adaptation prompt" — *not* a copy-paste suggestion.
- Per Q17 default: the user (or, if user delegates, the retrospective agent) drafts the adaptation; the user reviews and ratifies.
- Adaptation logged as `yokoten.deployed_to[]` entry with timestamp, decision_id, and adaptation taken.
- This makes propagation observable in evidence rather than implicit in standard-work.json.
- **Ratify-once shortcut (NEW v2.1):** if a yokoten record names `applicable_to_subsequent_sprints: ["all"]` or names ≥3 sprints, the user may ratify the adaptation **once** with scope `applies_to_remaining: true`. The orchestrator then auto-applies the same adaptation per subsequent sprint with a single-prompt confirmation ("Apply yokoten DEC-{ID} to sprint NN as ratified? (yes/no)") rather than a fresh nemawashi walkthrough. The user can revoke the bulk ratification at any sprint boundary by answering `no`, which downgrades remaining sprints back to per-sprint ratification.

**Step 1B — Execute Sprint via trine-eval.** Invoke `/trine-eval:harness-sprint {NN}`. Wait for completion. trine-eval's loop runs internally:
- Contract negotiation (2 rounds max)
- Implementation
- Evaluation (forked-context evaluator)
- Retry loop
- Update `sprint-state.json` and `progress.md`
- Git checkpoint

The council does NOT enter trine-eval's loop. trine-eval is unaware of council during this step. The council picks up at completion.

**Step 1C — Council Review (Fan-Out → Fan-In with Andon and Verification).**

Check `review_frequency`:
- `every-sprint` → always convene
- `every-N-sprints` → convene if sprint % N == 0 OR sprint failed
- `on-failure-only` → convene only if sprint failed
- `manual-only` → skip; user must invoke `/council-review`

**Fan-out:** Dispatch each agent as an isolated subagent via `Task` using `templates/dispatch-envelope.md`. Pass ONLY file paths and structured constraints. Never pass orchestrator reasoning. Per Q6 default: sequential dispatch in v0.1; parallel as a config knob `dispatch_mode`.

```
Agent 1 — architect: dispatch
Agent 2 — scope-guardian: dispatch
Agent 3 — henkaten-detector: dispatch
Agent 4 — retrospective: dispatch (in `mini` mode for per-sprint capture)
Agents 5–6 — qa-regression, rag-source: dispatch IF enabled
Agents 7+ — custom_agents from config: dispatch
```

**Andon handling (NEW, R2/R3) — runs concurrently with fan-in:**

- If any agent returns `andon_signal: stop` → orchestrator immediately writes a thank-the-puller acknowledgment, halts the sprint loop, jumps to Step 1F.
- If any agent returns `andon_signal: alert` → orchestrator writes thank-the-puller acknowledgment, dispatches the **swarm**:
  - The originating agent + any agents named in `swarm_request` (capped at 4 per the bounded fan-out rule).
  - Takt-bounded resolution window: default 10 minutes wall-clock (`config.andon_takt_seconds`, v2.1: raised from 5 to fit four-agent sequential dispatch).
  - **Swarm dispatch is parallel by default (v2.1)** — even when `dispatch_mode: sequential` is set for routine fan-out, swarm dispatches use parallel `Task` calls so the takt budget is achievable. Rationale: swarming is the case where wall-clock latency matters and parallel pays off.
  - If swarm resolves within the bound → sprint resumes with a logged decision. Decision-log entry includes `andon_resolution: {originator, swarm, resolution, duration_seconds}`.
  - If not → alert escalates to `stop`. Orchestrator jumps to Step 1F.

**Fan-in:** Each agent's output is written by the orchestrator to `.council/course-corrections/after-sprint-{NN}.md` under that agent's section. Evidence-quality check: verify each agent provided `evidence_class`, `confidence`, `coverage`, and (for `observed` claims) `verification`. If agent returned `status: error` → log failure, skip that section, note gap.

**Verification spot-check (NEW, R4; v2.1 allowlist enforcement):** Per agent output, pick one random `observed` claim and re-run its `verification` command via `scripts/run-verification.py` (which enforces the v2.1 syntax allowlist; see §7.0.2). Log result to `audit-log.jsonl`. If re-run diverges from agent report → log a new `quality-defect-anomaly` Henkaten with high impact and `change_origin: passive`. If the verification string fails the allowlist → reject the agent's output, ask for resubmission, log an `agent-capability-change` Henkaten (informational).

**Henkaten Register Write Procedure:**
- Determine next `HK-NNNN` ID (read henka-register, find max, increment)
- Validate against `schemas/henka-record.schema.json` (now requires `change_origin`, optional `andon_signal`, optional `yokoten`)
- Set `status: "classified"`, `sprint_context: {NN}`
- Append via `scripts/append-henka.py`

**Lifecycle transitions:**
- `classified` → `assessed` → `responded` → `closed`

**Standard Work Evolution (per-cycle only — see Step 1D and §8.5):** Mini retrospectives capture only; standard-work proposals emerge in `/council-retro` (per-cycle), not here.

**Step 1D — Course Correction.**

Read `correction_thresholds` from `.council/config.json`.

**Reversibility check (NEW, R9):** Before classifying as minor or major, the orchestrator classifies the proposed action as `reversible | irreversible` per Section 2.4.2. **Irreversible actions auto-escalate to MAJOR regardless of nominal class.**

**MINOR (auto-apply, Level 3, reversible only):**
- Technical notes additions to next contract
- Clarifying evaluation criteria (weight change ≤10%)
- Updating `.council/` state files
- Lessons learned to `progress.md`
- Noting new dependencies (informational)
- Updating feature status pending → done

Single-prompt: "Apply minor correction X? (yes/no)" — fast path preserved (Q15 default: nemawashi for *major* only).

**MAJOR (Level 5 approval, nemawashi-shaped walkthrough per R5):**

- Sprint reordering
- `features.json` modifications
- `spec.md` amendments
- Criteria weight changes >10%
- Adding new sprints
- Architectural pivots
- Governance rule changes
- **Any irreversible action** (R9)

Walkthrough sequence:

1. **Stage 1 — Present.** Orchestrator writes a position paper to `.council/proposed/DEC-{NNNN}.md` (using `templates/nemawashi-position-paper.md`) containing the consensus chain agent-by-agent with evidence and `verification` commands. Surface to user: *"I've drafted a proposal at .council/proposed/DEC-{NNNN}.md. May I walk you through it?"*
2. **Stage 2 — Walk.** Sequential walkthrough, one agent's perspective at a time. After each: *"Does this agent's framing match your understanding? (yes / refine / disagree)"* — three handles, not two.
3. **Stage 3 — Align.** Surface any disagreements; revise the position paper (new file version with `-rev{N}` suffix); repeat Stage 2 if needed.
4. **Stage 4 — Ratify.** Once all agent perspectives are aligned with the user's framing, the formal approve/reject prompt is a confirmation, not a decision. *"All perspectives aligned. Apply DEC-{NNNN}? (yes/no)"*

The "implement rapidly" half of nemawashi is preserved: once Stage 4 ratifies, the application is immediate and observable in a single git commit.

Write `.council/course-corrections/after-sprint-{NN}.md` (always, regardless of minor/major mix).

**Git operations:**
- Minor corrections (reversible only): commit with `DEC-{ID}: {description}`
- Sprint PASS: present `git merge sprint-{NN} → main` for Level 5 approval. On approval: `git merge --no-ff`, tag `sprint-{NN}-complete`.
- Sprint FAIL: preserve branch for forensics; checkout main.
- `git push` and other irreversible commands: **denied by hook** (Section 9.4.2) regardless of approval level; the user must run them manually.

**Step 1E — Decision Logging.** Write entry to `decision-log.jsonl` via `scripts/append-decision.py` with: sequential `DEC-NNNN`, timestamp, `council_agents_involved`, `evidence_cited` (with `verification` commands), `decision_type`, `decision_outcome`, `applied_automatically`, `user_approval_required`, `affected_files`, `linked_henka_id`, `sprint_context`, `autonomy_level_used`, `effective_autonomy_at_decision` (R10), `reversibility` (R9), `nemawashi_walkthrough_version` (R5; null for minor).

If decision responds to henka records → set `linked_henka_id`, update record status to `responded` (or `closed` if fully resolved). If `closed` → retrospective agent populates `yokoten` block (R6).

**Step 1F — Halt Conditions Check.** From `config.halt_conditions`:
1. `blocking_henkaten`: any blocking record not closed → andon-stop, HALT
2. `max_consecutive_failures`: last N sprints all failed → HALT
3. `high_risk_henkaten`: any high-risk record not closed → andon-stop, HALT
4. `user_intervention_requested`: major correction pending and Stage 4 not ratified → HALT
5. **Andon escalation:** any `andon_signal: stop` received → HALT (R3)
6. **Dynamic autonomy floor breach:** if effective autonomy dropped per R10 rules, write to `state/effective-autonomy.json` via `scripts/update-effective-autonomy.py` and HALT (do not auto-resume).

Recovery options per condition documented; present to user when halting.

**Step 1G — Context Compaction.** Compact to ≤500 words. Runs unconditionally after every sprint.
- **Preserve:** sprint number, all verdicts, open Henkaten records, unresolved decisions, active halt conditions, standard-work changes this session, current effective autonomy.
- **Discard:** implementation details, tool call history, agent reasoning traces, full eval/report text, contract negotiation discussion.
- Write to `.council/sessions/<UTC-ISO8601>.md`.
- Source of truth: `.harness/` and `.council/` files (always re-read).

**Step 1H — Per-Sprint Mini Retrospective (NEW, R7).** Invoke `/council-retro-mini` inline (≤30s, automatic, no user input). Capture-only; appended to `.council/retrospectives/sprint-{NN}-mini.md`.

**Step 1I — Next Sprint or Exit.**
- More sprints + no halt → increment, return to Step 1A.
- Sprint count divisible by `cycle_length` (default 5) → invoke `/council-retro` (per-cycle PDCA) before next sprint.
- All sprints complete → final summary, suggest `/council-retro` (final cycle) and optionally `/council-jishuken`.
- Halted → present reason and evidence, wait for user input.

### 8.3 `/council-review` — Manual Review

[src §8.3 lines 845–857] — minor revision: now also runs the andon and verification spot-check protocols.

| Field | Value |
|---|---|
| Defined in | `skills/council-review/SKILL.md` |
| Allowed tools | `Read, Glob, Grep, Bash, Write, Task` |

Steps: Load context → fan-out → andon handling → fan-in (with verification spot-check) → present findings (nemawashi walkthrough for major) → log decisions → present summary.

Optional flag: `--restore-autonomy` to reset a dynamic-autonomy floor drop after the user has reviewed (R10).

### 8.4 `/council-retro-mini` — Per-Sprint Mini Retrospective (NEW v2/R7)

| Field | Value |
|---|---|
| Defined in | `skills/council-retro-mini/SKILL.md` |
| Allowed tools | `Read, Glob, Grep, Bash, Write, Task` |
| Cadence | Per-sprint, automatic, ≤30s |

The retrospective agent runs in `mini` mode — Learning Points and Pattern Observations only, no Standard Work Proposals. Output appended to `.council/retrospectives/sprint-{NN}-mini.md`. No user input required; runs inline at end of every sprint via Step 1H of `/council-autorun`.

### 8.5 `/council-retro` — Per-Cycle PDCA Retrospective (REVISED v2/R7)

[src §8.4 lines 860–877] — semantics revised: this is now the per-cycle PDCA retrospective (every-N sprints by default 5), not the per-sprint retrospective.

| Field | Value |
|---|---|
| Defined in | `skills/council-retro/SKILL.md` |
| Allowed tools | `Read, Glob, Grep, Bash, Write, Task` |
| Cadence | Per-cycle (every-N sprints; configurable), or final at end of project |

Comprehensive cross-sprint retrospective. Identifies patterns and proposes kaizen, structured as explicit Plan / Do / Check / Act sections (per `templates/retrospective-pdca.md`).

Steps: Load FULL history → invoke retrospective agent in `pdca` mode (cross-sprint scope) → invoke architect (supporting structural assessment) → synthesize report → present standard-work proposals via nemawashi walkthrough for Level 5 approval → log decisions → write `.council/retrospectives/full-{date}.md`.

**Integration with trine-eval:** Reads `.harness/summary.md` (cross-sprint summary) and `.harness/regression/regression.json` (graduated invariants).

### 8.6 `/council-jishuken` — Per-Period Reflection Workshop (NEW v2/R7)

| Field | Value |
|---|---|
| Defined in | `skills/council-jishuken/SKILL.md` |
| Allowed tools | `Read, Glob, Grep, Bash, Write, Task` |
| Cadence | Per-period, user-invoked only |

Self-study workshop. The user picks the topic. The council convenes a guided reflection focused on *learning* rather than *fixing*. Output is `.council/jishuken/<topic>-<date>.md` and is **explicitly excluded** from standard-work proposals — it's reflection, not corrective action (Q16: decoupled in v0.1; promotion to standard-work happens through the next `/council-retro` cycle which can read jishuken artifacts).

Steps: User declares topic → orchestrator invokes retrospective agent in `jishuken` mode + architect (supporting context) → guided reflection with three sections (Reflection Notes, Open Questions, Hypotheses for Future Investigation) → write `.council/jishuken/<topic>-<date>.md` → no decision-log entry beyond "jishuken workshop conducted on topic X".

**v2.1:** the `--reset-autonomy-floor` flag previously documented here is **removed**. The single canonical path to reset a dynamic-autonomy floor drop is `/council-review --restore-autonomy` (§8.3). Two paths created state-drift risk; jishuken is reflection-only and never modifies state.

### 8.7 `/council-detect` — On-Demand Detection

[src §8.5 lines 880–898] — minor revision to surface `change_origin`.

| Field | Value |
|---|---|
| Defined in | `skills/council-detect/SKILL.md` |
| Allowed tools | `Read, Glob, Grep, Bash, Write, Task` |

**Sensitivity thresholds (NOT everything is a Henkaten):**
- File touched but content unchanged → NOT a change-point
- Whitespace/formatting only → informational at most
- Comments/documentation added → informational unless reveals requirement change
- Sprint state updated by normal flow → NOT a change-point (expected)
- Config values within documented ranges → informational

Only classify as `actionable+` when change affects: requirements, features, sprint plan, evaluation criteria, source material content, or architectural constraints.

Steps: Load baseline → invoke henkaten-detector → review output, apply sensitivity thresholds → write new records (with `change_origin` per R1) → present findings.

---

## 9. Autonomy and Enforcement in Claude Code

How Levels 0–5 from Section 2.4 (with reversibility axis R9 and dynamic floor R10) map to concrete enforcement mechanisms.

### 9.1 Level Mapping

| Level | Enforcement Mechanism in Claude Code |
|---|---|
| **0 — Observe only** | Agent frontmatter `tools: Read, Glob, Grep` only. No `Write`, `Edit`, `Bash`. |
| **1 — Classify and recommend** | Same tools as Level 0. Output is the agent's response text only — no file write. |
| **2 — Propose drafts** | Agent frontmatter may include `Write` but the agent prompt restricts writes to `.council/course-corrections/<draft>.md` only. Hooks (Section 9.4) block writes to other paths. |
| **3 — Auto-apply minor (reversible only)** | Orchestrator skill has `Write, Bash` and writes to `.council/` working files. Permission rules in `.claude/settings.json` allow writes to `.council/*` paths automatically. Irreversible actions blocked by `enforce-reversibility.sh` hook (Section 9.4.2). |
| **4 — Coordinate sequences (reversible only)** | Orchestrator skill executes the autorun loop. The user is informed of the scope at sprint start; the loop is bounded by sprint count from `sprints.json`. Subject to dynamic floor (R10). |
| **5 — Reserved (human-only)** | Skill explicitly asks the user via the chat (single-prompt for minor; nemawashi walkthrough for major per R5). The skill blocks until the user types `yes`. The harness's permission system also denies high-impact Bash commands at the `deny` tier — user must explicitly opt in per session. |

### 9.2 The `tools:` Frontmatter Contract

Each agent declares its allowed tools. The list **must match** the agent's autonomy level. Examples unchanged from v1.

### 9.3 `.claude/settings.json` Permission Rules

The plugin ships a `settings.json` template with tiered Bash command rules:

```json
{
  "permissions": {
    "allow": [
      "git status", "git diff", "git log", "git show", "git branch -l", "git ls-files"
    ],
    "ask": [
      "git add *", "git commit -m *", "git checkout -b *", "git tag *", "git stash *"
    ],
    "deny": [
      "git push *", "git push --force *", "git reset --hard *", "git rebase -i *", "git merge *"
    ]
  }
}
```

The user installs the plugin and chooses to merge these rules into their project `.claude/settings.json`. Level 5 git operations are denied by default; the user must explicitly move them to `ask` or `allow` per project. **All `deny` entries here are also classified `irreversible` in the reversibility table (Section 2.4.2)** — defense-in-depth: even if a user moves them to `allow`, the orchestrator still treats them as Level 5 / nemawashi-required.

**Orchestrator-issued `git merge` on sprint PASS (v2.1 clarification):** Section 8.2 Step 1D allows the orchestrator to present `git merge sprint-{NN} → main` for Level 5 approval after a PASS. Because `git merge *` is in the default `deny` tier, the user must move it to `ask` (recommended) or `allow` (not recommended) on first use, or run the merge manually outside the harness. The `/council-kickoff` skill surfaces this as a one-time setup prompt and writes the chosen tier to `.claude/settings.local.json`. Without the move, the orchestrator presents the proposed merge command for the user to copy-paste — the council never silently merges.

### 9.4 PreToolUse / PostToolUse Hooks

Per Q9 default, the plugin ships hooks; per Q13 mechanism-vs-discipline recommendation, the four highest-blast-radius rules are mechanism-enforced.

**`hooks/enforce-append-only.sh`** — PreToolUse hook (unchanged from v1). Blocks `Write`/`Edit` operations against the protected jsonl files.

**`hooks/enforce-reversibility.sh`** — PreToolUse hook (NEW v2/R9). Blocks irreversible Bash commands when the orchestrator's effective autonomy level (read from `.council/state/effective-autonomy.json`) is < 5.

```bash
#!/bin/bash
# PreToolUse hook. Block irreversible commands at autonomy < 5.
if [[ "$CC_TOOL_NAME" == "Bash" ]]; then
    cmd=$(echo "$CC_TOOL_INPUT" | jq -r '.command // empty')
    case "$cmd" in
        "git push"*|"git push --force"*|"git reset --hard"*|"git rebase -i"*|"git tag -d"*|*"--no-verify"*)
            level=$(jq -r '.level' .council/state/effective-autonomy.json 2>/dev/null || echo "5")
            if [[ "$level" -lt 5 ]]; then
                echo "BLOCKED: '$cmd' is irreversible at effective autonomy $level. Run /council-review --restore-autonomy or perform manually." >&2
                exit 1
            fi
            ;;
    esac
fi
exit 0
```

**`hooks/log-tool-call.sh`** — PostToolUse hook (unchanged from v1). Appends every successful tool call to `.council/audit-log.jsonl`. Per Q14, also tracks `andon_pull_count` per agent for anomaly detection.

**`hooks/session-stopped-marker.sh`** — Stop hook (unchanged from v1). Writes a session-stopped marker to `progress.md`.

### 9.5 Approval Gates as Chat Prompts

Two shapes:

**Single-prompt (minor reversible):**

> Apply minor correction: add technical note "use streaming response handler" to sprint 5 contract?
>
> (yes / no)

**Nemawashi walkthrough (major or irreversible — R5):**

A four-stage walkthrough as detailed in Section 8.2 Step 1D. Position paper is written to `.council/proposed/DEC-{NNNN}.md` first, then walked stage by stage with three handles per agent perspective (yes / refine / disagree), then ratification.

### 9.6 The Dispatch Envelope (Bounded Self-Organization)

[src §11 Rule 4] — unchanged from v1, with the addition that the envelope template now references `instructions/andon-protocol.md` and `instructions/evidence-first.md` so every dispatched agent inherits the andon authority and genchi-genbutsu evidence obligations.

`templates/dispatch-envelope.md` is the single source of truth for dispatch invocation. Every dispatch site in every skill uses it. **No skill may call another skill via `Task`** — that path is reserved for agent dispatches only.

### 9.7 Effective-Autonomy Observability (NEW v2/R10/Q20)

`.council/state/effective-autonomy.json` is updated by `scripts/update-effective-autonomy.py` on every change. Schema (see Section 11):

```json
{
  "level": 4,
  "last_change": "2026-05-07T12:34:56Z",
  "reason": "Two consecutive sprint FAILs in sprints 4 and 5 — dropped from L4 to L3 per R10 rule",
  "restored_when": "After 1 PASS"
}
```

Other systems (CI, observability dashboards, the user's terminal status line) poll this file. The reversibility hook (Section 9.4.2) reads this file on every Bash invocation.

---

## 10. trine-eval Integration Contract

Section 10 is **largely unchanged from v1**. Only changes: (a) Section 10.2 governance signal includes `taxonomy_version: "2.0"` to surface the 4M re-rooting; (b) Section 10.3 adds two new Phase 2 features the council leverages.

### 10.1 What henka-council Reads from `.harness/`

All read-only, unchanged from v1:

- `config.json`, `spec.md`, `features.json`, `sprints.json`, `sprint-state.json`, `progress.md`
- `contracts/sprint-{NN}.md`, `contracts/sprint-{NN}.tasks.json`
- `evals/sprint-{NN}-r{R}.md`, `evals/sprint-{NN}-r{R}-t{T}.md`
- `transcripts/sprint-{NN}-r{R}.json`
- `regression/regression.json`
- `summary.md`

### 10.2 What henka-council Writes to `.harness/`

**Exactly one optional key, written once at kickoff:**

```json
{
  "governance": {
    "enabled": true,
    "plugin": "henka-council",
    "council_state_path": ".council/",
    "review_frequency": "every-sprint",
    "taxonomy_version": "2.0"
  }
}
```

This is informational. trine-eval does not require it. Q8 default: open a small PR to trine-eval after henka-council 0.1.0 ships, adding a one-line note to `skills/harness-sprint/SKILL.md` documenting that this key may be present and that trine-eval should not interpret it.

**Any other modification to `.harness/` requires Level 5 approval and is logged as a `course-correction-major` decision.**

### 10.3 Phase 2 Features the Council Leverages

| trine-eval Phase 2 Feature | Council Use |
|---|---|
| `tasks.json` per sprint | Scope guardian uses the `task_id` + `criterion` mapping for exact-match scope drift detection |
| Multi-trial evals (`-tT.md`) | qa-regression compares trial files for non-determinism — flags consistency violations as `quality-defect-anomaly` Henkaten |
| Structured transcripts (`.json`) | henkaten-detector uses `tool_calls` and `criteria_audit` arrays as observed evidence (high confidence). **Verification spot-check (R4) uses transcript commands as the canonical re-runnable form when applicable.** |
| `criteria_audit` `verified_via_command` flags | qa-regression flags any sprint where flags don't match `tool_calls` as a `quality-defect-anomaly`. **Per R4, the council extends this from "did a command run?" to "what command, and would re-running it produce the same result?"** |
| Regression invariants (`regression.json`) | Each new graduation is a `method-process-change` Henkaten (informational) with `change_origin: active` |
| Cross-sprint `summary.md` | council-retro reads this verbatim as the primary cross-sprint evidence |
| `pass@k` / `pass^k` metrics | Retrospective agent reasons about consistency vs capability |
| Edge-case pass rate | Retrospective agent flags one-sided eval failure mode if cross-sprint edge-case rate diverges sharply from weighted score |

### 10.4 Sprint Lifecycle Composition

```
USER -> /council-autorun
  |
  v
council-autorun loads state, decides to run sprint NN
  |
  v
Step 1A: pre-sprint checks (council-internal)
  |
  v
Step 1A.5: yokoten review (R6) — surface adaptation prompts
  |
  v
Step 1B: dispatch /trine-eval:harness-sprint NN
  |   (trine-eval's full loop runs internally; council unaware)
  v
trine-eval returns control with sprint-state.json updated
  |
  v
Step 1C: council fan-out (with andon handling, swarming, verification spot-check)
  |
  v
Step 1D: orchestrator merges -> .council/course-corrections/after-sprint-NN.md
  |   - Reversibility check (R9)
  |   - Identifies minor vs major
  |   - Auto-applies minor reversible (Level 3)
  |   - Presents major or irreversible via nemawashi walkthrough (R5)
  v
Step 1E: append decision log entries (with effective_autonomy_at_decision)
  |
  v
Step 1F: halt check (incl. andon escalation, dynamic floor breach)
  |
  v
Step 1G: compact context
  |
  v
Step 1H: per-sprint mini retrospective (R7)
  |
  v
Step 1I: next sprint or exit (every-N -> dispatch /council-retro before next)
```

trine-eval does not know it's being wrapped. trine-eval continues to behave exactly as it does standalone. The council layer is additive.

### 10.5 Backward Compatibility

A trine-eval project without henka-council still works. A henka-council project without trine-eval cannot exist (the council depends on a sprint engine). This asymmetry is intentional and matches the source spec [src §17].

---

## 11. Schema Catalog

11 schemas in v2 (was 10). Section 11.3 (henka-record) and Section 11.4 (decision-log-entry) are revised; Section 11.11 (effective-autonomy) is new.

| # | Schema File | Used For | Append-only? | v1/v2 |
|---|---|---|---|---|
| 11.1 | `council-config.schema.json` | `.council/config.json` | No | v1 |
| 11.2 | `council-manifest.schema.json` | `.council/council-manifest.json` | No | v1 |
| 11.3 | `henka-record.schema.json` | Each line of `henka-register.jsonl` | **Yes** | **v2 revised** |
| 11.4 | `decision-log-entry.schema.json` | Each line of `decision-log.jsonl` | **Yes** | **v2 revised** |
| 11.5 | `standard-work.schema.json` | `.council/standard-work.json` | No | v1 |
| 11.6 | `audit-log-entry.schema.json` | Each line of `audit-log.jsonl` | **Yes** | v1 |
| 11.7 | `human-approval-log-entry.schema.json` | Standalone approval records | **Yes** | v1 |
| 11.8 | `conflict-resolution-entry.schema.json` | Conflict records | **Yes** | v1 |
| 11.9 | `evidence-index.schema.json` | Optional evidence citation index | No | v1 |
| 11.10 | `integration-signal.schema.json` | The `governance` key in `.harness/config.json` | No | v1 (taxonomy_version added) |
| 11.11 | `effective-autonomy.schema.json` | `.council/state/effective-autonomy.json` | No | **v2 NEW** |

### 11.3 `henka-record.schema.json` (REVISED v2)

Adds `change_origin` (R1), `andon_signal` (R2), `verification` (inside evidence entries; R4), `yokoten` block (R6), and `fourM_axis` (R8).

```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "type": "object",
  "required": ["henka_id", "sprint_context", "fourM_axis", "category", "change_origin", "impact_level", "description", "affected_artifacts", "response_type", "evidence", "status", "detected_at"],
  "properties": {
    "henka_id": {"type": "string", "pattern": "^HK-[0-9]{4,}$"},
    "sprint_context": {"type": "integer", "minimum": 0},
    "fourM_axis": {"enum": ["Man", "Machine", "Material", "Method"]},
    "category": {"type": "string", "description": "Sub-type (e.g. agent-capability-change, scope-change). Validated against built-in 13 + custom_henkaten_categories."},
    "change_origin": {
      "enum": ["active", "passive"],
      "description": "active = deliberately initiated (henkoten 変更点); passive = emerged unbidden (henkaten 変化点 strict sense)"
    },
    "impact_level": {"enum": ["informational", "actionable", "blocking", "high-risk"]},
    "description": {"type": "string"},
    "affected_artifacts": {"type": "array", "items": {"type": "string"}},
    "response_type": {"enum": ["log-only", "auto-correct", "propose-to-user", "escalate", "andon-alert", "andon-stop"]},
    "evidence": {
      "type": "array",
      "items": {
        "type": "object",
        "required": ["claim", "evidence_class", "confidence"],
        "properties": {
          "claim": {"type": "string"},
          "evidence_class": {"enum": ["observed", "inferred", "speculative"]},
          "confidence": {"enum": ["high", "medium", "low"]},
          "verification": {
            "type": "string",
            "description": "Required when evidence_class == observed. Re-runnable command (Bash, Python, grep, git diff)."
          },
          "source_file": {"type": "string"},
          "source_line_range": {"type": "string"}
        }
      }
    },
    "andon_signal": {
      "type": "object",
      "description": "Optional. Present if the agent that detected this Henkaten issued an andon signal.",
      "properties": {
        "type": {"enum": ["alert", "stop"]},
        "reason": {"type": "string"},
        "swarm_request": {"type": "array", "items": {"type": "string"}}
      }
    },
    "yokoten": {
      "type": "object",
      "description": "Optional. Populated by retrospective agent when status transitions to closed.",
      "properties": {
        "applicable_to_subsequent_sprints": {"type": "array", "items": {"type": "string"}},
        "adaptation_notes": {"type": "string", "description": "Guidance for how this learning translates; NOT a verbatim copy"},
        "deployed_to": {
          "type": "array",
          "items": {
            "type": "object",
            "properties": {
              "sprint": {"type": "string"},
              "applied_at": {"type": "string", "format": "date-time"},
              "decision_id": {"type": "string"},
              "adaptation_taken": {"type": "string"}
            }
          }
        }
      }
    },
    "status": {"enum": ["classified", "assessed", "responded", "closed"]},
    "detected_at": {"type": "string", "format": "date-time"},
    "detected_by_agent": {"type": "string"}
  }
}
```

### 11.4 `decision-log-entry.schema.json` (REVISED v2)

Adds `effective_autonomy_at_decision` (R10), `reversibility` (R9), `nemawashi_walkthrough_version` (R5), and `andon_resolution` (R3).

```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "type": "object",
  "required": ["decision_id", "timestamp", "decision_type", "decision_outcome", "autonomy_level_used", "effective_autonomy_at_decision", "reversibility"],
  "properties": {
    "decision_id": {"type": "string", "pattern": "^DEC-[0-9]{4,}$"},
    "timestamp": {"type": "string", "format": "date-time"},
    "council_agents_involved": {"type": "array", "items": {"type": "string"}},
    "evidence_cited": {"type": "array", "items": {"type": "object"}},
    "decision_type": {"type": "string"},
    "decision_outcome": {"enum": ["applied", "proposed", "rejected", "deferred", "superseded"]},
    "applied_automatically": {"type": "boolean"},
    "user_approval_required": {"type": "boolean"},
    "user_approval_status": {"enum": ["approved", "rejected", "revised", "pending", null]},
    "affected_files": {"type": "array", "items": {"type": "string"}},
    "linked_henka_id": {"type": "string"},
    "sprint_context": {"type": "integer"},
    "autonomy_level_used": {"type": "integer", "minimum": 0, "maximum": 5},
    "effective_autonomy_at_decision": {"type": "integer", "minimum": 0, "maximum": 5},
    "reversibility": {"enum": ["reversible", "irreversible"]},
    "nemawashi_walkthrough_version": {
      "type": "string",
      "description": "Filename of position paper, e.g. DEC-0042.md or DEC-0042-rev2.md. Null for minor (single-prompt) decisions."
    },
    "andon_resolution": {
      "type": "object",
      "description": "Present if this decision resolved an andon signal.",
      "properties": {
        "originator": {"type": "string"},
        "swarm": {"type": "array", "items": {"type": "string"}},
        "resolution": {"enum": ["resumed", "escalated_to_stop", "user_intervention"]},
        "duration_seconds": {"type": "number"}
      }
    }
  }
}
```

### 11.11 `effective-autonomy.schema.json` (NEW v2/R10/Q20)

```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "type": "object",
  "required": ["level", "last_change", "reason"],
  "properties": {
    "level": {"type": "integer", "minimum": 0, "maximum": 5},
    "last_change": {"type": "string", "format": "date-time"},
    "reason": {"type": "string", "description": "Human-readable explanation of why the current level is what it is."},
    "restored_when": {
      "type": ["string", "null"],
      "description": "Description of the condition that will restore the nominal level. Null if at nominal."
    },
    "trigger_history": {
      "type": "array",
      "description": "Most recent N triggers (default 10) for debugging and pull-rate analysis.",
      "items": {
        "type": "object",
        "properties": {
          "timestamp": {"type": "string", "format": "date-time"},
          "trigger": {"type": "string"},
          "level_before": {"type": "integer"},
          "level_after": {"type": "integer"}
        }
      }
    }
  }
}
```

Other schemas (11.1, 11.2, 11.5, 11.6, 11.7, 11.8, 11.9, 11.10) carry forward verbatim from v1 / source spec §10. Each schema validates on append via `scripts/append-*.py`.

---

## 12. Standard Work Template (Contracts-First)

[src §15 lines 1389–1459] — unchanged from v1.

`templates/contracts-first-standard-work.json` carries forward the source spec's sizing heuristics, 5 documented failure patterns (FP-CF-001 through FP-CF-005), 2 evaluation improvements (EI-CF-001, EI-CF-002), 6 workflow notes (WN-CF-001 through WN-CF-006). Used when the target project follows contracts-first methodology. The template seeds initial `standard-work.json` for contracts-first projects; subsequent retrospectives evolve it.

---

## 13. Risks and Mitigations

Updated from v1 to add the new v2 risks.

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| Self-referential complexity (henka-council uses trine-eval to build itself; manages trine-eval) | High | Medium | Keep boundaries strict. Treat trine-eval as a stable dependency. henka-council never governs its own construction. |
| Plugin cache lag (Sprint 12 lesson learned) | High | Low | Bump henka-council version on every release. Document the manual cache refresh path in README. |
| Subagent isolation depends on prompt construction discipline | Medium | High | Standardize the dispatch envelope template. Every dispatch site in every skill uses it. Review every dispatch in sprint contract reviews. |
| Hooks platform-specific (Bash) — cross-platform issues | Medium | Medium | Hooks under `hooks/` use Bash but must work on Git Bash on Windows. Test in CI. PowerShell equivalents in `hooks/win/` if needed. |
| Six agents fan-out per sprint = high token cost | Medium | Medium | Configurable `review_frequency`. Per Q6 default sequential dispatch in v0.1; parallel as opt-in. |
| Append-only enforcement requires hook to be active | Low | High | Document hook installation in README. `/council-kickoff` self-check verifies hooks; warns user if missing. |
| Schema drift between agents and orchestrator | Low | High | Single source-of-truth `schemas/`. Validation scripts run before every write. |
| Custom henkaten categories diverge across projects | Medium | Low | Custom categories live per-project in `.council/config.json`; cross-project portability not promised. Each custom sub-type must declare its 4M axis (R8). |
| trine-eval Phase 2 features absent in older trine-eval | Low | Low | Council reads these as optional inputs; absent → graceful degradation per Rule 11. Minimum trine-eval version 0.3.0+. |
| Approval gate UX is chat-text-only | Medium | Low | `mcp__ccd_session__spawn_task` for items the user should review later; clear multi-choice prompts in chat for in-the-moment decisions. |
| **[v2/R5] Nemawashi walkthrough adds friction to every major decision** | Medium | Low | Per Q15 default, nemawashi applies only to major corrections. Minor corrections retain the v1 single-step auto-apply model. Track average walkthrough duration; if >5 min for routine cases, revisit in v0.2. |
| **[v2/R2] Agent-issued andon signals could be spurious or could be missed** | Medium | Medium | Per Q14 default, strictly honor all andon signals; track per-agent pull-rates in audit-log; anomalous pull-rates surface as `quality-defect-anomaly` Henkaten. |
| **[v2/R4] Verification re-runs add latency to every fan-in** | Medium | Low | Spot-check is one random `observed` claim per agent (not every claim). `scripts/run-verification.py` enforces a per-command timeout. |
| **[v2/R7] Three retrospective cadences could overwhelm a small project** | Low | Low | Mini cadence is automatic and ≤30s. PDCA cadence is configurable (default every-5). Jishuken is user-invoked only — no cost unless used. |
| **[v2/R9] Reversibility classifier could be over-restrictive** | Medium | Low | Per Q19 default, per-tool classification in v0.1 (conservative). Per-action classification in v0.2 if v0.1 proves over-restrictive. |
| **[v2/R10] Dynamic autonomy floor could create surprise restrictions** | Low | Medium | Floor changes always written to `state/effective-autonomy.json` with explicit `reason` and `restored_when`. The user can poll, and the orchestrator surfaces every floor change in chat. |
| **[v2.1] `audit-log.jsonl` grows unbounded over a long project** | High | Low | Document a rotation policy in README: when `audit-log.jsonl` exceeds 50 MB, the council-autorun skill invokes `scripts/rotate-audit-log.py` which renames the current file to `audit-log-{ISO-week}.jsonl.gz` (gzip), starts a fresh `audit-log.jsonl`, and writes a `DEC-NNNN` entry recording the rotation with the previous file's SHA-256. Schema validation on append remains O(1) per line; rotation is the only file-rewriting operation and is always pre-announced. |
| **[v2.1] trine-eval Phase 2 features absent across minor versions** | Medium | Low | Ship a compatibility matrix in `docs/trine-eval-compat.md` mapping council features (e.g. transcript-based verification, regression invariants, summary.md) to minimum required trine-eval minor version. Minimum overall: trine-eval 0.3.0 (Q7). Council reads each Phase 2 feature defensively per Rule 11 and degrades gracefully if absent. |
| **[v2.1] Irreversible-action cleanup walkthroughs add friction** | Medium | Low | Per-tool reversibility (Q19) treats routine cleanup like deletion of a pushed tag as `irreversible`, triggering nemawashi (R5/R9). For frequent benign operations, the user can move specific commands from the reversibility hook's denylist to a per-project `irreversible_overrides` array in `.council/config.json` — each override requires Level 5 ratification at kickoff and is logged. v0.2 will move to per-action classification (Q19) which subsumes this. |

---

## 14. Decisions Required Before Sprint Planning

20 questions resolved with recommended defaults. The user may override any.

### Q1–Q12 (from v1, recommendations carried forward)

| # | Question | Recommended Default |
|---|---|---|
| Q1 | Spelling: `henka` vs `henkaten`? | **C** — repo `henka-council`; plugin name `henkaten-council`; concept terms stay "henkaten" in agent text and user-facing docs |
| Q2 | Plugin packaging — same marketplace, or separate? | **A** — new marketplace `~/.claude/local-marketplaces/henka-council/` |
| Q3 | Sprint-engine integration mode | **A** — wrap-only; trine-eval unaware |
| Q4 | CC-001 — ship qa-regression and rag-source as default agents? | **A** — honor source spec; defaults to 4 agents; CC-001 opt-in |
| Q5 | First sprint scope | **A** — incremental; Sprint 1 ships kickoff + manifest + architect only |
| Q6 | Agent dispatch model — parallel or sequential? | **C** with default `sequential` for v0.1 |
| Q7 | trine-eval Phase 2 features — adopt all? | **A** — adopt all; require trine-eval ≥ 0.3.0 |
| Q8 | trine-eval governance-key documentation PR | **A** — open small PR after henka-council 0.1.0 ships |
| Q9 | Hook layer — ship enforcement hooks? | **A** — ship hooks; defense-in-depth |
| Q10 | Bootstrap from VSCode state? | **C** — fresh start; reference original work in CHANGELOG |
| Q11 | Archaeologist + Prompt Forge — v0.1 or v0.2? | **B** — defer to v0.2 |
| Q12 | Sprint methodology for henka-council itself | **C** — hybrid: D1 Schema Definitions + D2 Agent Contracts as design phase, then 6 implementation sprints |

### Q13–Q20 (from supplement, recommendations carried forward)

| # | Question | Recommended Default |
|---|---|---|
| Q13 | How aggressive should mechanism-over-discipline be? | **Mechanism for the four high-blast-radius rules** (append-only logs, features.json modification, irreversible git commands, schema validation on append). Discipline for everything else, with retrospective-flagged escalation if discipline-only rules are violated. |
| Q14 | How much do we trust agent-issued andon signals? | **Strictly honor all andon signals**; track per-agent pull-rates in audit-log; anomalous pull-rates surface as `quality-defect-anomaly` Henkaten. No orchestrator-side filtering. |
| Q15 | Does nemawashi-shaped decision-making slow the loop too much? | **Apply nemawashi only to major corrections** (Section 8.2 Step 1D Major list, plus all irreversible actions per R9). Minor reversible corrections retain single-step auto-apply. |
| Q16 | Are jishuken outputs supposed to feed back into the system, or stay as standalone artifacts? | **Decoupled in v0.1.** Jishuken output is reflection. Promotion to standard-work happens through the next `/council-retro` cycle (which can read jishuken artifacts). Direct promotion is a v0.2 enhancement if the indirect path proves too slow. |
| Q17 | Should yokoten adaptations be subagent-authored or human-authored? | **Default to user**, with agent assistance via dispatch. The retrospective agent drafts an adaptation; the user reviews and ratifies. Honors nemawashi (R5). |
| Q18 | How does the 4M Man axis apply to Claude Code agentic systems? | **Add `agent-capability-change` in v0.1** (high-confidence: detectable via plugin version diff, agent file diff, model version diff). Defer `evaluator-bias-change` to v0.2 (requires statistical comparison). `human-reviewer-change` deferred (captured by trine-eval transcripts). |
| Q19 | Should reversibility classification be per-action or per-tool? | **Per-tool in v0.1** (simpler, conservative). Per-action in v0.2 if v0.1 proves over-restrictive. |
| Q20 | How do other systems observe the dynamic effective-autonomy state? | **`.council/state/effective-autonomy.json`** is updated via `scripts/update-effective-autonomy.py` on every change. Other systems poll. Schema in §11.11. |

---

## 15. Sprint Plan (REVISED v2)

Per Q12 default, hybrid contracts-first. Two design sprints (D1, D2) + six implementation sprints (S1–S6). v2 expands from v1's plan to absorb the new mechanisms (andon, nemawashi, yokoten, three retrospective cadences, reversibility, dynamic floor).

### Design Sprints

**D1 — Schema Definitions.** Lock the 11 JSON Schemas (Section 11). Includes the v2-revised henka-record (with `change_origin`, `andon_signal`, `yokoten`, `verification`, `fourM_axis`), the v2-revised decision-log-entry (with `effective_autonomy_at_decision`, `reversibility`, `nemawashi_walkthrough_version`, `andon_resolution`), and the new effective-autonomy schema. Deliverables: `schemas/*.json`, validator scripts in `scripts/`, schema unit tests, README documentation.

**D2 — Agent Contracts.** Lock the seven agent definitions (`agents/*.md`) with frontmatter, prompt templates, prohibitions, dispatch envelopes. Includes the andon authority (R2) and genchi-genbutsu evidence (R4) inherited via `instructions/andon-protocol.md` and `instructions/evidence-first.md`. Includes the retrospective agent's three modes (R7). Deliverables: `agents/*.md`, `instructions/*.md`, `templates/dispatch-envelope.md`, `templates/nemawashi-position-paper.md`, contract validation tests.

### Implementation Sprints

**S1 — Kickoff Skill + Plugin Bootstrap.** Ship `skills/council-kickoff/SKILL.md`, `plugin.json`, `.claude-plugin/`, README, `.claude/settings.json` template, baseline `agents/architect.md`, baseline `agents/orchestrator.md`. Per Q5 default: smallest possible Sprint 1. Acceptance: `/henka-council:council-kickoff` against a fresh trine-eval project produces valid `.council/` baseline.

**S2 — Core Agents + State Files.** Ship `agents/scope-guardian.md`, `agents/henkaten-detector.md`, `agents/retrospective.md` (mini mode only at this point), all three append-only state files via `scripts/append-*.py`, `state/effective-autonomy.json` initial write. Acceptance: each agent dispatched standalone produces validated output.

**S3 — Hooks + Reversibility + Effective-Autonomy Tracking.** Ship `hooks/enforce-append-only.sh`, `hooks/enforce-reversibility.sh`, `hooks/log-tool-call.sh`, `hooks/session-stopped-marker.sh`, **`hooks/win/*.ps1` PowerShell equivalents (v2.1)**, `scripts/update-effective-autonomy.py`, `scripts/rotate-audit-log.py` (v2.1). Per Q9 default: defense-in-depth. **Acceptance (v2.1):** hooks block forbidden writes on **both Git Bash on Windows and bash on macOS/Linux**; reversibility hook denies irreversible Bash at L<5; effective-autonomy state observable; audit-log rotation runs at 50 MB threshold and writes a `DEC` entry with the rotated file's SHA-256.

**S4 — Council Autorun + Andon Protocol + Verification Spot-Check.** Ship `skills/council-autorun/SKILL.md` implementing all of Steps 1A–1I (including 1A.5 yokoten review with ratify-once shortcut, 1C andon handling with parallel swarm dispatch and distinct-originator corroboration, 1H mini retrospective). Ship `instructions/andon-protocol.md`, `scripts/run-verification.py` with the v2.1 syntax allowlist enforced. Acceptance: full sprint loop runs end-to-end with andon escalation, verification spot-check rejecting non-allowlisted strings, and dynamic-floor drop only firing on distinct-originator corroboration.

**S5 — Nemawashi Walkthrough + Course Corrections.** Ship `skills/council-review/SKILL.md`, the nemawashi-shaped major decision flow in autorun Step 1D (R5), `templates/nemawashi-position-paper.md`, `.council/proposed/` directory handling. Per Q15 default: minor reversible retains single-prompt; major or irreversible uses walkthrough. Acceptance: a major decision walkthrough produces a position paper, walks the user agent-by-agent, and ratifies.

**S6 — Three Retrospective Cadences + Yokoten + Detect Skill.** Ship `skills/council-retro-mini/`, revised `skills/council-retro/` (PDCA), `skills/council-jishuken/`, `skills/council-detect/`, retrospective agent's PDCA and jishuken modes, yokoten propagation in step 1A.5 + retrospective agent. Acceptance: per-sprint mini runs inline; per-cycle PDCA produces standard-work proposals; jishuken produces reflection-only output.

### Out of v0.1 (Deferred to v0.2)

- Per Q11: Archaeologist, Prompt Forge
- Per Q6: parallel dispatch mode
- Per Q3 / Option B v1 §3.3: MCP-based git server
- Per Q18: `evaluator-bias-change` Man-axis sub-type
- Per Q19: per-action reversibility classification
- Per Q16: direct jishuken-to-standard-work promotion path
- CC-001 (qa-regression + rag-source) opt-in by default per Q4

### Provisional Sprint Sizing

Each sprint is one trine-eval contract → build → eval → retry cycle. Sizes are proposals; trine-eval's contract negotiation will refine them.

| Sprint | Estimated effort (trine-eval rounds) | Artifacts produced |
|---|---|---|
| D1 | 1 | 11 schemas + 4 validator scripts + tests |
| D2 | 1 | 7 agent files + 4 instruction files + dispatch envelope + position paper template |
| S1 | 1 | 1 skill + plugin metadata + baseline 2 agents |
| S2 | 1 | 3 agents + 3 append scripts + state initialization |
| S3 | 2 | 4 bash hooks + 4 PowerShell hooks + reversibility classifier + effective-autonomy script + audit-log rotation script (v2.1) |
| S4 | **3** (v2.1: was 2; absorbs verification allowlist enforcement, parallel swarm dispatch, distinct-originator corroboration, ratify-once yokoten shortcut) | 1 skill (largest) + andon protocol + verification spot-check + ambient-detection wiring + scheduled-vs-unscheduled suppression |
| S5 | 1 | 1 skill + nemawashi walkthrough flow + position-paper template integration + `proposed/archive/` move-on-ratify |
| S6 | 1 | 4 skills + retrospective agent's three modes + yokoten propagation |

Total: **~11 round-equivalents (v2.1: was 10)**. With trine-eval's typical 1–2 day per round, henka-council 0.1.0 ships in roughly 2.5–3.5 weeks of focused effort.

### 15.5 Testing Strategy (NEW v2.1)

Phase 0 deferred testing strategy. v2.1 specifies it explicitly so S4 and S6 acceptance criteria are non-vacuous.

**Schema fixtures (D1 acceptance).** For each of the 11 schemas, ship `tests/schemas/<schema>/valid/*.json` (≥3 examples) and `tests/schemas/<schema>/invalid/*.json` (≥3 with documented violations). `scripts/validate-*.py` is unit-tested against both directories. CI runs the validators on every commit.

**Hook tests (S3 acceptance).** Each hook has a fixture-driven test:
- `enforce-append-only`: attempts `Write` against `henka-register.jsonl` and confirms hook exit code 1; attempts append via `scripts/append-henka.py` and confirms success.
- `enforce-reversibility`: simulates `state/effective-autonomy.json` at L3 and confirms `git push` is blocked; sets L5 and confirms allowed.
- `log-tool-call`: runs an arbitrary tool call and confirms a corresponding line appears in `audit-log.jsonl`.
- `rotate-audit-log` (v2.1): seeds a 50 MB+ fixture and confirms rotation produces a gzipped archive plus a fresh empty current file plus a `DEC` entry with matching SHA-256.

Hook tests run in CI on **both** GitHub Actions `windows-latest` (PowerShell hooks) and `ubuntu-latest` (Bash hooks).

**End-to-end fixture project (S4 and S6 acceptance).** Ship a minimal fixture trine-eval project at `tests/fixtures/dummy-project/` with:
- `.harness/spec.md` describing two trivial features (e.g. "echo CLI" and "uppercase CLI")
- `.harness/features.json` and `.harness/sprints.json` for two sprints
- Stub source code that passes trivial evals

The S4 acceptance test runs `/henka-council:council-kickoff` against this fixture, then `/henka-council:council-autorun` for both sprints, and asserts:
1. `.council/` baseline created with all required files
2. Both sprints PASS end-to-end via trine-eval
3. At least one Henkaten record is detected and classified during pre-sprint check
4. Andon swarming exercised by an injected fault (a deliberately failing eval criterion that triggers `andon_signal: alert`)
5. Verification spot-check runs and produces an audit-log entry per sprint
6. Decision-log records `effective_autonomy_at_decision` and `reversibility` on every entry

The S6 acceptance test extends this by running `/council-retro-mini` inline (asserts file appears in `retrospectives/sprint-{NN}-mini.md`), `/council-retro` after sprint 2 (asserts PDCA file appears with all four sections present), and `/council-jishuken` on a user-supplied topic (asserts file appears in `jishuken/` and standard-work.json is unchanged).

**What the S4/S6 tests do NOT assert.** Token cost, wall-clock latency, parallel-vs-sequential dispatch correctness, or trine-eval Phase 2 feature behavior — those are integration concerns punted to v0.2. v0.1 acceptance is functional correctness against the dummy fixture.

---

## 16. Phase 0 → Phase 1 Transition

After this proposal is approved (or revised):

1. **Apply the user's decisions** from Section 14 (Q1–Q20) to a final spec — overwrite this proposal with a clean v2.1 reflecting any chosen overrides, OR keep this proposal and add an addendum.
2. **`cd henka-council; /trine-eval:harness-kickoff`** — kickoff against henka-council with this proposal as the product spec input. The kickoff skill seeds:
   - `.harness/spec.md` ← derived from this proposal's Sections 2, 5, 6, 7, 8, 11, 12 (the contract-bearing sections)
   - `.harness/features.json` ← derived from Section 4 (plugin layout) and Section 7 (agent contracts) — every agent file, every skill file, every schema, every hook, every instruction file is a feature
   - `.harness/sprints.json` ← derived from Section 15 (the 8-sprint plan)
   - `.harness/config.json` ← `project_type: "cli-tool"`, `rubric: "cli-tool"`, sane Phase 2 knobs
3. **Review the trine-eval-generated spec/features/sprints** before any code is written. The kickoff is itself a Level 5 gate — if the generated artifacts diverge from this proposal in surprising ways, revise before proceeding.
4. **`/trine-eval:harness-sprint D1`** — run the first design sprint.
5. **Iterate sprint by sprint.** Each sprint produces a working slice. Reviewer feedback on each sprint informs the next.
6. **At the end of S6, henka-council 0.1.0 ships.** Plugin can be installed; council can be applied to any trine-eval project.
7. **Phase 2 of henka-council** — Archaeologist, Prompt Forge, parallel dispatch mode, MCP-based git server (optional), `evaluator-bias-change` sub-type, per-action reversibility, direct jishuken→standard-work promotion, additional rubrics for non-trine-eval sprint engines.

---

## 17. v1 → v2 Changelog

Mapping each supplement redesign and new question to where v2 implements it.

| Change | Source | v2 Section(s) Implementing |
|---|---|---|
| Seven Pillars added as foundational principles | Supplement §2 | §2.6 |
| **R1** — `change_origin` field on henka-record | Supplement §6 R1 | §2.3 (DETECT step), §6.3, §11.3 |
| **R2** — Distributed andon authority | Supplement §6 R2 | §2.6 Pillar 2, §7.0.1, §8.2 Step 1C, §11.3 (`andon_signal`) |
| **R3** — Alert-vs-stop with swarming and takt-time bound | Supplement §6 R3 | §6.5 (response types), §8.2 Step 1C andon handling, §11.4 (`andon_resolution`) |
| **R4** — Genchi-genbutsu evidence with re-runnable verification | Supplement §6 R4 | §2.5 Rule 1 revised, §7.0.2, §8.2 Step 1C verification spot-check, §11.3 (`verification` in evidence) |
| **R5** — Nemawashi-shaped major-decision walkthrough | Supplement §6 R5 | §8.2 Step 1D Stage 1–4, §9.5, §11.4 (`nemawashi_walkthrough_version`), §4 (`proposed/`, position-paper template) |
| **R6** — Yokoten propagation as explicit pre-sprint substep | Supplement §6 R6 | §2.3 step 10, §8.2 Step 1A.5, §11.3 (`yokoten` block) |
| **R7** — Three improvement cadences as separate skills | Supplement §6 R7 | §4 (3 retro skills), §7.5 (three modes), §8.4–§8.6 |
| **R8** — 4M as primary lens; 13 sub-types; new Man-axis sub-type | Supplement §6 R8 | §6.1, §6.2, §11.3 (`fourM_axis`) |
| **R9** — Reversibility axis on autonomy enforcement | Supplement §6 R9 | §2.4.2, §8.2 Step 1D reversibility check, §9.4.2 hook, §11.4 (`reversibility`) |
| **R10** — Dynamic autonomy floor on consecutive failures | Supplement §6 R10 | §2.4.3, §8.2 Step 1F dynamic-floor breach, §9.7, §11.11 (effective-autonomy schema) |
| **Q13** — Mechanism vs. discipline boundaries | Supplement §7 Q13 | §9.4 (four mechanism-enforced rules), §13 |
| **Q14** — Trust posture for andon | Supplement §7 Q14 | §7.0.1 (strict honor), §9.4 (pull-rate tracking) |
| **Q15** — Nemawashi scope | Supplement §7 Q15 | §8.2 Step 1D (major-only by default) |
| **Q16** — Jishuken-to-standard-work coupling | Supplement §7 Q16 | §7.5 (jishuken mode excluded from standard-work proposals), §8.6 |
| **Q17** — Yokoten adaptation authorship | Supplement §7 Q17 | §8.2 Step 1A.5 (user with agent assist) |
| **Q18** — 4M Man axis sub-types in v0.1 | Supplement §7 Q18 | §6.2.1 (`agent-capability-change` added) |
| **Q19** — Reversibility classification granularity | Supplement §7 Q19 | §2.4.2 (per-tool in v0.1) |
| **Q20** — Effective-autonomy observability | Supplement §7 Q20 | §9.7, §11.11 |
| Sprint plan expanded to 2 design + 6 implementation | Supplement §6 R7 + R3 + R5 | §15 |

Sections of v1 carried forward unchanged into v2: §1 (with revised executive summary), §3 entirely, §5.1 entirely, §10 mostly, §12 entirely, §13 (with additions), §16, §17.

### 17.1 Post-Review Amendments (v2.1, applied 2026-05-07)

Reviewer feedback applied after first-draft sign-off. Each amendment cites the v2 section it modifies; the `[v2.1]` tag in section text marks the affected lines.

| # | Amendment | Sections touched |
|---|---|---|
| A1 | **Verification syntax allowlist.** `verification` strings constrained to a documented allowlist (read-only git/grep/cat/jq/test/schema-validators); `scripts/run-verification.py` enforces with timeout and CWD bounds; non-conformant strings rejected and logged as informational `agent-capability-change` Henkaten. | §7.0.2, §8.2 Step 1C |
| A2 | **Andon-stop distinct-originator corroboration.** Dynamic floor drop on three consecutive andon stops requires ≥2 distinct originator agents. Same-agent repeated stops surface as `quality-defect-anomaly` pull-rate anomalies but do not by themselves drop the floor. | §2.4.3, §8.1 step 3 (`dynamic_autonomy_thresholds`), §8.2 Step 1F |
| A3 | **`agent-capability-change` scheduled-vs-unscheduled suppression.** Edits to `agents/`, `instructions/`, etc. that fall within the active sprint's declared scope are scheduled and do NOT generate a Henkaten. Out-of-scope edits fire as before. Determined by reading sprint `tasks.json` / contract / sprints.json. Fail-safe: bypass on missing data. | §6.7 (new) |
| A4 | **Ratified position papers archived, not deleted.** Move to `proposed/archive/` so `decision-log.jsonl` `nemawashi_walkthrough_version` paths remain resolvable indefinitely. | §4 layout, §5.4 ownership rules |
| A5 | **Single autonomy-reset path.** Removed `/council-jishuken --reset-autonomy-floor`; `/council-review --restore-autonomy` is the canonical reset. Jishuken stays reflection-only. | §2.4.3, §8.6 |
| A6 | **Andon takt raised to 600s + parallel swarm dispatch.** Default `andon_takt_seconds` raised from 300 to 600 to fit four-agent dispatch; swarm dispatches use parallel `Task` calls even when default `dispatch_mode: sequential`. | §8.1 step 3, §8.2 Step 1C |
| A7 | **Cross-platform hooks.** `hooks/win/*.ps1` PowerShell equivalents added. S3 acceptance now requires hooks fire on Git Bash on Windows AND bash on macOS/Linux. CI runs on both `windows-latest` and `ubuntu-latest`. | §4 layout, §15 S3, §15.5 |
| A8 | **Testing strategy specified.** New §15.5 documents schema fixtures, hook tests, end-to-end dummy-project acceptance for S4 and S6. | §15.5 (new) |
| A9 | **Yokoten ratify-once-applies-to-N shortcut.** User may bulk-ratify a yokoten adaptation that names many sprints; subsequent sprints get a single-prompt confirmation rather than a fresh nemawashi walkthrough. Revocable per sprint. | §8.2 Step 1A.5 |
| A10 | **Rule 4 carve-out.** `andon_signal: stop` is mandatory; orchestrator must honor immediately. Rule 4 governs `swarm_request` only. | §2.5 Rule 4 |
| A11 | **Orchestrator merge path.** §9.3 clarifies that orchestrator-issued `git merge` on sprint PASS requires the user to move the command to `ask` tier; absent that, the orchestrator presents the command for manual execution. | §9.3 |
| A12 | **Three new risks logged.** Audit-log unbounded growth (with rotation policy and `scripts/rotate-audit-log.py`), trine-eval Phase 2 version compatibility matrix (`docs/trine-eval-compat.md`), irreversible-cleanup walkthrough friction (with `irreversible_overrides` config knob). | §13 |
| A13 | **S4 round estimate raised to 3 (was 2).** Absorbs the additional mechanism load from A1, A2, A6, A9. Total project estimate raised from ~10 to ~11 trine-eval rounds. | §15 sizing table |

---

## 18. Sign-off Checklist

Before proceeding to `/trine-eval:harness-kickoff`, the user has reviewed and decided on:

### Decisions inherited from v1

- [ ] §14 Q1 — Naming (henka vs henkaten)
- [ ] §14 Q2 — Plugin packaging
- [ ] §14 Q3 — Sprint-engine integration mode
- [ ] §14 Q4 — CC-001 status (4-agent vs 6-agent default)
- [ ] §14 Q5 — Sprint 1 scope
- [ ] §14 Q6 — Agent dispatch model
- [ ] §14 Q7 — trine-eval Phase 2 features
- [ ] §14 Q8 — trine-eval governance-key documentation PR
- [ ] §14 Q9 — Enforcement hooks
- [ ] §14 Q10 — Bootstrap from VSCode state
- [ ] §14 Q11 — Archaeologist + Prompt Forge timing
- [ ] §14 Q12 — Sprint methodology

### Decisions added by the supplement (R1–R10, Q13–Q20)

- [ ] §6 R1 — `change_origin` field on henka-record
- [ ] §7.0.1 R2 — Distributed andon authority
- [ ] §6.5 R3 — Alert-vs-stop with takt-bounded swarming
- [ ] §2.5 Rule 1 R4 — Genchi-genbutsu re-runnable verification on every observed claim
- [ ] §8.2 Step 1D R5 — Nemawashi-shaped major-decision walkthrough
- [ ] §8.2 Step 1A.5 R6 — Yokoten propagation as explicit pre-sprint substep
- [ ] §§8.4–8.6 R7 — Three improvement cadences as separate skills
- [ ] §6.1 R8 — 4M as primary lens; 13 sub-types; `agent-capability-change` added
- [ ] §2.4.2 R9 — Reversibility axis on autonomy enforcement
- [ ] §2.4.3 R10 — Dynamic autonomy floor on consecutive failures
- [ ] §14 Q13 — Mechanism vs. discipline boundaries
- [ ] §14 Q14 — Trust posture for agent-issued andon
- [ ] §14 Q15 — Nemawashi scope
- [ ] §14 Q16 — Jishuken-to-standard-work coupling
- [ ] §14 Q17 — Yokoten adaptation authorship
- [ ] §14 Q18 — 4M Man axis sub-types in v0.1
- [ ] §14 Q19 — Reversibility classification granularity
- [ ] §14 Q20 — Effective-autonomy observability

### Structural reviews

- [ ] §13 risks reviewed (incl. v2 additions)
- [ ] §4 plugin layout reviewed (incl. v2 additions)
- [ ] §7 agent contracts reviewed (per agent; incl. common §7.0 capabilities)
- [ ] §8 workflow contracts reviewed (per skill; incl. 3 new skills and revised autorun)
- [ ] §10 trine-eval integration contract reviewed
- [ ] §11 schema catalog reviewed (incl. revisions to 11.3, 11.4, and new 11.11)
- [ ] §15 sprint plan reviewed (D1, D2, S1–S6)

After sign-off, this proposal becomes the authoritative input to `/trine-eval:harness-kickoff` and the basis for all subsequent sprint contracts.

---

## 19. Bibliography

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

*End of Phase 0 Proposal v2.*
