# Changelog

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
