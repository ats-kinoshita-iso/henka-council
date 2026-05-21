# henkaten-council

A Claude Code plugin that adds a continuous-improvement governance layer on top
of any project managed by the [trine-eval](https://github.com/trine-eval/trine-eval)
harness. The council detects change points (henkaten), audits autonomous
decisions, manages a dynamic autonomy floor, and enforces the andon protocol
across sprints.

---

## What it Does

The `henkaten-council` plugin wires a council of specialized agents into the
Claude Code skill system. Each sprint, the council:

1. Detects change points using 4M axis classification (Man/Machine/Method/Material)
2. Audits every correction with evidence citations and reversibility flags
3. Manages a dynamic autonomy floor that drops on consecutive sprint failures
   or repeated andon stops from multiple distinct originators
4. Delegates sprint evaluation to the `trine-eval` harness via
   `/trine-eval:harness-sprint`
5. Records all governance activity to append-only JSONL logs under `.council/`

---

## Prerequisites

- Claude Code ≥ 0.3.0
- `trine-eval` ≥ 0.3.0 installed and initialized in your target project
  (run `/trine-eval:harness-kickoff` first if the `.harness/` directory does
  not yet exist)
- Git ≥ 2.30

---

## Install

### Option A — Marketplace (Recommended)

This repository ships its own single-plugin marketplace manifest
(`.claude-plugin/marketplace.json`). In Claude Code, add the repo as a
marketplace, then install the plugin from it:

```
/plugin marketplace add atsushi-kinoshita/henka-council
/plugin install henkaten-council@henkaten-council
```

Claude Code will fetch the plugin, auto-discover the skills and agents
under `skills/` and `agents/`, auto-register the hooks declared in
`hooks/hooks.json`, and load `CLAUDE.md` automatically for all future
sessions in the project.

### Option B — Direct Path Install

Clone this repository and add it as a local marketplace:

```
git clone https://github.com/atsushi-kinoshita/henka-council.git
/plugin marketplace add ./henka-council
/plugin install henkaten-council@henkaten-council
```

After installation, verify the plugin is active:

```
/plugin list
```

You should see `henkaten-council` in the output with status `active`.

---

## Hook Installation and Self-Check

The council's enforcement hooks must be registered with Claude Code's hook
system before the council can prevent append-only log overwrites or enforce
the reversibility policy. The hooks live in `hooks/` (Bash, for Linux/macOS)
and `hooks/win/` (PowerShell, for Windows).

> **As of v0.1.2:** hooks auto-register from `hooks/hooks.json` when the
> plugin is installed via the marketplace flow (Option A above). The kickoff
> skill's Step 1d.0 detects this case and the manual snippet below is then
> only a fallback — needed for direct-path installs on Claude Code builds
> that don't read plugin-level `hooks.json`, or for pure-PowerShell Windows
> hosts without bash.

When you run `/henkaten-council:council-kickoff` for the first time, the skill
performs a **hook installation self-check** and refuses to proceed past Step 1d
if neither auto-registration nor manual registration covers all four required
hooks.

The full registration snippet is in
[`skills/council-kickoff/SKILL.md`](skills/council-kickoff/SKILL.md) under
Step 1d.1 (Linux/macOS) and Step 1d.2 (Windows). The short version:

Add this `hooks` block to your target project's `.claude/settings.local.json`:

```json
"hooks": {
  "PreToolUse": [
    { "matcher": "Write|Edit",
      "hooks": [{ "type": "command",
                  "command": "bash ${CLAUDE_PLUGIN_ROOT}/hooks/enforce-append-only.sh" }] },
    { "matcher": "Bash",
      "hooks": [{ "type": "command",
                  "command": "bash ${CLAUDE_PLUGIN_ROOT}/hooks/enforce-reversibility.sh" }] }
  ],
  "PostToolUse": [
    { "matcher": "*",
      "hooks": [{ "type": "command",
                  "command": "bash ${CLAUDE_PLUGIN_ROOT}/hooks/log-tool-call.sh" }] }
  ],
  "Stop": [
    { "hooks": [{ "type": "command",
                  "command": "bash ${CLAUDE_PLUGIN_ROOT}/hooks/session-stopped-marker.sh" }] }
  ]
}
```

On Windows targets, substitute `pwsh -NoLogo -NoProfile -File ${CLAUDE_PLUGIN_ROOT}/hooks/win/<name>.ps1`
for each `bash ${CLAUDE_PLUGIN_ROOT}/hooks/<name>.sh`. The PowerShell hooks
ship functional parity with the bash siblings (v2.1 amendment A7).

`${CLAUDE_PLUGIN_ROOT}` is resolved by Claude Code at hook-fire time to the
plugin's installed directory. If your Claude Code build does not resolve that
variable yet, substitute the absolute path to where the plugin is installed
(e.g. `/home/<user>/.claude/plugins/cache/henkaten-council/<version>/`).

Do not skip the hook self-check. Running the council without the append-only
hook means JSONL logs can be silently overwritten, which breaks the governance
audit chain.

### Permissions for running council-kickoff against a target project

The kickoff skill writes into the target project's `.council/` directory and
may merge a `governance` block into the target's `.harness/config.json`.
Depending on your Claude Code permission tier, you may need to add Bash
permissions for the target project's path (e.g.
`Bash(mkdir -p /path/to/target/.council/**)`) before the orchestrator can
create the baseline. The council-kickoff skill will surface this requirement
if it hits a denial.

---

## Quickstart

### Step 1 — Initialize the trine-eval harness (if not already done)

```
/trine-eval:harness-kickoff
```

This creates `.harness/spec.md`, `.harness/features.json`, and
`.harness/sprints.json` in your project.

### Step 2 — Bootstrap the council governance baseline

```
/henkaten-council:council-kickoff
```

This creates the complete `.council/` directory structure:

```
.council/
  config.json
  council-manifest.json
  henka-register.jsonl
  decision-log.jsonl
  audit-log.jsonl
  standard-work.json
  state/
    effective-autonomy.json
  proposed/
  proposed/archive/
  course-corrections/
  retrospectives/
  sessions/
```

The kickoff skill also:
- Writes a governance signal to `.harness/config.json`
- Verifies that all required hooks are installed (hook self-check)
- Surfaces the one-time git merge opt-in setup note (see below)

### Step 3 — Run the council autorun loop (Sprint 4+)

Once the council baseline is in place, run:

```
/henkaten-council:council-autorun
```

to start the sprint review loop (available from Sprint 4 onward).

---

## Git Merge Opt-In

By default, `git merge` is in the `deny` tier in `.claude/settings.json`. This
means the Orchestrator cannot propose or execute merges without explicit user
override. If you want the Orchestrator to propose merges when a sprint PASSes,
move `git merge *` from the `deny` array to the `ask` array in
`.claude/settings.json`. The council-kickoff skill will remind you of this
one-time setup step.

---

## Dependency: trine-eval

The `henkaten-council` plugin depends on `trine-eval` as its harness. The
governance signal written to `.harness/config.json` by the kickoff skill tells
trine-eval that the council is active. Sprint evaluation is always delegated to
`/trine-eval:harness-sprint` — the council does not implement its own evaluation
engine.

---

## License

Apache-2.0 — see [LICENSE](LICENSE).
