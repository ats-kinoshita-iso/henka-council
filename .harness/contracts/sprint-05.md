# Sprint 05 Contract — S3 Hooks + Reversibility + Effective-Autonomy Tracking

## Scope

Sprint 5 ships the four Claude Code PreToolUse/PostToolUse/Stop hooks (both Bash and PowerShell flavors), the audit-log rotation script, a CI workflow that exercises both platforms, and the fixture tests that verify each hook's ALLOW and BLOCK paths. The Bash hooks (`enforce-append-only.sh`, `enforce-reversibility.sh`, `log-tool-call.sh`, `session-stopped-marker.sh`) are the authoritative implementations; four PowerShell equivalents under `hooks/win/` provide Windows parity per v2.1 amendment A7. The rotation script (`scripts/rotate-audit-log.py`) rotates `.council/audit-log.jsonl` at a 50 MB threshold, producing a timestamped gzip archive, a fresh empty current file, and a `DEC` entry with the archive's SHA-256. No `.council/` directory is created in the repo during this sprint; all write-path tests use isolated temporary directories or controlled temp files.

---

## Files in Scope

**New Bash hooks (4 files):**
- `hooks/enforce-append-only.sh` — PreToolUse: blocks `Write`/`Edit` against `.council/henka-register.jsonl`, `.council/decision-log.jsonl`, `.council/audit-log.jsonl`; reads envelope from stdin; exit 0 = allow, non-zero = block **[NEW]**
- `hooks/enforce-reversibility.sh` — PreToolUse: reads `.council/state/effective-autonomy.json` `level`; blocks irreversible Bash commands when `level < 5`; exit 0 = allow, non-zero = block **[NEW]**
- `hooks/log-tool-call.sh` — PostToolUse: appends one JSON line to `.council/audit-log.jsonl` conforming to `schemas/audit-log-entry.schema.json`; tracks `andon_pull_count` per agent **[NEW]**
- `hooks/session-stopped-marker.sh` — Stop: appends `SESSION_STOPPED` marker line to `.harness/progress.md` **[NEW]**

**New PowerShell hooks (4 files):**
- `hooks/win/enforce-append-only.ps1` — PowerShell equivalent of `enforce-append-only.sh` **[NEW]**
- `hooks/win/enforce-reversibility.ps1` — PowerShell equivalent of `enforce-reversibility.sh` **[NEW]**
- `hooks/win/log-tool-call.ps1` — PowerShell equivalent of `log-tool-call.sh` **[NEW]**
- `hooks/win/session-stopped-marker.ps1` — PowerShell equivalent of `session-stopped-marker.sh` **[NEW]**

**New Python script (1 file):**
- `scripts/rotate-audit-log.py` — rotates `.council/audit-log.jsonl` at 50 MB threshold; produces gzip archive, fresh empty current file, and DEC entry via `scripts/append-decision.py` with SHA-256 hash; CLI: `--threshold-bytes N`, `--file <path>`, `--decision-output <path>` for test isolation **[NEW]**

**New CI configuration (1 file):**
- `.github/workflows/ci.yml` — matrix job over `ubuntu-latest` and `windows-latest`; installs Python ≥3.10; runs hook fixture tests for `enforce-append-only`, `enforce-reversibility`, `log-tool-call`, `rotate-audit-log`; exits 0 only when all combinations pass **[NEW]**

**New hook fixture tests (4 bash + 4 PowerShell + 1 Python test = 9 files):**
- `tests/hooks/test-enforce-append-only.sh` — Bash: ALLOW path (non-protected file) and BLOCK path (Write against audit-log.jsonl) **[NEW]**
- `tests/hooks/test-enforce-reversibility.sh` — Bash: ALLOW path (level=5 or non-Bash tool) and BLOCK path (level=3 + `git push`) **[NEW]**
- `tests/hooks/test-log-tool-call.sh` — Bash: appends audit entry and asserts schema-valid line written **[NEW]**
- `tests/hooks/test-rotate-audit-log.sh` — Bash: uses `--threshold-bytes` to keep fixtures small; asserts archive exists, SHA-256 matches, source file reset, DEC entry emitted; asserts idempotency **[NEW]**
- `tests/hooks/win/test-enforce-append-only.ps1` **[NEW]**
- `tests/hooks/win/test-enforce-reversibility.ps1` **[NEW]**
- `tests/hooks/win/test-log-tool-call.ps1` **[NEW]**
- `tests/hooks/win/test-rotate-audit-log.ps1` **[NEW]**
- `tests/hooks/test-rotate-audit-log.py` — Python: runs `scripts/rotate-audit-log.py` via `subprocess`; full end-to-end including DEC entry validation against schema **[NEW]**

---

## Success Criteria

### Deterministic (weights sum to 72%)

<!-- SC weights: SC-1(6)+SC-2(6)+SC-3(7)+SC-4(7)+SC-5(6)+SC-6(8)+SC-7(6)+SC-8(7)+SC-9(7)+SC-10(6)+SC-11(6) = 72% -->

---

**SC-1 [weight: 6%] — All declared files exist at their specified paths and have valid syntax**

Input: check file existence and parse each file with the appropriate syntax checker.

Verification:
```python
python -c "
import pathlib, ast, sys, subprocess

errors = []

# All new files must exist
files = [
    'hooks/enforce-append-only.sh',
    'hooks/enforce-reversibility.sh',
    'hooks/log-tool-call.sh',
    'hooks/session-stopped-marker.sh',
    'hooks/win/enforce-append-only.ps1',
    'hooks/win/enforce-reversibility.ps1',
    'hooks/win/log-tool-call.ps1',
    'hooks/win/session-stopped-marker.ps1',
    'scripts/rotate-audit-log.py',
    '.github/workflows/ci.yml',
    'tests/hooks/test-enforce-append-only.sh',
    'tests/hooks/test-enforce-reversibility.sh',
    'tests/hooks/test-log-tool-call.sh',
    'tests/hooks/test-rotate-audit-log.sh',
    'tests/hooks/win/test-enforce-append-only.ps1',
    'tests/hooks/win/test-enforce-reversibility.ps1',
    'tests/hooks/win/test-log-tool-call.ps1',
    'tests/hooks/win/test-rotate-audit-log.ps1',
    'tests/hooks/test-rotate-audit-log.py',
]
for f in files:
    if not pathlib.Path(f).exists():
        errors.append(f'MISSING: {f}')

# Python syntax check
for f in ['scripts/rotate-audit-log.py', 'tests/hooks/test-rotate-audit-log.py']:
    p = pathlib.Path(f)
    if p.exists():
        try:
            ast.parse(p.read_text(encoding='utf-8'))
        except SyntaxError as e:
            errors.append(f'SYNTAX ERROR in {f}: {e}')

if errors:
    for e in errors: print(e)
    sys.exit(1)
print('ALL PRESENT AND VALID SYNTAX')
"
```

Pass condition: prints `ALL PRESENT AND VALID SYNTAX` and exits 0.

Maps to: §9.4, §13, §15.5, v2.1 amendments A7/A12

---

**SC-2 [weight: 6%] — Bash hook syntax check: all 4 Bash hooks parse cleanly**

Input: run `bash -n` on each Bash hook.

Verification:
```python
python -c "
import subprocess, sys

errors = []
hooks = [
    'hooks/enforce-append-only.sh',
    'hooks/enforce-reversibility.sh',
    'hooks/log-tool-call.sh',
    'hooks/session-stopped-marker.sh',
]
for h in hooks:
    r = subprocess.run(['bash', '-n', h], capture_output=True, text=True)
    if r.returncode != 0:
        errors.append(f'BASH SYNTAX ERROR in {h}: {r.stderr.strip()}')

if errors:
    for e in errors: print(e)
    sys.exit(1)
print('ALL BASH HOOKS VALID SYNTAX')
"
```

Pass condition: prints `ALL BASH HOOKS VALID SYNTAX` and exits 0.

Maps to: §9.4

---

**SC-3 [weight: 7%] — `enforce-append-only` hook ALLOW and BLOCK paths: Bash fixture test passes**

Input: run `tests/hooks/test-enforce-append-only.sh`. The test must construct a tool-call envelope JSON, pipe it to the hook, and assert correct exit codes for both ALLOW (non-protected file → exit 0) and BLOCK (Write against `.council/audit-log.jsonl` → non-zero exit).

Verification:
```
bash tests/hooks/test-enforce-append-only.sh
```

Pass condition: exits 0. Any ALLOW path that exits non-zero or BLOCK path that exits 0 causes the test to fail with a descriptive message.

Maps to: §9.4, §15.5

---

**SC-4 [weight: 7%] — `enforce-reversibility` hook ALLOW and BLOCK paths: Bash fixture test passes**

Input: run `tests/hooks/test-enforce-reversibility.sh`. The test must create a temp `effective-autonomy.json` at level 3, pipe a `Bash` tool-call envelope with `git push origin main` command to the hook, and assert non-zero exit (BLOCK). Then set level to 5, pipe the same envelope, and assert exit 0 (ALLOW). Additionally assert that a non-Bash tool call (`Write` tool) always exits 0 regardless of level.

Verification:
```
bash tests/hooks/test-enforce-reversibility.sh
```

Pass condition: exits 0.

Maps to: §9.4.2, R9

---

**SC-5 [weight: 6%] — `log-tool-call` hook writes a schema-valid audit entry: Bash fixture test passes**

Input: run `tests/hooks/test-log-tool-call.sh`. The test must pipe a PostToolUse envelope to the hook targeting a temp `audit-log.jsonl`, then validate the appended line against `schemas/audit-log-entry.schema.json` using Python's `jsonschema`.

Verification:
```
bash tests/hooks/test-log-tool-call.sh
```

Pass condition: exits 0. The appended audit-log line must parse as JSON and validate against the schema.

Maps to: §9.4, Q14, §11.6

---

**SC-6 [weight: 8%] — `rotate-audit-log.py` end-to-end: archive produced, SHA-256 matches, source reset, DEC entry emitted, idempotent**

Input: run `tests/hooks/test-rotate-audit-log.py` directly.

Verification:
```
python tests/hooks/test-rotate-audit-log.py
```

Pass condition: exits 0. The test must independently verify:
1. A file above `--threshold-bytes` triggers rotation: archive `.council/audit-log.<timestamp>.jsonl.gz` exists.
2. `hashlib.sha256` of the archive contents matches the SHA-256 recorded in the DEC entry (decoding the `.gz` and re-hashing the original bytes OR matching the DEC entry's recorded hash of the gz file — whichever convention the script documents).
3. After rotation the current `audit-log.jsonl` (or `--file` path) is empty (zero bytes or absent).
4. A DEC entry was appended to `decision-log.jsonl` (or `--decision-output` path) and validates against `schemas/decision-log-entry.schema.json`.
5. Running the script a second time on the already-rotated (now empty) file with the same threshold exits 0 with no new archive created (idempotent).

Maps to: §13, v2.1 amendment A12

---

**SC-7 [weight: 6%] — CI YAML parses as valid YAML and mentions both target platforms**

Input: load `.github/workflows/ci.yml` with Python's `yaml` module; assert both `ubuntu-latest` and `windows-latest` appear in the file.

Verification:
```python
python -c "
import pathlib, sys

errors = []
text = pathlib.Path('.github/workflows/ci.yml').read_text(encoding='utf-8')

# Text-search baseline (always runs — no external dependency required)
if 'ubuntu-latest' not in text:
    errors.append('CI YAML: missing ubuntu-latest platform')
if 'windows-latest' not in text:
    errors.append('CI YAML: missing windows-latest platform')

# Structural YAML parse (runs when pyyaml is available)
try:
    import yaml
    try:
        obj = yaml.safe_load(text)
        if not obj:
            errors.append('CI YAML: parsed to empty/null object')
    except yaml.YAMLError as e:
        errors.append(f'CI YAML parse error: {e}')
except ImportError:
    print('NOTE: pyyaml not installed — structural parse skipped; text-search check still enforced')

if errors:
    for e in errors: print('FAIL:', e)
    sys.exit(1)
print('CI YAML VALID')
"
```

Pass condition: prints `CI YAML VALID` and exits 0. The text-search check (both platform strings present) runs unconditionally; the YAML structural check is an additional gate when `pyyaml` is available.

Maps to: §15.5, v2.1 amendment A7

---

**SC-8 [weight: 7%] — `rotate-audit-log.py` Python syntax is valid and contains no stub markers; no script contains hard-coded absolute paths**

Input: `ast.parse` the rotation script and the Python test fixture; grep for stub markers and absolute paths.

Verification:
```python
python -c "
import pathlib, ast, sys, re

errors = []
py_files = [
    'scripts/rotate-audit-log.py',
    'tests/hooks/test-rotate-audit-log.py',
]
stub_markers = ['TODO', 'PLACEHOLDER', 'TBD', 'pass  # stub', 'raise NotImplementedError']
windows_abs = re.compile(r'[A-Za-z]:\\\\')
posix_abs = re.compile(r\"['\\\"/][a-z]{3,}/\")   # heuristic: '/home/', '/usr/', etc.

for f in py_files:
    p = pathlib.Path(f)
    if not p.exists():
        errors.append(f'MISSING: {f}')
        continue
    text = p.read_text(encoding='utf-8')
    try:
        ast.parse(text)
    except SyntaxError as e:
        errors.append(f'SYNTAX ERROR in {f}: {e}')
    for marker in stub_markers:
        if marker in text:
            errors.append(f'{f}: contains stub marker {marker!r}')
    if windows_abs.search(text):
        errors.append(f'{f}: contains hard-coded Windows absolute path')

if errors:
    for e in errors: print('FAIL:', e)
    sys.exit(1)
print('ALL PASS')
"
```

Pass condition: prints `ALL PASS` and exits 0.

Maps to: §4, §13

---

**SC-9 [weight: 7%] — Cross-sprint regression: all 4 sprint-4 Python scripts still parse; all 5 agent files still pass frontmatter checks**

Input: re-run sprint-4 SC-1 syntax check for the 4 scripts; re-run sprint-4 SC-6 frontmatter check for the 5 agents.

Verification:
```python
python -c "
import pathlib, ast, sys, re

errors = []

# Sprint-4 script syntax regression
for s in ['scripts/append-henka.py', 'scripts/append-decision.py',
          'scripts/compute-evidence-class.py', 'scripts/update-effective-autonomy.py']:
    p = pathlib.Path(s)
    if not p.exists():
        errors.append(f'MISSING (sprint-4 regression): {s}')
        continue
    try:
        ast.parse(p.read_text(encoding='utf-8'))
    except SyntaxError as e:
        errors.append(f'SYNTAX ERROR (sprint-4 regression) in {s}: {e}')

# Sprint-2/3/4 agent frontmatter regression
EXPECTED = {
    'agents/orchestrator.md':      {'tools': {'Read','Glob','Grep','Bash','Write','Task'}, 'context': 'inherit', 'level': '4'},
    'agents/architect.md':         {'tools': {'Read','Glob','Grep'}, 'context': 'fork', 'level': '2'},
    'agents/scope-guardian.md':    {'tools': {'Read','Glob','Grep'}, 'context': 'fork', 'level': '2'},
    'agents/henkaten-detector.md': {'tools': {'Read','Glob','Grep'}, 'context': 'fork', 'level': '1'},
    'agents/retrospective.md':     {'tools': {'Read','Glob','Grep'}, 'context': 'fork', 'level': '2'},
}
for path, spec in EXPECTED.items():
    text = pathlib.Path(path).read_text(encoding='utf-8')
    m = re.match(r'^---\s*\n(.*?)\n---', text, re.DOTALL)
    if not m:
        errors.append(f'{path}: no YAML frontmatter found')
        continue
    fm = m.group(1)
    lines = fm.splitlines()
    tools_block = []
    in_tools = False
    for l in lines:
        if re.match(r'\s*tools\s*:', l, re.IGNORECASE):
            tools_block.append(l); in_tools = True
        elif in_tools:
            if re.match(r'\s{2,}', l): tools_block.append(l)
            else: break
    tools_text = '\n'.join(tools_block)
    declared = set(re.findall(r'Read|Glob|Grep|Bash|Write|Task', tools_text))
    if declared != spec['tools']:
        errors.append(f'{path}: tools={declared}, expected={spec[\"tools\"]}')
    ctx_line = next((l for l in lines if 'context' in l.lower()), '')
    if spec['context'] not in ctx_line:
        errors.append(f'{path}: context line missing \"{spec[\"context\"]}\"')
    lvl_line = next((l for l in lines if 'level' in l.lower()), '')
    if not re.search(r'level:\s*' + re.escape(spec['level']) + r'\b', lvl_line):
        errors.append(f'{path}: level line missing level {spec[\"level\"]}')

if errors:
    for e in errors: print('FAIL:', e)
    sys.exit(1)
print('ALL PASS')
"
```

Pass condition: prints `ALL PASS` and exits 0.

Maps to: §7.1–§7.5, sprint-2/3/4 regression gate

---

**SC-10 [weight: 6%] — `enforce-append-only` hook correctly identifies all three protected files and only blocks Write/Edit (not Bash or Read)**

Input: construct envelopes for each of the three protected files with `Write` and `Edit` tool names, and also a `Bash` tool call, a `Read` tool call, and a `Write` against a non-protected path. Pipe each to the hook and assert exit codes.

Verification:
```python
python -c "
import subprocess, sys, json, tempfile, pathlib, os

errors = []
hook = 'hooks/enforce-append-only.sh'

cases = [
    # (envelope, expect_block: bool, description)
    ({'tool_name': 'Write', 'tool_args': {'file_path': '.council/henka-register.jsonl'}, 'cwd': '/tmp'}, True, 'Write on henka-register.jsonl must block'),
    ({'tool_name': 'Edit',  'tool_args': {'file_path': '.council/decision-log.jsonl'}, 'cwd': '/tmp'},  True, 'Edit on decision-log.jsonl must block'),
    ({'tool_name': 'Write', 'tool_args': {'file_path': '.council/audit-log.jsonl'}, 'cwd': '/tmp'},     True, 'Write on audit-log.jsonl must block'),
    ({'tool_name': 'Bash',  'tool_args': {'command': 'cat .council/audit-log.jsonl'}, 'cwd': '/tmp'},   False, 'Bash tool must not be blocked'),
    ({'tool_name': 'Read',  'tool_args': {'file_path': '.council/audit-log.jsonl'}, 'cwd': '/tmp'},     False, 'Read tool must not be blocked'),
    ({'tool_name': 'Write', 'tool_args': {'file_path': 'scripts/append-henka.py'}, 'cwd': '/tmp'},      False, 'Write on non-protected file must not be blocked'),
]

for envelope, expect_block, description in cases:
    r = subprocess.run(
        ['bash', hook],
        input=json.dumps(envelope),
        capture_output=True, text=True
    )
    blocked = (r.returncode != 0)
    if blocked != expect_block:
        errors.append(f'FAIL [{description}]: expected block={expect_block}, got returncode={r.returncode}')

if errors:
    for e in errors: print(e)
    sys.exit(1)
print('ALL PASS')
"
```

Pass condition: prints `ALL PASS` and exits 0.

Maps to: §9.4, instructions/controlled-artifacts.md

---

**SC-11 [weight: 6%] — `session-stopped-marker` hook appends the expected marker to a target file**

Input: invoke `hooks/session-stopped-marker.sh` (or `.ps1`) with an empty envelope and a temp target file; assert the marker text appears in the file.

Verification:
```python
python -c "
import subprocess, sys, json, tempfile, pathlib

errors = []
with tempfile.NamedTemporaryFile(mode='w', suffix='.md', delete=False) as f:
    target = pathlib.Path(f.name)

try:
    env_json = json.dumps({'tool_name': 'Stop', 'tool_args': {}, 'cwd': '/tmp'})
    r = subprocess.run(
        ['bash', 'hooks/session-stopped-marker.sh'],
        input=env_json,
        capture_output=True, text=True,
        env={**__import__('os').environ, 'COUNCIL_PROGRESS_FILE': str(target)}
    )
    # Hook may use COUNCIL_PROGRESS_FILE env var OR default to .harness/progress.md
    # Accept either: (a) exit 0 and marker appears in target, or
    # (b) exit 0 and marker appears in .harness/progress.md
    content = target.read_text(encoding='utf-8') if target.exists() else ''
    harness_progress = pathlib.Path('.harness/progress.md')
    harness_content = harness_progress.read_text(encoding='utf-8') if harness_progress.exists() else ''
    if r.returncode != 0:
        errors.append(f'Hook exited {r.returncode}: {r.stderr.strip()}')
    elif 'SESSION_STOPPED' not in content and 'SESSION_STOPPED' not in harness_content:
        errors.append('SESSION_STOPPED marker not found in target file or .harness/progress.md')
finally:
    target.unlink(missing_ok=True)

if errors:
    for e in errors: print('FAIL:', e)
    sys.exit(1)
print('ALL PASS')
"
```

Pass condition: prints `ALL PASS` and exits 0. Note: The test accepts the marker appearing in either the env-var-specified temp file or the default `.harness/progress.md`.

Maps to: §9.4

---

### LLM-as-judge (weights sum to 28%)

**SC-12 [weight: 12%] — Hook protocol correctness: `enforce-append-only.sh` and `enforce-reversibility.sh` correctly implement the Claude Code PreToolUse hook envelope protocol**

The judge reads both Bash hooks and scores against the following rubric dimensions:

1. **Stdin envelope parsing** (§9.4): Both hooks read the tool-call envelope from stdin (via `cat` or `read`). Neither hook assumes command-line arguments for envelope data. The envelope is parsed for `tool_name` and `tool_args` fields using `jq` (or equivalent). If `jq` is absent, the hook fails open (exit 0 with a stderr warning) rather than blocking unintentionally.

2. **`enforce-append-only.sh` targeted blocking** (§9.4): The hook extracts the `file_path` from `tool_args` and compares it against the three protected paths (case-insensitively or via path normalization). It blocks only `Write` and `Edit` tool calls on those paths. `Bash`, `Read`, and all other tools pass through unconditionally. The block message on stderr explains the restriction and points to `scripts/append-{henka,decision}.py` as the approved write path.

3. **`enforce-reversibility.sh` state-file reading** (§9.4.2, R9): The hook reads `.council/state/effective-autonomy.json` and extracts the `level` field. If the file does not exist (`.council/` not yet bootstrapped), the hook fails open — exits 0 with a stderr warning rather than blocking. The irreversibility heuristic matches at least: `git push`, `git reset --hard`, `git rebase`, `git merge`, `rm -rf`, `git filter-branch`, `git push --force` as patterns checked against the `tool_args.command` field when `tool_name == "Bash"`.

4. **Safe failure modes** (§9.4): Neither hook uses `set -e` in a way that causes silent exit on a pipeline failure. Both hooks handle missing/malformed stdin gracefully (empty input → exit 0, not crash). A hook that blocks 100% of tool calls (exit 1 unconditionally) fails this dimension.

Score: PASS if all 4 dimensions satisfied; PARTIAL (50% weight credit) if 2–3 satisfied; FAIL if ≤1 satisfied.

Maps to: §9.4, §9.4.2, R9

---

**SC-13 [weight: 8%] — Bash↔PowerShell parity: the four PowerShell hooks produce identical observable outcomes for matching inputs**

The judge reads corresponding pairs (e.g., `hooks/enforce-append-only.sh` vs `hooks/win/enforce-append-only.ps1`) and scores against the following rubric dimensions:

1. **Envelope parsing parity** (v2.1 A7): Each PowerShell hook reads the envelope from stdin and parses it using `ConvertFrom-Json`. The parsing logic covers the same fields (`tool_name`, `tool_args.file_path`, `tool_args.command`) as its Bash sibling.

2. **Exit-code parity** (v2.1 A7): For every input category (ALLOW / BLOCK) the PowerShell hook exits with the same code (0 or non-zero) as its Bash sibling. `exit 1` in Bash corresponds to `exit 1` in PowerShell — not `throw` without a corresponding `exit`.

3. **Audit entry format parity** (v2.1 A7, `log-tool-call`): The PowerShell `log-tool-call.ps1` appends audit log lines in the same JSON shape as `log-tool-call.sh`. The required fields (`entry_id`, `timestamp`, `event_type`, `agent_id`) are present in both. Field names, types, and enum values match.

4. **SESSION_STOPPED marker parity** (`session-stopped-marker`): The PowerShell `session-stopped-marker.ps1` appends the same `SESSION_STOPPED` marker text to the same target file (or same env-var override mechanism) as `session-stopped-marker.sh`.

Score: PASS if all 4 dimensions satisfied; PARTIAL (50% weight credit) if 2–3 satisfied; FAIL if ≤1 satisfied.

Maps to: v2.1 amendment A7

---

**SC-14 [weight: 8%] — Rotation invariants: `scripts/rotate-audit-log.py` preserves the audit chain and handles edge cases correctly**

The judge reads `scripts/rotate-audit-log.py` and scores against the following rubric dimensions:

1. **SHA-256 chain anchor** (§13, A12): The script computes `hashlib.sha256` of the archive file (the `.gz` file) and includes the hex digest in the DEC entry emitted to `decision-log.jsonl`. The DEC entry includes at minimum: `decision_id`, `timestamp`, `decision_type` (`"audit-log-rotation"`), `decision_outcome`, `autonomy_level_used`, `effective_autonomy_at_decision`, `reversibility`, and a `description` field that carries the archive path, original byte size, and SHA-256 hex digest.

2. **DEC entry via `append-decision.py`** (§13): The rotation script does NOT write directly to `decision-log.jsonl`. It calls `scripts/append-decision.py` (via `subprocess.run`) with the DEC JSON data, so the DEC entry inherits schema validation. The script does not contain a fallback that writes directly to `decision-log.jsonl` if `append-decision.py` fails.

3. **Idempotency** (§13): When the current `audit-log.jsonl` (or `--file` path) is at or below `--threshold-bytes`, the script exits 0 immediately with a "no rotation needed" message and creates no archive. If the file does not exist at all, the script exits 0 with a "file not found, nothing to rotate" message. The script never raises an unhandled exception on missing input.

4. **No archive deletion** (§13, audit-chain integrity): The script does not delete or truncate the archive after creation. The archive is a permanent audit record. The original `audit-log.jsonl` is replaced (truncated to zero or removed and recreated empty) only after the archive is confirmed written and the DEC entry is successfully appended.

Score: PASS if all 4 dimensions satisfied; PARTIAL (50% weight credit) if 2–3 satisfied; FAIL if ≤1 satisfied.

Maps to: §13, v2.1 amendment A12

---

## Should-NOT Criteria (Gate — Any Failure Blocks the Sprint)

**Gate 1 — Hooks MUST exit 0 (not block) when the input envelope does not match the hook's target pattern**

A hook that blocks every tool call regardless of input (e.g., always exits 1) is worse than no hook. The test verifies that at least one ALLOW input produces exit 0 for `enforce-append-only.sh` and `enforce-reversibility.sh`.

Verification:
```python
python -c "
import subprocess, sys, json

errors = []

# enforce-append-only: Write on a non-protected file must exit 0
allow_envelope = json.dumps({'tool_name': 'Write', 'tool_args': {'file_path': 'README.md'}, 'cwd': '/tmp'})
r = subprocess.run(['bash', 'hooks/enforce-append-only.sh'], input=allow_envelope, capture_output=True, text=True)
if r.returncode != 0:
    errors.append(f'GATE FAIL: enforce-append-only.sh blocked a Write on README.md (non-protected file); exit {r.returncode}')

# enforce-reversibility: non-Bash tool must exit 0 regardless of level
allow_envelope2 = json.dumps({'tool_name': 'Write', 'tool_args': {'file_path': 'foo.txt'}, 'cwd': '/tmp'})
r2 = subprocess.run(['bash', 'hooks/enforce-reversibility.sh'], input=allow_envelope2, capture_output=True, text=True)
if r2.returncode != 0:
    errors.append(f'GATE FAIL: enforce-reversibility.sh blocked a Write tool call (non-Bash); exit {r2.returncode}')

if errors:
    for e in errors: print(e)
    sys.exit(1)
print('GATE PASS')
"
```

---

**Gate 2 — Hooks MUST NOT make network calls**

No hook or rotation script may contain `curl`, `wget`, `Invoke-WebRequest`, `Invoke-RestMethod`, `requests.get`, or equivalent network-access patterns.

Verification:
```python
python -c "
import pathlib, sys, re

errors = []
network_patterns = [r'\bcurl\b', r'\bwget\b', r'Invoke-WebRequest', r'Invoke-RestMethod',
                    r'requests\.get', r'requests\.post', r'urllib\.request\.urlopen']
files_to_check = [
    'hooks/enforce-append-only.sh', 'hooks/enforce-reversibility.sh',
    'hooks/log-tool-call.sh', 'hooks/session-stopped-marker.sh',
    'hooks/win/enforce-append-only.ps1', 'hooks/win/enforce-reversibility.ps1',
    'hooks/win/log-tool-call.ps1', 'hooks/win/session-stopped-marker.ps1',
    'scripts/rotate-audit-log.py',
]
for f in files_to_check:
    p = pathlib.Path(f)
    if not p.exists():
        continue
    text = p.read_text(encoding='utf-8')
    for pattern in network_patterns:
        if re.search(pattern, text):
            errors.append(f'GATE FAIL: {f} contains network-call pattern {pattern!r}')

if errors:
    for e in errors: print(e)
    sys.exit(1)
print('GATE PASS')
"
```

---

**Gate 3 — Rotation script MUST NOT delete the archive after creation**

Verification:
```python
python -c "
import pathlib, sys, re

text = pathlib.Path('scripts/rotate-audit-log.py').read_text(encoding='utf-8')
errors = []
# Heuristic: look for unlink/remove calls following archive write
if re.search(r'\.unlink\(\)|os\.remove\(.*archive|os\.unlink\(.*archive', text):
    errors.append('GATE FAIL: rotate-audit-log.py appears to delete the archive after creation')
if errors:
    for e in errors: print(e)
    sys.exit(1)
print('GATE PASS')
"
```

---

**Gate 4 — Rotation script MUST call `scripts/append-decision.py` for the DEC entry (not write directly to `decision-log.jsonl`)**

Verification:
```python
python -c "
import pathlib, sys, re

text = pathlib.Path('scripts/rotate-audit-log.py').read_text(encoding='utf-8')
errors = []
# Must reference append-decision.py
if not re.search(r'append-decision\.py|append_decision', text):
    errors.append('GATE FAIL: rotate-audit-log.py does not appear to call scripts/append-decision.py for the DEC entry')
# Must not open decision-log.jsonl directly for writing (except through the subprocess call)
# Look for open(..., 'a') or open(..., 'w') calls that reference decision-log
if re.search(r'open\s*\(.*decision-log.*[\"\\'][wa][\"\\']', text):
    errors.append('GATE FAIL: rotate-audit-log.py appears to write directly to decision-log.jsonl')
if errors:
    for e in errors: print(e)
    sys.exit(1)
print('GATE PASS')
"
```

---

**Gate 5 — Hooks MUST NOT execute inside the actual `.council/` directory of this repo; `enforce-append-only` and `enforce-reversibility` tests use temp dirs for any state files they need**

`.council/` does not exist in this repo yet. Any hook or test that creates it will corrupt the repository state.

Verification:
```python
python -c "
import pathlib, sys, re

errors = []
# .council/ must not have been created
if pathlib.Path('.council').exists():
    errors.append('GATE FAIL: .council/ directory was created — hooks and tests must use temp dirs')

# Bash test fixtures must reference tempdir patterns for state files
test_files = [
    'tests/hooks/test-enforce-append-only.sh',
    'tests/hooks/test-enforce-reversibility.sh',
    'tests/hooks/test-log-tool-call.sh',
    'tests/hooks/test-rotate-audit-log.sh',
]
for f in test_files:
    p = pathlib.Path(f)
    if not p.exists():
        continue
    text = p.read_text(encoding='utf-8')
    # If the file references .council/ as a literal write path it must use mktemp
    if re.search(r'\.council/', text) and not re.search(r'mktemp|TMPDIR|/tmp/', text, re.IGNORECASE):
        errors.append(f'GATE FAIL: {f} references .council/ without a temp-dir context')

if errors:
    for e in errors: print(e)
    sys.exit(1)
print('GATE PASS')
"
```

---

**Gate 6 — Cross-sprint scope drift: only declared sprint-5 files were added or modified since sprint-4 harness checkpoint commit `26dfae8`**

Verification:
```python
python -c "
import subprocess, sys

ALLOWED_NEW = {
    'hooks/enforce-append-only.sh',
    'hooks/enforce-reversibility.sh',
    'hooks/log-tool-call.sh',
    'hooks/session-stopped-marker.sh',
    'hooks/win/enforce-append-only.ps1',
    'hooks/win/enforce-reversibility.ps1',
    'hooks/win/log-tool-call.ps1',
    'hooks/win/session-stopped-marker.ps1',
    'scripts/rotate-audit-log.py',
    '.github/workflows/ci.yml',
    'tests/hooks/test-enforce-append-only.sh',
    'tests/hooks/test-enforce-reversibility.sh',
    'tests/hooks/test-log-tool-call.sh',
    'tests/hooks/test-rotate-audit-log.sh',
    'tests/hooks/win/test-enforce-append-only.ps1',
    'tests/hooks/win/test-enforce-reversibility.ps1',
    'tests/hooks/win/test-log-tool-call.ps1',
    'tests/hooks/win/test-rotate-audit-log.ps1',
    'tests/hooks/test-rotate-audit-log.py',
    '.harness/contracts/sprint-05.md',
}
ALLOWED_MODIFY = {
    '.harness/progress.md',
    '.harness/sprint-state.json',
}
ALLOWED_ALL = ALLOWED_NEW | ALLOWED_MODIFY

result = subprocess.run(
    ['git', 'diff', '--name-only', '--diff-filter=ACM', '26dfae8..HEAD'],
    capture_output=True, text=True
)
if result.returncode != 0:
    print('GATE FAIL: git diff command failed:', result.stderr.strip()); sys.exit(1)

changed = [l.strip() for l in result.stdout.splitlines() if l.strip()]
errors = []
for f in changed:
    if f not in ALLOWED_ALL:
        errors.append(f'GATE FAIL: unexpected file outside sprint-5 scope: {f!r}')
if errors:
    for e in errors: print(e)
    sys.exit(1)
print('GATE PASS')
"
```

Pass condition: prints `GATE PASS` and exits 0.

---

## Reference Solutions

**Reference for SC-12 (highest-weight LLM-judge criterion) — `hooks/enforce-append-only.sh` expected structure:**

```bash
#!/usr/bin/env bash
# PreToolUse hook — block Write/Edit on append-only council logs.
# Reads Claude Code tool-call envelope JSON from stdin.
# Exit 0 = allow.  Non-zero exit = block (stderr message surfaced to user).

set -uo pipefail

PROTECTED_FILES=(
    ".council/henka-register.jsonl"
    ".council/decision-log.jsonl"
    ".council/audit-log.jsonl"
)

# Read envelope from stdin
envelope=$(cat 2>/dev/null || true)
if [[ -z "$envelope" ]]; then
    exit 0  # No envelope — fail open
fi

# Require jq; fail open if absent
if ! command -v jq &>/dev/null; then
    echo "enforce-append-only: jq not found — hook skipped (fail open)" >&2
    exit 0
fi

tool_name=$(echo "$envelope" | jq -r '.tool_name // empty' 2>/dev/null || true)
file_path=$(echo "$envelope" | jq -r '.tool_args.file_path // empty' 2>/dev/null || true)

# Only inspect Write and Edit tool calls
if [[ "$tool_name" != "Write" && "$tool_name" != "Edit" ]]; then
    exit 0
fi

# Normalize path: strip leading ./ if present
file_path="${file_path#./}"

for protected in "${PROTECTED_FILES[@]}"; do
    if [[ "$file_path" == "$protected" || "$file_path" == *"/$protected" ]]; then
        echo "BLOCKED: Direct ${tool_name} on append-only log '${file_path}' is forbidden." >&2
        echo "  Approved write paths: scripts/append-henka.py, scripts/append-decision.py" >&2
        exit 1
    fi
done

exit 0
```

**Reference for SC-14 (rotation invariants) — DEC entry chain anchor in `scripts/rotate-audit-log.py`:**

```python
import gzip, hashlib, pathlib, subprocess, json, sys
from datetime import datetime, timezone

def rotate(file_path: pathlib.Path, decision_output: pathlib.Path,
           threshold_bytes: int) -> int:
    if not file_path.exists():
        print(f"no-op: {file_path} does not exist", file=sys.stderr)
        return 0
    if file_path.stat().st_size <= threshold_bytes:
        print(f"no-op: {file_path} is below threshold ({file_path.stat().st_size} <= {threshold_bytes})", file=sys.stderr)
        return 0

    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    archive_path = file_path.parent / f"audit-log.{ts}.jsonl.gz"
    original_bytes = file_path.read_bytes()
    original_size = len(original_bytes)

    # Write gzip archive
    with gzip.open(archive_path, "wb") as gz:
        gz.write(original_bytes)

    # Compute SHA-256 of the archive file (not the raw bytes)
    sha256 = hashlib.sha256(archive_path.read_bytes()).hexdigest()

    # Truncate the current log
    file_path.write_bytes(b"")

    # Emit DEC entry via append-decision.py (inherits schema validation)
    # decision_id must match ^DEC-[0-9]{4,}$ per schema
    seq = int(datetime.now(timezone.utc).strftime("%H%M%S"))
    dec_entry = {
        "decision_id": f"DEC-{seq:04d}",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "decision_type": "audit-log-rotation",
        "decision_outcome": "applied",
        "autonomy_level_used": 3,
        "effective_autonomy_at_decision": 3,
        "reversibility": "irreversible",
        "description": json.dumps({
            "event": "audit-log-rotation",
            "archive_path": str(archive_path),
            "original_size_bytes": original_size,
            "sha256_archive": sha256,
        }),
    }
    r = subprocess.run(
        [sys.executable, "scripts/append-decision.py",
         "--output", str(decision_output)],
        input=json.dumps(dec_entry),
        capture_output=True, text=True,
    )
    if r.returncode != 0:
        print(f"ERROR: append-decision.py failed: {r.stderr}", file=sys.stderr)
        return 1

    print(f"ROTATED: {file_path} -> {archive_path} (sha256={sha256})")
    return 0
```

Key invariants shown:
- Archive written before source truncated
- SHA-256 computed on the gz archive file, recorded in DEC entry
- DEC entry emitted via `subprocess.run(['...', 'scripts/append-decision.py', ...])` — schema validation inherited
- Source file truncated (not deleted) after successful archive write
- Archive is never deleted

---

## Out of Scope

- **Hook installation into `.claude/settings.json` `hooks` block** — sprint 5 ships the hook content; registration is a one-time per-project setup step surfaced in the kickoff skill (sprint 3). No `settings.json` modification in this sprint.
- **Actually creating `.council/` on disk** — `.council/` is not created in this sprint; all write-path tests use isolated temp directories or temp files.
- **`scripts/run-verification.py`** — sprint 6 (S4) deliverable.
- **`tests/fixtures/dummy-project/`** — sprint 6 (S4) deliverable.
- **`council-autorun`, `council-review`, `council-retro`, `council-detect` skills** — sprints 6/7/8.
- **Orchestrator-side andon-detection logic** — Q14's andon_pull_count is tracked in the hook in this sprint; the orchestrator's response logic is sprint 6.
- **`hooks/win/install.ps1` or any hook installation automation** — sprint 5 ships the hooks themselves.
- **`agents/retrospective.md` pdca/jishuken modes full implementation** — sprint 8 (S6) deliverable.
- **`scripts/append-audit.py`** — not in sprints.json S2 or S3 features; out of scope.
- **Cross-platform PowerShell hook self-test in CI (Windows-actual run)** — CI YAML must declare `windows-latest` but actual triggering of the CI run is outside the evaluation environment. SC-7 verifies the YAML is syntactically valid and declares both platforms.

---

## Technical Notes

**Claude Code hook envelope shape (§9.4):** The envelope is a JSON object delivered to stdin with at minimum: `tool_name` (string), `tool_args` (object), `cwd` (string), `session_id` (string). `tool_args` shape is tool-specific: for `Write`/`Edit` it has `file_path`; for `Bash` it has `command`. PreToolUse hooks exit 0 to allow, non-zero to block (stderr surfaces to the user). PostToolUse hooks exit 0 to continue, non-zero to warn (the tool already ran). Stop hooks fire after the agent finishes; stdin may be empty or contain a minimal envelope.

**jq dependency:** Bash hooks may use `jq` for envelope parsing. If `jq` is absent, the hook must fail open (exit 0 with a stderr warning) rather than blocking all tool calls. The CI runner (`ubuntu-latest`) has `jq` installed by default. `windows-latest` does not — the PowerShell hooks must not use `jq`.

**PowerShell hooks use `ConvertFrom-Json`:** `$envelope = $Input | ConvertFrom-Json` (or `[Console]::In.ReadToEnd() | ConvertFrom-Json`). No external dependencies. Exit code in PowerShell is set via `exit N` (explicit) — throwing an uncaught exception produces a non-zero exit but the exact code is platform-dependent; prefer `exit 1` for portability.

**`log-tool-call.sh` and `andon_pull_count`:** The hook maintains a per-agent counter in a temp state file (e.g., `/tmp/council-andon-counts/`) or in `.council/state/` when that directory exists. On each invocation the hook reads the current count for the agent from the envelope, increments it, writes back, and includes the updated count in the audit-log entry. If no state file exists the count starts at 0. The audit entry must include `andon_pull_count` only when the tool call is andon-related (i.e., `tool_name` == `"Write"` targeting an andon-signal-related path, or `event_type` == `"andon-signal"`); for ordinary tool calls the field may be omitted or set to 0.

**`rotate-audit-log.py` CLI flags:** `--threshold-bytes N` (default 52428800 = 50 MB), `--file <path>` (default `.council/audit-log.jsonl`), `--decision-output <path>` (default `.council/decision-log.jsonl`). The `--file` and `--decision-output` flags enable test isolation without writing to `.council/`. When `--decision-output` points to a temp file, `append-decision.py` is called with `--output <temp-path>`.

**Schema path for `rotate-audit-log.py`:** The script calls `scripts/append-decision.py` as a subprocess. `append-decision.py` already resolves its own schema from `__file__`-relative paths (established in sprint 4). The rotation script does not need to resolve the schema itself.

**`decision-log-entry.schema.json` `decision_type` field:** The DEC entry for rotation must pass schema validation. The sprint 1 schema defines `decision_type` as a required string with no enum constraint, so any string value passes. Use `"audit-log-rotation"` consistently (as specified in SC-14 and the reference solution). The `decision_id` must match the pattern `^DEC-[0-9]{4,}$` — use a zero-padded numeric suffix (e.g., derive from timestamp seconds as `DEC-{HHMMSS}`).

**Cross-sprint scope drift baseline:** `26dfae8` is the sprint-4 harness checkpoint commit (the `harness: complete sprint 04 evaluation` commit per `git log`). Gate 6 uses `git diff --name-only --diff-filter=ACM 26dfae8..HEAD`. Sprint 6 will use the sprint-5 checkpoint commit. Document this baseline-bump pattern each sprint so future contracts inherit it cleanly.

**`.harness/sprint-state.json` in Gate 6 `ALLOWED_MODIFY`:** Listed to prevent false-positive gate failures when the harness updates it mid-sprint. The Generator does not modify this file; it is a harness artifact.

**Fixture test isolation strategy:** Bash fixture tests use `mktemp -d` to create a temp dir; all hook invocations that might write to `.council/` paths instead write to paths under the temp dir, passed via env vars or `--output` flags. This is the same pattern used in sprint 4's Python test fixture.

**Idempotency of rotation:** "Idempotent" means: run the script against a file at/below threshold → no rotation, exit 0. Run against a file above threshold → rotation occurs, exit 0. Run again immediately → file is now empty (below threshold), no new rotation, exit 0. The test fixture must use `--threshold-bytes 100` (not 50 MB) to avoid creating large files on the evaluator's disk — the `--threshold-bytes` flag exists precisely for this.

---

**Task taxonomy handoff:** Once this contract is approved by the Evaluator, a sibling `.harness/contracts/sprint-05.tasks.json` is emitted (guarded by `config.taxonomy.emit_tasks_json`, default `true`). It contains one JSON entry per criterion above — both Success Criteria and Should-NOT gates — with stable `task_id`s, `grader_type`, `weight`, `is_gate`, `verification_command`, and `rubric_dimension`. Downstream sprints (regression gate, Batch API, transcript capture, adversarial hygiene) consume that JSON; this markdown contract remains the human-readable source of truth. See `skills/sprint-contract/SKILL.md` for the schema.


## Evaluator Review

**Status: APPROVED with Major note**

### Summary
Round-1 blockers and majors (weight sum off-100%, `notes`→`description` field mismatch, PyYAML silent-skip, and two minors) were all addressed by the Generator's round-2 revision. One new shell-escape issue in SC-8's `windows_abs` regex was identified in round 2; it is implementation-fixable and does not block approval.

### Blockers (must fix before approval)
- None.

### Major issues
- M2 (new): SC-8 `windows_abs` regex on line 266 — shell double-quote escaping collapses `\\` to `\` and induces a SyntaxError. Fix during implementation: use `r"[A-Za-z]:\\\\"` (double-quoted raw string) or `r'[A-Za-z]:\x5c'` (hex escape).

### Minor / nice-to-have
- None from round 2. Round-1 minors (m1, m2) were applied by the Generator.
