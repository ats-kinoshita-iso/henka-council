"""End-to-end integration test for the from-plan pre-sprint chain.

Exercises Steps 2, 3, and 5 of the from-plan procedure against a real
tempdir project. Step 4 (hook self-check) and Step 6 (dispatch) are
out of scope here: hook registration is a `.claude/settings.local.json`
concern verified by the council-kickoff suite, and dispatch is a
runtime `Task` invocation that cannot be unit-tested.

What the chain proves:

  1. classify-plan-intent.py inspects a pre-sprint project state and
     returns {"route": "pre-sprint", "sprint": N}.
  2. persist-plan.py writes
     `.council/proposed/sprint-NN-contract-seed.md` with valid
     frontmatter and emits its canonical path on stdout.
  3. The persisted file's `plan_sha256` matches the SHA-256 of the
     normalised body bytes (chain integrity).
  4. append-decision.py accepts a `plan-bridge` decision-log entry
     whose evidence_cited sha256 matches the persisted file's
     `plan_sha256` and writes a validated JSONL line.

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
DECISION_SCHEMA = _REPO_ROOT / "schemas" / "decision-log-entry.schema.json"


PRE_SPRINT_STATE = {
    "current_sprint": 3,
    "sprints": [
        {"number": 1, "status": "PASS"},
        {"number": 2, "status": "PASS"},
    ],
}


PLAN_BODY = """# Sprint 3 contract seed

This is a non-binding seed for the contract negotiator. It should land
verbatim at `.council/proposed/sprint-03-contract-seed.md` and be
referenced by the orchestrator's Task dispatch to harness-sprint.
"""


def run(args: list[str], cwd: pathlib.Path) -> subprocess.CompletedProcess:
    """Invoke a Python script with subprocess and return the result."""
    return subprocess.run(
        [sys.executable] + args,
        capture_output=True,
        text=True,
        cwd=str(cwd),
    )


def setup_pre_sprint_project(root: pathlib.Path) -> None:
    """Stage a tempdir that the classifier should label `pre-sprint`."""
    harness = root / ".harness"
    contracts = harness / "contracts"
    council = root / ".council"
    harness.mkdir()
    contracts.mkdir()
    council.mkdir()
    (harness / "sprint-state.json").write_text(
        json.dumps(PRE_SPRINT_STATE), encoding="utf-8"
    )


def extract_frontmatter(content: str) -> dict:
    """Parse the JSON frontmatter from a persisted plan file."""
    match = re.match(r"^---\n(.*?)\n---\n\n(.*)$", content, re.DOTALL)
    if not match:
        raise ValueError("could not locate frontmatter fence in persisted file")
    return json.loads(match.group(1))


def expected_sha256(body: str) -> str:
    """Replicate persist-plan.py's normalisation and digest."""
    normalised = body if body.endswith("\n") else body + "\n"
    return hashlib.sha256(normalised.encode("utf-8")).hexdigest()


def main() -> int:
    """Run the chain end-to-end against a fresh tempdir."""
    failures: list[str] = []

    with tempfile.TemporaryDirectory() as tmp:
        root = pathlib.Path(tmp)
        setup_pre_sprint_project(root)

        # ----- Step 2 — classify ---------------------------------------
        result = run([str(CLASSIFY), "--project-root", str(root)], cwd=root)
        if result.returncode != 0:
            failures.append(
                f"classify: expected exit 0, got {result.returncode}; "
                f"stderr={result.stderr.strip()!r}"
            )
            classified = {}
        else:
            try:
                classified = json.loads(result.stdout)
            except json.JSONDecodeError as exc:
                failures.append(f"classify: stdout was not JSON ({exc})")
                classified = {}

        if classified.get("route") != "pre-sprint":
            failures.append(
                f"classify: expected route=pre-sprint, got {classified.get('route')!r}"
            )
        if classified.get("sprint") != 3:
            failures.append(
                f"classify: expected sprint=3, got {classified.get('sprint')!r}"
            )

        # ----- Step 3 — persist ----------------------------------------
        plan_path = root / "plan-body.md"
        plan_path.write_text(PLAN_BODY, encoding="utf-8")

        sprint = classified.get("sprint", 3)
        persist_result = run(
            [
                str(PERSIST),
                "--route", "pre-sprint",
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

        persisted_path = root / ".council" / "proposed" / "sprint-03-contract-seed.md"
        if not persisted_path.exists():
            failures.append(f"persist: expected file at {persisted_path}")
            return _report(failures)

        content = persisted_path.read_text(encoding="utf-8")
        try:
            frontmatter = extract_frontmatter(content)
        except (ValueError, json.JSONDecodeError) as exc:
            failures.append(f"persist: could not parse frontmatter ({exc})")
            return _report(failures)

        if frontmatter.get("intent") != "pre-sprint":
            failures.append(
                f"persist: intent expected pre-sprint, got {frontmatter.get('intent')!r}"
            )
        if frontmatter.get("sprint_target") != 3:
            failures.append(
                f"persist: sprint_target expected 3, "
                f"got {frontmatter.get('sprint_target')!r}"
            )

        # ----- chain integrity: sha256 matches the normalised body ----
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
            "timestamp": "2026-05-20T20:00:00Z",
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
            "description": "Plan-mode artifact persisted and routed to pre-sprint",
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

        if not log_path.exists():
            failures.append(f"append-decision: expected log at {log_path}")
        else:
            line = log_path.read_text(encoding="utf-8").splitlines()[-1]
            try:
                logged = json.loads(line)
            except json.JSONDecodeError as exc:
                failures.append(f"append-decision: log line not JSON ({exc})")
                logged = {}
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
    print("PASS: from-plan pre-sprint chain — classify, persist, append-decision")
    return 0


if __name__ == "__main__":
    sys.exit(main())
