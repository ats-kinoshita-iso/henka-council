"""Self-contained end-to-end test for scripts/update-effective-autonomy.py.

Verifies:
  1. Starting from a non-existent state file, calling the script with --level 4
     (--trigger-type initial) creates a valid file with level=4 and
     trigger_history length == 1.
  2. Calling the script a second time with --level 3 (--trigger-type sprint-fail)
     appends to trigger_history (length becomes 2) without overwriting previous entry.
  3. The final file validates against schemas/effective-autonomy.schema.json using
     jsonschema.Draft7Validator.

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

import jsonschema


# Resolve paths relative to this file so the test works from any CWD
_REPO_ROOT = pathlib.Path(__file__).parent.parent.parent
SCRIPT = _REPO_ROOT / "scripts" / "update-effective-autonomy.py"
SCHEMA_PATH = _REPO_ROOT / "schemas" / "effective-autonomy.schema.json"


def run_script(args: list[str]) -> subprocess.CompletedProcess:
    """Run the update-effective-autonomy.py script with the given args."""
    return subprocess.run(
        [sys.executable, str(SCRIPT)] + args,
        capture_output=True,
        text=True,
    )


def load_schema() -> dict:
    """Load the effective-autonomy schema."""
    return json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))


def validate_against_schema(state: dict, schema: dict) -> list[str]:
    """Return a list of validation error messages (empty list = valid)."""
    validator = jsonschema.Draft7Validator(schema)
    errors = sorted(validator.iter_errors(state), key=lambda e: list(e.path))
    return [
        f"[{e.validator}] at {' -> '.join(str(p) for p in e.absolute_path) or '(root)'}: {e.message}"
        for e in errors
    ]


def main() -> int:
    """Run all test steps; return 0 on pass, 1 on any failure."""
    failures: list[str] = []
    schema = load_schema()

    with tempfile.TemporaryDirectory() as tmpdir:
        state_file = pathlib.Path(tmpdir) / "effective-autonomy.json"

        # -----------------------------------------------------------------
        # Step 1: initial baseline — level 4, trigger_history length == 1
        # -----------------------------------------------------------------
        result1 = run_script([
            "--level", "4",
            "--trigger-type", "initial",
            "--reason", "initial baseline",
            "--from-level", "4",
            "--file", str(state_file),
        ])

        if result1.returncode != 0:
            failures.append(
                f"Step 1: script exited {result1.returncode}; stderr={result1.stderr.strip()!r}"
            )
        elif not state_file.exists():
            failures.append("Step 1: state file was not created")
        else:
            state1 = json.loads(state_file.read_text(encoding="utf-8"))

            if state1.get("level") != 4:
                failures.append(f"Step 1: expected level=4, got {state1.get('level')!r}")

            history1 = state1.get("trigger_history", [])
            if len(history1) != 1:
                failures.append(
                    f"Step 1: expected trigger_history length=1, got {len(history1)}"
                )

            schema_errors1 = validate_against_schema(state1, schema)
            if schema_errors1:
                for err in schema_errors1:
                    failures.append(f"Step 1 schema validation: {err}")

        # -----------------------------------------------------------------
        # Step 2: drop to level 3 — trigger_history length == 2
        # -----------------------------------------------------------------
        result2 = run_script([
            "--level", "3",
            "--trigger-type", "consecutive-fail-drop",
            "--reason", "two-sprint-fail",
            "--from-level", "4",
            "--file", str(state_file),
        ])

        if result2.returncode != 0:
            failures.append(
                f"Step 2: script exited {result2.returncode}; stderr={result2.stderr.strip()!r}"
            )
        elif not state_file.exists():
            failures.append("Step 2: state file disappeared unexpectedly")
        else:
            state2 = json.loads(state_file.read_text(encoding="utf-8"))

            if state2.get("level") != 3:
                failures.append(f"Step 2: expected level=3, got {state2.get('level')!r}")

            history2 = state2.get("trigger_history", [])
            if len(history2) != 2:
                failures.append(
                    f"Step 2: expected trigger_history length=2, got {len(history2)}"
                )
            else:
                # Ensure original entry is still present (not overwritten)
                first = history2[0]
                if first.get("trigger_type") != "initial":
                    failures.append(
                        f"Step 2: first trigger_history entry should still have trigger_type='initial', "
                        f"got {first.get('trigger_type')!r}"
                    )

            schema_errors2 = validate_against_schema(state2, schema)
            if schema_errors2:
                for err in schema_errors2:
                    failures.append(f"Step 2 schema validation: {err}")

    # -----------------------------------------------------------------
    # Report results
    # -----------------------------------------------------------------
    if failures:
        print("FAIL:", file=sys.stderr)
        for f in failures:
            print(f"  - {f}", file=sys.stderr)
        return 1

    print("ALL PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
