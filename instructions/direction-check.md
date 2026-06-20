# Direction Check — flagging wrong-direction work at work-start

## The failure this prevents

On the bay-o-net project, three sprints of work compounded on a wrong direction
before anyone noticed. The harness spec said "build a `.cmpx` writer"; the
strategic anchor (`divorce-spec.md`) said "no writer at any point." Sprint 9
shipped the writer; a silent side branch (`claude/wizardly-johnson-a95216`)
carried Sprints 10–12 further down the killed path. It was caught **by hand** at
contract review (ADR 0008). The lesson, recorded as yokoten
`YK-0001-divorce-spec-as-load-bearing-anchor`: **before any contract is approved,
the work must be compared to the strategic anchor — and divergent branches must
declare their purpose.**

## The mechanism

A **work charter** (`schemas/work-charter.schema.json`, written by
`/council-charter`) declares, at work-start, the strategic anchor the work must
honor, the workstreams it touches, and its **`exploration_mode`**:

- **mainline** — work on the sanctioned direction. Drift here is undeclared → BLOCK.
- **parallel-exploration** — a deliberate side-track/spike that may diverge.
- **competitive** — an intentional competing implementation benchmarked against
  mainline ("competitive code development").

The two non-mainline modes make divergence **legitimate when declared** — but
they require a `divergence_justification`. The charter is the single source of
truth; its `exploration_mode` is the one flag that propagates to every surface.

## Two-layer grader (why not pure determinism)

Pure keyword/grep checks fail two ways:
- **False negatives** — the next wrong direction is a *paraphrase*, not a keyword
  you pre-listed.
- **False positives → alarm fatigue** — a keyword like "writer" fires on the
  *sanctioned* YAML writer (bay-o-net's `HKP-0004`, literal-vs-intent).

So the check is layered, mirroring trine-eval's own code-first-then-LLM-judge
grader hierarchy:

- **Layer A — `scripts/direction-check.py` (deterministic, no LLM).** Presence
  and declaration tripwires: charter present? mode declared? anchor cited?
  known-killed workstream reintroduced? divergent mode justified? Exit codes
  encode the tier (0 PASS / 10 WARN / 20 BLOCK). Layer A runs on the surfaces
  that cannot call a model: the **git hook** and **CI**.
- **Layer B — `agents/direction-guardian.md` (LLM judge, in-session).** Reads the
  anchor's locked decisions/prohibitions and the proposed contract and judges
  semantic alignment, catching paraphrased/novel drift Layer A cannot see. Runs
  every sprint at `council-autorun` Step 1A.7. Calibrated with the anchor as
  reference; BLOCK decisions are multi-sampled (harness `trials`) so a single
  flaky sample never blocks alone.

## Tiered enforcement

| Situation | exploration_mode | Verdict |
|---|---|---|
| No drift, anchor cited | any | PASS |
| Drift, declared + justified | parallel-exploration / competitive | WARN |
| Drift, undeclared | mainline (or no charter) | BLOCK |
| Divergent branch, no charter | — | BLOCK |
| Missing anchor citation | mainline | WARN |

Per-check tiers are tunable via `direction_check.tier_overrides` in
`.council/config.json`. The trine-eval seam honors `direction_check.enforcement`
(`block` aborts the sprint on BLOCK; `warn` only surfaces it).

## The three surfaces

1. **In-session (council).** Step 1A.7 of `council-autorun` runs the
   `direction-guardian`; BLOCK on mainline issues `andon_signal: stop` and halts
   before delegating the sprint.
2. **Local git (`hooks/enforce-branch-charter.sh`).** PreToolUse Bash hook;
   blocks a `git commit`/`git checkout -b` on a divergent branch that has no
   sanctioned charter. Fails open whenever it cannot decide.
3. **GitHub (`templates/github/`).** A PR template forces a direction
   declaration; a GitHub Action runs Layer A on push/PR and posts a status check
   (red on undeclared mainline drift, neutral on declared exploration). The
   in-session gate can also open a draft PR labelled by `exploration_mode`.

## Configuration

`.council/config.json` → `direction_check` (off by default):

```json
{
  "direction_check": {
    "enabled": true,
    "anchor_path": "docs/divorce-spec.md",
    "locked_decisions": ["ADR-0008"],
    "killed_workstreams": ["cmpx writer", "cmpx parser refactor"],
    "mainline_branch": "main",
    "enforcement": "block",
    "tier_overrides": {},
    "github": { "open_draft_pr": false }
  }
}
```

Keep `killed_workstreams` keywords **specific** (e.g. `cmpx writer`, not
`writer`) so Layer A does not false-positive on sanctioned work — Layer B owns
the fuzzy/semantic judgment.
