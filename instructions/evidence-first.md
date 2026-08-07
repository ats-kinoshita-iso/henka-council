# Evidence-First Behavior — Behavioral Instructions

Every council agent MUST ground every claim in evidence before reporting it.
This instruction defines the mandatory evidence format, the verification
syntax allowlist, and the enforcement mechanism.

---

## Core Principle

Every recommendation, finding, or classification in an agent's output must
cite specific, re-runnable evidence. Claims that cannot be grounded in a
directly observable artifact are either `inferred` (citing the chain of
observed claims they derive from) or `speculative` (with restricted permitted
actions). Unsupported claims are rejected by the orchestrator.

This is the genchi genbutsu (現地現物 — "go and see") principle: every claim
must be traceable to a firsthand observation that another party can independently
reproduce.

---

## Mandatory Evidence Fields

Every claim in every agent output MUST include:

```json
{
  "claim": "what was observed or inferred",
  "evidence_class": "observed" | "inferred" | "speculative",
  "confidence": "high" | "medium" | "low",
  "verification": "re-runnable command (required for observed claims)"
}
```

### `evidence_class` — Required

- `observed` — the agent directly read the file, diff, or output and reports
  what it saw. MUST include a `verification` field with a re-runnable command.
- `inferred` — derived from one or more `observed` claims. MUST cite the
  observed claims it derives from. Does NOT require a `verification` field,
  but must name the source observed claims explicitly.
- `speculative` — hypothesis not yet grounded in observation. Permitted action:
  `log-only` only. An agent MUST NOT use a `speculative` claim as the basis for
  `propose-to-user` or `escalate` actions.

### `confidence` — Required

- `high` — strong evidence; deterministic reproduction likely.
- `medium` — reasonable evidence; one or more caveats.
- `low` — weak signal; easily dismissed. Default for `passive` change_origin
  unless corroborated by a second signal (see §6.3).

---

## Verification Syntax Allowlist

The `verification` field in `observed` claims MUST match one of the following
allowlisted command prefixes. The enforcer is `scripts/run-verification.py`,
which checks the string against this allowlist before executing the command.

Non-allowlisted strings are **rejected before execution** — the agent's output
is returned as invalid, and the rejection is logged as an `agent-capability-change`
Henkaten (informational).

| Allowed prefix | Purpose | Example |
|---|---|---|
| `git diff`, `git show`, `git log`, `git status`, `git branch`, `git ls-files` | Read-only git inspection | `git diff main..HEAD -- features.json` |
| `grep`, `rg` (read-only flags only) | Content search | `grep -n "feature_id" .harness/features.json` |
| `cat`, `head`, `tail` | File read | `cat .harness/sprints.json` |
| `jq` (explicit file path; no `-i` flag) | Structured JSON read | `jq '.sprints \| length' .harness/sprints.json` |
| `python3 -m json.tool`, `python3 scripts/validate-*.py` (bare `python` equally accepted) | Schema validation only | `python3 -m json.tool .council/config.json` |
| `test`, `[ ... ]` (POSIX file tests) | File-existence checks | `test -f .council/config.json` |

### Disallowed Verification Commands

The following are NEVER permitted in `verification` fields:

- Any command that writes to disk: `>`, `>>`, `tee`, `Write`, `Edit`
- Network calls: `curl`, `wget`, `gh`, `git push`, `git fetch`, `git pull`
- Project source execution: `bun run`, `uv run` (other than the allowlisted validators)
- Shell redirects or pipes-to-shell: `|sh`, `|bash`, `$(…)`, `` `…` ``
- Arbitrary evaluation: `eval`, `exec`
- In-place JSON editing: `jq -i …`

---

## Enforcement by `scripts/run-verification.py`

The orchestrator's fan-in step (Step 1C of `/council-autorun`) picks one
random `observed` claim per agent output and passes its `verification` string
to `scripts/run-verification.py` (a Sprint 4 deliverable). That script:

1. Checks the string against the allowlist before execution.
2. Rejects non-allowlisted strings and logs an `agent-capability-change`
   Henkaten (informational).
3. Executes allowlisted commands with a per-command timeout (default 10s),
   CPU/memory bounds, and `cwd=<project-root>`.
4. Compares the output to the agent's reported observation.
5. If the re-run diverges: logs a `quality-defect-anomaly` Henkaten with
   high impact and `change_origin: passive`.

Until `scripts/run-verification.py` is implemented (Sprint 4), agents must
include syntactically-conformant `verification` fields so they are immediately
enforceable when the script is wired in.

---

## Evidence Classification in Practice

### For `observed` claims

```json
{
  "claim": "features.json contains 11 feature entries",
  "evidence_class": "observed",
  "confidence": "high",
  "verification": "jq '.features | length' .harness/features.json"
}
```

### For `inferred` claims

```json
{
  "claim": "Sprint 3 depends on Sprint 2's agent contracts",
  "evidence_class": "inferred",
  "confidence": "high",
  "derived_from": [
    "observed: sprints.json[2].dependencies = [1, 2]",
    "observed: Sprint 2 delivers agents/ directory"
  ]
}
```

### For `speculative` claims

```json
{
  "claim": "the hook installation step may fail on Windows due to path separator differences",
  "evidence_class": "speculative",
  "confidence": "low",
  "permitted_action": "log-only"
}
```

---

## Coverage Section

Every agent response MUST include a `coverage` section listing:

- Files successfully read (with last-modified timestamp if available)
- Files expected but missing (with graceful-degradation note)
- Any `verification` commands that could not be executed in this context

Missing files must be handled gracefully: agents report `status: partial` and
note the degraded scope. Agents MUST NOT hallucinate missing file contents.

---

## Summary Checklist for Agents

Before emitting a response:

- [ ] Every claim includes `evidence_class` (`observed` | `inferred` | `speculative`).
- [ ] Every claim includes `confidence` (`high` | `medium` | `low`).
- [ ] Every `observed` claim includes a `verification` field.
- [ ] All `verification` strings match the allowlist prefixes above.
- [ ] No `speculative` claim is used as the basis for `propose-to-user` or `escalate`.
- [ ] `coverage` section lists available and missing inputs.
- [ ] No files were modified (all agent operations are read-only except orchestrator).
