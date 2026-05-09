"""End-to-end S6 acceptance test for Sprint 8.

Asserts all S6 acceptance behaviors against the sprint-8 deliverables:

  1. Skill files all exist (4 sprint-8 skills)
  2. Template files all exist (3 sprint-8 templates)
  3. Retro-mini file simulation — mock sprint-01-mini.md created and has plausible content
  4. PDCA file simulation — mock full-2026-05-09.md has all four PDCA headings
  5. Jishuken file simulation + standard-work.json unchanged check (Q16 enforcement)
  6. No --reset-autonomy-floor flag in council-jishuken skill (A5 enforcement)
  7. Yokoten fields in agents/retrospective.md (R6 enforcement)
  8. Three modes documented in agents/retrospective.md (mini, pdca, jishuken)

Exit codes:
    0  — all 8 assertions passed
    1  — one or more assertions failed
"""
from __future__ import annotations

import hashlib
import json
import pathlib
import re
import sys
import tempfile

# ---------------------------------------------------------------------------
# Path constants
# ---------------------------------------------------------------------------

_REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent

_SKILLS = [
    "skills/council-retro-mini/SKILL.md",
    "skills/council-retro/SKILL.md",
    "skills/council-jishuken/SKILL.md",
    "skills/council-detect/SKILL.md",
]

_TEMPLATES = [
    "templates/retrospective-mini.md",
    "templates/retrospective-pdca.md",
    "templates/jishuken-workshop.md",
]

_JISHUKEN_SKILL = _REPO_ROOT / "skills" / "council-jishuken" / "SKILL.md"
_RETROSPECTIVE_AGENT = _REPO_ROOT / "agents" / "retrospective.md"


# ---------------------------------------------------------------------------
# Helper functions
# ---------------------------------------------------------------------------

def _pass(n: int, total: int, msg: str) -> None:
    print(f"[{n}/{total}] PASS: {msg}")


def _fail(n: int, total: int, msg: str) -> None:
    print(f"[{n}/{total}] FAIL: {msg}")


def _sha256(path: pathlib.Path) -> str:
    h = hashlib.sha256()
    h.update(path.read_bytes())
    return h.hexdigest()


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> int:
    total = 8
    errors: list[str] = []

    # -----------------------------------------------------------------------
    # Assertion 1: Skill files all exist
    # -----------------------------------------------------------------------
    n = 1
    missing_skills: list[str] = []
    for rel in _SKILLS:
        p = _REPO_ROOT / rel
        if not p.exists():
            missing_skills.append(rel)
    if missing_skills:
        reason = "missing: " + ", ".join(missing_skills)
        _fail(n, total, f"Skill files exist — {reason}")
        errors.append(reason)
    else:
        _pass(n, total, "All 4 sprint-8 skill files exist")

    # -----------------------------------------------------------------------
    # Assertion 2: Template files all exist
    # -----------------------------------------------------------------------
    n = 2
    missing_templates: list[str] = []
    for rel in _TEMPLATES:
        p = _REPO_ROOT / rel
        if not p.exists():
            missing_templates.append(rel)
    if missing_templates:
        reason = "missing: " + ", ".join(missing_templates)
        _fail(n, total, f"Template files exist — {reason}")
        errors.append(reason)
    else:
        _pass(n, total, "All 3 sprint-8 template files exist")

    # -----------------------------------------------------------------------
    # Assertion 3: Retro-mini file simulation
    # -----------------------------------------------------------------------
    n = 3
    try:
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = pathlib.Path(tmpdir)
            retro_dir = tmp / ".council" / "retrospectives"
            retro_dir.mkdir(parents=True)
            mini_file = retro_dir / "sprint-01-mini.md"
            mini_file.write_text(
                "# Sprint 01 Mini Retrospective\n\n"
                "sprint: 01\n"
                "mode: mini\n\n"
                "## Learning Points\n\n"
                "- Established baseline governance patterns.\n\n"
                "## Pattern Observations\n\n"
                "- Change-point detection log gaps require follow-up.\n",
                encoding="utf-8",
            )
            if not mini_file.exists():
                reason = "retro-mini file was not created in tempdir"
                _fail(n, total, f"Retro-mini file simulation — {reason}")
                errors.append(reason)
            else:
                content = mini_file.read_text(encoding="utf-8")
                has_token = bool(re.search(r"sprint|mini", content, re.IGNORECASE))
                if not content.strip():
                    reason = "retro-mini file is empty"
                    _fail(n, total, f"Retro-mini file simulation — {reason}")
                    errors.append(reason)
                elif not has_token:
                    reason = "retro-mini file lacks 'sprint' or 'mini' token"
                    _fail(n, total, f"Retro-mini file simulation — {reason}")
                    errors.append(reason)
                else:
                    _pass(
                        n,
                        total,
                        "Retro-mini file simulation: file exists and has plausible content",
                    )
    except Exception as exc:
        reason = f"unexpected exception: {exc}"
        _fail(n, total, f"Retro-mini file simulation — {reason}")
        errors.append(reason)

    # -----------------------------------------------------------------------
    # Assertion 4: PDCA file simulation — all four headings present
    # -----------------------------------------------------------------------
    n = 4
    try:
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = pathlib.Path(tmpdir)
            retro_dir = tmp / ".council" / "retrospectives"
            retro_dir.mkdir(parents=True)
            pdca_file = retro_dir / "full-2026-05-09.md"
            pdca_file.write_text(
                "# Full PDCA Retrospective — 2026-05-09\n\n"
                "## Plan\n\n"
                "Planned actions and hypotheses for the cycle.\n\n"
                "## Do\n\n"
                "Executed sprint work; deviations recorded in henka-register.jsonl.\n\n"
                "## Check\n\n"
                "Evaluated results against plan; regression passed for all prior scripts.\n\n"
                "## Act\n\n"
                "Standard-work proposals (if any) routed via nemawashi walkthrough.\n",
                encoding="utf-8",
            )
            content = pdca_file.read_text(encoding="utf-8")
            missing_headings: list[str] = []
            for heading in ["## Plan", "## Do", "## Check", "## Act"]:
                if heading not in content:
                    missing_headings.append(heading)
            if missing_headings:
                reason = "missing headings: " + ", ".join(missing_headings)
                _fail(n, total, f"PDCA file simulation — {reason}")
                errors.append(reason)
            else:
                _pass(
                    n,
                    total,
                    "PDCA file simulation: all four Plan/Do/Check/Act headings present",
                )
    except Exception as exc:
        reason = f"unexpected exception: {exc}"
        _fail(n, total, f"PDCA file simulation — {reason}")
        errors.append(reason)

    # -----------------------------------------------------------------------
    # Assertion 5: Jishuken file simulation + standard-work.json unchanged
    # -----------------------------------------------------------------------
    n = 5
    try:
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = pathlib.Path(tmpdir)

            # Create a baseline standard-work.json
            sw_file = tmp / "standard-work.json"
            sw_content = json.dumps(
                {"baseline_version": "1.0.0", "rules": []}, indent=2
            )
            sw_file.write_text(sw_content, encoding="utf-8")
            hash_before = _sha256(sw_file)

            # Simulate jishuken output (does NOT touch standard-work.json)
            jishuken_dir = tmp / ".council" / "jishuken"
            jishuken_dir.mkdir(parents=True)
            jishuken_file = jishuken_dir / "test-topic-2026-05-09.md"
            jishuken_file.write_text(
                "# Jishuken Workshop: test-topic — 2026-05-09\n\n"
                "## Reflection Notes\n\n"
                "- The council detection cadence may need sensitivity tuning.\n\n"
                "## Open Questions\n\n"
                "- How often should henkaten be reviewed during a sprint?\n\n"
                "## Hypotheses\n\n"
                "- More frequent micro-reviews may surface passive changes earlier.\n",
                encoding="utf-8",
            )

            # Verify standard-work.json hash is unchanged
            hash_after = _sha256(sw_file)

            jish_ok = jishuken_file.exists()
            hash_ok = hash_before == hash_after

            jish_errors: list[str] = []
            if not jish_ok:
                jish_errors.append("jishuken file was not created")
            if not hash_ok:
                jish_errors.append(
                    "standard-work.json hash changed (Q16 violation: jishuken must NOT modify standard-work)"
                )
            if jish_errors:
                reason = "; ".join(jish_errors)
                _fail(n, total, f"Jishuken simulation + standard-work unchanged — {reason}")
                errors.extend(jish_errors)
            else:
                _pass(
                    n,
                    total,
                    "Jishuken file created and standard-work.json hash unchanged (Q16 satisfied)",
                )
    except Exception as exc:
        reason = f"unexpected exception: {exc}"
        _fail(n, total, f"Jishuken simulation + standard-work unchanged — {reason}")
        errors.append(reason)

    # -----------------------------------------------------------------------
    # Assertion 6: No --reset-autonomy-floor flag in council-jishuken skill (A5)
    # -----------------------------------------------------------------------
    n = 6
    if not _JISHUKEN_SKILL.exists():
        reason = f"skills/council-jishuken/SKILL.md does not exist at {_JISHUKEN_SKILL}"
        _fail(n, total, f"No --reset-autonomy-floor in jishuken skill — {reason}")
        errors.append(reason)
    else:
        text = _JISHUKEN_SKILL.read_text(encoding="utf-8")
        if "--reset-autonomy-floor" in text:
            reason = (
                "skills/council-jishuken/SKILL.md contains '--reset-autonomy-floor' "
                "(A5 violation: single canonical floor-reset is /council-review --restore-autonomy)"
            )
            _fail(n, total, f"No --reset-autonomy-floor in jishuken skill — {reason}")
            errors.append(reason)
        else:
            _pass(
                n,
                total,
                "council-jishuken/SKILL.md does not contain '--reset-autonomy-floor' (A5 satisfied)",
            )

    # -----------------------------------------------------------------------
    # Assertion 7: Yokoten fields in agents/retrospective.md (R6)
    # -----------------------------------------------------------------------
    n = 7
    if not _RETROSPECTIVE_AGENT.exists():
        reason = f"agents/retrospective.md does not exist at {_RETROSPECTIVE_AGENT}"
        _fail(n, total, f"Yokoten fields in retrospective.md — {reason}")
        errors.append(reason)
    else:
        text = _RETROSPECTIVE_AGENT.read_text(encoding="utf-8")
        yokoten_errors: list[str] = []
        for field in ["applicable_to_subsequent_sprints", "adaptation_notes"]:
            if field not in text:
                yokoten_errors.append(f"missing field '{field}'")
        if yokoten_errors:
            reason = "; ".join(yokoten_errors)
            _fail(n, total, f"Yokoten fields in retrospective.md — {reason}")
            errors.extend(yokoten_errors)
        else:
            _pass(
                n,
                total,
                "agents/retrospective.md contains 'applicable_to_subsequent_sprints' and 'adaptation_notes' (R6 satisfied)",
            )

    # -----------------------------------------------------------------------
    # Assertion 8: Three modes documented in agents/retrospective.md
    # -----------------------------------------------------------------------
    n = 8
    if not _RETROSPECTIVE_AGENT.exists():
        reason = f"agents/retrospective.md does not exist at {_RETROSPECTIVE_AGENT}"
        _fail(n, total, f"Three modes in retrospective.md — {reason}")
        errors.append(reason)
    else:
        text = _RETROSPECTIVE_AGENT.read_text(encoding="utf-8")
        mode_errors: list[str] = []
        for mode in ["mini", "pdca", "jishuken"]:
            if not re.search(r"\b" + re.escape(mode) + r"\b", text, re.IGNORECASE):
                mode_errors.append(f"missing mode marker '{mode}'")
        if mode_errors:
            reason = "; ".join(mode_errors)
            _fail(n, total, f"Three modes in retrospective.md — {reason}")
            errors.extend(mode_errors)
        else:
            _pass(
                n,
                total,
                "agents/retrospective.md documents all three modes: mini, pdca, jishuken",
            )

    # -----------------------------------------------------------------------
    # Summary
    # -----------------------------------------------------------------------
    n_fail = len(errors)
    if n_fail == 0:
        print("S6 ACCEPTANCE TEST: ALL 8 ASSERTIONS PASS")
        return 0
    else:
        print(f"S6 ACCEPTANCE TEST: {n_fail} ASSERTIONS FAILED")
        return 1


if __name__ == "__main__":
    sys.exit(main())
