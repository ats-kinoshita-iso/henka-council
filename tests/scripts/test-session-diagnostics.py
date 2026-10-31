#!/usr/bin/env python3
"""Cross-platform test for scripts/session-diagnostics.py and the projection-cost event.

Runs on Linux and Windows CI (python only; the bash/pwsh wrappers have their own
fixture tests). Asserts the ADR-0006 contract for a session event:

- exactly one event per SessionEnd payload;
- token totals equal the transcript's per-request usage, deduplicated by requestId;
- cost and per-model usage come from the transcript's cost-state entry;
- tool calls, failures, subagents, compactions, retries, denials are counted;
- the event validates against schemas/diagnostic-event.schema.json;
- no prompt text leaks into the event;
- nothing is written when <root>/.council does not exist.
"""
import json
import os
import pathlib
import subprocess
import sys
import tempfile

ROOT = pathlib.Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "session-diagnostics.py"
PROJECTION = ROOT / "scripts" / "measure-projection-cost.py"
FIXTURE = ROOT / "tests" / "fixtures" / "transcripts" / "session-fixture.jsonl"
SCHEMA = ROOT / "schemas" / "diagnostic-event.schema.json"

failures: list[str] = []


def check(cond: bool, msg: str) -> None:
    print(("PASS: " if cond else "FAIL: ") + msg)
    if not cond:
        failures.append(msg)


def run_hook(payload: dict, env_extra: dict | None = None) -> subprocess.CompletedProcess:
    env = dict(os.environ)
    env.pop("CLAUDE_PROJECT_DIR", None)
    env.pop("DIAGNOSTICS_LOG_PATH", None)
    env.update(env_extra or {})
    return subprocess.run(
        [sys.executable, str(SCRIPT)],
        input=json.dumps(payload),
        capture_output=True,
        text=True,
        env=env,
        timeout=60,
    )


def make_project(tmp: pathlib.Path, *, council: bool = True) -> pathlib.Path:
    proj = tmp / "proj"
    (proj / ".git").mkdir(parents=True)
    (proj / ".harness").mkdir()
    (proj / ".harness" / "sprint-state.json").write_text(json.dumps({"current_sprint": 9}), encoding="utf-8")
    if council:
        (proj / ".council").mkdir()
    return proj


def main() -> int:
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = pathlib.Path(tmpdir)
        proj = make_project(tmp)
        payload = {
            "session_id": "fixture-session-0001",
            "transcript_path": str(FIXTURE),
            "cwd": str(proj / "sub" / "dir"),
            "hook_event_name": "SessionEnd",
            "reason": "prompt_input_exit",
            "permission_mode": "acceptEdits",
        }
        (proj / "sub" / "dir").mkdir(parents=True)
        completed = run_hook(payload)
        check(completed.returncode == 0, f"hook exits 0 (stderr: {completed.stderr.strip()[:200]})")
        log = proj / ".council" / "diagnostics.jsonl"
        check(log.exists(), "diagnostics.jsonl written under <root>/.council")
        lines = [l for l in log.read_text(encoding="utf-8").splitlines() if l.strip()] if log.exists() else []
        check(len(lines) == 1, f"exactly one event written (got {len(lines)})")
        event = json.loads(lines[0]) if lines else {}

        check(event.get("kind") == "session" and event.get("source") == "claude-code-session", "kind=session, source=claude-code-session")
        check(event.get("session_id") == "fixture-session-0001", "session_id from payload")
        check(event.get("project") == "proj" and event.get("sprint") == 9, "project from root name, sprint from sprint-state.json")
        check(event.get("usage") == {"input_tokens": 16, "output_tokens": 170, "cache_read_input_tokens": 1500, "cache_creation_input_tokens": 200},
              f"usage totals deduplicated by requestId: {event.get('usage')}")
        check(event.get("sidechain_usage") == {"input_tokens": 1, "output_tokens": 20, "cache_read_input_tokens": 0, "cache_creation_input_tokens": 0},
              "sidechain usage split out")
        check(event.get("cost_usd") == 1.23 and event.get("cost_source") == "claude-code-estimate", "cost from cost-state, source labelled")
        check(event.get("usage_by_model", {}).get("claude-opus-5-5", {}).get("output_tokens") == 150, "per-model usage from cost-state modelUsage")
        check(event.get("model") == "claude-opus-5-5" and event.get("effort") == "high", "dominant model and most common effort")
        check(event.get("labels", {}).get("effort_levels") == "high,max", "mixed effort levels recorded as a label")
        counts = event.get("counts", {})
        check(counts.get("tool_calls") == 3 and counts.get("tool_calls_by_tool") == {"Bash": 1, "Read": 1, "Agent": 1}, f"tool calls counted by tool: {counts.get('tool_calls_by_tool')}")
        check(counts.get("tool_failures") == 1 and counts.get("subagents") == 1, "tool failures and subagent launches counted")
        check(counts.get("compactions") == 1 and counts.get("api_retries") == 1 and counts.get("permission_denials") == 1, "compactions, retries, denials counted")
        check(event.get("duration_ms") == 60000 and event.get("api_duration_ms") == 40000 and event.get("thinking_duration_ms") == 2200, "durations from cost-state and thinking time deduplicated")
        check(event.get("num_turns") == 1, "one user prompt counted as a turn")
        check("PROMPT-CANARY-7731" not in lines[0] if lines else False, "no prompt text in the event")
        check(event.get("labels", {}).get("end_reason") == "prompt_input_exit", "end reason label")

        try:
            import jsonschema  # type: ignore
            schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
            errs = list(jsonschema.Draft7Validator(schema).iter_errors(event))
            check(not errs, "event validates against diagnostic-event.schema.json" + (f" ({errs[0].message})" if errs else ""))
        except ImportError:
            print("SKIP: jsonschema not installed")

        # second firing appends a second event (append-only), does not rewrite
        run_hook(payload)
        lines2 = [l for l in log.read_text(encoding="utf-8").splitlines() if l.strip()]
        check(len(lines2) == 2 and lines2[0] == lines[0], "append-only: second firing appends, first line unchanged")

        # no .council -> nothing written, nothing created
        proj2 = make_project(tmp / "two", council=False)
        completed2 = run_hook(dict(payload, cwd=str(proj2)))
        check(completed2.returncode == 0 and not (proj2 / ".council").exists(), "without .council nothing is written and nothing is created")

        # empty / malformed stdin -> exit 0
        env = dict(os.environ)
        env.pop("CLAUDE_PROJECT_DIR", None)
        empty = subprocess.run([sys.executable, str(SCRIPT)], input="", capture_output=True, text=True, env=env, timeout=60)
        check(empty.returncode == 0, "empty payload exits 0")

        # DIAGNOSTICS_LOG_PATH override
        override = tmp / "elsewhere" / "diag.jsonl"
        completed3 = run_hook(payload, {"DIAGNOSTICS_LOG_PATH": str(override)})
        check(completed3.returncode == 0 and override.exists(), "DIAGNOSTICS_LOG_PATH override honoured")

        # projection-cost --emit-event writes one event only when .council exists
        plugin_root = tmp / "plugin"
        (plugin_root / ".council").mkdir(parents=True)
        (plugin_root / ".claude-plugin").mkdir()
        (plugin_root / "CLAUDE.md").write_text("# plugin\n\nsome words here\n", encoding="utf-8")
        (plugin_root / ".claude-plugin" / "plugin.json").write_text(json.dumps({"name": "x", "skills": [], "agents": []}), encoding="utf-8")
        proc = subprocess.run([sys.executable, str(PROJECTION), "--repo-root", str(plugin_root), "--emit-event", "--json"], capture_output=True, text=True, timeout=60)
        plines = (plugin_root / ".council" / "diagnostics.jsonl").read_text(encoding="utf-8").splitlines() if (plugin_root / ".council" / "diagnostics.jsonl").exists() else []
        pevent = json.loads(plines[0]) if plines else {}
        check(proc.returncode == 0 and len(plines) == 1 and pevent.get("kind") == "projection-cost" and pevent.get("labels", {}).get("budget") == "8000",
              f"projection-cost --emit-event appends one event (rc={proc.returncode}, stderr={proc.stderr.strip()[:120]})")
        plugin2 = tmp / "plugin2"
        (plugin2 / ".claude-plugin").mkdir(parents=True)
        (plugin2 / "CLAUDE.md").write_text("# p\n", encoding="utf-8")
        (plugin2 / ".claude-plugin" / "plugin.json").write_text(json.dumps({"name": "y", "skills": [], "agents": []}), encoding="utf-8")
        proc2 = subprocess.run([sys.executable, str(PROJECTION), "--repo-root", str(plugin2), "--emit-event"], capture_output=True, text=True, timeout=60)
        check(proc2.returncode == 0 and not (plugin2 / ".council").exists(), "projection-cost --emit-event creates nothing without .council")

    print()
    if failures:
        print(f"{len(failures)} CHECK(S) FAILED")
        return 1
    print("ALL CHECKS PASSED")
    return 0


if __name__ == "__main__":
    sys.exit(main())
