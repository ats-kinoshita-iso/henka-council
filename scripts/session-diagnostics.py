#!/usr/bin/env python3
"""Session diagnostics: the SessionEnd hook and the backfill command.

One ``kind: session`` event (schema 1.1) per settled process lifetime goes into
``<root>/.council/diagnostics.jsonl`` (cloud-catcher ADR-0006 amendment A1, Stage 1).
Every event comes from one deriver, ``scripts/session_lifetimes.py``; this script
only decides when to call it and what context to attach.

Hook mode (no arguments; the native hook payload on stdin, dispatched on
``hook_event_name``; Stage 1 handles SessionEnd only):

1. With ``AUTOMATE_RUN`` set (an auto-mate crew or gate) write nothing at all.
2. Settle this process's ``/clear`` predecessor, noted under ``CLAUDE_PID`` at its
   own SessionEnd: its closing cost-state is written after that hook returns.
3. ``reason: clear``: leave such a note. Any other reason: settle the lifetime the
   transcript's last cost-state closes (the payload's ``prompt_id`` picks the right
   one when another process resumed the same session at the same time).
4. Settle notes older SessionEnds of this project left pending, while time remains.

Work that would overrun the budget (``DIAGNOSTICS_BUDGET_MS``, default 1000) is left
as a pending note; a later SessionEnd of the same project settles it. Root from
``CLAUDE_PROJECT_DIR`` or the payload cwd; nothing is written unless
``<root>/.council`` exists (``DIAGNOSTICS_LOG_PATH`` overrides the ledger for tests).
Always exits 0.

Backfill mode::

    session-diagnostics.py --backfill <transcript.jsonl>... [--root DIR] [--log FILE]
                           [--projects-root DIR] [--print]

derives every settled lifetime of each transcript (recovered: backfill) and appends
the new ones with the same protocol, or prints them with ``--print``.

Privacy: events never contain prompt or response text, tool inputs or outputs.
Invoked by hooks/session-diagnostics.sh and hooks/win/session-diagnostics.ps1.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _diaglib as dl  # noqa: E402
import session_lifetimes as sl  # noqa: E402
from _hooklib import council_dir, crew_guard, read_payload, resolve_root  # noqa: E402

Json = Dict[str, Any]


def _ledger_for(root: Path, override: Optional[str]) -> Optional[Path]:
    if override:
        return Path(override)
    council = council_dir(root)
    return council / dl.LEDGER_NAME if council is not None else None


def _budget_s() -> float:
    raw = os.environ.get("DIAGNOSTICS_BUDGET_MS")
    try:
        return max(0.0, float(raw) / 1000.0) if raw else dl.DEFAULT_BUDGET_S
    except ValueError:
        return dl.DEFAULT_BUDGET_S


class Settler:
    """Collects the events one hook firing settles and appends them once."""

    def __init__(self, ledger: Path, project: str, pid: Optional[str], deadline: float) -> None:
        self.ledger = ledger
        self.project = project
        self.pid = pid
        self.deadline = deadline
        self.events: List[Json] = []

    def derive(self, transcript: Path, selection: sl.Selection, hints: sl.Hints, context: sl.Context) -> sl.Derivation:
        derivation = sl.derive_detail(transcript, selection=selection, hints=hints, deadline=self.deadline)
        self.events.extend(sl.lifetimes_to_events(derivation.lifetimes, context))
        return derivation

    def pending(self, note: Json) -> None:
        note = dict(note, kind="pending", pid=self.pid, created_epoch=note.get("created_epoch") or time.time())
        name = dl.pending_note_name(str(note["session_id"]), str(note["mode"]), int(note["offset"]))
        dl.write_note(self.ledger, name, note)

    def settle_note(self, path: Path, note: Json) -> bool:
        """Derive a noted lifetime; True when the note is done with."""
        transcript = Path(str(note.get("transcript_path") or ""))
        if not transcript.is_file() or dl.note_is_stale(note):
            return True
        if note.get("mode") not in ("last_before", "first_after") or not isinstance(note.get("offset"), int):
            return True  # not a note this version can read
        same_process = bool(self.pid) and note.get("pid") == self.pid
        context = dl.context_from(
            self.project,
            note.get("context"),
            recovered="none" if same_process else "backfill",
            end_reason=note.get("end_reason"),
            cleared_from_session_id=note.get("cleared_from_session_id"),
            **_at_start(note.get("at_start")),
        )
        hints = sl.Hints(bool(note.get("fork")), tuple(str(p) for p in note.get("fork_parent_ids") or ()))
        selection = sl.Selection(str(note.get("mode")), int(note.get("offset") or 0), note.get("prompt_id"))
        derivation = self.derive(transcript, selection, hints, context)
        return derivation.selected > 0

    def flush(self) -> None:
        if self.events:
            dl.append_events(self.ledger, self.events, give_up_at=self.deadline + dl.APPEND_GRACE_S)


def _at_start(context: Any) -> Dict[str, Any]:
    if not isinstance(context, dict):
        return {}
    return {
        "sprint_at_start": context.get("sprint"),
        "phase_at_start": context.get("phase"),
        "head_at_start": context.get("head"),
    }


def session_end(payload: Json, started: float) -> int:
    root = resolve_root(payload.get("cwd") if isinstance(payload.get("cwd"), str) else None)
    ledger = _ledger_for(root, os.environ.get("DIAGNOSTICS_LOG_PATH"))
    if ledger is None:
        return 0  # council not initialized here: record nothing, create nothing
    session_id = payload.get("session_id")
    transcript_raw = payload.get("transcript_path")
    if not isinstance(session_id, str) or not session_id or not isinstance(transcript_raw, str):
        return 0
    transcript = Path(transcript_raw)
    reason = payload.get("reason") if isinstance(payload.get("reason"), str) else None
    prompt_id = payload.get("prompt_id") if isinstance(payload.get("prompt_id"), str) else None
    pid_raw = os.environ.get("CLAUDE_PID")
    pid = pid_raw if pid_raw and dl.PID_RE.match(pid_raw) else None
    deadline = started + _budget_s()
    observed = dl.observe(root)
    settler = Settler(ledger, root.name, pid, deadline)

    # 1. This process's /clear predecessor: its closing cost-state exists by now.
    clear_path = dl.run_dir(ledger) / dl.clear_note_name(pid, session_id) if pid else None
    opened_by: Optional[Json] = None
    if clear_path is not None:
        note = dl.read_note(clear_path)
        if note is not None and note.get("session_id") != session_id:
            opened_by = note
            _guarded("the /clear predecessor", lambda: _settle_or_defer(settler, clear_path, note))

    # 2. This session's own lifetime.
    at_start = opened_by.get("context") if opened_by else None
    cleared_from = opened_by.get("session_id") if opened_by else None
    if reason == "clear":
        size = transcript.stat().st_size if transcript.is_file() else 0
        note = {
            "kind": "clear",
            "pid": pid,
            "session_id": session_id,
            "transcript_path": str(transcript),
            "mode": "first_after",
            "offset": size,
            "end_reason": reason,
            "context": observed,
            "cleared_from_session_id": cleared_from,
            "at_start": at_start,
            "created_epoch": time.time(),
        }
        _guarded("the /clear note", lambda: dl.write_note(ledger, dl.clear_note_name(pid, session_id), note))
    elif transcript.is_file():
        _guarded(
            "this lifetime",
            lambda: _settle_own(
                settler,
                root=root,
                transcript=transcript,
                session_id=session_id,
                reason=reason,
                prompt_id=prompt_id,
                observed=observed,
                opened_by=opened_by,
            ),
        )

    # 3. Notes left by earlier SessionEnds of this project, while time remains.
    for path in dl.list_notes(ledger):
        if path == clear_path or time.monotonic() > deadline:
            continue
        note = dl.read_note(path)
        if note is None:
            dl.delete_note(path)
            continue
        if path.name.startswith("clear-") and not dl.note_is_orphaned(note, pid):
            continue  # its own successor settles it, keeping the /clear link
        if not _guarded(path.name, lambda path=path, note=note: _settle_or_keep(settler, path, note)):
            break

    try:
        settler.flush()
    except sl.DeadlineExceeded:
        dl.log("ledger locked by another writer; events left to a later SessionEnd or backfill")
    return 0


def _guarded(what: str, work: Any) -> bool:
    """Run one unit of work; a failure is logged and never stops the others.
    Returns False when the deadline passed."""
    try:
        work()
    except sl.DeadlineExceeded:
        return False
    except Exception as exc:  # diagnostics must never block a session
        dl.log(f"{what}: {exc}")
    return True


def _settle_or_defer(settler: Settler, path: Path, note: Json) -> None:
    """Settle a noted lifetime now or turn the note into a pending one."""
    try:
        settled = settler.settle_note(path, note)
    except sl.DeadlineExceeded:
        settled = False
    if not settled:
        settler.pending(note)
    dl.delete_note(path)


def _settle_or_keep(settler: Settler, path: Path, note: Json) -> None:
    if settler.settle_note(path, note):
        dl.delete_note(path)


def _settle_own(
    settler: Settler,
    *,
    root: Path,
    transcript: Path,
    session_id: str,
    reason: Optional[str],
    prompt_id: Optional[str],
    observed: Json,
    opened_by: Optional[Json],
) -> None:
    size = transcript.stat().st_size
    hints = dl.fork_hint(settler.pid) if opened_by is None else sl.Hints()
    at_start = opened_by.get("context") if opened_by else None
    cleared_from = opened_by.get("session_id") if opened_by else None
    own = {
        "session_id": session_id,
        "transcript_path": str(transcript),
        "mode": "last_before",
        "offset": size,
        "prompt_id": prompt_id,
        "end_reason": reason,
        "context": observed,
        "cleared_from_session_id": cleared_from,
        "at_start": at_start,
        "fork": hints.fork,
        "fork_parent_ids": list(hints.fork_parent_ids),
    }
    context = dl.context_from(
        root.name,
        observed,
        recovered="none",
        end_reason=reason,
        cleared_from_session_id=cleared_from,
        **_at_start(at_start),
    )
    try:
        derivation = settler.derive(transcript, sl.Selection("last_before", size, prompt_id), hints, context)
    except sl.DeadlineExceeded:
        settler.pending(own)
        raise
    if derivation.open_after is not None:
        # Activity follows the last cost-state: a lifetime still open here (a
        # concurrent writer, or a cost-state not written yet). A later SessionEnd
        # settles it once its cost-state exists.
        settler.pending(dict(own, mode="first_after", offset=derivation.open_after, prompt_id=None))


def hook_main() -> int:
    started = time.monotonic()
    if crew_guard():
        return 0  # auto-mate crew or gate: write nothing (ADR-0006 A1 D1.9)
    payload = read_payload()
    if payload.get("hook_event_name") == "SessionEnd":
        return session_end(payload, started)
    return 0  # Stage 1 records at SessionEnd only


def backfill_main(argv: List[str]) -> int:
    parser = argparse.ArgumentParser(
        prog="session-diagnostics.py --backfill",
        description="Derive every settled lifetime of the given transcripts (ADR-0006 A1).",
    )
    parser.add_argument("transcripts", nargs="+", type=Path)
    parser.add_argument("--root", type=Path, help="project root (default: CLAUDE_PROJECT_DIR or the cwd's repo)")
    parser.add_argument("--log", type=Path, help="ledger to append to (default: <root>/.council/diagnostics.jsonl)")
    parser.add_argument("--projects-root", type=Path, help="Claude Code projects directory, for fork parents")
    parser.add_argument("--print", dest="print_only", action="store_true", help="print events, append nothing")
    args = parser.parse_args(argv)
    root = (args.root or resolve_root(os.getcwd())).resolve()
    ledger = args.log or _ledger_for(root, None)
    if ledger is None and not args.print_only:
        print(f"session-diagnostics: no .council/ under {root}; pass --root, --log or --print", file=sys.stderr)
        return 2
    context = sl.Context(project=root.name, recovered="backfill")
    events: List[Json] = []
    for transcript in args.transcripts:
        if not transcript.is_file():
            print(f"session-diagnostics: not a file: {transcript}", file=sys.stderr)
            return 2
        lifetimes = sl.derive(transcript, projects_root=args.projects_root)
        events.extend(sl.lifetimes_to_events(lifetimes, context))
    if args.print_only or ledger is None:
        for event in events:
            print(json.dumps(event, ensure_ascii=False))
        return 0
    appended = dl.append_events(ledger, events)
    print(f"session-diagnostics: {len(events)} settled lifetime(s), {len(appended)} new event(s) appended to {ledger}")
    return 0


def main(argv: List[str]) -> int:
    if argv and argv[0] == "--backfill":
        return backfill_main(argv[1:])
    if argv and argv[0] in ("-h", "--help"):
        print(__doc__)
        return 0
    return hook_main()


if __name__ == "__main__":
    if sys.argv[1:2] == ["--backfill"]:
        sys.exit(main(sys.argv[1:]))
    try:
        sys.exit(main(sys.argv[1:]))
    except Exception as exc:  # diagnostics must never block a session
        print(f"session-diagnostics: {exc}", file=sys.stderr)
        sys.exit(0)
