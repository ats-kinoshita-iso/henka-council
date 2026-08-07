"""Validate a decision-log-entry JSON object and append it to .council/decision-log.jsonl.

Usage:
    python3 scripts/append-decision.py --file <path-to-json>
    echo '{"decision_id": "DEC-0001", ...}' | python3 scripts/append-decision.py

Exit codes:
    0  — validated and appended successfully
    1  — validation failure, JSON parse error, or I/O error
    2  — usage error
"""
from __future__ import annotations

import argparse
import json
import pathlib
import subprocess
import sys
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


SCHEMA_PATH = pathlib.Path(__file__).parent.parent / "schemas" / "decision-log-entry.schema.json"
DEFAULT_OUTPUT = pathlib.Path(".council") / "decision-log.jsonl"


def load_schema() -> dict:
    """Load and return the decision-log-entry JSON schema."""
    return json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))


def validate(instance: dict, schema: dict) -> None:
    """Validate instance against schema using Draft7Validator; print errors to stderr."""
    validator = jsonschema.Draft7Validator(schema)
    errors = sorted(validator.iter_errors(instance), key=lambda e: list(e.path))
    if errors:
        for err in errors:
            path = " -> ".join(str(p) for p in err.absolute_path) or "(root)"
            print(f"  [{err.validator}] at {path}: {err.message}", file=sys.stderr)
        raise jsonschema.ValidationError("Schema validation failed.")


def append_line(output_path: pathlib.Path, instance: dict) -> None:
    """Append the JSON-serialised instance as one line to output_path."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(instance) + "\n")


def git_add(path: pathlib.Path) -> None:
    """Stage path with git add; silently ignore git errors."""
    subprocess.run(["git", "add", str(path)], check=False)


def main(argv: Optional[list[str]] = None) -> int:
    """Entry point; returns integer exit code."""
    parser = argparse.ArgumentParser(
        description="Validate a decision-log-entry JSON object and append it to the log."
    )
    source = parser.add_mutually_exclusive_group()
    source.add_argument(
        "--file",
        type=pathlib.Path,
        help="Path to JSON file to read (default: read from stdin).",
    )
    parser.add_argument(
        "--output",
        type=pathlib.Path,
        default=DEFAULT_OUTPUT,
        help="Output JSONL file (default: .council/decision-log.jsonl).",
    )
    args = parser.parse_args(argv)

    # Read input
    try:
        if args.file:
            raw = args.file.read_text(encoding="utf-8")
        else:
            raw = sys.stdin.read()
        instance = json.loads(raw)
    except FileNotFoundError as exc:
        print(f"ERROR: File not found: {exc}", file=sys.stderr)
        return 1
    except json.JSONDecodeError as exc:
        print(f"ERROR: Invalid JSON input: {exc}", file=sys.stderr)
        return 1

    # Validate against schema
    try:
        schema = load_schema()
        validate(instance, schema)
    except jsonschema.ValidationError:
        print("INVALID: schema validation failed (details above).", file=sys.stderr)
        return 1
    except Exception as exc:
        print(f"ERROR loading schema: {exc}", file=sys.stderr)
        return 1

    # Append to output file
    try:
        append_line(args.output, instance)
    except OSError as exc:
        print(f"ERROR writing to {args.output}: {exc}", file=sys.stderr)
        return 1

    # Call git add only when writing to the canonical .council/ path
    canonical = str(args.output).replace("\\", "/")
    if ".council/" in canonical:
        git_add(args.output)

    print(f"APPENDED: {args.output}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
