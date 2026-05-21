# Plan Mode Integration — Research

**Author:** scheduled research agent (Claude Code on the web)
**Date:** 2026-05-21
**Status:** proposal-only research; no code or controlled artifact has been modified.
**Audience:** plugin maintainers familiar with henka-council v0.1.2.

---

## OPEN QUESTIONS

The following points were not fully resolvable from public documentation at
research time and are flagged here so the reader can correct any inference
before adopting the recommendation.

1. **`ExitPlanMode` `tool_input` schema.** The Hooks reference page truncates
   the per-tool `tool_input` table before reaching `ExitPlanMode`
   ([observed: https://code.claude.com/docs/en/hooks], "tool_input schemas"
   section). Based on the tool's purpose (the assistant must hand a *plan* to
   the user for approval), I assume the payload contains a `plan` string field
   — but this is **[inferred]** from observed tool behavior, not quoted from
   the docs.
2. **`UserPromptExpansion` permission-mode visibility.** The page documents
   common input fields including `permission_mode`
   [observed: https://code.claude.com/docs/en/hooks], but it does not
   explicitly state that `permission_mode: "plan"` is propagated to slash
   commands invoked while plan mode is active. **[inferred]** from the
   common-input-fields contract.
3. **`/trine-eval:planner` interface.** This plugin (henka-council) is the
   only repo I have. The trine-eval planner is referenced by the user as
   "Expands user prompts into product specifications with sprint
   decomposition." There is no copy of trine-eval in this checkout
   [observed: `ls /home/user/henka-council/` shows no `trine-eval/`]. I
   reason from the `.harness/spec.md`/`config.json` integration points only
   and mark all trine-eval-planner claims **[inferred]**.
4. **Will a hook-injected `additionalContext` actually shape the plan the
   model writes?** Docs say `additionalContext` is wrapped in a system
   reminder "at the point where the hook fired"
   [observed: https://code.claude.com/docs/en/hooks]. For a `PreToolUse`
   match on `ExitPlanMode`, the hook fires *after* the model has already
   composed its plan. Therefore injecting council critique into the same
   tool-call cycle is too late — the model would have to be re-prompted.
   Discussed in §4. **[inferred]**.

---

## 1. Current state of Plan mode in Claude Code

### 1.1 What Plan mode is

Plan mode is one of six Claude Code permission modes. The defining behavior
is: *read-only research; reads and shell exploration are permitted, edits
are not; the assistant writes a plan and surfaces it for approval before any
mutating work runs.*

> "Plan mode tells Claude to research and propose changes without making
> them. Claude reads files, runs shell commands to explore, and writes a
> plan, but does not edit your source."
> — [observed: https://code.claude.com/docs/en/permission-modes#analyze-before-you-edit-with-plan-mode]

Plan mode is entered three ways:

1. `Shift+Tab` cycles `default → acceptEdits → plan` in CLI.
2. `/plan <prompt>` prefixes a single prompt with plan mode.
3. `claude --permission-mode plan` starts a session in plan mode.

A project may set it as default via `permissions.defaultMode: "plan"` in
`.claude/settings.json`
[observed: https://code.claude.com/docs/en/permission-modes#set-plan-mode-as-the-default].

### 1.2 ExitPlanMode is a *tool*, not a hook event

There is no `EnterPlanMode` or `ExitPlanMode` hook event. The full hook
event list — `SessionStart`, `Setup`, `UserPromptSubmit`,
`UserPromptExpansion`, `PreToolUse`, `PermissionRequest`,
`PermissionDenied`, `PostToolUse`, `PostToolUseFailure`, `PostToolBatch`,
`Notification`, `SubagentStart`, `SubagentStop`, `TaskCreated`,
`TaskCompleted`, `Stop`, `StopFailure`, `TeammateIdle`,
`InstructionsLoaded`, `ConfigChange`, `CwdChanged`, `FileChanged`,
`WorktreeCreate`, `WorktreeRemove`, `PreCompact`, `PostCompact`,
`Elicitation`, `ElicitationResult`, `SessionEnd` — has no plan-mode-specific
entry [observed: https://code.claude.com/docs/en/hooks].

Instead, `ExitPlanMode` appears as a matchable **tool name** for `PreToolUse`,
`PostToolUse`, `PostToolUseFailure`, `PermissionRequest`, and
`PermissionDenied` events
[observed: https://code.claude.com/docs/en/hooks]. The exact matcher syntax
the plugin already uses elsewhere (`hooks/hooks.json:6` → `"matcher":
"Write|Edit"`) extends naturally: `"matcher": "ExitPlanMode"` would fire only
on plan submission.

### 1.3 Plan submission and approval flow

When the assistant calls `ExitPlanMode`, the CLI surfaces the proposed plan
to the user, who chooses among:

> "Approve and start in auto mode / Approve and accept edits / Approve and
> review each edit manually / Keep planning with feedback / Refine with
> Ultraplan"
> — [observed: https://code.claude.com/docs/en/permission-modes#review-and-approve-a-plan]

Approval *exits* plan mode and switches the session to whichever permission
mode the chosen approve-option implies. "Keep planning with feedback" returns
to the loop without exiting plan mode.

### 1.4 PreToolUse hook decision controls

A `PreToolUse` hook can write a `hookSpecificOutput` JSON object to stdout
that includes:

```json
{
  "hookSpecificOutput": {
    "hookEventName": "PreToolUse",
    "permissionDecision": "allow" | "deny" | "ask" | "defer",
    "permissionDecisionReason": "...",
    "additionalContext": "..."
  }
}
```

[observed: https://code.claude.com/docs/en/hooks]. The `additionalContext`
string is "wrapped in a system reminder and inserted into the conversation
at the point where the hook fired"
[observed: https://code.claude.com/docs/en/hooks]. Exit code 2 also blocks,
feeding stderr back to Claude as an error message
[observed: https://code.claude.com/docs/en/hooks].

### 1.5 The built-in `Plan` subagent

Claude Code ships a built-in `Plan` subagent that is *only* used during plan
mode. It "inherits from main conversation" and is restricted to "Read-only
tools (denied access to Write and Edit tools)"
[observed: https://code.claude.com/docs/en/sub-agents]. Its existence
matters because:

> "This prevents infinite nesting (subagents cannot spawn other subagents)
> while still gathering necessary context."
> — [observed: https://code.claude.com/docs/en/sub-agents]

That single sentence has a sharp consequence for the council: **inside
plan mode, the main session cannot dispatch council agents via the `Agent`
tool from within research delegated to `Plan`** — Plan itself is a subagent,
and subagents cannot spawn subagents. Orchestration must happen at the
*main session* level, not nested under Plan.

### 1.6 Hook-input visibility of plan mode

Every hook payload includes a `permission_mode` field
[observed: https://code.claude.com/docs/en/hooks]. When the session is in
plan mode, this is `"plan"` — letting hooks detect plan mode at fire time
without needing a dedicated plan event. **[inferred]** that this propagates
to `UserPromptExpansion` (the docs show `permission_mode` in the common
input fields shared by all events, but do not call out the propagation by
name).

---

## 2. Agent capabilities recap

### 2.1 Orchestrator (Level 4, henka-council)

Defined at `agents/orchestrator.md:1-14`. `tools: Read, Glob, Grep, Bash,
Write, Task`. `context: inherit`. It is the only council agent allowed to
`Task`-dispatch other agents or to `Write` files; "All other agents are
proposal-only (Level 1–2) and return their output as text"
[observed: `agents/orchestrator.md:21-23`]. It manages the dynamic autonomy
floor, honors andon signals (verbatim thank-the-puller before any analytical
response), writes the decision log via `scripts/append-decision.py`, and is
forbidden from modifying sacred `.harness/{spec.md,features.json,sprints.json}`
without Level 5 approval [observed: `agents/orchestrator.md:201-214`].

### 2.2 Architect (Level 2, henka-council)

Defined at `agents/architect.md:1-12`. `tools: Read, Glob, Grep`.
`context: fork`. Proposal-only: "MUST NOT modify any file (no Write, Edit,
or Bash operations)" [observed: `agents/architect.md:34-39`]. Its outputs
are a *coherence rating*, *drift indicators*, *dependency health*,
*proposed amendments*, *risk flags*, and an *optional andon signal*
[observed: `agents/architect.md:67-124`]. The architect already speaks the
right vocabulary for plan critique — it reads `spec.md`, `features.json`,
`sprints.json`, and existing contracts to assess coherence between *plan and
implementation*.

### 2.3 trine-eval planner **[inferred from external description]**

I could not read the planner spec — it lives in the separate trine-eval
plugin, which is not present in this checkout
[observed: `ls /home/user/henka-council/` shows no `trine-eval/` and
`grep planner` in spec.md returns nothing
(`grep -n planner .harness/spec.md` → no matches)]. From the user-supplied
description ("Expands user prompts into product specifications with sprint
decomposition") and the `.harness/config.json` integration point
(`components_enabled.planner: true`, line 14), I assume the planner is
the trine-eval-side agent that produces `spec.md`, `features.json`, and
`sprints.json` at kickoff and is invoked via `/trine-eval:harness-kickoff`
or `/trine-eval:harness-sprint` [observed: `.harness/spec.md:185-187`,
`skills/council-kickoff/SKILL.md:469-495`]. **[inferred]** that it accepts a
free-form user description and returns a structured spec/sprint plan.

The planner is therefore the *generative* counterpart to the architect's
*reviewer* role. In plan-mode integration terms: planner = spec author,
architect = spec auditor.

---

## 3. Integration candidates

Each design below is evaluated against the constraints in §4. None violates
append-only or sacred-file rules.

### 3.1 Design A — `PreToolUse(ExitPlanMode)` audit gate

**Trigger:** PreToolUse hook with `"matcher": "ExitPlanMode"` registered in
`hooks/hooks.json` alongside the existing `Write|Edit` and `Bash` matchers.
**Which agent runs:** none directly — the hook is a shell script that
*reads* the proposed plan (passed via stdin `tool_input.plan`, **[inferred]**)
and stages it for the architect. Two sub-variants:
  - **A-sync:** the hook synchronously dispatches the architect via a
    headless Claude Code invocation (`claude -p ... --agent architect`),
    waits for the response, and returns a `hookSpecificOutput` with
    `additionalContext` containing the architect's coherence rating and any
    `andon_signal`. Permission decision: `"ask"` so the user sees the
    council's read before approving.
  - **A-async:** the hook writes the plan to
    `.council/proposed/plan-mode-pending-<session_id>.md` and returns
    `permissionDecision: "allow"` immediately with a one-line
    `additionalContext` saying "Architect review queued; see file." A
    separate watcher (or the next sprint loop) picks it up.

**Artifact produced:** a `plan-mode-review-<session_id>.md` under
`.council/proposed/` plus, on a `stop` andon, a closing entry in
`decision-log.jsonl` via `scripts/append-decision.py`. No write to
`henka-register.jsonl` from the hook itself — the henka entry, if any, is
written by the orchestrator at the next sprint boundary so authorship stays
correct.

**How output reaches `ExitPlanMode`:** via `additionalContext` in the
hook's stdout. This is shown to the user alongside the plan
[observed: https://code.claude.com/docs/en/hooks "Add context for
Claude"]. **Limitation:** by the time the hook fires, the plan is already
written — the hook cannot *edit* the plan, only annotate it. To get the
architect to *shape* the plan, see Design B.

**Controlled artifacts touched:**
- `.council/proposed/plan-mode-review-<session_id>.md` (council working
  file, orchestrator-writable per
  `instructions/controlled-artifacts.md:60-67`). Hook writes are
  problematic here — hooks run outside the orchestrator. **Mitigation:**
  hook writes to a single dedicated subdirectory
  `.council/proposed/plan-mode/` reviewed at the next sprint boundary.
- `.council/decision-log.jsonl` only via `scripts/append-decision.py` on
  andon-stop terminations (the orchestrator authors the closing entry, not
  the hook).

**Verdict:** viable, lowest-friction, but constrained to *annotation*. Good
fit for the audit-only use case where the user wants the council's read
before approving but doesn't expect plan re-generation.

### 3.2 Design B — Slash command `/plan-with-council` that drives the planner→architect chain

**Trigger:** a new skill registered as
`skills/plan-with-council/SKILL.md`, invoked as
`/henkaten-council:plan-with-council <user prompt>`. The user types this
*instead of* entering plan mode via `Shift+Tab`; the skill body instructs
the orchestrator to:
1. Enter plan mode (via `/plan` prefix).
2. Dispatch `/trine-eval:planner` (or `/trine-eval:harness-sprint` if a
   sprint plan already exists) via `Task` to draft the plan body.
3. Fan in to the **architect** with the draft as input.
4. If architect returns `andon_signal: alert` or `stop`, honor it (verbatim
   thank-the-puller), pause, and surface the andon to the user before any
   `ExitPlanMode` call.
5. Otherwise, the orchestrator calls `ExitPlanMode` with a plan body that
   embeds (a) the planner's spec, (b) the architect's coherence rating, and
   (c) any flagged risks or proposed amendments.

**Which agent runs:** planner (trine-eval) then architect (henka-council),
sequentially. Orchestrator is the only `Task` caller (per
`agents/orchestrator.md:50-52`).

**Artifact produced:**
- `.council/proposed/DEC-<NNNN>-plan-mode.md` if the architect finds a
  major risk requiring nemawashi (per `instructions/human-approval.md:33-58`).
- A draft plan presented to the user via `ExitPlanMode`. The plan *is* the
  deliverable; the user's approve-option chooses how the session proceeds
  (auto / acceptEdits / default).

**How output reaches `ExitPlanMode`:** the orchestrator composes the plan
text in its own turn and calls `ExitPlanMode` directly — no hook needed.

**Controlled artifacts touched:** only `.council/proposed/` (council-owned).
No append-only file is written *during* plan mode itself; the
decision-log entry is written when the user approves, by the orchestrator
in the post-plan-mode permission mode (where Write is enabled). Sacred
files are untouched. Note: if the trine-eval planner is what produces
`spec.md`/`features.json`/`sprints.json`, those writes happen via
`/trine-eval:harness-kickoff`, which is the trine-eval plugin's
responsibility and already accounted for under Level 5 / kickoff governance
(see `.harness/spec.md:209`).

**Verdict:** most powerful and most aligned with the council's existing
discipline. The user explicitly opts in (no silent rerouting), and every
council rule applies normally because the orchestrator is in charge from
turn one.

### 3.3 Design C — `SubagentStart` hook that routes `Plan` to architect critique

**Trigger:** `SubagentStart` hook with a matcher on `agent_type == "Plan"`
[observed: https://code.claude.com/docs/en/hooks — `SubagentStart` payload
includes `agent_type`]. When the built-in `Plan` subagent spawns during
plan mode, the hook fires.

**Which agent runs:** the hook itself runs a shell script that calls the
architect via a headless Claude Code invocation. The architect reads the
*current* `.harness/spec.md`, `features.json`, and `sprints.json` (its
normal inputs per `agents/architect.md:52-62`) and returns coherence
findings *before* Plan begins its research. Findings are injected into
the conversation via the hook's `additionalContext`.

**Artifact produced:** none persisted by default. Optionally a snapshot at
`.council/proposed/plan-mode/preflight-<session_id>.md`.

**How output reaches `ExitPlanMode`:** indirectly — the architect's preflight
critique is added to context *before* the model writes its plan, so the
plan can incorporate the architect's coherence assessment. This is closer
to "shape the plan" than Design A.

**Controlled artifacts touched:** same low surface as Design A —
`.council/proposed/plan-mode/` only.

**Verdict:** viable, but couples henka-council to the built-in Plan
subagent's spawn lifecycle, which is a Claude-Code-internal behavior. A
future CLI release that bypasses Plan (or invokes it under a different
`agent_type`) silently breaks the integration. Designs A and B do not have
this fragility because they hook on documented tool names, not on internal
subagent identifiers.

### 3.4 Design D — `UserPromptSubmit` enrichment when `permission_mode == "plan"`

**Trigger:** `UserPromptSubmit` hook that reads `permission_mode` from the
payload [observed: https://code.claude.com/docs/en/hooks] and, if
`"plan"`, prepends a static `additionalContext` block listing the project's
current `features.json` (truncated), the last 3 entries from
`decision-log.jsonl`, and the latest `state/effective-autonomy.json`.

**Which agent runs:** none. This is a static enrichment hook; it provides
the model with *governance state* but does not invoke an agent.

**Artifact produced:** none.

**How output reaches `ExitPlanMode`:** indirectly, via context that the
model uses while composing the plan.

**Controlled artifacts touched:** none written; only read.

**Verdict:** zero-cost, complementary to Designs A–C. Useful as a baseline
even if a richer design ships, because it gives the model the council's
ground truth without any agent dispatch. Should not be the *primary*
integration because it does not actually run the architect; it just makes
the council's state legible.

---

## 4. Constraints and risks

### 4.1 Projection cost (8,000-token advisory budget)

Per `instructions/projection-cost.md:62-87`, the always-projected surface is
`CLAUDE.md` + every file listed in `.claude-plugin/plugin.json` under
`"skills"` and `"agents"`. Today only `CLAUDE.md` is loaded
(plugin.json:1-11 doesn't list skills/agents arrays), so headroom is large.
But:

- **Design A** adds no projection cost — hooks are not projected.
- **Design B** adds one new skill file. Slash-skill bodies are *not*
  auto-projected; the skill is read on invocation. Cost impact at session
  start: zero. Cost on invocation: bounded by the SKILL.md size, governed
  by the same trim/promote rule in `instructions/projection-cost.md:69-86`.
- **Design C** adds no projection cost.
- **Design D** adds no projection cost.

None of the proposals require enlarging the always-projected surface, so the
8,000-token budget is not a binding constraint.

### 4.2 Autonomy floor interaction

When `state/effective-autonomy.json.level` is below 4
(`agents/orchestrator.md:96-119`), Level 4 multi-step sequences are
forbidden. Design B is the only proposal that requires Level 4 (it chains
two `Task` calls — planner then architect). Mitigation: if the floor is
below 4 at invocation time, the orchestrator should fall back to the
single-step Design A behavior (annotate the model's plan, do not chain),
and log the degradation as a `coverage` note rather than executing the
chain anyway. This mirrors the graceful-degradation pattern in
`agents/orchestrator.md:218-225`.

### 4.3 Andon protocol implications

If the architect returns `andon_signal: stop` while reviewing a plan, the
orchestrator MUST write the verbatim thank-the-puller acknowledgment
*before any analytical response*
[observed: `instructions/andon-protocol.md:38-46`]. In Design B that's
straightforward (orchestrator is on-turn). In Design A, the hook is *not*
the orchestrator — it has no authority to issue the thank-the-puller. The
hook must therefore *not* emit a stop on the architect's behalf; if the
architect's review (called from the hook) returns a stop, the hook should
write the stop into a `pending-andon` file under `.council/proposed/` and
return `permissionDecision: "deny"` with a `permissionDecisionReason`
asking the user to re-engage the orchestrator. The orchestrator then
honors the andon on its next turn.

This is a real subtlety: **hooks are outside the council's authority
hierarchy.** They can carry information across the boundary but cannot
issue council signals. Designs A and C inherit this limitation; Designs B
and D are unaffected.

### 4.4 Proposal-only agent invoked from a writing context

The architect's contract forbids it from holding `Write`/`Edit`/`Bash`
even when called from a context that *expects* to write
[observed: `agents/architect.md:34-39`]. Subagents have an independent
`permissionMode` field [observed: https://code.claude.com/docs/en/sub-agents
"Conditional rules with hooks"], but plugin-loaded subagents have that
field *ignored*: "For security reasons, plugin subagents do not support the
`hooks`, `mcpServers`, or `permissionMode` frontmatter fields"
[observed: https://code.claude.com/docs/en/sub-agents §225-232]. The
plugin loads the architect via `agents/architect.md`, so the architect
cannot self-elevate to `plan` permission mode regardless of who invokes
it. This is the right behavior — the architect's read-only-ness comes from
its `tools: Read, Glob, Grep` declaration, not from session permission
mode, and that declaration is honored by the harness even inside a
non-plan session.

Practical consequence: if a hook calls the architect via a headless
`claude -p` invocation (Designs A or C), and that headless run is not
itself in plan mode, the architect *still* cannot write because its tool
list excludes Write/Edit/Bash. Safe.

### 4.5 Append-only file protection

`.council/{henka-register,decision-log,audit-log}.jsonl` are append-only;
the `PreToolUse` hook `hooks/enforce-append-only.sh` blocks direct
`Write`/`Edit` against them [observed: `hooks/hooks.json:5-12`,
`instructions/controlled-artifacts.md:40-53`]. None of the four proposals
write to these files from the hook layer. Designs A–C write *only* to
`.council/proposed/` (which is council-owned but not append-only) and use
the sanctioned `scripts/append-decision.py` and `scripts/append-henka.py`
only via the orchestrator on its own turn — never from a hook subshell.

### 4.6 Sacred-file protection

No design modifies `.harness/spec.md`, `.harness/features.json`, or
`.harness/sprints.json`. Design B *generates* a plan body that may
*propose* changes to those files, but the actual mutation only happens
after `ExitPlanMode` is approved and the session re-enters a writing mode,
at which point the existing reversibility hook (`hooks/enforce-reversibility.sh`)
and the orchestrator's nemawashi requirement still apply.

### 4.7 Stop / andon during plan mode

If a `stop` andon fires while the user is reviewing a plan, the
orchestrator cannot proceed even after the user clicks "approve and run".
The thank-the-puller acknowledgment must precede everything. In Design B
this is natural — the orchestrator detects the stop *before* calling
`ExitPlanMode` and does not call it at all; the next user turn is "explain
why I stopped" rather than "approve plan". Designs A and C cannot achieve
this guarantee from inside the hook, which is another reason B is preferred.

---

## 5. Recommendation

**Primary: Design B (`/plan-with-council` skill)**, supplemented by
**Design D** as a free baseline.

Justification, in three sentences: Design B is the only proposal where the
council's existing rules apply automatically — the orchestrator is on-turn,
the andon protocol works without translation, the autonomy floor is read
before any chain runs, and the `ExitPlanMode` call carries a plan that the
architect has already reviewed (instead of one critiqued after the fact).
Design D costs nothing and gives the model the council's state during *any*
plan-mode session, including the default `Shift+Tab` path that doesn't go
through the new skill; it is a strict improvement and should ship in the
same change. Designs A and C are correct-but-fragile alternatives — A
cannot shape the plan (only annotate it), C couples to a Claude-Code
internal name (`Plan` subagent) that the docs do not promise to preserve.

### Minimum next steps to prototype

1. **Add skill file:** `skills/plan-with-council/SKILL.md`. Front-matter
   modeled on `skills/council-kickoff/SKILL.md:1-22` with
   `agents_used: [orchestrator, architect]` and a body that walks the
   orchestrator through the planner→architect chain described in §3.2.
   Reference `instructions/andon-protocol.md` and
   `instructions/human-approval.md` for andon and nemawashi behavior.
2. **Register the skill** in `.claude-plugin/plugin.json`. The plugin
   manifest at `.claude-plugin/plugin.json:1-11` does not currently list
   `skills` or `agents` arrays — confirm whether the v0.1.2 packaging
   relies on directory auto-discovery (the `instructions/projection-cost.md:18-23`
   discovery rule assumes a `skills` array). If so, also re-baseline
   projection-cost via `scripts/measure-projection-cost.py` per
   `instructions/projection-cost.md:107-113`.
3. **Add Design D hook:** new `UserPromptSubmit` entry in
   `hooks/hooks.json:1-44` that runs a small script — call it
   `hooks/plan-mode-context.sh` — which checks `permission_mode == "plan"`
   in stdin, and on a match prints a `hookSpecificOutput` with
   `additionalContext` summarizing the current `features.json`, last 3
   `decision-log.jsonl` entries, and `state/effective-autonomy.json.level`.
   Cap output size; the on-demand-context budget is not the same as the
   always-projected budget, but bloating each plan-mode prompt is still
   wasteful.
4. **Update `agents/orchestrator.md` §"Sub-Agents Dispatched"**
   (`agents/orchestrator.md:182-196`) to add `plan-with-council` as a
   permitted dispatch entry-point. No new agent is added; the existing
   architect handles the review.
5. **Add a test fixture** under `tests/fixtures/dummy-project/` that
   exercises `/plan-with-council "add feature X"` end-to-end. Acceptance
   criterion: the resulting `ExitPlanMode` call's `tool_input.plan`
   contains both the planner's draft and the architect's coherence rating;
   no write occurs to `.harness/spec.md`/`features.json`/`sprints.json`;
   `.council/decision-log.jsonl` gains exactly one entry per approved
   plan, written via `scripts/append-decision.py`.
6. **Document the new path** in `README.md` and `CHANGELOG.md` under a new
   `0.2.0` heading.

The Design A and C variants can be revisited as fallbacks if the
`/plan-with-council` slash command proves clunky in practice (e.g., users
keep entering plan mode via `Shift+Tab` and missing the council
integration). At that point Design D's enrichment becomes the *only*
governance signal in those default sessions, which may be sufficient.

---

## Citations

- `agents/orchestrator.md:1-248` — orchestrator definition, tool grant,
  andon and autonomy rules, prohibitions.
- `agents/architect.md:1-166` — architect tools, read-only constraint,
  outputs, andon signal structure.
- `instructions/controlled-artifacts.md:18-95` — sacred files, append-only
  logs, agent write constraints.
- `instructions/projection-cost.md:14-87` — always-projected surface and
  budget rules.
- `instructions/andon-protocol.md:33-52` — thank-the-puller acknowledgment.
- `instructions/human-approval.md:11-58` — minor vs major (nemawashi) paths.
- `hooks/hooks.json:1-45` — current PreToolUse / PostToolUse / Stop
  registrations.
- `.claude-plugin/plugin.json:1-11` — plugin manifest (no skills/agents
  arrays at v0.1.2; auto-discovery assumed).
- `.harness/spec.md:183-209` — trine-eval delegation surface.
- `skills/council-kickoff/SKILL.md:469-495` — Task-dispatch syntax used to
  call trine-eval skills.
- [observed: https://code.claude.com/docs/en/permission-modes] — plan mode
  semantics and approve options.
- [observed: https://code.claude.com/docs/en/hooks] — hook event list,
  PreToolUse output schema, `additionalContext` injection.
- [observed: https://code.claude.com/docs/en/sub-agents] — built-in Plan
  subagent, plugin subagent `permissionMode` restriction, no-nested-spawn
  rule.
