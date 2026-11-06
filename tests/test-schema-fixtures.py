#!/usr/bin/env python3
"""Schema fixture runner.

Issue #9 noted that the schema fixtures under tests/schemas/** were never
exercised in CI — their regression value was zero. This runner closes that gap.

For each tests/schemas/<name>/:
  - valid/*.json   MUST validate against schemas/<name>.schema.json
  - invalid/*.json MUST fail validation. If a sibling <name>.violation.md
    declares an "Expected jsonschema error keyword", the failure must include
    at least one error with that validator keyword — so a fixture fails for the
    documented reason, not incidentally. A `false` (boolean) subschema is named
    `false`. When the note also has a "Fails only on this keyword" section, every
    error must carry that keyword: the fixture is otherwise valid.

Run: python tests/test-schema-fixtures.py
"""
import json
import pathlib
import re
import sys

from jsonschema import Draft7Validator

ROOT = pathlib.Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "tests" / "schemas"
SCHEMAS = ROOT / "schemas"

errors: list[str] = []
checked = 0


def fail(msg: str) -> None:
    errors.append(msg)
    print("FAIL: " + msg)


def expected_keyword(json_path: pathlib.Path) -> tuple[str | None, bool]:
    vm = json_path.with_suffix(".violation.md")
    if not vm.exists():
        return None, False
    text = vm.read_text(encoding="utf-8")
    m = re.search(r"Expected jsonschema error keyword\s*\n+\s*`([^`]+)`", text)
    only = re.search(r"Fails only on this keyword\s*\n+\s*yes", text) is not None
    return (m.group(1).strip() if m else None), only


def keyword(error: object) -> str:
    """The validator keyword of an error; a boolean `false` subschema is 'false'."""
    validator = getattr(error, "validator", None)
    return "false" if validator is None else str(validator)


def main() -> int:
    global checked
    for sdir in sorted(p for p in FIXTURES.iterdir() if p.is_dir()):
        schema_path = SCHEMAS / f"{sdir.name}.schema.json"
        if not schema_path.exists():
            fail(f"no schema {schema_path.name} for fixtures dir '{sdir.name}'")
            continue
        validator = Draft7Validator(json.loads(schema_path.read_text(encoding="utf-8")))

        for f in sorted((sdir / "valid").glob("*.json")):
            checked += 1
            errs = list(validator.iter_errors(json.loads(f.read_text(encoding="utf-8"))))
            if errs:
                fail(f"{sdir.name}/valid/{f.name} should VALIDATE but failed: {errs[0].message}")

        for f in sorted((sdir / "invalid").glob("*.json")):
            checked += 1
            errs = list(validator.iter_errors(json.loads(f.read_text(encoding="utf-8"))))
            if not errs:
                fail(f"{sdir.name}/invalid/{f.name} should FAIL but validated clean")
                continue
            kw, only = expected_keyword(f)
            got = sorted({keyword(e) for e in errs})
            if kw and kw not in got:
                fail(f"{sdir.name}/invalid/{f.name} fails on {got}, but .violation.md expects '{kw}'")
            elif kw and only and got != [kw]:
                fail(f"{sdir.name}/invalid/{f.name} fails on {got}, but should fail only on '{kw}'")

    print(f"\nchecked {checked} fixtures across {len(list(FIXTURES.iterdir()))} schema dirs")
    if errors:
        print(f"{len(errors)} FAILURE(S)")
        return 1
    print("ALL SCHEMA FIXTURES CLASSIFY CORRECTLY")
    return 0


if __name__ == "__main__":
    sys.exit(main())
