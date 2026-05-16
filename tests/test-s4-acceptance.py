"""End-to-end S4 acceptance test for Sprint 6.

Exercises all six §15.5 assertions against the dummy-project fixture:

  1. scripts/run-verification.py with an allowed command exits 0.
  2. scripts/run-verification.py with a disallowed command exits non-zero
     and emits a rejection message.
  3. skills/council-autorun/SKILL.md exists and contains all 10 step headings.
  4. instructions/andon-protocol.md contains the verbatim thank-the-puller text.
  5. The dummy-project fixture has valid JSON in .harness/config.json and
     .harness/sprints.json, with >= 2 sprint entries.
  6. tests/scripts/test-run-verification.py exits 0.

Exit codes:
    0  — all 6 assertions passed
    1  — one or more assertions failed
"""
from __future__ import annotations

import json
import pathlib
import re
import subprocess
import sys
import tempfile

# ---------------------------------------------------------------------------
# Path constants
# ---------------------------------------------------------------------------

_REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent
_RUN_VERIFICATION = _REPO_ROOT / "scripts" / "run-verification.py"
_SKILL_MD = _REPO_ROOT / "skills" / "council-autorun" / "SKILL.md"
_ANDON_PROTOCOL = _REPO_ROOT / "instructions" / "andon-protocol.md"
_FIXTURE_BASE = _REPO_ROOT / "tests" / "fixtures" / "dummy-project"
_FIXTURE_CONFIG = _FIXTURE_BASE / ".harness" / "config.json"
_FIXTURE_SPRINTS = _FIXTURE_BASE / ".harness" / "sprints.json"
_TEST_RUN_VERIFICATION = _REPO_ROOT / "tests" / "scripts" / "test-run-verification.py"


def _pass(n: int, total: int, msg: str) -> None:
    print(f"[{n}/{total}] PASS: {msg}")


def _fail(n: int, total: int, msg: str) -> None:
    print(f"[{n}/{total}] FAIL: {msg}")


def main() -> int:
    total = 6
    failures: list[str] = []

    # -----------------------------------------------------------------------
    # Assertion 1: run-verification.py with an allowed command exits 0
    # -----------------------------------------------------------------------
    n = 1
    try:
        r = subprocess.run(
            [sys.executable, str(_RUN_VERIFICATION), "--check-only", "git diff HEAD"],
            capture_output=True,
            text=True,
        )
        if r.returncode == 0:
            _pass(n, total, "run-verification.py allowed command (git diff HEAD) exits 0")
        else:
            msg = (
                f"run-verification.py allowed command exited {r.returncode}; "
                f"stderr={r.stderr.strip()!r}"
            )
            _fail(n, total, msg)
            failures.append(msg)
    except Exception as exc:
        msg = f"run-verification.py invocation raised an exception: {exc}"
        _fail(n, total, msg)
        failures.append(msg)

    # -----------------------------------------------------------------------
    # Assertion 2: run-verification.py with a disallowed command exits non-zero
    #              and emits a rejection-related message
    # -----------------------------------------------------------------------
    n = 2
    try:
        with tempfile.TemporaryDirectory() as tmpdir:
            henka_file = pathlib.Path(tmpdir) / "henka-register.jsonl"
            r = subprocess.run(
                [
                    sys.executable,
                    str(_RUN_VERIFICATION),
                    "--check-only",
                    "--henka-output",
                    str(henka_file),
                    "rm -rf /tmp/test",
                ],
                capture_output=True,
                text=True,
            )
        if r.returncode == 0:
            msg = "run-verification.py disallowed command (rm -rf /tmp/test) exited 0 (expected non-zero)"
            _fail(n, total, msg)
            failures.append(msg)
        else:
            combined = r.stdout + r.stderr
            rejection_keywords = ["rejected", "not allowed", "disallowed", "rm", "allowlist"]
            found_keyword = any(kw.lower() in combined.lower() for kw in rejection_keywords)
            if not found_keyword:
                msg = (
                    f"run-verification.py disallowed command exited {r.returncode} "
                    f"but output contained no rejection keyword; "
                    f"stdout={r.stdout[:200]!r} stderr={r.stderr[:200]!r}"
                )
                _fail(n, total, msg)
                failures.append(msg)
            else:
                _pass(
                    n,
                    total,
                    f"run-verification.py disallowed command exits {r.returncode} with rejection message",
                )
    except Exception as exc:
        msg = f"run-verification.py disallowed-command test raised an exception: {exc}"
        _fail(n, total, msg)
        failures.append(msg)

    # -----------------------------------------------------------------------
    # Assertion 3: skills/council-autorun/SKILL.md exists and contains all 11
    #              step headings (1A, 1A.5, 1A.6, 1B, 1C, 1D, 1E, 1F, 1G, 1H, 1I)
    # -----------------------------------------------------------------------
    n = 3
    required_steps = [
        "1A", "1A.5", "1A.6", "1B", "1C", "1D", "1E", "1F", "1G", "1H", "1I"
    ]
    if not _SKILL_MD.exists():
        msg = f"skills/council-autorun/SKILL.md does not exist at {_SKILL_MD}"
        _fail(n, total, msg)
        failures.append(msg)
    else:
        text = _SKILL_MD.read_text(encoding="utf-8")
        missing_steps: list[str] = []
        for step in required_steps:
            pattern = (
                r"(?i)(#{1,4}\s+step\s+"
                + re.escape(step)
                + r"\b|step\s+"
                + re.escape(step)
                + r"[\s:*])"
            )
            if not re.search(pattern, text):
                missing_steps.append(step)
        if missing_steps:
            msg = f"SKILL.md missing step headings: {', '.join(missing_steps)}"
            _fail(n, total, msg)
            failures.append(msg)
        else:
            _pass(n, total, "SKILL.md exists and contains all 11 step headings")

    # -----------------------------------------------------------------------
    # Assertion 4: instructions/andon-protocol.md contains verbatim
    #              thank-the-puller text
    # -----------------------------------------------------------------------
    n = 4
    verbatim = "Thank you for stopping the line"
    if not _ANDON_PROTOCOL.exists():
        msg = f"instructions/andon-protocol.md does not exist at {_ANDON_PROTOCOL}"
        _fail(n, total, msg)
        failures.append(msg)
    else:
        text = _ANDON_PROTOCOL.read_text(encoding="utf-8")
        if verbatim in text:
            _pass(
                n,
                total,
                "andon-protocol.md contains verbatim thank-the-puller text",
            )
        else:
            msg = (
                f"andon-protocol.md does not contain verbatim text {verbatim!r}"
            )
            _fail(n, total, msg)
            failures.append(msg)

    # -----------------------------------------------------------------------
    # Assertion 5: dummy-project fixture has valid JSON in config.json and
    #              sprints.json; sprints.json has >= 2 sprint entries
    # -----------------------------------------------------------------------
    n = 5
    fixture_errors: list[str] = []

    if not _FIXTURE_CONFIG.exists():
        fixture_errors.append(f"Missing fixture file: {_FIXTURE_CONFIG}")
    else:
        try:
            json.loads(_FIXTURE_CONFIG.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            fixture_errors.append(f"config.json is not valid JSON: {exc}")

    if not _FIXTURE_SPRINTS.exists():
        fixture_errors.append(f"Missing fixture file: {_FIXTURE_SPRINTS}")
    else:
        try:
            data = json.loads(_FIXTURE_SPRINTS.read_text(encoding="utf-8"))
            sprints = data.get("sprints", data if isinstance(data, list) else [])
            if len(sprints) < 2:
                fixture_errors.append(
                    f"sprints.json has {len(sprints)} sprint(s); expected >= 2"
                )
        except json.JSONDecodeError as exc:
            fixture_errors.append(f"sprints.json is not valid JSON: {exc}")

    if fixture_errors:
        for fe in fixture_errors:
            msg = f"Fixture validation error: {fe}"
            _fail(n, total, msg)
            failures.append(msg)
    else:
        _pass(
            n,
            total,
            "dummy-project fixture has valid JSON in config.json and sprints.json (>= 2 sprints)",
        )

    # -----------------------------------------------------------------------
    # Assertion 6: tests/scripts/test-run-verification.py exits 0
    # -----------------------------------------------------------------------
    n = 6
    if not _TEST_RUN_VERIFICATION.exists():
        msg = (
            f"tests/scripts/test-run-verification.py does not exist at "
            f"{_TEST_RUN_VERIFICATION}"
        )
        _fail(n, total, msg)
        failures.append(msg)
    else:
        try:
            r = subprocess.run(
                [sys.executable, str(_TEST_RUN_VERIFICATION)],
                capture_output=True,
                text=True,
            )
            if r.returncode == 0:
                _pass(n, total, "tests/scripts/test-run-verification.py exits 0")
            else:
                msg = (
                    f"tests/scripts/test-run-verification.py exited {r.returncode}; "
                    f"stdout={r.stdout[-400:]!r} stderr={r.stderr[-200:]!r}"
                )
                _fail(n, total, msg)
                failures.append(msg)
        except Exception as exc:
            msg = f"test-run-verification.py invocation raised an exception: {exc}"
            _fail(n, total, msg)
            failures.append(msg)

    # -----------------------------------------------------------------------
    # Summary
    # -----------------------------------------------------------------------
    n_fail = len(failures)
    if n_fail == 0:
        print("S4 ACCEPTANCE TEST: ALL 6 ASSERTIONS PASS")
        return 0
    else:
        print(f"S4 ACCEPTANCE TEST: {n_fail} ASSERTIONS FAILED")
        return 1


if __name__ == "__main__":
    sys.exit(main())
