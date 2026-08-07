"""Self-contained test for scripts/run-verification.py.

Exercises:
  1. --help exits 0
  2. Allowlisted command (git diff HEAD) with --check-only exits 0
  3. Disallowed command (rm -rf /tmp/test) with --check-only exits non-zero
     with a stderr message explaining the rejection
  4. Disallowed pipe-to-shell (echo foo | sh) with --check-only exits non-zero
  5. sleep 5 results in either pre-invocation rejection (sleep not in allowlist)
     OR timeout-driven termination with --timeout 1
  6. Henkaten emission on rejection: the appended record parses against
     schemas/henka-record.schema.json
  7. Rejection Henkaten append anchors .council/ to the invoking cwd, not the
     plugin install directory (NO-OP warning without .council/, append with it)
  8. Executed allowlisted commands inherit the invoking cwd
  9. The test run itself never creates .council/ in the repo root

Exit codes:
    0  — all assertions passed
    1  — one or more assertions failed
"""
from __future__ import annotations

import json
import pathlib
import shutil
import subprocess
import sys
import tempfile

import jsonschema


# ---------------------------------------------------------------------------
# Path constants
# ---------------------------------------------------------------------------
_REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent.parent
_SCRIPT = _REPO_ROOT / "scripts" / "run-verification.py"
_SCHEMA_PATH = _REPO_ROOT / "schemas" / "henka-record.schema.json"


def run(
    args: list[str],
    env_extras: dict[str, str] | None = None,
    cwd: pathlib.Path | None = None,
) -> subprocess.CompletedProcess:
    """Run scripts/run-verification.py with *args*; return CompletedProcess."""
    import os
    env = os.environ.copy()
    if env_extras:
        env.update(env_extras)
    return subprocess.run(
        [sys.executable, str(_SCRIPT)] + args,
        capture_output=True,
        text=True,
        env=env,
        cwd=str(cwd) if cwd is not None else None,
    )


def load_henka_schema() -> dict:
    """Load the henka-record JSON schema."""
    return json.loads(_SCHEMA_PATH.read_text(encoding="utf-8"))


def validate_henka_record(record: dict, schema: dict) -> list[str]:
    """Return list of validation error strings (empty = valid)."""
    validator = jsonschema.Draft7Validator(schema)
    errors = sorted(validator.iter_errors(record), key=lambda e: list(e.path))
    return [
        f"[{e.validator}] at "
        f"{' -> '.join(str(p) for p in e.absolute_path) or '(root)'}: {e.message}"
        for e in errors
    ]


def main() -> int:
    failures: list[str] = []
    schema = load_henka_schema()

    # Snapshot whether .council/ already exists (a real council project, or a
    # dogfooded baseline). Test 7 must fail only if THIS run *creates* it — the
    # mere presence of .council/ is not a test failure.
    council_dir = _REPO_ROOT / ".council"
    council_existed_before = council_dir.exists()

    # ------------------------------------------------------------------
    # Test 1: --help exits 0
    # ------------------------------------------------------------------
    r = run(["--help"])
    if r.returncode != 0:
        failures.append(
            f"Test 1 FAIL: --help exited {r.returncode}; stderr={r.stderr.strip()!r}"
        )
    else:
        print("Test 1 PASS: --help exits 0")

    # ------------------------------------------------------------------
    # Test 2: allowlisted command with --check-only exits 0
    # ------------------------------------------------------------------
    r = run(["--check-only", "git diff HEAD"])
    if r.returncode != 0:
        failures.append(
            f"Test 2 FAIL: allowlisted 'git diff HEAD' with --check-only exited "
            f"{r.returncode}; stderr={r.stderr.strip()!r}"
        )
    else:
        print("Test 2 PASS: 'git diff HEAD' --check-only exits 0")

    # ------------------------------------------------------------------
    # Test 3: disallowed command exits non-zero with stderr message
    # ------------------------------------------------------------------
    r = run(["--check-only", "rm -rf /tmp/test"])
    if r.returncode == 0:
        failures.append(
            "Test 3 FAIL: 'rm -rf /tmp/test' with --check-only should exit non-zero but exited 0"
        )
    elif not (r.stderr.strip() or r.stdout.strip()):
        failures.append(
            "Test 3 FAIL: rejection of 'rm -rf /tmp/test' produced no stderr/stdout message"
        )
    else:
        print(f"Test 3 PASS: 'rm -rf /tmp/test' rejected (exit {r.returncode})")

    # ------------------------------------------------------------------
    # Test 4: pipe-to-shell rejected
    # ------------------------------------------------------------------
    r = run(["--check-only", "echo foo | sh"])
    if r.returncode == 0:
        failures.append(
            "Test 4 FAIL: pipe-to-shell 'echo foo | sh' should be rejected but exited 0"
        )
    else:
        print(f"Test 4 PASS: 'echo foo | sh' rejected (exit {r.returncode})")

    # ------------------------------------------------------------------
    # Test 5: sleep is rejected by allowlist (pre-invocation) OR timed out
    # ------------------------------------------------------------------
    # sleep is not in the allowlist, so --check-only should reject it
    r_check = run(["--check-only", "sleep 5"])
    if r_check.returncode != 0:
        # Pre-invocation rejection: PASS
        print(f"Test 5 PASS: 'sleep 5' rejected by allowlist pre-check (exit {r_check.returncode})")
    else:
        # sleep somehow passed the allowlist check; try execution with short timeout
        r_exec = run(["--timeout", "1", "sleep 5"])
        if r_exec.returncode != 0:
            print(f"Test 5 PASS: 'sleep 5' terminated by timeout (exit {r_exec.returncode})")
        else:
            failures.append(
                "Test 5 FAIL: 'sleep 5' was neither rejected by allowlist nor terminated by timeout"
            )

    # ------------------------------------------------------------------
    # Test 6: Henkaten emission on rejection — record validates against schema
    # ------------------------------------------------------------------
    with tempfile.TemporaryDirectory() as tmpdir:
        henka_file = pathlib.Path(tmpdir) / "henka-register.jsonl"

        # Reject a disallowed command and capture the Henkaten record
        r = run(
            ["--check-only", "--henka-output", str(henka_file), "rm -rf /tmp/henka-test"],
        )
        if r.returncode == 0:
            failures.append(
                "Test 6 FAIL: 'rm -rf /tmp/henka-test' should be rejected but exited 0"
            )
        elif not henka_file.exists():
            failures.append(
                f"Test 6 FAIL: Henkaten record file was not written to {henka_file}"
            )
        else:
            lines = [l.strip() for l in henka_file.read_text(encoding="utf-8").splitlines() if l.strip()]
            if not lines:
                failures.append("Test 6 FAIL: Henkaten record file is empty")
            else:
                try:
                    record = json.loads(lines[-1])
                except json.JSONDecodeError as exc:
                    failures.append(f"Test 6 FAIL: Henkaten record is not valid JSON: {exc}")
                    record = None

                if record is not None:
                    schema_errors = validate_henka_record(record, schema)
                    if schema_errors:
                        for err in schema_errors:
                            failures.append(f"Test 6 FAIL: Henkaten record schema error: {err}")
                    else:
                        print("Test 6 PASS: Henkaten record written and validates against schema")

    # ------------------------------------------------------------------
    # Test 7: rejection Henkaten append anchors .council/ to the invoking
    # cwd, not the plugin install directory (Linux-container portability fix)
    # ------------------------------------------------------------------
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = pathlib.Path(tmpdir)

        # 7a: no .council/ in the invoking cwd → NO-OP warning, no write
        r = run(["--check-only", "rm -rf /tmp/henka-cwd-test"], cwd=tmp)
        if r.returncode == 0:
            failures.append("Test 7a FAIL: rejected command exited 0")
        elif (tmp / ".council").exists():
            failures.append(
                "Test 7a FAIL: .council/ was created in the invoking cwd without opt-in"
            )
        elif "NO-OP" not in r.stderr:
            failures.append(
                "Test 7a FAIL: expected the '.council … NO-OP' warning on stderr; "
                f"got {r.stderr.strip()!r}"
            )
        else:
            print("Test 7a PASS: missing .council/ in invoking cwd -> NO-OP warning")

        # 7b: .council/ present in the invoking cwd → record appended there
        (tmp / ".council").mkdir()
        r = run(["--check-only", "rm -rf /tmp/henka-cwd-test"], cwd=tmp)
        register = tmp / ".council" / "henka-register.jsonl"
        if r.returncode == 0:
            failures.append("Test 7b FAIL: rejected command exited 0")
        elif not register.exists():
            failures.append(
                "Test 7b FAIL: Henkaten record was not appended to .council/ in "
                "the invoking cwd (still anchored to the plugin install dir?)"
            )
        else:
            record = json.loads(
                register.read_text(encoding="utf-8").splitlines()[-1]
            )
            schema_errors = validate_henka_record(record, schema)
            if schema_errors:
                for err in schema_errors:
                    failures.append(f"Test 7b FAIL: Henkaten record schema error: {err}")
            else:
                print(
                    "Test 7b PASS: rejection record lands in "
                    "<cwd>/.council/henka-register.jsonl"
                )

    # ------------------------------------------------------------------
    # Test 8: executed allowlisted commands inherit the invoking cwd
    # ------------------------------------------------------------------
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = pathlib.Path(tmpdir)
        (tmp / "probe.json").write_text('{"anchor": "invoking-cwd"}', encoding="utf-8")
        interp = "python" if shutil.which("python") else "python3"
        r = run([f"{interp} -m json.tool probe.json"], cwd=tmp)
        if r.returncode != 0 or "invoking-cwd" not in r.stdout:
            failures.append(
                "Test 8 FAIL: allowlisted command did not execute in the invoking cwd "
                f"(exit {r.returncode}; stdout={r.stdout.strip()!r}; "
                f"stderr={r.stderr.strip()!r})"
            )
        else:
            print("Test 8 PASS: executed command ran in the invoking cwd")

    # ------------------------------------------------------------------
    # Test 9: verify .council/ was NOT created in the repo root
    # ------------------------------------------------------------------
    if council_dir.exists() and not council_existed_before:
        failures.append(
            f"Test 9 FAIL: .council/ was created at {council_dir} during tests "
            "(sub-tests must isolate writes via temp dirs / --henka-output)"
        )
    else:
        print("Test 9 PASS: .council/ was not created by the test run")

    # ------------------------------------------------------------------
    # Report
    # ------------------------------------------------------------------
    if failures:
        print("\nFAIL:", file=sys.stderr)
        for f in failures:
            print(f"  - {f}", file=sys.stderr)
        return 1

    print("\nALL PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
