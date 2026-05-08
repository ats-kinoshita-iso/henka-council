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

### Option A — Plugin Registry (Recommended)

In Claude Code, run:

```
/plugin install henkaten-council
```

Claude Code will fetch the plugin, register the skills and agents, and load
`CLAUDE.md` automatically for all future sessions in the project.

### Option B — Direct Path Install

Clone this repository alongside your project and register it:

```
git clone https://github.com/atsushi-kinoshita/henka-council.git
/plugin install ./henka-council
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

When you run `/henkaten-council:council-kickoff` for the first time, the skill
performs a **hook installation self-check**:

- It verifies that `hooks/enforce-append-only.sh` (or its PowerShell equivalent)
  is registered in Claude Code's `PreToolUse` hook configuration.
- It verifies that `hooks/enforce-reversibility.sh` is also registered.
- If any hook is missing, the kickoff skill reports the gap and provides the
  exact registration command to run before proceeding.

Do not skip the hook self-check. Running the council without the append-only
hook means JSONL logs can be silently overwritten, which breaks the governance
audit chain.

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

MIT — see [LICENSE](LICENSE).
