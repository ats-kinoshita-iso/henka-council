# henka-council — Phase 0 Proposal

**Status:** Draft for review
**Date:** 2026-05-07
**Author:** Synthesized from the henkaten-council VSCode specification (`henka-council.txt`)
**Scope:** This document is the Phase 0 proposal for reimplementing the henkaten-council governance system as a Claude Code plugin that wraps and extends [trine-eval](https://github.com/ats-kinoshita-iso/trine-eval). No code is produced; this proposal defines the contracts that subsequent sprints will implement.

---

## 0. How to Read This Document

This proposal is structured so each section is independently reviewable and can be cited verbatim by future sprint contracts. The terminology choices (henka vs henkaten, `.council/` vs `.henka/`), the plugin packaging decision, and several other open questions are listed in [Section 14 — Decisions Required Before Sprint Planning](#14-decisions-required-before-sprint-planning). **Reviewing those open questions first** lets you correct any wrong assumptions before reading the rest.

The section numbering deliberately mirrors the source specification (`henka-council.txt`) where the topic is the same — so Section 6 here covers the Henkaten Taxonomy, matching the source's Section 6 — to make cross-reference trivial. New sections that exist only in the Claude Code reimplementation are numbered 11+.

Throughout this proposal, **direct quotes from the source spec** are marked with the source line range in brackets like `[src §4.2 lines 160–193]`.

---

## 1. Executive Summary

henka-council is a **governance layer** that wraps a sprint execution engine (in our case, [trine-eval](https://github.com/ats-kinoshita-iso/trine-eval)) with change-point detection, multi-agent review, bounded course correction, and approval gates. It encodes the Toyota Production System concept of a *henkaten* (変化点 — "change point"): every moment where conditions shift is a potential source of defects, so changes must be detected, classified, and consciously managed rather than absorbed silently.

The system was originally built for VSCode + Copilot Chat with an MCP-based git server, `.agent.md` definition files, and a `runSubagent` isolation primitive. **The platform-agnostic core (taxonomy, autonomy model, governance rules, schemas, fan-out/fan-in pattern, append-only audit trail) transfers cleanly to Claude Code.** The platform-specific shell needs targeted redesign — most VSCode primitives have direct Claude Code equivalents (subagents via `Task`, agent files in `agents/`, skills in `skills/<name>/SKILL.md`), and several Claude Code capabilities (the hooks system, the versioned plugin cache, the `.mcp.json` registration, the `Stop` and `PreToolUse` enforcement points) actually let the redesign be **stronger** than the original.

This Phase 0 proposal:

1. Maps every VSCode primitive in the source spec to a Claude Code equivalent, with caveats where the mapping is imperfect
2. Specifies the henka-council plugin layout — every file the plugin will ship and what it owns
3. Defines the trine-eval integration contract — exactly what henka-council reads from `.harness/`, what governance signal it writes, and what Phase 2 trine-eval features (transcripts, `tasks.json`, regression invariants, `criteria_audit`) the council leverages
4. Maps autonomy levels 0–5 to concrete enforcement mechanisms (frontmatter tools list, hooks, settings.json permissions, approval prompts)
5. Carries forward all 12 governance rules, the 12-category taxonomy, and the 10 schemas verbatim — these are platform-agnostic and do not change
6. Lists 12 open design questions that need explicit user decisions before sprint planning begins

**What this proposal does not do:** it does not produce code, it does not draft sprint contracts, it does not run `/trine-eval:harness-kickoff`. Those happen *after* this proposal is approved (or revised).

---

## 2. Conceptual Model (Preserved from Source Spec)

These elements are platform-agnostic and reproduce the source specification verbatim where possible. They are restated here so the proposal stands alone.

### 2.1 Three-Layer Architecture

```
+-------------------------------------------------------------------+
|  Council Plugin (Governance Layer)                               |
|  State: .council/                                                 |
|  Owns: change detection, classification, review, correction,     |
|        decision logging, approval gates, standard work evolution |
|  /council-kickoff -> Bootstrap .council/ + delegate to trine-eval|
|  /council-autorun -> Outer loop per sprint:                       |
|    1. PRE-SPRINT: Henkaten check                                  |
|    2. EXECUTE: Sprint loop (trine-eval contract->build->eval)    |
|    3. POST-SPRINT: Council convenes (fan-out -> fan-in)          |
|    4. COURSE CORRECT: minor=auto, major=propose                   |
|    5. NEXT or HALT                                                |
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

This means trine-eval is simultaneously the *engine* that builds henka-council AND a *target* henka-council can govern. The two roles are kept separate — at no point during henka-council's development does henka-council govern its own construction; it is built straight through trine-eval, and only after release does it get pointed at trine-eval as a governance target.

### 2.3 The Henkaten Loop (10 Steps)

[src §7 lines 611–636]

1. **DETECT** change (from sprint results, user input, or environment)
2. **CLASSIFY** change (assign to taxonomy category)
3. **ASSESS** impact (informational, actionable, blocking, high-risk)
4. **ASSEMBLE** or adjust council (minimum viable set of agents)
5. **EXECUTE** bounded response (within autonomy level)
6. **VERIFY** evidence (all claims must cite source)
7. **REQUEST** human approval (when required by impact level)
8. **UPDATE** artifacts (decisions, corrections, state files)
9. **CAPTURE** learning (retrospective, patterns, standard work)
10. **UPDATE** standard work (evolve process based on evidence)

Sprint Lifecycle Integration:

```
Sprint Intake       -> /council-kickoff          (steps 1-5)
Planning            -> /trine-eval:harness-kickoff produces spec/features/sprints
Execution           -> /trine-eval:harness-sprint loop (contract -> build -> eval -> retry)
Inter-Sprint Review -> council convenes          (steps 1-10)
Retrospective       -> /council-retro            (pattern analysis, kaizen)
Closure             -> /trine-eval:harness-summary + /council-retro at horizon
```

### 2.4 Autonomy Model (6 Levels)

[src §5 lines 417–471]

| Level | Name | Permits | Prohibits | Used By |
|---|---|---|---|---|
| **0** | Observe only | Read state, eval reports, harness artifacts | Any recommendation, output, modification | (passive monitoring; no agent uses by default) |
| **1** | Classify and recommend | Level 0 + classify changes, write recommendations to agent notes, log observations | Propose changes to controlled artifacts, modify state | henkaten-detector, rag-source |
| **2** | Propose changes (drafts) | Level 1 + create draft course corrections, propose contract amendments, write review reports | Modify `.harness/` files, modify `.council/` state directly, finalize artifacts | architect, scope-guardian, retrospective, qa-regression |
| **3** | Auto-apply minor corrections | Level 2 + update `.council/` working files (decision-log, henka-register), apply minor corrections to upcoming sprint contracts (technical notes, clarifications), update progress.md | Modify features.json, reorder sprints, change spec.md, modify prior eval reports, change criteria weights by >10%, promote drafts to final | orchestrator |
| **4** | Coordinate sequences under supervision | Level 3 + execute multi-step workflows (full council review cycle), invoke multiple agents sequentially, apply approved corrections to `.harness/` files | Operate without user awareness of scope, modify governance rules, change autonomy levels, override halt conditions | orchestrator (during autorun) |
| **5** | Reserved (never autonomous) | Only with explicit prior human approval per action: modify features.json, reorder sprints, amend spec.md, change governance rules, release controlled artifacts, merge branches, push to remote, reset git | Any action without explicit human approval on that specific action | None (human only) |

### 2.5 The 12 Governance Rules

[src §11 lines 1126–1194]

Carried forward verbatim. Each rule's enforcement mechanism in Claude Code is detailed in [Section 9](#9-autonomy-and-enforcement-in-claude-code).

1. **Evidence-First Behavior** — Every recommendation cites specific evidence (eval report findings, file diffs, feature comparisons, Henkaten records). Unsupported claims are rejected by the orchestrator.
2. **Draft Until Approved** — All council-proposed changes to `.harness/` are DRAFTS until explicit user approval. Drafts go to `.council/course-corrections/`.
3. **features.json Is Sacred** — No agent may remove, rename, or reinterpret features without Level 5 approval. Feature status updates (pending → done) are the only auto-applicable change.
4. **Bounded Self-Organization** — Agents may flag the need for another perspective, but the orchestrator decides whether to invoke additional agents. No agent invokes another directly.
5. **Workspace Is Source Of Truth** — All decisions, evidence, classifications, and approvals must be written to structured workspace files. Do not rely on conversation history; it may be compacted.
6. **Halt On Blocking Henkaten** — If any record is classified as blocking or high-risk, the autorun loop MUST halt and present the situation to the user.
7. **Minor / Major Correction Threshold** — Minor (auto-apply at Level 3): technical notes, clarifications, progress updates, status pending→done. Major (Level 5 approval): sprint reordering, feature changes, spec amendments, weight changes >10%, new sprints, architectural pivots.
8. **Decision Logging Is Mandatory** — Every correction, classification, and review outcome is logged to `decision-log.jsonl` with timestamp, agents, evidence, and outcome.
9. **No Scope Expansion By Agents** — Agents may flag gaps but adding features requires Level 5 approval.
10. **Retry Is Targeted** — Corrections are specific and bounded; no "refactor everything" without explicit user approval.
11. **Graceful Degradation** — When expected input files are missing, agents do not fail silently or hallucinate. Specific behavior per missing file is documented; agents report a `coverage` section listing what was available vs. unavailable.
12. **Evidence Classification Required** — All findings include `evidence_class` (observed | inferred | speculative) and `confidence` (high | medium | low). The orchestrator prioritizes observed > inferred > speculative when resolving conflicts.

---

## 3. Claude Code Environment Mapping

For each VSCode-specific primitive in the source spec, the Claude Code equivalent and any caveats. This section is the heart of the platform translation.

### 3.1 Direct Mappings (Equal or Stronger in Claude Code)

| VSCode Primitive | Claude Code Equivalent | Notes |
|---|---|---|
| `runSubagent` for isolation | **`Task` tool with `subagent_type: "<plugin>:<agent>"`** | Each agent file (e.g., `agents/architect.md`) sets `context: fork` in frontmatter. The `Task` dispatch creates a fresh subagent with no access to orchestrator reasoning — exactly the isolation contract the spec requires. trine-eval already proves this works (`trine-eval:evaluator` is dispatched this way in every sprint). |
| `.agent.md` files with YAML frontmatter | **`agents/<name>.md` with frontmatter** | Same pattern — `name`, `description`, `model`, `tools`, `context: fork`. Plugin-namespaced as `<plugin>:<agent>` when invoked. |
| `.prompt.md` files for slash commands | **`skills/<name>/SKILL.md` with frontmatter + body** | Same pattern. User invokes as `/<plugin>:<skill>`. |
| `tools: [read, search]` in agent frontmatter | **`tools: Read, Glob, Grep, Bash, Write` in agent frontmatter** | Direct map; tool names are the Claude Code tool names. Level 0/1 agents get `Read, Glob, Grep`; Level 2 agents may add `Write` for `.council/` paths only. |
| `user-invocable: true/false` | **Skills are user-invocable (`/command`); agents are dispatched only by skills** | Concept maps to Claude Code's split: skills are the user-facing entry, agents are the dispatched workers. |
| Multi-root workspace | **Worktrees + cross-repo file references** | The henka-council plugin lives in `~/.claude/plugins/cache/henka-council/` (alongside `trine-eval/`). The target project lives wherever the user is working. trine-eval already demonstrates this pattern. |
| Persistent state in files | **Identical** — Claude Code has full file access. No translation needed. | The "workspace is source of truth" principle holds verbatim. |
| Append-only logs | **Bash redirect (`>> log.jsonl`) + a PreToolUse hook to block in-place edits** | Claude Code has no file ACLs, but a hook can block `Write`/`Edit` operations against the protected jsonl files (Section 9.4). |
| Schema-validated state | **JSON Schema files in `schemas/` + Python or Node validation in skills** | Same approach. The 10 schemas in source §10 transfer verbatim. |
| Context compaction (≤500 words between sprints) | **Claude Code's session compaction + structured re-read** | Skills already follow the pattern: re-read `.harness/sprint-state.json` and `.council/decision-log.jsonl` at the start of every iteration. Conversation memory is unreliable; files are reliable. |
| MCP for git server with autonomy gating | **Direct Bash tool calls + `.claude/settings.json` permission rules** (or, alternately, a custom MCP server) | See Section 3.3 for the tradeoff analysis. |

### 3.2 Mappings That Need Care

| VSCode Primitive | Claude Code Equivalent | Concern / Mitigation |
|---|---|---|
| Subagent isolation guarantees | `Task` with `context: fork` | The spec's principle is that an agent receives ONLY file paths, never orchestrator reasoning. In Claude Code, this is enforced by *prompt construction* — the orchestrator skill must be careful not to leak reasoning into the `prompt:` argument of the `Task` tool. **Mitigation:** standardize a "subagent dispatch envelope" template that orchestrator skills must use; review every dispatch site against the template during sprint authoring. |
| `.agent.md` frontmatter `tools:` declares allowed tools | Frontmatter `tools:` in Claude Code agent files | Direct map but note: the Claude Code plugin manager **caches** these definitions and the runtime spawns from the cache. Cache lag was a real problem in trine-eval Sprint 12 (the `Write` addition didn't take effect until version bump + reinstall). **Mitigation:** Include "version bump on tool changes" in the standard work template (Section 7); document the manual cache refresh path in the plugin README. |
| Per-agent tool access control (VSCode UI) | Frontmatter + hooks | VSCode has UI-level checks; Claude Code relies on agent discipline + hook enforcement. **Mitigation:** the PreToolUse hook approach in Section 9.4 catches frontmatter violations before they fire. |
| User-invocable skills vs. orchestrator-only skills | Naming conventions | Claude Code does not enforce "internal-only skills"; any skill can be called as `/<plugin>:<skill>`. **Mitigation:** prefix orchestrator-internal helpers with `_` (e.g., `_council-fanout`) and document the "do not invoke directly" caveat in their SKILL.md frontmatter description. The convention is informational; users who type `/council:_council-fanout` will get the skill, but the description tells them not to. |
| `mcp.json` for MCP server registration | `.mcp.json` per-project | Same file format, different location (`.mcp.json` at project root, not `.vscode/mcp.json`). |

### 3.3 The Git MCP Server — Drop or Keep?

The source spec [src §13 lines 1283–1346] introduces a Python MCP server that exposes `git_status`, `git_diff`, `git_log`, `git_show`, `git_branch_list` (Level 1), `git_add`, `git_commit`, `git_branch_create`, `git_checkout`, `git_tag`, `git_stash` (Level 3), and `git_merge`, `git_push`, `git_reset`, `git_rebase` (Level 5). The server validates the caller's declared `autonomy_level` against each tool's minimum.

**Two viable options:**

**Option A — Drop the MCP server, use direct Bash with permission rules.**
- Claude Code's `.claude/settings.json` already supports tiered Bash command allowlists. We configure: `allow: ["git status", "git diff", "git log", "git show", "git branch"]`, `ask: ["git add", "git commit", "git checkout -b", "git tag", "git stash"]`, `deny: ["git push", "git reset --hard", "git rebase -i", "git merge"]`.
- Level 5 commands are configured to `deny` by default; the user explicitly types them or moves them to `ask` per-session.
- **Pro:** simpler, no extra process, no MCP server to maintain, native to the harness.
- **Con:** less granular than the MCP server's per-call validation; relies on the harness's permission system rather than agent-declared autonomy level.

**Option B — Build a Claude Code MCP server in Python.**
- Mirrors the source spec exactly. Each agent declares its `autonomy_level` and the MCP server validates per call.
- **Pro:** preserves the spec's "permission gating per tool" design; richer per-call audit (every git operation goes through one validator).
- **Con:** new dependency to install (Python + the `mcp` library), new failure mode (server not running), more moving parts in the user's setup.

**Recommendation:** **Option A for v0.1**, with a clear path to Option B in a future sprint if the per-call gating proves needed. Rationale: trine-eval Phase 2 already lands a sandbox model and a regression gate; layering an MCP server on top adds complexity that may not be needed once the council ships its own audit log. We can always upgrade later.

### 3.4 Claude Code Capabilities the Source Spec Did Not Have

Several Claude Code capabilities have no direct VSCode equivalent. The proposal recommends adopting them where they materially strengthen the council:

| Claude Code Capability | How henka-council Uses It |
|---|---|
| **Hooks (PreToolUse, PostToolUse, Stop, SessionStart, SessionEnd)** | Enforce append-only on `.jsonl` logs (PreToolUse blocks `Write`/`Edit` on protected files). Auto-emit a session-stopped marker to `.council/decision-log.jsonl` so resume detects mid-loop interruption. Log every tool call to `.council/audit-log.jsonl` (PostToolUse). |
| **`.claude/settings.json` permission rules** | Tiered Bash command allowlist enforces autonomy levels at the runtime layer (Level 5 commands set to `deny` so the user must explicitly opt in per-session). |
| **Plugin marketplaces with versioned cache** | Clean install path; version bumps trigger cache refresh. The trine-eval Sprint 12 lessons-learned (cache lag, manual sync workaround) inform a "version bump = required for tools changes" rule in the standard work template. |
| **`/compact` and `/clear`** | Manual context compaction. The spec's "context compaction ≤500 words" rule maps to a documented `/compact` invocation between sprints. The orchestrator skill can also auto-issue compaction via `mcp__ccd_session__mark_chapter` if available, or write a compacted note to `.council/sessions/<timestamp>.md`. |
| **`mcp__ccd_session__spawn_task` (chip surface)** | Out-of-scope items found during a council review can be spawned as separate tasks for the user. This is a stronger pattern than the source spec's "log to henka-register and continue" — items the human should fix later become discoverable chips rather than buried log entries. |
| **`ScheduleWakeup` / `/loop`** | The autorun loop can self-pace (sleep until a sprint completes, wake to do council review) without holding context. |
| **`mcp__ccd_session__mark_chapter`** | Sprint boundaries become marked chapters in the transcript, making the audit trail navigable. |
| **The `Stop` hook** | Triggers on every session pause — the natural place to auto-write the "session interrupted, current sprint state should be committed" marker to `progress.md`. trine-eval already uses this pattern. |
| **Background agents (`run_in_background: true`)** | Long-running fan-out (4–6 council agents in parallel) can dispatch as background tasks; the orchestrator awaits all results before fan-in. |

---

## 4. Plugin Layout

Proposed file tree for the henka-council plugin. Directory ownership and append-only rules are documented in Section 5.

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
├── skills/                                      # five user-facing slash commands
│   ├── council-kickoff/
│   │   └── SKILL.md                             # bootstraps .council/, calls trine-eval kickoff
│   ├── council-autorun/
│   │   └── SKILL.md                             # outer sprint loop wrapping trine-eval
│   ├── council-review/
│   │   └── SKILL.md                             # manual on-demand fan-out
│   ├── council-retro/
│   │   └── SKILL.md                             # full retrospective
│   └── council-detect/
│       └── SKILL.md                             # on-demand henkaten detection
├── rules/
│   └── council-conventions.md                   # the 12 governance rules (verbatim from source §11)
├── instructions/                                # behavioral constraints (source §12)
│   ├── controlled-artifacts.md
│   ├── evidence-first.md
│   ├── human-approval.md
│   └── prompt-injection-defense.md
├── templates/                                   # output templates
│   ├── council-review-report.md
│   ├── course-correction.md
│   ├── retrospective.md
│   └── contracts-first-standard-work.json
├── schemas/                                     # 10 JSON Schemas (source §10)
│   ├── council-config.schema.json
│   ├── council-manifest.schema.json
│   ├── henka-record.schema.json
│   ├── decision-log-entry.schema.json
│   ├── standard-work.schema.json
│   ├── audit-log-entry.schema.json
│   ├── human-approval-log-entry.schema.json
│   ├── conflict-resolution-entry.schema.json
│   ├── evidence-index.schema.json
│   └── integration-signal.schema.json
├── hooks/
│   ├── enforce-append-only.sh                   # PreToolUse: block in-place edit of protected .jsonl files
│   ├── log-tool-call.sh                         # PostToolUse: append to .council/audit-log.jsonl
│   └── session-stopped-marker.sh                # Stop: mark uncommitted sprint state
├── scripts/                                     # ancillary tooling (Python preferred for cross-platform)
│   ├── validate-council-config.py
│   ├── validate-henka-record.py
│   ├── validate-decision-log.py
│   ├── append-henka.py                          # safe append helper that validates before writing
│   ├── append-decision.py                       # ditto
│   └── compute-evidence-class.py
├── README.md                                    # user-facing intro + install instructions
├── LICENSE
├── CLAUDE.md                                    # plugin-side CLAUDE.md (loaded when council skills run)
└── docs/
    ├── phase-0-proposal.md                      # this document
    └── architecture.md                          # post-Phase-0 derivative architecture diagram (future)
```

**Notes on the layout:**

- `agents/` contains seven files (six council agents + the orchestrator). The orchestrator is itself an agent file, dispatched by skills at Level 4.
- `skills/` is the user surface: every slash command corresponds to one skill. No skill calls another skill directly — they all dispatch agents via `Task`.
- `instructions/` are behavioral constraint files referenced from agent and skill files. They are not loaded as skills; they are referenced as `@instructions/controlled-artifacts.md` in agent prompts.
- `templates/` provides the markdown shapes for the three primary outputs (review report, correction, retrospective) and the standard-work JSON template.
- `schemas/` holds JSON Schema definitions for every state file. `scripts/validate-*.py` use them.
- `hooks/` and `.claude/settings.json` together implement the autonomy enforcement layer (Section 9).
- `scripts/append-henka.py` and `scripts/append-decision.py` are the **only** sanctioned write paths to the protected jsonl files. They validate before appending and call `git add` so every entry becomes a tracked commit candidate. The PreToolUse hook (Section 9.4) blocks any other write path.

---

## 5. State Model and File Inventory

[src §9 lines 900–943] Carried forward verbatim with one Claude-Code-specific addition (`audit-log.jsonl`, written by the PostToolUse hook).

### 5.1 `.harness/` — Sprint Execution State (Owned by trine-eval; read-only to council)

| File | Purpose | Council access |
|---|---|---|
| `config.json` | Project configuration (type, rubric, methodology, governance signal) | Read-only; council writes the optional `governance` key only at kickoff |
| `spec.md` | Product specification — source of truth for requirements | Read-only |
| `features.json` | Canonical feature list — **SACRED**, never modified without Level 5 | Read-only |
| `sprints.json` | Sprint plan with dependencies and feature assignments | Read-only |
| `sprint-state.json` | Current sprint status, pass/fail history, scores, rounds | Read-only |
| `progress.md` | Human-readable progress summary | Read-only (council writes to its own `progress.md` notes via course corrections) |
| `contracts/sprint-{NN}.md` | Sprint contracts (one per sprint) | Read-only |
| `contracts/sprint-{NN}.tasks.json` | Machine-readable taxonomy (Phase 2) | Read-only — *new for Claude Code reimplementation; the source spec was based on local-eval which predates this* |
| `evals/sprint-{NN}-r{R}.md` | Evaluation reports | Read-only — historical record, never modified |
| `evals/sprint-{NN}-r{R}-t{T}.md` | Trial-loop evaluation reports (Phase 2) | Read-only — *new for Claude Code* |
| `transcripts/sprint-{NN}-r{R}.json` | Structured transcripts (Phase 2) | Read-only — *new; valuable input for henkaten-detector evidence* |
| `regression/regression.json` | Graduated regression invariants (Phase 2) | Read-only — *new; council uses this to detect Method/Process Henkaten when invariants graduate* |

### 5.2 `.council/` — Governance State (Owned by henka-council)

| File | Purpose | Write access |
|---|---|---|
| `config.json` | Governance settings | council-kickoff; subsequent changes require Level 5 |
| `council-manifest.json` | Active council composition | council-kickoff and council-autorun (assemble/dissolve) |
| `henka-register.jsonl` | **Append-only** log of Henkaten records | `scripts/append-henka.py` only |
| `decision-log.jsonl` | **Append-only** log of all decisions | `scripts/append-decision.py` only |
| `audit-log.jsonl` | **Append-only** action-level trace of all tool calls | PostToolUse hook only — *new for Claude Code* |
| `standard-work.json` | Evolving process improvement profile | retrospective proposes; user approves; orchestrator writes |
| `course-corrections/after-sprint-{NN}.md` | One per sprint boundary | orchestrator writes during autorun |
| `retrospectives/sprint-{NN}.md` | Per-sprint retrospective report | retrospective agent writes (via `Task` output) and orchestrator persists |
| `sessions/<timestamp>.md` | Compacted session notes (≤500 words each) | orchestrator on `/compact` invocation — *new for Claude Code; replaces VSCode "inline context note"* |

### 5.3 Append-Only Enforcement

[src §9 lines 929–935]

- **`henka-register.jsonl`**: never delete or modify existing entries. Only append new entries or update `status` field of existing entries. Status updates are append-only at the entry level — the original entry remains; a new entry with the same `henka_id` and updated `status` is appended (the latest entry wins on read).
- **`decision-log.jsonl`**: never delete or modify existing entries. Only append.
- **`audit-log.jsonl`**: never delete or modify existing entries. Only append.

The PreToolUse hook (Section 9.4) enforces this by blocking `Write` and `Edit` operations against these files. The only sanctioned write path is `scripts/append-*.py` which uses Bash with `>>` redirection.

### 5.4 Ownership Rules

[src §9 lines 936–943]

| Path | Owner | Modification Rule |
|---|---|---|
| `.harness/*` | trine-eval | Council reads only; modifications require Level 5 approval and are logged as a course correction |
| `.harness/config.json` `governance` key | henka-council | Council writes once at kickoff; subsequent changes require Level 5 |
| `.council/decision-log.jsonl`, `.council/henka-register.jsonl`, `.council/audit-log.jsonl` | henka-council | Append-only; enforced by hook |
| `.council/course-corrections/`, `.council/retrospectives/` | henka-council | Orchestrator writes; no append-only constraint (each file is per-sprint) |
| `.council/standard-work.json` | henka-council | Retrospective proposes; user approves at Level 5; orchestrator writes |
| `.council/sessions/` | henka-council | Orchestrator writes on compaction |

---

## 6. The 12 Henkaten Categories

[src §6 lines 472–610] Carried forward verbatim. The categories are platform-agnostic.

| # | Category | Description | Detection Signals | Default Impact | Recommended Agents | Human Review |
|---|---|---|---|---|---|---|
| 6.1 | source-material-change | Source documents, specifications, reference material, or data inputs added/modified/superseded | File mtime, git diff on source dirs, version number changes | informational → blocking | Architect, Scope Guardian | If affects requirements traceability |
| 6.2 | requirement-change | A requirement added/modified/removed/reinterpreted since last sprint | features.json diff, spec.md changes, user requests, evaluator finding unstated requirements | actionable → blocking | Scope Guardian, Architect | Any removal or reinterpretation |
| 6.3 | scope-change | Boundary of in/out of project or current sprint shifted | sprints.json diff, contract criteria expanding beyond spec, evaluator flagging out-of-scope work | actionable → blocking | Scope Guardian, Architect | Any expansion beyond original features.json |
| 6.4 | tool-environment-change | Development tools, runtime, model capabilities, extensions changed | Package version changes, plugin updates, subagent behavior changes, new tool availability | informational; blocking if relied-upon capability removed | Architect | If affects reproducibility |
| 6.5 | method-process-change | Development process, evaluation criteria, or workflow steps modified | Contract template changes, rubric changes, retry-logic changes, standard-work updates | informational → actionable | Retrospective, Architect | Yes, for evaluation criteria or governance rule changes |
| 6.6 | measurement-criteria-change | How success is measured changed | Contract criteria diverging from spec, evaluator suggesting new criteria, weight rebalancing | actionable | Scope Guardian, Retrospective | If criteria change affects already-passed sprints |
| 6.7 | schedule-priority-change | Sprint ordering, priorities, or timeline expectations shifted | User requesting reorder, dependency conflicts, complexity estimates proven wrong | actionable → blocking | Architect, Scope Guardian | For sprint reordering or priority changes |
| 6.8 | risk-compliance-change | New risk identified or compliance requirement changed | Evaluator security flags, edge cases, regulatory changes | actionable → high-risk | Architect, Henkaten Detector | Always for compliance |
| 6.9 | quality-defect-anomaly | Unexpected failure/regression/anomaly outside normal eval criteria | Evaluator unexpected behaviors, gate criteria failing in novel ways, architectural inconsistencies | actionable → blocking | Architect, Retrospective | If affects controlled artifacts |
| 6.10 | dependency-change | A sprint dependency changed (depended-upon failed, new dependency discovered) | sprint-state.json showing failed dependency, implementation revealing undocumented coupling | blocking if failed; actionable if new | Architect, Scope Guardian | If failure requires sprint reordering |
| 6.11 | retrospective-improvement | Pattern/learning emerged suggesting process improvement, not defect fix | Recurring failure patterns, evaluator consistently flagging similar issues, efficiency opportunities | informational | Retrospective | Before applying to standard work |
| 6.12 | architectural-discovery | Implementation revealed architectural constraints/patterns/opportunities not visible during planning | Sprint requiring structural changes, evaluator noting architectural concerns, cross-cutting concerns emerging | actionable → blocking | Architect, Retrospective | If discovery requires plan-level changes |

### 6.1 Confidence Calibration Table

[src §6 lines 584–596]

| Category | High confidence when | Low confidence when |
|---|---|---|
| Source Material Change | File diff confirms content change | Only timestamp changed |
| Requirement Change | Explicit user request or spec edit | Evaluator implied unstated requirement |
| Scope Change | features/sprints.json modified | Contract criteria expanded ambiguously |
| Tool/Environment Change | Version/capability confirmed | Behavior change without confirmation |
| Quality Defect | Deterministic failure reproduced | Single intermittent failure |
| Dependency Change | sprint-state shows explicit fail | Suspected but unconfirmed coupling |

Low-confidence detections classify as `impact_level: "informational"` unless corroborated by a second signal.

### 6.2 Impact Levels and Response Types

[src §6 lines 598–610]

**Impact levels (ordered by severity):**
- `informational`: Noted, no action required. Response: log-only.
- `actionable`: Requires attention but does not block. Response: auto-correct or propose-to-user.
- `blocking`: Cannot proceed until resolved. Response: halt loop, present to user.
- `high-risk`: Safety/compliance/integrity concern. Response: halt loop, escalate.

**Response types:**
- `log-only`: Record the change-point, no action needed.
- `auto-correct`: Orchestrator applies minor correction (Level 3).
- `propose-to-user`: Write course correction proposal, present for approval.
- `escalate`: Flag for immediate human review with full evidence.
- `halt`: Stop the autorun loop immediately.

### 6.3 Custom Categories

[src §19 lines 1623–1631]

The taxonomy is extensible. Users define additional categories in `.council/config.json`:

```json
{
  "custom_henkaten_categories": [
    {
      "category_id": "custom-rag-corpus-drift",
      "description": "RAG corpus content drift detected via document hash comparison",
      "detection_signals": ["document hash differs from indexed snapshot"],
      "default_impact_level": "actionable",
      "recommended_agents": ["rag-source", "scope-guardian"]
    }
  ]
}
```

Custom categories are considered alongside the 12 built-in categories during classification.

---

## 7. Agent Contracts

For each council agent: role, autonomy level, tools (Claude Code tool names), input files, output structure, prohibitions, graceful degradation behavior, and dispatch invocation.

The agent definitions in `agents/<name>.md` use Claude Code agent frontmatter:

```yaml
---
name: architect
description: Reviews sprint output against overall spec/plan coherence; proposes plan amendments
model: sonnet
maxTurns: 30
tools: Read, Glob, Grep
context: fork
thinking: { type: adaptive, effort: high }
---
```

`context: fork` is the critical flag — it gives the agent a fresh execution context, so the orchestrator's reasoning never leaks in.

### 7.1 Orchestrator (Henkaten Council Orchestrator)

[src §4.1 lines 135–157]

| Field | Value |
|---|---|
| Autonomy | Level 4 (coordinate sequences under supervision) |
| Tools | `Read, Glob, Grep, Bash, Write, Task` (full tool access for routing + minor corrections) |
| Context | `inherit` — the orchestrator is the conductor; it must see what the user typed |
| Sub-agents it dispatches | architect, scope-guardian, henkaten-detector, retrospective, qa-regression (if enabled), rag-source (if enabled), plus any `custom_agents` |
| Defined in | `agents/orchestrator.md` |

**Responsibilities:**
- Routes analytical work to bounded worker agents (never performs analysis itself when a worker should)
- Applies minor corrections (Level 3 actions): updating `.council/` working files, technical notes on next contract, status pending→done
- Presents major corrections for human approval (Level 5 gate)
- Manages `decision-log.jsonl` and `henka-register.jsonl` via `scripts/append-*.py`
- Enforces halt conditions
- Compacts context between sprints (writes to `.council/sessions/<timestamp>.md`)
- Maximum 4 agents per review (the bounded fan-out rule)

**Prohibited:**
- Performing analysis that a worker agent should do
- Modifying `features.json`, `spec.md`, `sprints.json` without Level 5 approval
- Self-approving or fabricating evidence
- Passing internal reasoning to subagents (subagent dispatches use ONLY file paths + structured task)
- Creating unbounded retry loops

**Dispatch invocation pattern (from a skill):**

```python
# Inside a skill — pseudo-code showing the dispatch envelope
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

DO NOT modify any files. DO NOT invoke other agents. DO NOT propose adding features not in features.json.
Cite specific evidence for every claim. Classify confidence (observed/inferred/speculative).
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

**Inputs (read-only):** `.harness/sprint-state.json`, `.harness/evals/sprint-{NN}-r{R}.md`, `.harness/contracts/sprint-{NN}.md`, `.harness/spec.md`, `.harness/features.json`, `.harness/sprints.json`, project source structure.

**Outputs:** Coherence Rating (1–5), Drift Indicators (specific divergences), Dependency Health, Proposed Amendments (bounded, evidence-cited), Risk Flags.

**Invoked:** After every sprint completion, before next sprint begins.

**Prohibited:** Modify any files. Approve own recommendations. Invoke other agents. Propose adding features not in original `features.json`. Make claims without specific evidence.

**Graceful degradation:** Missing `spec.md` → assess coherence against contracts only, note reduced confidence. Missing `sprints.json` → skip dependency check, note in `missing_evidence`. Missing eval reports → status: `partial`. Missing source code → skip structural assessment.

### 7.3 Scope Guardian

[src §4.3 lines 196–225]

| Field | Value |
|---|---|
| Autonomy | Level 2 |
| Tools | `Read, Glob, Grep` |
| Context | `fork` |
| Defined in | `agents/scope-guardian.md` |

**Inputs:** `.harness/features.json` (current vs original), contracts, evals, sprints.json, spec.md, `.council/henka-register.jsonl`.

**Outputs:** Feature Integrity Check (all features present and unmodified?), Scope Drift Detection, Unauthorized Changes, Feature Status Assessment, Correction Proposals with evidence.

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

**Inputs:** evals, contracts, sprint-state.json, sprints.json, henka-register (avoid duplicates), decision-log, **and Phase 2 trine-eval transcripts (`.harness/transcripts/sprint-{NN}-r{R}.json`)** — *the spec didn't have these; we add them as a richer evidence source.*

**Outputs:** New Change Points (henka_id, category, impact_level, description, affected_artifacts, response_type, evidence), Pattern Observations across sprint history, Escalation Flags.

**Invoked:** After every sprint completion. Pre-sprint optional. On-demand via `/council-detect`.

**Prohibited:** Modify any files. Determine the response (only classify). Duplicate existing records. Classify ambiguous observations as "blocking" without strong evidence. Conservative impact assessment (err toward lower).

**Graceful degradation:** Missing eval → status: `partial`. Missing henka-register → first run. Missing sprint-state.json → skip cross-sprint pattern detection.

### 7.5 Retrospective

[src §4.5 lines 259–289]

| Field | Value |
|---|---|
| Autonomy | Level 2 |
| Tools | `Read, Glob, Grep` |
| Context | `fork` |
| Defined in | `agents/retrospective.md` |

**Inputs:** All evals, sprint-state, all contracts, henka-register, decision-log, standard-work.json, prior retrospectives, **and Phase 2 trine-eval `summary.md` cross-sprint metrics** — *useful for pattern analysis*.

**Outputs:** Learning Points, Pattern Analysis, Standard Work Proposals (sizing, contract quality, evaluation approach), Kaizen Recommendation (highest-priority single improvement).

**Invoked:** After every sprint (brief capture). Full retrospective on `/council-retro`.

**Prohibited:** Modify `standard-work.json` directly (only propose). Modify any files. Recommend process changes without 2+ sprints of evidence (or 1 with strong deterministic). Recommend expanding scope or adding features. Must distinguish product issues (Generator's concern) from process issues.

**Graceful degradation:** Missing evals → status: `partial`. Missing standard-work → blank profile. Only 1 sprint complete → learning points only, defer pattern analysis.

### 7.6 QA Regression

[src §4.6 lines 292–322]

| Field | Value |
|---|---|
| Autonomy | Level 2 |
| Tools | `Read, Glob, Grep` |
| Context | `fork` |
| Defined in | `agents/qa-regression.md` |
| Status | **Initially `proposed` (CC-001 from source spec)**; agent file ships but is not in default fan-out |

**Inputs:** ALL evaluation reports (historical comparison is primary), all contracts, sprint-state, features, spec, sprints.json, henka-register, project source, **and Phase 2 trine-eval `regression.json` graduated invariants**.

**Outputs:** Regression Detection (later work broke earlier work, with before/after evidence), Consistency Check (cross-sprint contradictions), Integration Assessment, Criteria Drift Analysis, Accumulation Issues, Recommended Regression Tests.

**Prohibited:** Modify any files. Re-run or override evaluator grades. Distinguish actual regressions from incomplete features. Every regression claim must cite eval report section from sprint A vs sprint B.

### 7.7 RAG Source

[src §4.7 lines 326–357]

| Field | Value |
|---|---|
| Autonomy | Level 1 |
| Tools | `Read, Glob, Grep` |
| Context | `fork` |
| Defined in | `agents/rag-source.md` |
| Status | **Initially `proposed` (CC-001 from source spec)**; agent file ships but is not in default fan-out |

**Inputs:** spec, features, config.json, source material directories, henka-register, decision-log, other agents' outputs (when invoked for verification).

**Outputs:** Source Inventory, Traceability Check, Citation Verification (confirmed/unsupported/missing/partial), Source Change Detection, Relevant Context Surfaced.

**Three functions:** Retrieval, Verification, Change detection.

**Prohibited:** Modify any files. Interpret requirements (only verify traceability). Fabricate citations. Assume missing source means requirement is invalid.

### 7.8 Archaeologist (Pre-Project Utility — Out of Council Loop)

[src §4.8 lines 361–386]

Operates outside the governance loop. User-invocable directly.

| Field | Value |
|---|---|
| Autonomy | N/A (not in loop) |
| Tools | `Read, Glob, Grep` |
| Context | `fork` |
| Defined in | `agents/archaeologist.md` (optional v0.1 deliverable; could defer to v0.2) |
| User-invocable | YES |

**Output:** Structured archaeological report covering: entity types & domain model, data flows & integration points, task patterns & workflows, failure modes & fragility points, reusable assets, accidental vs essential complexity assessment. Each finding has `Finding`, `Evidence (file + location)`, `Interpretation`. Findings classified as `observed | inferred | speculative`.

**When invoked:** Before `/council-kickoff` when migrating/rebuilding existing systems. When onboarding new data source types. When inheriting unfamiliar codebases.

**Open question:** Does v0.1 of henka-council ship the Archaeologist? Or defer to v0.2? See Section 14, Question 11.

### 7.9 Prompt Forge (Pre-Processing Utility — Out of Council Loop)

[src §4.9 lines 389–415]

Operates outside the governance loop. User-invocable directly.

| Field | Value |
|---|---|
| Autonomy | N/A (not in loop) |
| Tools | `Read, Glob, Grep` |
| Defined in | `agents/prompt-forge.md` (optional v0.1; defer to v0.2 likely) |
| User-invocable | YES |

**Capabilities:** Intent extraction, constraint discovery, success criteria derivation, decomposition, context grounding, anti-pattern detection, SME enrichment, format structuring.

**Open question:** v0.1 or v0.2? See Section 14, Question 11.

---

## 8. Workflow Contracts (Skills)

Each skill is a `skills/<name>/SKILL.md` file with a body that documents the step-by-step procedure. Skills dispatch agents via `Task`. Skills do not call other skills directly.

### 8.1 `/council-kickoff` — Bootstrap Governance

[src §8.1 lines 641–688]

| Field | Value |
|---|---|
| Defined in | `skills/council-kickoff/SKILL.md` |
| Frontmatter `allowed-tools` | `Read, Glob, Grep, Bash, Write, Task` |
| Invoked as | `/henka-council:council-kickoff` |

**Procedure:**

1. Check for existing state (re-bootstrap option, layer on existing `.harness/`, manual review)
2. Gather project context (read README, package files, source). Identify project type. Ask 1–2 clarifying questions.
3. Create `.council/config.json` with `project_type`, `council_agents`, `autonomy_levels`, `review_frequency`, `halt_conditions`, `correction_thresholds`, `henkaten_taxonomy_version: "1.0"`.
4. Create `.council/council-manifest.json` with `council_id: "COUNCIL-0001"`, list 4 (or 6 if CC-001 approved) core agents, `trigger_type: "kickoff"`, `status: "assembled"`.
5. Initialize remaining state: empty `henka-register.jsonl`, `decision-log.jsonl` with first entry (council-assembly), initial `standard-work.json` (version 1.0, empty improvements), `course-corrections/`, `retrospectives/`, `audit-log.jsonl`, `sessions/`.
5B. Git baseline: `git init` if needed; `git checkout -b project-{name}` (or accept existing branch); stage and commit `.harness/` + `.council/` baseline. Message: `council-kickoff: baseline state (DEC-0001)`.
6. **Delegate to trine-eval planning** via `/trine-eval:harness-kickoff`. Detect contracts-first methodology. If contracts-first → generate Phase 1 design sprints (D1–D6). Otherwise → standard trine-eval planning. trine-eval creates: `config.json`, `spec.md`, `features.json`, `sprints.json`, `sprint-state.json`, `progress.md`.
6B. Write governance signal to `.harness/config.json`: `{governance: {enabled: true, plugin: "henka-council", council_state_path: ".council/", review_frequency: "every-sprint"}}`.
7. Present governance plan to user (council composition, autonomy levels, halt conditions, project plan summary). Offer to start `/council-autorun`.

### 8.2 `/council-autorun` — Sprint Loop with Governance

[src §8.2 lines 691–842]

The most complex skill — wraps trine-eval's sprint execution with pre-sprint and post-sprint council activity. Documented in detail because the integration boundary lives here.

| Field | Value |
|---|---|
| Defined in | `skills/council-autorun/SKILL.md` |
| Frontmatter `allowed-tools` | `Read, Glob, Grep, Bash, Write, Task` |
| Invoked as | `/henka-council:council-autorun` |

**Procedure:**

**Step 0 — Load state.** Read `.harness/` and `.council/` state. Determine starting sprint from `sprint-state.json.current_sprint`. If `.council/` missing → instruct user to run `/council-kickoff` first.

**FOR EACH SPRINT in `.harness/sprints.json`:**

**Step 1A — Pre-Sprint Henkaten Check.**
- Create sprint branch: `git checkout -b sprint-{NN}` if git available.
- `git diff` between main and current state for observed evidence.
- Check `.harness/` state changes (mtime vs last decision-log entry).
- Check for unresolved Henkaten records (status not `closed`).
- Check for user-modified project files outside governance.
- **Routing:**
  - Blocking/high-risk records exist → HALT (Step 1F).
  - State changes detected → invoke henkaten-detector (subagent dispatch), classify findings.
  - Actionable/informational records only → attach as context notes for the sprint.
  - No changes → proceed normally.

**Step 1B — Execute Sprint via trine-eval.** Invoke `/trine-eval:harness-sprint {NN}`. Wait for completion. trine-eval's loop runs internally:
- Contract negotiation (2 rounds max)
- Implementation
- Evaluation (forked-context evaluator)
- Retry loop
- Update `sprint-state.json` and `progress.md`
- Git checkpoint

The council does NOT enter trine-eval's loop. trine-eval is unaware of council during this step. The council picks up at completion.

**Step 1C — Council Review (Fan-Out → Fan-In).**

Check `review_frequency`:
- `every-sprint` → always convene
- `every-N-sprints` → convene if sprint % N == 0 OR sprint failed
- `on-failure-only` → convene only if sprint failed
- `manual-only` → skip; user must invoke `/council-review`

**Fan-out:** Dispatch each agent as an isolated subagent via `Task` with ONLY file paths and structured constraints. Never pass orchestrator reasoning.

```
Agent 1 — architect: dispatch
Agent 2 — scope-guardian: dispatch
Agent 3 — henkaten-detector: dispatch
Agent 4 — retrospective: dispatch
Agents 5–6 — qa-regression, rag-source: dispatch IF enabled (CC-001 status)
Agents 7+ — custom_agents from config: dispatch
```

The orchestrator skill can dispatch these in parallel (`run_in_background: true`) and await all results, or sequentially (lower token cost; longer wall-clock). **Recommendation: parallel for v0.1**, with a config knob `council_agents.dispatch_mode: parallel | sequential`.

**Fan-in:** Each agent's output is written by the orchestrator to `.council/course-corrections/after-sprint-{NN}.md` under that agent's section. Evidence quality check: verify each agent provided `evidence_class`, `confidence`, `coverage`. If agent returned `status: error` → log failure, skip that section, note gap.

**Henkaten Register Write Procedure:**
- Determine next `HK-NNNN` ID (read henka-register, find max, increment)
- Validate against `schemas/henka-record.schema.json`
- Set `status: "classified"`
- Set `sprint_context: {NN}`
- Append via `scripts/append-henka.py` (which validates and uses `>>` redirection)

**Lifecycle transitions:**
- `classified` → `assessed` (orchestrator evaluates impact, routes response)
- `assessed` → `responded` (decision-log entry created addressing this record)
- `responded` → `closed` (resolution confirmed effective)

**Standard Work Evolution:**
- Read current `standard-work.json`
- Read retrospective proposals from this sprint
- Identify new proposals (not already reflected)
- Present as before/after for Level 5 approval
- On approval → update `standard-work.json`, log decision
- On rejection → log with `rejected` status

**Step 1D — Course Correction.**

Read `correction_thresholds` from `.council/config.json`.

**MINOR (auto-apply, Level 3):**
- Technical notes additions to next contract
- Clarifying evaluation criteria (weight change ≤10%)
- Updating `.council/` state files
- Lessons learned to `progress.md`
- Noting new dependencies (informational)
- Updating feature status pending → done

**MAJOR (present to user, Level 5):**
- Sprint reordering
- `features.json` modifications
- `spec.md` amendments
- Criteria weight changes >10%
- Adding new sprints
- Architectural pivots
- Governance rule changes

When presenting major: cite evidence, show before/after, explain impact on remaining sprints, ask for explicit approval. On approval → apply and log. On rejection → log without change.

Write `.council/course-corrections/after-sprint-{NN}.md` (always, regardless of minor/major mix).

**Git operations:**
- Minor corrections: commit with `DEC-{ID}: {description}`
- Sprint PASS: present `git merge sprint-{NN} → main` for Level 5 approval. On approval: `git merge --no-ff`, tag `sprint-{NN}-complete`.
- Sprint FAIL: preserve branch for forensics; checkout main.

**Step 1E — Decision Logging.** Write entry to `decision-log.jsonl` via `scripts/append-decision.py` with: sequential `DEC-NNNN`, timestamp, `council_agents_involved`, `evidence_cited`, `decision_type`, `decision_outcome`, `applied_automatically`, `user_approval_required`, `affected_files`, `linked_henka_id`, `sprint_context`, `autonomy_level_used`. If decision responds to henka records → set `linked_henka_id`, update record status to `responded` (or `closed` if fully resolved).

**Step 1F — Halt Conditions Check.** From `config.halt_conditions`:
1. `blocking_henkaten`: any blocking record not closed → HALT
2. `max_consecutive_failures`: last N sprints all failed → HALT
3. `high_risk_henkaten`: any high-risk record not closed → HALT
4. `user_intervention_requested`: major correction pending → HALT

Recovery options per condition documented; present to user when halting.

**Step 1G — Context Compaction.** Compact to ≤500 words. Runs unconditionally after every sprint.
- **Preserve:** sprint number, all verdicts, open Henkaten records, unresolved decisions, active halt conditions, standard work changes this session.
- **Discard:** implementation details, tool call history, agent reasoning traces, full eval/report text, contract negotiation discussion.
- Write to `.council/sessions/<UTC-ISO8601>.md`.
- Source of truth: `.harness/` and `.council/` files (always re-read).

**Step 1H — Next Sprint or Exit.**
- More sprints + no halt → increment, return to Step 1A.
- All sprints complete → final summary, suggest `/council-retro`.
- Halted → present reason and evidence, wait for user input.

### 8.3 `/council-review` — Manual Review

[src §8.3 lines 845–857]

Convene full council on-demand. Same isolation contract as autorun Step 1C.

| Field | Value |
|---|---|
| Defined in | `skills/council-review/SKILL.md` |
| Allowed tools | `Read, Glob, Grep, Bash, Write, Task` |

Steps: Load context → fan-out → fan-in → present findings → propose corrections (minor/major) → log decisions → present summary.

### 8.4 `/council-retro` — Full Retrospective

[src §8.4 lines 860–877]

Comprehensive cross-sprint retrospective. Identifies patterns and proposes kaizen.

| Field | Value |
|---|---|
| Defined in | `skills/council-retro/SKILL.md` |
| Allowed tools | `Read, Glob, Grep, Bash, Write, Task` |

Steps: Load FULL history → invoke retrospective agent (cross-sprint scope) → invoke architect (supporting structural assessment) → synthesize report → present standard-work proposals for Level 5 approval → log decisions → write `.council/retrospectives/full-{date}.md`.

**Integration with trine-eval:** This skill reads `.harness/summary.md` (the cross-sprint summary trine-eval produces) and `.harness/regression/regression.json` (graduated invariants). The trine-eval summary is a primary input for the Retrospective agent's pattern analysis.

### 8.5 `/council-detect` — On-Demand Detection

[src §8.5 lines 880–898]

Detect and classify change-points outside the autorun loop.

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

Steps: Load baseline → invoke henkaten-detector → review output, apply sensitivity thresholds → write new records (if any) → present findings.

---

## 9. Autonomy and Enforcement in Claude Code

How Levels 0–5 from Section 2.4 map to concrete enforcement mechanisms.

### 9.1 Level Mapping

| Level | Enforcement Mechanism in Claude Code |
|---|---|
| **0 — Observe only** | Agent frontmatter `tools: Read, Glob, Grep` only. No `Write`, `Edit`, `Bash`. |
| **1 — Classify and recommend** | Same tools as Level 0. Output is the agent's response text only — no file write. |
| **2 — Propose drafts** | Agent frontmatter may include `Write` but the agent prompt restricts writes to `.council/course-corrections/<draft>.md` only. Hooks (Section 9.4) block writes to other paths. |
| **3 — Auto-apply minor** | Orchestrator skill has `Write, Bash` and writes to `.council/` working files. Permission rules in `.claude/settings.json` allow writes to `.council/*` paths automatically. |
| **4 — Coordinate sequences** | Orchestrator skill executes the autorun loop. The user is informed of the scope at sprint start; the loop is bounded by sprint count from `sprints.json`. |
| **5 — Reserved (human-only)** | Skill explicitly asks the user via the chat: `"Approve sprint reorder? (yes/no)"`. The skill blocks until the user types `yes`. The harness's permission system also denies high-impact Bash commands (`git push`, `git reset --hard`, etc.) at the `deny` tier — user must explicitly opt in. |

### 9.2 The `tools:` Frontmatter Contract

Each agent declares its allowed tools. The list **must match** the agent's autonomy level. Examples:

```yaml
# agents/architect.md (Level 2)
tools: Read, Glob, Grep
# Architect proposes only via its response text; the orchestrator parses and persists.
# Architect does NOT have Write — proposals are not written by the agent itself.
```

```yaml
# agents/orchestrator.md (Level 4)
tools: Read, Glob, Grep, Bash, Write, Task
# Orchestrator writes to .council/, dispatches subagents, runs git commands.
```

This is the first layer of enforcement: an agent without `Write` *cannot* write files, period — Claude Code blocks the call.

### 9.3 `.claude/settings.json` Permission Rules

The plugin ships a `settings.json` template with tiered Bash command rules:

```json
{
  "permissions": {
    "allow": [
      "git status",
      "git diff",
      "git log",
      "git show",
      "git branch -l",
      "git ls-files"
    ],
    "ask": [
      "git add *",
      "git commit -m *",
      "git checkout -b *",
      "git tag *",
      "git stash *"
    ],
    "deny": [
      "git push *",
      "git push --force *",
      "git reset --hard *",
      "git rebase -i *",
      "git merge *"
    ]
  }
}
```

The user installs the plugin and chooses to merge these rules into their project `.claude/settings.json`. **Level 5 git operations (`push`, `reset --hard`, `rebase -i`, `merge`) are denied by default**; the user must explicitly move them to `ask` or `allow` per project. This enforces the Level 5 "human approval per action" rule at the runtime layer.

### 9.4 PreToolUse / PostToolUse Hooks

The plugin ships three hooks under `hooks/`:

**`hooks/enforce-append-only.sh`** — PreToolUse hook. Blocks `Write`/`Edit` operations against the protected jsonl files.

```bash
#!/bin/bash
# PreToolUse hook. Block in-place modification of append-only logs.
# Only allows Bash with >> redirection (the sanctioned append path).
# Reads the tool name and args from environment variables CC_TOOL_NAME, CC_TOOL_INPUT.

if [[ "$CC_TOOL_NAME" == "Write" || "$CC_TOOL_NAME" == "Edit" ]]; then
    file_path=$(echo "$CC_TOOL_INPUT" | jq -r '.file_path // empty')
    case "$file_path" in
        *.council/decision-log.jsonl|*.council/henka-register.jsonl|*.council/audit-log.jsonl)
            echo "BLOCKED: $file_path is append-only. Use scripts/append-*.py instead." >&2
            exit 1
            ;;
    esac
fi
exit 0
```

**`hooks/log-tool-call.sh`** — PostToolUse hook. Appends every successful tool call to `.council/audit-log.jsonl`.

**`hooks/session-stopped-marker.sh`** — Stop hook. Writes a session-stopped marker to `progress.md` (matches trine-eval's existing pattern).

### 9.5 Approval Gates as Chat Prompts

Level 5 actions that aren't covered by `settings.json` permission rules (e.g., modifying `features.json`, applying a major correction) are gated by explicit chat prompts in the orchestrator skill:

> **Major correction proposed:** Reorder sprints 4 and 5 because architect identified circular dependency.
>
> **Evidence:**
> - architect: "Sprint 4 depends on Sprint 5's auth module per .harness/sprints.json:42"
> - sprint-state.json shows Sprint 4 attempted but cannot complete
>
> **Before:** sprints.json sprint 4 = auth, sprint 5 = users
> **After:** sprints.json sprint 4 = users, sprint 5 = auth
>
> **Impact:** Sprint 4 retry will succeed; Sprint 5 timeline shifts by 1 day.
>
> **Approve this change?** (yes / no / revise)

The skill blocks until the user types a response. On `yes`: apply, log `DEC-NNNN` with `user_approval_status: approved`. On `no`: log with `rejected`, continue without change. On `revise`: ask user for new proposal text, retry approval.

### 9.6 The Dispatch Envelope (Bounded Self-Organization)

[src §11 Rule 4]

The orchestrator skill must use a standardized dispatch envelope when calling `Task`. The envelope specifies:

1. **Subagent type** (`henka-council:<agent>`)
2. **Description** (one line)
3. **Prompt template** with sections:
   - Role statement (1 sentence)
   - Inputs list (file paths only)
   - Output structure (template path or inline schema)
   - Prohibitions (boilerplate from agent's autonomy level)
   - Evidence-classification reminder

The envelope template lives at `templates/dispatch-envelope.md`. Every dispatch site in every skill uses this template. **No skill may call another skill via `Task`** — that path is reserved for agent dispatches only.

This implements Rule 4 (bounded self-organization) by ensuring agents receive only file paths, never orchestrator reasoning, and ensuring agents cannot recursively dispatch other agents.

---

## 10. trine-eval Integration Contract

The integration boundary between henka-council and trine-eval. This is where the two plugins meet.

### 10.1 What henka-council Reads from `.harness/`

All read-only:

- `.harness/config.json` — for project_type and rubric (informs council's project_type setting)
- `.harness/spec.md` — coherence review input
- `.harness/features.json` — scope guardian input (canonical feature list)
- `.harness/sprints.json` — sprint plan / dependency review input
- `.harness/sprint-state.json` — current sprint status / pass/fail history
- `.harness/progress.md` — narrative context
- `.harness/contracts/sprint-{NN}.md` — sprint contract for scope comparison
- `.harness/contracts/sprint-{NN}.tasks.json` — *Phase 2; machine-readable taxonomy used by scope-guardian and qa-regression*
- `.harness/evals/sprint-{NN}-r{R}.md` — eval reports (primary evidence for all agents)
- `.harness/evals/sprint-{NN}-r{R}-t{T}.md` — *Phase 2 multi-trial eval reports; used for consistency analysis by retrospective + qa-regression*
- `.harness/transcripts/sprint-{NN}-r{R}.json` — *Phase 2 structured transcripts; richer evidence for henkaten-detector*
- `.harness/regression/regression.json` — *Phase 2 graduated invariants; flagged as Method/Process Henkaten on update*
- `.harness/summary.md` — *cross-sprint summary; primary input for council-retro*

### 10.2 What henka-council Writes to `.harness/`

**Exactly one optional key, written once at kickoff:**

```json
{
  "governance": {
    "enabled": true,
    "plugin": "henka-council",
    "council_state_path": ".council/",
    "review_frequency": "every-sprint"
  }
}
```

This is informational. trine-eval does not require it. trine-eval Phase 2 should add a new section in `skills/harness-sprint/SKILL.md` documenting that this key may be present and that trine-eval should not attempt to interpret it. **This is a non-blocking addition to trine-eval** — see Section 14, Question 8.

**Any other modification to `.harness/` requires Level 5 approval and is logged as a `course-correction-major` decision.**

### 10.3 Phase 2 Features the Council Leverages

Sprint 12's deliverables in trine-eval enable richer council behavior:

| trine-eval Phase 2 Feature | Council Use |
|---|---|
| `tasks.json` per sprint | Scope guardian uses the `task_id` + `criterion` mapping for exact-match scope drift detection (no fuzzy matching) |
| Multi-trial evals (`-tT.md`) | qa-regression compares trial files for non-determinism — flags consistency violations as `quality-defect-anomaly` Henkaten |
| Structured transcripts (`.json`) | henkaten-detector uses `tool_calls` and `criteria_audit` arrays as observed evidence (high confidence) |
| `criteria_audit` `verified_via_command` flags | qa-regression flags any sprint where flags don't match `tool_calls` as a `quality-defect-anomaly` |
| Regression invariants (`regression.json`) | Each new graduation is a `method-process-change` Henkaten (informational) |
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
Step 1B: dispatch /trine-eval:harness-sprint NN
  |   (trine-eval's full loop runs internally)
  |   - contract negotiation
  |   - implementation
  |   - evaluation (forked-context evaluator)
  |   - retry loop
  |   - sprint state update
  |   - git commit
  v
trine-eval returns control with sprint-state.json updated
  |
  v
Step 1C: council fan-out (architect, scope-guardian, henkaten-detector,
                          retrospective, [qa-regression], [rag-source])
  |   - All agents read .harness/ (read-only)
  |   - Each writes structured findings to its agent output
  v
Step 1D: orchestrator merges -> .council/course-corrections/after-sprint-NN.md
  |   - Identifies minor vs major
  |   - Auto-applies minor (Level 3)
  |   - Presents major to user (Level 5 gate)
  v
Step 1E: append decision log entries
  |
  v
Step 1F: halt check
  |
  v
Step 1G: compact context
  |
  v
Step 1H: next sprint or exit
```

trine-eval does not know it's being wrapped. trine-eval continues to behave exactly as it does standalone. The council layer is additive.

### 10.5 Backward Compatibility

A trine-eval project without henka-council still works. A henka-council project without trine-eval cannot exist (the council depends on a sprint engine). This asymmetry is intentional and matches the source spec [src §17].

---

## 11. Schema Catalog (Verbatim from Source)

[src §10 lines 944–1124]

The 10 schemas are platform-agnostic and ship as JSON Schema files in `schemas/`. Carried forward verbatim. Each schema maps to one state-file shape.

| # | Schema File | Used For | Append-only? |
|---|---|---|---|
| 11.1 | `council-config.schema.json` | `.council/config.json` | No (Level 5 modifications allowed) |
| 11.2 | `council-manifest.schema.json` | `.council/council-manifest.json` | No |
| 11.3 | `henka-record.schema.json` | Each line of `henka-register.jsonl` | **Yes** |
| 11.4 | `decision-log-entry.schema.json` | Each line of `decision-log.jsonl` | **Yes** |
| 11.5 | `standard-work.schema.json` | `.council/standard-work.json` | No (versioned, supersession allowed) |
| 11.6 | `audit-log-entry.schema.json` | Each line of `audit-log.jsonl` | **Yes** |
| 11.7 | `human-approval-log-entry.schema.json` | Standalone approval records (optional file) | **Yes** |
| 11.8 | `conflict-resolution-entry.schema.json` | Conflict records (in-line within decision-log) | **Yes** |
| 11.9 | `evidence-index.schema.json` | Optional evidence citation index | No |
| 11.10 | `integration-signal.schema.json` | The `governance` key in `.harness/config.json` | No |

Field details preserved verbatim from source §10. Each schema validates on append via `scripts/append-*.py`.

---

## 12. Standard Work Template (Contracts-First)

[src §15 lines 1389–1459]

Carried forward as `templates/contracts-first-standard-work.json`. Used when the target project follows contracts-first methodology (hexagonal architecture, design-before-implementation, Phase 1 D1–D6 sprints).

Sizing heuristics, 5 documented failure patterns (FP-CF-001 through FP-CF-005), 2 evaluation improvements (EI-CF-001, EI-CF-002), 6 workflow notes (WN-CF-001 through WN-CF-006). Carried verbatim. The template seeds initial `standard-work.json` for contracts-first projects; subsequent retrospectives evolve it.

---

## 13. Risks and Mitigations

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| Self-referential complexity (henka-council uses trine-eval to build itself; manages trine-eval) | High | Medium | Keep boundaries strict. Treat trine-eval as a stable dependency. henka-council never governs its own construction; it's built straight through trine-eval. |
| Plugin cache lag (Sprint 12 lesson learned) | High | Low | Bump henka-council version on every release. Document the manual cache refresh path in README. |
| Subagent isolation depends on prompt construction discipline | Medium | High | Standardize the dispatch envelope template. Every dispatch site in every skill uses it. Review every dispatch in sprint contract reviews. |
| Hooks platform-specific (Bash) — cross-platform issues | Medium | Medium | Hooks under `hooks/` use Bash but must work on Git Bash on Windows (which the user has). Test in CI. Provide PowerShell equivalents in `hooks/win/` if needed. |
| Six agents fan-out per sprint = high token cost | Medium | Medium | Configurable `review_frequency` (every-sprint default; can switch to every-N or on-failure-only). Optional batched mode similar to trine-eval's Batch API. |
| Append-only enforcement requires hook to be active | Low | High | Document hook installation in README. Add a self-check in `/council-kickoff` that verifies hooks are configured; warn user if not. |
| Schema drift between agents and orchestrator | Low | High | Single source-of-truth `schemas/`. Validation scripts run before every write. |
| Custom henkaten categories diverge across projects | Medium | Low | The taxonomy is intentionally extensible. Custom categories live per-project in `.council/config.json`; cross-project portability is not promised. |
| trine-eval Phase 2 features (transcripts, tasks.json) absent in older trine-eval | Low | Low | Council reads these as optional inputs; absent → graceful degradation per Rule 11. henka-council's minimum required trine-eval version is 0.3.0+ (Phase 2 baseline). |
| Approval gate UX is chat-text-only (vs VSCode UI prompt) | Medium | Low | Use `mcp__ccd_session__spawn_task` for items the user should review later; use clear "Approve / Reject / Revise / Defer" multi-choice prompts in the chat for in-the-moment decisions. |

---

## 14. Decisions Required Before Sprint Planning

The following design questions need explicit answers before the kickoff. Each has a recommended default with rationale; the user may override any.

### Q1. Spelling: `henka` vs `henkaten`?

The Toyota Production System term is **henkaten** (変化点, "change point"). The repo is named `henka-council` (a contraction). The source spec consistently uses "henkaten-council".

**Options:**
- **A.** Rename repo and plugin to `henkaten-council` (canonical Japanese; matches source spec).
- **B.** Keep `henka-council` and use "henka" throughout the plugin (simpler English contraction; matches existing repo name).
- **C.** Repo `henka-council`; plugin name `henkaten-council`; concept terms stay "henkaten" in agent text and user-facing docs.

**Recommendation:** **C** — keeps the repo URL stable, uses the canonical Japanese term in concept-bearing surfaces. The plugin `name` field in `plugin.json` can be `henkaten-council` while the repo / cli command stays `henka-council`. *Lowest disruption.*

### Q2. Plugin Packaging — Same Marketplace, or Separate?

Three options:
- **A.** New marketplace: `~/.claude/local-marketplaces/henka-council/` (mirrors trine-eval's setup).
- **B.** Add henka-council as a second plugin to the existing `trine-eval` marketplace.
- **C.** Joint distribution: ship henka-council inside trine-eval's repo as a sub-plugin.

**Recommendation:** **A** (new marketplace). Keeps the plugins independent at the marketplace layer; simpler for users who want trine-eval without governance overhead. Matches the spec's "two composable independent layers" principle.

### Q3. Sprint-Engine Integration Mode

- **A.** Wrap-only — council unaware to trine-eval (matches spec exactly; trine-eval gets a one-line addition documenting the optional `governance` key).
- **B.** Plugin-aware — trine-eval Phase 3 introduces a "council awareness" config that surfaces additional hooks (e.g., explicitly emits a "sprint about to begin" event the council can subscribe to).

**Recommendation:** **A**. The spec's design works because trine-eval is unaware. Plugin-aware mode would couple the two and complicate trine-eval. Defer plugin-aware mode to a future sprint if needed.

### Q4. CC-001 Status — Ship qa-regression and rag-source as Default Agents?

The source spec lists CC-001 as "filed but not yet applied" — qa-regression and rag-source agent files exist but are not in the default fan-out.

**Options:**
- **A.** Honor source spec status: ship the agent files, but `.council/config.json` `council_agents` defaults to `[architect, scope-guardian, henkaten-detector, retrospective]` only.
- **B.** Apply CC-001 in v0.1: defaults include all 6.
- **C.** Apply CC-001 conditionally: defaults include all 6 only when `project_type == "rag-system"` (rag-source is most useful there).

**Recommendation:** **A**. Faithful to source spec. The user can opt in by editing `.council/config.json`. Avoids opening a sub-debate during the kickoff. Document CC-001 status in the README with instructions for opting in.

### Q5. First Sprint Scope — How Much Does Sprint 1 Deliver?

Two viable phasings:
- **A.** Sprint 1 ships only the kickoff skill + manifest + minimal agent files (architect only). Sprint 2 adds scope-guardian + henkaten-detector. Sprint 3 adds retrospective. Sprint 4 ships the autorun loop. (4–6 sprints; small per-sprint scope.)
- **B.** Sprint 1 ships kickoff + 4 default agents (no autorun yet). Sprint 2 ships autorun + course-correction. Sprint 3 ships hooks + audit log. (3 sprints; medium per-sprint scope.)
- **C.** Sprint 1 ships everything as a single MVP. Subsequent sprints harden + add CC-001 + add Archaeologist/Prompt Forge.

**Recommendation:** **A**. Matches the contracts-first methodology in source §15 ("one deliverable per sprint, stop after each for human feedback"). Earliest feedback. Lowest blast radius if early architecture decisions are wrong.

### Q6. Agent Dispatch Model — Parallel or Sequential?

When the council fans out 4–6 agents per sprint:
- **A.** Sequential — orchestrator dispatches one agent at a time, awaits each result before next dispatch. Slower, deterministic, lower peak token usage.
- **B.** Parallel — orchestrator uses `run_in_background: true` to dispatch all agents concurrently, then awaits all. Faster, peak token usage is higher.
- **C.** Configurable — `.council/config.json` knob `dispatch_mode: parallel | sequential`. Default sequential for v0.1, can opt into parallel.

**Recommendation:** **C** with default `sequential`. Easier to debug initially. `parallel` becomes a Phase 2 enhancement after the fan-out logic is stable.

### Q7. trine-eval Phase 2 Features — Adopt All?

The council can leverage transcripts, tasks.json, regression.json, multi-trial eval files, criteria_audit, etc. (see Section 10.3).

**Options:**
- **A.** Adopt all in v0.1 (richer evidence; council relies on Phase 2 trine-eval).
- **B.** Adopt only `tasks.json` and `regression.json` in v0.1; transcripts and multi-trial in v0.2.
- **C.** Adopt none in v0.1 (council reads only the same files local-eval had — keeps spec equivalence).

**Recommendation:** **A**. The Phase 2 features materially strengthen the council's evidence quality. Council should require trine-eval ≥ 0.3.0 (the Phase 2 release).

### Q8. Should trine-eval's Skill Documentation Mention the `governance` Key?

The spec writes a `governance` key to `.harness/config.json` at kickoff. trine-eval would benefit from a one-line note in `skills/harness-sprint/SKILL.md` saying "this key may be present; trine-eval does not interpret it."

**Options:**
- **A.** Include a small PR to trine-eval adding the documentation note (1-line addition).
- **B.** Don't touch trine-eval; document the key only in henka-council's README.

**Recommendation:** **A**. The note is non-blocking, makes the integration explicit, and follows the "evidence-first" rule (a future trine-eval contributor reading the file shouldn't be surprised by an unfamiliar config key). Open as a small PR after henka-council 0.1.0 ships.

### Q9. Hook Layer — Ship Enforcement Hooks or Document and Rely on Discipline?

- **A.** Ship `hooks/enforce-append-only.sh`, `hooks/log-tool-call.sh`, `hooks/session-stopped-marker.sh`. The user installs them by adding three lines to `.claude/settings.json`.
- **B.** Document the rules but don't ship hooks. Rely on agent prompts and orchestrator discipline.
- **C.** Ship the hooks but make them opt-in in `.council/config.json`.

**Recommendation:** **A**. Defense-in-depth. Hooks are mechanically enforced; agent discipline is best-effort. The cost is minimal (three small Bash scripts) and the benefit is large (prevents an accidental Edit on `decision-log.jsonl` from corrupting the audit trail).

### Q10. Bootstrap from VSCode State?

The source spec §16 lists current henka records (HK-0003, HK-0004) and decisions (DEC-0001, DEC-0002). Carry these forward to henka-council as starting state? Or treat the Claude Code reimplementation as a fresh start?

**Options:**
- **A.** Carry forward verbatim. Initial `henka-register.jsonl` contains HK-0003, HK-0004; initial `decision-log.jsonl` contains DEC-0001, DEC-0002.
- **B.** Carry forward but renumber (HK-0001, HK-0002, DEC-0001, DEC-0002) to avoid the appearance of skipped IDs.
- **C.** Fresh start. Reference source-spec history in CHANGELOG.md but don't replay records.

**Recommendation:** **C**. The henka-council Claude Code reimplementation is structurally different from the VSCode original (different agent definitions, different tool surface, different runtime). The historical records belong to the VSCode codebase; replaying them creates false continuity. Reference the original work in CHANGELOG / README.

### Q11. Archaeologist + Prompt Forge — v0.1 or v0.2?

These two utilities (source §4.8, §4.9) operate outside the governance loop. They're useful but not part of the core council.

**Options:**
- **A.** Ship in v0.1. Adds 2 sprint deliverables.
- **B.** Defer to v0.2.
- **C.** Ship Archaeologist (more directly useful for kickoff against existing codebases); defer Prompt Forge.

**Recommendation:** **B**. Keep v0.1 focused on the council itself. Archaeologist and Prompt Forge are valuable but conceptually separate (they're pre-processing utilities, not governance agents). Defer to v0.2.

### Q12. Sprint Methodology for henka-council Itself

henka-council's own development uses trine-eval. What sprint methodology?
- **A.** Standard trine-eval sprints (no contracts-first design phase).
- **B.** Contracts-first methodology — Phase 1 D1–D6 design sprints (D1 Domain Models, D2 Port Definitions, D3 Adapter Roadmap, D4 Contract Tests, D5 ADRs, D6 Vertical Slice Plan), then Phase 2 implementation sprints.
- **C.** Hybrid — D1 Schema Definitions + D2 Agent Contracts as design phase, then implementation.

**Recommendation:** **C**. The schemas and agent contracts are the structurally-load-bearing artifacts; locking them in design before implementation reduces refactor risk. Two design sprints (D1: Schema Definitions; D2: Agent Contracts) → then 5–6 implementation sprints.

---

## 15. Phase 0 → Phase 1 Transition

After this proposal is approved (or revised):

1. **Apply the user's decisions** from Section 14 to a final spec — overwrite this proposal with a clean v1.0 reflecting the chosen options, OR keep this proposal and add an addendum.
2. **`cd henka-council; /trine-eval:harness-kickoff`** — kickoff against henka-council with the proposal as the product spec input. The kickoff skill seeds:
   - `.harness/spec.md` ← derived from this proposal's Sections 2, 5, 6, 7, 8, 11, 12 (the contract-bearing sections)
   - `.harness/features.json` ← derived from Section 4 (plugin layout) and Section 7 (agent contracts) — every agent file, every skill file, every schema, every hook is a feature
   - `.harness/sprints.json` ← derived from Section 14 Q5 + Q12 (the sprint plan)
   - `.harness/config.json` ← `project_type: "cli-tool"` (per user's earlier decision), `rubric: "cli-tool"`, sane Phase 2 knobs
3. **Review the trine-eval-generated spec/features/sprints** before any code is written. The kickoff is itself a Level 5 gate — if the generated artifacts diverge from this proposal in surprising ways, revise before proceeding.
4. **`/trine-eval:harness-sprint 1`** — run the first sprint. Per Q5 default, Sprint 1 ships kickoff skill + manifest + architect agent only.
5. **Iterate sprint by sprint.** Each sprint produces a working slice. Reviewer feedback on each sprint informs the next.
6. **At the end of Sprint 5–6, henka-council 0.1.0 ships.** Plugin can be installed; council can be applied to any trine-eval project.
7. **Phase 2 of henka-council** — Archaeologist, Prompt Forge, parallel dispatch mode, MCP-based git server (optional), additional rubrics for non-trine-eval sprint engines.

---

## 16. Appendix — Cross-Reference Table to Source Spec

For verification: every source spec section is addressed in this proposal.

| Source Section | This Proposal Section |
|---|---|
| §1 Concept and Purpose | §1 Executive Summary; §2 Conceptual Model |
| §2 Architecture | §2.1 Three-Layer Architecture |
| §3 Separation of Concerns | §5 State Model and File Inventory |
| §4 Agent Catalog | §7 Agent Contracts (subsections 7.1–7.9) |
| §5 Autonomy Model | §2.4; §9 Autonomy and Enforcement in Claude Code |
| §6 Henkaten Taxonomy | §6 The 12 Henkaten Categories |
| §7 Operating Model — Henkaten Loop | §2.3 The Henkaten Loop |
| §8 Workflows / Commands | §8 Workflow Contracts (Skills) |
| §9 State Model and File Inventory | §5 State Model and File Inventory |
| §10 Schema Catalog | §11 Schema Catalog (Verbatim from Source) |
| §11 Governance Rules | §2.5 The 12 Governance Rules |
| §12 Instruction Files | §4 Plugin Layout (`instructions/` dir) |
| §13 Git Lifecycle Integration | §3.3 The Git MCP Server — Drop or Keep?; §9.3 settings.json Permission Rules |
| §14 Templates | §4 Plugin Layout (`templates/` dir) |
| §15 Standard Work Template | §12 Standard Work Template (Contracts-First) |
| §16 Current State Snapshot | §14 Q10 Bootstrap from VSCode State? |
| §17 local-eval Integration Contract | §10 trine-eval Integration Contract |
| §18 Platform-Specific vs Platform-Agnostic | §3 Claude Code Environment Mapping |
| §19 Extensibility Model | §6.3 Custom Categories; §7 Custom Agents |

---

## 17. Sign-off Checklist

Before proceeding to `/trine-eval:harness-kickoff`, the user has reviewed and decided on:

- [ ] Section 14 Q1 — Naming (henka vs henkaten)
- [ ] Section 14 Q2 — Plugin packaging
- [ ] Section 14 Q3 — Sprint-engine integration mode
- [ ] Section 14 Q4 — CC-001 status (4-agent vs 6-agent default)
- [ ] Section 14 Q5 — Sprint 1 scope
- [ ] Section 14 Q6 — Agent dispatch model
- [ ] Section 14 Q7 — trine-eval Phase 2 features
- [ ] Section 14 Q8 — trine-eval governance-key documentation PR
- [ ] Section 14 Q9 — Enforcement hooks
- [ ] Section 14 Q10 — Bootstrap from VSCode state
- [ ] Section 14 Q11 — Archaeologist + Prompt Forge timing
- [ ] Section 14 Q12 — Sprint methodology
- [ ] Section 13 risks reviewed
- [ ] Section 4 plugin layout reviewed
- [ ] Section 7 agent contracts reviewed (per agent)
- [ ] Section 8 workflow contracts reviewed (per skill)
- [ ] Section 10 trine-eval integration contract reviewed
- [ ] Section 11 schema catalog reviewed (every schema's existence and shape)

After sign-off, this proposal becomes the authoritative input to `/trine-eval:harness-kickoff` and the basis for all subsequent sprint contracts.

---

*End of Phase 0 Proposal.*
