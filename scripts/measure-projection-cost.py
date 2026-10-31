"""Measure the projection cost of the plugin's always-projected file set.

The "always-projected" set for the henkaten-council plugin is:
  - CLAUDE.md (Claude Code root convention; auto-loaded for any session in
    a directory that contains it)
  - Files listed in .claude-plugin/plugin.json under "skills"
  - Files listed in .claude-plugin/plugin.json under "agents"

These files consume working context every time a council skill runs. Without
governance, the always-projected set can grow unboundedly and crowd out the
working context available for actual loop work. This script measures the
total in tokens (estimated as words * 1.3 unless the file's YAML front-matter
declares a `projection_cost_tokens` integer override) and reports against
a configurable budget.

Usage:
    python scripts/measure-projection-cost.py
    python scripts/measure-projection-cost.py --budget 8000
    python scripts/measure-projection-cost.py --strict
    python scripts/measure-projection-cost.py --json
    python scripts/measure-projection-cost.py --repo-root /path/to/other/plugin

Exit codes:
    0  — measurement completed; total may be over budget unless --strict
    1  — total exceeds budget AND --strict was passed
    2  — usage or I/O error
"""
from __future__ import annotations

import argparse
import json
import pathlib
import re
import sys
from typing import Optional

DEFAULT_REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent
DEFAULT_BUDGET = 8000
WORD_TO_TOKEN_RATIO = 1.3

_FRONTMATTER_RE = re.compile(r"\A---\s*\n(.*?)\n---\s*\n", re.DOTALL)
_COST_OVERRIDE_RE = re.compile(
    r"^\s*projection_cost_tokens\s*:\s*(\d+)\s*$", re.MULTILINE
)


def discover_always_projected_files(repo_root: pathlib.Path) -> list[pathlib.Path]:
    """Return the always-projected files for the plugin rooted at repo_root."""
    files: list[pathlib.Path] = []
    claude_md = repo_root / "CLAUDE.md"
    plugin_manifest = repo_root / ".claude-plugin" / "plugin.json"
    if claude_md.exists():
        files.append(claude_md)
    if plugin_manifest.exists():
        manifest = json.loads(plugin_manifest.read_text(encoding="utf-8-sig"))
        for relpath in manifest.get("skills", []):
            files.append(repo_root / relpath)
        for relpath in manifest.get("agents", []):
            files.append(repo_root / relpath)
    return files


def measure_file(path: pathlib.Path) -> tuple[int, str]:
    """Return (token_count, source) for path. Source is 'override' or 'estimate'."""
    text = path.read_text(encoding="utf-8-sig")
    match = _FRONTMATTER_RE.match(text)
    if match:
        override = _COST_OVERRIDE_RE.search(match.group(1))
        if override:
            return int(override.group(1)), "override"
    word_count = len(text.split())
    return int(round(word_count * WORD_TO_TOKEN_RATIO)), "estimate"


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        description="Measure projection cost of the always-projected file set."
    )
    parser.add_argument(
        "--repo-root",
        type=pathlib.Path,
        default=DEFAULT_REPO_ROOT,
        help="Plugin root to measure (default: this script's parent directory).",
    )
    parser.add_argument(
        "--budget",
        type=int,
        default=DEFAULT_BUDGET,
        help=f"Token budget (default: {DEFAULT_BUDGET}).",
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Exit non-zero if total exceeds budget.",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Emit machine-readable JSON instead of human-readable summary.",
    )
    parser.add_argument(
        "--ci",
        action="store_true",
        help="Emit human-readable summary plus a GitHub Actions ::warning:: "
        "annotation when over budget. Cross-platform; intended for CI.",
    )
    parser.add_argument(
        "--emit-event",
        action="store_true",
        help="Append a kind=projection-cost diagnostic event to "
        "<repo-root>/.council/diagnostics.jsonl when that directory exists "
        "(ADR-0006 in cloud-catcher). Never creates the directory.",
    )
    args = parser.parse_args(argv)

    try:
        files = discover_always_projected_files(args.repo_root)
    except (OSError, json.JSONDecodeError) as exc:
        print(f"ERROR: failed to discover projected files: {exc}", file=sys.stderr)
        return 2

    entries: list[dict] = []
    total = 0
    for path in files:
        try:
            tokens, source = measure_file(path)
        except OSError as exc:
            print(f"ERROR: cannot read {path}: {exc}", file=sys.stderr)
            return 2
        rel = str(path.relative_to(args.repo_root)).replace("\\", "/")
        entries.append({"path": rel, "tokens": tokens, "source": source})
        total += tokens

    over = total > args.budget
    payload = {
        "files": entries,
        "total_tokens": total,
        "budget": args.budget,
        "headroom_tokens": args.budget - total,
        "over_budget": over,
    }

    if args.json:
        print(json.dumps(payload, indent=2))
    else:
        print("Projection cost measurement (henkaten-council always-projected set)")
        print(f"{'File':<55} {'Tokens':>8}  Source")
        print("-" * 75)
        for entry in entries:
            print(f"{entry['path']:<55} {entry['tokens']:>8}  {entry['source']}")
        print("-" * 75)
        print(f"{'TOTAL':<55} {total:>8}")
        print(f"Budget: {args.budget}; headroom: {args.budget - total} tokens")
        if over and not args.ci:
            print(f"WARNING: over budget by {total - args.budget} tokens")

    # Emit the GitHub Actions annotation whenever --ci is set and we are over
    # budget, regardless of --json. Previously this lived only inside the
    # human-readable branch, so `--ci --json` silently dropped the annotation.
    if args.ci and over:
        print(
            f"::warning::Projection cost exceeds budget by "
            f"{total - args.budget} tokens"
        )

    if args.emit_event:
        emit_projection_event(args.repo_root, payload)

    if args.strict and over:
        return 1
    return 0


def emit_projection_event(repo_root: pathlib.Path, payload: dict) -> bool:
    """Append a projection-cost diagnostic event; True when one was written.

    Writes only when <repo_root>/.council already exists, never creates it, and
    never raises: diagnostics must not fail a measurement run.
    """
    council = repo_root / ".council"
    if not council.is_dir():
        return False
    try:
        import uuid
        from datetime import datetime, timezone

        event = {
            "schema_version": "1.0",
            "event_id": str(uuid.uuid4()),
            "ts": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "source": "henkaten-council",
            "kind": "projection-cost",
            "project": repo_root.resolve().name,
            "labels": {
                "projected_tokens": str(payload["total_tokens"]),
                "budget": str(payload["budget"]),
                "over_budget": "true" if payload["over_budget"] else "false",
                "files": str(len(payload["files"])),
            },
            "summary": (
                f"always-projected set: {payload['total_tokens']} tokens "
                f"against a budget of {payload['budget']}"
            ),
        }
        with (council / "diagnostics.jsonl").open("a", encoding="utf-8", newline="\n") as handle:
            handle.write(json.dumps(event, ensure_ascii=False) + "\n")
        return True
    except Exception as exc:  # never fail the measurement because of diagnostics
        print(f"WARNING: could not append projection-cost event: {exc}", file=sys.stderr)
        return False


if __name__ == "__main__":
    sys.exit(main())
