# Changelog

## v0.1.3 — 2026-08-06

Linux/container portability release. Fixes confirmed breakage when a Windows
checkout is reused on Linux (e.g. a WSL `claude` installing the plugin from a
`/mnt/c` directory marketplace), plus path-anchoring defects that only
manifest in installed-plugin contexts. No changes to schemas or the
governance protocol.

### Added

- **`.gitattributes`** — forces `eol=lf` for `*.sh` and `*.py` (with a
  `* text=auto` default). Windows checkouts previously produced CRLF hook
  scripts; bash on Linux fails to parse those and exits 2. For the Stop hook
  (`hooks/session-stopped-marker.sh`) exit 2 means "block the stop", which
  sent headless `claude -p` sessions into a multi-turn loop returning an
  empty result (observed live 2026-08-06 in WSL). Existing Windows checkouts
  pick up the policy after a re-checkout, e.g.
  `git rm -r --cached . && git reset --hard` (or delete and re-clone).
- **`requirements.txt`** — declares the previously undeclared `jsonschema>=4.0`
  runtime dependency of the seven council scripts that import it. CI now
  installs from this file instead of an inline package list.
- **`skills/council-kickoff/SKILL.md` Step 1f** — Python dependency
  pre-flight: verifies `jsonschema` is importable at kickoff and surfaces the
  install command before any governance state exists.
- **CI** — runs `tests/scripts/test-run-verification.py` on both platforms
  (the test existed and was isolation-hardened in #25 but was never wired
  into the workflow).
- **Hook fixture tests** — backslash Windows-path envelope cases (relative,
  absolute, and bare-filename-with-backslash-cwd, plus a non-`.council`
  allow case) in both `tests/hooks/test-enforce-append-only.sh` and
  `tests/hooks/win/test-enforce-append-only.ps1`, locking in the path
  normalization the hooks already perform.

### Changed

- **Skill and instruction call sites** — every documented script invocation
  now uses `python3` (Debian/Ubuntu images ship no bare `python`) and an
  explicit `${CLAUDE_PLUGIN_ROOT}/scripts/...` path instead of a bare
  relative `scripts/...` path, which resolved against the user's project cwd
  and failed in installed-plugin contexts. Touched: `council-kickoff`,
  `council-review`, `council-autorun`, `council-detect`, `from-plan`
  SKILL.md files, `instructions/evidence-first.md` (allowlist table), and
  `instructions/projection-cost.md`. The council-detect call also switched
  from a nonexistent `--record` flag to the stdin form
  (`echo '{...}' | python3 .../append-henka.py`) matching the script's
  actual interface.
- **Council scripts** (`append-henka.py`, `append-decision.py`,
  `update-effective-autonomy.py`, `validate-*.py`, `persist-plan.py`) — a
  missing `jsonschema` package now fails closed with the exact install
  command (exit 1) instead of an uncaught `ModuleNotFoundError` traceback.
- **`README.md` Prerequisites** — documents the Python ≥ 3.10 + `jsonschema`
  requirement with the install command, and the `python3`-first convention.

### Fixed

- **`scripts/run-verification.py`** — anchored `.council/` and the
  verification-command execution cwd to the plugin install directory
  (`_REPO_ROOT`) instead of the invoking project's cwd, inconsistent with
  every other council script's cwd-relative `pathlib.Path(".council")`. In an
  installed-plugin context, rejection Henkaten records were appended to (and
  executed commands ran inside) the plugin cache directory. `.council/` now
  resolves against the invoking cwd, executed commands inherit the invoking
  cwd, and only the sibling `append-henka.py` lookup stays anchored to the
  script's own directory. Covered by new tests 7a/7b/8 in
  `tests/scripts/test-run-verification.py`.
- **`henka-council.txt`** — line endings normalized (the only file whose
  committed content was CRLF).
- **`.claude-plugin/plugin.json`** — `license` said `Apache-2.0`; the LICENSE
  file and README are MIT (the #17 consistency pass missed this field).
  `homepage` pointed at the wrong GitHub org; corrected to
  `ats-kinoshita-iso/henka-council`.

## v0.1.2 — 2026-05-20

Plugin-packaging readiness pass. Makes henka-council installable via the
Claude Code marketplace flow on parity with `trine-eval`. No behavioral
changes to agents, scripts, schemas, or the governance protocol — all
changes are packaging, hook auto-registration, and documentation.

### Added

- **`.claude-plugin/marketplace.json`** — single-repo marketplace declaration
  with `source: "./"` so the repo can be added directly as a plugin
  marketplace via `/plugin marketplace add <git-url>` and the plugin
  installed via `/plugin install henkaten-council@henkaten-council`.
- **`hooks/hooks.json`** — plugin-level hook manifest that auto-registers
  the four required hooks (PreToolUse × 2, PostToolUse, Stop) at install
  time. Users no longer need to hand-edit `.claude/settings.local.json`
  for the standard marketplace install path. Bash variants are canonical;
  the PowerShell parity scripts in `hooks/win/` remain as documented
  fallback for hosts without bash.

### Changed

- **`.claude-plugin/plugin.json`** — dropped the explicit `skills` and
  `agents` arrays. They were incomplete (listed 1 of 7 skills and 2 of 7
  agents), which would have masked five skills and five agents at install
  time. Claude Code now auto-discovers from the `skills/` and `agents/`
  directories, matching trine-eval's manifest pattern. Also converted
  `author` from string form to object form for consistency.
- **`skills/council-kickoff/SKILL.md` Step 1d** — added Step 1d.0
  (auto-registration check) that passes when
  `${CLAUDE_PLUGIN_ROOT}/hooks/hooks.json` exists and declares all four
  required matchers. The existing manual registration snippets in
  1d.1 / 1d.2 / 1d.3 are now framed as the fallback path for direct-path
  installs or pure-PowerShell Windows hosts. Step 1d.3's fail condition
  now requires both auto-registration absent and manual registration absent.
- **`README.md` Install section** — Option A now describes the marketplace
  flow (`/plugin marketplace add` + `/plugin install …@…`). The previous
  single-step `/plugin install henkaten-council` instruction was incorrect:
  no public registry entry existed to resolve.
- **`README.md` Hook Installation section** — added preamble noting that
  hooks auto-register via the marketplace install path; the manual snippet
  is now framed as a fallback.

### Fixed

- **`README.md` license footer** — said `MIT`; the project actually ships
  under Apache-2.0 (LICENSE file is Apache-2.0, and `plugin.json` was
  already correct). Footer updated to match.

## v0.1.1 — 2026-05-12

### Fixed

First-dogfood findings — attempting `/henkaten-council:council-kickoff` against
a real downstream project (bay-o-net) surfaced several gaps in the kickoff
SKILL.md that would block a real user. All fixes are documentation/scaffolding,
no behavioral changes to hooks, scripts, or schemas.

- **`skills/council-kickoff/SKILL.md` Step 1d** — the original SKILL promised
  "provide the exact registration command and pause" if hooks were unregistered,
  but never specified what the command was. Step 1d now contains the literal
  copyable JSON snippet for `.claude/settings.local.json` covering all four
  required hook events (PreToolUse × 2, PostToolUse, Stop), with separate
  subsections for Linux/macOS (Step 1d.1) and Windows/PowerShell (Step 1d.2),
  plus the message to surface to the user (Step 1d.3). Uses `${CLAUDE_PLUGIN_ROOT}`
  for plugin-relative path resolution with fallback guidance for environments
  that don't resolve that variable.
- **`skills/council-kickoff/SKILL.md` Step 1c** — clarified that
  `.council/config.json`'s `project_type` (language/toolchain) and
  `.harness/config.json`'s `project_type` (trine-eval rubric) are different
  fields with the same name; explicitly noted it is normal for them to differ
  (`python` for council, `cli-tool` for harness). Added `Cargo.toml` → `rust`
  to the project-type detection list.
- **`skills/council-kickoff/SKILL.md` Step 8** — replaced the "merge by hand"
  instruction with a call to the new `scripts/inject-governance.py` helper.
  Hand-editing JSON to inject a single key is error-prone; the helper is
  idempotent, preserves all unrelated keys, and respects an existing
  `governance.enabled: false` opt-out.

### Added

- **`scripts/inject-governance.py`** — idempotent helper that merges the
  council governance block into a target project's `.harness/config.json`.
  Exit codes: 0 (written or already correct), 1 (file error), 2 (user opted
  out via `governance.enabled: false`, not overwritten).
- **`README.md` Hook Installation section** — replaced the vague "the kickoff
  skill provides the exact registration command" pointer with the actual JSON
  snippet inline. Also added a "Permissions for running council-kickoff
  against a target project" subsection noting that cross-repo writes require
  Bash permission rules in the target project's `.claude/settings.local.json`.

### Process notes

The bay-o-net dogfood attempt was halted by a sandbox guardrail when the
orchestrator tried to create `.council/` infrastructure in the target repo.
This is itself a v0.1.0 gap: the kickoff SKILL doesn't document the permission
setup required to even *run* the kickoff. The fix in v0.1.1 surfaces that
requirement in the README.

## v0.1.0 — 2026-05-12

Initial release. Ships the complete 8-sprint trine-eval harness build:
11 schemas, 4 council scripts, 4 bash hooks + 4 PowerShell parity hooks,
audit-log rotation, 7 skills (kickoff, autorun, review, retro-mini, retro,
jishuken, detect), 4-stage nemawashi walkthrough, three retrospective
cadences, yokoten propagation, end-to-end S4 and S6 acceptance tests, and
CI matrix on ubuntu-latest + windows-latest. All 8 planned sprints PASS
at 100% weighted score (PR #1, merged at `7681983`).

See `.harness/progress.md` for the full sprint-by-sprint scoreboard.
