"""Classify a plan-mode artifact's dispatch route from live governance state.

Reads `.harness/` and `.council/` state under the project root and decides
which lifecycle entry point the plan targets. The route is consumed by
`scripts/persist-plan.py` and by the orchestrator's Step 6 dispatch.

Classification rules (skills/from-plan/SKILL.md Step 2):

  bootstrap         — `.harness/` does not exist (no kickoff yet).
  course-correction — `.council/henka-register.jsonl` contains an open
                      `change_origin: active` record flagged
                      `impact_level: high-risk` (status not in
                      {responded, closed}); OR the most recent sprint
                      entry in `.harness/sprint-state.json` is FAIL.
  pre-sprint        — both `.harness/` and `.council/` exist; the current
                      sprint is a pending integer and its contract file
                      `.harness/contracts/sprint-NN.md` does not yet
                      exist.
  ambiguous         — state is consistent but no rule fires (e.g. the
                      previous sprint passed and no new sprint is open).
                      Caller decides how to proceed; the SKILL.md tells
                      the Orchestrator to ask the user.

Course-correction is evaluated before pre-sprint because an open
high-risk henka or a failed sprint blocks normal forward progress.

Output: a single JSON object on stdout:

    {"route": "<route>", "sprint": <int|null>, "reason": "<short reason>"}

Exit codes:
    0  — classified successfully (any of the three concrete routes)
    1  — I/O error, malformed state file
    2  — usage error or ambiguous (no rule fires; the caller must ask)
"""
from __future__ import annotations

import argparse
import json
import pathlib
import sys
from typing import Optional

HARNESS_DIR = pathlib.Path(".harness")
COUNCIL_DIR = pathlib.Path(".council")
SPRINT_STATE = HARNESS_DIR / "sprint-state.json"
CONTRACTS_DIR = HARNESS_DIR / "contracts"
HENKA_REGISTER = COUNCIL_DIR / "henka-register.jsonl"

OPEN_STATUSES = {"classified", "assessed"}


def read_json(path: pathlib.Path) -> dict:
    """Read and parse a JSON file. Raises OSError or json.JSONDecodeError."""
    return json.loads(path.read_text(encoding="utf-8"))


def has_open_high_risk_henka(register: pathlib.Path) -> Optional[dict]:
    """Return the first open high-risk active henka record, or None.

    "Open" means status is `classified` or `assessed` (not yet responded
    to or closed). Lines that fail to parse are skipped — a corrupt line
    must not silently change the route, but malformed registers should
    not crash the classifier either; the harness's own integrity tests
    catch corruption separately.
    """
    if not register.exists():
        return None
    try:
        with register.open("r", encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    record = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if (
                    record.get("change_origin") == "active"
                    and record.get("impact_level") == "high-risk"
                    and record.get("status") in OPEN_STATUSES
                ):
                    return record
    except OSError:
        return None
    return None


def most_recent_failed_sprint(state: dict) -> Optional[int]:
    """Return the number of the most recent FAIL sprint entry, or None.

    "Most recent" is the entry with the largest `number` field that
    carries status FAIL. Status comparison is case-insensitive because
    the harness has historically written both `PASS` and `pass`.
    """
    candidates = []
    for entry in state.get("sprints", []):
        status = str(entry.get("status", "")).upper()
        number = entry.get("number")
        if status == "FAIL" and isinstance(number, int):
            candidates.append(number)
    return max(candidates) if candidates else None


def pending_sprint_without_contract(
    state: dict, contracts_dir: pathlib.Path
) -> Optional[int]:
    """Return the pending sprint number if its contract is missing.

    The "pending sprint" is `state["current_sprint"]` when it is an
    integer (the harness writes the literal string "complete" once all
    sprints have passed; numeric values are in-flight slots). The
    contract is considered missing when `sprint-NN.md` is absent from
    `contracts/` — that is the file the planner emits at the start of a
    sprint, so its absence is the canonical "needs a seed" signal.
    """
    current = state.get("current_sprint")
    if not isinstance(current, int):
        return None
    contract = contracts_dir / f"sprint-{current:02d}.md"
    return current if not contract.exists() else None


def classify(project_root: pathlib.Path) -> dict:
    """Run the classification and return a result dict."""
    harness = project_root / HARNESS_DIR
    council = project_root / COUNCIL_DIR
    state_path = project_root / SPRINT_STATE
    contracts = project_root / CONTRACTS_DIR
    register = project_root / HENKA_REGISTER

    if not harness.exists():
        return {
            "route": "bootstrap",
            "sprint": None,
            "reason": ".harness/ does not exist; the project has not been kicked off.",
        }

    if not council.exists():
        return {
            "route": "bootstrap",
            "sprint": None,
            "reason": ".harness/ exists but .council/ does not; kickoff is incomplete.",
        }

    open_henka = has_open_high_risk_henka(register)
    if open_henka is not None:
        sprint = open_henka.get("sprint_context")
        return {
            "route": "course-correction",
            "sprint": sprint if isinstance(sprint, int) else None,
            "reason": (
                f"Open high-risk active henka {open_henka.get('henka_id', '<no id>')} "
                f"requires response before normal sprint progress."
            ),
        }

    state: dict = {}
    if state_path.exists():
        try:
            state = read_json(state_path)
        except (OSError, json.JSONDecodeError) as exc:
            raise SystemExit(
                f"ERROR: failed to read {state_path}: {exc}"
            ) from exc

    failed = most_recent_failed_sprint(state)
    if failed is not None:
        return {
            "route": "course-correction",
            "sprint": failed,
            "reason": f"Most recent FAIL sprint is {failed}.",
        }

    pending = pending_sprint_without_contract(state, contracts)
    if pending is not None:
        return {
            "route": "pre-sprint",
            "sprint": pending,
            "reason": (
                f"Sprint {pending} is pending and "
                f"contracts/sprint-{pending:02d}.md is absent."
            ),
        }

    return {
        "route": "ambiguous",
        "sprint": None,
        "reason": (
            "Both .harness/ and .council/ exist; the most recent sprint "
            "passed and no pending sprint slot is open. The user must "
            "name the intent explicitly."
        ),
    }


def main(argv: Optional[list[str]] = None) -> int:
    """Entry point; returns integer exit code."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--project-root",
        type=pathlib.Path,
        default=pathlib.Path("."),
        help="Project root (default: current directory).",
    )
    args = parser.parse_args(argv)

    try:
        result = classify(args.project_root.resolve())
    except SystemExit as exc:
        print(str(exc), file=sys.stderr)
        return 1

    print(json.dumps(result))
    return 2 if result["route"] == "ambiguous" else 0


if __name__ == "__main__":
    sys.exit(main())
