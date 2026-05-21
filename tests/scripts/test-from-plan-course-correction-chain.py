"""End-to-end integration test for the from-plan course-correction chain.

Exercises Steps 2, 3, and 5 against a tempdir staged with an open
high-risk active henka so the classifier returns `course-correction`.
Step 6 dispatch (the `/henkaten-council:council-review --consider`
Task invocation) is a runtime concern and is not unit-tested here.

What the chain proves:

  1. classify-plan-intent.py returns
     {"route": "course-correction", "sprint": <sprint_context>}
     when an open high-risk active henka is present.
  2. persist-plan.py writes a position paper to
     `.council/proposed/position-paper-sprint-NN-<ts>.md` with a
     timestamp in the filename. The script prints the canonical path
     to stdout (the test captures and uses it rather than guessing).
  3. The persisted frontmatter's `plan_sha256` equals SHA-256 over
     the normalised body.
  4. A `plan-bridge` decision-log entry citing that sha256 validates
     and appends cleanly.

Exit codes:
    0  — all assertions passed
    1  — one or more assertions failed
"""
from __future__ import annotations

import hashlib
import json
import pathlib
import re
import subprocess
import sys
import tempfile

_REPO_ROOT = pathlib.Path(__file__).parent.parent.parent
CLASSIFY = _REPO_ROOT / "scripts" / "classify-plan-intent.py"
PERSIST = _REPO_ROOT / "scripts" / "persist-plan.py"
APPEND_DECISION = _REPO_ROOT / "scripts" / "append-decision.py"


COURSE_CORRECTION_STATE = {
    "current_sprint": 4,
    "sprints": [
        {"number": 1, "status": "PASS"},
        {"number": 2, "status": "PASS"},
        {"number": 3, "status": "PASS"},
    ],
}


OPEN_HIGH_RISK_HENKA = {
    "henka_id": "HK-0042",
    "sprint_context": 3,
    "fourM_axis": "Method",
    "category": "scope-change",
    "change_origin": "active",
    "impact_level": "high-risk",
    "status": "classified",
    "description": "Stub henka for course-correction integration test.",
    "affected_artifacts": ["spec.md"],
    "response_type": "propose-to-user",
    "evidence": [],
    "detected_at": "2026-05-20T20:00:00Z",
}


PLAN_BODY = """# Course-correction proposal

Proposed change to address the open high-risk henka HK-0042. This is a
NON-binding seed for the council fan-out; agents review the proposal
rather than defer to it.
"""


def run(args: list[str], cwd: pathlib.Path) -> subprocess.CompletedProcess:
    """Run a Python script via subprocess and capture stdout/stderr."""
    return subprocess.run(
        [sys.executable] + args,
        capture_output=True,
        text=True,
        cwd=str(cwd),
    )


def setup_course_correction_project(root: pathlib.Path) -> None:
    """Stage a tempdir whose state forces a course-correction classification."""
    harness = root / ".harness"
    contracts = harness / "contracts"
    council = root / ".council"
    harness.mkdir()
    contracts.mkdir()
    council.mkdir()
    (harness / "sprint-state.json").write_text(
        json.dumps(COURSE_CORRECTION_STATE), encoding="utf-8"
    )
    register = council / "henka-register.jsonl"
    register.write_text(json.dumps(OPEN_HIGH_RISK_HENKA) + "\n", encoding="utf-8")


def extract_frontmatter(content: str) -> dict:
    """Parse JSON frontmatter from a persisted plan file."""
    match = re.match(r"^---\n(.*?)\n---\n\n(.*)$", content, re.DOTALL)
    if not match:
        raise ValueError("could not locate frontmatter fence")
    return json.loads(match.group(1))


def expected_sha256(body: str) -> str:
    """Replicate persist-plan.py body canonicalisation + digest."""
    normalised = body if body.endswith("\n") else body + "\n"
    return hashlib.sha256(normalised.encode("utf-8")).hexdigest()


def main() -> int:
    """Run the chain end-to-end against a fresh tempdir."""
    failures: list[str] = []

    with tempfile.TemporaryDirectory() as tmp:
        root = pathlib.Path(tmp)
        setup_course_correction_project(root)

        # ----- Step 2 — classify ---------------------------------------
        result = run([str(CLASSIFY), "--project-root", str(root)], cwd=root)
        if result.returncode != 0:
            failures.append(
                f"classify: expected exit 0, got {result.returncode}; "
                f"stderr={result.stderr.strip()!r}"
            )
            return _report(failures)

        classified = json.loads(result.stdout)
        if classified.get("route") != "course-correction":
            failures.append(
                f"classify: expected course-correction, got {classified.get('route')!r}"
            )
        if classified.get("sprint") != 3:
            failures.append(
                f"classify: expected sprint=3 (from henka sprint_context), "
                f"got {classified.get('sprint')!r}"
            )

        sprint = classified.get("sprint", 3)

        # ----- Step 3 — persist ----------------------------------------
        plan_path = root / "plan-body.md"
        plan_path.write_text(PLAN_BODY, encoding="utf-8")

        persist_result = run(
            [
                str(PERSIST),
                "--route", "course-correction",
                "--sprint", str(sprint),
                "--plan-body", str(plan_path),
            ],
            cwd=root,
        )
        if persist_result.returncode != 0:
            failures.append(
                f"persist: expected exit 0, got {persist_result.returncode}; "
                f"stderr={persist_result.stderr.strip()!r}"
            )
            return _report(failures)

        # course-correction paths embed a timestamp, so capture from stdout
        persisted_rel = persist_result.stdout.strip().splitlines()[-1]
        persisted_path = (root / persisted_rel).resolve()
        if not persisted_path.exists():
            failures.append(
                f"persist: stdout path {persisted_rel!r} does not resolve to a file"
            )
            return _report(failures)

        # filename pattern: position-paper-sprint-NN-<ts>.md
        if not re.match(
            r"^position-paper-sprint-\d{2}-\d{8}T\d{6}Z\.md$",
            persisted_path.name,
        ):
            failures.append(
                f"persist: filename {persisted_path.name!r} does not match "
                f"the position-paper-sprint-NN-<ts>.md pattern"
            )

        content = persisted_path.read_text(encoding="utf-8")
        frontmatter = extract_frontmatter(content)

        if frontmatter.get("intent") != "course-correction":
            failures.append(
                f"persist: intent expected course-correction, "
                f"got {frontmatter.get('intent')!r}"
            )
        if frontmatter.get("sprint_target") != sprint:
            failures.append(
                f"persist: sprint_target expected {sprint}, "
                f"got {frontmatter.get('sprint_target')!r}"
            )

        actual_sha = frontmatter.get("plan_sha256", "")
        expected = expected_sha256(PLAN_BODY)
        if actual_sha != expected:
            failures.append(
                f"persist: plan_sha256 mismatch — frontmatter={actual_sha!r}, "
                f"expected={expected!r}"
            )

        # ----- Step 5 — append decision-log entry ----------------------
        decision_entry = {
            "decision_id": "DEC-0001",
            "timestamp": "2026-05-20T20:30:00Z",
            "decision_type": "plan-bridge",
            "decision_outcome": "applied",
            "council_agents_involved": ["orchestrator"],
            "evidence_cited": [
                {"path": str(persisted_path), "sha256": actual_sha},
            ],
            "applied_automatically": True,
            "user_approval_required": False,
            "affected_files": [str(persisted_path)],
            "sprint_context": sprint,
            "autonomy_level_used": 4,
            "effective_autonomy_at_decision": 4,
            "reversibility": "reversible",
            "nemawashi_walkthrough_version": None,
            "description": (
                "Plan-mode artifact persisted and routed to course-correction"
            ),
        }
        entry_file = root / "decision-entry.json"
        entry_file.write_text(json.dumps(decision_entry), encoding="utf-8")

        log_path = root / "out.jsonl"
        append_result = run(
            [
                str(APPEND_DECISION),
                "--file", str(entry_file),
                "--output", str(log_path),
            ],
            cwd=root,
        )
        if append_result.returncode != 0:
            failures.append(
                f"append-decision: expected exit 0, got {append_result.returncode}; "
                f"stderr={append_result.stderr.strip()!r}"
            )

        if log_path.exists():
            line = log_path.read_text(encoding="utf-8").splitlines()[-1]
            logged = json.loads(line)
            cited = (logged.get("evidence_cited") or [{}])[0].get("sha256")
            if cited != actual_sha:
                failures.append(
                    f"append-decision: cited sha256 {cited!r} does not match "
                    f"persisted plan_sha256 {actual_sha!r}"
                )

    return _report(failures)


def _report(failures: list[str]) -> int:
    """Print results and return the appropriate exit code."""
    if failures:
        print("FAIL:", file=sys.stderr)
        for f in failures:
            print(f"  - {f}", file=sys.stderr)
        return 1
    print(
        "PASS: from-plan course-correction chain — classify, persist, "
        "append-decision"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
