#!/usr/bin/env python3
"""Check .claude-plugin/plugin.json against the rules current Claude Code enforces.

Claude Code 2.1.318 refuses to load a plugin whose manifest breaks these rules,
and then registers none of its hooks, skills or agents; the marketplace install
fails too. `claude plugin validate .` reports the same errors, but CI has no
claude CLI, so the rules are checked here:

- every skills entry starts with "./" and names a directory containing SKILL.md;
- every agents entry starts with "./" and names an existing .md file;
- hooks/hooks.json exists and parses as JSON with a top-level "hooks" object.

Run: python tests/test-plugin-manifest.py
"""
import json
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
MANIFEST = ROOT / ".claude-plugin" / "plugin.json"
HOOKS = ROOT / "hooks" / "hooks.json"

errors: list[str] = []


def check(cond: bool, msg: str) -> None:
    print(("PASS: " if cond else "FAIL: ") + msg)
    if not cond:
        errors.append(msg)


def main() -> int:
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8-sig"))
    for entry in manifest.get("skills", []):
        check(isinstance(entry, str) and entry.startswith("./"), f"skills entry {entry!r} starts with ./")
        path = ROOT / entry
        check(path.is_dir(), f"skills entry {entry!r} is a directory")
        check((path / "SKILL.md").is_file(), f"skills entry {entry!r} contains SKILL.md")
    for entry in manifest.get("agents", []):
        check(isinstance(entry, str) and entry.startswith("./"), f"agents entry {entry!r} starts with ./")
        check(entry.endswith(".md") and (ROOT / entry).is_file(), f"agents entry {entry!r} is an existing .md file")
    try:
        hooks = json.loads(HOOKS.read_text(encoding="utf-8"))
        check(isinstance(hooks.get("hooks"), dict), "hooks/hooks.json has a top-level hooks object")
    except (OSError, json.JSONDecodeError) as exc:
        check(False, f"hooks/hooks.json readable and valid JSON ({exc})")
    print()
    if errors:
        print(f"{len(errors)} MANIFEST CHECK(S) FAILED")
        return 1
    print("PLUGIN MANIFEST VALID")
    return 0


if __name__ == "__main__":
    sys.exit(main())
