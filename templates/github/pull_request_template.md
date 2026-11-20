<!--
Installed by /henkaten-council:council-kickoff into the target repo as
.github/pull_request_template.md. Forces a direction declaration at PR-open so
divergent work is intentional, not silent (the bay-o-net wizardly-johnson case).
-->

## What & why

<!-- Brief description of the change and the problem it solves. -->

## Direction check

- **Strategic anchor:** <!-- e.g. docs/divorce-spec.md §Persistence format / ADR-0008 -->
- **exploration_mode:** <!-- mainline | parallel-exploration | competitive -->
- [ ] This work is reconciled with the strategic anchor's locked decisions.
- [ ] If `exploration_mode` is **not** `mainline`, the divergence is justified below
      (the competing hypothesis being tested):

  <!-- divergence_justification (required for parallel-exploration / competitive) -->

- [ ] A work charter exists at `.council/charters/` for this work
      (`/henkaten-council:council-charter`).

<!--
The direction-check GitHub Action (Layer A) will post a status check:
red = undeclared mainline drift / silent divergent branch; neutral = declared
exploration. The in-session council gate (Layer B) judges semantic alignment.
-->
