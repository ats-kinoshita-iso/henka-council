#!/usr/bin/env python3
"""Regression guard: nemawashi `pattern_type` must be consumed by Stage 4 routing.

The position-paper template documents a `pattern_type` enum that declares which
standard-work[] array a ratification updates. This test pins that producer to
its consumer — the Stage 4 "Post-Ratify Actions" routing in council-autorun —
so the values can never again be documented-but-unrouted (the issue #9 /
ADR-0005 gap: pattern_type was set by producers but never read by the skill).

Run: python tests/test-stage4-routing.py
"""
import json
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
AUTORUN = ROOT / "skills" / "council-autorun" / "SKILL.md"
PAPER = ROOT / "templates" / "nemawashi-position-paper.md"
SW_SCHEMA = ROOT / "schemas" / "standard-work.schema.json"

# Canonical pattern_type -> standard-work array mapping. Routing must name each
# target array, and each array must exist in the schema.
PATTERN_TO_ARRAY = {
    "procedure": "procedures",
    "failure-pattern": "failure_patterns",
    "evaluation-improvement": "evaluation_improvements",
    "workflow-note": "workflow_notes",
    "loop-shape": "loop_shapes",
}

errors: list[str] = []


def check(cond: bool, msg: str) -> None:
    print(("PASS: " if cond else "FAIL: ") + msg)
    if not cond:
        errors.append(msg)


def stage4_region(text: str) -> str:
    start = text.find("Stage 4 — Ratify")
    if start == -1:
        return ""
    rest = text[start:]
    end = rest.find("\n## ")  # next top-level step heading bounds the section
    return rest[:end] if end != -1 else rest


def main() -> int:
    paper = PAPER.read_text(encoding="utf-8")
    autorun = AUTORUN.read_text(encoding="utf-8")
    schema = json.loads(SW_SCHEMA.read_text(encoding="utf-8"))
    arrays = set(schema.get("properties", {}))

    # 1. Extract the documented pattern_type enum from the position-paper template.
    m = re.search(r"pattern_type:\s*([a-z0-9 \-|]+?)\s*(?:#|$)", paper, re.MULTILINE)
    check(m is not None, "nemawashi-position-paper.md declares a pattern_type enum")
    enum = [v.strip() for v in m.group(1).split("|") if v.strip()] if m else []

    # 2. Stage 4 must exist and actually read pattern_type (the original gap was zero mentions).
    region = stage4_region(autorun)
    check(bool(region), "council-autorun has a Stage 4 — Ratify section")
    check("pattern_type" in region, "Stage 4 routing reads pattern_type")

    # 3. Every documented enum value is handled in Stage 4 AND maps to a real schema array.
    for value in enum:
        check(value in region, f"Stage 4 routing handles pattern_type '{value}'")
        array = PATTERN_TO_ARRAY.get(value)
        check(array is not None, f"pattern_type '{value}' has a canonical array mapping")
        if array:
            check(array in arrays, f"standard-work schema defines '{array}'")
            check(array in region, f"Stage 4 routing names the '{array}' array")

    print()
    if errors:
        print(f"{len(errors)} FAILURE(S)")
        return 1
    print("ALL STAGE-4 ROUTING CHECKS PASSED")
    return 0


if __name__ == "__main__":
    sys.exit(main())
