"""Persist a plan-mode artifact into the council audit trail.

Reads the plan body from --plan-body (file path) or stdin, computes its
SHA-256, snapshots governance state, validates the frontmatter against
schemas/plan-handoff.schema.json, and writes a frontmatter-stamped file
to the route's canonical location under .council/proposed/.

Pre-creates .council/proposed/ when absent (bootstrap case) so the
chicken-and-egg with council-kickoff resolves cleanly; the council-kickoff
skill's mkdir -p semantics swallow the pre-created directory on subsequent
invocation.

Usage:
    python3 scripts/persist-plan.py --route bootstrap --plan-body plan.md
    python3 scripts/persist-plan.py --route pre-sprint --sprint 3 \\
        --plan-body plan.md
    python3 scripts/persist-plan.py --route course-correction --sprint 5 \\
        --plan-body plan.md
    cat plan.md | python3 scripts/persist-plan.py --route bootstrap

Output:
    Prints the canonical path of the written file to stdout on success.

Exit codes:
    0 — written successfully, or already present with identical body sha256
    1 — I/O error, schema validation failure, or unreadable plan body
    2 — usage error (missing --sprint for non-bootstrap, etc.)
"""
from __future__ import annotations

import argparse
import datetime
import hashlib
import json
import pathlib
import subprocess
import sys
from typing import Optional

try:
    import jsonschema
except ModuleNotFoundError:
    print(
        "ERROR: the 'jsonschema' package is required but not installed.\n"
        "  Install it with: python3 -m pip install -r requirements.txt\n"
        "  (run from the plugin root; on Windows substitute 'python' for 'python3')",
        file=sys.stderr,
    )
    sys.exit(1)


SCHEMA_PATH = (
    pathlib.Path(__file__).parent.parent / "schemas" / "plan-handoff.schema.json"
)
COUNCIL_DIR = pathlib.Path(".council")
PROPOSED_DIR = COUNCIL_DIR / "proposed"
STATE_FILE = COUNCIL_DIR / "state" / "effective-autonomy.json"
HENKA_REGISTER = COUNCIL_DIR / "henka-register.jsonl"

DEFAULT_AUTONOMY = 4  # matches orchestrator.md Level 4 default


def now_iso() -> str:
    """Return the current UTC time as an ISO 8601 string ending in 'Z'."""
    return (
        datetime.datetime.now(datetime.timezone.utc)
        .isoformat(timespec="seconds")
        .replace("+00:00", "Z")
    )


def sha256_hex(body: str) -> str:
    """Return the SHA-256 hex digest of the body's UTF-8 bytes."""
    return hashlib.sha256(body.encode("utf-8")).hexdigest()


def capture_governance_state() -> dict[str, int]:
    """Snapshot the autonomy floor and open-henka count.

    Returns defaults (autonomy=4, count=0) when .council/ is absent
    (bootstrap case). Read failures are non-fatal; the function falls back
    to the defaults rather than failing the persist step.
    """
    autonomy = DEFAULT_AUTONOMY
    if STATE_FILE.exists():
        try:
            data = json.loads(STATE_FILE.read_text(encoding="utf-8"))
            level = data.get("level")
            if isinstance(level, int) and 0 <= level <= 5:
                autonomy = level
        except (json.JSONDecodeError, OSError):
            pass

    open_count = 0
    if HENKA_REGISTER.exists():
        try:
            with HENKA_REGISTER.open("r", encoding="utf-8") as fh:
                for line in fh:
                    if line.strip():
                        open_count += 1
        except OSError:
            pass

    return {"effective_autonomy": autonomy, "open_henka_count": open_count}


def route_to_path(route: str, sprint: Optional[int]) -> pathlib.Path:
    """Return the canonical persisted path for the given route."""
    if route == "bootstrap":
        return PROPOSED_DIR / "from-plan-bootstrap.md"
    if route == "pre-sprint":
        if sprint is None:
            raise ValueError("pre-sprint route requires a sprint number")
        return PROPOSED_DIR / f"sprint-{sprint:02d}-contract-seed.md"
    if route == "course-correction":
        if sprint is None:
            raise ValueError("course-correction route requires a sprint number")
        ts = datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        return PROPOSED_DIR / f"position-paper-sprint-{sprint:02d}-{ts}.md"
    raise ValueError(f"unknown route: {route}")


def build_frontmatter(
    route: str,
    sprint: Optional[int],
    plan_sha: str,
    session_id: Optional[str],
    state: dict[str, int],
) -> dict[str, object]:
    """Compose the frontmatter dict (validated separately)."""
    fm: dict[str, object] = {
        "intent": route,
        "generated_at": now_iso(),
        "plan_sha256": plan_sha,
        "governance_state_at_capture": state,
    }
    if sprint is not None:
        fm["sprint_target"] = sprint
    if session_id is not None:
        fm["plan_mode_session_id"] = session_id
    return fm


def normalize_body(body: str) -> str:
    """Canonicalise the plan body to a single trailing newline.

    The sha256 is computed on the normalised form so that an external auditor
    who reads the persisted file, strips the frontmatter fence, and re-hashes
    the remaining bytes will get the same digest stored in `plan_sha256`.
    """
    return body if body.endswith("\n") else body + "\n"


def serialize(frontmatter: dict[str, object], body: str) -> str:
    """Compose the file content: --- + JSON frontmatter + --- + body.

    Frontmatter is emitted as pretty-printed JSON inside the YAML-style '---'
    fences. JSON is a valid YAML subset, so any YAML parser will accept it,
    and we avoid taking on a YAML dependency for downstream readers. `body`
    must already be normalised (see `normalize_body`).
    """
    fm_json = json.dumps(frontmatter, indent=2)
    return f"---\n{fm_json}\n---\n\n{body}"


def validate_frontmatter(fm: dict[str, object]) -> None:
    """Validate the frontmatter against plan-handoff.schema.json."""
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    jsonschema.Draft7Validator(schema).validate(fm)


def git_add(path: pathlib.Path) -> None:
    """Stage path with git add; silently ignore git errors."""
    subprocess.run(["git", "add", str(path)], check=False)


def main(argv: Optional[list[str]] = None) -> int:
    """Entry point; returns integer exit code."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--route",
        required=True,
        choices=["bootstrap", "pre-sprint", "course-correction"],
        help="Which lifecycle entry point the plan targets.",
    )
    parser.add_argument(
        "--sprint",
        type=int,
        default=None,
        help="Sprint number (required for pre-sprint and course-correction).",
    )
    parser.add_argument(
        "--plan-body",
        type=pathlib.Path,
        default=None,
        help="Path to the plan body file. If omitted, read from stdin.",
    )
    parser.add_argument(
        "--session-id",
        type=str,
        default=None,
        help="Claude Code session id at plan-approval time (optional).",
    )
    parser.add_argument(
        "--print-path-only",
        action="store_true",
        help="Print the canonical path without writing or reading the body.",
    )
    args = parser.parse_args(argv)

    if args.route in ("pre-sprint", "course-correction") and args.sprint is None:
        print(
            f"ERROR: --sprint is required when --route is {args.route}",
            file=sys.stderr,
        )
        return 2

    if args.print_path_only:
        try:
            print(route_to_path(args.route, args.sprint))
        except ValueError as exc:
            print(f"ERROR: {exc}", file=sys.stderr)
            return 2
        return 0

    try:
        if args.plan_body:
            body = args.plan_body.read_text(encoding="utf-8")
        else:
            body = sys.stdin.read()
    except (FileNotFoundError, OSError) as exc:
        print(f"ERROR: failed to read plan body: {exc}", file=sys.stderr)
        return 1

    if not body.strip():
        print("ERROR: plan body is empty", file=sys.stderr)
        return 1

    body = normalize_body(body)

    try:
        target = route_to_path(args.route, args.sprint)
    except ValueError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2

    state = capture_governance_state()
    plan_sha = sha256_hex(body)
    frontmatter = build_frontmatter(
        args.route, args.sprint, plan_sha, args.session_id, state
    )

    try:
        validate_frontmatter(frontmatter)
    except jsonschema.ValidationError as exc:
        path = " -> ".join(str(p) for p in exc.absolute_path) or "(root)"
        print(
            f"ERROR: frontmatter failed schema validation at {path}: {exc.message}",
            file=sys.stderr,
        )
        return 1
    except (json.JSONDecodeError, OSError) as exc:
        print(f"ERROR: could not load schema {SCHEMA_PATH}: {exc}", file=sys.stderr)
        return 1

    try:
        target.parent.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        print(f"ERROR: could not create {target.parent}: {exc}", file=sys.stderr)
        return 1

    if target.exists():
        try:
            existing = target.read_text(encoding="utf-8")
            if f'"plan_sha256": "{plan_sha}"' in existing:
                print(
                    f"OK: identical plan already at {target} (sha256 match) — no write"
                )
                return 0
        except OSError:
            pass

    content = serialize(frontmatter, body)

    try:
        target.write_text(content, encoding="utf-8")
    except OSError as exc:
        print(f"ERROR: failed to write {target}: {exc}", file=sys.stderr)
        return 1

    if ".council/" in str(target).replace("\\", "/"):
        git_add(target)

    print(str(target))
    return 0


if __name__ == "__main__":
    sys.exit(main())
