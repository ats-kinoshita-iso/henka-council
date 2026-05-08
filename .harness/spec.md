# henka-council — Product Specification v0.1

> **Source of authority:** All design decisions in this document derive from
> `docs/phase-0-proposal-v2.md` (v2.1 amendments applied 2026-05-07).
> Section references in parentheses resolve against that document.

---

## 1. Product Vision

henka-council is a **governance layer** that wraps a sprint execution engine
(trine-eval) with change-point detection, multi-agent review, bounded course
correction, and approval gates. It encodes the Toyota Production System concept
of a *henkaten* (変化点 — "change point"): every moment where conditions shift
is a potential source of defects, so changes must be detected, classified, and
consciously managed rather than absorbed silently (§1 Executive Summary). The
plugin is packaged as a Claude Code plugin (`~/.claude/local-marketplaces/
henka-council/`) that consumers install alongside trine-eval; trine-eval itself
remains unaware of and unchanged by the governance layer (§10.4).

---

## 2. Feature List

### Must-Have (v0.1)

These features represent the minimum complete implementation. Every file in the
plugin layout (§4), every schema in the catalog (§11), every agent contract
(§7), and every skill contract (§8) is a must-have feature. The seven pillars
of henkaten management (§2.6) are design constraints that apply to every
must-have feature.

#### Seven Pillars (Design Constraints — §2.6)

All implementation choices must be traceable to one of the seven pillars:

1. **DETECT** — state changes are observable continuously, classified by 4M
   axis and active/passive origin, distinguishing council-initiated from
   externally-observed changes.
2. **HALT** — halt authority is distributed to every agent; alert (recoverable)
   and stop (committed) are distinguished; the social cost of halting is
   structurally reduced via thank-the-puller acknowledgment.
3. **DIAGNOSE** — every claim is grounded in a re-runnable observation
   conformant with the verification syntax allowlist (§7.0.2, v2.1 amendment
   A1); the audit trail records "what was observed and how."
4. **DECIDE** — significant decisions are reached via the nemawashi four-stage
   walkthrough (yes/refine/disagree handles) before a single ratify prompt is
   posed (§8.2 Step 1D, §2.6 Pillar 4).
5. **PREVENT** — every governance rule that can be enforced by mechanism (hooks,
   permission system, schema validation) is enforced that way; agent discipline
   is the last line of defense (§9.4, Q13).
6. **PROPAGATE** — learning is propagated to subsequent sprints via the yokoten
   explicit pre-sprint substep (§8.2 Step 1A.5), observable in sprint contracts,
   not just in a lessons-learned log.
7. **IMPROVE** — improvement is enacted at three cadences (per-sprint mini,
   per-cycle PDCA, per-period jishuken) with explicit mechanisms for each
   (§7.5, §8.4–§8.6).

#### Plugin Layout Files (§4)

**Plugin metadata and configuration:**
- `.claude-plugin/plugin.json` — version, name (`henkaten-council`), author, license
- `.mcp.json` — placeholder; empty (Option A; §3.3)
- `.claude/settings.json` — tiered Bash allowlist (`allow`/`ask`/`deny`) enforcing autonomy levels (§9.3)
- `README.md` — user-facing intro and install instructions
- `LICENSE`
- `CLAUDE.md` — plugin-side CLAUDE.md loaded when council skills run

**Agent files (`agents/`) — seven files (§7):**
- `agents/orchestrator.md` — Level 4, tools: Read/Glob/Grep/Bash/Write/Task, `inherit` context
- `agents/architect.md` — Level 2, tools: Read/Glob/Grep, `fork` context
- `agents/scope-guardian.md` — Level 2, tools: Read/Glob/Grep, `fork` context
- `agents/henkaten-detector.md` — Level 1, tools: Read/Glob/Grep, `fork` context
- `agents/retrospective.md` — Level 2, tools: Read/Glob/Grep, `fork` context; three modes (mini/pdca/jishuken)
- `agents/qa-regression.md` — Level 2, `fork` context; ships but not in default fan-out (CC-001 opt-in per Q4)
- `agents/rag-source.md` — Level 1, `fork` context; ships but not in default fan-out (CC-001 opt-in per Q4)

**Skill files (`skills/`) — seven slash commands (§8):**
- `skills/council-kickoff/SKILL.md` — bootstraps `.council/`, writes governance signal, delegates to trine-eval
- `skills/council-autorun/SKILL.md` — outer sprint loop, Steps 1A–1I including yokoten review and mini retro
- `skills/council-review/SKILL.md` — manual on-demand fan-out; `--restore-autonomy` flag
- `skills/council-retro-mini/SKILL.md` — per-sprint automatic capture (≤30s, no standard-work proposals)
- `skills/council-retro/SKILL.md` — per-cycle PDCA retrospective (every-N sprints, default 5)
- `skills/council-jishuken/SKILL.md` — per-period reflection workshop, user-invoked, reflection-only
- `skills/council-detect/SKILL.md` — on-demand henkaten detection with sensitivity thresholds

**Behavioral instruction files (`instructions/`) — four files (§4):**
- `instructions/controlled-artifacts.md`
- `instructions/evidence-first.md` — revised in v2: re-runnable verification required (R4)
- `instructions/human-approval.md` — revised in v2: nemawashi walkthrough for major decisions (R5)
- `instructions/andon-protocol.md` — thank-the-puller, swarming, alert vs stop (R2/R3)
- `instructions/prompt-injection-defense.md`

**Output templates (`templates/`) — eight files (§4):**
- `templates/council-review-report.md`
- `templates/course-correction.md`
- `templates/retrospective-mini.md` — per-sprint capture shape
- `templates/retrospective-pdca.md` — Plan/Do/Check/Act sections explicit
- `templates/jishuken-workshop.md` — Reflection Notes/Open Questions/Hypotheses
- `templates/nemawashi-position-paper.md` — four-stage walkthrough position paper
- `templates/dispatch-envelope.md` — standardized subagent dispatch template; the ONLY dispatch path
- `templates/contracts-first-standard-work.json` — seeds initial `standard-work.json` for contracts-first projects

**Hook files (`hooks/`) — eight files (four Bash + four PowerShell; §9.4, v2.1 amendment A7):**
- `hooks/enforce-append-only.sh` — PreToolUse: blocks Write/Edit on protected `.jsonl` files
- `hooks/enforce-reversibility.sh` — PreToolUse: denies irreversible Bash commands at effective autonomy < 5 (R9)
- `hooks/log-tool-call.sh` — PostToolUse: appends to `.council/audit-log.jsonl`; tracks andon pull-rate per agent (Q14)
- `hooks/session-stopped-marker.sh` — Stop hook: marks uncommitted sprint state in `progress.md`
- `hooks/win/enforce-append-only.ps1` — PowerShell equivalent (v2.1 amendment A7)
- `hooks/win/enforce-reversibility.ps1` — PowerShell equivalent (v2.1 amendment A7)
- `hooks/win/log-tool-call.ps1` — PowerShell equivalent (v2.1 amendment A7)
- `hooks/win/session-stopped-marker.ps1` — PowerShell equivalent (v2.1 amendment A7)

**Ancillary scripts (`scripts/`) — eight Python scripts (§4):**
- `scripts/validate-council-config.py` — validates `.council/config.json`
- `scripts/validate-henka-record.py` — validates henka-record lines
- `scripts/validate-decision-log.py` — validates decision-log lines
- `scripts/append-henka.py` — validates then appends to `henka-register.jsonl`; the ONLY sanctioned write path
- `scripts/append-decision.py` — validates then appends to `decision-log.jsonl`; the ONLY sanctioned write path
- `scripts/compute-evidence-class.py` — helper for evidence classification
- `scripts/update-effective-autonomy.py` — writes `.council/state/effective-autonomy.json` (R10; Q20)
- `scripts/run-verification.py` — re-runs an `observed` claim's verification command; enforces v2.1 syntax allowlist (R4; amendment A1)
- `scripts/rotate-audit-log.py` — rotates `audit-log.jsonl` at 50 MB threshold; writes a `DEC` entry with SHA-256 of rotated file (v2.1 amendment A12)

#### JSON Schemas (§11) — eleven schema files

All eleven schemas live in `schemas/`. The three schemas marked REVISED carry v2
fields; the one marked NEW is absent from v1:

- `schemas/council-config.schema.json` (11.1)
- `schemas/council-manifest.schema.json` (11.2)
- `schemas/henka-record.schema.json` (11.3, **REVISED v2**) — adds `fourM_axis` (R8), `change_origin` active|passive (R1), `andon_signal` block (R2), `verification` inside evidence items (R4), `yokoten` block with `applicable_to_subsequent_sprints`/`adaptation_notes`/`deployed_to` (R6)
- `schemas/decision-log-entry.schema.json` (11.4, **REVISED v2**) — adds `effective_autonomy_at_decision` (R10), `reversibility` (R9), `nemawashi_walkthrough_version` (R5), `andon_resolution` (R3)
- `schemas/standard-work.schema.json` (11.5)
- `schemas/audit-log-entry.schema.json` (11.6)
- `schemas/human-approval-log-entry.schema.json` (11.7)
- `schemas/conflict-resolution-entry.schema.json` (11.8)
- `schemas/evidence-index.schema.json` (11.9)
- `schemas/integration-signal.schema.json` (11.10) — the `governance` key written to `.harness/config.json`; includes `taxonomy_version: "2.0"`
- `schemas/effective-autonomy.schema.json` (11.11, **NEW v2/R10**) — `{level, last_change, reason, restored_when, trigger_history[]}`

#### Agent Contracts — behavioral specifications (§7)

Each agent file must implement the contract defined in §7, including the common
capabilities inherited from `instructions/andon-protocol.md` and
`instructions/evidence-first.md` (§7.0):

- **Andon authority (§7.0.1):** every agent can return `{andon_signal: {type: "alert"|"stop", reason, evidence[], swarm_request[]}}`. The orchestrator MUST honor `stop` immediately. Every andon triggers a thank-the-puller acknowledgment written verbatim before any analytical response.
- **Genchi-genbutsu evidence (§7.0.2, v2.1 amendment A1):** every claim carries `evidence_class` (observed/inferred/speculative), `confidence`, and — for `observed` claims — a `verification` string that MUST match the allowlisted forms (read-only git/grep/cat/jq/test/schema-validators). `scripts/run-verification.py` enforces the allowlist with a 10s timeout and project-root CWD. Non-conformant strings are rejected and logged as `agent-capability-change` Henkaten (informational). Divergence between re-run result and agent's report logs a `quality-defect-anomaly` Henkaten (high impact).

Per-agent specifications:
- **Orchestrator (§7.1):** Level 4; routes all analytical work to workers; applies minor reversible corrections (Level 3); presents major/irreversible via nemawashi; honors all andon signals; spot-checks one random `observed` claim per fan-in; manages dynamic autonomy floor (R10); max 4 agents per fan-out.
- **Architect (§7.2):** Level 2; coherence rating (1–5), drift indicators with `verification` commands, dependency health, proposed amendments, risk flags; invoked after every sprint and at kickoff.
- **Scope Guardian (§7.3):** Level 2; feature integrity check, scope drift detection, unauthorized changes; exact string matching required; MOST CRITICAL prohibition: must never modify `features.json`.
- **Henkaten Detector (§7.4):** Level 1; classifies new change points with `change_origin: active|passive`, 4M axis, sub-type, impact level, `verification` evidence; applies scheduled-vs-unscheduled suppression for `agent-capability-change` during active sprint (§6.7, v2.1 amendment A3).
- **Retrospective (§7.5):** Level 2; three modes dispatched by invoking skill — mini (capture-only, no standard-work proposals), pdca (Plan/Do/Check/Act + standard-work proposals), jishuken (reflection-only, no standard-work proposals); populates `yokoten` block when closing Henkaten records (R6).
- **QA Regression (§7.6):** Level 2; ships with `status: proposed`; not in default fan-out; regression detection, consistency check, criteria drift analysis.
- **RAG Source (§7.7):** Level 1; ships with `status: proposed`; not in default fan-out; source inventory, traceability check, citation verification.

#### Henkaten Taxonomy (§6) — 4M lens with 13 sub-types

The primary classification lens is 4M (Man / Machine / Material / Method). Every
henka-record must declare `fourM_axis` and one of the 13 sub-types:

- **Man axis:** `agent-capability-change` (NEW v2/Q18) — model upgrades, prompt-template revisions, agent-file edits, plugin version bumps. Scheduled-vs-unscheduled suppression rule applies during active sprint (§6.7, v2.1 amendment A3): edits within sprint scope are deliverables, not change-points.
- **Machine axis:** `tool-environment-change`, `dependency-change`
- **Material axis:** `source-material-change`, `requirement-change`
- **Method axis:** `scope-change`, `method-process-change`, `measurement-criteria-change`, `schedule-priority-change`, `risk-compliance-change`, `quality-defect-anomaly`, `retrospective-improvement`, `architectural-discovery`

Every henka-record also carries `change_origin: active|passive` (R1): active =
deliberately initiated (henkoten 変更点); passive = emerged unbidden (henkaten
変化点 strict sense). Passive changes default to lower confidence/impact unless
corroborated by a second signal (§6.3).

Impact levels: `informational` → `actionable` → `blocking` → `high-risk`.
Response types: `log-only`, `auto-correct`, `propose-to-user`, `escalate`,
`andon-alert`, `andon-stop`.

#### Skill Workflow Contracts (§8)

Each skill file must implement the procedure detailed in §8, including:

- **`/council-kickoff` (§8.1):** creates complete `.council/` baseline (7 files + 5 directories + `state/effective-autonomy.json` initialized to Level 4); writes governance signal to `.harness/config.json`; delegates to `/trine-eval:harness-kickoff`; configures `andon_takt_seconds: 600` (v2.1 amendment A6) and `dynamic_autonomy_thresholds: {andon_stop_distinct_originators_required: 2, andon_stop_consecutive_count: 3, ...}` (v2.1 amendment A2).
- **`/council-autorun` (§8.2):** implements the full 9-step sprint loop (Steps 1A–1I):
  - Step 1A: pre-sprint henkaten check including plugin manifest diff and unresolved record check
  - Step 1A.5: yokoten review — surfaces applicable adaptation prompts; includes ratify-once shortcut for yokoten records naming ≥3 sprints or `applicable_to_subsequent_sprints: ["all"]` (v2.1 amendment A9)
  - Step 1B: delegates sprint execution to `/trine-eval:harness-sprint`
  - Step 1C: fan-out (sequential default per Q6) with andon handling; parallel swarm dispatch even in sequential mode (v2.1 amendment A6); verification spot-check via `scripts/run-verification.py` with allowlist enforcement; fan-in writes to `.council/course-corrections/after-sprint-{NN}.md`
  - Step 1D: reversibility check (R9) before classifying minor/major; minor reversible auto-applied at Level 3; major OR irreversible uses nemawashi four-stage walkthrough (R5); position paper written to `.council/proposed/DEC-{NNNN}.md`; ratified papers archived to `proposed/archive/` (v2.1 amendment A4)
  - Step 1E: decision-log entry via `scripts/append-decision.py` with `effective_autonomy_at_decision` and `reversibility`
  - Step 1F: halt conditions check including dynamic autonomy floor breach (R10); andon-stop trigger requires ≥2 distinct originator agents (v2.1 amendment A2)
  - Step 1G: context compaction to `.council/sessions/<UTC-ISO8601>.md`
  - Step 1H: per-sprint mini retrospective via `/council-retro-mini` inline
  - Step 1I: next sprint or per-cycle PDCA trigger at `sprint % cycle_length == 0`
- **`/council-review` (§8.3):** manual fan-out with same andon/verification protocols as autorun; `--restore-autonomy` flag resets dynamic floor drop (the single canonical reset path; §9.3 / v2.1 amendment A5).
- **`/council-retro-mini` (§8.4):** dispatches retrospective agent in `mini` mode; ≤30s; output to `retrospectives/sprint-{NN}-mini.md`; no user input required.
- **`/council-retro` (§8.5):** per-cycle PDCA; retrospective agent in `pdca` mode + architect; synthesizes `.council/retrospectives/full-{date}.md`; standard-work proposals presented via nemawashi for Level 5 approval; reads `.harness/summary.md` and `.harness/regression/regression.json`.
- **`/council-jishuken` (§8.6):** user-invoked reflection workshop; retrospective agent in `jishuken` mode + architect; output to `.council/jishuken/<topic>-<date>.md`; explicitly decoupled from standard-work proposals (Q16); jishuken does NOT modify `state/effective-autonomy.json`.
- **`/council-detect` (§8.7):** on-demand detection with sensitivity thresholds; applies `change_origin` classification (R1); records new henka-register entries.

#### Autonomy and Enforcement Model (§2.4, §9)

- **Six autonomy levels (§2.4.1):** L0 (observe-only) through L5 (human-only), mapped to concrete Claude Code enforcement mechanisms (§9.1).
- **Reversibility axis (§2.4.2, R9):** every action tagged `reversible|irreversible`; L3–L4 may auto-execute reversible actions; irreversible actions auto-escalate to L5 regardless of nominal level.
- **Dynamic autonomy floor (§2.4.3, R10):** temporary level drop on: 2 consecutive FAIL sprints (L4→L3); 3 consecutive `andon_stop` events from ≥2 distinct originator agents (all L2→L1; v2.1 amendment A2); any `active` high-risk henkaten (all→L1). State observable in `.council/state/effective-autonomy.json`.
- **12 governance rules (§2.5):** all 12 rules are active constraints; Rule 1 (Evidence-First) and Rule 4 (Bounded Self-Organization) carry v2 revisions. Rule 4 carve-out (v2.1 amendment A10): `andon_signal: stop` is mandatory and bypasses Rule 4.
- **Mechanism-enforced rules (§9.4, Q13):** four rules enforced by mechanism — append-only logs (hook), features.json modification (hook + Level 5 gate), irreversible Bash commands (reversibility hook), schema validation on append (scripts).
- **`.claude/settings.json` permission rules (§9.3):** ships tiered allowlist; `git push *`, `git reset --hard *`, `git rebase -i *`, `git merge *` in default `deny` tier. Orchestrator-issued `git merge` on sprint PASS requires user to move to `ask` tier or execute manually; `/council-kickoff` surfaces as a one-time setup prompt (v2.1 amendment A11).
- **trine-eval integration (§10):** council reads `.harness/` state as read-only input; writes exactly one optional key (`governance`) at kickoff; any other `.harness/` modification requires Level 5 approval; requires trine-eval ≥ 0.3.0 (Q7).
- **Standard work template (§12):** `templates/contracts-first-standard-work.json` carries sizing heuristics, FP-CF-001 through FP-CF-005, EI-CF-001/EI-CF-002, WN-CF-001 through WN-CF-006.

#### `.council/` Runtime State (§5.2)

The following files and directories are created by `/council-kickoff` in the
target project (not in the plugin source):

- `config.json`, `council-manifest.json` — governance settings and active council composition
- `henka-register.jsonl` — append-only; `scripts/append-henka.py` only
- `decision-log.jsonl` — append-only; `scripts/append-decision.py` only
- `audit-log.jsonl` — append-only; PostToolUse hook only
- `standard-work.json` — retrospective proposes; user approves at L5; orchestrator writes
- `course-corrections/after-sprint-{NN}.md` — one per sprint boundary
- `proposed/DEC-{NNNN}.md` — nemawashi position papers
- `proposed/archive/` — ratified or superseded position papers archived here (v2.1 amendment A4)
- `retrospectives/sprint-{NN}-mini.md` — per-sprint capture
- `retrospectives/full-{date}.md` — per-cycle PDCA
- `jishuken/<topic>-<date>.md` — per-period reflection workshops
- `sessions/<UTC-ISO8601>.md` — compacted session notes
- `state/effective-autonomy.json` — live effective autonomy observable by external systems (R10/Q20)

---

### Should-Have (v0.1)

These features significantly improve the quality of the v0.1 deliverable and are
required for meaningful acceptance testing (§15.5, v2.1 amendment A8):

- **Schema test fixtures (D1 acceptance):** for each of the 11 schemas, ship `tests/schemas/<schema>/valid/*.json` (≥3 examples) and `tests/schemas/<schema>/invalid/*.json` (≥3 with documented violations). `scripts/validate-*.py` unit-tested against both directories.
- **Hook tests (S3 acceptance):** fixture-driven tests for each hook verifying:
  - `enforce-append-only`: Write against `henka-register.jsonl` returns exit code 1; `scripts/append-henka.py` succeeds.
  - `enforce-reversibility`: at L3 `git push` blocked; at L5 allowed.
  - `log-tool-call`: tool call produces a corresponding audit-log line.
  - `rotate-audit-log`: 50 MB+ fixture produces gzipped archive + fresh current file + `DEC` entry with matching SHA-256.
  - Hook tests run in CI on both `windows-latest` (PowerShell hooks) and `ubuntu-latest` (Bash hooks; v2.1 amendment A7).
- **End-to-end fixture project (S4 and S6 acceptance):** minimal trine-eval project at `tests/fixtures/dummy-project/` with `.harness/spec.md`, `.harness/features.json`, and `.harness/sprints.json` for two trivial features; stub source that passes trivial evals. S4 acceptance asserts: `.council/` baseline created; both sprints PASS; ≥1 henkaten classified; andon swarming exercised by injected fault; verification spot-check produces audit-log entry per sprint; decision-log has `effective_autonomy_at_decision` and `reversibility` on every entry. S6 acceptance extends: `/council-retro-mini` produces `retrospectives/sprint-{NN}-mini.md`; `/council-retro` produces PDCA file with all four sections; `/council-jishuken` produces jishuken file with `standard-work.json` unchanged.
- **trine-eval compatibility matrix:** `docs/trine-eval-compat.md` mapping council features to minimum required trine-eval minor versions (v2.1 amendment A12).
- **Audit-log rotation policy:** `scripts/rotate-audit-log.py` with 50 MB threshold documented in README (v2.1 amendment A12).

---

### Nice-to-Have (out of v0.1, deferred to v0.2 — §15 "Out of v0.1")

- **Archaeologist agent** (§7.8) — pre-project utility (Q11: deferred)
- **Prompt Forge agent** (§7.9) — pre-processing utility (Q11: deferred)
- **Parallel dispatch by default** (Q6: sequential default in v0.1; parallel as opt-in config knob `dispatch_mode`)
- **MCP-based git server** (§3.3 Option B: deferred; direct Bash used in v0.1)
- **`evaluator-bias-change` Man-axis sub-type** (Q18: deferred; requires statistical comparison not available in v0.1)
- **Per-action reversibility classification** (Q19: per-tool in v0.1; per-action in v0.2)
- **Direct jishuken-to-standard-work promotion** (Q16: indirect path through `/council-retro` in v0.1)
- **CC-001 default-on** for qa-regression + rag-source (Q4: opt-in by default in v0.1)
- **`pass@k`/`pass^k` metrics consumption** from trine-eval Phase 2 (§10.3: council reads defensively; full analysis deferred)

---

## 3. User Interaction Patterns

### 3.1 The Seven Slash Commands (§8)

All commands are invoked as `/henka-council:<command>`:

| Command | Cadence | User action required |
|---|---|---|
| `/henka-council:council-kickoff` | Once per project | Provides project context; approves governance plan; answers 1–2 clarifying questions |
| `/henka-council:council-autorun` | Per project run | Monitors andon alerts; approves major decisions via nemawashi; approves per-cycle PDCA standard-work |
| `/henka-council:council-review` | On demand | Reviews manual fan-out findings; may pass `--restore-autonomy` to reset a floor drop |
| `/henka-council:council-retro-mini` | Per sprint (automatic) | No input required; runs inline at end of every sprint |
| `/henka-council:council-retro` | Per cycle (every-N sprints) | Reviews PDCA report; approves/rejects standard-work proposals via nemawashi |
| `/henka-council:council-jishuken` | Per period (user-invoked) | Declares topic; reviews reflection output; no corrective action triggered |
| `/henka-council:council-detect` | On demand | Reviews detected change-points and classification |

### 3.2 Nemawashi Four-Stage Walkthrough (§8.2 Step 1D, §9.5)

Major decisions (sprint reordering, `features.json` changes, `spec.md` amendments, criteria weight changes >10%, new sprints, architectural pivots, governance rule changes, or any irreversible action) use a four-stage walkthrough:

1. **Stage 1 — Present:** orchestrator writes position paper to `.council/proposed/DEC-{NNNN}.md` using `templates/nemawashi-position-paper.md`. User is invited: *"I've drafted a proposal at .council/proposed/DEC-{NNNN}.md. May I walk you through it?"*
2. **Stage 2 — Walk:** orchestrator presents each agent's perspective sequentially. After each: *"Does this agent's framing match your understanding? (yes / refine / disagree)"* — three handles, not two.
3. **Stage 3 — Align:** disagreements surfaced; position paper revised with `-rev{N}` suffix; Stage 2 repeated if needed.
4. **Stage 4 — Ratify:** once all agent perspectives aligned, final prompt: *"All perspectives aligned. Apply DEC-{NNNN}? (yes/no)"* — a confirmation, not a decision. Ratified papers archived to `proposed/archive/` (v2.1 amendment A4).

### 3.3 Thank-the-Puller Andon Protocol (§7.0.1, §8.2 Step 1C)

When any agent issues `andon_signal: alert` or `andon_signal: stop`:

- Orchestrator writes a thank-the-puller acknowledgment to the escalating agent *verbatim before* any analytical response. Enforced by the andon acknowledgment section in the orchestrator skill template.
- `stop` → orchestrator immediately halts the sprint loop; no analysis before honoring (v2.1 amendment A10).
- `alert` → orchestrator dispatches a swarm: originating agent + agents named in `swarm_request` (capped at 4). Swarm dispatches are parallel `Task` calls regardless of `dispatch_mode` setting (v2.1 amendment A6). Takt-bound: 600s wall-clock (`andon_takt_seconds`; v2.1 amendment A6). If swarm resolves within bound → sprint resumes with a logged decision; if not → escalates to `stop`.
- Per-agent andon pull-rates are tracked in `audit-log.jsonl`. Anomalous pull-rates surface as `quality-defect-anomaly` Henkaten (Q14).

### 3.4 Single-Prompt Minor Approval (§8.2 Step 1D)

Minor reversible corrections (technical notes, clarifications, progress updates, feature status pending→done, weight changes ≤10%) bypass the nemawashi walkthrough and use a single-line prompt:

> Apply minor correction: [description]?  (yes / no)

### 3.5 Yokoten Ratify-Once Shortcut (§8.2 Step 1A.5, v2.1 amendment A9)

When a yokoten record names `applicable_to_subsequent_sprints: ["all"]` or names ≥3 sprints, the user may ratify the adaptation **once** with scope `applies_to_remaining: true`. Subsequent sprints receive a single-prompt confirmation:

> Apply yokoten DEC-{ID} to sprint NN as ratified? (yes/no)

Answering `no` at any sprint boundary downgrades remaining sprints back to per-sprint ratification.

### 3.6 Autonomy-Floor Restore Path (§8.3, §2.4.3)

The single canonical path to reset a dynamic-autonomy floor drop is `/council-review --restore-autonomy`. There is no other path (jishuken does not modify state; v2.1 amendment A5).

---

## 4. Technical Constraints

### 4.1 Claude Code Plugin Format

- Plugin packaged for the Claude Code local marketplace: `~/.claude/local-marketplaces/henka-council/`
- Plugin metadata in `.claude-plugin/plugin.json` (Q2 default: new marketplace)
- All skills invoked as `/henka-council:<skill-name>`
- All agents invoked by the orchestrator via `Task` with `subagent_type: "henka-council:<agent-name>"`
- Plugin-side `CLAUDE.md` is loaded when council skills run

### 4.2 Cross-Platform Hooks (v2.1 Amendment A7)

Both Bash (macOS/Linux, Git Bash on Windows) and PowerShell (Windows native) hook variants must be shipped and must fire correctly on their respective platforms. CI validates both via GitHub Actions `windows-latest` and `ubuntu-latest`. This is a hard constraint; a hook that fires on one platform but silently fails on the other violates Pillar 5 (PREVENT) and fails the S3 acceptance criteria.

### 4.3 trine-eval Dependency

- Minimum trine-eval version: **0.3.0** (Q7)
- trine-eval is a hard dependency; henka-council cannot operate without it
- trine-eval is unmodified (Option A, §3.3); the council is additive
- A `docs/trine-eval-compat.md` compatibility matrix ships with the plugin (v2.1 amendment A12)

### 4.4 Append-Only State File Enforcement

The PreToolUse hook (`enforce-append-only.sh` / `.ps1`) blocks all `Write` and `Edit` tool operations against `henka-register.jsonl`, `decision-log.jsonl`, and `audit-log.jsonl`. The only sanctioned write paths are `scripts/append-henka.py` and `scripts/append-decision.py` (which validate before appending). The PostToolUse hook writes to `audit-log.jsonl`. This is a mechanism-enforced rule, not an agent-discipline rule (§9.4, Q13).

### 4.5 Verification Syntax Allowlist (v2.1 Amendment A1, §7.0.2)

`verification` strings in agent outputs MUST match one of the allowlisted prefixes:
`git diff…`/`git show…`/`git log…`/`git status`/`git branch…`/`git ls-files…`, `grep…`/`rg…` (read-only flags only), `cat…`/`head…`/`tail…`, `jq…` (against explicit file path; no `-i`), `python -m json.tool…`/`python scripts/validate-*.py…`, `test…`/`[…]` (POSIX file tests). Disallowed: write operations, network calls, shell redirects, pipe-to-shell, `eval`, `exec`, project source execution (other than allowlisted validators). `scripts/run-verification.py` enforces with 10s timeout, project-root CWD, and pre-invocation allowlist check.

### 4.6 Dynamic Autonomy Floor with Distinct-Originator Corroboration (§2.4.3, v2.1 Amendment A2)

The andon-stop floor-drop trigger requires 3 consecutive `andon_signal: stop` events from **≥2 distinct originator agents**. Three consecutive stops from the same agent are tracked as `quality-defect-anomaly` Henkaten (pull-rate anomaly) but do not by themselves drop the floor. This prevents a single flaky agent from locking the council into recommend-only mode.

### 4.7 Scheduled-vs-Unscheduled Suppression for `agent-capability-change` (§6.7, v2.1 Amendment A3)

During an active sprint, file edits to `agents/`, `instructions/`, `templates/`, `skills/`, `hooks/`, `scripts/`, or `schemas/` that fall within the active sprint's declared scope are classified as scheduled deliverables and do NOT generate a Henkaten record. Out-of-scope edits fire as `agent-capability-change` with `change_origin: passive`. Sprint scope is determined by reading (in priority order): `contracts/sprint-{NN}.tasks.json`, `contracts/sprint-{NN}.md` "Files in scope" section, `sprints.json` fallback. If none are available, the suppression rule is bypassed (fail-safe — every edit fires) and a `coverage` warning is emitted.

### 4.8 No Agent May Invoke Another Agent Directly (§2.5 Rule 4)

All agent dispatch flows through the orchestrator using `templates/dispatch-envelope.md`. No skill may call another skill via `Task`. The orchestrator passes only file paths and structured constraints to subagents — never internal reasoning.

### 4.9 features.json Is Sacred (§2.5 Rule 3)

No agent may remove, rename, or reinterpret features without Level 5 approval. Feature status updates (`pending` → `done`) are the only auto-applicable change. The scope-guardian's MOST CRITICAL prohibition is that it must never modify `features.json`.

### 4.10 Irreversibility Table and Double Defense-in-Depth (§2.4.2, §9.3)

`git push`, `git push --force`, `git reset --hard`, `git rebase -i`, `git tag -d` are tagged `irreversible` in both the reversibility hook's denylist AND the `settings.json` `deny` tier. Both layers must deny them. Even if a user moves them to `allow`, the orchestrator treats them as Level 5 / nemawashi-required.

---

## 5. Success Criteria

Each criterion is pass/fail based on observable file artifacts, hook exit codes, or end-to-end test assertions. Sprint references in parentheses indicate which sprint produces the tested deliverable.

### D1 — Schema Definitions

**SC-D1-1:** All 11 schema files exist at `schemas/*.schema.json` and are valid JSON Schema draft-07 (§11). Pass: `python -m json.tool schemas/*.schema.json` succeeds for all 11 files.

**SC-D1-2:** `henka-record.schema.json` contains required fields `fourM_axis` (enum: Man/Machine/Material/Method), `change_origin` (enum: active/passive), `andon_signal` block, `verification` inside evidence items, and `yokoten` block with `deployed_to` array (§11.3, v2 revisions). Pass: field names present in schema `required` or `properties`.

**SC-D1-3:** `decision-log-entry.schema.json` contains `effective_autonomy_at_decision`, `reversibility`, `nemawashi_walkthrough_version`, and `andon_resolution` (§11.4, v2 revisions). Pass: fields present in schema `properties`.

**SC-D1-4:** `effective-autonomy.schema.json` exists and contains `level` (integer 0–5), `last_change` (date-time), `reason` (string), `restored_when` (string or null), `trigger_history` array (§11.11, NEW v2). Pass: schema `required` includes `level`, `last_change`, `reason`.

**SC-D1-5:** For each of the 11 schemas, `tests/schemas/<schema>/valid/` contains ≥3 valid JSON fixtures and `tests/schemas/<schema>/invalid/` contains ≥3 invalid JSON fixtures with documented violations. Pass: directory listing confirms fixture count; all valid fixtures pass and all invalid fixtures fail the corresponding `scripts/validate-*.py` (§15.5).

**SC-D1-6:** `scripts/append-henka.py` and `scripts/append-decision.py` reject invalid input (malformed JSON, schema violations) with non-zero exit code. Pass: invalid fixture inputs cause both scripts to exit with code ≠ 0.

### D2 — Agent Contracts

**SC-D2-1:** All seven agent files exist at `agents/*.md` with frontmatter `tools:` and `context:` declarations matching their §7 contracts. Pass: each file parses; frontmatter `tools` lists match the level definitions in §9.1.

**SC-D2-2:** Each agent file references `@instructions/andon-protocol.md` and `@instructions/evidence-first.md` to inherit the common capabilities (§7.0). Pass: both strings present in each agent file body.

**SC-D2-3:** `agents/qa-regression.md` and `agents/rag-source.md` carry a `status: proposed` marker indicating they are not in the default fan-out (§7.6, §7.7, Q4). Pass: `status: proposed` string present in each file.

**SC-D2-4:** `agents/retrospective.md` documents all three dispatch modes (mini / pdca / jishuken) with their respective output shapes and standard-work-proposal permissions (§7.5). Pass: strings "mini", "pdca", "jishuken" all present in the file; "No standard-work proposals" explicitly stated for mini mode and jishuken mode.

**SC-D2-5:** All four instruction files exist at `instructions/*.md` including `andon-protocol.md` and `evidence-first.md` (§4). Pass: four files present.

**SC-D2-6:** `templates/dispatch-envelope.md` and `templates/nemawashi-position-paper.md` exist (§4, D2 deliverables). Pass: both files present.

### S1 — Kickoff Skill + Plugin Bootstrap

**SC-S1-1:** `.claude-plugin/plugin.json` exists and is valid JSON with `name: "henkaten-council"` (Q1), `version`, `author`, `license` fields (§4). Pass: JSON parses; required fields present.

**SC-S1-2:** Running `/henka-council:council-kickoff` against a fresh trine-eval fixture project creates all required `.council/` files and directories: `config.json`, `council-manifest.json`, `henka-register.jsonl`, `decision-log.jsonl`, `audit-log.jsonl`, `standard-work.json`, `course-corrections/`, `proposed/`, `proposed/archive/`, `retrospectives/`, `jishuken/`, `sessions/`, `state/effective-autonomy.json` (§8.1, §5.2). Pass: all 13 paths exist.

**SC-S1-3:** `.council/config.json` produced by kickoff contains `andon_takt_seconds: 600` and `dynamic_autonomy_thresholds.andon_stop_distinct_originators_required: 2` (§8.1 step 3, v2.1 amendments A2, A6). Pass: values present in JSON.

**SC-S1-4:** `.council/state/effective-autonomy.json` produced by kickoff contains `level: 4`, a valid `last_change` ISO 8601 timestamp, `reason: "initial"`, `restored_when: null` (§8.1 step 5, §9.7). Pass: JSON parses; fields present and match expected values.

**SC-S1-5:** `.harness/config.json` contains a `governance` key written by kickoff with `enabled: true`, `plugin: "henka-council"`, `council_state_path: ".council/"`, `taxonomy_version: "2.0"` (§10.2, §11.10). Pass: key present; values match.

### S2 — Core Agents + State Files

**SC-S2-1:** `agents/scope-guardian.md`, `agents/henkaten-detector.md`, and `agents/retrospective.md` exist with correct frontmatter (§7.3, §7.4, §7.5). Pass: three files present; frontmatter `tools:` and `context: fork` present.

**SC-S2-2:** When dispatched standalone with valid input files, each of the three agents (architect, scope-guardian, henkaten-detector) produces output that includes `evidence_class`, `confidence`, `coverage` sections, and at least one `verification` string per `observed` claim. Pass: output contains required keys (manual or scripted inspection of test output).

**SC-S2-3:** `scripts/append-henka.py` produces a valid `.jsonl` line when given a minimal valid henka-record JSON; the line validates against `schemas/henka-record.schema.json`. Pass: script exits 0; produced line passes validation.

**SC-S2-4:** `scripts/append-decision.py` produces a valid `.jsonl` line when given a minimal valid decision-log-entry JSON; the line validates against `schemas/decision-log-entry.schema.json`. Pass: script exits 0; produced line passes validation.

**SC-S2-5:** `scripts/update-effective-autonomy.py` writes a valid `state/effective-autonomy.json` when given a level change trigger; the written file validates against `schemas/effective-autonomy.schema.json` (§9.7, R10/Q20). Pass: file validates; `trigger_history` array grows by one entry.

### S3 — Hooks + Reversibility + Effective-Autonomy Tracking

**SC-S3-1:** `hooks/enforce-append-only.sh` exits with code 1 when a `Write` tool call targets `henka-register.jsonl`, `decision-log.jsonl`, or `audit-log.jsonl`. Passes for append via `scripts/append-henka.py`. This test runs on BOTH `ubuntu-latest` and `windows-latest` CI platforms (v2.1 amendment A7). Pass: exit code 1 on blocked operations; exit code 0 on allowed operations; both platforms pass.

**SC-S3-2:** `hooks/enforce-reversibility.sh` (and `.ps1`) blocks `git push`, `git reset --hard`, `git rebase -i` when `.council/state/effective-autonomy.json` contains `level: 3`. Allows the same commands when `level: 5`. Both platforms pass (§9.4.2, R9; v2.1 amendment A7). Pass: exit code 1 on blocked; exit code 0 on allowed; both platforms pass.

**SC-S3-3:** `hooks/log-tool-call.sh` (and `.ps1`) produces a valid audit-log line in `audit-log.jsonl` after any tool call. Line validates against `schemas/audit-log-entry.schema.json` (§9.4). Both platforms pass. Pass: line present; validates.

**SC-S3-4:** `scripts/rotate-audit-log.py` when given a fixture `audit-log.jsonl` exceeding 50 MB produces: a gzip-compressed archive file `audit-log-{ISO-week}.jsonl.gz`, a fresh empty `audit-log.jsonl`, and a `DEC-NNNN` decision-log entry whose body contains the SHA-256 of the rotated file (§13, v2.1 amendment A12). Pass: three artifacts present; SHA-256 in DEC entry matches archive hash.

### S4 — Council Autorun + Andon Protocol + Verification Spot-Check

**SC-S4-1:** `/henka-council:council-autorun` run against the `tests/fixtures/dummy-project/` fixture completes both sprints with `PASS` status. `.council/` baseline exists at sprint start (§15.5). Pass: `sprint-state.json` shows both sprints PASS.

**SC-S4-2:** At least one Henkaten record is detected and classified with valid `fourM_axis`, `change_origin`, `impact_level`, and ≥1 `evidence` item during the pre-sprint check (§15.5, assertion 3). Pass: `henka-register.jsonl` has ≥1 line; line validates against `henka-record.schema.json`.

**SC-S4-3:** An injected deliberately-failing eval criterion triggers `andon_signal: alert` from at least one agent; the swarm is dispatched and the audit-log records an `andon_resolution` entry (§15.5, assertion 4; §7.0.1). Pass: `andon_signal` key present in an agent output; `andon_resolution` present in corresponding `decision-log.jsonl` entry.

**SC-S4-4:** Verification spot-check runs per sprint: each sprint produces ≥1 audit-log entry recording the re-run of a `verification` command (§15.5, assertion 5; §8.2 Step 1C). Pass: audit-log contains entries with `verification_spot_check: true` for each sprint.

**SC-S4-5:** Every entry in `decision-log.jsonl` has non-null `effective_autonomy_at_decision` and non-null `reversibility` fields (§15.5, assertion 6; §11.4). Pass: `jq '[.effective_autonomy_at_decision, .reversibility] | all(. != null)' decision-log.jsonl` returns truthy for all lines.

**SC-S4-6:** `scripts/run-verification.py` rejects a verification string that does not match the allowlist (e.g. `curl https://example.com`) with a non-zero exit code and a log entry (§7.0.2, v2.1 amendment A1). Pass: exit code ≠ 0; audit-log entry with `agent-capability-change` (informational) present.

**SC-S4-7:** The andon-stop dynamic floor drop is NOT triggered by three consecutive stops from the same agent. It IS triggered when ≥2 distinct agents have each contributed to ≥3 cumulative stops (§2.4.3, v2.1 amendment A2). Pass: fixture test confirms floor drop does not fire on single-agent repeated stops; fires correctly on multi-agent scenario.

**SC-S4-8:** The scheduled-vs-unscheduled suppression rule prevents Henkaten records for agent file edits that are within the active sprint's declared scope. Edits outside scope fire normally (§6.7, v2.1 amendment A3). Pass: fixture test confirms zero Henkaten records for in-scope edits; ≥1 record for out-of-scope edit.

### S5 — Nemawashi Walkthrough + Course Corrections

**SC-S5-1:** A major decision (e.g. sprint reordering) triggered during `/council-autorun` produces a position paper at `.council/proposed/DEC-{NNNN}.md` conformant with `templates/nemawashi-position-paper.md` (§8.2 Step 1D Stage 1, §15 S5). Pass: file exists; all four stage sections present.

**SC-S5-2:** The walkthrough presents each agent's perspective sequentially with the three-handle prompt (yes / refine / disagree) before reaching the Stage 4 ratify prompt (§8.2 Step 1D Stage 2–4). Pass: walkthrough transcript shows three-handle prompts and final ratify prompt before any decision is applied.

**SC-S5-3:** After ratification, the position paper is moved to `.council/proposed/archive/DEC-{NNNN}.md` and the `decision-log.jsonl` entry's `nemawashi_walkthrough_version` field resolves to the archived path (§5.4, v2.1 amendment A4). Pass: original path absent; archive path present; decision-log path matches archive.

**SC-S5-4:** Minor reversible corrections use the single-prompt path and do NOT produce a position paper or invoke the nemawashi walkthrough (§8.2 Step 1D, Q15). Pass: no `DEC-*.md` file created for minor corrections; decision-log shows `nemawashi_walkthrough_version: null` on corresponding entries.

**SC-S5-5:** An irreversible action (e.g. `git push` attempted by orchestrator) auto-escalates to the nemawashi walkthrough regardless of nominal minor/major classification (§2.4.2, R9). Pass: decision-log shows `reversibility: irreversible` and non-null `nemawashi_walkthrough_version` for the action.

### S6 — Three Retrospective Cadences + Yokoten + Detect Skill

**SC-S6-1:** `/council-retro-mini` invoked at the end of each sprint produces `.council/retrospectives/sprint-{NN}-mini.md` containing Learning Points and Pattern Observations sections. Standard-work proposals section is absent (§8.4, §15.5). Pass: file exists; Learning Points and Pattern Observations sections present; "Standard Work Proposals" section absent.

**SC-S6-2:** `/council-retro` invoked after sprint 2 of the fixture project produces `.council/retrospectives/full-{date}.md` with all four PDCA sections (Plan, Do, Check, Act) and ≥1 standard-work proposal (§8.5, §15.5). Pass: file exists; all four PDCA section headers present; standard-work proposal section non-empty.

**SC-S6-3:** `/council-jishuken` invoked with a user-supplied topic produces `.council/jishuken/<topic>-<date>.md` with Reflection Notes, Open Questions, and Hypotheses for Future Investigation sections. `standard-work.json` is unchanged after jishuken (§8.6, §15.5, Q16). Pass: file exists; three section headers present; standard-work.json hash unchanged before and after.

**SC-S6-4:** `/council-detect` invoked on-demand classifies at least the detectable changes in the fixture project with `change_origin` populated. Output is written to `henka-register.jsonl` (§8.7). Pass: ≥1 new line in `henka-register.jsonl`; each line has non-null `change_origin`.

**SC-S6-5:** Yokoten propagation: a closed Henkaten record with non-empty `yokoten.applicable_to_subsequent_sprints` triggers an adaptation prompt at the next sprint's Step 1A.5. The ratify-once shortcut: a yokoten record naming ≥3 sprints can be bulk-ratified; subsequent sprints show single-prompt confirmation rather than a fresh nemawashi walkthrough (§8.2 Step 1A.5, v2.1 amendment A9). Pass: adaptation prompt appears in sprint output; bulk-ratified yokoten produces single-prompt confirmations for subsequent sprints.

**SC-S6-6:** `skills/council-jishuken/SKILL.md` does NOT contain `--reset-autonomy-floor` flag; only `/council-review --restore-autonomy` resets the floor. Pass: string `reset-autonomy-floor` absent from jishuken skill file (v2.1 amendment A5).

---

## 6. Design Tension Notes

The following tensions in v2 are surfaced for Generator sprints to be aware of.
These are not unresolved design decisions (all are resolved in v2) but areas
where implementation must be careful.

**Note 1: Self-referential development (§2.2).** During sprints D1–S6, henka-council is building itself via trine-eval. The scheduled-vs-unscheduled suppression rule (§6.7, v2.1 amendment A3) is specifically designed to prevent the henka-register from filling with records describing the plugin's own deliverables. Generators must ensure the suppression rule is active from D2 onward (as soon as henkaten-detector is defined).

**Note 2: Sequential dispatch default vs. parallel swarm (§8.2 Step 1C, v2.1 amendment A6).** Routine fan-out uses sequential dispatch; swarm dispatch is parallel even in sequential mode. The skill file must implement both code paths. The parallel swarm path should not be conflated with the Q6 `dispatch_mode` config knob — swarm parallelism is unconditional.

**Note 3: Git merge requires user opt-in (§9.3, v2.1 amendment A11).** The orchestrator cannot silently execute `git merge` even after a sprint PASS. The `/council-kickoff` skill must surface the `ask`-tier opt-in and must fall back to presenting the command for manual execution if the user has not opted in. Generator implementing S1 should ensure this one-time setup prompt is present.

**Note 4: `proposed/archive/` must exist at kickoff (§5.2, v2.1 amendment A4).** The `.council/proposed/archive/` directory must be created by `/council-kickoff`, not on first use, so `decision-log.jsonl` paths are always resolvable.

**Note 5: trine-eval Phase 2 features are optional inputs (§10.3, Rule 11).** The council reads `tasks.json`, `transcripts/`, `regression.json`, and `summary.md` defensively. Missing files produce `coverage` warnings but do not abort. Generators implementing agents that consume these files must honor the graceful-degradation contract.
