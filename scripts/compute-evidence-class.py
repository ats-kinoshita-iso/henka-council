"""Classify an evidence claim as 'observed', 'inferred', or 'speculative'.

Classification rules (§4, R4, evidence-first.md):
  - 'observed'    : input has a non-empty 'verification' string
  - 'inferred'    : no verification, confidence >= 2 (medium/high on 1-5 scale)
  - 'speculative' : no verification AND confidence <= 1, OR explicit hint

Usage:
    python scripts/compute-evidence-class.py --claim '{"verification": "git log -5", "confidence": 5}'
    echo '{"confidence": 3}' | python scripts/compute-evidence-class.py

Exit codes:
    0  — classification successful (class printed to stdout)
    1  — input parse error
    2  — usage error
"""
from __future__ import annotations

import argparse
import json
import sys
from typing import Optional


def classify(claim: dict) -> str:
    """Return 'observed', 'inferred', or 'speculative' for the given claim dict."""
    verification = claim.get("verification", "")
    confidence = claim.get("confidence", None)
    hint = claim.get("evidence_class_hint", None)

    # 'observed' requires a non-empty verification string
    if isinstance(verification, str) and verification.strip():
        return "observed"

    # No verification: use confidence (integer 1-5) to distinguish inferred vs speculative
    # Treat missing confidence as 0 (speculative)
    if confidence is None:
        conf_int = 0
    else:
        try:
            conf_int = int(confidence)
        except (TypeError, ValueError):
            conf_int = 0

    if conf_int <= 1:
        return "speculative"

    # confidence >= 2 with no verification -> inferred
    # Allow hint to override to speculative if explicitly set
    if hint == "speculative":
        return "speculative"

    return "inferred"


def main(argv: Optional[list[str]] = None) -> int:
    """Entry point; returns integer exit code."""
    parser = argparse.ArgumentParser(
        description="Classify an evidence claim as observed, inferred, or speculative."
    )
    source = parser.add_mutually_exclusive_group()
    source.add_argument(
        "--claim",
        type=str,
        help="JSON string representing the evidence claim.",
    )
    source.add_argument(
        "--file",
        type=str,
        help="Path to JSON file containing the evidence claim.",
    )
    args = parser.parse_args(argv)

    # Read the claim from --claim, --file, or stdin
    try:
        if args.claim is not None:
            raw = args.claim
        elif args.file is not None:
            import pathlib
            raw = pathlib.Path(args.file).read_text(encoding="utf-8")
        else:
            raw = sys.stdin.read()
        claim = json.loads(raw)
    except FileNotFoundError as exc:
        print(f"ERROR: File not found: {exc}", file=sys.stderr)
        return 1
    except json.JSONDecodeError as exc:
        print(f"ERROR: Invalid JSON input: {exc}", file=sys.stderr)
        return 1

    result = classify(claim)
    print(result)
    return 0


if __name__ == "__main__":
    sys.exit(main())
