# ADR 0002: Projection-Cost Budget for the Always-Projected Surface

- **Status:** Accepted
- **Date:** 2026-05-13
- **Author:** Sangen Option A integration (PR-A)
- **Scope:** Plugin-wide governance of the always-projected file set

---

## Context

Every Claude Code session that runs a henkaten-council skill loads a fixed
set of files into working context before any loop begins. The set comprises
`CLAUDE.md` plus every file listed in `.claude-plugin/plugin.json` under
`"skills"` and `"agents"`. As of PR-A baseline this is four files totalling
approximately 6,588 estimated tokens
([CLAUDE.md](../../CLAUDE.md),
[skills/council-kickoff/SKILL.md](../../skills/council-kickoff/SKILL.md),
[agents/orchestrator.md](../../agents/orchestrator.md),
[agents/architect.md](../../agents/architect.md)).

Working context is finite. Tokens consumed by the always-projected surface
are unavailable for loop work, retrieved instructions, agent fan-out, and
the user's own input and outputs. Until PR-A there has been no measurement
of this surface, no budget governing it, and no discipline against
unbounded growth.

The risk is not catastrophic but it is real and one-directional: every
addition to an always-projected file makes every future loop slightly more
context-constrained, and the marginal cost of any single addition is below
the threshold of perception. The cumulative drift over many edits can be
substantial.

This ADR introduces a governance mechanism: measure, budget, surface, and
enforce-by-convention rather than by build-failure at this stage.

---

## Decision

Adopt a projection-cost budget of **8,000 tokens** for the always-projected
file set, governed advisorily.

The mechanism has four parts:

1. **Measurement script.** [`scripts/measure-projection-cost.py`](../../scripts/measure-projection-cost.py)
   discovers the always-projected file set from `.claude-plugin/plugin.json`
   plus the `CLAUDE.md` convention, computes per-file token counts (override
   from front-matter `projection_cost_tokens` if present, otherwise
   `int(round(word_count * 1.3))`), reports per-file and total, and exits
   non-zero only if `--strict` is passed.
2. **Documented methodology.** [`instructions/projection-cost.md`](../../instructions/projection-cost.md)
   defines what the always-projected set is, how cost is measured, how the
   budget is set and revised, and what to do when the budget is exceeded.
   The methodology lives in `instructions/` (on-demand load) so it does not
   itself contribute to the always-projected surface.
3. **Kickoff surfacing.** A new step in
   [`skills/council-kickoff/SKILL.md`](../../skills/council-kickoff/SKILL.md)
   runs the measurement script during project bootstrap and reports the
   total and headroom to the user. Idempotent and informational; does not
   block kickoff completion.
4. **CI advisory check.** [`.github/workflows/ci.yml`](../../.github/workflows/ci.yml)
   runs the script on every push and pull request and emits a `::warning::`
   annotation if the total exceeds the budget. The build does not fail.

The 8,000-token budget is chosen empirically: at PR-A the measured baseline
is ~6,588 tokens, leaving roughly 1,412 tokens of headroom. That is enough
slack to absorb the small additions PR-B, PR-C, and PR-D will make to
`CLAUDE.md` and `skills/council-kickoff/SKILL.md` without immediately
forcing a re-baseline conversation. It is not so generous that drift can
hide; the headroom is approximately 18% of the current surface, comparable
to the fraction of working context that a typical mid-size loop consumes.

A `projection_cost_tokens` front-matter override is permitted on agent and
skill files. Override is optional at PR-A merge; backfill can happen
incrementally. The override exists for files where a tokenizer-accurate
count is preferable to the 1.3-words approximation.

---

## Consequences

### Positive

- The always-projected surface becomes a measured, named, and budgeted
  thing. Drift cannot hide.
- Authors see the cost of their additions on every PR via the CI advisory
  annotation, and at every project bootstrap via the kickoff report.
- The methodology lives in `instructions/projection-cost.md` (on-demand)
  rather than `CLAUDE.md` (always-projected), so the governance does not
  itself bloat the surface it governs.
- The override convention permits authors to pin a precise count when
  precision matters, without requiring it of all files.
- The design composes cleanly with PR-B (stop conditions), PR-C
  (loop-shape pattern category), and PR-D (Cynefin classification), each
  of which adds small amounts of always-projected text that fit within the
  current headroom.

### Negative / accepted

- Advisory enforcement at this stage means a determined author can
  exceed the budget by ignoring the warning. Mitigation: the kickoff
  report makes this visible at project bootstrap, and the headroom is
  small enough that a meaningful overrun will be obvious in CI logs.
  Strict enforcement can be turned on later (see "Out of scope" below)
  once empirical data establishes a sustainable budget level.
- The 1.3 word-to-token ratio is approximate and will be off by up to
  ~10% for typical English markdown. This is acceptable for drift
  detection but inadequate for precise comparison across model
  generations. The override path exists for authors who need precision;
  the methodology will be revised when a tokenizer-accurate counter
  becomes generally available.
- Adding the kickoff step and the CI job is itself a small surface
  expansion (the new step in `council-kickoff/SKILL.md` adds tokens to
  the always-projected surface). The expected addition is ~150-300
  tokens, well within the 1,412-token headroom. PR-A's measurement after
  these additions is the baseline against which subsequent PRs are
  judged.
- The budget itself (`DEFAULT_BUDGET = 8000` in the script,
  `8,000 tokens` in the instructions, `8,000` in this ADR) lives in
  three places. Synchronisation is by convention, not enforced. If the
  budget is revised, all three must move together. The first ADR that
  raises it must call this out explicitly.

### Out of scope

- **Strict CI enforcement.** Deliberately deferred until empirical data
  from at least one quarter of advisory measurement establishes a
  sustainable budget level.
- **Tokenizer-accurate measurement.** The 1.3 multiplier is good enough
  for drift detection.
- **Per-loop projection-manifest budgeting.** Sangen's full design
  governs not just the always-projected surface but the per-loop
  on-demand surface too. henka-council's PR-A absorbs only the
  always-projected discipline; per-loop manifests remain the agent's
  judgment, governed by working-context exhaustion rather than by a
  recorded budget.

---

## Alternatives Considered

### Strict CI fail-on-over-budget from PR-A merge

Rejected for now. Without empirical data on what a sustainable budget
looks like across normal plugin evolution, a strict gate could block
unrelated work by happening to push a CLAUDE.md edit over the budget.
Advisory-first lets us observe several quarters' worth of churn before
deciding what level of strictness is appropriate.

### Hard schema-level enforcement (e.g. `projection_cost_tokens` required
in every front-matter)

Rejected. The override convention is opt-in for a reason: most files
will be measured by estimate, and forcing every author to maintain an
accurate token count on every edit is a lot of friction for a discipline
that is fundamentally advisory.

### No measurement; rely on author discipline

Rejected. Author discipline is exactly what this ADR is trying to
support, not replace. Measurement and surfacing are the leverage that
makes discipline cheap.

### Budget at the current baseline (~6,600) with no headroom

Rejected. Zero headroom means the budget would be exceeded by PR-A's own
additions to `CLAUDE.md` and `council-kickoff/SKILL.md`, which would
trigger a warning on the introducing PR. Unhelpful.

### Budget at 12,000 or higher (substantial headroom)

Rejected. With ~80% headroom the budget becomes ceremonial — drift can
accumulate for years before it bites. The chosen 8,000 is tight enough
to make a meaningful overrun visible within a small number of edits.

---

## Trigger Conditions for Re-Baseline

The budget should be revisited when any of the following holds:

- Two consecutive PRs trigger the CI advisory warning.
- A new always-projected file is being proposed that cannot fit within
  current headroom and cannot be moved to on-demand.
- The plugin manifest grows to include a new auto-load category not
  covered by the current discovery rule.
- A tokenizer-accurate counter becomes available and the methodology is
  updated; the baseline measurement under the new counter may diverge
  meaningfully from the current estimate.

In every case, the re-baseline is a separate ADR that justifies the new
number and updates `DEFAULT_BUDGET` in the script,
`instructions/projection-cost.md`, and the budget statement in the new
ADR's predecessor reference.
