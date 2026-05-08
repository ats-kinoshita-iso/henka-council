# Sprint 03 Contract — S1 Kickoff Skill + Plugin Bootstrap

## Scope

Sprint 3 delivers the plugin bootstrap layer and the council-kickoff skill that together constitute the S1 milestone. The six plugin scaffold files (`.claude-plugin/plugin.json`, `.mcp.json`, `.claude/settings.json`, `CLAUDE.md`, `README.md`, and `LICENSE`) establish the plugin's identity, permission model, and user-facing installation surface. The `skills/council-kickoff/SKILL.md` document specifies the procedure by which an invoker bootstraps a complete `.council/` governance baseline in a target project. This sprint is a documentation-of-behavior milestone: the skill is a procedural markdown contract, not executable code — actual `.council/` creation is validated end-to-end in sprint 6 (S4). Two existing files from sprint 2 (`agents/orchestrator.md` and `agents/architect.md`) are validated-in-place to confirm they remain S1-acceptance-grade after the new skill is written. Sprint 1 schemas and Sprint 2 agent contracts are read-only dependencies.

---

## Files in Scope

**New files (7):**
- `.claude-plugin/plugin.json` — plugin identity manifest (name, version, author, license) (§4, Q1/Q2) **[NEW]**
- `.mcp.json` — MCP placeholder, empty/minimal (§4, §3.3 Option A) **[NEW]**
- `.claude/settings.json` — tiered Bash allowlist with `allow`/`ask`/`deny` tiers for git commands (§9.3, v2.1 amendment A11) **[NEW]**
- `CLAUDE.md` — plugin-side CLAUDE.md loaded when council skills run (§4) **[NEW]**
- `README.md` — user-facing intro + install instructions including hook installation self-check note (§4) **[NEW]**
- `LICENSE` — project license file (§4) **[NEW]**
- `skills/council-kickoff/SKILL.md` — kickoff skill procedure; bootstraps complete `.council/` baseline including config, manifest, three jsonl files, standard-work, six directories (including `proposed/archive/`), and `state/effective-autonomy.json`; configures `andon_takt_seconds: 600` and `dynamic_autonomy_thresholds` with `andon_stop_distinct_originators_required: 2`; writes governance signal to `.harness/config.json`; delegates to `/trine-eval:harness-sprint`; surfaces git merge opt-in one-time setup (§8.1, v2.1 amendments A2/A4/A6/A11) **[NEW]**

**Existing files validated in-place (2):**
- `agents/orchestrator.md` — S1 acceptance baseline; must still pass sprint 2's SC-2 frontmatter checks (§7.1) **[VALIDATED-EXISTING]**
- `agents/architect.md` — S1 acceptance baseline; must still pass sprint 2's SC-2 frontmatter checks (§7.2) **[VALIDATED-EXISTING]**

---

## Success Criteria

### Deterministic (weights sum to 60%)

**SC-1 [weight: 8%] — All 7 new files exist at their declared paths**

Input: check that every new file in the "Files in Scope" list is present on disk.

Verification:
```python
python -c "
import pathlib, sys
files = [
    '.claude-plugin/plugin.json',
    '.mcp.json',
    '.claude/settings.json',
    'CLAUDE.md',
    'README.md',
    'LICENSE',
    'skills/council-kickoff/SKILL.md',
]
missing = [f for f in files if not pathlib.Path(f).exists()]
if missing:
    print('MISSING:', missing); sys.exit(1)
print('ALL PRESENT')
"
```

Pass condition: script prints `ALL PRESENT` and exits 0.

Maps to: §4, Q1/Q2, §8.1

---

**SC-2 [weight: 10%] — `.claude-plugin/plugin.json` is valid JSON and contains all required fields with correct values**

Input: parse `.claude-plugin/plugin.json` and check for required fields.

Verification:
```python
python -c "
import json, pathlib, sys
text = pathlib.Path('.claude-plugin/plugin.json').read_text(encoding='utf-8')
try:
    obj = json.loads(text)
except json.JSONDecodeError as e:
    print('FAIL: not valid JSON:', e); sys.exit(1)
errors = []
# name must be exactly 'henkaten-council' (Q1 - repo is henka-council but plugin is henkaten-council)
if obj.get('name') != 'henkaten-council':
    errors.append(f'name must be exactly \"henkaten-council\", got {obj.get(\"name\")!r}')
# version, author, license must be present and non-empty strings
for field in ['version', 'author', 'license']:
    val = obj.get(field)
    if not val or not isinstance(val, str) or not val.strip():
        errors.append(f'field \"{field}\" must be a non-empty string, got {val!r}')
if errors:
    for e in errors: print('FAIL:', e)
    sys.exit(1)
print('ALL PASS')
"
```

Pass condition: script prints `ALL PASS` and exits 0.

Maps to: §4, Q1/Q2

---

**SC-3 [weight: 7%] — `.mcp.json` and `.claude/settings.json` are valid JSON; `.claude/settings.json` has tiered Bash allowlist with `allow`, `ask`, `deny` keys and a `git ` prefix in at least one tier**

Input: parse both JSON files and inspect the settings structure.

Verification:
```python
python -c "
import json, pathlib, sys, re
errors = []

# .mcp.json must parse as JSON
try:
    json.loads(pathlib.Path('.mcp.json').read_text(encoding='utf-8'))
except json.JSONDecodeError as e:
    errors.append(f'.mcp.json: not valid JSON: {e}')

# .claude/settings.json must parse as JSON and have tiered allowlist
try:
    settings = json.loads(pathlib.Path('.claude/settings.json').read_text(encoding='utf-8'))
    perms = settings.get('permissions', settings)  # support both wrapped and flat layout
    # must have all three tier keys
    for tier in ['allow', 'ask', 'deny']:
        if tier not in perms:
            errors.append(f'.claude/settings.json: missing tier \"{tier}\" key in permissions')
    # at least one tier must contain a 'git ' prefixed entry
    all_entries = []
    for tier in ['allow', 'ask', 'deny']:
        val = perms.get(tier, [])
        if isinstance(val, list):
            all_entries.extend(val)
    git_found = any(isinstance(e, str) and e.startswith('git ') for e in all_entries)
    if not git_found:
        errors.append('.claude/settings.json: no entry starting with \"git \" found across all tiers')
except json.JSONDecodeError as e:
    errors.append(f'.claude/settings.json: not valid JSON: {e}')
except Exception as e:
    errors.append(f'.claude/settings.json: unexpected error: {e}')

if errors:
    for e in errors: print('FAIL:', e)
    sys.exit(1)
print('ALL PASS')
"
```

Pass condition: script prints `ALL PASS` and exits 0.

Maps to: §9.3, §3.3, v2.1 amendment A11

---

**SC-4 [weight: 7%] — `LICENSE` is non-empty and contains a recognizable license header; `CLAUDE.md` is substantive (≥500 non-whitespace chars, plugin-relevant content, no stub markers)**

Input: check character counts and content presence for LICENSE and CLAUDE.md.

Verification:
```python
python -c "
import pathlib, sys, re
errors = []

# LICENSE: non-empty, contains at least one recognizable license keyword
lic = pathlib.Path('LICENSE').read_text(encoding='utf-8')
lic_nws = re.sub(r'\s+', '', lic)
if len(lic_nws) < 50:
    errors.append(f'LICENSE: too short ({len(lic_nws)} non-whitespace chars), likely empty or stub')
license_keywords = ['MIT License', 'Apache License', 'GNU General Public License', 'BSD', 'ISC License', 'Permission is hereby granted', 'Apache-2.0', 'MIT']
if not any(kw in lic for kw in license_keywords):
    errors.append('LICENSE: does not contain a recognizable license header (expected one of: MIT, Apache, BSD, ISC, GPL or similar)')

# CLAUDE.md: >=500 non-whitespace chars, no stub markers, plugin-relevant
claude = pathlib.Path('CLAUDE.md').read_text(encoding='utf-8')
claude_nws = re.sub(r'\s+', '', claude)
if len(claude_nws) < 500:
    errors.append(f'CLAUDE.md: too short ({len(claude_nws)} non-whitespace chars, need >= 500); likely a stub')
for marker in ['TODO', 'PLACEHOLDER', 'TBD', '<!-- stub -->']:
    if marker in claude:
        errors.append(f'CLAUDE.md: contains stub marker \"{marker}\"')
# Must contain council-relevant terms
if not any(kw in claude for kw in ['council', 'henkaten', 'skill', 'henka']):
    errors.append('CLAUDE.md: does not appear to be plugin-relevant (missing council/henkaten/skill/henka keywords)')

if errors:
    for e in errors: print('FAIL:', e)
    sys.exit(1)
print('ALL PASS')
"
```

Pass condition: script prints `ALL PASS` and exits 0.

Maps to: §4

---

**SC-5 [weight: 7%] — `README.md` is ≥800 characters, contains install instructions, and mentions hook installation self-check**

Input: check README.md for minimum length and required content.

Verification:
```python
python -c "
import pathlib, sys, re
errors = []
readme = pathlib.Path('README.md').read_text(encoding='utf-8')
if len(readme) < 800:
    errors.append(f'README.md: too short ({len(readme)} chars, need >= 800)')
# Must mention install instructions
if not re.search(r'install', readme, re.IGNORECASE):
    errors.append('README.md: does not contain install instructions (missing \"install\" keyword)')
# Must mention hook installation self-check (§4 / §13 risk note about hook installation)
if not re.search(r'hook', readme, re.IGNORECASE):
    errors.append('README.md: does not mention hooks (required: hook installation self-check note per §4)')
# Must mention /council-kickoff or council-kickoff invocation
if not re.search(r'council.kickoff', readme, re.IGNORECASE):
    errors.append('README.md: does not mention council-kickoff (should tell user how to invoke the kickoff skill)')
if errors:
    for e in errors: print('FAIL:', e)
    sys.exit(1)
print('ALL PASS')
"
```

Pass condition: script prints `ALL PASS` and exits 0.

Maps to: §4, §13

---

**SC-6 [weight: 12%] — `skills/council-kickoff/SKILL.md` has valid YAML frontmatter with a `description` field, is ≥2000 characters, and mentions every required `.council/` artifact by name**

Input: parse the YAML frontmatter of the skill file and scan for required artifact mentions.

Verification:
```python
python -c "
import pathlib, sys, re
errors = []
text = pathlib.Path('skills/council-kickoff/SKILL.md').read_text(encoding='utf-8')

# Must be >= 2000 chars total
if len(text) < 2000:
    errors.append(f'skills/council-kickoff/SKILL.md: too short ({len(text)} chars, need >= 2000)')

# Must have YAML frontmatter with description field
m = re.match(r'^---\s*\n(.*?)\n---', text, re.DOTALL)
if not m:
    errors.append('skills/council-kickoff/SKILL.md: no YAML frontmatter found (expected --- delimiters)')
else:
    fm = m.group(1)
    desc_line = next((l for l in fm.splitlines() if 'description' in l.lower()), '')
    if not desc_line:
        errors.append('skills/council-kickoff/SKILL.md: YAML frontmatter missing \"description\" field')

# Must mention all required .council/ artifacts by name (§8.1 step 3, 5)
required_artifacts = [
    'config.json',
    'manifest.json',
    'henka-register.jsonl',
    'decision-log.jsonl',
    'audit-log.jsonl',
    'standard-work.json',
    'proposed/archive',
    'state/effective-autonomy.json',
]
for artifact in required_artifacts:
    if artifact not in text:
        errors.append(f'skills/council-kickoff/SKILL.md: missing required artifact mention: {artifact!r}')

# Must mention takt and originators settings with correct values (v2.1 A2/A6)
if 'andon_takt_seconds: 600' not in text:
    errors.append('skills/council-kickoff/SKILL.md: missing or wrong value for andon_takt_seconds (must document 600, not 300 or other)')
if 'andon_stop_distinct_originators_required: 2' not in text:
    errors.append('skills/council-kickoff/SKILL.md: missing or wrong value for andon_stop_distinct_originators_required (must document 2)')

# Must mention trine-eval delegation as a slash-command (v2.1 A6)
if not re.search(r'/trine-eval:', text, re.IGNORECASE):
    errors.append('skills/council-kickoff/SKILL.md: does not mention /trine-eval: delegation (required by §8.1 step 6; prose mention without slash-command syntax is not sufficient)')

# Must mention git merge opt-in (v2.1 A11)
if not re.search(r'git merge|merge.*opt.in|ask.*tier', text, re.IGNORECASE):
    errors.append('skills/council-kickoff/SKILL.md: does not mention git merge opt-in setup (required by v2.1 A11)')

if errors:
    for e in errors: print('FAIL:', e)
    sys.exit(1)
print('ALL PASS')
"
```

Pass condition: script prints `ALL PASS` and exits 0.

Maps to: §8.1, v2.1 amendments A2/A4/A6/A11

---

**SC-7 [weight: 6%] — Cross-sprint regression: `agents/orchestrator.md` and `agents/architect.md` still pass sprint 2's SC-2 frontmatter checks**

Input: re-run a subset of the sprint 2 SC-2 verification against the two S1-baseline agent files to confirm they have not been regressed.

Verification:
```python
python -c "
import pathlib, sys, re

EXPECTED = {
    'agents/orchestrator.md': {'tools': {'Read','Glob','Grep','Bash','Write','Task'}, 'context': 'inherit', 'level': '4'},
    'agents/architect.md':    {'tools': {'Read','Glob','Grep'}, 'context': 'fork', 'level': '2'},
}

errors = []
for path, spec in EXPECTED.items():
    text = pathlib.Path(path).read_text(encoding='utf-8')
    m = re.match(r'^---\s*\n(.*?)\n---', text, re.DOTALL)
    if not m:
        errors.append(f'{path}: no YAML frontmatter found'); continue
    fm = m.group(1)
    lines = fm.splitlines()
    # Support both inline YAML (tools: [Read, Bash]) and block-sequence (tools:\n  - Read\n  - Bash)
    tools_block = []
    in_tools = False
    for l in lines:
        if re.match(r'\s*tools\s*:', l, re.IGNORECASE):
            tools_block.append(l)
            in_tools = True
        elif in_tools:
            if re.match(r'\s{2,}', l):  # continuation of block sequence
                tools_block.append(l)
            else:
                break
    tools_text = '\n'.join(tools_block)
    declared = set(re.findall(r'Read|Glob|Grep|Bash|Write|Task', tools_text))
    if declared != spec['tools']:
        errors.append(f'{path}: tools={declared}, expected={spec[\"tools\"]}')
    ctx_line = next((l for l in fm.splitlines() if 'context' in l.lower()), '')
    if spec['context'] not in ctx_line:
        errors.append(f'{path}: context line does not contain \"{spec[\"context\"]}\" (got: {ctx_line!r})')
    lvl_line = next((l for l in fm.splitlines() if 'level' in l.lower()), '')
    if not re.search(r'level:\s*' + re.escape(spec['level']) + r'\b', lvl_line):
        errors.append(f'{path}: level line does not declare level {spec[\"level\"]} exactly (got: {lvl_line!r})')

if errors:
    for e in errors: print('FAIL:', e)
    sys.exit(1)
print('ALL PASS')
"
```

Pass condition: script prints `ALL PASS` and exits 0.

Maps to: §7.1, §7.2 (sprint 2 regression gate)

---

**SC-8 [weight: 3%] — No new file contains stub markers or is content-empty**

Input: check all 7 new files for stub markers and minimum content.

Verification:
```python
python -c "
import pathlib, sys, re
files = [
    ('.claude-plugin/plugin.json', 2),
    ('.mcp.json', 2),
    ('.claude/settings.json', 2),
    ('CLAUDE.md', 200),
    ('README.md', 400),
    ('LICENSE', 50),
    ('skills/council-kickoff/SKILL.md', 500),
]
errors = []
stub_markers = ['TODO', 'PLACEHOLDER', 'TBD', '<!-- stub -->']
for path, min_nws in files:
    text = pathlib.Path(path).read_text(encoding='utf-8')
    nws = re.sub(r'\s+', '', text)
    if len(nws) < min_nws:
        errors.append(f'{path}: too short ({len(nws)} non-whitespace chars, need >= {min_nws})')
    # Only check stub markers in markdown files
    if path.endswith('.md'):
        for marker in stub_markers:
            if marker in text:
                errors.append(f'{path}: contains stub marker \"{marker}\"')
if errors:
    for e in errors: print('FAIL:', e)
    sys.exit(1)
print('ALL PASS')
"
```

Pass condition: script prints `ALL PASS` and exits 0.

Maps to: §4

---

### LLM-as-judge (weights sum to 40%)

**SC-9 [weight: 22%] — `skills/council-kickoff/SKILL.md` correctly and completely documents the kickoff procedure including all v2.1 amendments**

The judge reads `skills/council-kickoff/SKILL.md` and scores against the following rubric dimensions:

1. **Pre-flight checks** (§8.1 step 1): The skill describes a check for existing `.council/` state and offers a re-bootstrap option rather than silently overwriting. The check covers both the target project's `.council/` and the existence of `.harness/` (or instructs the user to run trine-eval kickoff first).

2. **Core state file creation** (§8.1 steps 3–5): The skill documents creation of all required `.council/` files in order: `config.json` (with `andon_takt_seconds: 600` and `dynamic_autonomy_thresholds` containing `andon_stop_distinct_originators_required: 2`), `council-manifest.json` (with `council_id: "COUNCIL-0001"` and a list of core agents), the three append-only jsonl files (`henka-register.jsonl`, `decision-log.jsonl`, `audit-log.jsonl`), and `standard-work.json`. Idempotency guards (skip-if-already-exists checks) are present for the jsonl files.

3. **Directory structure and archived proposals** (§8.1 step 5, v2.1 amendment A4): The skill explicitly names the six directories to create: `course-corrections/`, `proposed/`, `proposed/archive/`, `retrospectives/`, `sessions/`, and `state/`. The `proposed/archive/` path appears explicitly (not just `proposed/` alone) — this is the v2.1 A4 requirement that ratified position papers are archived rather than deleted so decision-log paths remain resolvable. The `state/` directory must also be named explicitly because it is the parent path for `state/effective-autonomy.json` (dimension 4).

4. **`state/effective-autonomy.json` initial write** (§8.1 step 5, §11.11, R10/Q20): The skill documents writing `state/effective-autonomy.json` with initial values `{level: 4, last_change: <now>, reason: "initial", restored_when: null, trigger_history: []}`. The level-4 default is stated explicitly and `trigger_history` is initialized as an empty array (matching the sprint 1 `effective-autonomy.schema.json`).

5. **Governance signal and trine-eval delegation** (§8.1 steps 6/6B, v2.1 amendment A6): The skill documents writing the governance signal to `.harness/config.json` with the structure `{governance: {enabled: true, plugin: "henkaten-council", council_state_path: ".council/", review_frequency: "every-sprint"}}`. The delegation to `/trine-eval:harness-sprint` (or `/trine-eval:harness-kickoff` for initial kickoff) is documented as a `Task` call, not a direct invocation.

6. **Git merge opt-in surface** (§9.3, v2.1 amendment A11): The skill surfaces the one-time git merge setup step — explaining that `git merge` is in the `deny` tier by default and the user must move it to the `ask` tier in `.claude/settings.json` if they want the orchestrator to propose it. The skill presents this as a user choice with clear instructions, not an automatic change.

Score: PASS if ≥5 of 6 dimensions are fully satisfied; PARTIAL (50% weight credit) if 3–4 dimensions satisfied; FAIL if ≤2 dimensions satisfied.

Maps to: §8.1, v2.1 amendments A2/A4/A6/A11, §9.3

---

**SC-10 [weight: 10%] — `.claude/settings.json` tier semantics reflect §9.3's intent**

The judge reads `.claude/settings.json` and scores against the following rubric dimensions:

1. **`allow` tier: read-only git operations** (§9.3): The `allow` tier contains only read-only git operations. Specifically, commands like `git status`, `git diff`, `git log`, `git show`, `git branch -l` (listing), and `git ls-files` should appear. No write or mutation operations appear in `allow`.

2. **`ask` tier: branch-local mutation operations** (§9.3): The `ask` tier contains branch-local git write operations that require user confirmation. Expected entries include `git add`, `git commit`, `git checkout -b` (branch creation), `git tag`, `git stash`. These are reversible within the local branch.

3. **`deny` tier: destructive or cross-repo operations** (§9.3, §2.4.2): The `deny` tier contains irreversible or high-blast-radius operations. Specifically, `git push` (with `*` wildcard or explicit remote), `git push --force`, `git reset --hard`, `git rebase -i`, and `git merge` must appear in `deny`. All entries in `deny` correspond to operations classified as `irreversible` in the reversibility table (§2.4.2).

Score: PASS if all 3 dimensions are fully satisfied; PARTIAL (50% weight credit) if 2 dimensions satisfied; FAIL if ≤1 dimension satisfied.

Maps to: §9.3, §2.4.2, v2.1 amendment A11

---

**SC-11 [weight: 8%] — `README.md` tells the user the right minimum steps to install the plugin and run `/council-kickoff`, including the hook self-check note**

The judge reads `README.md` and scores against the following rubric dimensions:

1. **Install steps** (§4): The README provides a clear step-by-step or equivalent install procedure. At minimum, it covers: (a) cloning or obtaining the plugin, (b) how the plugin is registered in Claude Code (e.g., marketplace or direct path), and (c) any prerequisite (e.g., trine-eval ≥ 0.3.0).

2. **Invocation instruction** (§8.1): The README tells the user the exact command to invoke the kickoff skill (e.g., `/henka-council:council-kickoff` or equivalent slash-command syntax).

3. **Hook installation self-check** (§4, §13 risk table): The README contains a note about hook installation — explaining that the hooks in `hooks/` must be registered/enabled, and that `/council-kickoff` verifies hook presence and warns if hooks are missing. The note should reference both the hook files and the self-check behavior.

Score: PASS if all 3 dimensions are fully satisfied; PARTIAL (50% weight credit) if 2 dimensions satisfied; FAIL if ≤1 dimension satisfied.

Maps to: §4, §8.1, §13

---

## Should-NOT Criteria (Gate — Any Failure Blocks the Sprint)

**Gate 1 — `.claude-plugin/plugin.json` `name` must be exactly `henkaten-council`**

The plugin name must be `henkaten-council` (with "ten") per Q1. The on-disk directory is `henka-council` (without "ten"); this is intentional and must not cause the name field to be set incorrectly.

Verification:
```python
python -c "
import json, pathlib, sys
try:
    obj = json.loads(pathlib.Path('.claude-plugin/plugin.json').read_text(encoding='utf-8'))
except Exception as e:
    print('GATE FAIL: cannot parse plugin.json:', e); sys.exit(1)
name = obj.get('name', '')
if name != 'henkaten-council':
    print(f'GATE FAIL: plugin.json name is {name!r}, must be exactly \"henkaten-council\" (Q1: repo=henka-council, plugin=henkaten-council)'); sys.exit(1)
print('GATE PASS')
"
```

---

**Gate 2 — `.claude/settings.json` `allow` tier must NOT contain `git push --force` or `rm -rf`**

Destructive operations must never appear in the `allow` tier — they would bypass the user approval gate and silently execute.

Verification:
```python
python -c "
import json, pathlib, sys, re
try:
    settings = json.loads(pathlib.Path('.claude/settings.json').read_text(encoding='utf-8'))
    perms = settings.get('permissions', settings)
    allow_entries = perms.get('allow', [])
except Exception as e:
    print('GATE FAIL: cannot parse .claude/settings.json:', e); sys.exit(1)
errors = []
for entry in allow_entries:
    if isinstance(entry, str):
        if 'push --force' in entry or 'push --force' in entry.replace('-f', '--force'):
            errors.append(f'GATE FAIL: \"allow\" tier contains dangerous entry: {entry!r}')
        if 'rm -rf' in entry or 'rm -fr' in entry:
            errors.append(f'GATE FAIL: \"allow\" tier contains dangerous entry: {entry!r}')
        if re.search(r'git push\b', entry):
            errors.append(f'GATE FAIL: \"allow\" tier contains git push (must be in deny): {entry!r}')
if errors:
    for e in errors: print(e)
    sys.exit(1)
print('GATE PASS')
"
```

---

**Gate 3 — `skills/council-kickoff/SKILL.md` frontmatter must contain a `description` field**

Claude Code skill discovery reads the `description` field from SKILL.md frontmatter to surface the skill to users. A missing or empty `description` means the skill cannot be discovered or invoked.

Verification:
```python
python -c "
import pathlib, sys, re
text = pathlib.Path('skills/council-kickoff/SKILL.md').read_text(encoding='utf-8')
m = re.match(r'^---\s*\n(.*?)\n---', text, re.DOTALL)
if not m:
    print('GATE FAIL: no YAML frontmatter found in skills/council-kickoff/SKILL.md'); sys.exit(1)
fm = m.group(1)
desc_line = next((l for l in fm.splitlines() if re.match(r'\s*description\s*:', l)), '')
if not desc_line:
    print('GATE FAIL: no \"description\" key in SKILL.md frontmatter'); sys.exit(1)
desc_val = re.sub(r'^\s*description\s*:\s*', '', desc_line).strip()
if not desc_val:
    print('GATE FAIL: \"description\" key in SKILL.md frontmatter is empty'); sys.exit(1)
print('GATE PASS')
"
```

---

**Gate 4 — The kickoff skill must NOT actually create `.council/` (sprint 3 ships the skill as a document; end-to-end execution is sprint 6)**

The SKILL.md file must not contain shell commands, inline `Bash` blocks, or embedded scripts that would actually write files to disk when the markdown is read. It is a procedural contract, not an executable script. Inline code fences showing example JSON structures are acceptable; runnable shell invocations are not.

Verification (absence check — manual review supported by heuristic):
```python
python -c "
import pathlib, sys, re
text = pathlib.Path('skills/council-kickoff/SKILL.md').read_text(encoding='utf-8')
errors = []
# Flag bash/shell code fences that contain write operations
# A code fence labeled 'bash' or 'sh' containing 'mkdir', 'touch', '>' operators suggests actual execution
bash_fences = re.findall(r'\`\`\`(?:bash|sh|shell)\n(.*?)\`\`\`', text, re.DOTALL)
for fence in bash_fences:
    if re.search(r'\bmkdir\b|\btouch\b|\btee\b', fence):
        errors.append('GATE FAIL: SKILL.md contains a bash/sh code fence with file-creation command (mkdir/touch/tee); skill must be a procedural document, not an executable script')
        break
# The skill must not itself delegate to itself (recursive skill call)
if re.search(r'/council-kickoff.*Task|Task.*council-kickoff', text, re.IGNORECASE):
    errors.append('GATE FAIL: SKILL.md appears to delegate to itself recursively')
if errors:
    for e in errors: print(e)
    sys.exit(1)
print('GATE PASS')
"
```

---

**Gate 5 — No files created outside the 7 declared new files and the 2 validated-existing files**

Sprint 3 must not create schema files, append scripts, hook files, additional templates, additional agent files, or any files under `.harness/` (except as part of the governance signal that SKILL.md documents writing — but that is a runtime operation, not a generator-created file).

Verification:
```python
python -c "
import subprocess, sys

ALLOWED_NEW = {
    '.claude-plugin/plugin.json',
    '.mcp.json',
    '.claude/settings.json',
    'CLAUDE.md',
    'README.md',
    'LICENSE',
    'skills/council-kickoff/SKILL.md',
}
ALLOWED_EXISTING = {
    'agents/orchestrator.md',
    'agents/architect.md',
}
ALLOWED_ALL = ALLOWED_NEW | ALLOWED_EXISTING

result = subprocess.run(
    ['git', 'diff', '--name-only', 'HEAD'],
    capture_output=True, text=True
)
if result.returncode != 0:
    result = subprocess.run(
        ['git', 'diff', '--name-only', '--cached',
         '4b825dc642cb6eb9a060e54bf8d69288fbee4904'],
        capture_output=True, text=True
    )
changed = [l.strip() for l in result.stdout.splitlines() if l.strip()]
errors = []
for f in changed:
    if f not in ALLOWED_ALL:
        if f.startswith('.harness/'):
            errors.append(f'GATE FAIL: .harness/ file modified (runtime-only): {f!r}')
        else:
            errors.append(f'GATE FAIL: unexpected file outside sprint-3 scope: {f!r}')
if errors:
    for e in errors: print(e)
    sys.exit(1)
print('GATE PASS')
"
```

Pass condition: script prints `GATE PASS` and exits 0. The script checks git-tracked changes against HEAD; untracked files not in the declared scope are caught by the evaluator's file-existence pass.

---

**Gate 6 — `skills/council-kickoff/SKILL.md` must NOT delegate to itself or invoke another skill recursively beyond the documented `/trine-eval:harness-sprint` handoff**

The skill may document delegation to `/trine-eval:harness-kickoff` (for initial planning) and `/trine-eval:harness-sprint` (for sprint execution). It must not reference `/henka-council:council-kickoff` as a `Task` target (self-recursion) or any other council skill (e.g. `/henka-council:council-autorun`) as a direct `Task` call.

Verification:
```python
python -c "
import pathlib, sys, re
text = pathlib.Path('skills/council-kickoff/SKILL.md').read_text(encoding='utf-8')
errors = []
# Self-reference as a Task target
if re.search(r'Task.*?council-kickoff|council-kickoff.*?Task', text):
    errors.append('GATE FAIL: SKILL.md appears to invoke /council-kickoff as a Task target (self-recursion)')
# Reference to other council skills as Task targets (not just prose mentions)
forbidden_skill_calls = ['council-autorun', 'council-review', 'council-retro', 'council-detect', 'council-jishuken']
for skill in forbidden_skill_calls:
    # Allow prose mentions; only flag if the skill name appears adjacent to 'Task' dispatch syntax
    if re.search(r'Task.*?' + skill + r'|' + skill + r'.*?Task', text):
        errors.append(f'GATE FAIL: SKILL.md appears to dispatch to /{skill} as a Task (skills must not call other skills directly)')
if errors:
    for e in errors: print(e)
    sys.exit(1)
print('GATE PASS')
"
```

---

## Reference Solutions

Reference content for **SC-9** (highest-weighted LLM-judge criterion) — expected step structure for `skills/council-kickoff/SKILL.md`. The Generator should produce a skill that walks through approximately this sequence:

```
## Procedure

### Step 1 — Pre-Flight Checks
- If `.council/` already exists: present re-bootstrap option; require user confirmation before overwriting.
- If `.harness/` does not exist: instruct user to run `/trine-eval:harness-kickoff` first (or offer to delegate immediately).
- Gather project context: project name, project type, council agents to activate.

### Step 2 — Create `.council/config.json`
Write config with:
  - project_type: <detected>
  - council_agents: ["orchestrator", "architect", "scope-guardian", "henkaten-detector"]
  - autonomy_levels: {default: 4}
  - review_frequency: "every-sprint"
  - henkaten_taxonomy_version: "2.0"
  - andon_takt_seconds: 600              # v2.1 amendment A6 (raised from 300)
  - dynamic_autonomy_thresholds:
      andon_stop_distinct_originators_required: 2   # v2.1 amendment A2
      andon_stop_consecutive_count: 3

### Step 3 — Create `.council/council-manifest.json`
Write manifest with:
  - council_id: "COUNCIL-0001"
  - agents: [list of 4 core agents with roles]
  - trigger_type: "kickoff"
  - status: "assembled"

### Step 4 — Initialize Append-Only Logs (idempotent)
- If `henka-register.jsonl` does not exist: create empty file.
- If `decision-log.jsonl` does not exist: create with first entry (DEC-0001, kickoff decision).
- If `audit-log.jsonl` does not exist: create empty file.

### Step 5 — Write `.council/standard-work.json` (seed)
Write initial standard-work seed based on project type.

### Step 6 — Create Directories
Create if not exist:
  - `.council/course-corrections/`
  - `.council/proposed/`
  - `.council/proposed/archive/`    # v2.1 amendment A4: ratified position papers archived here
  - `.council/retrospectives/`
  - `.council/sessions/`
  - `.council/state/`

### Step 7 — Write `.council/state/effective-autonomy.json`
Write initial state:
  {
    "level": 4,
    "last_change": "<ISO-8601-now>",
    "reason": "initial",
    "restored_when": null,
    "trigger_history": []
  }

### Step 8 — Write Governance Signal to `.harness/config.json`
Append or merge the governance block:
  {
    "governance": {
      "enabled": true,
      "plugin": "henkaten-council",
      "council_state_path": ".council/",
      "review_frequency": "every-sprint"
    }
  }

### Step 9 — Delegate to trine-eval
Call `/trine-eval:harness-kickoff` via Task to produce `.harness/spec.md`,
`.harness/features.json`, and `.harness/sprints.json` if not already present.
(Or `/trine-eval:harness-sprint NN` for per-sprint loop invocation when the harness
baseline already exists and a specific sprint number is being evaluated.)

### Step 10 — Surface Git Merge Opt-In (v2.1 amendment A11)
Display one-time setup note:
  "git merge is in the deny tier by default. If you want the orchestrator to
   propose merges on sprint PASS, move 'git merge *' from deny to ask in
   .claude/settings.json. This is a one-time per-project setup step."
Offer to show the exact line to edit.

### Step 11 — Confirm Baseline
Present summary of all created files. Offer to run `/council-autorun` to start the sprint loop.
```

---

## Out of Scope

- **Actually creating `.council/` on disk** — the kickoff skill is a procedural document this sprint; end-to-end execution is validated in sprint 6 (S4 fan-out fixture test).
- **Hooks** (`hooks/*.sh`, `hooks/win/*.ps1`) — sprint 5 (S3) deliverables.
- **Append scripts** (`scripts/append-henka.py`, `scripts/append-decision.py`, `scripts/append-audit.py`, `scripts/compute-evidence-class.py`, `scripts/update-effective-autonomy.py`) — sprint 4 (S2) deliverables.
- **`council-autorun`, `council-review`, `council-retro-mini`, `council-retro`, `council-jishuken`, `council-detect` skills** — sprints 6/7/8 (S4–S6) deliverables.
- **`scripts/run-verification.py`** — sprint 6 (S4) deliverable.
- **Additional template files** (`retrospective-mini.md`, `retrospective-pdca.md`, `jishuken-workshop.md`) — sprint 8 (S6) deliverables.
- **The `trine-eval` harness kickoff implementation** — trine-eval is a stable dependency; the skill references it via slash-command delegation, not implementation.
- **`tests/fixtures/dummy-project/`** — sprint 6 (S4) deliverable.
- **Any new agent files** — `agents/scope-guardian.md`, `agents/henkaten-detector.md`, `agents/retrospective.md` are sprint 4 (S2) deliverables. Sprint 3 only validates the two existing S1-baseline agents.
- **CI configuration** — sprint 5 (S3) deliverable.

---

## Technical Notes

**Plugin name is `henkaten-council` (not `henka-council`):** Per Q1, the repo directory is `henka-council` but the plugin's `name` field in `plugin.json` is `henkaten-council` (with "ten"). This is intentional. Do not treat the mismatch as a typo. Gate 1 enforces this exactly.

**Skill frontmatter `description` field:** Claude Code uses the YAML frontmatter `description` field of SKILL.md files to surface skills in the skill picker and `/` command completion. The description should begin with a use-case phrase like "Use this skill to bootstrap a new henka-council governance baseline in a trine-eval project." Gate 3 enforces presence; SC-9 evaluates phrasing quality.

**SKILL.md is a procedural document, not an executable script:** Sprint 3 ships the kickoff skill as a markdown contract describing what the invoker (Claude Code agent) must do. Code fences showing example JSON file contents are appropriate. Code fences labeled `bash`/`sh` containing file-creation commands (`mkdir`, `touch`, `tee`, `>`) would imply the file is a shell script, which is incorrect at this sprint stage. Gate 4 heuristically checks for this.

**`.claude/settings.json` tier semantics (§9.3):** `allow` = read-only git inspection (`git status`, `git diff`, `git log`, `git show`, `git branch -l`, `git ls-files`). `ask` = branch-local reversible mutations (`git add *`, `git commit -m *`, `git checkout -b *`, `git tag *`, `git stash *`). `deny` = destructive or cross-repo operations (`git push *`, `git push --force *`, `git reset --hard *`, `git rebase -i *`, `git merge *`). Note that `git merge` is in `deny` by default per v2.1 amendment A11 — users must explicitly move it to `ask` if they want the orchestrator to propose merges on sprint PASS.

**`.mcp.json` is a placeholder:** Per §3.3 Option A (drop the MCP server, use direct Bash with permission rules), the `.mcp.json` file is an empty or minimal JSON object `{}`. It exists as a placeholder to preserve the path to Option B (MCP-based git server) without activating it.

**Six directories including `proposed/archive/`:** The `proposed/archive/` path is a v2.1 amendment A4 requirement — ratified position papers are moved here after ratification so the `decision-log.jsonl` `nemawashi_walkthrough_version` path references remain resolvable indefinitely. Both `proposed/` and `proposed/archive/` must be named explicitly in the skill.

**Cross-reference syntax:** The skill file may reference agents and instructions using path-based markdown links to `agents/<name>.md` and `instructions/<name>.md` in the body. These references are prose mentions within the S3 deliverable and do not violate any future-sprint reference prohibition.

**SC-7 YAML tools parsing (both inline and block-sequence supported):** SC-7 now parses the `tools:` block spanning multiple indented lines to handle both inline format (`tools: [Read, Bash]`) and block-sequence format (`tools:\n  - Read\n  - Bash`). The agent files themselves (`agents/orchestrator.md`, `agents/architect.md`) were created in sprint 2 and must not be modified in sprint 3 — their existing format is read-only.

**Sprint 2 regression:** `agents/orchestrator.md` and `agents/architect.md` must not be modified during sprint 3 implementation. SC-7 verifies their frontmatter is intact. If the kickoff skill needs to reference these agents, it does so via prose or path mentions in the SKILL.md body, not by editing the agent files themselves.

---

**Task taxonomy handoff:** Once this contract is approved by the Evaluator, a sibling `.harness/contracts/sprint-03.tasks.json` is emitted (guarded by `config.taxonomy.emit_tasks_json`, default `true`). It contains one JSON entry per criterion above — both Success Criteria and Should-NOT gates — with stable `task_id`s, `grader_type`, `weight`, `is_gate`, `verification_command`, and `rubric_dimension`. Downstream sprints (regression gate, Batch API, transcript capture, adversarial hygiene) consume that JSON; this markdown contract remains the human-readable source of truth.

## Evaluator Review

**Status: APPROVED**

### Summary
All five round-1 blockers and majors are confirmed fixed in the file. Weights sum correctly (deterministic 60%, LLM-judge 40%, total 100%). Two cosmetic "five" vs "six" inconsistencies remain in non-normative prose only (lines 18 and 752); the normative rubric dimension SC-9 dim 3 correctly states "six". No new verification issues found.

### Blockers (must fix before approval)
- None.

### Major issues
- None.

### Minor / nice-to-have
- Line 18 (Files in Scope description) still reads "five directories (including `proposed/archive/`)" — SC-9 dim 3 says six. Non-normative prose, no criterion reads from this line, but it is misleading. Suggest updating to "six directories" in a follow-up pass.
- Line 752 (Technical Notes) still uses the heading "**Five directories** including `proposed/archive/`:" — same residual from B1 partial fix. Same recommendation: update to "Six directories" for consistency. Neither instance affects gradeability.
