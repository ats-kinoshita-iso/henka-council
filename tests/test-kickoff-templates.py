#!/usr/bin/env python3
"""Regression guard for council-kickoff template drift (issue #20).

Every JSON template embedded in skills/council-kickoff/SKILL.md must validate
against the schema it bootstraps. This prevents the skill from silently drifting
from the schemas it writes — the failure mode where council-kickoff emitted
config.json / council-manifest.json / standard-work.json shapes that failed
their own (additionalProperties: false) schemas.

Run: python tests/test-kickoff-templates.py
Exit 0 = all embedded templates validate; non-zero = drift detected.
"""
import json
import pathlib
import re
import sys

from jsonschema import Draft7Validator

ROOT = pathlib.Path(__file__).resolve().parents[1]
SKILL = ROOT / "skills" / "council-kickoff" / "SKILL.md"
SCHEMAS = ROOT / "schemas"

# Fill-in tokens the skill uses in its templates -> representative valid values.
PLACEHOLDERS = {
    "<plugin version, e.g. 0.1.2>": "0.1.2",
    "<detected or user-provided>": "sample-project",
    "<same as config>": "sample-project",
    "<detected>": "sample-project",
    "<ISO-8601-now>": "2026-01-01T00:00:00Z",
}

# Identify a parsed block by a signature top-level key -> schema file.
SIGNATURES = [
    ("council_version", "council-config.schema.json"),
    ("manifest_version", "council-manifest.schema.json"),
    ("decision_id", "decision-log-entry.schema.json"),
    ("trigger_history", "effective-autonomy.schema.json"),
]

# Templates that must be present AND valid. The first three are the artifacts
# that drifted; the last two were already correct and are pinned here so they
# cannot regress either.
REQUIRED = {
    "council-config.schema.json",
    "council-manifest.schema.json",
    "standard-work.schema.json",
    "decision-log-entry.schema.json",
    "effective-autonomy.schema.json",
}


def schema_for(obj: dict) -> str | None:
    for key, name in SIGNATURES:
        if key in obj:
            return name
    if "procedures" in obj and "updated_at" in obj:
        return "standard-work.schema.json"
    return None


def main() -> int:
    text = SKILL.read_text(encoding="utf-8")
    blocks = re.findall(r"```json\n(.*?)\n```", text, re.DOTALL)

    errors: list[str] = []
    validated: set[str] = set()

    for raw in blocks:
        filled = raw
        for token, value in PLACEHOLDERS.items():
            filled = filled.replace(token, value)
        try:
            obj = json.loads(filled)
        except json.JSONDecodeError:
            continue  # non-council JSON snippet (settings/hook registration) — skip
        if not isinstance(obj, dict):
            continue
        name = schema_for(obj)
        if name is None:
            continue  # not a council-state artifact (e.g. the governance block)
        schema = json.loads((SCHEMAS / name).read_text(encoding="utf-8"))
        errs = sorted(Draft7Validator(schema).iter_errors(obj), key=lambda e: list(e.path))
        if errs:
            errors.append(f"{name}: {errs[0].message}")
            print(f"FAIL: kickoff template invalid against {name}: {errs[0].message}")
        else:
            validated.add(name)
            print(f"PASS: kickoff template validates against {name}")

    for name in sorted(REQUIRED - validated):
        errors.append(f"no valid kickoff template found for {name}")
        print(f"FAIL: no valid kickoff template found for {name}")

    print()
    if errors:
        print(f"{len(errors)} FAILURE(S)")
        return 1
    print("ALL KICKOFF TEMPLATE CHECKS PASSED")
    return 0


if __name__ == "__main__":
    sys.exit(main())
