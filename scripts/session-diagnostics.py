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
   one when another process resumed the same session at the same time); activity
   after that cost-state (a lifetime still open) leaves a pending note.
4. Settle notes earlier SessionEnds of this project left, oldest first, while time
   remains.
5. Append: every derived event is first written to the spool in
   ``.council/state/run/``, then the notes it came from are removed, then the events
   are appended under the ledger lock and their spool files removed. Events whose
   append failed (lock held, time up, a write error) stay in the spool, and the next
   SessionEnd of the project appends them first.

Work past the budget (``DIAGNOSTICS_BUDGET_MS``, default 1000) is left as a pending
note. The root is the nearest directory at or above ``CLAUDE_PROJECT_DIR`` (else the
payload cwd) that holds ``.council/``, within the git repo; nothing is written when
there is none (``DIAGNOSTICS_LOG_PATH`` overrides the ledger for tests). Logs go to
stderr, which the wrappers discard; stdout stays empty. Always exits 0.

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
from typing import Any, Callable, Dict, List, Optional, Tuple

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _diaglib as dl  # noqa: E402
import session_lifetimes as sl  # noqa: E402
from _hooklib import crew_guard, governed_root, read_payload, resolve_root  # noqa: E402

Json = Dict[str, Any]


def _budget_s() -> float:
    raw = os.environ.get("DIAGNOSTICS_BUDGET_MS")
    try:
        return max(0.0, float(raw) / 1000.0) if raw else dl.DEFAULT_BUDGET_S
    except ValueError:
        return dl.DEFAULT_BUDGET_S


class Settler:
    """Collects what one hook firing settles, then spools, cleans up and appends once."""

    def __init__(self, ledger: Path, project: str, pid: Optional[str], deadline: float) -> None:
        self.ledger = ledger
        self.project = project
        self.pid = pid
        self.pid_start = dl.process_start(pid)
        self.deadline = deadline
        self.events: List[Json] = []
        self.done: List[Path] = []  # notes whose work is spooled or obsolete
        self.notes: List[Json] = []  # new pending notes

    def derive(self, transcript: Path, selection: sl.Selection, hints: sl.Hints, context: sl.Context) -> sl.Derivation:
        derivation = sl.derive_detail(transcript, selection=selection, hints=hints, deadline=self.deadline)
        self.events.extend(sl.lifetimes_to_events(derivation.lifetimes, context))
        return derivation

    def pending(self, note: Json) -> None:
        self.notes.append(
            dict(
                note,
                kind="pending",
                pid=note.get("pid", self.pid),
                pid_start=note.get("pid_start", self.pid_start),
                created_epoch=note.get("created_epoch") or time.time(),
            )
        )

    def same_process(self, note: Json) -> bool:
        return dl.same_process(note, self.pid, self.pid_start)

    def settle_note(self, path: Path, note: Json) -> bool:
        """Derive a noted lifetime. True when it settled (its events are collected);
        a note whose transcript is gone, that this version cannot read, or that is
        stale and still unsettled is marked done without an event."""
        transcript = Path(str(note.get("transcript_path") or ""))
        if not transcript.is_file():
            self.done.append(path)
            return False
        if note.get("mode") not in ("last_before", "first_after", "holding") or not isinstance(note.get("offset"), int):
            self.done.append(path)
            return False
        if transcript.stat().st_size > dl.MAX_NOTE_TRANSCRIPT_BYTES:
            if dl.note_is_stale(note):
                dl.log(f"{path.name}: transcript too large for the hook; record it with --backfill")
                self.done.append(path)
            return False
        same = self.same_process(note)
        context = dl.context_from(
            self.project,
            note.get("context"),
            recovered="none" if same else "sweep",
            end_reason=note.get("end_reason"),
            cleared_from_session_id=note.get("cleared_from_session_id"),
            **_at_start(note.get("at_start")),
        )
        hints = sl.Hints(bool(note.get("fork")), tuple(str(p) for p in note.get("fork_parent_ids") or ()))
        uuid = note.get("uuid") if isinstance(note.get("uuid"), str) else None
        selection = sl.Selection(str(note.get("mode")), int(note.get("offset") or 0), note.get("prompt_id"), uuid)
        derivation = self.derive(transcript, selection, hints, context)
        if derivation.selected > 0:
            self.done.append(path)
            return True
        if dl.note_is_stale(note):
            dl.log(f"{path.name}: still open after {dl.NOTE_MAX_AGE_S / 86400:.0f} days; left to --backfill")
            self.done.append(path)
        return False

    def flush(self) -> None:
        """Spool the derived events, remove the notes they came from, write the new
        notes, then append under the lock and empty the spool of what is recorded."""
        spooled = dl.read_spool(self.ledger)
        events: Dict[str, Json] = {}
        for _, event in spooled:
            events.setdefault(event["event_id"], event)
        for event in dl.valid_events(self.events):
            events.setdefault(event["event_id"], event)
        spool_ok = True
        try:
            on_disk = {path.name for path, _ in spooled}
            for event in events.values():
                if dl.spool_path(self.ledger, event["event_id"]).name not in on_disk:
                    dl.write_spool(self.ledger, event)
        except OSError as exc:
            spool_ok = False
            dl.log(f"could not spool events: {exc}")
        for note in self.notes:
            try:
                key = note.get("uuid") or int(note["offset"])
                dl.write_note(self.ledger, dl.pending_note_name(str(note["session_id"]), str(note["mode"]), key), note)
            except OSError as exc:
                dl.log(f"could not write a pending note: {exc}")
        if spool_ok:
            for path in self.done:
                dl.delete_note(path)
        if not events:
            return
        try:
            dl.append_events(
                self.ledger, list(events.values()), give_up_at=self.deadline + dl.APPEND_GRACE_S, validated=True
            )
        except (sl.DeadlineExceeded, OSError) as exc:
            reason = "the ledger lock is held by another writer" if isinstance(exc, sl.DeadlineExceeded) else str(exc)
            if spool_ok:
                dl.log(f"{reason}: {len(events)} event(s) kept in .council/state/run/ for the next SessionEnd")
            else:
                dl.log(f"{reason}: {len(events)} event(s) not written; their notes are kept")
            return
        for event_id in events:
            dl.delete_note(dl.spool_path(self.ledger, event_id))
        if not spool_ok:
            for path in self.done:
                dl.delete_note(path)


def _at_start(context: Any) -> Dict[str, Any]:
    if not isinstance(context, dict):
        return {}
    return {
        "sprint_at_start": context.get("sprint"),
        "phase_at_start": context.get("phase"),
        "head_at_start": context.get("head"),
    }


def _ledger(cwd: Optional[str]) -> Optional[Tuple[Path, Path]]:
    """(root, ledger) for a hook payload, or None when no governed root is found."""
    override = os.environ.get("DIAGNOSTICS_LOG_PATH")
    root = governed_root(cwd)
    if override:
        return (root or resolve_root(cwd)), Path(override)
    if root is None:
        return None
    return root, root / ".council" / dl.LEDGER_NAME


def session_end(payload: Json, started: float) -> int:
    found = _ledger(payload.get("cwd") if isinstance(payload.get("cwd"), str) else None)
    if found is None:
        return 0  # council not initialized here: record nothing, create nothing
    root, ledger = found
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
    predecessor = dl.read_note(clear_path) if clear_path is not None else None
    if clear_path is not None and predecessor is not None and predecessor.get("session_id") != session_id:
        if settler.same_process(predecessor):
            opened_by = predecessor  # a pid reused by another process is not our /clear
        found_note: Json = predecessor
        found_path: Path = clear_path
        _guarded("the /clear predecessor", lambda: _settle_or_defer(settler, found_path, found_note))

    # 2. This session's own lifetime.
    if reason == "clear":
        size = transcript.stat().st_size if transcript.is_file() else 0
        clear_note: Json = {
            "kind": "clear",
            "pid": pid,
            "pid_start": settler.pid_start,
            "session_id": session_id,
            "transcript_path": str(transcript),
            "mode": "first_after",
            "offset": size,
            "end_reason": reason,
            "context": observed,
            "cleared_from_session_id": opened_by.get("session_id") if opened_by else None,
            "at_start": opened_by.get("context") if opened_by else None,
            "created_epoch": time.time(),
        }
        name = dl.clear_note_name(pid, session_id)
        if _guarded("the /clear note", lambda: dl.write_note(ledger, name, clear_note)):
            # the predecessor's note had this name: its work is collected, keep the new one
            settler.done = [path for path in settler.done if path.name != name]
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

    # 3. Notes left by earlier SessionEnds of this project, oldest first, while time remains.
    for path in dl.list_notes(ledger):
        if path == clear_path:
            continue
        if time.monotonic() > deadline:
            break
        waiting = dl.read_note(path)
        if waiting is None:
            settler.done.append(path)
            continue
        if path.name.startswith("clear-") and not dl.note_is_orphaned(waiting, pid, settler.pid_start):
            continue  # its own successor settles it, keeping the /clear link
        if not _guarded(path.name, _bind(settler.settle_note, path, waiting)):
            break

    try:
        settler.flush()
    except Exception as exc:  # diagnostics must never block a session
        dl.log(f"flush: {exc}")
    return 0


def _bind(work: Callable[[Path, Json], Any], path: Path, note: Json) -> Callable[[], Any]:
    return lambda: work(path, note)


def _guarded(what: str, work: Callable[[], Any]) -> bool:
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
    """Settle a /clear predecessor now, or turn its note into a pending one."""
    try:
        settled = settler.settle_note(path, note)
    except sl.DeadlineExceeded:
        settled = False
    if not settled and path not in settler.done:
        settler.pending(note)
        settler.done.append(path)


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
    # Lifetimes still open here (a concurrent writer, or a cost-state not written yet):
    # a later SessionEnd settles each once its cost-state exists.
    tails = list(derivation.open_tails)
    if derivation.open_after is not None and not any(offset >= derivation.open_after for _, offset in tails):
        tails.append((None, derivation.open_after))
    for uuid, offset in tails:
        if uuid is not None:
            settler.pending(dict(own, mode="holding", uuid=uuid, offset=offset, prompt_id=None))
        else:
            settler.pending(dict(own, mode="first_after", offset=offset, prompt_id=None))


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
    parser.add_argument(
        "--root", type=Path, help="project root (default: the governed root at or above CLAUDE_PROJECT_DIR or the cwd)"
    )
    parser.add_argument("--log", type=Path, help="ledger to append to (default: <root>/.council/diagnostics.jsonl)")
    parser.add_argument("--projects-root", type=Path, help="Claude Code projects directory, for fork parents")
    parser.add_argument("--print", dest="print_only", action="store_true", help="print events, append nothing")
    args = parser.parse_args(argv)
    root = (args.root or governed_root(os.getcwd()) or resolve_root(os.getcwd())).resolve()
    council = root / ".council"
    ledger = args.log or (council / dl.LEDGER_NAME if council.is_dir() else None)
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
