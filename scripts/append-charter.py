"""Validate a work-charter JSON object and write it to .council/charters/.

Unlike append-henka.py / append-decision.py, a charter is a council-owned
*working* file (mutable, NOT append-only): re-running updates it in place. The
output path is derived from sprint_context (sprint-NN.json) or, failing that,
from the branch name, unless --output is given explicitly.

Usage:
    python scripts/append-charter.py --file <charter.json>
    echo '{...}' | python scripts/append-charter.py --output .council/charters/sprint-12.json

Exit codes:
    0  — validated and written
    1  — validation failure, JSON parse error, or I/O error
    2  — usage error
"""
from __future__ import annotations

import argparse
import json
import pathlib
import re
import subprocess
import sys
from typing import Optional

import jsonschema

SCHEMA_PATH = pathlib.Path(__file__).parent.parent / "schemas" / "work-charter.schema.json"
CHARTERS_DIR = pathlib.Path(".council") / "charters"
_DIVERGENT_MODES = {"parallel-exploration", "competitive"}


def load_schema() -> dict:
    return json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))


def validate(instance: dict, schema: dict) -> None:
    validator = jsonschema.Draft7Validator(schema)
    errors = sorted(validator.iter_errors(instance), key=lambda e: list(e.path))
    if errors:
        for err in errors:
            path = " -> ".join(str(p) for p in err.absolute_path) or "(root)"
            print(f"  [{err.validator}] at {path}: {err.message}", file=sys.stderr)
        raise jsonschema.ValidationError("Schema validation failed.")


def check_divergence_justification(instance: dict) -> None:
    """Cross-field rule the schema alone can't express: non-mainline modes need a justification."""
    mode = instance.get("exploration_mode")
    if mode in _DIVERGENT_MODES:
        just = (instance.get("divergence_justification") or "").strip()
        if len(just) < 20:
            print(
                f"INVALID: exploration_mode '{mode}' requires a divergence_justification "
                f"(>= 20 chars). Declared divergence must record WHY it diverges.",
                file=sys.stderr,
            )
            raise jsonschema.ValidationError("missing divergence_justification")


def _slug(text: str) -> str:
    return re.sub(r"[^A-Za-z0-9._-]+", "-", text).strip("-") or "charter"


def derive_output(instance: dict) -> pathlib.Path:
    if isinstance(instance.get("sprint_context"), int):
        return CHARTERS_DIR / f"sprint-{instance['sprint_context']:02d}.json"
    if instance.get("branch"):
        return CHARTERS_DIR / f"branch-{_slug(str(instance['branch']))}.json"
    cid = instance.get("charter_id", "charter")
    return CHARTERS_DIR / f"{_slug(str(cid))}.json"


def write_charter(output_path: pathlib.Path, instance: dict) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(instance, indent=2) + "\n", encoding="utf-8")


def git_add(path: pathlib.Path) -> None:
    subprocess.run(["git", "add", str(path)], check=False)


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Validate and write a work charter.")
    source = parser.add_mutually_exclusive_group()
    source.add_argument("--file", type=pathlib.Path, help="JSON file to read (default: stdin).")
    parser.add_argument("--output", type=pathlib.Path, help="Explicit output path (default: derived).")
    args = parser.parse_args(argv)

    try:
        raw = args.file.read_text(encoding="utf-8") if args.file else sys.stdin.read()
        instance = json.loads(raw)
    except FileNotFoundError as exc:
        print(f"ERROR: File not found: {exc}", file=sys.stderr)
        return 1
    except json.JSONDecodeError as exc:
        print(f"ERROR: Invalid JSON input: {exc}", file=sys.stderr)
        return 1

    try:
        validate(instance, load_schema())
        check_divergence_justification(instance)
    except jsonschema.ValidationError:
        print("INVALID: charter validation failed (details above).", file=sys.stderr)
        return 1
    except Exception as exc:
        print(f"ERROR loading schema: {exc}", file=sys.stderr)
        return 1

    output_path = args.output or derive_output(instance)
    try:
        write_charter(output_path, instance)
    except OSError as exc:
        print(f"ERROR writing to {output_path}: {exc}", file=sys.stderr)
        return 1

    if ".council/" in str(output_path).replace("\\", "/"):
        git_add(output_path)

    print(f"WROTE: {output_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
