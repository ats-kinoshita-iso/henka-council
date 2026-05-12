#!/usr/bin/env python3
"""Merge the henka-council governance block into a target project's `.harness/config.json`.

Idempotent helper for council-kickoff Step 8. Preserves all keys the harness owns
(mode, project_type, rubric, components_enabled, regression, batch, transcripts,
trials, thinking, etc.); only writes / updates the `governance` key. Safe to run
multiple times — the second invocation is a no-op when the block already matches.

CLI:
    python scripts/inject-governance.py --file <path-to-.harness/config.json>
        [--council-state-path .council/]
        [--review-frequency every-sprint]
        [--dry-run]

Exit codes:
    0 — governance block written or already present and identical
    1 — file not found / not valid JSON / write failed
    2 — file is valid but the existing `governance.enabled` is `false` (the
        user opted out); script does NOT overwrite, prints a warning, exits 2.
"""
from __future__ import annotations

import argparse
import json
import pathlib
import sys
from typing import Any


def build_block(council_state_path: str, review_frequency: str) -> dict[str, Any]:
    return {
        "enabled": True,
        "plugin": "henkaten-council",
        "council_state_path": council_state_path,
        "review_frequency": review_frequency,
    }


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument(
        "--file",
        required=True,
        help="Path to the target project's .harness/config.json",
    )
    p.add_argument(
        "--council-state-path",
        default=".council/",
        help="council state directory (default: .council/)",
    )
    p.add_argument(
        "--review-frequency",
        default="every-sprint",
        choices=["every-sprint", "every-cycle", "manual"],
        help="how often to surface council reports (default: every-sprint)",
    )
    p.add_argument(
        "--dry-run",
        action="store_true",
        help="print what would change without writing",
    )
    args = p.parse_args()

    config_path = pathlib.Path(args.file)
    desired = build_block(args.council_state_path, args.review_frequency)

    if not config_path.exists():
        # First-time write — create a minimal harness config with just the governance block.
        # The caller (council-kickoff) should have already verified .harness/ exists; if
        # config.json is absent the project was never trine-eval-initialized and the
        # kickoff Step 1a check should have failed before reaching Step 8.
        print(
            f"ERROR: {config_path} does not exist. Run /trine-eval:harness-kickoff first.",
            file=sys.stderr,
        )
        return 1

    try:
        existing = json.loads(config_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as exc:
        print(f"ERROR: failed to read {config_path}: {exc}", file=sys.stderr)
        return 1

    if not isinstance(existing, dict):
        print(
            f"ERROR: {config_path} top-level is not a JSON object (got {type(existing).__name__})",
            file=sys.stderr,
        )
        return 1

    current = existing.get("governance")

    # Opt-out case: respect user's explicit disable.
    if isinstance(current, dict) and current.get("enabled") is False:
        print(
            f"WARNING: {config_path} has governance.enabled=false. Not overwriting. "
            "Set governance.enabled=true manually if you want council reports.",
            file=sys.stderr,
        )
        return 2

    if current == desired:
        print(f"OK: governance block already correct in {config_path} (no change)")
        return 0

    # Merge: replace the governance key, leave everything else alone.
    merged = dict(existing)
    merged["governance"] = desired

    if args.dry_run:
        print(f"DRY RUN: would write the following to {config_path}:")
        print(json.dumps(merged, indent=2))
        return 0

    try:
        config_path.write_text(
            json.dumps(merged, indent=2) + "\n",
            encoding="utf-8",
        )
    except OSError as exc:
        print(f"ERROR: failed to write {config_path}: {exc}", file=sys.stderr)
        return 1

    print(f"OK: wrote governance block to {config_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
