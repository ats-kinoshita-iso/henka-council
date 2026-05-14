---
name: council-kickoff
description: >
  Use this skill to bootstrap a new henkaten-council governance baseline in a
  trine-eval project. Invoke it once per project before running any council
  review cycle. It creates the complete .council/ directory structure, seeds
  all required state files, writes the governance signal to .harness/config.json,
  and delegates initial sprint planning to /trine-eval:harness-kickoff (or
  /trine-eval:harness-sprint for subsequent sprints).
version: "0.1.0"
author: Atsushi Kinoshita
skill_type: bootstrap
requires_trine_eval: true
agents_used:
  - orchestrator
cross_references:
  - agents/orchestrator.md
  - agents/architect.md
  - instructions/controlled-artifacts.md
  - instructions/andon-protocol.md
  - instructions/evidence-first.md
---

# Council Kickoff Skill

This skill bootstraps the complete `.council/` governance baseline for a
project that is managed by the `trine-eval` harness. Run it once, in the target
project's root directory, before invoking any other council skill.

The kickoff skill is a **procedural document** — it specifies what the invoking
agent (Orchestrator) must do, in what order, with what idempotency guards. It is
not an executable script. Actual `.council/` creation is performed by the
Orchestrator at runtime; end-to-end validation is covered in sprint 6 (S4).

---

## Procedure

### Step 1 — Pre-Flight Checks

Before writing any file, the Orchestrator must verify the environment.

#### 1a. Harness check

If `.harness/` does not exist in the project root, the council cannot function
because trine-eval has not been initialized. In this case:

- Inform the user: "The trine-eval harness is not initialized. Run
  `/trine-eval:harness-kickoff` first, then re-invoke
  `/henkaten-council:council-kickoff`."
- Offer to delegate immediately: "Would you like me to call
  `/trine-eval:harness-kickoff` now via Task dispatch?"
- If the user confirms, dispatch via `Task` to `/trine-eval:harness-kickoff`
  and wait for completion before continuing.

#### 1b. Existing `.council/` check

If `.council/` already exists:

- Report which files are present (e.g. "Found existing `.council/config.json`,
  `.council/henka-register.jsonl`, 3 other files").
- Ask the user: "A council baseline already exists. Do you want to (a) skip
  creation of files that already exist (idempotent re-run), or (b) overwrite
  everything with fresh defaults? Option (a) is strongly recommended to
  preserve existing audit logs."
- If the user chooses (b), require explicit confirmation before overwriting
  append-only logs (`henka-register.jsonl`, `decision-log.jsonl`, `audit-log.jsonl`).
  These are governance artifacts; overwriting them is an irreversible action
  requiring Level 5 approval.
- If the user chooses (a) or provides no preference, apply idempotent guards
  throughout the rest of this procedure (skip-if-already-exists for all files).

#### 1c. Gather project context

Collect the following before writing any configuration:

- **Project name**: read from `package.json`, `pyproject.toml`, or ask the user.
- **Project type**: infer from file structure (e.g. `package.json` → `javascript`,
  `pyproject.toml` → `python`, `go.mod` → `go`, `Cargo.toml` → `rust`). Default:
  `unknown`. **Note:** `.council/config.json`'s `project_type` is the language/
  toolchain context for council reporting (e.g. `python`). This is distinct from
  `.harness/config.json`'s `project_type`, which is the trine-eval *rubric* type
  (e.g. `cli-tool`, `web-app`, `api-service`). It is normal and expected for
  these two values to differ — `cli-tool` describes how trine-eval grades the
  project, `python` describes its toolchain. The kickoff skill must not overwrite
  the harness-side value.
- **Council agents to activate**: default to the four core agents
  (`orchestrator`, `architect`, `scope-guardian`, `henkaten-detector`).
  Ask if the user wants to enable optional agents (`qa-regression`, `rag-source`).

#### 1d. Hook installation self-check

Verify that the required hooks are registered in Claude Code's hook system:

- `hooks/enforce-append-only.sh` (or `hooks/win/enforce-append-only.ps1` on
  Windows) must be registered as a `PreToolUse` hook.
- `hooks/enforce-reversibility.sh` (or `hooks/win/enforce-reversibility.ps1`)
  must also be registered as a `PreToolUse` hook.
- `hooks/log-tool-call.sh` (or `hooks/win/log-tool-call.ps1`) must be registered
  as a `PostToolUse` hook.
- `hooks/session-stopped-marker.sh` (or `hooks/win/session-stopped-marker.ps1`)
  must be registered as a `Stop` hook.

Read the target project's `.claude/settings.local.json` (creating an empty
`{ "permissions": {}, "hooks": {} }` object if absent) and check for a `hooks`
key with entries pointing at the four hook scripts above.

##### 1d.1 — Registration snippet (Linux/macOS)

If `hooks` is absent or any of the four hooks is missing, surface the following
copyable JSON to the user as the **exact registration command** (this is what
goes into `.claude/settings.local.json`). Paths use `${CLAUDE_PLUGIN_ROOT}`,
which Claude Code resolves to the plugin's installed directory at hook-fire
time. If the runtime does not resolve that variable, the user should substitute
the absolute path to the plugin install (e.g.
`/home/<user>/.claude/plugins/cache/henkaten-council/<version>/`).

```json
{
  "permissions": { "allow": [], "ask": [], "deny": [] },
  "hooks": {
    "PreToolUse": [
      {
        "matcher": "Write|Edit",
        "hooks": [
          { "type": "command", "command": "bash ${CLAUDE_PLUGIN_ROOT}/hooks/enforce-append-only.sh" }
        ]
      },
      {
        "matcher": "Bash",
        "hooks": [
          { "type": "command", "command": "bash ${CLAUDE_PLUGIN_ROOT}/hooks/enforce-reversibility.sh" }
        ]
      }
    ],
    "PostToolUse": [
      {
        "matcher": "*",
        "hooks": [
          { "type": "command", "command": "bash ${CLAUDE_PLUGIN_ROOT}/hooks/log-tool-call.sh" }
        ]
      }
    ],
    "Stop": [
      {
        "hooks": [
          { "type": "command", "command": "bash ${CLAUDE_PLUGIN_ROOT}/hooks/session-stopped-marker.sh" }
        ]
      }
    ]
  }
}
```

##### 1d.2 — Registration snippet (Windows / PowerShell)

On Windows targets, replace each `bash ${CLAUDE_PLUGIN_ROOT}/hooks/<name>.sh`
command with `pwsh -NoLogo -NoProfile -File ${CLAUDE_PLUGIN_ROOT}/hooks/win/<name>.ps1`.
The PowerShell hooks ship functional parity with the bash siblings per v2.1
amendment A7 — same envelope parsing, same allow/block exit codes, same audit
log entry format. The four PS1 paths are:

- `hooks/win/enforce-append-only.ps1` (PreToolUse matcher: `Write|Edit`)
- `hooks/win/enforce-reversibility.ps1` (PreToolUse matcher: `Bash`)
- `hooks/win/log-tool-call.ps1` (PostToolUse matcher: `*`)
- `hooks/win/session-stopped-marker.ps1` (Stop hook)

##### 1d.3 — What to do if hooks are missing

If any of the four hooks is absent from `.claude/settings.local.json`, do NOT
proceed past Step 1d. Report to the user:

> "Hook `<name>` is not registered. The council cannot enforce append-only
> log protection without it. Paste the snippet above into your
> `.claude/settings.local.json` `hooks` block, then re-invoke
> `/henkaten-council:council-kickoff`."

The council-kickoff skill must **never modify `.claude/settings.local.json`
automatically.** Hook registration is a user-driven action; the skill surfaces
the snippet but does not write it.

---

### Step 1e — Projection Cost Measurement (advisory)

Run the projection-cost measurement script and surface the result to the user.
This step is informational only; it does not block kickoff completion.

```bash
python ${CLAUDE_PLUGIN_ROOT}/scripts/measure-projection-cost.py --json
```

On Windows targets, substitute `python` with `python.exe` if the bare command
is not on `PATH`. The script reads `.claude-plugin/plugin.json` from the
plugin install directory, sums per-file token estimates for the always-projected
file set (`CLAUDE.md` + `skills` + `agents`), and reports the total against
an 8,000-token advisory budget.

Surface to the user:

> "Plugin projection-cost baseline: `<total>` of 8,000 tokens (`<headroom>`
> remaining). Methodology and re-baseline rules: `instructions/projection-cost.md`."

If the measurement reports `over_budget: true`, append:

> "WARNING: the always-projected surface is over budget by `<delta>` tokens.
> See `docs/design/adr-0002-projection-cost-budget.md` for remediation paths
> (trim, promote to on-demand, or re-baseline via a follow-up ADR)."

This step is idempotent: re-running kickoff against an already-bootstrapped
project re-runs the measurement and re-surfaces the result. The script does
not write any files; it emits to stdout only.

---

### Step 2 — Create `.council/config.json`

Write `.council/config.json` with the following content structure (idempotent:
skip if already present and idempotent mode is active):

```json
{
  "project_name": "<detected or user-provided>",
  "project_type": "<detected>",
  "council_agents": [
    "orchestrator",
    "architect",
    "scope-guardian",
    "henkaten-detector"
  ],
  "autonomy_levels": {
    "default": 4
  },
  "review_frequency": "every-sprint",
  "henkaten_taxonomy_version": "2.0",
  "andon_takt_seconds": 600,
  "dynamic_autonomy_thresholds": {
    "andon_stop_distinct_originators_required": 2,
    "andon_stop_consecutive_count": 3,
    "consecutive_sprint_fails_for_floor_drop": 2
  }
}
```

Key values to note:

- `andon_takt_seconds: 600` — raised from 300 per v2.1 amendment A6. This is
  the maximum wall-clock seconds the Orchestrator waits for swarm agents to
  respond to an `andon_signal: alert` before timing out and escalating.
- `andon_stop_distinct_originators_required: 2` — per v2.1 amendment A2, a
  dynamic autonomy floor drop triggered by andon stops requires the stops to
  originate from at least 2 distinct agent identities. Same-agent repeated
  stops are tracked as `quality-defect-anomaly` henkaten records, not floor-drop
  triggers.

Schema reference: `schemas/council-config.schema.json`

---

### Step 3 — Create `.council/council-manifest.json`

Write `.council/council-manifest.json` (idempotent):

```json
{
  "council_id": "COUNCIL-0001",
  "project_name": "<same as config>",
  "trigger_type": "kickoff",
  "status": "assembled",
  "agents": [
    {
      "name": "orchestrator",
      "role": "coordinator",
      "level": 4,
      "agent_file": "agents/orchestrator.md"
    },
    {
      "name": "architect",
      "role": "coherence-reviewer",
      "level": 2,
      "agent_file": "agents/architect.md"
    },
    {
      "name": "scope-guardian",
      "role": "scope-integrity",
      "level": 2,
      "agent_file": "agents/scope-guardian.md"
    },
    {
      "name": "henkaten-detector",
      "role": "change-point-classifier",
      "level": 1,
      "agent_file": "agents/henkaten-detector.md"
    }
  ],
  "created_at": "<ISO-8601-now>"
}
```

Schema reference: `schemas/council-manifest.schema.json`

---

### Step 4 — Initialize Append-Only Logs (Idempotent)

The three governance logs are append-only. Apply the following idempotency
rule: **create if the file does not exist; never overwrite if it does**
(unless the user explicitly chose full-overwrite in Step 1b and confirmed
the irreversible action).

#### `henka-register.jsonl`

If `.council/henka-register.jsonl` does not exist: create an empty file.
Do not write any seed record; the first henkaten record will be appended by
`scripts/append-henka.py` when the first change point is detected.

#### `decision-log.jsonl`

If `.council/decision-log.jsonl` does not exist: create the file with a
single seed entry representing the kickoff decision:

```json
{"dec_id":"DEC-0001","timestamp":"<ISO-8601-now>","decision_type":"kickoff","decision_outcome":"council-baseline-created","council_agents_involved":["orchestrator"],"evidence_cited":[],"applied_automatically":true,"user_approval_required":false,"affected_files":[".council/config.json",".council/council-manifest.json"],"linked_henka_id":null,"sprint_context":"kickoff","autonomy_level_used":4,"effective_autonomy_at_decision":4,"reversibility":"reversible","nemawashi_walkthrough_version":null}
```

#### `audit-log.jsonl`

If `.council/audit-log.jsonl` does not exist: create an empty file. The
`hooks/log-tool-call.sh` hook will populate it at runtime.

---

### Step 5 — Write `.council/standard-work.json`

Write `.council/standard-work.json` with a seed based on project type
(idempotent):

```json
{
  "version": "1.0",
  "project_type": "<detected>",
  "last_updated": "<ISO-8601-now>",
  "procedures": [],
  "known_henkaten_patterns": [],
  "yokoten_entries": []
}
```

Schema reference: `schemas/standard-work.schema.json`

---

### Step 6 — Create Directory Structure

Create the following six directories under `.council/` if they do not already
exist (idempotent — `mkdir -p` semantics, no error if present):

1. `.council/course-corrections/`
2. `.council/proposed/`
3. `.council/proposed/archive/`
4. `.council/retrospectives/`
5. `.council/sessions/`
6. `.council/state/`

The `proposed/archive/` path is required by v2.1 amendment A4: after a position
paper is ratified via the nemawashi walkthrough (Step 1D in the autorun skill),
the position paper file is moved from `proposed/` to `proposed/archive/`. This
preserves the `nemawashi_walkthrough_version` path reference in the
`decision-log.jsonl` entry indefinitely. If the archive directory were absent,
ratified-paper paths would resolve to 404 errors during later audit reviews.

The `state/` directory is required because `state/effective-autonomy.json` is
written in Step 7 below. It must exist before that write.

---

### Step 7 — Write `.council/state/effective-autonomy.json`

Write the initial autonomy state file (idempotent: skip if already present in
idempotent mode):

```json
{
  "level": 4,
  "last_change": "<ISO-8601-now>",
  "reason": "initial",
  "restored_when": null,
  "trigger_history": []
}
```

Key values:

- `level: 4` — default is Level 4 (Coordinate Sequences Under Supervision).
  This matches the Orchestrator's designation in `agents/orchestrator.md`.
- `trigger_history: []` — initialized as an empty array. The
  `scripts/update-effective-autonomy.py` script (Sprint 4 deliverable) appends
  entries here on every floor change. Entries track what event triggered the
  change, the timestamp, and the originating agent.

Schema reference: `schemas/effective-autonomy.schema.json`

The file path `state/effective-autonomy.json` (relative to `.council/`) is the
canonical location. The Orchestrator reads this file at the start of every
sprint loop iteration.

---

### Step 8 — Write Governance Signal to `.harness/config.json`

Write (or merge) the governance block into `.harness/config.json`. **Use
`scripts/inject-governance.py`** rather than hand-editing the file — manual
JSON merge is error-prone and can corrupt unrelated harness keys (mode,
project_type, components_enabled, etc.). The helper script preserves every
key the harness owns and only updates `governance`.

```bash
python ${CLAUDE_PLUGIN_ROOT}/scripts/inject-governance.py --file .harness/config.json
```

The script is idempotent: a second invocation when the governance block already
matches exits 0 with `OK: governance block already correct`. If the user has
previously set `governance.enabled: false` (opt-out), the script preserves that
setting and exits 2 with a warning — the council-kickoff skill should treat
this as a user-driven veto and not override it.

The block written has the following shape:

```json
{
  "governance": {
    "enabled": true,
    "plugin": "henkaten-council",
    "council_state_path": ".council/",
    "review_frequency": "every-sprint"
  }
}
```

This signal tells the `trine-eval` harness that the `henkaten-council` plugin
is active for this project. Trine-eval reads `governance.enabled` before
deciding whether to include governance report sections in sprint evaluation
output.

Note: `.harness/config.json` is the only `.harness/` file that the council
plugin writes to. The sacred files (`.harness/spec.md`, `.harness/features.json`,
`.harness/sprints.json`) are read-only from the council's perspective and require
Level 5 approval to modify (see `instructions/controlled-artifacts.md`).

---

### Step 9 — Delegate to trine-eval

After the council baseline is in place, delegate to trine-eval for harness
initialization or sprint evaluation via `Task`:

- **First-time kickoff** (`.harness/spec.md` does not yet exist): call
  `/trine-eval:harness-kickoff` to produce `.harness/spec.md`,
  `.harness/features.json`, and `.harness/sprints.json`.
- **Sprint loop** (harness baseline already exists): call
  `/trine-eval:harness-sprint NN` where `NN` is the sprint number being
  evaluated.

The delegation syntax for the Orchestrator is a `Task` call, not a direct
invocation:

```
Task: /trine-eval:harness-kickoff
```

or

```
Task: /trine-eval:harness-sprint 01
```

The council-kickoff skill does not implement trine-eval logic. It delegates and
waits for the result before continuing to Step 10.

---

### Step 10 — Surface Git Merge Opt-In (v2.1 Amendment A11)

Display the following one-time setup note to the user after all files are
written:

> **One-time setup note:** `git merge` is in the `deny` tier by default in
> `.claude/settings.json`. This means the Orchestrator will never propose or
> execute a merge without your explicit override. If you want the Orchestrator
> to propose merges when a sprint PASSes, move `git merge *` from the `deny`
> array to the `ask` array in `.claude/settings.json`.
>
> This is a one-time per-project configuration step. The ask tier requires
> user confirmation before each merge, so it is safe to enable.

Offer to show the user the exact line to edit:

```json
"ask": [
  ...existing entries...,
  "git merge *"
]
```

Remove the corresponding entry from `deny`:

```json
"deny": [
  ...entries without "git merge *"...
]
```

This is presented as a **user choice**, not an automatic change. The
council-kickoff skill must never modify `.claude/settings.json` automatically.

The git merge configuration is surfaced here because the `ask` tier in
`.claude/settings.json` is the correct mechanism per §9.3. Moving `git merge`
to `ask` is the only supported way to enable orchestrator-proposed merges; the
skill must not describe any other path.

---

### Step 11 — Confirm Baseline

Present a summary of all files created or verified:

```
Council baseline complete:
  .council/config.json              [created / already present]
  .council/council-manifest.json    [created / already present]
  .council/henka-register.jsonl     [created / already present]
  .council/decision-log.jsonl       [created / already present]
  .council/audit-log.jsonl          [created / already present]
  .council/standard-work.json       [created / already present]
  .council/state/effective-autonomy.json  [created / already present]
  .council/course-corrections/      [created / already present]
  .council/proposed/                [created / already present]
  .council/proposed/archive/        [created / already present]
  .council/retrospectives/          [created / already present]
  .council/sessions/                [created / already present]
  .harness/config.json              [governance signal written]
  Hook self-check:                  [pass / gap reported]
```

If any file could not be created (permission error, disk full, etc.), report
the failure explicitly and do not mark the baseline as complete.

After confirming the baseline, inform the user that `/henkaten-council:council-autorun`
is the next skill to invoke when they are ready to start the sprint review loop
(available from Sprint 4 onward).

---

## Idempotency Summary

| File / Directory | Guard |
|---|---|
| `.council/config.json` | Skip if present (idempotent mode) |
| `.council/council-manifest.json` | Skip if present (idempotent mode) |
| `.council/henka-register.jsonl` | Create only if absent |
| `.council/decision-log.jsonl` | Create only if absent |
| `.council/audit-log.jsonl` | Create only if absent |
| `.council/standard-work.json` | Skip if present (idempotent mode) |
| `.council/state/effective-autonomy.json` | Skip if present (idempotent mode) |
| All six directories | `mkdir -p` semantics (no error if present) |
| `.harness/config.json` | Merge `governance` key; do not overwrite |

---

## Error Handling

| Error Condition | Behavior |
|---|---|
| `.harness/` missing | Pause; offer trine-eval kickoff delegation |
| `.council/` exists | Ask user for idempotent vs full-overwrite |
| Hook missing | Report gap; pause until user confirms installation |
| File write fails | Report failure; do not mark baseline complete |
| trine-eval delegation fails | Report error; mark trine-eval step as incomplete |
| User declines git merge opt-in | Acknowledge; proceed; do not modify settings.json |

---

## Cross-References

- Orchestrator agent contract: `agents/orchestrator.md`
- Architect agent contract: `agents/architect.md`
- Council config schema: `schemas/council-config.schema.json`
- Council manifest schema: `schemas/council-manifest.schema.json`
- Effective autonomy schema: `schemas/effective-autonomy.schema.json`
- Standard work schema: `schemas/standard-work.schema.json`
- Controlled artifacts: `instructions/controlled-artifacts.md`
- Andon protocol: `instructions/andon-protocol.md`
- Evidence first: `instructions/evidence-first.md`
- Human approval: `instructions/human-approval.md`
- Bash permission model: `.claude/settings.json`
