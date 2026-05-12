"""Rotate .council/audit-log.jsonl when it exceeds a size threshold.

Produces a timestamped gzip archive, truncates the current file to empty,
and appends a DEC entry (via scripts/append-decision.py) with the SHA-256
of the archive file.

CLI:
    python scripts/rotate-audit-log.py [--file <path>] [--threshold-bytes <int>]
                                       [--decision-output <path>]

Exit codes:
    0  -- success (rotation performed or not needed)
    1  -- error (archive failed, DEC entry failed, etc.)
"""
from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import pathlib
import subprocess
import sys
from datetime import datetime, timezone


DEFAULT_AUDIT_LOG = pathlib.Path(".council") / "audit-log.jsonl"
DEFAULT_DECISION_LOG = pathlib.Path(".council") / "decision-log.jsonl"
DEFAULT_THRESHOLD = 52428800  # 50 MB


def compute_sha256(path: pathlib.Path) -> str:
    """Return hex SHA-256 digest of the file at path."""
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def next_decision_id(decision_output: pathlib.Path) -> str:
    """Generate a DEC-NNNN id.

    If the decision log exists, counts existing lines to derive the next id.
    Falls back to a timestamp-derived id when the log is absent.
    """
    if decision_output.exists():
        try:
            lines = [
                ln.strip()
                for ln in decision_output.read_text(encoding="utf-8").splitlines()
                if ln.strip()
            ]
            return f"DEC-{(len(lines) + 1):04d}"
        except OSError:
            pass
    # Fallback: use HHMMSS from current UTC time
    seq = int(datetime.now(timezone.utc).strftime("%H%M%S"))
    return f"DEC-{seq:06d}"


def rotate(
    file_path: pathlib.Path,
    decision_output: pathlib.Path,
    threshold_bytes: int,
) -> int:
    """Perform rotation if file_path exceeds threshold_bytes.

    Returns 0 on success or no-op, 1 on error.
    """
    if not file_path.exists():
        print(f"file not found, nothing to rotate: {file_path}", file=sys.stdout)
        return 0

    size = file_path.stat().st_size
    if size < threshold_bytes:
        print(f"no rotation needed: {file_path} ({size} bytes < {threshold_bytes} threshold)")
        return 0

    # Build archive path: same directory, timestamped filename, colons replaced with dashes
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H-%M-%SZ")
    archive_path = file_path.parent / f"{file_path.stem}.{ts}{file_path.suffix}.gz"

    # Read original content
    original_bytes = file_path.read_bytes()
    original_size = len(original_bytes)

    # Write gzip archive
    try:
        with gzip.open(archive_path, "wb") as gz:
            gz.write(original_bytes)
    except OSError as exc:
        print(f"ERROR: failed to write archive {archive_path}: {exc}", file=sys.stderr)
        return 1

    # Compute SHA-256 of the archive file (not the raw bytes)
    sha256_hex = compute_sha256(archive_path)

    # Truncate the current log (write empty bytes)
    try:
        file_path.write_bytes(b"")
    except OSError as exc:
        print(f"ERROR: failed to truncate {file_path}: {exc}", file=sys.stderr)
        return 1

    # Build DEC entry conforming to schemas/decision-log-entry.schema.json
    decision_id = next_decision_id(decision_output)
    timestamp_iso = datetime.now(timezone.utc).isoformat()

    dec_entry = {
        "decision_id": decision_id,
        "timestamp": timestamp_iso,
        "decision_type": "audit-log-rotation",
        "decision_outcome": "applied",
        "autonomy_level_used": 3,
        "effective_autonomy_at_decision": 3,
        "reversibility": "irreversible",
        "description": json.dumps({
            "event": "audit-log-rotation",
            "archive_path": archive_path.as_posix(),
            "original_size_bytes": original_size,
            "sha256_archive": sha256_hex,
        }),
    }

    # Route DEC entry through append-decision.py (inherits schema validation)
    scripts_dir = pathlib.Path(__file__).parent
    append_script = scripts_dir / "append-decision.py"

    result = subprocess.run(
        [sys.executable, str(append_script), "--output", str(decision_output)],
        input=json.dumps(dec_entry),
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        print(f"ERROR: append-decision.py failed:\n{result.stderr}", file=sys.stderr)
        return 1

    print(f"ROTATED: {file_path} -> {archive_path} (sha256={sha256_hex})")
    return 0


def main(argv: list[str] | None = None) -> int:
    """Entry point; returns integer exit code."""
    parser = argparse.ArgumentParser(
        description="Rotate audit-log.jsonl when it exceeds a size threshold."
    )
    parser.add_argument(
        "--file",
        type=pathlib.Path,
        default=DEFAULT_AUDIT_LOG,
        help=f"Path to the audit log file (default: {DEFAULT_AUDIT_LOG}).",
    )
    parser.add_argument(
        "--threshold-bytes",
        type=int,
        default=DEFAULT_THRESHOLD,
        help=f"Rotation threshold in bytes (default: {DEFAULT_THRESHOLD} = 50 MB).",
    )
    parser.add_argument(
        "--decision-output",
        type=pathlib.Path,
        default=DEFAULT_DECISION_LOG,
        help=f"Path to the decision log for the DEC entry (default: {DEFAULT_DECISION_LOG}).",
    )
    args = parser.parse_args(argv)
    return rotate(args.file, args.decision_output, args.threshold_bytes)


if __name__ == "__main__":
    sys.exit(main())
