"""Read, merge, and write .council/state/effective-autonomy.json with trigger_history append semantics.

The trigger_history array is never overwritten — each invocation appends exactly one entry.
The final merged state is validated against schemas/effective-autonomy.schema.json before writing.

Usage:
    python3 scripts/update-effective-autonomy.py \\
        --level 3 --reason "two-sprint-fail" --trigger-type consecutive-fail-drop \\
        --from-level 4

Exit codes:
    0  — state written successfully
    1  — validation failure or I/O error
    2  — usage error
"""
from __future__ import annotations

import argparse
import json
import pathlib
import sys
from datetime import datetime, timezone
from typing import Optional

try:
    import jsonschema
except ModuleNotFoundError:
    print(
        "ERROR: the 'jsonschema' package is required but not installed.\n"
        "  Install it with: python3 -m pip install -r requirements.txt\n"
        "  (run from the plugin root; on Windows substitute 'python' for 'python3')",
        file=sys.stderr,
    )
    sys.exit(1)


SCHEMA_PATH = pathlib.Path(__file__).parent.parent / "schemas" / "effective-autonomy.schema.json"
DEFAULT_STATE_FILE = pathlib.Path(".council") / "state" / "effective-autonomy.json"

TRIGGER_TYPES = [
    "consecutive-fail-drop",
    "andon-stop-drop",
    "high-risk-henkaten-drop",
    "restore-autonomy",
    "manual-override",
    "sprint-pass-restore",
    "initial",
]


def load_schema() -> dict:
    """Load and return the effective-autonomy JSON schema."""
    return json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))


def load_existing(state_file: pathlib.Path) -> dict:
    """Return existing state dict, or an empty baseline if the file does not exist."""
    if state_file.exists():
        try:
            return json.loads(state_file.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            print(f"WARNING: Existing state file is corrupt; starting fresh: {exc}", file=sys.stderr)
    return {}


def build_trigger_entry(
    *,
    trigger_type: str,
    from_level: int,
    to_level: int,
    reason: str,
) -> dict:
    """Build a single trigger_history entry conforming to the schema items shape."""
    return {
        "trigger_type": trigger_type,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "from_level": from_level,
        "to_level": to_level,
        "notes": reason,
    }


def validate_state(state: dict, schema: dict) -> None:
    """Validate state against schema using Draft7Validator; print errors to stderr."""
    validator = jsonschema.Draft7Validator(schema)
    errors = sorted(validator.iter_errors(state), key=lambda e: list(e.path))
    if errors:
        for err in errors:
            path = " -> ".join(str(p) for p in err.absolute_path) or "(root)"
            print(f"  [{err.validator}] at {path}: {err.message}", file=sys.stderr)
        raise jsonschema.ValidationError("Schema validation failed.")


def main(argv: Optional[list[str]] = None) -> int:
    """Entry point; returns integer exit code."""
    parser = argparse.ArgumentParser(
        description="Update .council/state/effective-autonomy.json with trigger_history append semantics."
    )
    parser.add_argument(
        "--level",
        type=int,
        required=True,
        help="New effective autonomy level (0-5).",
    )
    parser.add_argument(
        "--reason",
        type=str,
        required=True,
        help="Human-readable reason for this level change.",
    )
    parser.add_argument(
        "--trigger-type",
        type=str,
        required=True,
        choices=TRIGGER_TYPES,
        help=f"Type of trigger event: {', '.join(TRIGGER_TYPES)}.",
    )
    parser.add_argument(
        "--from-level",
        type=int,
        required=True,
        help="Effective autonomy level before this transition.",
    )
    parser.add_argument(
        "--file",
        type=pathlib.Path,
        default=DEFAULT_STATE_FILE,
        help="Path to the state file (default: .council/state/effective-autonomy.json).",
    )
    parser.add_argument(
        "--restored-when",
        type=str,
        default=None,
        help="Description of the restoration condition (null when at or above nominal level).",
    )
    args = parser.parse_args(argv)

    # Load existing state (merge semantics — never clobber trigger_history)
    existing = load_existing(args.file)

    now_iso = datetime.now(timezone.utc).isoformat()

    # Build the new trigger entry
    new_trigger = build_trigger_entry(
        trigger_type=args.trigger_type,
        from_level=args.from_level,
        to_level=args.level,
        reason=args.reason,
    )

    # Preserve existing trigger_history and append the new entry
    history: list = list(existing.get("trigger_history") or [])
    history.append(new_trigger)

    # Determine restored_when semantics
    # If level is going up (restoration event), set restored_when to now
    if args.restored_when is not None:
        restored_when: Optional[str] = args.restored_when
    elif args.level > args.from_level:
        # Level rising -> restoration occurred; record when
        restored_when = now_iso
    else:
        # Level same or dropping -> null
        restored_when = None

    # Build the merged state
    state: dict = {
        "level": args.level,
        "last_change": now_iso,
        "reason": args.reason,
        "restored_when": restored_when,
        "trigger_history": history,
    }

    # Validate before writing
    try:
        schema = load_schema()
        validate_state(state, schema)
    except jsonschema.ValidationError:
        print("INVALID: resulting state failed schema validation (details above).", file=sys.stderr)
        return 1
    except Exception as exc:
        print(f"ERROR loading schema: {exc}", file=sys.stderr)
        return 1

    # Write state file (pretty-printed, 2-space indent)
    try:
        args.file.parent.mkdir(parents=True, exist_ok=True)
        args.file.write_text(json.dumps(state, indent=2), encoding="utf-8")
    except OSError as exc:
        print(f"ERROR writing state file {args.file}: {exc}", file=sys.stderr)
        return 1

    print(f"WRITTEN: {args.file} (level={args.level}, trigger_history len={len(history)})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
