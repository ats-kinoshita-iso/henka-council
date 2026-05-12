# Sprint 06 Contract — S4 Council Autorun + Andon Protocol + Verification Spot-Check

## Scope

Sprint 6 ships the council-autorun skill (`skills/council-autorun/SKILL.md`) with all ten named steps (1A, 1A.5, 1B through 1I) per §8.2, the verification spot-check script (`scripts/run-verification.py`) with §7.0.2 allowlist enforcement, a 10-second timeout, and `agent-capability-change` Henkaten logging for non-conformant strings, a full enrichment of `instructions/andon-protocol.md` that fills in the verbatim thank-the-puller acknowledgment, Rule 4 carve-out, and pull-rate tracking, a `tests/fixtures/dummy-project/` trine-eval fixture with two trivial features and two sprints, and an end-to-end S4 acceptance test against the §15.5 assertions 1–6. Dynamic autonomy floor distinct-originator corroboration logic and scheduled-vs-unscheduled suppression rules are documented inline in `skills/council-autorun/SKILL.md` and `agents/henkaten-detector.md`. No `.council/` directory is created in this repo; all write-path tests use the dummy-project fixture or isolated temp directories.

---

## Files in Scope

**New files (8):**
- `skills/council-autorun/SKILL.md` — full Steps 1A through 1I (§8.2), YAML frontmatter, ≥3000 chars **[NEW]**
- `scripts/run-verification.py` — allowlist enforcement, 10s timeout, project-root CWD, pre-invocation string check, `agent-capability-change` Henkaten logging for non-conformant strings (§7.0.2, v2.1 amendment A1) **[NEW]**
- `tests/scripts/test-run-verification.py` — fixture test for `scripts/run-verification.py`; exits 0 on pass **[NEW]**
- `tests/fixtures/dummy-project/.harness/config.json` — minimal trine-eval fixture (§15.5) **[NEW]**
- `tests/fixtures/dummy-project/.harness/spec.md` — minimal fixture spec **[NEW]**
- `tests/fixtures/dummy-project/.harness/sprints.json` — two trivial sprints **[NEW]**
- `tests/fixtures/dummy-project/src/` — minimal stub source file(s) **[NEW]**
- `tests/test-s4-acceptance.py` (or `tests/test-s4-acceptance.sh`) — end-to-end test exercising §15.5 assertions 1–6 **[NEW]**

**Enriched files (1):**
- `instructions/andon-protocol.md` — full implementation: verbatim thank-the-puller acknowledgment, alert vs stop semantics, swarming, Rule 4 carve-out, pull-rate tracking reference (§7.0.1, v2.1 amendment A10) **[ENRICHED]**

**Prose-only enrichments (no separate files):**
- Dynamic autonomy floor logic (§2.4.3, A2): distinct-originator corroboration — documented in `skills/council-autorun/SKILL.md` Step 1F
- Scheduled-vs-unscheduled suppression (§6.7, A3): priority-ordered source resolution — documented in `skills/council-autorun/SKILL.md` Step 1A and/or `agents/henkaten-detector.md`

---

## Success Criteria

### Deterministic (weights sum to 67%)

<!-- SC weights: SC-1(7)+SC-2(6)+SC-3(8)+SC-4(8)+SC-5(7)+SC-6(8)+SC-7(7)+SC-8(6)+SC-9(5)+SC-10(5) = 67% -->

---

**SC-1 [weight: 7%] — All declared sprint-6 files exist at their specified paths and Python files parse cleanly**

Input: check file existence and `ast.parse` all Python files.

Verification:
```python
python -c "
import pathlib, ast, sys

errors = []

files = [
    'skills/council-autorun/SKILL.md',
    'scripts/run-verification.py',
    'tests/scripts/test-run-verification.py',
    'tests/fixtures/dummy-project/.harness/config.json',
    'tests/fixtures/dummy-project/.harness/spec.md',
    'tests/fixtures/dummy-project/.harness/sprints.json',
    'instructions/andon-protocol.md',
]
# Accept either .py or .sh for the acceptance test
acceptance_py = pathlib.Path('tests/test-s4-acceptance.py')
acceptance_sh = pathlib.Path('tests/test-s4-acceptance.sh')
if not acceptance_py.exists() and not acceptance_sh.exists():
    errors.append('MISSING: tests/test-s4-acceptance.py (or .sh)')

for f in files:
    if not pathlib.Path(f).exists():
        errors.append(f'MISSING: {f}')

# Python syntax check
for f in ['scripts/run-verification.py', 'tests/scripts/test-run-verification.py']:
    p = pathlib.Path(f)
    if p.exists():
        try:
            ast.parse(p.read_text(encoding='utf-8'))
        except SyntaxError as e:
            errors.append(f'SYNTAX ERROR in {f}: {e}')

# dummy-project src/ directory must exist (at least one file)
src_dir = pathlib.Path('tests/fixtures/dummy-project/src')
if not src_dir.exists() or not any(src_dir.iterdir()):
    errors.append('MISSING or EMPTY: tests/fixtures/dummy-project/src/')

if errors:
    for e in errors: print(e)
    sys.exit(1)
print('ALL PRESENT AND VALID SYNTAX')
"
```

Pass condition: prints `ALL PRESENT AND VALID SYNTAX` and exits 0.

Maps to: §8.2, §7.0.2, §15.5

---

**SC-2 [weight: 6%] — `scripts/run-verification.py` is invocable and `--help` exits 0; `--check-only` is a recognized flag**

Input: invoke `python scripts/run-verification.py --help` and verify `--check-only` is a recognized flag.

Verification:
```python
python -c "
import subprocess, sys
errors = []

# --help must exit 0
r = subprocess.run(
    [sys.executable, 'scripts/run-verification.py', '--help'],
    capture_output=True, text=True
)
if r.returncode != 0:
    errors.append(f'FAIL: --help exited {r.returncode}: {r.stderr[:300]}')

# --check-only must be a recognized flag (should not produce 'unrecognized argument' error)
r2 = subprocess.run(
    [sys.executable, 'scripts/run-verification.py', '--check-only', 'git status'],
    capture_output=True, text=True
)
combined = (r2.stdout + r2.stderr).lower()
if 'unrecognized' in combined or 'invalid choice' in combined or 'error: argument' in combined:
    errors.append(f'FAIL: --check-only flag not recognized: {r2.stderr[:300]}')

if errors:
    for e in errors: print(e)
    sys.exit(1)
print('PASS')
"
```

Pass condition: exits 0.

Maps to: §7.0.2, v2.1 amendment A1

---

**SC-3 [weight: 8%] — `scripts/run-verification.py` allowlist enforcement: allowed string exits 0, disallowed string exits non-zero with stderr message**

Input: feed an allowed verification string (e.g., `git diff HEAD`) → expect exit 0. Feed a disallowed string (e.g., `rm -rf /tmp/test`) → expect non-zero exit and a stderr message explaining the rejection.

Verification:
```python
python -c "
import subprocess, sys

errors = []

# Allowed: git diff is in the allowlist
r_allow = subprocess.run(
    [sys.executable, 'scripts/run-verification.py', '--check-only', 'git diff HEAD'],
    capture_output=True, text=True
)
if r_allow.returncode != 0:
    errors.append(f'FAIL: allowlisted command rejected (exit {r_allow.returncode}): {r_allow.stderr[:300]}')

# Disallowed: rm is not in the allowlist
r_deny = subprocess.run(
    [sys.executable, 'scripts/run-verification.py', '--check-only', 'rm -rf /tmp/test'],
    capture_output=True, text=True
)
if r_deny.returncode == 0:
    errors.append('FAIL: non-allowlisted command was accepted (exit 0)')
if r_deny.returncode != 0 and not (r_deny.stderr.strip() or r_deny.stdout.strip()):
    errors.append('FAIL: rejection produced no stderr/stdout message')

if errors:
    for e in errors: print(e)
    sys.exit(1)
print('ALLOWLIST ENFORCEMENT PASS')
"
```

Pass condition: prints `ALLOWLIST ENFORCEMENT PASS` and exits 0.

Maps to: §7.0.2, v2.1 amendment A1

---

**SC-4 [weight: 8%] — `scripts/run-verification.py` timeout enforcement: a command exceeding 10s is terminated and exits non-zero**

Input: feed a command that sleeps longer than the script's timeout limit. The script must terminate it and exit non-zero. To keep the test fast, accept either (a) a `--timeout N` flag that overrides the default 10s, or (b) the default 10s path if runtime permits.

Verification:
```python
python -c "
import subprocess, sys, time

# Try with --timeout 2 override if supported; fall back to testing the pre-invocation string
# check which also blocks 'sleep' commands
args_with_override = [sys.executable, 'scripts/run-verification.py', '--timeout', '2', 'sleep 5']
args_check_only = [sys.executable, 'scripts/run-verification.py', '--check-only', 'sleep 999']

start = time.time()
r = subprocess.run(args_with_override, capture_output=True, text=True, timeout=30)
elapsed = time.time() - start

errors = []
if r.returncode == 0:
    # Also accept if the script rejects 'sleep' at pre-invocation string check
    r2 = subprocess.run(args_check_only, capture_output=True, text=True, timeout=10)
    if r2.returncode == 0:
        errors.append('FAIL: sleep command not rejected by timeout or allowlist check')

if errors:
    for e in errors: print(e)
    sys.exit(1)
print('TIMEOUT ENFORCEMENT PASS')
"
```

Pass condition: prints `TIMEOUT ENFORCEMENT PASS` and exits 0. Note: if the script rejects `sleep` at the allowlist pre-check stage (before execution), that is also a valid pass — the important thing is that `sleep 5` or `sleep 999` cannot complete successfully.

Maps to: §7.0.2, v2.1 amendment A1

---

**SC-5 [weight: 7%] — `tests/scripts/test-run-verification.py` exits 0**

Input: run the fixture test suite for `run-verification.py`.

Verification:
```
python tests/scripts/test-run-verification.py
```

Pass condition: exits 0.

Maps to: §7.0.2, §15.5

---

**SC-6 [weight: 8%] — `skills/council-autorun/SKILL.md` has YAML frontmatter, is ≥3000 chars, and contains a heading for each of the required steps**

Input: read `skills/council-autorun/SKILL.md` and check frontmatter presence, length, and per-step heading existence.

Verification:
```python
python -c "
import pathlib, re, sys

p = pathlib.Path('skills/council-autorun/SKILL.md')
if not p.exists():
    print('MISSING: skills/council-autorun/SKILL.md'); sys.exit(1)

text = p.read_text(encoding='utf-8')
errors = []

# YAML frontmatter check
if not text.startswith('---'):
    errors.append('FAIL: missing YAML frontmatter (must start with ---)')

# Length check
if len(text) < 3000:
    errors.append(f'FAIL: SKILL.md is only {len(text)} chars; expected >= 3000')

# Per-step heading check (partial credit: each absent step is a separate failure)
required_steps = ['1A', '1A.5', '1B', '1C', '1D', '1E', '1F', '1G', '1H', '1I']
for step in required_steps:
    # Accept '## Step 1A', '### Step 1A', 'Step 1A:', '**Step 1A**', etc.
    pattern = r'(?i)(#{1,4}\s+step\s+' + re.escape(step) + r'\b|step\s+' + re.escape(step) + r'[\s:*])'
    if not re.search(pattern, text):
        errors.append(f'MISSING step heading: Step {step}')

if errors:
    for e in errors: print(e)
    sys.exit(1)
print('SKILL.md STRUCTURE PASS')
"
```

Pass condition: prints `SKILL.md STRUCTURE PASS` and exits 0. Partial credit applies: if some step headings are missing the criterion fails, but the LLM-judge SC-11 can still award partial weight for the steps that are present.

Maps to: §8.2, v2.1 amendments A1, A2, A6, A9

---

**SC-7 [weight: 7%] — `instructions/andon-protocol.md` contains the verbatim thank-the-puller text, mentions Rule 4 carve-out, and mentions pull-rate tracking**

Input: grep for the three required content anchors in `instructions/andon-protocol.md`.

Verification:
```python
python -c "
import pathlib, sys

p = pathlib.Path('instructions/andon-protocol.md')
if not p.exists():
    print('MISSING: instructions/andon-protocol.md'); sys.exit(1)

text = p.read_text(encoding='utf-8')
errors = []

# Verbatim thank-the-puller acknowledgment
if 'Thank you for stopping the line' not in text:
    errors.append('FAIL: missing verbatim thank-the-puller text (\"Thank you for stopping the line\")')

# Rule 4 carve-out
if 'Rule 4' not in text and 'rule 4' not in text.lower():
    errors.append('FAIL: missing Rule 4 carve-out mention')

# Pull-rate tracking reference
if 'pull-rate' not in text and 'pull_rate' not in text:
    errors.append('FAIL: missing pull-rate tracking reference')

if errors:
    for e in errors: print(e)
    sys.exit(1)
print('ANDON PROTOCOL CONTENT PASS')
"
```

Pass condition: prints `ANDON PROTOCOL CONTENT PASS` and exits 0.

Maps to: §7.0.1, v2.1 amendment A10

---

**SC-8 [weight: 6%] — `tests/fixtures/dummy-project/` directory structure matches the §15.5 fixture spec (config.json, spec.md, sprints.json present and sprints.json has at least 2 sprint entries)**

Input: check directory contents and parse the JSON files.

Verification:
```python
python -c "
import pathlib, json, sys

errors = []
base = pathlib.Path('tests/fixtures/dummy-project')

required_files = [
    base / '.harness' / 'config.json',
    base / '.harness' / 'spec.md',
    base / '.harness' / 'sprints.json',
]
for f in required_files:
    if not f.exists():
        errors.append(f'MISSING: {f}')

# sprints.json must parse and have >= 2 sprint entries
sprints_path = base / '.harness' / 'sprints.json'
if sprints_path.exists():
    try:
        data = json.loads(sprints_path.read_text(encoding='utf-8'))
        sprints = data.get('sprints', data if isinstance(data, list) else [])
        if len(sprints) < 2:
            errors.append(f'FAIL: dummy-project sprints.json has {len(sprints)} sprint(s); expected >= 2')
    except json.JSONDecodeError as e:
        errors.append(f'INVALID JSON in sprints.json: {e}')

# config.json must parse
config_path = base / '.harness' / 'config.json'
if config_path.exists():
    try:
        json.loads(config_path.read_text(encoding='utf-8'))
    except json.JSONDecodeError as e:
        errors.append(f'INVALID JSON in config.json: {e}')

if errors:
    for e in errors: print(e)
    sys.exit(1)
print('FIXTURE STRUCTURE PASS')
"
```

Pass condition: prints `FIXTURE STRUCTURE PASS` and exits 0.

Maps to: §15.5

---

**SC-9 [weight: 5%] — End-to-end S4 acceptance test exits 0**

Input: run `tests/test-s4-acceptance.py` (or `.sh`). The test exercises §15.5 assertions 1–6 against the dummy-project fixture.

Verification:
```python
python -c "
import subprocess, sys, pathlib

py_path = pathlib.Path('tests/test-s4-acceptance.py')
sh_path = pathlib.Path('tests/test-s4-acceptance.sh')

if py_path.exists():
    r = subprocess.run([sys.executable, str(py_path)], capture_output=True, text=True)
elif sh_path.exists():
    r = subprocess.run(['bash', str(sh_path)], capture_output=True, text=True)
else:
    print('MISSING: tests/test-s4-acceptance.py or .sh'); sys.exit(1)

if r.returncode != 0:
    print(f'FAIL: acceptance test exited {r.returncode}')
    print(r.stdout[-800:])
    print(r.stderr[-400:])
    sys.exit(1)
print('S4 ACCEPTANCE TEST PASS')
"
```

Pass condition: prints `S4 ACCEPTANCE TEST PASS` and exits 0.

Note: the acceptance test must internally assert all six §15.5 assertions listed in Technical Notes (not merely `exit 0` with no test logic). The LLM-judge SC-11 cross-references this criterion; a trivially-passing test that asserts nothing will fail SC-11 dimension 6.

Maps to: §15.5 assertions 1–6

---

**SC-10 [weight: 5%] — Cross-sprint regression: sprint-4 and sprint-5 Python scripts still parse; sprint-2 agent files still pass frontmatter checks**

Input: re-run `ast.parse` on sprint-4 scripts and frontmatter regex on 5 agents.

Verification:
```python
python -c "
import pathlib, ast, sys, re

errors = []

# Sprint-4 scripts
for s in ['scripts/append-henka.py', 'scripts/append-decision.py',
          'scripts/compute-evidence-class.py', 'scripts/update-effective-autonomy.py']:
    p = pathlib.Path(s)
    if not p.exists():
        errors.append(f'MISSING (sprint-4 regression): {s}')
        continue
    try:
        ast.parse(p.read_text(encoding='utf-8'))
    except SyntaxError as e:
        errors.append(f'SYNTAX ERROR (sprint-4): {s}: {e}')

# Sprint-5 script
for s in ['scripts/rotate-audit-log.py']:
    p = pathlib.Path(s)
    if not p.exists():
        errors.append(f'MISSING (sprint-5 regression): {s}')
        continue
    try:
        ast.parse(p.read_text(encoding='utf-8'))
    except SyntaxError as e:
        errors.append(f'SYNTAX ERROR (sprint-5): {s}: {e}')

# Agent frontmatter
EXPECTED = {
    'agents/orchestrator.md':      {'tools': {'Read','Glob','Grep','Bash','Write','Task'}, 'context': 'inherit', 'level': '4'},
    'agents/architect.md':         {'tools': {'Read','Glob','Grep'}, 'context': 'fork', 'level': '2'},
    'agents/scope-guardian.md':    {'tools': {'Read','Glob','Grep'}, 'context': 'fork', 'level': '2'},
    'agents/henkaten-detector.md': {'tools': {'Read','Glob','Grep'}, 'context': 'fork', 'level': '1'},
    'agents/retrospective.md':     {'tools': {'Read','Glob','Grep'}, 'context': 'fork', 'level': '2'},
}
for path, spec in EXPECTED.items():
    fp = pathlib.Path(path)
    if not fp.exists():
        errors.append(f'MISSING agent: {path}'); continue
    text = fp.read_text(encoding='utf-8')
    m = re.match(r'^---\s*\n(.*?)\n---', text, re.DOTALL)
    if not m:
        errors.append(f'{path}: no YAML frontmatter'); continue
    fm = m.group(1)
    lines = fm.splitlines()
    tools_block = []; in_tools = False
    for l in lines:
        if re.match(r'\s*tools\s*:', l, re.IGNORECASE):
            tools_block.append(l); in_tools = True
        elif in_tools:
            if re.match(r'\s{2,}', l): tools_block.append(l)
            else: break
    declared = set(re.findall(r'Read|Glob|Grep|Bash|Write|Task', '\n'.join(tools_block)))
    if declared != spec['tools']:
        errors.append(f'{path}: tools={declared}, expected={spec[\"tools\"]}')
    ctx_line = next((l for l in lines if 'context' in l.lower()), '')
    if spec['context'] not in ctx_line:
        errors.append(f'{path}: missing context \"{spec[\"context\"]}\"')
    lvl_line = next((l for l in lines if 'level' in l.lower()), '')
    if not re.search(r'level:\s*' + re.escape(spec['level']) + r'\b', lvl_line):
        errors.append(f'{path}: missing level {spec[\"level\"]}')

if errors:
    for e in errors: print('FAIL:', e)
    sys.exit(1)
print('ALL PASS')
"
```

Pass condition: prints `ALL PASS` and exits 0.

Maps to: sprint-2/3/4/5 regression gate

---

### LLM-as-judge (weights sum to 33%)

**SC-11 [weight: 15%] — `skills/council-autorun/SKILL.md` step-by-step correctness: each named step describes the spec-required behavior**

The judge reads `skills/council-autorun/SKILL.md` and scores each step against the following rubric dimensions:

1. **Step 1A — Pre-sprint henkaten check** (§8.2): The step directs the orchestrator to diff the plugin manifest against the previous sprint baseline, check for unresolved henkaten records in `.council/henka-register.jsonl`, and classify any newly detected changes on the 4M axis with `change_origin`. It specifies what "unresolved" means (records without a `closed_at` timestamp or equivalent). Scheduled-vs-unscheduled suppression: the step describes how henkaten-detector reads sprint scope from `tasks.json` / contract / `sprints.json` in priority order with a fail-safe bypass and coverage warning.

2. **Step 1A.5 — Yokoten review** (§8.2, A9): The step surfaces adaptation prompts from prior henkaten records' `yokoten` blocks. The ratify-once shortcut (for yokoten naming ≥3 sprints or `"all"`) is described. The orchestrator does not execute yokoten changes — it surfaces them to the user.

3. **Step 1C — Fan-out + andon handling + verification spot-check** (§8.2, A6): The step specifies that fan-out is sequential by default (per Q6) but swarm dispatch for andon is unconditionally parallel (A6). It directs the orchestrator to run `scripts/run-verification.py` on the verification string of each `observed` claim before fan-out results are accepted. Non-conformant strings are rejected and logged as `agent-capability-change` Henkaten records.

4. **Step 1D — Reversibility check and decision routing** (§8.2, R9): The step distinguishes minor reversible (auto-apply), major reversible (user prompt), and irreversible (nemawashi walkthrough stub, to be fully implemented in sprint 7 S5). The reversibility classification precedes the minor/major classification. The nemawashi stub in sprint 6 records a placeholder DEC entry with `nemawashi_walkthrough_version: null`.

5. **Step 1F — Halt conditions including dynamic autonomy floor** (§8.2, §2.4.3, A2): The step enumerates halt triggers including floor breach. The distinct-originator rule is stated: a floor drop requires ≥2 distinct originator agents issuing `stop` signals; same-agent repeated stops are tracked as pull-rate anomaly, not a floor drop. The halt condition for `andon_signal: stop` is described as unconditional.

6. **Steps 1G, 1H, 1I — Context compaction, mini retrospective, next-cycle trigger** (§8.2): Step 1G describes compaction to `.council/sessions/<timestamp>.md`. Step 1H calls the `/council-retro-mini` skill (stub acceptable in sprint 6). Step 1I describes per-sprint or per-cycle trigger logic.

Score: PASS (full) if all 6 dimensions satisfied; PARTIAL (67% credit) if 4–5 satisfied; PARTIAL (33% credit) if 2–3 satisfied; FAIL if ≤1 satisfied.

Maps to: §8.2, §2.4.3, §6.7, v2.1 amendments A1, A2, A6, A9

---

**SC-12 [weight: 10%] — `scripts/run-verification.py` allowlist correctness: covers the full §7.0.2 allowlist and correctly rejects non-conformant strings**

The judge reads `scripts/run-verification.py` and scores against the following rubric dimensions:

1. **Allowlist coverage** (§7.0.2): The script admits commands starting with the following prefixes: `git diff`, `git show`, `git log`, `git status`, `git branch`, `git ls-files` (read-only git); `grep`, `rg` (read-only search); `cat`, `head`, `tail` (read-only file inspection); `jq` without `-i` flag; `python -m json.tool`, `python scripts/validate-` (validation helpers); POSIX `test` / `[` expressions. The allowlist is implemented as a prefix-match list or equivalent, not an open-ended regex.

2. **Rejection policy** (§7.0.2, A1): Commands not matching any allowlist prefix are rejected before execution. The rejection message identifies the specific non-conformant command string. The script does NOT execute the command even partially before checking the allowlist. Write operations (`git push`, `git commit`, `git add`, redirects `>`, `>>`), network calls (`curl`, `wget`, `requests`), pipe-to-shell patterns (`` `...` ``, `$(...)`), `eval`, and `exec` are explicitly rejected.

3. **10-second timeout** (§7.0.2): The script enforces a default 10-second execution timeout via `subprocess.run(timeout=10)` or equivalent. A `--timeout N` flag overrides the default (enables test isolation). On timeout the script terminates the subprocess and exits non-zero with a message identifying the command that timed out.

4. **`agent-capability-change` Henkaten logging** (§7.0.2, A1): When a non-conformant string is rejected, the script logs (or describes how to log) an `agent-capability-change` Henkaten record. At minimum it prints a structured JSON block to stderr or stdout that includes `event_type: "agent-capability-change"`, the rejected command string, and a timestamp. Full schema-conformant logging via `scripts/append-henka.py` is a bonus.

Score: PASS if all 4 dimensions satisfied; PARTIAL (50% credit) if 2–3 satisfied; FAIL if ≤1 satisfied.

Maps to: §7.0.2, v2.1 amendment A1

---

**SC-13 [weight: 8%] — `instructions/andon-protocol.md` materially extends the sprint-2 baseline**

The judge reads `instructions/andon-protocol.md` and scores against the following rubric dimensions:

1. **Verbatim acknowledgment** (§7.0.1, A10): The file contains the verbatim text "Thank you for stopping the line. Your signal has been received and will be honored. No further sprint steps will proceed until this is resolved." (or the spec-required verbatim phrase). The file indicates this must be written before any analytical response.

2. **Alert vs stop semantics** (§7.0.1): Both signal types are defined with distinct orchestrator behaviors: `alert` triggers a bounded swarm (parallel, ≤4 agents, `andon_takt_seconds`-bounded, auto-escalates to `stop` on timeout); `stop` causes immediate halt with no further fan-out, awaiting `/council-review`.

3. **Rule 4 carve-out** (A10): The file explicitly names the Rule 4 Bounded Self-Organization constraint and explains why `stop` bypasses it (jidoka / distributed halt authority). The carve-out is non-negotiable — `stop` cannot be filtered or deferred by the orchestrator for any reason.

4. **Pull-rate tracking and distinct-originator corroboration** (§2.4.3, A2): The file references pull-rate tracking per agent in `audit-log.jsonl`. Anomalous pull-rates (same agent, ≥3 consecutive stops) are flagged as `quality-defect-anomaly` Henkaten, NOT as floor-drop triggers. The floor-drop trigger requires ≥2 distinct originator agents.

Score: PASS if all 4 dimensions satisfied; PARTIAL (50% credit) if 2–3 satisfied; FAIL if ≤1 satisfied.

Maps to: §7.0.1, §2.4.3, v2.1 amendment A10

---

## Should-NOT Criteria (Gate — Any Failure Blocks the Sprint)

**Gate 1 — The autorun skill MUST NOT reference or execute against the actual `.council/` directory of this repo**

`.council/` does not exist in this repo. Any reference in `skills/council-autorun/SKILL.md` to operational `.council/` paths must be in the context of a target project (the dummy-project fixture), not this repository's root.

Verification:
```python
python -c "
import pathlib, sys

errors = []
# .council/ must not have been created in this repo
if pathlib.Path('.council').exists():
    errors.append('GATE FAIL: .council/ directory was created in the plugin repo')

if errors:
    for e in errors: print(e)
    sys.exit(1)
print('GATE PASS')
"
```

---

**Gate 2 — `scripts/run-verification.py` MUST NOT execute commands outside the §7.0.2 allowlist**

The script must reject non-allowlisted commands before execution. A command like `rm -rf /tmp/test` must be rejected, not executed.

Verification:
```python
python -c "
import subprocess, sys, pathlib

if not pathlib.Path('scripts/run-verification.py').exists():
    print('GATE SKIP: run-verification.py missing (caught by SC-1)'); sys.exit(0)

# rm -rf is definitely not in the allowlist; must be rejected (non-zero exit)
r = subprocess.run(
    [sys.executable, 'scripts/run-verification.py', '--check-only', 'rm -rf /tmp/gate2test'],
    capture_output=True, text=True
)
if r.returncode == 0:
    print('GATE FAIL: run-verification.py accepted a non-allowlisted rm command')
    sys.exit(1)
print('GATE PASS')
"
```

---

**Gate 3 — `scripts/run-verification.py` MUST NOT make network calls**

No verification script may contain `curl`, `wget`, `Invoke-WebRequest`, `requests.get`, `urllib.request.urlopen`, or equivalent network-access patterns.

Verification:
```python
python -c "
import pathlib, sys, re

errors = []
network_patterns = [r'\bcurl\b', r'\bwget\b', r'Invoke-WebRequest', r'Invoke-RestMethod',
                    r'requests\.get', r'requests\.post', r'urllib\.request\.urlopen']
p = pathlib.Path('scripts/run-verification.py')
if p.exists():
    text = p.read_text(encoding='utf-8')
    for pat in network_patterns:
        if re.search(pat, text):
            errors.append(f'GATE FAIL: run-verification.py contains network-call pattern {pat!r}')
if errors:
    for e in errors: print(e)
    sys.exit(1)
print('GATE PASS')
"
```

---

**Gate 4 — The autorun skill MUST NOT trigger an infinite-loop autorun or dispatch itself as a sub-skill**

`skills/council-autorun/SKILL.md` must not contain a recursive call to `/henkaten-council:council-autorun` (or any self-invocation pattern).

Verification:
```python
python -c "
import pathlib, sys, re

p = pathlib.Path('skills/council-autorun/SKILL.md')
if not p.exists():
    print('GATE SKIP: SKILL.md missing (caught by SC-1)'); sys.exit(0)

text = p.read_text(encoding='utf-8')
# Reject self-invocation patterns
if re.search(r'council-autorun.*council-autorun|/henkaten-council:council-autorun.*Step', text, re.IGNORECASE):
    print('GATE FAIL: SKILL.md contains potential self-invocation pattern')
    sys.exit(1)
print('GATE PASS')
"
```

---

**Gate 5 — The autorun skill MUST reference (not implement) the nemawashi walkthrough for major/irreversible decisions; full walkthrough is sprint 7 territory**

`skills/council-autorun/SKILL.md` Step 1D must acknowledge that the full nemawashi walkthrough is deferred to S5 (sprint 7). It must include a placeholder DEC entry (e.g., `nemawashi_walkthrough_version: null`) within or adjacent to the Step 1D section. It must not implement the full four-stage walkthrough.

Verification:
```python
python -c "
import pathlib, sys, re

p = pathlib.Path('skills/council-autorun/SKILL.md')
if not p.exists():
    print('GATE SKIP: SKILL.md missing (caught by SC-1)'); sys.exit(0)

text = p.read_text(encoding='utf-8')
errors = []

# Must contain nemawashi_walkthrough_version (placeholder DEC entry)
if not re.search(r'nemawashi_walkthrough_version', text, re.IGNORECASE):
    # Fallback: accept 'nemawashi' appearing within 500 chars of 'Step 1D' heading
    m = re.search(r'step\s+1D', text, re.IGNORECASE)
    if m:
        window = text[max(0, m.start()-100):m.start()+600]
        if not re.search(r'nemawashi', window, re.IGNORECASE):
            errors.append('GATE FAIL: SKILL.md Step 1D section makes no reference to nemawashi placeholder')
    else:
        errors.append('GATE FAIL: SKILL.md contains no nemawashi_walkthrough_version and no Step 1D section')

if errors:
    for e in errors: print(e)
    sys.exit(1)
print('GATE PASS')
"
```

---

**Gate 6 — Cross-sprint scope drift: only declared sprint-6 files were added or modified since sprint-5 harness checkpoint commit `171444e`**

Verification:
```python
python -c "
import subprocess, sys

ALLOWED_NEW = {
    'skills/council-autorun/SKILL.md',
    'scripts/run-verification.py',
    'tests/scripts/test-run-verification.py',
    'tests/fixtures/dummy-project/.harness/config.json',
    'tests/fixtures/dummy-project/.harness/spec.md',
    'tests/fixtures/dummy-project/.harness/sprints.json',
    'tests/test-s4-acceptance.py',
    'tests/test-s4-acceptance.sh',
    '.harness/contracts/sprint-06.md',
    'instructions/andon-protocol.md',
}
# Accept any file under tests/fixtures/dummy-project/src/
ALLOWED_MODIFY = {
    '.harness/progress.md',
    '.harness/sprint-state.json',
}

result = subprocess.run(
    ['git', 'diff', '--name-only', '--diff-filter=ACM', '171444e..HEAD'],
    capture_output=True, text=True
)
if result.returncode != 0:
    print('GATE FAIL: git diff command failed:', result.stderr.strip()); sys.exit(1)

changed = [l.strip() for l in result.stdout.splitlines() if l.strip()]
errors = []
for f in changed:
    # Allow pre-sprint-6 cleanup commits that are in this baseline range
    # Authoritative list from: git show --name-only --format= cc97a86 fd9960c 49e50a8 345eed5 | sort -u
    pre_sprint6_cleanup = {
        '.claude-plugin/plugin.json',
        '.gitignore',
        '.harness/sprint-06-playbook.md',
        'docs/design/discovery_gate.md',
        'docs/phase-0-proposal-supplement.md',
        'docs/phase-0-proposal-v2.md',
        'docs/phase-0-proposal.md',
        'hooks/session-stopped-marker.sh',
        'hooks/win/session-stopped-marker.ps1',
    }
    if f in pre_sprint6_cleanup:
        continue
    if f.startswith('tests/fixtures/dummy-project/src/'):
        continue
    if f not in ALLOWED_NEW and f not in ALLOWED_MODIFY:
        errors.append(f'GATE FAIL: unexpected file outside sprint-6 scope: {f!r}')
if errors:
    for e in errors: print(e)
    sys.exit(1)
print('GATE PASS')
"
```

Pass condition: prints `GATE PASS` and exits 0.

---

## Reference Solutions

**Reference for SC-11 (heaviest LLM-judge criterion) — expected control-flow shape for Step 1C fan-out and Step 1F halt conditions:**

```
## Step 1C — Fan-Out, Andon Handling, and Verification Spot-Check

Default dispatch mode: sequential (Q6 default).
Swarm dispatch on andon: unconditionally parallel (v2.1 A6).

For each agent in the fan-out roster:
  1. Dispatch agent (sequential Task call unless swarm context).
  2. Receive agent output.
  3. If output contains andon_signal:
       - Write thank-the-puller acknowledgment VERBATIM before any other action.
       - If type == "stop": jump to Step 1F immediately; skip remaining agents.
       - If type == "alert": dispatch swarm (parallel, ≤4 agents, takt-bounded);
           if swarm unresolved within andon_takt_seconds: escalate to stop → Step 1F.
  4. For each evidence claim with evidence_class == "observed":
       a. Extract the claim's verification string.
       b. Call: python scripts/run-verification.py "<verification_string>"
       c. If exit non-zero (non-conformant string):
            - Reject the claim.
            - Log agent-capability-change Henkaten record:
                { fourM_axis: "Machine", change_origin: "active",
                  description: "Non-conformant verification string rejected",
                  rejected_string: "<string>", agent_id: "<agent>" }
            - Flag the agent output as partially unverified (proceed with caution).
  5. Collect verified agent outputs for Step 1D.

## Step 1F — Halt Conditions

The sprint loop halts if ANY of the following are true:

1. andon_signal: stop received from any agent — UNCONDITIONAL halt.
   No filter, no deferral, no second-guessing.

2. Dynamic autonomy floor breach — current effective_autonomy.level has dropped
   below the operational minimum (default: level 3).
   Floor-drop trigger requires: >= 2 DISTINCT originator agents each issuing
   an independent stop signal within the current sprint loop.
   Same-agent repeated stops = pull-rate anomaly (logged as quality-defect-anomaly
   Henkaten) — does NOT count toward floor drop. Single agent cannot drop the floor.

3. Verification spot-check failure rate > threshold — if >= N% of observed claims
   across all agents fail the allowlist check, halt and surface the pattern.

4. Schema validation failure on a controlled artifact append — if append-henka.py
   or append-decision.py returns non-zero, halt before the record is partially written.

On halt: write a decision-log entry with decision_type: "sprint-halt",
describe the trigger, and surface to the user. Sprint does not auto-resume.
Restart requires explicit /council-review invocation.
```

The above sketch shows the expected control-flow shape; an implementation may use different prose as long as it captures these invariants.

---

## Out of Scope

- **Full nemawashi walkthrough** (Steps 1D Stages 1–4) — sprint 7 (S5) deliverable. Sprint 6 ships a stub reference only.
- **`skills/council-review/SKILL.md`** — sprint 7 (S5) deliverable.
- **`skills/council-retro/SKILL.md`, `skills/council-retro-mini/SKILL.md`, `skills/council-jishuken/SKILL.md`** — sprint 8 (S6) deliverables.
- **`skills/council-detect/SKILL.md`** — sprint 8 (S6) deliverable.
- **`agents/retrospective.md` pdca/jishuken modes full implementation** — sprint 8 (S6) deliverable.
- **Live integration with `.council/`** — `.council/` does not exist in this repo; all write-path tests use the dummy-project fixture or temp directories.
- **Hook installation in `.claude/settings.json`** — hooks shipped in sprint 5; their registration is end-to-end-tested via the dummy-project fixture in this sprint, not via modification of the repo's own settings.
- **Actual execution of `/trine-eval:harness-sprint`** — Step 1B describes the delegation; the acceptance test verifies the skill's orchestration logic, not a live trine-eval run.
- **`agents/qa-regression.md` and `agents/rag-source.md`** — status: proposed; not in default fan-out (sprint 2 baseline; no changes in sprint 6).

---

## Technical Notes

**`scripts/run-verification.py` allowlist (§7.0.2):** Admitted prefix terms:
- `git diff`, `git show`, `git log`, `git status`, `git branch`, `git ls-files` (read-only git)
- `grep`, `rg` (read-only search; no `--include` that writes)
- `cat`, `head`, `tail` (read-only file inspection)
- `jq` (no `-i` in-place flag)
- `python -m json.tool`, `python scripts/validate-` (schema validation helpers)
- POSIX `test`, `[` (test expressions)

Disallowed: write operations (`git push`, `git commit`, `git add`, `git reset`, `git rebase`, `git merge`, `rm`, `mv`, `cp` to writable locations), network calls (`curl`, `wget`, requests library), shell redirects (`>`, `>>`), pipe-to-shell (`` `...` ``, `$(...)`), `eval`, `exec`, project-source execution.

The `--check-only` flag performs the allowlist check without executing the command — used for testing.

**Dynamic autonomy floor (§2.4.3, A2):** Distinct-originator corroboration. A single agent issuing N andon-stops counts as 1 originator; the floor drops only when ≥2 different agents independently issue `stop` signals. `update-effective-autonomy.py` (sprint 4) writes the new level; SKILL.md Step 1F is the only place that decides whether to call it.

**§15.5 acceptance assertions 1–6 (dummy-project target):**
1. `scripts/run-verification.py` with an allowed command exits 0 against the fixture.
2. `scripts/run-verification.py` with a disallowed command exits non-zero.
3. `skills/council-autorun/SKILL.md` exists and contains all 10 step headings.
4. `instructions/andon-protocol.md` contains the verbatim thank-the-puller text.
5. The dummy-project fixture has valid JSON in `.harness/config.json` and `.harness/sprints.json`.
6. `tests/scripts/test-run-verification.py` exits 0 (fixture unit tests pass).

**Cross-sprint baseline ref:** `171444e` is the sprint-5 harness checkpoint commit (`harness: complete sprint 05 evaluation`). Gate 6 uses `git diff --name-only --diff-filter=ACM 171444e..HEAD`. Pre-sprint-6 cleanup commits (cc97a86, fd9960c, 49e50a8, 345eed5) fall between this baseline and sprint 6 HEAD; they are explicitly allowed in the ALLOWED sets.

**Partial-credit-friendly SC pattern:** SC-6 uses per-step grep — each missing step is a separate `errors.append` line. If SKILL.md ships Steps 1A–1F but not 1G–1I, SC-6 fails (exit 1) but the LLM-judge SC-11 can still award partial weight for the steps that are present. Contract authors should favor this pattern over atomic all-or-nothing checks for large deliverables.

**Dummy-project fixture scope:** The fixture needs only to be a minimal valid trine-eval project. Two trivial features (e.g., "a hello-world function") and two sprints (sprint 1 ships the feature, sprint 2 adds a test) are sufficient. The `src/` directory needs at minimum one stub file (e.g., `src/hello.py` with a single function). No real trine-eval evaluation is executed against it — the acceptance test exercises the presence and structural validity of the fixture.

**`andon-protocol.md` enrichment scope:** The sprint-2 baseline already contains significant content (verified from the existing file). Sprint 6's deliverable is to ensure the file contains all required elements from §7.0.1 and A10, particularly the verbatim acknowledgment text and the pull-rate / distinct-originator corroboration rules. If the sprint-2 baseline already contains these elements (as observed), SC-7 and SC-13 will pass based on the existing content — no change is required. The enrichment SC rewards implementations that materially extend the baseline; a baseline that is already complete receives full credit.

---

**Task taxonomy handoff:** Once this contract is approved by the Evaluator, a sibling `.harness/contracts/sprint-06.tasks.json` is emitted (guarded by `config.taxonomy.emit_tasks_json`, default `true`). It contains one JSON entry per criterion above — both Success Criteria and Should-NOT gates — with stable `task_id`s, `grader_type`, `weight`, `is_gate`, `verification_command`, and `rubric_dimension`. Downstream sprints (regression gate, Batch API, transcript capture, adversarial hygiene) consume that JSON; this markdown contract remains the human-readable source of truth. See `skills/sprint-contract/SKILL.md` for the schema.

## Evaluator Review

**Status: APPROVED**

**Round:** 2 (final)

### Summary

All three B/M items from round 1 are resolved. B1 (phantom files) is fully fixed: the `pre_sprint6_cleanup` set in Gate 6 now lists exactly the 9 files confirmed by `git show --name-only --format= cc97a86 fd9960c 49e50a8 345eed5 | sort -u` — no phantom `docs/design-doc-v2.md` or `docs/status.md`. M1 (step count) is fixed: Scope now reads "all ten named steps" with no occurrence of "nine". All three minors are addressed: SC-2 tests `--check-only` flag recognition, SC-9 note cross-references the six §15.5 assertions requirement (backed by SC-11), and Gate 5 requires the literal `nemawashi_walkthrough_version` string before falling back to the looser window search.

Weight tally: SC-1 through SC-10 = 7+6+8+8+7+8+7+6+5+5 = **67%** deterministic; SC-11+SC-12+SC-13 = 15+10+8 = **33%** LLM-judge. Total = **100%**. Valid.

Gate 6 runs clean against current HEAD (only the 9 pre-sprint-6 cleanup files appear in the diff, all of which are in the allowlist). Authoritative file list verified against actual git history.

### Blockers

None.

### Majors

None.

### Minors (informational, not blocking)

**Minor A — SC-9 note mislabels the SC-11 backstop dimension.** The SC-9 note states a trivially-passing test that asserts nothing will fail SC-11 dimension 6. SC-11 dimension 6 covers Steps 1G/1H/1I (context compaction, mini-retro, trigger), not acceptance-test assertion completeness. The prose concern is real but the dimension number is wrong. No mechanical impact — SC-9 deterministic still runs the test, and an LLM judge evaluating SC-11 will apply common sense. Informational only; not a blocker.

### Approved Criteria

SC-1, SC-2, SC-3, SC-4, SC-5, SC-6, SC-7, SC-8, SC-9, SC-10 (deterministic — verification commands are executable, pass conditions are unambiguous)

SC-11, SC-12, SC-13 (LLM-judge — rubric dimensions are specific and enumerated; SC-11 has a reference solution)

Gate 1, Gate 2, Gate 3, Gate 4, Gate 5, Gate 6 (all gates have executable verification commands; Gate 6 verified clean against live HEAD)
