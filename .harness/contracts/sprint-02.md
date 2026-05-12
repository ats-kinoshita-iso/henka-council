# Sprint 02 Contract — D2 Agent Contracts

## Scope

Sprint 2 delivers the complete agent contract layer for the henka-council plugin: seven agent markdown files, five behavioral instruction files, and two output templates — 14 markdown files in total. These are static text artifacts that define agent roles, tools, autonomy levels, and behavioral obligations; no runtime code is produced. Every downstream sprint (S1 through S6) depends on these contracts as the authoritative specification of what each agent may and must do. The schemas produced in Sprint 1 are read-only dependencies.

---

## Files in Scope

**Agent files (7):**
- `agents/orchestrator.md` — Level 4, tools: Read/Glob/Grep/Bash/Write/Task, context: inherit (§7.1)
- `agents/architect.md` — Level 2, tools: Read/Glob/Grep, context: fork (§7.2)
- `agents/scope-guardian.md` — Level 2, tools: Read/Glob/Grep, context: fork (§7.3)
- `agents/henkaten-detector.md` — Level 1, tools: Read/Glob/Grep, context: fork (§7.4, §6.7, v2.1 amendment A3)
- `agents/retrospective.md` — Level 2, tools: Read/Glob/Grep, context: fork; three modes mini/pdca/jishuken (§7.5)
- `agents/qa-regression.md` — Level 2, tools: Read/Glob/Grep, context: fork; status: proposed (§7.6, Q4)
- `agents/rag-source.md` — Level 1, tools: Read/Glob/Grep, context: fork; status: proposed (§7.7, Q4)

**Instruction files (5):**
- `instructions/controlled-artifacts.md` (§4)
- `instructions/evidence-first.md` — verification syntax allowlist, evidence_class, confidence required (§4, R4, v2.1 amendment A1)
- `instructions/human-approval.md` — nemawashi walkthrough for major decisions (§4, R5)
- `instructions/andon-protocol.md` — thank-the-puller, alert vs stop, swarming, Rule 4 carve-out (§4, R2/R3, v2.1 amendment A10)
- `instructions/prompt-injection-defense.md` (§4)

**Template files (2):**
- `templates/dispatch-envelope.md` — single source of truth for all agent dispatch; references andon-protocol.md and evidence-first.md (§9.6)
- `templates/nemawashi-position-paper.md` — four-stage walkthrough structure (§8.2 Step 1D, R5)

---

## Success Criteria

### Deterministic (weights sum to 61%)

**SC-1 [weight: 12%] — All 14 files exist at their declared paths**

Input: check that every file in the "Files in Scope" list is present on disk.

Verification:
```python
python -c "
import pathlib, sys
files = [
    'agents/orchestrator.md',
    'agents/architect.md',
    'agents/scope-guardian.md',
    'agents/henkaten-detector.md',
    'agents/retrospective.md',
    'agents/qa-regression.md',
    'agents/rag-source.md',
    'instructions/controlled-artifacts.md',
    'instructions/evidence-first.md',
    'instructions/human-approval.md',
    'instructions/andon-protocol.md',
    'instructions/prompt-injection-defense.md',
    'templates/dispatch-envelope.md',
    'templates/nemawashi-position-paper.md',
]
missing = [f for f in files if not pathlib.Path(f).exists()]
if missing:
    print('MISSING:', missing); sys.exit(1)
print('ALL PRESENT')
"
```

Pass condition: script prints `ALL PRESENT` and exits 0. Any missing file causes a non-zero exit listing the missing paths.

Maps to: SC-D2-1 partial, SC-D2-5, SC-D2-6 (§5)

---

**SC-2 [weight: 12%] — Every agent file has valid YAML frontmatter with required keys, correct tool declarations, and correct context values**

Input: parse the YAML frontmatter (between `---` delimiters) of each of the 7 agent files.

Verification:
```python
python -c "
import pathlib, sys, re

EXPECTED = {
    'agents/orchestrator.md':      {'tools': {'Read','Glob','Grep','Bash','Write','Task'}, 'context': 'inherit', 'level': '4'},
    'agents/architect.md':         {'tools': {'Read','Glob','Grep'}, 'context': 'fork', 'level': '2'},
    'agents/scope-guardian.md':    {'tools': {'Read','Glob','Grep'}, 'context': 'fork', 'level': '2'},
    'agents/henkaten-detector.md': {'tools': {'Read','Glob','Grep'}, 'context': 'fork', 'level': '1'},
    'agents/retrospective.md':     {'tools': {'Read','Glob','Grep'}, 'context': 'fork', 'level': '2'},
    'agents/qa-regression.md':     {'tools': {'Read','Glob','Grep'}, 'context': 'fork', 'level': '2'},
    'agents/rag-source.md':        {'tools': {'Read','Glob','Grep'}, 'context': 'fork', 'level': '1'},
}

errors = []
for path, spec in EXPECTED.items():
    text = pathlib.Path(path).read_text(encoding='utf-8')
    # Extract frontmatter block
    m = re.match(r'^---\s*\n(.*?)\n---', text, re.DOTALL)
    if not m:
        errors.append(f'{path}: no YAML frontmatter found (expected --- delimiters)')
        continue
    fm = m.group(1)
    # Check tools (any line containing the tool names)
    tools_line = next((l for l in fm.splitlines() if 'tools' in l.lower()), '')
    declared = set(re.findall(r'Read|Glob|Grep|Bash|Write|Task', tools_line))
    if declared != spec['tools']:
        errors.append(f'{path}: tools={declared}, expected={spec[\"tools\"]}')
    # Check context
    ctx_line = next((l for l in fm.splitlines() if 'context' in l.lower()), '')
    if spec['context'] not in ctx_line:
        errors.append(f'{path}: context line does not contain \"{spec[\"context\"]}\" (got: {ctx_line!r})')
    # Check level (word-boundary match to avoid '1' matching '12')
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

Maps to: SC-D2-1 (§5, §7, §9.1, §9.2)

---

**SC-3 [weight: 8%] — Every agent file body references both `@instructions/andon-protocol.md` and `@instructions/evidence-first.md`**

Input: scan each of the 7 agent files for the two required cross-reference strings.

Verification:
```python
python -c "
import pathlib, sys
agents = [
    'agents/orchestrator.md',
    'agents/architect.md',
    'agents/scope-guardian.md',
    'agents/henkaten-detector.md',
    'agents/retrospective.md',
    'agents/qa-regression.md',
    'agents/rag-source.md',
]
errors = []
for path in agents:
    text = pathlib.Path(path).read_text(encoding='utf-8')
    if '@instructions/andon-protocol.md' not in text:
        errors.append(f'{path}: missing @instructions/andon-protocol.md reference')
    if '@instructions/evidence-first.md' not in text:
        errors.append(f'{path}: missing @instructions/evidence-first.md reference')
if errors:
    for e in errors: print('FAIL:', e)
    sys.exit(1)
print('ALL PASS')
"
```

Pass condition: script prints `ALL PASS` and exits 0.

Maps to: SC-D2-2 (§5, §7.0)

---

**SC-4 [weight: 8%] — `agents/qa-regression.md` and `agents/rag-source.md` carry `status: proposed` marker and state exclusion from default fan-out; `agents/retrospective.md` contains the strings "mini", "pdca", and "jishuken" and explicitly states "No standard-work proposals" for mini mode and jishuken mode**

Input: scan the three agent files for required strings.

Verification:
```python
python -c "
import pathlib, sys, re
errors = []

# qa-regression and rag-source must carry status: proposed
for path in ['agents/qa-regression.md', 'agents/rag-source.md']:
    text = pathlib.Path(path).read_text(encoding='utf-8')
    if 'status: proposed' not in text and 'status:proposed' not in text.replace(' ', ''):
        errors.append(f'{path}: missing \"status: proposed\" marker')
    # Body must explicitly state exclusion from default fan-out (Q4)
    if not re.search(r'not in.*default fan.out|excluded from.*fan.out|default fan.out.*not|not.*included.*default fan.out', text, re.IGNORECASE):
        errors.append(f'{path}: body does not state exclusion from default fan-out (Q4 requirement)')

# retrospective must document all three modes and prohibit standard-work proposals in mini and jishuken
retro = pathlib.Path('agents/retrospective.md').read_text(encoding='utf-8')
for mode in ['mini', 'pdca', 'jishuken']:
    if mode not in retro:
        errors.append(f'agents/retrospective.md: mode \"{mode}\" not mentioned')
# Check that standard-work prohibition is stated for mini and jishuken
# The phrase must appear (case-insensitive) at least twice (once per prohibited mode)
prohibitions = re.findall(r'[Nn]o standard[-\s]work proposals?', retro)
if len(prohibitions) < 2:
    errors.append('agents/retrospective.md: \"No standard-work proposals\" must appear explicitly for both mini mode and jishuken mode (found ' + str(len(prohibitions)) + ' occurrence(s))')

if errors:
    for e in errors: print('FAIL:', e)
    sys.exit(1)
print('ALL PASS')
"
```

Pass condition: script prints `ALL PASS` and exits 0.

Maps to: SC-D2-3, SC-D2-4 (§5, §7.5, §7.6, §7.7, Q4)

---

**SC-5 [weight: 8%] — `templates/dispatch-envelope.md` references both `instructions/andon-protocol.md` and `instructions/evidence-first.md`; `templates/nemawashi-position-paper.md` contains all four stage headings**

Input: scan the two template files for required content.

Verification:
```python
python -c "
import pathlib, sys, re
errors = []

env = pathlib.Path('templates/dispatch-envelope.md').read_text(encoding='utf-8')
if 'instructions/andon-protocol.md' not in env:
    errors.append('templates/dispatch-envelope.md: missing reference to instructions/andon-protocol.md')
if 'instructions/evidence-first.md' not in env:
    errors.append('templates/dispatch-envelope.md: missing reference to instructions/evidence-first.md')

nema = pathlib.Path('templates/nemawashi-position-paper.md').read_text(encoding='utf-8')
for stage_keyword in ['Stage 1', 'Stage 2', 'Stage 3', 'Stage 4']:
    # Require stage keyword at the start of a line (possibly preceded by markdown heading markers)
    if not re.search(r'^#{0,6}\s*' + re.escape(stage_keyword), nema, re.MULTILINE):
        errors.append(f'templates/nemawashi-position-paper.md: missing \"{stage_keyword}\" as a section heading (must appear at start of a line)')

if errors:
    for e in errors: print('FAIL:', e)
    sys.exit(1)
print('ALL PASS')
"
```

Pass condition: script prints `ALL PASS` and exits 0.

Maps to: SC-D2-6 (§5, §9.6, §8.2 Step 1D, R5)

---

**SC-6 [weight: 5%] — No instruction file is empty or stub-only (each must contain substantive behavioral content)**

Input: check that every instruction file has meaningful length and is not a placeholder. `instructions/evidence-first.md` and `instructions/human-approval.md` require a higher threshold (≥500 non-whitespace chars) given their mandatory complex content; other instruction files require ≥200 non-whitespace chars.

Verification:
```python
python -c "
import pathlib, sys, re
# Files requiring a higher threshold due to mandatory complex content
high_threshold = {
    'instructions/evidence-first.md': 500,
    'instructions/human-approval.md': 500,
}
instructions = [
    'instructions/controlled-artifacts.md',
    'instructions/evidence-first.md',
    'instructions/human-approval.md',
    'instructions/andon-protocol.md',
    'instructions/prompt-injection-defense.md',
]
errors = []
for path in instructions:
    text = pathlib.Path(path).read_text(encoding='utf-8')
    non_ws = re.sub(r'\s+', '', text)
    threshold = high_threshold.get(path, 200)
    if len(non_ws) < threshold:
        errors.append(f'{path}: content too short ({len(non_ws)} non-whitespace chars, need >= {threshold}); likely a stub')
    stub_markers = ['TODO', 'PLACEHOLDER', 'TBD', '<!-- stub -->']
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

Maps to: Should-NOT gate enforcement (spec §4, all instruction files)

---

**SC-6b [weight: 4%] — `instructions/evidence-first.md` contains the verification syntax allowlist prefixes and core evidence concepts (§7.0.2, v2.1 amendment A1)**

Input: check that `instructions/evidence-first.md` contains the six allowlisted prefix terms from §7.0.2 and the two mandatory evidence field names.

Verification:
```python
python -c "
import pathlib, sys
ef = pathlib.Path('instructions/evidence-first.md').read_text(encoding='utf-8')
errors = []
# Six allowlist prefix terms from §7.0.2 table
for kw in ['git diff', 'grep', 'cat', 'jq', 'python -m json.tool', 'test']:
    if kw not in ef:
        errors.append(f'instructions/evidence-first.md: missing required allowlist term: {kw!r}')
# Core evidence field names required by §7.0.2 and v2.1 A1
for kw in ['evidence_class', 'confidence']:
    if kw not in ef:
        errors.append(f'instructions/evidence-first.md: missing required concept: {kw!r}')
if errors:
    for e in errors: print('FAIL:', e)
    sys.exit(1)
print('ALL PASS')
"
```

Pass condition: script prints `ALL PASS` and exits 0.

Maps to: §4, R4, §7.0.2, v2.1 amendment A1

---

**SC-6c [weight: 4%] — `instructions/human-approval.md` contains the four nemawashi stage labels, three-handle prompt keywords, and reversibility rule (§8.2 Step 1D, R5, R9)**

Input: check that `instructions/human-approval.md` contains the mandatory behavioral content the downstream sprint (S5) depends on.

Verification:
```python
python -c "
import pathlib, sys
ha = pathlib.Path('instructions/human-approval.md').read_text(encoding='utf-8')
errors = []
# Four nemawashi stage labels
for stage in ['Stage 1', 'Stage 2', 'Stage 3', 'Stage 4']:
    if stage not in ha:
        errors.append(f'instructions/human-approval.md: missing stage label: {stage!r}')
# Three-handle prompt keywords (yes / refine / disagree) — 'yes' is too common; check the two distinctive ones
for kw in ['refine', 'disagree']:
    if kw not in ha:
        errors.append(f'instructions/human-approval.md: missing three-handle keyword: {kw!r}')
# Reversibility rule: irreversible actions auto-escalate
if 'reversib' not in ha:
    errors.append('instructions/human-approval.md: missing reversibility rule (expected keyword \"reversib\")')
# Minor vs major path distinction
for kw in ['minor', 'major']:
    if kw not in ha:
        errors.append(f'instructions/human-approval.md: missing path distinction keyword: {kw!r}')
if errors:
    for e in errors: print('FAIL:', e)
    sys.exit(1)
print('ALL PASS')
"
```

Pass condition: script prints `ALL PASS` and exits 0.

Maps to: §4, R5, R9, §8.2 Step 1D, §9.5

---

### LLM-as-judge (weights sum to 39%)

**SC-7 [weight: 20%] — `instructions/andon-protocol.md` correctly and completely describes the andon protocol**

The judge reads `instructions/andon-protocol.md` and scores against the following rubric dimensions:

1. **Thank-the-puller acknowledgment** (§7.0.1, R2): The file specifies that the orchestrator MUST write a thank-the-puller acknowledgment to the escalating agent *verbatim before* any analytical response when any `andon_signal` (alert or stop) is received. The verb "before" or equivalent phrasing must appear.
2. **Alert vs stop distinction** (§7.0.1, R3): The file clearly distinguishes `andon_signal: alert` (recoverable, triggers swarm) from `andon_signal: stop` (committed, immediately halts sprint loop). Both types are named and their differing consequences explained.
3. **Swarming protocol** (§8.2 Step 1C, v2.1 amendment A6): The file describes that an `alert` triggers dispatch of the originating agent plus agents named in `swarm_request`, capped at 4 agents total; swarm dispatches are parallel regardless of the `dispatch_mode` setting; the resolution window is takt-bounded (default 10 minutes / `andon_takt_seconds`); unresolved swarms escalate to `stop`.
4. **Rule 4 carve-out** (v2.1 amendment A10): The file states that `andon_signal: stop` is mandatory and bypasses Rule 4 (Bounded Self-Organization). Rule 4 governs `swarm_request` (suggestive), not `stop` (mandatory). This carve-out must be explicit.
5. **Andon signal structure**: The file documents the required output structure — a JSON object with `type` (alert|stop), `reason`, `evidence` (array), and `swarm_request` (array of agent IDs).

Score: PASS if ≥4 of 5 dimensions are fully satisfied; PARTIAL (50% weight credit) if 3 dimensions satisfied; FAIL if ≤2 dimensions satisfied.

Maps to: SC-D2-2 partial (§5, §7.0.1, R2/R3, v2.1 amendments A6/A10)

---

**SC-8 [weight: 11%] — `agents/orchestrator.md` correctly documents the orchestrator's authority and evidence obligations**

The judge reads `agents/orchestrator.md` and scores against the following rubric dimensions:

1. **Level and tools** (§7.1): The file declares Level 4 autonomy and lists exactly the tools `Read, Glob, Grep, Bash, Write, Task` — no more, no fewer.
2. **Context: inherit** (§7.1, §9.1): The file declares `context: inherit` in frontmatter. The body explains why — the orchestrator must see what the user typed (it is the conductor).
3. **Andon authority and thank-the-puller** (§7.0.1): The body states the orchestrator honors all andon signals; stop signals are honored immediately before analysis; a thank-the-puller acknowledgment is written verbatim first.
4. **Evidence obligations and verification spot-check** (§7.0.2, §8.2 Step 1C): The body states the orchestrator spot-checks one random `observed` claim per fan-in by re-running its verification via `scripts/run-verification.py`; divergence logs a `quality-defect-anomaly` Henkaten; allowlist violation logs an `agent-capability-change` Henkaten.
5. **Prohibitions** (§7.1): The body explicitly prohibits at least three of: performing analysis a worker agent should do; modifying `features.json`/`spec.md`/`sprints.json` without Level 5 approval; passing internal reasoning to subagents; filtering or second-guessing andon signals; auto-applying irreversible actions regardless of nominal autonomy.
6. **Dynamic autonomy floor** (§7.1, R10): The body states the orchestrator manages the dynamic autonomy floor and writes `state/effective-autonomy.json` on level changes.

Score: PASS if ≥5 of 6 dimensions are fully satisfied; PARTIAL (50% weight credit) if 3–4 satisfied; FAIL if ≤2 satisfied.

Maps to: SC-D2-1 partial (§5, §7.1, §7.0.1, §7.0.2)

---

**SC-9 [weight: 8%] — `agents/henkaten-detector.md` correctly describes the 4M classification system, change_origin field, and scheduled-vs-unscheduled suppression rule**

The judge reads `agents/henkaten-detector.md` and scores against the following rubric dimensions:

1. **4M classification** (§6.1, §7.4, R8): The file mentions all four 4M axes (Man, Machine, Material, Method) and the requirement to assign a `fourM_axis` value and a sub-type to every detected change point.
2. **change_origin: active | passive** (§6.3, R1): The file explains the distinction — `active` (henkoten: deliberately initiated) vs `passive` (henkaten strict sense: emerged unbidden) — and states that passive changes default to lower confidence/impact unless corroborated by a second signal.
3. **Scheduled-vs-unscheduled suppression rule** (§6.7, v2.1 amendment A3): The file describes the suppression rule for `agent-capability-change`: edits within the active sprint's declared scope are scheduled deliverables (no Henkaten record); out-of-scope edits fire as `agent-capability-change` with `change_origin: passive`. The file names the scope-lookup priority order: tasks.json → sprint contract "Files in scope" → sprints.json fallback; and the fail-safe bypass (every edit fires if no scope source is available) with a `coverage` warning.
4. **`agent-capability-change` sub-type** (§6.2.1, Q18): The file specifically names `agent-capability-change` as the Man-axis sub-type covering model upgrades, prompt-template revisions, agent-file edits, and plugin version bumps.

Score: PASS if all 4 dimensions are fully satisfied; PARTIAL (50% weight credit) if 2–3 satisfied; FAIL if ≤1 satisfied.

Maps to: SC-D2-1 partial (§5, §7.4, §6.1, §6.3, §6.7, v2.1 amendment A3)

---

## Should-NOT Criteria (Gate — Any Failure Blocks the Sprint)

- **MUST NOT give any agent file tools beyond its §7 contract.** Specifically: `agents/architect.md`, `agents/scope-guardian.md`, `agents/henkaten-detector.md`, `agents/retrospective.md`, `agents/qa-regression.md`, and `agents/rag-source.md` must not list `Bash`, `Write`, or `Task` in their `tools:` frontmatter. Only `agents/orchestrator.md` may declare those three tools.

  Verification (absence check):
  ```python
  python -c "
  import pathlib, sys, re
  restricted = ['agents/architect.md','agents/scope-guardian.md','agents/henkaten-detector.md','agents/retrospective.md','agents/qa-regression.md','agents/rag-source.md']
  disallowed = {'Bash', 'Write', 'Task'}
  errors = []
  for path in restricted:
      text = pathlib.Path(path).read_text(encoding='utf-8')
      m = re.match(r'^---\s*\n(.*?)\n---', text, re.DOTALL)
      if not m: continue
      tools_line = next((l for l in m.group(1).splitlines() if 'tools' in l.lower()), '')
      found = {t for t in disallowed if t in tools_line}
      if found:
          errors.append(f'{path}: declares disallowed tool(s) {found}')
  if errors:
      for e in errors: print('GATE FAIL:', e); sys.exit(1)
  print('GATE PASS')
  "
  ```

- **MUST NOT declare `context: inherit` in any agent file other than `agents/orchestrator.md`.** All six non-orchestrator agent files must declare `context: fork`.

  Verification (absence check):
  ```python
  python -c "
  import pathlib, sys, re
  non_orch = ['agents/architect.md','agents/scope-guardian.md','agents/henkaten-detector.md','agents/retrospective.md','agents/qa-regression.md','agents/rag-source.md']
  errors = []
  for path in non_orch:
      text = pathlib.Path(path).read_text(encoding='utf-8')
      m = re.match(r'^---\s*\n(.*?)\n---', text, re.DOTALL)
      if not m: continue
      fm = m.group(1)
      if 'inherit' in fm:
          errors.append(f'{path}: declares context: inherit (must be fork)')
  if errors:
      for e in errors: print('GATE FAIL:', e); sys.exit(1)
  print('GATE PASS')
  "
  ```

- **MUST NOT place `agents/qa-regression.md` or `agents/rag-source.md` in the default fan-out.** Both files must carry `status: proposed` and the body must explicitly state they are not in the default fan-out (Q4). Their descriptions must not imply automatic inclusion.

  Verification (absence check — full runnable command):
  ```python
  python -c "
  import pathlib, sys, re
  errors = []
  for path in ['agents/qa-regression.md', 'agents/rag-source.md']:
      text = pathlib.Path(path).read_text(encoding='utf-8')
      if 'status: proposed' not in text and 'status:proposed' not in text.replace(' ', ''):
          errors.append(f'{path}: GATE FAIL: missing \"status: proposed\" marker')
      if not re.search(r'not in.*default fan.out|excluded from.*fan.out|default fan.out.*not|not.*included.*default fan.out', text, re.IGNORECASE):
          errors.append(f'{path}: GATE FAIL: body does not explicitly state exclusion from default fan-out (required by Q4)')
  if errors:
      for e in errors: print(e); sys.exit(1)
  print('GATE PASS')
  "
  ```

- **MUST NOT reference files from future sprints that do not yet exist.** Agent and instruction files may reference schemas from `schemas/` (Sprint 1 deliverables) and files within Sprint 2's own deliverables (`agents/`, `instructions/`, `templates/` files). They must not reference `scripts/append-henka.py`, `scripts/append-decision.py`, `scripts/run-verification.py`, `hooks/*.sh`, `hooks/win/*.ps1`, or any `skills/*/SKILL.md` by path (these are Sprint 3–8 deliverables). Descriptive prose that mentions these files by name without a path reference (e.g. "the orchestrator invokes `scripts/run-verification.py`") is acceptable.

  Verification:
  ```python
  python -c "
  import pathlib, sys, re
  sprint2_files = [
      'agents/orchestrator.md','agents/architect.md','agents/scope-guardian.md',
      'agents/henkaten-detector.md','agents/retrospective.md','agents/qa-regression.md',
      'agents/rag-source.md','instructions/controlled-artifacts.md',
      'instructions/evidence-first.md','instructions/human-approval.md',
      'instructions/andon-protocol.md','instructions/prompt-injection-defense.md',
      'templates/dispatch-envelope.md','templates/nemawashi-position-paper.md',
  ]
  # Paths that must not appear as hyperlink-style references (e.g. [text](path) or @path)
  forbidden_path_patterns = [
      r'scripts/append-henka\.py',
      r'scripts/append-decision\.py',
      r'scripts/run-verification\.py',
      r'scripts/update-effective-autonomy\.py',
      r'scripts/rotate-audit-log\.py',
      r'hooks/(?!win/).+\.(sh|ps1)',
      r'hooks/win/.+\.ps1',
      r'skills/[^/]+/SKILL\.md',
  ]
  errors = []
  combined = re.compile('|'.join(forbidden_path_patterns))
  # Allow plain prose mentions (not prefixed with @, ./, or /)
  # A reference is a path-like if preceded by @, ./, /, or markdown link syntax [...](<path>)
  # Character class uses [@/\(] — no '.' to avoid false positives from sentence-ending periods
  path_ref = re.compile(r'[@/\(](' + '|'.join(forbidden_path_patterns) + r')')
  for f in sprint2_files:
      text = pathlib.Path(f).read_text(encoding='utf-8')
      for m in path_ref.finditer(text):
          errors.append(f'{f}: disallowed path reference: {m.group(0)!r}')
  if errors:
      for e in errors: print('GATE FAIL:', e); sys.exit(1)
  print('GATE PASS')
  "
  ```

- **MUST NOT create any file outside the 14 files listed in "Files in Scope".** In particular, no schema files, no script files, no hook files, no skill files, no test fixtures, no `.harness/` modifications, and no template files beyond `dispatch-envelope.md` and `nemawashi-position-paper.md` may be created in this sprint.

- **MUST NOT modify any `.harness/*` files.** All harness files are read-only for this sprint.

---

## Reference Solutions

Reference content for **SC-7** (highest-weighted LLM-judge criterion) — key facts that `instructions/andon-protocol.md` MUST communicate, drawn directly from §7.0.1, R2/R3, and v2.1 amendments A6/A10:

```
## Andon Protocol — Behavioral Instructions

Every council agent may issue an andon signal in its output:

  {
    "andon_signal": {
      "type": "alert" | "stop",
      "reason": "concise statement of what triggered the signal",
      "evidence": ["file:line or command output references"],
      "swarm_request": ["agent_id_1", "agent_id_2"]
    }
  }

### Thank-the-Puller Acknowledgment (mandatory)

When the orchestrator receives any andon_signal (alert or stop), it MUST
write a thank-the-puller acknowledgment to the escalating agent verbatim
BEFORE any analytical response. This is non-negotiable. Pull-rate per agent
is tracked in the audit log; anomalous pull-rates are flagged as
quality-defect-anomaly Henkaten.

### Alert vs Stop

- andon_signal: alert — recoverable escalation. The sprint loop pauses.
  The orchestrator dispatches a swarm: the originating agent plus any agents
  named in swarm_request (total capped at 4). Swarm dispatches are parallel
  Task calls, regardless of dispatch_mode. Resolution window: 10 minutes
  wall-clock (andon_takt_seconds). If resolved within bound, sprint resumes
  with a logged decision. If not resolved, alert escalates to stop.

- andon_signal: stop — committed halt. The orchestrator immediately halts
  the sprint loop. No analysis before honoring. User must resume.
  Requires explicit /council-review invocation to restart.

### Rule 4 Carve-Out (v2.1 amendment A10)

Rule 4 (Bounded Self-Organization) states that agents may flag the need for
another perspective via swarm_request, but the orchestrator decides whether
to invoke additional agents. However: andon_signal: stop is mandatory and
bypasses Rule 4. Stop signals are not suggestions — they are immediate
halts. The orchestrator may NOT defer, filter, or second-guess a stop signal.
```

---

## Out of Scope

- **Running the agents:** agent files are static text contracts; runtime execution is Sprint 6 (S4 fan-out). No agent invocation occurs in this sprint.
- **Skill files (S1–S6 — Sprints 3–8):** `skills/*/SKILL.md` files are not created in this sprint. The dispatch-envelope template describes the dispatch pattern but is not an executable skill.
- **Hook files (S3 — Sprint 5):** `hooks/*.sh` and `hooks/win/*.ps1` are not created here.
- **Plugin bootstrap files (S1 — Sprint 3):** `.claude-plugin/plugin.json`, `.mcp.json`, `.claude/settings.json`, `README.md`, `LICENSE`, `CLAUDE.md` are Sprint 3 deliverables.
- **Append and compute scripts (S2 — Sprint 4):** `scripts/append-henka.py`, `scripts/append-decision.py`, `scripts/compute-evidence-class.py`, `scripts/update-effective-autonomy.py`, `scripts/run-verification.py`, `scripts/rotate-audit-log.py` are Sprint 4 deliverables.
- **Live integration with `.council/` state:** no `.council/` directory exists yet; kickoff runs in Sprint 3.
- **Additional output templates:** `templates/council-review-report.md`, `templates/course-correction.md`, `templates/retrospective-mini.md`, `templates/retrospective-pdca.md`, `templates/jishuken-workshop.md`, and `templates/contracts-first-standard-work.json` are Sprint 8 (S6) deliverables.
- **Validator scripts for schemas not covered in Sprint 1:** `scripts/validate-council-config.py`, `scripts/validate-henka-record.py`, `scripts/validate-decision-log.py` were Sprint 1 deliverables; do not recreate them here.
- **Everything listed in §15 "Out of v0.1":** Archaeologist agent, Prompt Forge agent, parallel dispatch default, MCP-based git server, `evaluator-bias-change` sub-type, direct jishuken-to-standard-work promotion, CC-001 default-on, `pass@k`/`pass^k` metrics.

---

## Technical Notes

**Agent file frontmatter format:** Agent files MUST use YAML frontmatter between `---` delimiters at the very top of the file. Minimum required keys for all agent files: `name`, `description`, `tools`, `context`, `level`. Example:

```yaml
---
name: Architect
description: >
  Coherence and drift reviewer. Level 2 proposal-only agent. Reviews sprint
  results against spec/plan coherence.
tools: Read, Glob, Grep
context: fork
level: 2
---
```

The `tools` key value is a comma-separated string (not a YAML list) matching Claude Code's subagent dispatch format. The `context` key is either `inherit` (orchestrator only) or `fork` (all other agents). The `level` key is an integer string (1, 2, or 4 for the agents in this sprint). This frontmatter convention allows the SC-2 verification script to locate and parse the declarations without a full YAML parser dependency.

**Cross-references between files:** Agent files MUST reference their behavioral instruction dependencies using the `@instructions/<file>.md` path syntax in the body text (not just prose mention). The dispatch-envelope template MUST reference both instruction files by their relative paths `instructions/andon-protocol.md` and `instructions/evidence-first.md`. The nemawashi position paper template MUST contain all four stage headings explicitly (`Stage 1`, `Stage 2`, `Stage 3`, `Stage 4`).

**`status: proposed` placement:** For `agents/qa-regression.md` and `agents/rag-source.md`, the `status: proposed` marker may appear either in the YAML frontmatter or in the body — either is acceptable for SC-4. However, placing it in both locations is preferred for discoverability by downstream sprint code that may parse frontmatter only.

**Level assignment rationale (from §2.4.1):** Level 1 = classify and recommend (henkaten-detector, rag-source); Level 2 = propose drafts (architect, scope-guardian, retrospective, qa-regression); Level 4 = coordinate sequences under supervision (orchestrator). No Level 0, 3, or 5 agent files are created in this sprint.

**Scheduled-vs-unscheduled suppression note (§6.7, v2.1 amendment A3):** Sprint 2's own deliverables (this sprint's `agents/`, `instructions/`, and `templates/` files) are scheduled deliverables and MUST NOT generate Henkaten records per the suppression rule. The henkaten-detector.md file must document this suppression rule so that when the detector is instantiated in future sprints, it applies it correctly.

**`instructions/evidence-first.md` must include the verification syntax allowlist** from §4.5 / §7.0.2 (v2.1 amendment A1). The allowlist specifies the permitted prefixes for `verification` strings in agent outputs: `git diff/show/log/status/branch/ls-files`, `grep/rg` (read-only), `cat/head/tail`, `jq` (explicit file path, no `-i`), `python -m json.tool/python scripts/validate-*.py`, `test/[…]` (POSIX file tests). Disallowed: write operations, network calls, shell redirects, pipe-to-shell, `eval`, `exec`, project source execution. The instruction file must cite `scripts/run-verification.py` as the enforcer.

**`instructions/human-approval.md` must document the four-stage nemawashi walkthrough** with all four stage labels, the three-handle prompt (yes / refine / disagree) for Stage 2, and the distinction between the minor single-prompt path and the major walkthrough path. It must also note the reversibility rule: irreversible actions auto-escalate to major/nemawashi regardless of nominal class.

**`templates/dispatch-envelope.md` is the single dispatch path (§9.6, §4.8):** The template must make clear that: (a) no skill may call another skill via `Task` — only agent dispatches use this template; (b) the orchestrator passes ONLY file paths and structured constraints to subagents, never internal reasoning; (c) every dispatched agent inherits andon authority and genchi-genbutsu obligations via the instructions cross-references.

**Sprint 1 dependency:** The agent files and instruction files may (and should) reference the schema files produced in Sprint 1 (`schemas/henka-record.schema.json`, etc.) as authoritative data contracts. These references should use relative paths. No schema files may be created or modified in Sprint 2.

**Self-referential note (§2.2, Design Tension Note 1):** Because Sprint 2 is itself building the henkaten-detector.md file, any future invocation of the detector in sprints 3+ would recognize Sprint 2's deliverables as scheduled (suppressed) rather than unscheduled. The suppression rule must be in the detector's contract document even though the detector cannot execute during its own construction sprint.


## Evaluator Review

**Status: APPROVED**

### Summary
All three original blockers/majors (B1, M1, M2) have been materially addressed: Gate 3 now carries a standalone Python verification script with the fan-out-exclusion regex; SC-6b adds token-presence verification for `evidence-first.md` with two specific anchors (`git diff`, `python -m json.tool`) plus `evidence_class`/`confidence` field names; SC-6c adds stage-label and three-handle verification for `human-approval.md` with strong anchors (`Stage 1-4`, `refine`, `disagree`, `reversib`). Weight arithmetic confirmed correct (deterministic 61%, LLM-judge 39%, grand total 100%). Three new minor-class observations are noted below; none rise to blocker or major level in this final round.

### Blockers (must fix before approval)
- None.

### Major issues
- None. M1 and M2 from round 1 are adequately closed. SC-6b has four weak keywords (`cat`, `grep`, `jq`, `test`) that are trivially matchable in any prose document, but the two strong anchors (`git diff`, `python -m json.tool`) combined with the 500-char SC-6 floor provide adequate assurance against stubs. Acceptable at 4% weight.

### Minor / nice-to-have
- **SC-4 prohibition regex is case-sensitive on the body word:** `[Nn]o standard[-\s]work proposals?` matches `No ...` and `no ...` but not title-case `No Standard-Work Proposals`. If the Generator writes the prohibition as a heading (e.g. `### No Standard-Work Proposals`), SC-4 will incorrectly fail. The criterion text telegraphs the expected string, so this constrains the Generator rather than being a contract defect, but adding `re.IGNORECASE` to the `findall` call would eliminate the fragility.
- **SC-4 count-based proxy can be fooled by same-section double mention:** `len(prohibitions) >= 2` passes if the same section mentions the prohibition twice, leaving one mode undocumented. Low practical risk; a position-aware check (e.g., require one match near `mini` and one near `jishuken` within ±3 lines) would be more robust.
- **SC-6b keyword `test` is trivially present in almost any document:** the substring appears in common English words (`testing`, `attest`, `context`, `protest`). Only `git diff` and `python -m json.tool` serve as meaningful anchors. Consider replacing `test` with `test -` (POSIX file-test flag prefix) to require actual file-test syntax rather than arbitrary prose matches.
