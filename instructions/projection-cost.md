# Projection Cost — Governance of the Always-Projected Surface

Every Claude Code session that runs a henkaten-council skill loads a fixed
set of files into working context before any loop begins. That set is the
**always-projected surface**, and it consumes context permanently for the
duration of the session. Without governance, the always-projected surface
can grow unboundedly and crowd out the working context available for the
loop's actual work.

This instruction defines the measurement methodology, the governance budget,
the override convention, and the change-control discipline for the
always-projected surface.

---

## What is always-projected

The always-projected file set for the henkaten-council plugin is:

- `CLAUDE.md` at the repository root (Claude Code root convention; auto-loaded
  for any session in a directory that contains it).
- Every file listed in `.claude-plugin/plugin.json` under `"skills"`.
- Every file listed in `.claude-plugin/plugin.json` under `"agents"`.

Files referenced from these (e.g. `@instructions/<name>.md` cross-references
inside an agent file) are loaded **on demand**, not always-projected, and are
out of scope for the projection-cost budget. Likewise, schemas, scripts,
templates, and tests are not in the always-projected set unless explicitly
listed in the plugin manifest.

The discovery rule is mechanical and is implemented in
[`scripts/measure-projection-cost.py`](../scripts/measure-projection-cost.py).
If a future plugin manifest revision adds a new auto-load category, that
category must be added to the discovery function and to this document in the
same change.

---

## Measurement methodology

Token cost for each file is computed as one of two values:

1. **Override**: if the file's YAML front-matter contains a
   `projection_cost_tokens: <integer>` key, that integer is used verbatim.
   This permits authors to record an authoritative tokenizer-based count when
   one is available, and to set a hard ceiling for review.
2. **Estimate**: otherwise, `int(round(word_count * 1.3))`. The 1.3 multiplier
   is a rough word-to-token approximation that matches typical English markdown
   for the Claude tokenizer family within ~10%. It is deliberately approximate;
   the override path exists for files where precision matters.

The estimate is intentionally imprecise. It is meant to surface drift, not
to enforce a tokenizer-accurate count. When a tokenizer-accurate counter
becomes generally available, the methodology should be revised in this file
(no constitutional change required); the policy lives here, not in the
schemas.

---

## The budget

The current always-projected budget is **8,000 tokens**. The baseline at
PR-A merge is approximately 6,588 tokens, leaving roughly 1,412 tokens of
headroom.

The budget is advisory: the measurement script reports it, the kickoff skill
surfaces it, and CI emits a `::warning::` annotation if exceeded. The build
does **not** fail on over-budget at this stage.

Overruns are not permitted to accumulate silently. When the running total
exceeds budget the appropriate response is one of:

- **Trim**: prune content from one of the always-projected files (move
  references to on-demand instructions, collapse repeated context into a
  single citation, remove obsolete sections).
- **Re-baseline**: if the surface has grown for documented and load-bearing
  reasons, raise the budget via an ADR that justifies why the additional cost
  is identity-essential. This is the same pattern that
  [docs/design/adr-0002-projection-cost-budget.md](../docs/design/adr-0002-projection-cost-budget.md)
  followed for the initial 8,000.
- **Promote**: move always-projected content into an on-demand file
  (under `instructions/`), deleting it from the always-projected file and
  cross-referencing it via `@instructions/<name>.md`. This is the cheapest
  remediation path when content is referenced by agents but does not need to
  be primed before any loop runs.

---

## Front-matter override convention

Agent and skill files MAY include `projection_cost_tokens: <integer>` in
their YAML front-matter. The integer must reflect a real measurement (a
tokenizer-accurate count, or the rounded estimate) and must be updated when
the file substantively changes. If absent, the measurement script falls back
to the word-count estimate.

Override is optional at PR-A merge; backfill is incremental. Files that ship
without an override will be measured by estimate until an author records a
precise value.

---

## When the script runs

- **At kickoff** (`/henkaten-council:council-kickoff` Step 1e): runs once
  per project bootstrap, surfacing the current total and headroom to the
  user. Advisory only.
- **In CI** (`.github/workflows/ci.yml`): runs once per push and pull
  request on every supported runner. Emits a `::warning::` annotation if
  over budget. Does not fail the build.
- **By hand**: any contributor can run
  `python scripts/measure-projection-cost.py` (optionally with `--budget`,
  `--strict`, `--json`, or `--repo-root` flags) at any time.

---

## Out of scope at PR-A

- Strict CI enforcement (fail-the-build on over-budget). Deliberately
  deferred until empirical data from at least one quarter of advisory
  measurement establishes a sustainable budget level.
- Tokenizer-accurate measurement. The 1.3 word-to-token approximation is
  good enough for drift detection; precision will follow tokenizer
  availability.
- Per-loop projection-manifest budgeting (the on-demand surface a single
  loop loads). The always-projected surface is the only governance target
  at this stage.

When any of these is reconsidered, update this document and file an ADR.
