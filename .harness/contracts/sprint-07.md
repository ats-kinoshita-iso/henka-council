# Sprint 07 Contract — S5 Nemawashi Walkthrough + Course Corrections

## Scope

Sprint 7 completes the nemawashi walkthrough machinery that sprint 6 stubbed in Step 1D. It delivers: (1) `skills/council-review/SKILL.md`, a new manual fan-out skill with identical andon/verification protocols to council-autorun and the `--restore-autonomy` flag as the single canonical floor-reset path per v2.1 amendment A5; (2) a full enrichment of `skills/council-autorun/SKILL.md` Step 1D replacing the sprint-6 stub with the complete four-stage walkthrough (write position paper → sequential agent presentation → alignment revision loop → formal ratify prompt), including irreversible-action auto-escalation logic (§2.4.2, R9) and the preserved single-prompt minor approval path with `nemawashi_walkthrough_version: null` in the DEC entry (Q15); and (3) minor structural enrichment of `templates/nemawashi-position-paper.md` to fully support all four stages if the sprint-2 baseline requires it. `.council/proposed/archive/` move-on-ratify semantics and decision-log path resolution (§5.4, A4) are documented inline within the affected skill files. No `.council/` directory is created in this repo; all behavior is documented as governance instructions for a target project.

---

## Files in Scope

**New files (1):**
- `skills/council-review/SKILL.md` — manual fan-out skill; YAML frontmatter; ≥2000 chars; `--restore-autonomy` flag as single canonical floor-reset; andon/verification protocols matching council-autorun **[NEW]**

**Enriched files (2):**
- `skills/council-autorun/SKILL.md` — Step 1D fully replaced: four-stage nemawashi walkthrough (Stages 1–4), post-ratify archive move, irreversible-action auto-escalation, single-prompt minor path **[ENRICHED]**
- `templates/nemawashi-position-paper.md` — full four-stage scaffold (Stage 1–4 section headings with guidance prompts); sprint-2 baseline enriched as needed **[ENRICHED]**

**Prose-only (documented inside file artifacts above):**
- `.council/proposed/archive/` move-on-ratify semantics and DEC path resolution (§5.4, A4) — inside council-autorun Step 1D and council-review SKILL.md
- Irreversible-action auto-escalation logic (§2.4.2, R9) — inside council-autorun Step 1D and referenced in council-review SKILL.md
- Single-prompt minor approval path with `nemawashi_walkthrough_version: null` (Q15) — inside council-autorun Step 1D

---

## Success Criteria

### Deterministic (weights sum to 60%)

<!-- SC weights: SC-1(8)+SC-2(10)+SC-3(10)+SC-4(8)+SC-5(8)+SC-6(10)+SC-7(6) = 60% -->

---

**SC-1 [weight: 8%] — All declared sprint-7 files exist at their specified paths**

Input: check existence of the three deliverable files.

Verification:
```python
python -c "
import pathlib, sys

errors = []
files = [
    'skills/council-review/SKILL.md',
    'skills/council-autorun/SKILL.md',
    'templates/nemawashi-position-paper.md',
]
for f in files:
    if not pathlib.Path(f).exists():
        errors.append(f'MISSING: {f}')

if errors:
    for e in errors: print(e)
    sys.exit(1)
print('ALL FILES PRESENT')
"
```

Pass condition: prints `ALL FILES PRESENT` and exits 0.

Maps to: §8.2, §8.3, sprints.json sprint 7 features

---

**SC-2 [weight: 10%] — `skills/council-review/SKILL.md` has YAML frontmatter, is ≥2000 chars, mentions `--restore-autonomy`, and references `andon-protocol.md` and `run-verification.py`**

Input: read `skills/council-review/SKILL.md` and check structural anchors.

Verification:
```python
python -c "
import pathlib, re, sys

p = pathlib.Path('skills/council-review/SKILL.md')
if not p.exists():
    print('MISSING: skills/council-review/SKILL.md'); sys.exit(1)

text = p.read_text(encoding='utf-8')
errors = []

# YAML frontmatter
if not text.startswith('---'):
    errors.append('FAIL: missing YAML frontmatter (must start with ---)')

# Length
if len(text) < 2000:
    errors.append(f'FAIL: SKILL.md is only {len(text)} chars; expected >= 2000')

# --restore-autonomy flag (A5)
if '--restore-autonomy' not in text:
    errors.append('FAIL: missing --restore-autonomy flag mention')

# andon-protocol.md reference
if 'andon-protocol.md' not in text and 'andon_protocol' not in text:
    errors.append('FAIL: missing andon-protocol.md reference')

# run-verification.py reference
if 'run-verification.py' not in text and 'run_verification' not in text:
    errors.append('FAIL: missing run-verification.py reference')

if errors:
    for e in errors: print(e)
    sys.exit(1)
print('COUNCIL-REVIEW STRUCTURE PASS')
"
```

Pass condition: prints `COUNCIL-REVIEW STRUCTURE PASS` and exits 0.

Maps to: §8.3, v2.1 amendment A5, v2.1 amendment A1

---

**SC-3 [weight: 10%] — `skills/council-autorun/SKILL.md` Step 1D enrichment: all four stage headings present, mentions `proposed/archive/`, `nemawashi_walkthrough_version: null`, and irreversible auto-escalation**

Input: read the enriched Step 1D section and grep for required anchors. Partial credit: each missing anchor is a separate failure.

Verification:
```python
python -c "
import pathlib, re, sys

p = pathlib.Path('skills/council-autorun/SKILL.md')
if not p.exists():
    print('MISSING: skills/council-autorun/SKILL.md'); sys.exit(1)

text = p.read_text(encoding='utf-8')
errors = []

# Per-stage heading check (partial-credit-friendly: each is separate)
for stage_label in ['Stage 1', 'Stage 2', 'Stage 3', 'Stage 4']:
    pattern = r'(?i)(#{1,4}\s+' + re.escape(stage_label) + r'\b|' + re.escape(stage_label) + r'[\s:—\-])'
    if not re.search(pattern, text):
        errors.append(f'MISSING stage heading in Step 1D: {stage_label}')

# proposed/archive/ path
if 'proposed/archive' not in text:
    errors.append('FAIL: missing proposed/archive/ mention (post-ratify move path)')

# nemawashi_walkthrough_version: null (single-prompt minor path marker)
if 'nemawashi_walkthrough_version: null' not in text and 'nemawashi_walkthrough_version\":null' not in text:
    errors.append('FAIL: missing nemawashi_walkthrough_version: null (single-prompt minor path, Q15)')

# irreversible auto-escalation
if not re.search(r'irrev\w+.{0,60}(auto.?escalat|major path|mandatory)', text, re.IGNORECASE | re.DOTALL):
    if not re.search(r'(auto.?escalat|mandatory escalation).{0,80}irrev', text, re.IGNORECASE | re.DOTALL):
        errors.append('FAIL: missing irreversible-action auto-escalation logic (R9, §2.4.2)')

if errors:
    for e in errors: print(e)
    sys.exit(1)
print('STEP 1D ENRICHMENT PASS')
"
```

Pass condition: prints `STEP 1D ENRICHMENT PASS` and exits 0. Partial credit from LLM-judge SC-8 applies when individual stage headings are present but others are missing.

Maps to: §8.2 Step 1D Stages 1–4, §2.4.2, R9, Q15, v2.1 amendment A4

---

**SC-4 [weight: 8%] — `templates/nemawashi-position-paper.md` contains all four stage section headings explicitly**

Input: read the template and check for each stage heading.

Verification:
```python
python -c "
import pathlib, re, sys

p = pathlib.Path('templates/nemawashi-position-paper.md')
if not p.exists():
    print('MISSING: templates/nemawashi-position-paper.md'); sys.exit(1)

text = p.read_text(encoding='utf-8')
errors = []

for stage_label in ['Stage 1', 'Stage 2', 'Stage 3', 'Stage 4']:
    pattern = r'(?i)(#{1,4}\s+' + re.escape(stage_label) + r'\b|' + re.escape(stage_label) + r'[\s:—\-])'
    if not re.search(pattern, text):
        errors.append(f'MISSING: {stage_label} heading in position-paper template')

if errors:
    for e in errors: print(e)
    sys.exit(1)
print('POSITION PAPER TEMPLATE PASS')
"
```

Pass condition: prints `POSITION PAPER TEMPLATE PASS` and exits 0.

Maps to: §8.2 Step 1D, sprints.json sprint 7 feature "templates/nemawashi-position-paper.md"

---

**SC-5 [weight: 8%] — `skills/council-review/SKILL.md` mentions `--restore-autonomy` as the single canonical floor-reset and describes the DEC entry it produces**

Input: grep for the canonical-floor-reset framing and the DEC entry fields it mandates.

Verification:
```python
python -c "
import pathlib, re, sys

p = pathlib.Path('skills/council-review/SKILL.md')
if not p.exists():
    print('MISSING: skills/council-review/SKILL.md'); sys.exit(1)

text = p.read_text(encoding='utf-8')
errors = []

# Canonical single path (A5)
canonical_patterns = [
    r'single canonical',
    r'only.{0,30}floor.{0,30}reset',
    r'floor.{0,30}reset.{0,30}only',
    r'canonical.{0,30}floor',
]
if not any(re.search(pat, text, re.IGNORECASE) for pat in canonical_patterns):
    errors.append('FAIL: --restore-autonomy not framed as single canonical floor-reset path (A5)')

# DEC entry type
if 'autonomy-floor-restore' not in text and 'autonomy_floor_restore' not in text:
    errors.append('FAIL: missing decision_type autonomy-floor-restore for DEC entry')

# update-effective-autonomy.py invocation on restore
if 'update-effective-autonomy' not in text and 'update_effective_autonomy' not in text:
    errors.append('FAIL: missing update-effective-autonomy.py invocation on --restore-autonomy')

if errors:
    for e in errors: print(e)
    sys.exit(1)
print('RESTORE-AUTONOMY CANONICAL PATH PASS')
"
```

Pass condition: prints `RESTORE-AUTONOMY CANONICAL PATH PASS` and exits 0.

Maps to: v2.1 amendment A5, §8.3

---

**SC-6 [weight: 10%] — `skills/council-autorun/SKILL.md` still passes the sprint-6 SC-6 structural check (all ten step headings present, YAML frontmatter, ≥3000 chars)**

Input: the enrichment of Step 1D must not have removed or corrupted existing step headings or the overall file structure.

Verification:
```python
python -c "
import pathlib, re, sys

p = pathlib.Path('skills/council-autorun/SKILL.md')
if not p.exists():
    print('MISSING: skills/council-autorun/SKILL.md'); sys.exit(1)

text = p.read_text(encoding='utf-8')
errors = []

# YAML frontmatter
if not text.startswith('---'):
    errors.append('FAIL: missing YAML frontmatter (must start with ---)')

# Length
if len(text) < 3000:
    errors.append(f'FAIL: SKILL.md is only {len(text)} chars; expected >= 3000')

# All ten step headings (sprint-6 regression)
required_steps = ['1A', '1A.5', '1B', '1C', '1D', '1E', '1F', '1G', '1H', '1I']
for step in required_steps:
    pattern = r'(?i)(#{1,4}\s+step\s+' + re.escape(step) + r'\b|step\s+' + re.escape(step) + r'[\s:*—])'
    if not re.search(pattern, text):
        errors.append(f'MISSING step heading: Step {step}')

if errors:
    for e in errors: print(e)
    sys.exit(1)
print('AUTORUN REGRESSION PASS')
"
```

Pass condition: prints `AUTORUN REGRESSION PASS` and exits 0.

Maps to: §8.2 (sprint-6 regression), sprint-06 SC-6

---

**SC-7 [weight: 6%] — Cross-sprint regression: sprint-4 and sprint-5 scripts still parse; sprint-6 S4 acceptance test still exits 0**

Input: re-run `ast.parse` on sprint-4/5 Python scripts and execute the S4 acceptance test.

Verification:
```python
python -c "
import pathlib, ast, sys, subprocess

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
for s in ['scripts/rotate-audit-log.py', 'scripts/run-verification.py']:
    p = pathlib.Path(s)
    if not p.exists():
        errors.append(f'MISSING (sprint-5/6 regression): {s}')
        continue
    try:
        ast.parse(p.read_text(encoding='utf-8'))
    except SyntaxError as e:
        errors.append(f'SYNTAX ERROR (sprint-5/6): {s}: {e}')

# Sprint-6 S4 acceptance test
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

if errors:
    for e in errors: print(e)
    sys.exit(1)
print('CROSS-SPRINT REGRESSION PASS')
"
```

Pass condition: prints `CROSS-SPRINT REGRESSION PASS` and exits 0.

Maps to: sprint-4/5/6 regression gate

---

### LLM-as-judge (weights sum to 40%)

**SC-8 [weight: 18%] — `skills/council-autorun/SKILL.md` Step 1D nemawashi walkthrough correctness**

The judge reads the enriched Step 1D section in `skills/council-autorun/SKILL.md` and scores against the following rubric dimensions:

1. **Stage 1 — Position paper creation** (§8.2 Step 1D): The step directs the orchestrator to write a position paper to `.council/proposed/DEC-{NNNN}.md` using `templates/nemawashi-position-paper.md` BEFORE presenting anything to the user. The position paper includes the proposed change, rationale, reversibility assessment, all contributing agent perspectives with evidence chains, and a consensus chain. The NNNN counter is defined (e.g., sequential or padded sprint-relative).

2. **Stage 2 — Sequential agent presentation** (§8.2 Step 1D): The step specifies sequential (not parallel) agent-by-agent presentation. Each agent's perspective is presented with the three-handle prompt: `yes` (record agreement, proceed to next agent), `refine` (record refinement, re-present with refinement), `disagree` (record disagreement, continue to next agent, bring to Stage 3). The presentation script text is included or referenced from the position paper template.

3. **Stage 3 — Alignment revision loop** (§8.2 Step 1D): The step is triggered by at least one `disagree` handle (or unresolved `refine`). Multiple `refine` handles from different agents may be batched into a single revision pass. Revisions use the `-rev{N}` suffix naming convention. Stage 2 is repeated after each revision. Escalation-to-halt is triggered if alignment is not reached within N revision cycles (2 cycles per template default). All disagreements must be addressed before Stage 4.

4. **Stage 4 — Ratify prompt and post-ratify actions** (§8.2 Step 1D, A4): The ratify prompt is described as a formal confirmation (not a decision). On `yes`: change is applied, commit message `DEC-{NNNN}: {description}` format noted, position paper moved to `.council/proposed/archive/`, DEC entry written with `nemawashi_walkthrough_version: {N}`, `reversibility`, `status: ratified`, `applied_at`. Audit-log entry for the archive move is required. On `no`: position paper left in `.council/proposed/`, DEC entry with `status: rejected`.

5. **Irreversible-action auto-escalation** (§2.4.2, R9): The step explicitly states that a nominally minor change that is actually irreversible MUST auto-escalate to the nemawashi path regardless of its nominal classification. The reversibility check precedes the minor/major classification. The criterion is stated unconditionally — no exception allows a truly irreversible change to take the minor auto-apply path.

6. **Single-prompt minor approval path** (Q15, §8.2 Step 1D): The step preserves the minor reversible path. For a reversible minor change at effective-autonomy level ≥ 4: no position paper is created; the orchestrator prompts the user with a one-line summary; on confirmation the change is applied. The DEC entry for this path has `decision_type: course-correction-minor`, `nemawashi_walkthrough_version: null` (exactly — not 0, not omitted), `reversibility: reversible`.

Score: PASS (full) if all 6 dimensions satisfied; PARTIAL (67% credit) if 4–5 satisfied; PARTIAL (33% credit) if 2–3 satisfied; FAIL if ≤1 satisfied.

Maps to: §8.2 Step 1D Stages 1–4, §2.4.2, R9, Q15, v2.1 amendments A4, A5

---

**SC-9 [weight: 12%] — `skills/council-review/SKILL.md` manual fan-out and `--restore-autonomy` correctness**

The judge reads `skills/council-review/SKILL.md` and scores against the following rubric dimensions:

1. **Manual fan-out scope and invocation context** (§8.3): The file clearly describes that council-review is a manually-invoked skill (not automatic) used when the orchestrator has halted or when the user wants to review course-corrections outside the autorun loop. The skill performs its own agent fan-out (sequential by default, same ordering as autorun) but does NOT call `/henkaten-council:council-autorun` — the two are sibling flows, not parent/child.

2. **Identical andon/verification protocols** (§8.3, §7.0.2, A1): The skill explicitly states that it uses the same andon-protocol.md rules and verification spot-check via `scripts/run-verification.py` as council-autorun. It is not a lighter-weight version — it carries the full governance weight.

3. **`--restore-autonomy` flag authority and audit requirements** (A5): The file describes: the flag requires Level 5 (human) approval; it produces a DEC entry with `decision_type: autonomy-floor-restore`, `effective_autonomy_at_decision` reflecting the NEW (higher) level, and `applied_at`; it calls `scripts/update-effective-autonomy.py` to persist the new state. The flag is described as the SINGLE canonical path to raise the autonomy floor — no other skill, command, or agent can do this.

4. **Difference from council-autorun** (§8.3): The file articulates how council-review differs from council-autorun: council-review is invoked after a halt (or on demand), has no Step 1B (no trine-eval delegation), and is not automatically triggered by the sprint loop. The manual nature means the user explicitly invokes `/henkaten-council:council-review`.

Score: PASS if all 4 dimensions satisfied; PARTIAL (50% credit) if 2–3 satisfied; FAIL if ≤1 satisfied.

Maps to: §8.3, v2.1 amendment A5, v2.1 amendment A1

---

**SC-10 [weight: 10%] — `templates/nemawashi-position-paper.md` template completeness and scaffolding quality**

The judge reads `templates/nemawashi-position-paper.md` and scores against the following rubric dimensions:

1. **Stage 1 scaffolding** (§8.2): The Stage 1 section provides useful prompts for the position paper author: proposed change description, rationale, reversibility assessment with the reversibility table reference, per-agent findings with evidence chains (evidence_class, confidence, verification), consensus chain, and affected artifacts table.

2. **Stage 2 scaffolding** (§8.2): The Stage 2 section provides the Orchestrator's presentation script (what to say to the user for each agent perspective), explains all three handles (`yes`, `refine`, `disagree`) with instructions for how to proceed after each, and has a Stage 2 completion record structure.

3. **Stage 3 scaffolding** (§8.2): The Stage 3 section describes the skip condition (all Stage 2 responses were `yes`), the revision-naming convention (`DEC-{NNNN}-rev{N}.md`), the escalation-to-halt condition (alignment not reached after N cycles), and a revision log table.

4. **Stage 4 scaffolding** (§8.2, A4): The Stage 4 section provides the ratification prompt script, the `yes`/`no` branches with their DEC entry fields (including `nemawashi_walkthrough_version`, `reversibility`, `status`), and the archive-move instruction.

Score: PASS if all 4 dimensions satisfied; PARTIAL (50% credit) if 2–3 satisfied; FAIL if ≤1 satisfied.

Maps to: §8.2 Step 1D, sprints.json sprint 7 feature "templates/nemawashi-position-paper.md"

---

## Should-NOT Criteria (Gate — Any Failure Blocks the Sprint)

**Gate 1 — `skills/council-review/SKILL.md` MUST NOT invoke `/henkaten-council:council-autorun` or call it as a parent/child sub-skill**

council-review and council-autorun are sibling flows. council-review must not delegate to council-autorun unconditionally.

Verification:
```python
python -c "
import pathlib, sys, re

p = pathlib.Path('skills/council-review/SKILL.md')
if not p.exists():
    print('GATE SKIP: SKILL.md missing (caught by SC-1)'); sys.exit(0)

text = p.read_text(encoding='utf-8')
# Must not unconditionally invoke council-autorun
if re.search(r'/henkaten-council:council-autorun', text, re.IGNORECASE):
    print('GATE FAIL: council-review SKILL.md invokes council-autorun (must be sibling, not child)')
    sys.exit(1)
print('GATE PASS')
"
```

---

**Gate 2 — `--restore-autonomy` MUST be documented in `skills/council-review/SKILL.md` as the ONLY canonical floor-reset path; no other skill may claim this authority**

Check that no other skills already in scope claim to reset the autonomy floor outside the `--restore-autonomy` flag in council-review.

Verification:
```python
python -c "
import pathlib, sys, re

errors = []

# council-review MUST have --restore-autonomy
cr = pathlib.Path('skills/council-review/SKILL.md')
if cr.exists():
    text = cr.read_text(encoding='utf-8')
    if '--restore-autonomy' not in text:
        errors.append('GATE FAIL: council-review SKILL.md missing --restore-autonomy flag')
else:
    errors.append('GATE FAIL: council-review SKILL.md missing (cannot check autonomy claim)')

# Other skills must NOT claim to reset the autonomy floor
for skill_path in pathlib.Path('skills').glob('*/SKILL.md'):
    if skill_path == cr:
        continue
    text = skill_path.read_text(encoding='utf-8')
    # Flag any other skill claiming autonomy floor reset authority
    if re.search(r'(reset.{0,20}autonomy.{0,20}floor|restore.{0,20}autonomy.{0,20}floor)', text, re.IGNORECASE):
        errors.append(f'GATE FAIL: {skill_path} claims autonomy floor reset authority (A5 violation)')

if errors:
    for e in errors: print(e)
    sys.exit(1)
print('GATE PASS')
"
```

---

**Gate 3 — Position paper move-on-ratify MUST NOT delete the original; it MUST be moved to `proposed/archive/` (documented, not executed)**

The Step 1D text in `skills/council-autorun/SKILL.md` must not instruct the orchestrator to delete the position paper after ratification. It must instruct a move to `proposed/archive/`.

Verification:
```python
python -c "
import pathlib, sys, re

p = pathlib.Path('skills/council-autorun/SKILL.md')
if not p.exists():
    print('GATE SKIP: SKILL.md missing (caught by SC-1)'); sys.exit(0)

text = p.read_text(encoding='utf-8')
errors = []

# Must mention proposed/archive/ as the post-ratify destination
if 'proposed/archive' not in text:
    errors.append('GATE FAIL: Step 1D does not mention proposed/archive/ as post-ratify destination (A4)')

# Must NOT instruct deletion of the position paper (no 'rm DEC-' or 'delete.*DEC-' pattern)
if re.search(r'(rm|delete|unlink).{0,40}DEC-', text, re.IGNORECASE):
    errors.append('GATE FAIL: Step 1D instructs deletion of position paper (must move, not delete)')

if errors:
    for e in errors: print(e)
    sys.exit(1)
print('GATE PASS')
"
```

---

**Gate 4 — Single-prompt minor approval path MUST set `nemawashi_walkthrough_version: null` exactly — not 0, not omitted**

Verification:
```python
python -c "
import pathlib, sys, re

p = pathlib.Path('skills/council-autorun/SKILL.md')
if not p.exists():
    print('GATE SKIP: SKILL.md missing (caught by SC-1)'); sys.exit(0)

text = p.read_text(encoding='utf-8')
errors = []

# Must contain the exact string nemawashi_walkthrough_version: null
if 'nemawashi_walkthrough_version: null' not in text and 'nemawashi_walkthrough_version\":null' not in text and 'nemawashi_walkthrough_version\" : null' not in text:
    errors.append('GATE FAIL: nemawashi_walkthrough_version: null not found exactly (must not be 0 or omitted, Q15)')

if errors:
    for e in errors: print(e)
    sys.exit(1)
print('GATE PASS')
"
```

---

**Gate 5 — Irreversible-action auto-escalation MUST fire regardless of nominal classification; no exception path that allows a truly irreversible change to take the minor auto-apply path**

Verification:
```python
python -c "
import pathlib, sys, re

p = pathlib.Path('skills/council-autorun/SKILL.md')
if not p.exists():
    print('GATE SKIP: SKILL.md missing (caught by SC-1)'); sys.exit(0)

text = p.read_text(encoding='utf-8')
errors = []

# Must reference irreversible + escalation in close proximity
irrev_escalate = re.search(
    r'irrev\w+.{0,200}(escalat|major path|nemawashi|mandatory)',
    text, re.IGNORECASE | re.DOTALL
)
escalate_irrev = re.search(
    r'(escalat|mandatory).{0,200}irrev\w+',
    text, re.IGNORECASE | re.DOTALL
)
if not irrev_escalate and not escalate_irrev:
    errors.append('GATE FAIL: Step 1D does not describe irreversible-action auto-escalation (R9, §2.4.2)')

if errors:
    for e in errors: print(e)
    sys.exit(1)
print('GATE PASS')
"
```

---

**Gate 6 — Cross-sprint scope drift: only declared sprint-7 files were added or modified since sprint-6 harness checkpoint commit `8461cb3`**

Verification:
```python
python -c "
import subprocess, sys

ALLOWED_NEW = {
    'skills/council-review/SKILL.md',
    '.harness/contracts/sprint-07.md',
}
ALLOWED_MODIFY = {
    'skills/council-autorun/SKILL.md',
    'templates/nemawashi-position-paper.md',
    '.harness/progress.md',
    '.harness/sprint-state.json',
}
# Pre-sprint-7 housekeeping files allowed through
PRE_SPRINT7_CLEANUP = set()

result = subprocess.run(
    ['git', 'diff', '--name-only', '--diff-filter=ACM', '8461cb3..HEAD'],
    capture_output=True, text=True
)
if result.returncode != 0:
    print('GATE FAIL: git diff command failed:', result.stderr.strip()); sys.exit(1)

changed = [l.strip() for l in result.stdout.splitlines() if l.strip()]
errors = []
for f in changed:
    if f in PRE_SPRINT7_CLEANUP:
        continue
    if f in ALLOWED_NEW or f in ALLOWED_MODIFY:
        continue
    errors.append(f'GATE FAIL: unexpected file outside sprint-7 scope: {f!r}')

if errors:
    for e in errors: print(e)
    sys.exit(1)
print('GATE PASS')
"
```

Pass condition: prints `GATE PASS` and exits 0.

---

## Reference Solutions

**Reference for SC-8 (heaviest LLM-judge criterion) — worked example of the full 4-stage nemawashi walkthrough**

The following worked example shows the expected control-flow shape for a nemawashi triggered by a course-correction proposal. An implementation may use different prose as long as it captures these invariants.

**Scenario:** The orchestrator's course-correction step (Step 1D) proposes adding a `--strict` flag to `scripts/run-verification.py` that would reject commands with any shell metacharacter, replacing the current prefix-match allowlist. Agent perspectives differ.

```
## Stage 1 — Write Position Paper

Orchestrator writes: .council/proposed/DEC-0042.md

  Document ID: DEC-0042
  Proposed Change: Add --strict flag to scripts/run-verification.py that replaces
    prefix-match allowlist with full metacharacter rejection. Affects: scripts/run-verification.py.
  Reversibility: reversible (git revert restores prior behavior; no persistent state change)
  Rationale: Three agent-capability-change Henkaten records in sprint 6 showed that
    agents submitted jq '...' strings with shell-escaping that bypassed the prefix check.
  Agent Perspectives:
    - architect: observed that the current prefix check has a gap for embedded subshells.
      evidence_class: observed, confidence: 4,
      verification: git diff HEAD -- scripts/run-verification.py
      View: supports --strict; coherence with §7.0.2 intent is stronger with metachar rejection.
    - scope-guardian: inferred that --strict breaks any legitimate jq expression using $(...)
      for dynamic queries. Proposes limiting --strict to commands NOT starting with jq.
      evidence_class: inferred, confidence: 3
      View: refine — scope --strict to non-jq commands.
    - henkaten-detector: observed no scheduled sprint work referencing --strict.
      change_origin: active (orchestrator-proposed). classification: Method.
      View: yes — the change is coherent with the sprint scope.
  Consensus Chain: architect and henkaten-detector support; scope-guardian has a refinement.
    Residual uncertainty: whether jq with $() is a real-world verification need.

## Stage 2 — Sequential Agent Presentation

Orchestrator presents architect's perspective:
  "architect found a gap in the prefix check for embedded subshells (observed, confidence 4;
  verified via git diff). architect supports --strict for full metachar rejection.
  Does architect's framing match your understanding? (yes / refine / disagree)"
User: yes → record architect: yes.

Orchestrator presents scope-guardian's perspective:
  "scope-guardian inferred that --strict would break legitimate jq $() expressions and
  proposes limiting --strict to non-jq commands. Does this framing match your
  understanding? (yes / refine / disagree)"
User: refine "also allow python scripts/validate- with $() substitution"
  → record scope-guardian: refined (two-exception carve-out: jq and python validate scripts).
  Re-present: "scope-guardian's refined position: limit --strict to commands not starting
  with jq or python scripts/validate-. Does that match? (yes / refine / disagree)"
User: yes → record scope-guardian: yes (after refine).

Orchestrator presents henkaten-detector's perspective:
  "henkaten-detector classified this as an active Method change with no sprint-scheduled
  coverage. It supports the change. Does this framing match? (yes / refine / disagree)"
User: yes → record henkaten-detector: yes.

Stage 2 outcome: architect: yes | scope-guardian: yes (after refine) | henkaten-detector: yes
All perspectives aligned → no disagreements → skip Stage 3.

## Stage 3 — Alignment (SKIPPED — no disagree handles)

## Stage 4 — Ratify

Orchestrator says:
  "All perspectives are aligned on DEC-0042. To confirm:
  Proposed change: Add --strict flag to run-verification.py, excluding jq and
    python scripts/validate- prefixes from metachar rejection.
  Affected files: scripts/run-verification.py
  Reversibility: reversible
  Apply DEC-0042? (yes/no)"
User: yes

Post-ratify actions:
  - Apply change to scripts/run-verification.py
  - git commit -m "DEC-0042: add --strict flag to run-verification.py with jq/validate carve-out"
  - mv .council/proposed/DEC-0042.md .council/proposed/archive/DEC-0042.md
  - Write decision-log entry:
      { decision_type: "course-correction-major",
        nemawashi_walkthrough_version: 0,   # 0 revisions (no Stage 3 needed)
        reversibility: "reversible",
        status: "ratified",
        applied_at: "<ISO-8601 timestamp>",
        dec_id: "DEC-0042" }
  - Append audit-log entry: "DEC-0042 position paper archived at proposed/archive/DEC-0042.md"

Alternative path (with disagree → Stage 3):
  If scope-guardian had said "disagree" instead of "refine":
    Stage 2 outcome: architect: yes | scope-guardian: disagree | henkaten-detector: yes
    → advance to Stage 3.
    Orchestrator creates DEC-0042-rev1.md incorporating the exception carve-out.
    Stage 2 repeated for DEC-0042-rev1.md → all say yes → Stage 4 with
    nemawashi_walkthrough_version: 1 in the DEC entry.
```

**Reference for SC-9 (council-review) — expected `--restore-autonomy` DEC entry structure:**

```yaml
decision_type: autonomy-floor-restore
dec_id: DEC-0043
effective_autonomy_at_decision: 4   # new level AFTER restore
previous_level: 2                   # level before restore
status: ratified
applied_at: <ISO-8601>
reversibility: reversible            # autonomy floor can be re-lowered
trigger: "--restore-autonomy invoked by user after /council-review"
```

After writing this entry, `scripts/update-effective-autonomy.py` is called with the new level so `.council/state/effective-autonomy.json` reflects the restored floor.

---

## Out of Scope

- **`skills/council-retro-mini/SKILL.md`, `skills/council-retro/SKILL.md`, `skills/council-jishuken/SKILL.md`** — sprint 8 (S6) deliverables.
- **`skills/council-detect/SKILL.md`** — sprint 8 (S6) deliverable.
- **`agents/retrospective.md` pdca/jishuken modes** — sprint 8 (S6) deliverable.
- **Yokoten propagation logic** — retrospective agent populates yokoten block (sprint 8); sprint 7 does not add new yokoten machinery.
- **Live execution of nemawashi against a real `.council/` directory** — `.council/` does not exist in this repo; all nemawashi behavior is documented as governance instructions for a target project.
- **Modifications to sprint 1–6 deliverables other than:** Step 1D in `skills/council-autorun/SKILL.md` and `templates/nemawashi-position-paper.md` (the two explicitly enriched files).
- **New Python scripts or hooks** — sprint 7 is markdown-only; no new `.py` or `.sh` files.
- **`agents/qa-regression.md` and `agents/rag-source.md`** — status: proposed; no changes in sprint 7.

---

## Technical Notes

**`--restore-autonomy` flag (v2.1 amendment A5):** The SINGLE canonical floor-reset path. No other skill may reset the autonomy floor. Authority: Level 5 (human-approved invocation of `/council-review --restore-autonomy`). The flag produces a DEC entry with `decision_type: autonomy-floor-restore` and `effective_autonomy_at_decision` reflecting the new (higher) level. After `--restore-autonomy`, `scripts/update-effective-autonomy.py` is invoked to persist the new state to `.council/state/effective-autonomy.json`.

**Position paper file naming convention:**
- Initial draft: `.council/proposed/DEC-{NNNN}.md`
- Stage 3 revisions: `.council/proposed/DEC-{NNNN}-rev{N}.md` (N = 1, 2, ...)
- Post-ratify archive: `.council/proposed/archive/DEC-{NNNN}.md` (or final revision filename)
- The `nemawashi_walkthrough_version` field in the DEC entry equals the number of revisions (0 if no Stage 3 was triggered, 1 if one revision cycle was needed, etc.)

**Three handles in Stage 2:**
- `yes` — proceed to next agent; no revision needed
- `refine` — record the specific refinement; re-present the agent's perspective with the refinement incorporated; if accepted, record as "yes after refine"
- `disagree` — record the disagreement; continue to next agent; advance to Stage 3 after all agents are presented

**Disagree vs refine semantics:** A single `disagree` from any agent advances to Stage 3. Multiple `refine` handles (with user accepting all refinements in Stage 2) do NOT require Stage 3 — they are incorporated inline and produce `nemawashi_walkthrough_version: 0` in the DEC entry.

**Irreversibility auto-escalation (§2.4.2, R9):** The reversibility check is the FIRST check in Step 1D, preceding minor/major classification. If the change is irreversible, it goes directly to nemawashi regardless of its size or scope. The YAML schema for `decision-log-entry` already has a `reversibility` field (sprint 1 deliverable); sprint 7 just ensures the routing logic in Step 1D enforces it.

**Single-prompt minor approval path (Q15):** For reversible minor changes at effective-autonomy level ≥ 4: no position paper is created; the orchestrator prompts with one line; the DEC entry has `nemawashi_walkthrough_version: null` (exactly — not 0, not omitted).

**Cross-sprint baseline ref:** `8461cb3` is the sprint-6 harness checkpoint commit (`harness: complete sprint 06 evaluation`). Gate 6 uses `git diff --name-only --diff-filter=ACM 8461cb3..HEAD`. Only the three file artifacts listed in "Files in Scope" plus harness metadata files (progress.md, sprint-state.json, contracts/sprint-07.md) should appear in this diff.

**Sprint 7 is markdown-only:** No new Python scripts, no new shell hooks, no new JSON schemas. All deliverables are `.md` files. The cross-sprint regression (SC-7) verifies that no existing script was broken by the enrichment.

**Partial-credit-friendly SC pattern (per playbook):** SC-3 uses per-stage grep — each missing stage heading is a separate `errors.append`. If council-autorun Step 1D ships Stages 1–3 but not Stage 4, SC-3 fails, but LLM-judge SC-8 can award partial weight (67% credit) for the stages that are present. Contract authors favor this pattern over atomic all-or-nothing checks for large deliverables.

**Weight distribution rationale:** Deterministic 60% / LLM-judge 40%. Higher LLM-judge proportion than sprint 6 (33%) reflects that this sprint is markdown-only — the substance is in the prose quality of the walkthrough description, not in executable code. The deterministic checks anchor the structural requirements (files exist, headings present, key strings found); the LLM-judge checks verify that the walkthrough actually makes sense as a governance protocol.


---

## Evaluator Review

**Status: APPROVED**

### Summary
Sprint 7 ships three markdown artifacts (council-review skill, enriched council-autorun Step 1D, enriched nemawashi-position-paper template) covering the complete four-stage nemawashi walkthrough. Weights sum to exactly 100% (deterministic 60%: SC-1(8)+SC-2(10)+SC-3(10)+SC-4(8)+SC-5(8)+SC-6(10)+SC-7(6); LLM-judge 40%: SC-8(18)+SC-9(12)+SC-10(10)). Contract applies sprint-3-through-6 lessons: Gate 6 anchors on baseline commit ref 8461cb3, Gate 4 enforces nemawashi_walkthrough_version: null literally (not 0, not omitted), SC-3 uses per-stage grep for partial-credit-friendly grading, and no shell-escape regex traps or DEC-entry schema mismatches are present in the verification commands.

### Blockers (must fix before approval)
- None.

### Major issues
- None.

### Minor / nice-to-have
- SC-7 cross-sprint regression runs the sprint-6 S4 acceptance test via subprocess; if the dummy-project fixture path drifts across worktrees this could produce a false FAIL. Not a blocker for sprint 7, but worth noting for the sprint-8 playbook.
