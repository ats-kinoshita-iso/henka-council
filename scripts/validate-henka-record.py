"""Validate a henka-record JSON file against the henka-record.schema.json schema.

Usage:
    python3 scripts/validate-henka-record.py <path-to-json-file>

Exit codes:
    0 — valid
    1 — invalid (schema violation or parse error)
    2 — usage error (wrong number of arguments)
"""
import sys
import json
import pathlib

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


SCHEMA_PATH = pathlib.Path(__file__).parent.parent / "schemas" / "henka-record.schema.json"


def main() -> int:
    if len(sys.argv) != 2:
        print(f"Usage: {sys.argv[0]} <path-to-json-file>", file=sys.stderr)
        return 2

    target_path = pathlib.Path(sys.argv[1])

    try:
        target_doc = json.loads(target_path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        print(f"ERROR: File not found: {target_path}", file=sys.stderr)
        return 1
    except json.JSONDecodeError as exc:
        print(f"ERROR: Invalid JSON in {target_path}: {exc}", file=sys.stderr)
        return 1

    try:
        schema_doc = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    except Exception as exc:
        print(f"ERROR: Could not load schema from {SCHEMA_PATH}: {exc}", file=sys.stderr)
        return 1

    validator = jsonschema.Draft7Validator(schema_doc)
    errors = sorted(validator.iter_errors(target_doc), key=lambda e: list(e.path))

    if errors:
        print(f"INVALID: {target_path}")
        for error in errors:
            path = " -> ".join(str(p) for p in error.absolute_path) if error.absolute_path else "(root)"
            print(f"  [{error.validator}] at {path}: {error.message}", file=sys.stderr)
        return 1

    print(f"VALID: {target_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
