"""Self-contained tests for scripts/classify-plan-intent.py.

Covers the four observable outcomes:

  1. No `.harness/` -> route=bootstrap, exit 0.
  2. Pending sprint with no contract -> route=pre-sprint, sprint=N, exit 0.
  3. Most recent sprint FAIL -> route=course-correction, sprint=N, exit 0.
  4. Open high-risk active henka -> route=course-correction (henka path
     takes precedence over a passing sprint), exit 0.

Plus the "ambiguous" outcome (state consistent but no rule fires) which
exits 2.

Exit codes:
    0  — all assertions passed
    1  — one or more assertions failed
"""
from __future__ import annotations

import json
import pathlib
import subprocess
import sys
import tempfile

_REPO_ROOT = pathlib.Path(__file__).parent.parent.parent
SCRIPT = _REPO_ROOT / "scripts" / "classify-plan-intent.py"


def run_classifier(project_root: pathlib.Path) -> subprocess.CompletedProcess:
    """Invoke the classifier against the given project root."""
    return subprocess.run(
        [sys.executable, str(SCRIPT), "--project-root", str(project_root)],
        capture_output=True,
        text=True,
    )


def write_sprint_state(harness: pathlib.Path, state: dict) -> None:
    """Write sprint-state.json into a project-root .harness/ directory."""
    harness.mkdir(parents=True, exist_ok=True)
    (harness / "sprint-state.json").write_text(
        json.dumps(state), encoding="utf-8"
    )


def write_henka_records(council: pathlib.Path, records: list[dict]) -> None:
    """Write henka records as one JSON line each into henka-register.jsonl."""
    council.mkdir(parents=True, exist_ok=True)
    register = council / "henka-register.jsonl"
    with register.open("w", encoding="utf-8") as fh:
        for record in records:
            fh.write(json.dumps(record) + "\n")


def expect(
    failures: list[str],
    label: str,
    result: subprocess.CompletedProcess,
    expected_route: str,
    expected_sprint=None,
    expected_exit: int = 0,
) -> None:
    """Compare a classifier invocation against expected outcome."""
    if result.returncode != expected_exit:
        failures.append(
            f"{label}: expected exit {expected_exit}, got {result.returncode}; "
            f"stderr={result.stderr.strip()!r}"
        )
        return
    try:
        payload = json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        failures.append(f"{label}: stdout was not JSON ({exc}): {result.stdout!r}")
        return
    if payload.get("route") != expected_route:
        failures.append(
            f"{label}: expected route={expected_route!r}, got {payload.get('route')!r}"
        )
    if payload.get("sprint") != expected_sprint:
        failures.append(
            f"{label}: expected sprint={expected_sprint!r}, got {payload.get('sprint')!r}"
        )


def case_bootstrap_no_harness(failures: list[str]) -> None:
    """`.harness/` absent -> bootstrap."""
    with tempfile.TemporaryDirectory() as tmp:
        root = pathlib.Path(tmp)
        result = run_classifier(root)
        expect(failures, "bootstrap-no-harness", result, "bootstrap", None, 0)


def case_bootstrap_no_council(failures: list[str]) -> None:
    """`.harness/` present but `.council/` absent -> bootstrap."""
    with tempfile.TemporaryDirectory() as tmp:
        root = pathlib.Path(tmp)
        write_sprint_state(root / ".harness", {"current_sprint": 1, "sprints": []})
        result = run_classifier(root)
        expect(failures, "bootstrap-no-council", result, "bootstrap", None, 0)


def case_pre_sprint_pending_no_contract(failures: list[str]) -> None:
    """Pending integer current_sprint with no contract file -> pre-sprint."""
    with tempfile.TemporaryDirectory() as tmp:
        root = pathlib.Path(tmp)
        write_sprint_state(
            root / ".harness",
            {
                "current_sprint": 3,
                "sprints": [
                    {"number": 1, "status": "PASS"},
                    {"number": 2, "status": "PASS"},
                ],
            },
        )
        (root / ".council").mkdir()
        (root / ".harness" / "contracts").mkdir()
        result = run_classifier(root)
        expect(failures, "pre-sprint-pending", result, "pre-sprint", 3, 0)


def case_pre_sprint_skipped_when_contract_exists(failures: list[str]) -> None:
    """If the contract file already exists, do NOT classify as pre-sprint."""
    with tempfile.TemporaryDirectory() as tmp:
        root = pathlib.Path(tmp)
        write_sprint_state(
            root / ".harness",
            {
                "current_sprint": 3,
                "sprints": [
                    {"number": 1, "status": "PASS"},
                    {"number": 2, "status": "PASS"},
                ],
            },
        )
        contracts = root / ".harness" / "contracts"
        contracts.mkdir()
        (contracts / "sprint-03.md").write_text("# Sprint 3", encoding="utf-8")
        (root / ".council").mkdir()
        result = run_classifier(root)
        expect(failures, "no-pre-sprint-with-contract", result, "ambiguous", None, 2)


def case_course_correction_via_fail(failures: list[str]) -> None:
    """Most recent FAIL sprint -> course-correction."""
    with tempfile.TemporaryDirectory() as tmp:
        root = pathlib.Path(tmp)
        write_sprint_state(
            root / ".harness",
            {
                "current_sprint": 4,
                "sprints": [
                    {"number": 1, "status": "PASS"},
                    {"number": 2, "status": "PASS"},
                    {"number": 3, "status": "FAIL"},
                ],
            },
        )
        (root / ".council").mkdir()
        result = run_classifier(root)
        expect(failures, "course-correction-fail", result, "course-correction", 3, 0)


def case_course_correction_via_open_henka(failures: list[str]) -> None:
    """Open high-risk active henka -> course-correction even if sprints PASS."""
    with tempfile.TemporaryDirectory() as tmp:
        root = pathlib.Path(tmp)
        write_sprint_state(
            root / ".harness",
            {
                "current_sprint": 4,
                "sprints": [
                    {"number": 1, "status": "PASS"},
                    {"number": 2, "status": "PASS"},
                    {"number": 3, "status": "PASS"},
                ],
            },
        )
        write_henka_records(
            root / ".council",
            [
                {
                    "henka_id": "HK-0007",
                    "change_origin": "active",
                    "impact_level": "high-risk",
                    "status": "classified",
                    "sprint_context": 3,
                }
            ],
        )
        result = run_classifier(root)
        expect(failures, "course-correction-henka", result, "course-correction", 3, 0)


def case_henka_closed_does_not_block(failures: list[str]) -> None:
    """A closed high-risk henka must not be treated as open."""
    with tempfile.TemporaryDirectory() as tmp:
        root = pathlib.Path(tmp)
        write_sprint_state(
            root / ".harness",
            {
                "current_sprint": 4,
                "sprints": [
                    {"number": 1, "status": "PASS"},
                    {"number": 2, "status": "PASS"},
                    {"number": 3, "status": "PASS"},
                ],
            },
        )
        write_henka_records(
            root / ".council",
            [
                {
                    "henka_id": "HK-0007",
                    "change_origin": "active",
                    "impact_level": "high-risk",
                    "status": "closed",
                    "sprint_context": 3,
                }
            ],
        )
        contracts = root / ".harness" / "contracts"
        contracts.mkdir()
        result = run_classifier(root)
        expect(failures, "closed-henka-pre-sprint", result, "pre-sprint", 4, 0)


def case_passive_high_risk_is_ignored(failures: list[str]) -> None:
    """A passive (not active) high-risk record must not trigger course-correction."""
    with tempfile.TemporaryDirectory() as tmp:
        root = pathlib.Path(tmp)
        write_sprint_state(
            root / ".harness",
            {
                "current_sprint": 4,
                "sprints": [{"number": 3, "status": "PASS"}],
            },
        )
        write_henka_records(
            root / ".council",
            [
                {
                    "henka_id": "HK-0008",
                    "change_origin": "passive",
                    "impact_level": "high-risk",
                    "status": "classified",
                    "sprint_context": 3,
                }
            ],
        )
        contracts = root / ".harness" / "contracts"
        contracts.mkdir()
        result = run_classifier(root)
        expect(failures, "passive-henka-pre-sprint", result, "pre-sprint", 4, 0)


def case_ambiguous_when_complete(failures: list[str]) -> None:
    """current_sprint = 'complete' and no FAIL/open henka -> ambiguous."""
    with tempfile.TemporaryDirectory() as tmp:
        root = pathlib.Path(tmp)
        write_sprint_state(
            root / ".harness",
            {
                "current_sprint": "complete",
                "sprints": [
                    {"number": 1, "status": "PASS"},
                    {"number": 2, "status": "PASS"},
                ],
            },
        )
        (root / ".council").mkdir()
        result = run_classifier(root)
        expect(failures, "ambiguous-complete", result, "ambiguous", None, 2)


def main() -> int:
    """Run all test cases and report."""
    failures: list[str] = []
    for case in (
        case_bootstrap_no_harness,
        case_bootstrap_no_council,
        case_pre_sprint_pending_no_contract,
        case_pre_sprint_skipped_when_contract_exists,
        case_course_correction_via_fail,
        case_course_correction_via_open_henka,
        case_henka_closed_does_not_block,
        case_passive_high_risk_is_ignored,
        case_ambiguous_when_complete,
    ):
        case(failures)

    if failures:
        print("FAIL:", file=sys.stderr)
        for f in failures:
            print(f"  - {f}", file=sys.stderr)
        return 1

    print("PASS: classify-plan-intent.py — 9 cases")
    return 0


if __name__ == "__main__":
    sys.exit(main())
