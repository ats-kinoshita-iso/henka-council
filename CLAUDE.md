# Henkaten Council — Plugin Instructions for Claude Code

This file is loaded automatically by Claude Code whenever a council skill runs
inside a project that has installed the `henkaten-council` plugin. It provides
behavioral context and constraints that apply to every agent and skill in this
plugin.

---

## What the Henkaten Council Plugin Does

The `henkaten-council` plugin adds a continuous-improvement governance layer on
top of any project managed by the `trine-eval` harness. It introduces:

- **Change-point detection (henkaten)** — every deviation from planned behavior
  is classified using the 4M axis (Man/Machine/Method/Material), assigned a
  `change_origin` (active vs. passive), and recorded in
  `.council/henka-register.jsonl`.
- **Autonomous decision audit** — every correction applied by the Orchestrator
  is logged to `.council/decision-log.jsonl` with evidence citations,
  reversibility classification, and the effective autonomy level at decision time.
- **Dynamic autonomy floor** — the Orchestrator reads
  `.council/state/effective-autonomy.json` at the start of every sprint loop
  and adjusts its authority accordingly. The floor can drop (two consecutive
  sprint FAILs, three distinct-originator andon stops) or be restored via
  `/council-review --restore-autonomy`.
- **Andon protocol** — any council agent may issue `andon_signal: alert` or
  `andon_signal: stop` to surface problems. The Orchestrator honors all stop
  signals unconditionally and precedes every response to a stop signal with the
  verbatim thank-the-puller acknowledgment.
- **Trine-eval integration** — the plugin delegates sprint evaluation to
  `/trine-eval:harness-sprint` via `Task` dispatch. The governance signal in
  `.harness/config.json` records that this plugin is active.

---

## Agent Hierarchy

| Agent | Level | Context | Tools |
|---|---|---|---|
| orchestrator | 4 | inherit | Read, Glob, Grep, Bash, Write, Task |
| architect | 2 | fork | Read, Glob, Grep |
| scope-guardian | 2 | fork | Read, Glob, Grep |
| henkaten-detector | 1 | fork | Read, Glob, Grep |
| retrospective | 2 | fork | Read, Glob, Grep |

The Orchestrator is the **only** agent permitted to use `Task` and `Write`. All
other agents are proposal-only and return their output as text.

---

## Controlled Artifacts

The following files are **append-only** within a live sprint. No agent or skill
may overwrite or delete them:

- `.council/henka-register.jsonl`
- `.council/decision-log.jsonl`
- `.council/audit-log.jsonl`

Any write attempt to these files must go through the approved append scripts
(`scripts/append-henka.py`, `scripts/append-decision.py`). The
`hooks/enforce-append-only.sh` hook enforces this at the `PreToolUse` level.

The following files are **sacred** and require Level 5 (human) approval before
any modification:

- `.harness/spec.md`
- `.harness/features.json`
- `.harness/sprints.json`

---

## Skills Provided by This Plugin

| Skill | Invocation | Purpose |
|---|---|---|
| council-kickoff | `/henkaten-council:council-kickoff` | Bootstrap `.council/` governance baseline in a new project |

Additional skills (council-autorun, council-review, council-retro, council-detect)
are delivered in later sprints (S4–S6).

---

## Bash Permission Model

The `.claude/settings.json` file in this repository defines three tiers:

- **allow** — read-only git inspection (`git status`, `git diff`, `git log`,
  `git show`, `git branch -l`, `git ls-files`). These run without prompting.
- **ask** — branch-local reversible mutations (`git add`, `git commit`,
  `git checkout -b`, `git tag`, `git stash`). These require user confirmation.
- **deny** — destructive or cross-repo operations (`git push`, `git reset --hard`,
  `git rebase`, `git merge`, `rm -rf`). These are blocked entirely by default.

The `git merge` command is in `deny` by default per v2.1 amendment A11. If you
want the Orchestrator to propose merges on sprint PASS, move `git merge *` from
`deny` to `ask` in `.claude/settings.json`. This is a one-time per-project
setup step.

---

## Evidence and Verification

All agent outputs must include:

- `evidence_class`: one of `observed`, `inferred`, `assumed`
- `confidence`: integer 1–5
- For `observed` claims: a `verification` field containing a conformant command
  from the verification syntax allowlist

The Orchestrator spot-checks one random `observed` claim per agent output during
fan-in. Non-conformant verification strings are rejected and logged as
`agent-capability-change` henkaten records.

---

## Key File Paths at a Glance

```
.council/
  config.json                   — council configuration (autonomy, andon settings)
  council-manifest.json         — active agent roster and council identity
  henka-register.jsonl          — append-only henkaten change-point log
  decision-log.jsonl            — append-only decision audit log
  audit-log.jsonl               — append-only tool-call audit log
  standard-work.json            — current standard-work baseline
  state/
    effective-autonomy.json     — live autonomy floor (level, trigger_history)
  proposed/                     — nemawashi position papers (in-flight)
  proposed/archive/             — ratified position papers (post-ratify archive)
  course-corrections/           — applied course-correction files
  retrospectives/               — retrospective outputs (mini, PDCA, jishuken)
  sessions/                     — context compaction snapshots
```
