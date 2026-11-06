"""Ledger, notes and context for the session diagnostics hook and its backfill command.

``scripts/session_lifetimes.py`` derives events from files; this module decides
where they go and what the hook adds that is not on disk:

- the append protocol of ``.council/diagnostics.jsonl``: an exclusive lock file,
  each event validated (``jsonschema`` when importable, otherwise structural checks
  read from the same schema), an event_id already in the ledger or in its newest
  rotated archive skipped, one LF-terminated UTF-8 line per event;
- notes under ``.council/state/run/``, a directory that ignores itself in git: a
  ``/clear`` note keyed by ``CLAUDE_PID`` (the old session's closing cost-state is
  written only after its SessionEnd hook returns, so the successor's SessionEnd in
  the same process settles it) and pending notes for work past the time budget;
- the context a hook observes: sprint and phase from ``.harness/sprint-state.json``
  and the commit at ``HEAD``; and a fork hint from the claude process command line.

Stdlib only; Python 3.10. Never calls os.kill.
"""
from __future__ import annotations

import contextlib
import gzip
import hashlib
import importlib
import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, Dict, Iterator, List, Optional, Set

import session_lifetimes as sl
from _hooklib import git_output, harness_context

SCHEMA_PATH = Path(__file__).resolve().parent.parent / "schemas" / "diagnostic-event.schema.json"
LEDGER_NAME = "diagnostics.jsonl"
DEFAULT_BUDGET_S = 1.0
APPEND_GRACE_S = 0.3
LOCK_STALE_S = 30.0
NOTE_MAX_AGE_S = 30 * 86400.0
CLEAR_NOTE_GRACE_S = 86400.0
PID_RE = re.compile(r"^[0-9]{1,10}$")
UUID5_RE = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-5[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$")

Json = Dict[str, Any]


def log(message: str) -> None:
    print(f"session-diagnostics: {message}", file=sys.stderr)


# --------------------------------------------------------------------------------------
# Context a hook observes
# --------------------------------------------------------------------------------------


def observe(root: Path) -> Json:
    """Sprint, phase and HEAD as the hook sees them now."""
    sprint, phase = harness_context(root)
    head = git_output(root, "rev-parse", "HEAD", timeout=1.0)
    return {"sprint": sprint, "phase": phase, "head": head}


def process_args(pid: Optional[str]) -> List[str]:
    """The claude process's command line (Linux /proc, else ps); [] when unknown."""
    if not pid or not PID_RE.match(pid):
        return []
    proc = Path("/proc") / pid / "cmdline"
    try:
        raw = proc.read_bytes()
        return [part.decode("utf-8", "replace") for part in raw.split(b"\0") if part]
    except OSError:
        pass
    if sys.platform == "darwin":
        try:
            completed = subprocess.run(
                ["ps", "-o", "args=", "-p", pid], capture_output=True, text=True, timeout=0.5, check=False
            )
        except (OSError, subprocess.SubprocessError):
            return []
        return completed.stdout.split() if completed.returncode == 0 else []
    return []


def fork_hint(pid: Optional[str]) -> sl.Hints:
    """Hints.fork when the process was started with --fork-session, with the
    --resume argument as the parent to look at first."""
    args = process_args(pid)
    if "--fork-session" not in args:
        return sl.Hints()
    parents: List[str] = []
    for position, arg in enumerate(args):
        if arg in ("--resume", "-r") and position + 1 < len(args):
            parents.append(args[position + 1])
        elif arg.startswith("--resume="):
            parents.append(arg.split("=", 1)[1])
    return sl.Hints(fork=True, fork_parent_ids=tuple(p for p in parents if sl.SESSION_ID_RE.match(p)))


def context_from(project: str, observed: Optional[Json], **extra: Any) -> sl.Context:
    observed = observed or {}
    return sl.Context(
        project=project,
        sprint=observed.get("sprint"),
        phase=observed.get("phase"),
        head=observed.get("head"),
        observed=bool(observed),
        **extra,
    )


# --------------------------------------------------------------------------------------
# Ledger
# --------------------------------------------------------------------------------------


def newest_archive(ledger: Path) -> Optional[Path]:
    """The newest rotated archive (scripts/rotate-audit-log.py names them
    <stem>.<UTC timestamp><suffix>.gz, which sort by time)."""
    archives = sorted(ledger.parent.glob(f"{ledger.stem}.*{ledger.suffix}.gz"))
    return archives[-1] if archives else None


def _jsonl_lines(path: Path) -> Iterator[bytes]:
    if path.suffix == ".gz":
        with gzip.open(path, "rb") as handle:
            yield from handle
    else:
        with path.open("rb") as handle:
            yield from handle


def known_event_ids(ledger: Path) -> Set[str]:
    """event_ids already recorded in the ledger or its newest rotated archive."""
    ids: Set[str] = set()
    for path in (ledger, newest_archive(ledger)):
        if path is None or not path.is_file():
            continue
        try:
            for line in _jsonl_lines(path):
                try:
                    entry = json.loads(line)
                except ValueError:
                    continue
                if isinstance(entry, dict) and isinstance(entry.get("event_id"), str):
                    ids.add(entry["event_id"])
        except (OSError, EOFError) as exc:
            log(f"could not read {path.name}: {exc}")
    return ids


class LedgerLock:
    """An exclusive lock file (O_CREAT|O_EXCL works on every platform)."""

    def __init__(self, path: Path, give_up_at: Optional[float]) -> None:
        self.path = path
        self.give_up_at = give_up_at

    def __enter__(self) -> "LedgerLock":
        while True:
            try:
                handle = os.open(str(self.path), os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o644)
            except FileExistsError:
                try:
                    if time.time() - self.path.stat().st_mtime > LOCK_STALE_S:
                        self.path.unlink()
                        continue
                except FileNotFoundError:
                    continue
                if self.give_up_at is not None and time.monotonic() > self.give_up_at:
                    raise sl.DeadlineExceeded() from None
                time.sleep(0.02)
                continue
            try:
                os.write(handle, str(os.getpid()).encode("ascii"))
            finally:
                os.close(handle)
            return self

    def __exit__(self, *_: object) -> None:
        with contextlib.suppress(FileNotFoundError):
            self.path.unlink()


def append_events(ledger: Path, events: List[Json], give_up_at: Optional[float] = None) -> List[str]:
    """Append the events whose event_id is new; returns the appended ids."""
    if not events:
        return []
    notes = ensure_run_dir(ledger)
    with LedgerLock(notes / "diagnostics.lock", give_up_at):
        known = known_event_ids(ledger)
        lines: List[str] = []
        appended: List[str] = []
        for event in events:
            event_id = event.get("event_id")
            if not isinstance(event_id, str) or event_id in known:
                continue
            problem = validate_event(event)
            if problem:
                log(f"event {event_id} rejected by the schema, not written: {problem}")
                continue
            known.add(event_id)
            appended.append(event_id)
            lines.append(json.dumps(event, ensure_ascii=False) + "\n")
        if lines:
            prefix = b""
            if ledger.is_file() and ledger.stat().st_size > 0:
                with ledger.open("rb") as handle:
                    handle.seek(-1, os.SEEK_END)
                    if handle.read(1) != b"\n":
                        prefix = b"\n"
            with ledger.open("ab") as handle:
                handle.write(prefix + "".join(lines).encode("utf-8"))
    return appended


# --------------------------------------------------------------------------------------
# Notes in .council/state/run/
# --------------------------------------------------------------------------------------


def run_dir(ledger: Path) -> Path:
    return ledger.parent / "state" / "run"


def ensure_run_dir(ledger: Path) -> Path:
    """.council/state/run/, created on first use with a .gitignore that ignores the
    whole directory (itself included): the archivist reads .council/state, so only
    this subdirectory may be ignored."""
    path = run_dir(ledger)
    path.mkdir(parents=True, exist_ok=True)
    ignore = path / ".gitignore"
    if not ignore.exists():
        ignore.write_text("# local, per-machine state of the session diagnostics hook\n*\n", encoding="utf-8")
    return path


def write_note(ledger: Path, name: str, note: Json) -> None:
    folder = ensure_run_dir(ledger)
    temporary = folder / f".{name}.{os.getpid()}.tmp"
    temporary.write_text(json.dumps(note, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")
    os.replace(temporary, folder / name)


def read_note(path: Path) -> Optional[Json]:
    try:
        note = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return note if isinstance(note, dict) else None


def delete_note(path: Path) -> None:
    with contextlib.suppress(FileNotFoundError):
        path.unlink()


def list_notes(ledger: Path) -> List[Path]:
    folder = run_dir(ledger)
    if not folder.is_dir():
        return []
    return sorted(p for p in folder.glob("*.json") if p.name.startswith(("clear-", "pending-")))


def clear_note_name(pid: Optional[str], session_id: str) -> str:
    key = pid if pid and PID_RE.match(pid) else "nopid-" + hashlib.sha1(session_id.encode("utf-8")).hexdigest()[:12]
    return f"clear-{key}.json"


def pending_note_name(session_id: str, mode: str, offset: int) -> str:
    digest = hashlib.sha1(f"{session_id}|{mode}|{offset}".encode("utf-8")).hexdigest()[:16]
    return f"pending-{digest}.json"


def note_is_stale(note: Json) -> bool:
    created = note.get("created_epoch")
    return isinstance(created, (int, float)) and time.time() - float(created) > NOTE_MAX_AGE_S


def note_is_orphaned(note: Json, pid: Optional[str]) -> bool:
    """A /clear note another process may settle: its successor never ran a SessionEnd
    within CLEAR_NOTE_GRACE_S (or the note carries no process id at all)."""
    if note.get("pid") and note.get("pid") == pid:
        return False
    if not note.get("pid"):
        return True
    created = note.get("created_epoch")
    return isinstance(created, (int, float)) and time.time() - float(created) > CLEAR_NOTE_GRACE_S


# --------------------------------------------------------------------------------------
# Validation
# --------------------------------------------------------------------------------------

_SCHEMA_CACHE: Dict[str, Json] = {}


def load_schema() -> Json:
    if "schema" not in _SCHEMA_CACHE:
        _SCHEMA_CACHE["schema"] = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    return _SCHEMA_CACHE["schema"]


def validate_event(event: Json, prefer_jsonschema: Optional[bool] = None) -> Optional[str]:
    """None when the event conforms, else the first problem.

    Uses jsonschema's Draft-7 validator when it is importable (and not disabled with
    DIAGNOSTICS_NO_JSONSCHEMA=1), else structural_problem() over the same schema.
    """
    schema = load_schema()
    if prefer_jsonschema is None:
        prefer_jsonschema = not os.environ.get("DIAGNOSTICS_NO_JSONSCHEMA")
    if prefer_jsonschema:
        try:
            jsonschema = importlib.import_module("jsonschema")
        except ImportError:
            jsonschema = None
        if jsonschema is not None:
            errors = sorted(jsonschema.Draft7Validator(schema).iter_errors(event), key=lambda e: list(e.path))
            return str(errors[0].message) if errors else None
    return structural_problem(event, schema)


def _is_int(value: Any, minimum: int = 0) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and value >= minimum


def _is_num(value: Any, minimum: float = 0.0) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and value >= minimum


def _usage_problem(name: str, usage: Any, definition: Json) -> Optional[str]:
    if not isinstance(usage, dict):
        return f"{name} is not an object"
    allowed = set(definition["properties"])
    for key in definition.get("required", []):
        if key not in usage:
            return f"{name}.{key} is required"
    for key, value in usage.items():
        if key not in allowed:
            return f"{name}.{key} is not allowed"
        if key == "cost_usd":
            if not _is_num(value):
                return f"{name}.cost_usd is not a number >= 0"
        elif not _is_int(value):
            return f"{name}.{key} is not an integer >= 0"
    return None


def structural_problem(event: Json, schema: Optional[Json] = None) -> Optional[str]:
    """The checks a SessionEnd hook can make without jsonschema: every key the schema
    allows, every key it requires, the types of the measures and A1's session rules.
    Property names come from the schema file itself, so the two cannot drift."""
    schema = schema or load_schema()
    props = schema["properties"]
    definitions = schema["definitions"]
    if not isinstance(event, dict):
        return "event is not an object"
    for key in event:
        if key not in props:
            return f"{key} is not allowed"
    for key in schema["required"]:
        if key not in event:
            return f"{key} is required"
    for key in ("schema_version", "source", "kind"):
        if event.get(key) not in props[key]["enum"]:
            return f"{key} {event.get(key)!r} is not allowed"
    if not isinstance(event.get("event_id"), str) or sl.parse_ts(event.get("ts")) is None:
        return "event_id or ts malformed"
    labels = event.get("labels", {})
    if not isinstance(labels, dict) or any(not isinstance(v, str) or len(v) > 80 for v in labels.values()):
        return "labels must be strings of at most 80 characters"
    if event.get("kind") != "session":
        if "lifetime" in event:
            return "lifetime is for kind=session only"
        return None
    if event.get("schema_version") != "1.1":
        return "a session event must be schema 1.1"
    if not UUID5_RE.match(event["event_id"]):
        return "event_id is not a UUIDv5"
    for key in ("session_id", "lifetime", "usage", "cost_usd", "outcome"):
        if key not in event:
            return f"{key} is required for a session event"
    if not isinstance(event.get("session_id"), str) or not event["session_id"]:
        return "session_id is empty"
    for key in ("usage", "sidechain_usage"):
        if key in event:
            problem = _usage_problem(key, event[key], definitions["usage"])
            if problem:
                return problem
    for key, definition in (("usage_by_model", "usage"), ("cost_state_usage_by_model", "cost_state_usage")):
        if key in event:
            if not isinstance(event[key], dict):
                return f"{key} is not an object"
            for model, usage in event[key].items():
                problem = _usage_problem(f"{key}.{model}", usage, definitions[definition])
                if problem:
                    return problem
    counts = event.get("counts", {})
    if not isinstance(counts, dict):
        return "counts is not an object"
    for key, value in counts.items():
        if key not in props["counts"]["properties"]:
            return f"counts.{key} is not allowed"
        if isinstance(value, dict):
            if not all(isinstance(k, str) and _is_int(v) for k, v in value.items()):
                return f"counts.{key} must map names to integers >= 0"
        elif not _is_int(value):
            return f"counts.{key} is not an integer >= 0"
    for key in ("duration_ms", "api_duration_ms", "thinking_duration_ms", "num_turns"):
        if event.get(key) is not None and not _is_int(event[key]):
            return f"{key} is not an integer >= 0"
    lifetime = event["lifetime"]
    lifetime_def = definitions["lifetime"]
    if not isinstance(lifetime, dict):
        return "lifetime is not an object"
    for key in lifetime:
        if key not in lifetime_def["properties"]:
            return f"lifetime.{key} is not allowed"
    for key in lifetime_def["required"]:
        if key not in lifetime:
            return f"lifetime.{key} is required"
    if not re.match(lifetime_def["properties"]["spec"]["pattern"], str(lifetime["spec"])):
        return "lifetime.spec malformed"
    if not re.match(lifetime_def["properties"]["anchor"]["pattern"], str(lifetime["anchor"])):
        return "lifetime.anchor malformed"
    for key in ("start_source", "recovered"):
        if lifetime[key] not in lifetime_def["properties"][key]["enum"]:
            return f"lifetime.{key} {lifetime[key]!r} is not allowed"
    coverage = lifetime["coverage"]
    coverage_def = definitions["coverage"]
    if not isinstance(coverage, dict):
        return "lifetime.coverage is not an object"
    for key in coverage:
        if key not in coverage_def["properties"]:
            return f"lifetime.coverage.{key} is not allowed"
    for key in coverage_def["required"]:
        if key not in coverage:
            return f"lifetime.coverage.{key} is required"
    if coverage["fork_parent"] not in coverage_def["properties"]["fork_parent"]["enum"]:
        return "lifetime.coverage.fork_parent is not allowed"
    if coverage["context"] not in coverage_def["properties"]["context"]["enum"]:
        return "lifetime.coverage.context is not allowed"
    if not isinstance(coverage["shortfall"], list) or any(
        not isinstance(item, str) or len(item) > 120 for item in coverage["shortfall"]
    ):
        return "lifetime.coverage.shortfall malformed"
    for key in ("subagent_files", "subagent_launches_without_file", "copied_entries_excluded"):
        if not _is_int(coverage[key]):
            return f"lifetime.coverage.{key} is not an integer >= 0"
    cost = event.get("cost_usd")
    if cost is not None and not _is_num(cost):
        return "cost_usd is not a number >= 0"
    if event["outcome"] == "interrupted":
        if cost is not None or not str(lifetime["anchor"]).startswith("open:") or lifetime["end_reason"] != "none":
            return "an interrupted lifetime has no cost, an open: anchor and end_reason none"
        if lifetime["cum_cost_end_usd"] is not None or lifetime["recovered"] == "none":
            return "an interrupted lifetime has no closing anchor and is always recovered"
    elif event["outcome"] == "ended":
        if not str(lifetime["anchor"]).startswith("cs:") or lifetime["end_reason"] == "none":
            return "a settled lifetime has a cs: anchor"
        if not isinstance(lifetime["cost_lineage"], str) or not _is_num(lifetime["cum_cost_end_usd"]):
            return "a settled lifetime carries its cost lineage and closing cost"
        if (lifetime["cum_cost_start_usd"] is None) != (cost is None):
            return "cost_usd is null exactly when the restored base is unknown"
    else:
        return "outcome must be ended or interrupted"
    if cost is None:
        if event.get("cost_source") is not None or "cost_state_usage_by_model" in event:
            return "a null cost has no cost source and no cost-state figures"
        if event.get("duration_ms") is not None or event.get("api_duration_ms") is not None:
            return "a null cost has null durations"
    elif event.get("cost_source") != "claude-code-estimate":
        return "a session cost is a claude-code-estimate"
    return None
