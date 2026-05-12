"""End-to-end fixture test for scripts/rotate-audit-log.py.

Uses tempfile.TemporaryDirectory for full isolation.
Verifies:
  1. A file above --threshold-bytes triggers rotation: archive exists.
  2. SHA-256 of the archive matches what is recorded in the DEC entry.
  3. After rotation the source file is empty (zero bytes).
  4. DEC entry validates against schemas/decision-log-entry.schema.json.
  5. Running a second time on the already-empty file exits 0 with no new archive.
"""
from __future__ import annotations

import gzip
import hashlib
import json
import pathlib
import subprocess
import sys
import tempfile


SCHEMA_PATH = pathlib.Path("schemas/decision-log-entry.schema.json")
ROTATE_SCRIPT = pathlib.Path("scripts/rotate-audit-log.py")
THRESHOLD = 100  # small value to avoid large temp files


def compute_sha256_file(path: pathlib.Path) -> str:
    """Compute SHA-256 of a file and return hex digest."""
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def build_fake_audit_log(path: pathlib.Path, min_size_bytes: int) -> None:
    """Write enough JSONL lines to exceed min_size_bytes."""
    line = json.dumps({
        "entry_id": "AUD-001",
        "timestamp": "2026-01-01T00:00:00Z",
        "event_type": "tool-call",
        "agent_id": "test-agent",
    }) + "\n"
    content = ""
    while len(content.encode("utf-8")) <= min_size_bytes + 10:
        content += line
    path.write_text(content, encoding="utf-8")


def main() -> int:
    errors: list[str] = []

    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = pathlib.Path(tmpdir)
        audit_log = tmp / "audit-log.jsonl"
        decision_log = tmp / "decision-log.jsonl"

        # Build a fake audit log above the threshold
        build_fake_audit_log(audit_log, THRESHOLD + 10)
        assert audit_log.exists(), "Test setup failed: audit log not created"
        original_size = audit_log.stat().st_size
        print(f"Created fake audit log: {original_size} bytes (threshold: {THRESHOLD})")

        # --- Run the rotation script ---
        result = subprocess.run(
            [
                sys.executable,
                str(ROTATE_SCRIPT),
                "--file", str(audit_log),
                "--threshold-bytes", str(THRESHOLD),
                "--decision-output", str(decision_log),
            ],
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            errors.append(
                f"rotate-audit-log.py exited {result.returncode}:\n"
                f"stdout: {result.stdout}\nstderr: {result.stderr}"
            )

        # 1. Archive exists
        archives = list(tmp.glob("audit-log.*.jsonl.gz"))
        if not archives:
            errors.append("No archive file created in temp dir")
        else:
            print(f"Archive created: {archives[0].name}")
            archive_path = archives[0]

            # 2. SHA-256 matches DEC entry
            if decision_log.exists():
                lines = [
                    ln.strip()
                    for ln in decision_log.read_text(encoding="utf-8").splitlines()
                    if ln.strip()
                ]
                if lines:
                    try:
                        dec_entry = json.loads(lines[-1])
                        desc_raw = dec_entry.get("description", "")
                        if isinstance(desc_raw, str):
                            try:
                                desc = json.loads(desc_raw)
                            except json.JSONDecodeError:
                                desc = {}
                        else:
                            desc = desc_raw

                        recorded_sha256 = desc.get("sha256_archive", "")
                        expected_sha256 = compute_sha256_file(archive_path)

                        if recorded_sha256 == expected_sha256:
                            print(f"SHA-256 matches: {expected_sha256}")
                        else:
                            errors.append(
                                f"SHA-256 mismatch: expected={expected_sha256}, "
                                f"recorded={recorded_sha256}"
                            )
                    except (json.JSONDecodeError, KeyError) as exc:
                        errors.append(f"Failed to parse DEC entry: {exc}")
                else:
                    errors.append("Decision log is empty after rotation")
            else:
                errors.append(f"Decision log not created at {decision_log}")

        # 3. Source file is empty after rotation
        if audit_log.exists():
            current_size = audit_log.stat().st_size
            if current_size == 0:
                print("Source file is empty after rotation")
            else:
                errors.append(
                    f"Source file should be empty after rotation, but has {current_size} bytes"
                )
        else:
            errors.append("Source audit log no longer exists (should be truncated, not deleted)")

        # 4. DEC entry validates against schema
        if decision_log.exists() and SCHEMA_PATH.exists():
            try:
                import jsonschema
                schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
                lines = [
                    ln.strip()
                    for ln in decision_log.read_text(encoding="utf-8").splitlines()
                    if ln.strip()
                ]
                if lines:
                    dec_entry = json.loads(lines[-1])
                    validator = jsonschema.Draft7Validator(schema)
                    schema_errors = list(validator.iter_errors(dec_entry))
                    if schema_errors:
                        for se in schema_errors:
                            errors.append(f"DEC schema error: {se.message}")
                    else:
                        print("DEC entry passes schema validation")
                else:
                    errors.append("Decision log is empty — no DEC entry to validate")
            except ImportError:
                print("jsonschema not installed — skipping schema validation (field check only)")
            except Exception as exc:
                errors.append(f"Schema validation failed with exception: {exc}")
        elif not SCHEMA_PATH.exists():
            print(f"Schema file not found at {SCHEMA_PATH} — skipping schema validation")

        # 5. Idempotency: second run on already-empty file exits 0 with no new archive
        archives_before = list(tmp.glob("audit-log.*.jsonl.gz"))
        result2 = subprocess.run(
            [
                sys.executable,
                str(ROTATE_SCRIPT),
                "--file", str(audit_log),
                "--threshold-bytes", str(THRESHOLD),
                "--decision-output", str(decision_log),
            ],
            capture_output=True,
            text=True,
        )
        if result2.returncode != 0:
            errors.append(
                f"Second (idempotent) run exited {result2.returncode}:\n"
                f"stdout: {result2.stdout}\nstderr: {result2.stderr}"
            )
        else:
            print("Second (idempotent) run exited 0")

        archives_after = list(tmp.glob("audit-log.*.jsonl.gz"))
        if len(archives_after) == len(archives_before):
            print(f"No new archive on idempotent run (archive count: {len(archives_after)})")
        else:
            errors.append(
                f"New archive created on idempotent run: before={len(archives_before)}, "
                f"after={len(archives_after)}"
            )

    # Report
    print("")
    if errors:
        for err in errors:
            print(f"FAIL: {err}")
        return 1

    print("ALL ASSERTIONS PASSED")
    return 0


if __name__ == "__main__":
    sys.exit(main())
