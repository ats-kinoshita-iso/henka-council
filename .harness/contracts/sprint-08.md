# Sprint 08 Contract — S6 Three Retrospective Cadences + Yokoten + Detect Skill

## Scope

Sprint 8 is the final sprint. It delivers the complete retrospective cadence machinery: `skills/council-retro-mini/SKILL.md` (per-sprint automatic ≤30s, mini mode, no standard-work proposals), `skills/council-retro/SKILL.md` (per-cycle PDCA retrospective with architect, Plan/Do/Check/Act output, standard-work proposals via nemawashi), `skills/council-jishuken/SKILL.md` (per-period user-invoked reflection, jishuken mode, reflection-only, NO `--reset-autonomy-floor` flag per A5), and `skills/council-detect/SKILL.md` (on-demand henkaten detection with sensitivity thresholds and `change_origin` classification). It also completes `agents/retrospective.md` with full `pdca` and `jishuken` mode implementations (mini mode shipped in sprint 4), adds yokoten propagation logic to all three retrospective modes, ships three supporting templates (`templates/retrospective-mini.md`, `templates/retrospective-pdca.md`, `templates/jishuken-workshop.md`), and delivers an end-to-end S6 acceptance test extending the sprint-4 dummy-project fixture. No `.council/` directory is created in this repo; all acceptance test assertions operate against the dummy-project fixture or isolated temp directories.

---

## Files in Scope

**New files — skills (4):**
- `skills/council-retro-mini/SKILL.md` — per-sprint automatic, ≤30s, mini mode, no standard-work proposals, output to `.council/retrospectives/sprint-{NN}-mini.md` **[NEW]**
- `skills/council-retro/SKILL.md` — per-cycle PDCA, pdca mode + architect, Plan/Do/Check/Act output to `.council/retrospectives/full-{date}.md`, standard-work proposals via nemawashi, reads `.harness/summary.md` and `regression.json` **[NEW]**
- `skills/council-jishuken/SKILL.md` — per-period user-invoked, jishuken mode + architect, output to `.council/jishuken/<topic>-<date>.md`, reflection-only, NO `--reset-autonomy-floor` flag (A5), decoupled from standard-work proposals (Q16) **[NEW]**
- `skills/council-detect/SKILL.md` — on-demand henkaten detection, sensitivity thresholds, `change_origin` classification, writes to `henka-register.jsonl` via `scripts/append-henka.py` **[NEW]**

**New files — templates (3):**
- `templates/retrospective-mini.md` — per-sprint capture shape: Learning Points, Pattern Observations, coverage, yokoten block placeholder **[NEW]**
- `templates/retrospective-pdca.md` — Plan/Do/Check/Act four-section structure, standard-work proposals table, yokoten block placeholder **[NEW]**
- `templates/jishuken-workshop.md` — Reflection Notes / Open Questions / Hypotheses three-section structure **[NEW]**

**New files — tests (1):**
- `tests/test-s6-acceptance.py` (or `tests/test-s6-acceptance.sh`) — end-to-end S6 acceptance test extending S4 dummy-project fixture: retro-mini file exists, PDCA file has all four sections, jishuken file present with `standard-work.json` unchanged **[NEW]**

**Enriched files (1):**
- `agents/retrospective.md` — full `pdca` mode and `jishuken` mode implementations; yokoten propagation block for all three modes **[ENRICHED]**

---

## Success Criteria

### Deterministic (weights sum to 62%)

<!-- SC weights: SC-1(8)+SC-2(8)+SC-3(8)+SC-4(6)+SC-5(6)+SC-6(6)+SC-7(8)+SC-8(6)+SC-9(6) = 62% -->

---

**SC-1 [weight: 8%] — All declared sprint-8 files exist at their specified paths**

Input: check existence of all 9 deliverable files (4 skills + 3 templates + 1 acceptance test + 1 enriched agent).

Verification:
```python
python -c "
import pathlib, sys

errors = []
files = [
    'skills/council-retro-mini/SKILL.md',
    'skills/council-retro/SKILL.md',
    'skills/council-jishuken/SKILL.md',
    'skills/council-detect/SKILL.md',
    'templates/retrospective-mini.md',
    'templates/retrospective-pdca.md',
    'templates/jishuken-workshop.md',
    'agents/retrospective.md',
]
for f in files:
    if not pathlib.Path(f).exists():
        errors.append(f'MISSING: {f}')

# Accept either .py or .sh for the acceptance test
acceptance_py = pathlib.Path('tests/test-s6-acceptance.py')
acceptance_sh = pathlib.Path('tests/test-s6-acceptance.sh')
if not acceptance_py.exists() and not acceptance_sh.exists():
    errors.append('MISSING: tests/test-s6-acceptance.py (or .sh)')

if errors:
    for e in errors: print(e)
    sys.exit(1)
print('ALL FILES PRESENT')
"
```

Pass condition: prints `ALL FILES PRESENT` and exits 0.

Maps to: §8.4, §8.5, §8.6, §8.7, §7.5, §4, §15.5, sprints.json sprint 8 features

---

**SC-2 [weight: 8%] — All four skills have YAML frontmatter; each skill's key structural anchors are present (partial-credit-friendly per skill)**

Input: read each skill and check for YAML frontmatter start and key strings. Each skill's check is independent.

Verification:
```python
python -c "
import pathlib, sys

errors = []

checks = {
    'skills/council-retro-mini/SKILL.md': ['30s', 'mini', 'retrospectives/sprint-'],
    'skills/council-retro/SKILL.md': ['pdca', 'Plan', 'Do', 'Check', 'Act', 'nemawashi', 'summary.md'],
    'skills/council-jishuken/SKILL.md': ['jishuken', 'reflection', 'council/jishuken/'],
    'skills/council-detect/SKILL.md': ['henka-register.jsonl', 'change_origin', 'sensitivity'],
}

for path_str, required_strings in checks.items():
    p = pathlib.Path(path_str)
    if not p.exists():
        errors.append(f'MISSING: {path_str}')
        continue
    text = p.read_text(encoding='utf-8')
    if not text.startswith('---'):
        errors.append(f'FAIL [{path_str}]: missing YAML frontmatter (must start with ---)')
    for s in required_strings:
        if s not in text:
            errors.append(f'FAIL [{path_str}]: missing required string: {s!r}')

if errors:
    for e in errors: print(e)
    sys.exit(1)
print('ALL SKILLS STRUCTURE PASS')
"
```

Pass condition: prints `ALL SKILLS STRUCTURE PASS` and exits 0.

Maps to: §8.4, §8.5, §8.6, §8.7

---

**SC-3 [weight: 8%] — `skills/council-retro-mini/SKILL.md` mentions ≤30s time budget AND explicitly prohibits standard-work proposals**

Input: grep for time budget and the no-standard-work-proposals constraint.

Verification:
```python
python -c "
import pathlib, re, sys

p = pathlib.Path('skills/council-retro-mini/SKILL.md')
if not p.exists():
    print('MISSING: skills/council-retro-mini/SKILL.md'); sys.exit(1)

text = p.read_text(encoding='utf-8')
errors = []

# Time budget
time_patterns = [r'30\s*s', r'30-second', r'thirty.second', r'within\s+30']
if not any(re.search(pat, text, re.IGNORECASE) for pat in time_patterns):
    errors.append('FAIL: missing <=30s time budget mention')

# No standard-work proposals
nosw_patterns = [
    r'no standard.work propos',
    r'must not.{0,60}standard.work propos',
    r'standard.work.{0,60}not.{0,30}(propos|allow|permit)',
    r'capture.only',
]
if not any(re.search(pat, text, re.IGNORECASE) for pat in nosw_patterns):
    errors.append('FAIL: missing explicit no-standard-work-proposals rule for mini mode')

if errors:
    for e in errors: print(e)
    sys.exit(1)
print('RETRO-MINI CONSTRAINTS PASS')
"
```

Pass condition: prints `RETRO-MINI CONSTRAINTS PASS` and exits 0.

Maps to: §8.4, sprints.json "no standard-work proposals"

---

**SC-4 [weight: 6%] — `skills/council-retro/SKILL.md` contains all four PDCA section labels (Plan, Do, Check, Act) — partial-credit-friendly per section**

Input: grep for each PDCA section label. Each missing label is a separate failure.

Verification:
```python
python -c "
import pathlib, re, sys

p = pathlib.Path('skills/council-retro/SKILL.md')
if not p.exists():
    print('MISSING: skills/council-retro/SKILL.md'); sys.exit(1)

text = p.read_text(encoding='utf-8')
errors = []

for section in ['Plan', 'Do', 'Check', 'Act']:
    pattern = r'(?i)(#{1,4}\s+' + section + r'\b|\\*\\*' + section + r'\\*\\*|\\b' + section + r'\\b.{0,60}(section|phase|step))'
    if not re.search(r'(?i)' + section + r'\b', text):
        errors.append(f'FAIL: missing PDCA section label: {section!r}')

if errors:
    for e in errors: print(e)
    sys.exit(1)
print('PDCA SECTIONS PASS')
"
```

Pass condition: prints `PDCA SECTIONS PASS` and exits 0.

Maps to: §8.5, sprints.json "Plan/Do/Check/Act sections"

---

**SC-5 [weight: 6%] — `skills/council-jishuken/SKILL.md` MUST contain reflection-only framing AND must NOT contain `--reset-autonomy-floor`**

Input: check the reflection-only framing and the absence of the prohibited flag.

Verification:
```python
python -c "
import pathlib, re, sys

p = pathlib.Path('skills/council-jishuken/SKILL.md')
if not p.exists():
    print('MISSING: skills/council-jishuken/SKILL.md'); sys.exit(1)

text = p.read_text(encoding='utf-8')
errors = []

# reflection-only framing
reflection_patterns = [
    r'reflection.only',
    r'reflect\w+.{0,60}only',
    r'no standard.work propos',
    r'decoupled from standard.work',
]
if not any(re.search(pat, text, re.IGNORECASE) for pat in reflection_patterns):
    errors.append('FAIL: missing reflection-only framing in council-jishuken/SKILL.md')

# prohibited flag
if '--reset-autonomy-floor' in text:
    errors.append('FAIL: council-jishuken/SKILL.md contains --reset-autonomy-floor (forbidden per A5)')

if errors:
    for e in errors: print(e)
    sys.exit(1)
print('JISHUKEN CONSTRAINTS PASS')
"
```

Pass condition: prints `JISHUKEN CONSTRAINTS PASS` and exits 0.

Maps to: §8.6, v2.1 amendment A5, Q16

---

**SC-6 [weight: 6%] — `skills/council-detect/SKILL.md` mentions sensitivity thresholds, `change_origin` classification, and `append-henka.py` write path**

Input: grep for key detect-skill anchors.

Verification:
```python
python -c "
import pathlib, re, sys

p = pathlib.Path('skills/council-detect/SKILL.md')
if not p.exists():
    print('MISSING: skills/council-detect/SKILL.md'); sys.exit(1)

text = p.read_text(encoding='utf-8')
errors = []

if not re.search(r'sensitiv\w+', text, re.IGNORECASE):
    errors.append('FAIL: missing sensitivity thresholds mention')

if 'change_origin' not in text:
    errors.append('FAIL: missing change_origin classification mention')

if not re.search(r'(append-henka|henka-register\.jsonl)', text, re.IGNORECASE):
    errors.append('FAIL: missing append-henka.py / henka-register.jsonl write path mention')

if errors:
    for e in errors: print(e)
    sys.exit(1)
print('DETECT SKILL ANCHORS PASS')
"
```

Pass condition: prints `DETECT SKILL ANCHORS PASS` and exits 0.

Maps to: §8.7

---

**SC-7 [weight: 8%] — `agents/retrospective.md` has all three mode sections (mini, pdca, jishuken) AND the yokoten propagation block — partial-credit-friendly per-mode**

Input: grep for each mode section heading and the yokoten block fields. Each missing element is a separate failure.

Verification:
```python
python -c "
import pathlib, re, sys

p = pathlib.Path('agents/retrospective.md')
if not p.exists():
    print('MISSING: agents/retrospective.md'); sys.exit(1)

text = p.read_text(encoding='utf-8')
errors = []

# Per-mode section check (partial-credit-friendly — each is separate)
for mode in ['mini', 'pdca', 'jishuken']:
    pattern = r'(?i)(#{1,4}\s+mode.{0,20}' + mode + r'|mode.{0,5}:?\s+[\"\'`]?' + mode + r'[\"\'`]?|\\*\\*' + mode + r'\\*\\*)'
    if not re.search(r'(?i)\b' + mode + r'\b', text):
        errors.append(f'FAIL: missing mode section for: {mode!r}')

# Yokoten block fields
for field in ['applicable_to_subsequent_sprints', 'adaptation_notes']:
    if field not in text:
        errors.append(f'FAIL: missing yokoten block field: {field!r}')

if 'yokoten' not in text.lower():
    errors.append('FAIL: missing yokoten mention in agents/retrospective.md')

if errors:
    for e in errors: print(e)
    sys.exit(1)
print('RETROSPECTIVE AGENT ENRICHMENT PASS')
"
```

Pass condition: prints `RETROSPECTIVE AGENT ENRICHMENT PASS` and exits 0.

Maps to: §7.5, R6, sprints.json sprint 8 "Yokoten propagation"

---

**SC-8 [weight: 6%] — All three templates have their required structural elements — partial-credit-friendly per template**

Input: check each template for its key section headings.

Verification:
```python
python -c "
import pathlib, re, sys

errors = []

# retrospective-mini.md: Learning Points + Pattern Observations
mini = pathlib.Path('templates/retrospective-mini.md')
if not mini.exists():
    errors.append('MISSING: templates/retrospective-mini.md')
else:
    t = mini.read_text(encoding='utf-8')
    if not re.search(r'(?i)learning.points?', t):
        errors.append('FAIL [retrospective-mini.md]: missing Learning Points section')
    if not re.search(r'(?i)pattern.observ', t):
        errors.append('FAIL [retrospective-mini.md]: missing Pattern Observations section')

# retrospective-pdca.md: Plan + Do + Check + Act
pdca = pathlib.Path('templates/retrospective-pdca.md')
if not pdca.exists():
    errors.append('MISSING: templates/retrospective-pdca.md')
else:
    t = pdca.read_text(encoding='utf-8')
    for section in ['Plan', 'Do', 'Check', 'Act']:
        if not re.search(r'(?i)' + section + r'\b', t):
            errors.append(f'FAIL [retrospective-pdca.md]: missing section: {section!r}')

# jishuken-workshop.md: Reflection Notes + Open Questions + Hypotheses
jish = pathlib.Path('templates/jishuken-workshop.md')
if not jish.exists():
    errors.append('MISSING: templates/jishuken-workshop.md')
else:
    t = jish.read_text(encoding='utf-8')
    if not re.search(r'(?i)reflection.notes?', t):
        errors.append('FAIL [jishuken-workshop.md]: missing Reflection Notes section')
    if not re.search(r'(?i)open.questions?', t):
        errors.append('FAIL [jishuken-workshop.md]: missing Open Questions section')
    if not re.search(r'(?i)hypothes', t):
        errors.append('FAIL [jishuken-workshop.md]: missing Hypotheses section')

if errors:
    for e in errors: print(e)
    sys.exit(1)
print('ALL TEMPLATES STRUCTURE PASS')
"
```

Pass condition: prints `ALL TEMPLATES STRUCTURE PASS` and exits 0.

Maps to: §4, sprints.json sprint 8 template features

---

**SC-9 [weight: 6%] — End-to-end S6 acceptance test exits 0 AND cross-sprint regression (prior scripts still parse, S4 acceptance test still exits 0)**

Input: run the S6 acceptance test and the cross-sprint regression check.

Verification:
```python
python -c "
import pathlib, ast, sys, subprocess

errors = []

# Sprint-4 scripts parse cleanly
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

# Sprint-5/6 scripts parse cleanly
for s in ['scripts/rotate-audit-log.py', 'scripts/run-verification.py']:
    p = pathlib.Path(s)
    if not p.exists():
        errors.append(f'MISSING (sprint-5/6 regression): {s}')
        continue
    try:
        ast.parse(p.read_text(encoding='utf-8'))
    except SyntaxError as e:
        errors.append(f'SYNTAX ERROR (sprint-5/6): {s}: {e}')

# S4 acceptance test still exits 0
py_path = pathlib.Path('tests/test-s4-acceptance.py')
sh_path = pathlib.Path('tests/test-s4-acceptance.sh')
if py_path.exists():
    r = subprocess.run([sys.executable, str(py_path)], capture_output=True, text=True, timeout=60)
    if r.returncode != 0:
        errors.append(f'FAIL: S4 acceptance test exited {r.returncode}: {r.stdout[-400:]} {r.stderr[-200:]}')
elif sh_path.exists():
    r = subprocess.run(['bash', str(sh_path)], capture_output=True, text=True, timeout=60)
    if r.returncode != 0:
        errors.append(f'FAIL: S4 acceptance test (sh) exited {r.returncode}: {r.stdout[-400:]}')
else:
    errors.append('MISSING: tests/test-s4-acceptance.py or .sh (sprint-6 regression)')

# S6 acceptance test exits 0
s6_py = pathlib.Path('tests/test-s6-acceptance.py')
s6_sh = pathlib.Path('tests/test-s6-acceptance.sh')
if s6_py.exists():
    r = subprocess.run([sys.executable, str(s6_py)], capture_output=True, text=True, timeout=60)
    if r.returncode != 0:
        errors.append(f'FAIL: S6 acceptance test exited {r.returncode}: {r.stdout[-400:]} {r.stderr[-200:]}')
elif s6_sh.exists():
    r = subprocess.run(['bash', str(s6_sh)], capture_output=True, text=True, timeout=60)
    if r.returncode != 0:
        errors.append(f'FAIL: S6 acceptance test (sh) exited {r.returncode}: {r.stdout[-400:]}')
else:
    errors.append('MISSING: tests/test-s6-acceptance.py or .sh')

if errors:
    for e in errors: print(e)
    sys.exit(1)
print('ACCEPTANCE AND REGRESSION PASS')
"
```

Pass condition: prints `ACCEPTANCE AND REGRESSION PASS` and exits 0.

Maps to: §15.5, sprint-4/5/6/7 regression gate

---

### LLM-as-judge (weights sum to 38%)

**SC-10 [weight: 16%] — `agents/retrospective.md` three-mode separation correctness**

The judge reads the full `agents/retrospective.md` and scores against the following rubric dimensions:

1. **Mini mode completeness** (§8.4, §7.5): The `mini` mode section specifies: dispatched by `/council-retro-mini`; cadence is per-sprint, automatic, ≤30s; output is `.council/retrospectives/sprint-{NN}-mini.md`; the mode produces Learning Points and Pattern Observations; standard-work proposals are explicitly forbidden (capture-only); yokoten block is populated when closing Henkaten records.

2. **PDCA mode completeness** (§8.5, §7.5): The `pdca` mode section specifies: dispatched by `/council-retro`; per-cycle cadence; output is `.council/retrospectives/full-{date}.md` with Plan/Do/Check/Act structure; MAY produce standard-work proposals, but ONLY via nemawashi walkthrough (Level 5 approval required); proposals require ≥2 sprints evidence (or 1 with explicit justification); reads `.harness/summary.md` and prior retrospectives.

3. **Jishuken mode completeness** (§8.6, §7.5, Q16, A5): The `jishuken` mode section specifies: dispatched by `/council-jishuken`; per-period, user-invoked only; output is `.council/jishuken/<topic>-<date>.md` with Reflection Notes / Open Questions / Hypotheses sections; explicitly NO standard-work proposals; a finding that suggests a standard-work change must be re-raised in a future PDCA pass; the `--reset-autonomy-floor` flag is explicitly NOT present (reflected in the text); single canonical floor-reset is `/council-review --restore-autonomy`.

4. **Per-mode standard-work proposal authority table** (§7.5): The agent contract includes an explicit summary table (or equivalent section) showing `mini: No`, `pdca: MAY`, `jishuken: No` with rationale for each.

5. **Yokoten propagation mechanics** (R6, §8.2 Step 1A.5): The agent describes HOW yokoten propagation works when closing a Henkaten record: populates `applicable_to_subsequent_sprints` (list of sprint numbers or `["all"]`) and `adaptation_notes`; states that the Orchestrator reads these fields during Step 1A.5 of subsequent sprints to surface adaptation prompts.

Score: PASS (full) if all 5 dimensions satisfied; PARTIAL (60% credit) if 3–4 satisfied; PARTIAL (30% credit) if 1–2 satisfied; FAIL if 0 satisfied.

Maps to: §7.5, §8.4, §8.5, §8.6, R6, Q16, v2.1 amendment A5

---

**SC-11 [weight: 12%] — `skills/council-retro/SKILL.md` and `skills/council-jishuken/SKILL.md` flow correctness**

The judge reads both skill files and scores against the following rubric dimensions:

1. **council-retro PDCA flow** (§8.5): The skill describes: invocation context (per-cycle or manual); agent dispatch (retrospective agent in `pdca` mode + architect); input files read (`.harness/summary.md`, `regression.json`, prior retrospectives); output file path (`.council/retrospectives/full-{date}.md`); the four explicit PDCA sections in the output; standard-work proposals emitted via the nemawashi walkthrough stub (not by direct write); the skill does NOT write to `standard-work.json` directly.

2. **council-jishuken reflection-only flow** (§8.6, Q16): The skill describes: on-demand user invocation with a topic argument; retrospective agent in `jishuken` mode + architect; output to `.council/jishuken/<topic>-<date>.md`; the three output sections (Reflection Notes, Open Questions, Hypotheses); explicit statement that findings do NOT automatically become standard-work proposals (re-raise via PDCA if needed); no `--reset-autonomy-floor` flag.

3. **Integration cross-references** (§8.5, §8.6): Both skills reference `agents/retrospective.md` as the dispatched agent; council-retro references the nemawashi walkthrough (linking back to council-autorun Step 1D or council-review); council-jishuken references the PDCA pass as the promotion path for standard-work findings.

Score: PASS if all 3 dimensions satisfied; PARTIAL (50% credit) if 1–2 satisfied; FAIL if 0 satisfied.

Maps to: §8.5, §8.6, Q16, v2.1 amendment A5

---

**SC-12 [weight: 10%] — Yokoten propagation design coherence**

The judge reads `agents/retrospective.md` and `skills/council-retro-mini/SKILL.md` and assesses whether the yokoten propagation design is internally consistent and actionable.

1. **Record-close trigger** (R6): The retrospective agent clearly describes that yokoten block population happens specifically when CLOSING (resolving/closing) a Henkaten record — not on every retrospective run and not as a general annotation.

2. **Field semantics** (R6): `applicable_to_subsequent_sprints` is defined as a list of future sprint numbers (or `["all"]`) that should receive the adaptation prompt; `adaptation_notes` is the human-readable starting point for the adaptation. The semantics of each field are unambiguous.

3. **Step 1A.5 integration** (§8.2 Step 1A.5): The agent (or the mini skill file) explicitly references that council-autorun Step 1A.5 reads these fields to surface adaptation prompts at the start of subsequent sprints; the ratify-once shortcut for `"all"` sprints or ≥3 named sprints is referenced or compatible.

Score: PASS if all 3 dimensions satisfied; PARTIAL (50% credit) if 1–2 satisfied; FAIL if 0 satisfied.

Maps to: R6, §8.2 Step 1A.5, v2.1 amendment A9

---

## Should-NOT Criteria (Gate — Any Failure Blocks the Sprint)

**Gate 1 — `skills/council-jishuken/SKILL.md` MUST NOT contain the literal string `--reset-autonomy-floor`**

The single canonical floor-reset path is `/council-review --restore-autonomy` (A5). Jishuken is reflection-only and must not claim or reference this flag.

Verification:
```python
python -c "
import pathlib, sys

p = pathlib.Path('skills/council-jishuken/SKILL.md')
if not p.exists():
    print('GATE SKIP: SKILL.md missing (caught by SC-1)'); sys.exit(0)

text = p.read_text(encoding='utf-8')
if '--reset-autonomy-floor' in text:
    print('GATE FAIL: council-jishuken/SKILL.md contains --reset-autonomy-floor (A5 violation)')
    sys.exit(1)
print('GATE PASS')
"
```

---

**Gate 2 — `skills/council-jishuken/SKILL.md` MUST NOT propose standard-work changes via nemawashi**

Jishuken is decoupled from standard-work proposals (Q16). Jishuken findings may inform a future PDCA pass, but the jishuken skill must not invoke, describe, or initiate the nemawashi walkthrough for standard-work changes.

Verification:
```python
python -c "
import pathlib, re, sys

p = pathlib.Path('skills/council-jishuken/SKILL.md')
if not p.exists():
    print('GATE SKIP: SKILL.md missing (caught by SC-1)'); sys.exit(0)

text = p.read_text(encoding='utf-8')
# If jishuken claims to emit standard-work proposals via nemawashi, gate fails
if re.search(r'standard.work.{0,80}(propos|nemawashi|walkthrough)', text, re.IGNORECASE):
    # Allow the pattern ONLY if it's negated (i.e., 'does not propose', 'must not', 'no standard-work')
    negated = re.search(r'(no|not|must.not|never|decoupled).{0,80}standard.work.{0,80}(propos|nemawashi)', text, re.IGNORECASE)
    positive = re.search(r'(emit|produce|initiat|invoke).{0,80}standard.work.{0,80}(propos|nemawashi)', text, re.IGNORECASE)
    if positive and not negated:
        print('GATE FAIL: council-jishuken/SKILL.md proposes standard-work changes via nemawashi (Q16 violation)')
        sys.exit(1)
print('GATE PASS')
"
```

---

**Gate 3 — `skills/council-retro-mini/SKILL.md` MUST NOT propose standard-work changes**

Mini mode is capture-only. The mini skill must not include standard-work proposals or nemawashi invocation.

Verification:
```python
python -c "
import pathlib, re, sys

p = pathlib.Path('skills/council-retro-mini/SKILL.md')
if not p.exists():
    print('GATE SKIP: SKILL.md missing (caught by SC-1)'); sys.exit(0)

text = p.read_text(encoding='utf-8')
# Gate fails if it positively initiates standard-work proposals
if re.search(r'(emit|produce|initiat|invoke|creat).{0,60}standard.work.{0,60}propos', text, re.IGNORECASE):
    print('GATE FAIL: council-retro-mini/SKILL.md proposes standard-work changes (mini mode violation)')
    sys.exit(1)
print('GATE PASS')
"
```

---

**Gate 4 — `agents/retrospective.md` pdca mode MUST NOT write to `standard-work.json` directly; proposals MUST go via nemawashi**

The pdca mode MAY produce proposals, but they must route through the nemawashi walkthrough (Level 5 approval), not via direct file write.

Verification:
```python
python -c "
import pathlib, re, sys

p = pathlib.Path('agents/retrospective.md')
if not p.exists():
    print('GATE SKIP: agents/retrospective.md missing (caught by SC-1)'); sys.exit(0)

text = p.read_text(encoding='utf-8')
# Must NOT instruct direct modification of standard-work.json
if re.search(r'(write|modify|update|overwrite).{0,80}standard.work\.json', text, re.IGNORECASE):
    # Allow if it's a prohibition statement
    if not re.search(r'(must not|may not|never|prohibited).{0,80}(write|modify|update).{0,80}standard.work', text, re.IGNORECASE):
        print('GATE FAIL: agents/retrospective.md instructs direct write to standard-work.json (must go via nemawashi)')
        sys.exit(1)
print('GATE PASS')
"
```

---

**Gate 5 — Cross-sprint scope drift: only declared sprint-8 files were added or modified since sprint-7 harness checkpoint commit `4282b4c`**

Verification:
```python
python -c "
import subprocess, sys

ALLOWED_NEW = {
    'skills/council-retro-mini/SKILL.md',
    'skills/council-retro/SKILL.md',
    'skills/council-jishuken/SKILL.md',
    'skills/council-detect/SKILL.md',
    'templates/retrospective-mini.md',
    'templates/retrospective-pdca.md',
    'templates/jishuken-workshop.md',
    'tests/test-s6-acceptance.py',
    'tests/test-s6-acceptance.sh',
    '.harness/contracts/sprint-08.md',
}
ALLOWED_MODIFY = {
    'agents/retrospective.md',
    '.harness/progress.md',
    '.harness/sprint-state.json',
}

result = subprocess.run(
    ['git', 'diff', '--name-only', '--diff-filter=ACM', '4282b4c..HEAD'],
    capture_output=True, text=True
)
if result.returncode != 0:
    print('GATE FAIL: git diff command failed:', result.stderr.strip()); sys.exit(1)

changed = [l.strip() for l in result.stdout.splitlines() if l.strip()]
errors = []
for f in changed:
    if f in ALLOWED_NEW or f in ALLOWED_MODIFY:
        continue
    errors.append(f'GATE FAIL: unexpected file outside sprint-8 scope: {f!r}')

if errors:
    for e in errors: print(e)
    sys.exit(1)
print('GATE PASS')
"
```

Pass condition: prints `GATE PASS` and exits 0.

---

## Reference Solutions

**Reference for SC-10 (heaviest LLM-judge criterion) — expected shape of three-mode separation in `agents/retrospective.md`**

The following sketch shows the invariants an implementation must capture. Prose may differ.

```
## Three Modes

### Mode: `mini` — Per-Sprint Capture (No Standard-Work Proposals)
Dispatched by: /council-retro-mini (automatic, per-sprint, ≤30s)
Output: .council/retrospectives/sprint-{NN}-mini.md
Sections: Learning Points, Pattern Observations
Standard-Work Proposals: NO. Capture-only. MUST NOT include proposals.
Yokoten: When closing a Henkaten record, populate the yokoten block:
  - applicable_to_subsequent_sprints: list of sprint numbers or ["all"]
  - adaptation_notes: starting point for the adaptation prompt

### Mode: `pdca` — Per-Cycle PDCA Retrospective (MAY Produce Standard-Work Proposals)
Dispatched by: /council-retro (per-cycle, configurable N sprints)
Output: .council/retrospectives/full-{date}.md
Sections: Plan / Do / Check / Act (explicit PDCA structure)
Inputs: .harness/summary.md, regression.json, prior retrospectives, jishuken artifacts
Standard-Work Proposals: MAY produce proposals. Requirements:
  - ≥2 sprints evidence (or 1 with explicit justification)
  - Routed via nemawashi walkthrough (Stage 1–4) for Level 5 approval
  - MUST NOT write to standard-work.json directly

### Mode: `jishuken` — Per-Period Reflection Workshop (No Standard-Work Proposals)
Dispatched by: /council-jishuken (per-period, user-invoked only)
Output: .council/jishuken/<topic>-<date>.md
Sections: Reflection Notes / Open Questions / Hypotheses for Future Investigation
Standard-Work Proposals: NO. Reflection-only. A finding that suggests a standard-work
  change must be re-raised in a future PDCA pass — it does NOT flow directly from
  jishuken to standard-work.json.
Note: --reset-autonomy-floor flag is NOT available. Single canonical floor-reset:
  /council-review --restore-autonomy.

## Per-Mode Standard-Work Proposal Summary
| Mode      | Standard-Work Proposals? | Rationale                          |
|-----------|--------------------------|-------------------------------------|
| mini      | No                       | Capture-only; observation cadence   |
| pdca      | MAY (via nemawashi)      | Full PDCA; improvement cadence      |
| jishuken  | No                       | Reflection-only; decoupled (Q16)    |
```

**Reference for SC-12 (yokoten propagation) — expected yokoten block structure when closing a Henkaten record:**

```yaml
# When retrospective agent closes a Henkaten record, it adds:
yokoten:
  applicable_to_subsequent_sprints: [9, 10]   # or ["all"] for universal lessons
  adaptation_notes: >
    The architect's coherence check loop added 3 minutes to the fan-out in sprint 8.
    Future sprints should set a 2-minute cap on architect re-analysis per SC-7 note.
```

Council-autorun Step 1A.5 reads all `henka-register.jsonl` records with a populated `yokoten` block and surfaces them as adaptation prompts before sprint work begins. The `ratify-once` shortcut (v2.1 amendment A9) applies when `applicable_to_subsequent_sprints` is `["all"]` or contains ≥3 sprint numbers.

---

## Out of Scope

- **Live integration with an actual `.council/` directory** — the acceptance test extends the sprint-4 dummy-project fixture; no live `.council/` directory is created in this repo.
- **Full implementation of `.harness/summary.md` generation** — `council-retro` reads `summary.md` as an input if it exists; generating it is trine-eval territory, not council territory.
- **New Python scripts or schemas** — sprint 8 is markdown-only (4 skills, 3 templates, 1 enriched agent) plus one acceptance test script; no new `.py` governance scripts, no new JSON schemas (yokoten block schema already exists from sprint 1).
- **Modifications to sprint 1–7 deliverables other than `agents/retrospective.md`** — the only existing file enriched in sprint 8 is `agents/retrospective.md`.
- **`agents/qa-regression.md` and `agents/rag-source.md`** — status: proposed; no changes in sprint 8.
- **CI/CD changes** — sprint 8 does not add new CI jobs or matrix runners.
- **Jishuken findings automatically becoming standard-work proposals** — Q16 is explicit: jishuken is decoupled; a finding must be re-raised via a PDCA pass.
- **`--reset-autonomy-floor` flag anywhere** — A5 reserves floor-reset authority exclusively for `/council-review --restore-autonomy`; no new skill may introduce this flag.

---

## Technical Notes

**Three retrospective cadences (§7.5, §8.4, §8.5, §8.6):**

| Skill | Mode | Cadence | Output Path | Standard-Work? |
|---|---|---|---|---|
| `/council-retro-mini` | `mini` | Per-sprint, automatic (Step 1H) | `.council/retrospectives/sprint-{NN}-mini.md` | No |
| `/council-retro` | `pdca` | Per-cycle (every N sprints; manual also) | `.council/retrospectives/full-{date}.md` | MAY via nemawashi |
| `/council-jishuken` | `jishuken` | Per-period, manual user invocation | `.council/jishuken/<topic>-<date>.md` | No (Q16) |

**Jishuken vs PDCA (Q16):** PDCA is the formal continuous-improvement cadence and CAN propose standard-work changes via nemawashi. Jishuken is reflection-only. A jishuken finding that suggests a standard-work change must be re-raised in a PDCA pass. The jishuken skill document must NOT describe or reference a standard-work proposal flow.

**A5 amendment — `--reset-autonomy-floor` flag does NOT exist in jishuken:** The single canonical path to raise a dynamic-autonomy floor drop is `/council-review --restore-autonomy` (sprint 7 deliverable). No other skill may introduce or reference `--reset-autonomy-floor`.

**Yokoten propagation per R6:** When the retrospective agent closes a Henkaten record, it populates the `yokoten` block (`applicable_to_subsequent_sprints`, `adaptation_notes`). Council-autorun Step 1A.5 (sprint 6 deliverable, enriched sprint 7) reads these fields and surfaces adaptation prompts at the start of subsequent sprints. The ratify-once shortcut (A9) applies when `applicable_to_subsequent_sprints: ["all"]` or contains ≥3 sprint numbers.

**Cross-sprint baseline ref:** `4282b4c` is the sprint-7 harness checkpoint commit (`harness: complete sprint 07 evaluation`). Gate 5 uses `git diff --name-only --diff-filter=ACM 4282b4c..HEAD`. Only the files listed in "Files in Scope" plus harness metadata files (`progress.md`, `sprint-state.json`, `contracts/sprint-08.md`) should appear in this diff.

**Sprint 8 is markdown-only (except the acceptance test):** No new governance Python scripts (beyond `tests/test-s6-acceptance.py`), no new shell hooks, no new JSON schemas. All deliverables are `.md` files plus one test file. SC-9's cross-sprint regression verifies that no existing script was broken.

**Partial-credit-friendly SC pattern:** SC-7 uses per-mode grep (each missing mode is a separate `errors.append`). SC-8 uses per-template checks. SC-4 uses per-PDCA-section checks. This allows partial scoring when, for example, pdca and mini modes are present but jishuken is missing.

**Weight distribution rationale:** Deterministic 62% / LLM-judge 38%. This is consistent with sprint 7's 60/40 split for a markdown-heavy sprint. The three LLM-judge criteria (SC-10 at 16%, SC-11 at 12%, SC-12 at 10%) cover the substance: three-mode separation (the most complex single artifact), skill-level flow correctness, and yokoten propagation design. The deterministic checks anchor structural requirements; the LLM-judge checks verify that the content actually makes sense as a governance protocol.

**S6 acceptance test design:** The test extends the S4 dummy-project fixture by simulating all three retrospective outputs:
1. Creates a mock `.council/retrospectives/sprint-01-mini.md` (retro-mini file exists check)
2. Creates a mock `.council/retrospectives/full-2026-05-09.md` with Plan/Do/Check/Act headings (PDCA four-section check)
3. Creates a mock `.council/jishuken/test-topic-2026-05-09.md` and verifies that `standard-work.json` (if it exists) was NOT modified during the jishuken step (Q16 enforcement check)

---

## Evaluator Review

**Status: APPROVED**

### Summary
Weights sum correctly (deterministic 62% + LLM-judge 38% = 100%). All deterministic SCs carry verbatim, runnable Python verification commands with no placeholders. Gate 5 correctly uses baseline ref `4282b4c..HEAD`. LLM-judge criteria specify explicit scoring dimensions with partial-credit tiers, and reference solutions are provided for both SC-10 (heaviest judge criterion at 16%) and SC-12.

### Blockers (must fix before approval)
- None.

### Major issues
- None.

### Minor / nice-to-have
- Gate 2's negation heuristic (checking for a `positive` match and absence of a `negated` match) is logically complex — a sufficiently creative phrasing in the delivered file could thread the needle and pass when it should fail. This is a low-probability edge case and not a blocker, but worth noting for future contract authors.
- SC-11's reference solution is omitted (only SC-10 and SC-12 have one). Given SC-11 is 12% weight, a brief sketch for the council-retro and council-jishuken flow expectations would strengthen grader reliability.
