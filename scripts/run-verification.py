"""Enforce the §7.0.2 verification syntax allowlist and optionally execute the command.

Usage:
    python scripts/run-verification.py [--check-only] [--timeout N]
                                       [--henka-output <path>] <verification_string>

Exit codes:
    0  — command is allowlisted (and, in execution mode, completed successfully)
    1  — command rejected by allowlist, timed out, or other error
    <N> — subprocess exit code when command executes and exits non-zero
"""
from __future__ import annotations

import argparse
import json
import os
import pathlib
import re
import shlex
import subprocess
import sys
from datetime import datetime, timezone

# ---------------------------------------------------------------------------
# Repository layout helpers
# ---------------------------------------------------------------------------

# Project root is two levels above this script (scripts/ → repo root)
_REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent

# Default council register path (may not exist)
_DEFAULT_COUNCIL_DIR = _REPO_ROOT / ".council"
_DEFAULT_HENKA_REGISTER = _DEFAULT_COUNCIL_DIR / "henka-register.jsonl"

# ---------------------------------------------------------------------------
# §7.0.2 Allowlist definition
# ---------------------------------------------------------------------------
# Each entry is either:
#   - A tuple ("git", "diff") meaning first two tokens must match exactly
#   - A string "cat" meaning first token matches
#   - A special marker for multi-token commands
#
# We represent as a list of prefix tuples (already tokenised).

_ALLOWLIST_PREFIXES: list[tuple[str, ...]] = [
    # Read-only git inspection
    ("git", "diff"),
    ("git", "show"),
    ("git", "log"),
    ("git", "status"),
    ("git", "branch"),
    ("git", "ls-files"),
    # Read-only file search
    ("grep",),
    ("rg",),
    # Read-only file reading
    ("cat",),
    ("head",),
    ("tail",),
    # JSON inspection (jq, no -i flag)
    ("jq",),
    # JSON pretty-print / validate
    ("python", "-m", "json.tool"),
    # Schema validators from sprint 1 (python scripts/validate-*.py)
    # Handled specially below via _is_python_validate()
    # POSIX test expressions
    ("test",),
    ("[",),
    # Node one-line expressions
    ("node", "-e"),
]

# Explicitly disallowed tokens/patterns (checked before allowlist prefix match
# when a string could theoretically match a prefix after tokenisation games)
_DISALLOWED_TOKENS: frozenset[str] = frozenset([
    "rm", "mv", "cp", "dd", "truncate", "mkdir", "touch",
    "curl", "wget", "ssh", "scp", "rsync",
    "eval", "exec", "source",
    "sleep",
    "tee",
    "chmod", "chown",
    "kill", "killall",
    "sudo", "su",
    "pip", "npm", "yarn", "bun",
    "git-push", "git-commit", "git-add", "git-reset", "git-rebase", "git-merge",
])

# Pipe-to-shell patterns
_PIPE_TO_SHELL_RE = re.compile(r"\|\s*(sh|bash|zsh|fish|dash|cmd|powershell)\b", re.IGNORECASE)

# Shell redirect patterns
_REDIRECT_RE = re.compile(r"(?<![<>])>|>>|2>|&>")

# Subshell / backtick patterns
_SUBSHELL_RE = re.compile(r"`[^`]+`|\$\([^)]+\)")


def _is_python_validate(tokens: list[str]) -> bool:
    """Return True if the command is `python scripts/validate-*.py ...`."""
    if len(tokens) < 2:
        return False
    if tokens[0] not in ("python", "python3"):
        return False
    script_arg = tokens[1]
    # Must be scripts/validate-*.py (basename check too)
    name = pathlib.Path(script_arg).name
    return name.startswith("validate-") and name.endswith(".py") and "validate-" in script_arg


def _jq_has_inplace(tokens: list[str]) -> bool:
    """Return True if the jq command uses the -i (in-place) flag."""
    return "-i" in tokens[1:]


def check_allowlist(command_string: str) -> tuple[bool, str]:
    """
    Check whether *command_string* is on the §7.0.2 allowlist.

    Returns:
        (allowed: bool, reason: str)
        reason is empty string when allowed.
    """
    s = command_string.strip()
    if not s:
        return False, "Empty command string."

    # ---- Structural checks ------------------------------------------------
    # 1. Pipe-to-shell
    if _PIPE_TO_SHELL_RE.search(s):
        return False, f"Rejected: pipe-to-shell pattern detected in: {s!r}"

    # 2. Shell redirects (>, >>)
    if _REDIRECT_RE.search(s):
        return False, f"Rejected: shell redirect operator detected in: {s!r}"

    # 3. Subshell / backtick
    if _SUBSHELL_RE.search(s):
        return False, f"Rejected: subshell/backtick pattern detected in: {s!r}"

    # ---- Tokenise to check prefix ----------------------------------------
    try:
        tokens = shlex.split(s)
    except ValueError as exc:
        return False, f"Rejected: could not parse command string ({exc}): {s!r}"

    if not tokens:
        return False, "Rejected: empty token list after parsing."

    first = tokens[0]

    # ---- Explicit disallow list -------------------------------------------
    # Check first token against disallowed set
    if first in _DISALLOWED_TOKENS:
        return False, f"Rejected: command {first!r} is not in the §7.0.2 allowlist: {s!r}"

    # For git sub-commands that are disallowed
    if first == "git" and len(tokens) >= 2:
        git_sub = tokens[1].lower()
        disallowed_git_subs = {
            "push", "commit", "add", "reset", "rebase", "merge",
            "rm", "mv", "checkout", "switch", "restore", "clean",
            "config", "stash", "tag", "fetch", "pull", "clone",
            "init", "remote", "submodule",
        }
        if git_sub in disallowed_git_subs:
            return False, (
                f"Rejected: git sub-command {git_sub!r} is not in the §7.0.2 allowlist: {s!r}"
            )

    # For python commands, check for python scripts/validate-*.py specially
    if first in ("python", "python3"):
        if _is_python_validate(tokens):
            return True, ""
        # Check for python -m json.tool
        if len(tokens) >= 3 and tokens[1] == "-m" and tokens[2] == "json.tool":
            return True, ""
        # Any other python invocation is rejected
        return False, (
            f"Rejected: python command {s!r} does not match any allowlisted form "
            f"(allowed: 'python -m json.tool', 'python scripts/validate-*.py')"
        )

    # jq: allowed but not with -i
    if first == "jq":
        if _jq_has_inplace(tokens):
            return False, f"Rejected: jq with -i (in-place) flag is not allowed: {s!r}"
        return True, ""

    # ---- Prefix matching against allowlist --------------------------------
    for prefix in _ALLOWLIST_PREFIXES:
        n = len(prefix)
        if tuple(tokens[:n]) == prefix:
            return True, ""

    return False, f"Rejected: command prefix {tokens[:2]!r} is not in the §7.0.2 allowlist: {s!r}"


# ---------------------------------------------------------------------------
# Henkaten logging on rejection
# ---------------------------------------------------------------------------

def _build_henka_record(command_string: str) -> dict:
    """Build an agent-capability-change Henkaten record for a rejected command."""
    now = datetime.now(timezone.utc)
    ts = now.strftime("%Y%m%d%H%M%S")
    henka_id = f"HK-{ts}"
    # Ensure at least 4 digits after HK-
    if len(ts) < 4:
        henka_id = f"HK-{ts:>04}"
    detected_at = now.isoformat()

    # Build a safe verification command to re-check this rejection
    safe_cmd = f"python scripts/run-verification.py --check-only {shlex.quote(command_string)}"

    return {
        "henka_id": henka_id,
        "sprint_context": 6,
        "fourM_axis": "Method",
        "category": "agent-capability-change",
        "change_origin": "passive",
        "impact_level": "actionable",
        "description": (
            f"Verification string rejected by §7.0.2 allowlist: {command_string!r}"
        ),
        "affected_artifacts": [".council/henka-register.jsonl"],
        "response_type": "log-only",
        "evidence": [
            {
                "claim": (
                    f"Command string {command_string!r} did not match any "
                    "§7.0.2 allowlisted prefix and was rejected before execution."
                ),
                "evidence_class": "observed",
                "confidence": "high",
                "verification": safe_cmd,
            }
        ],
        "status": "classified",
        "detected_at": detected_at,
        "detected_by_agent": "run-verification",
    }


def _log_rejection(command_string: str, henka_output: pathlib.Path | None) -> None:
    """
    Log an agent-capability-change Henkaten record for a rejected command.

    If henka_output is provided, write directly to that path (test isolation).
    Otherwise try to call scripts/append-henka.py with the default .council/ output.
    If .council/ doesn't exist and no override path is given, emit a warning only.
    """
    record = _build_henka_record(command_string)

    # Always print a structured JSON block to stderr so the caller can see it
    print(
        json.dumps({"event_type": "agent-capability-change", "record": record}, indent=2),
        file=sys.stderr,
    )

    append_script = _REPO_ROOT / "scripts" / "append-henka.py"

    if henka_output is not None:
        # Test-isolation path: write directly via append-henka.py --output
        if append_script.exists():
            try:
                record_json = json.dumps(record)
                subprocess.run(
                    [sys.executable, str(append_script), "--output", str(henka_output)],
                    input=record_json,
                    text=True,
                    capture_output=True,
                    timeout=10,
                    check=False,
                )
            except Exception as exc:  # noqa: BLE001
                print(f"WARNING: failed to call append-henka.py: {exc}", file=sys.stderr)
        else:
            # Fallback: write the JSONL line directly
            henka_output.parent.mkdir(parents=True, exist_ok=True)
            with henka_output.open("a", encoding="utf-8") as fh:
                fh.write(json.dumps(record) + "\n")
        return

    # Production path: require .council/ to exist
    if not _DEFAULT_COUNCIL_DIR.exists():
        print(
            "WARNING: .council/ directory does not exist in this repository; "
            "Henkaten append is a NO-OP.",
            file=sys.stderr,
        )
        return

    if not append_script.exists():
        print(
            f"WARNING: {append_script} not found; cannot append Henkaten record.",
            file=sys.stderr,
        )
        return

    try:
        record_json = json.dumps(record)
        subprocess.run(
            [sys.executable, str(append_script)],
            input=record_json,
            text=True,
            capture_output=True,
            timeout=10,
            check=False,
        )
    except Exception as exc:  # noqa: BLE001
        print(f"WARNING: failed to call append-henka.py: {exc}", file=sys.stderr)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Enforce the §7.0.2 verification syntax allowlist and optionally "
            "execute the verification command."
        ),
    )
    parser.add_argument(
        "verification_string",
        help="The verification command string to check and/or execute.",
    )
    parser.add_argument(
        "--check-only",
        action="store_true",
        default=False,
        help=(
            "Validate against the allowlist; exit 0 if allowed, non-zero if rejected. "
            "Do NOT execute the command."
        ),
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=10,
        metavar="N",
        help="Override the default 10-second execution timeout (seconds). Default: 10.",
    )
    parser.add_argument(
        "--henka-output",
        type=pathlib.Path,
        default=None,
        metavar="PATH",
        help=(
            "Path to write Henkaten rejection records (for test isolation). "
            "If not set, uses .council/henka-register.jsonl (NO-OP if .council/ absent)."
        ),
    )

    args = parser.parse_args(argv)

    # Allow HENKA_OUTPUT_PATH env var as an alternative to --henka-output
    henka_output: pathlib.Path | None = args.henka_output
    if henka_output is None and os.environ.get("HENKA_OUTPUT_PATH"):
        henka_output = pathlib.Path(os.environ["HENKA_OUTPUT_PATH"])

    command_string = args.verification_string

    # ---- Allowlist check --------------------------------------------------
    allowed, reason = check_allowlist(command_string)

    if not allowed:
        print(reason, file=sys.stderr)
        _log_rejection(command_string, henka_output)
        return 1

    if args.check_only:
        # Allowlist passed; do not execute
        return 0

    # ---- Execute ----------------------------------------------------------
    try:
        result = subprocess.run(
            command_string,
            shell=True,
            capture_output=True,
            text=True,
            cwd=str(_REPO_ROOT),
            timeout=args.timeout,
        )
    except subprocess.TimeoutExpired:
        print(
            f"ERROR: command timed out after {args.timeout}s: {command_string!r}",
            file=sys.stderr,
        )
        return 1

    # Forward subprocess output
    if result.stdout:
        sys.stdout.write(result.stdout)
    if result.stderr:
        sys.stderr.write(result.stderr)

    return result.returncode


if __name__ == "__main__":
    sys.exit(main())
