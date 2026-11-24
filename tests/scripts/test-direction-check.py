#!/usr/bin/env python3
"""Replay + tiering tests for scripts/direction-check.py (Layer A).

The headline test REPLAYS the bay-o-net direction-drift episode: the pre-rescope
harness spec said "build a .cmpx writer" while the strategic anchor said "no
writer at any point". Three sprints compounded on that wrong direction before it
was caught manually. This proves the Layer A gate would have BLOCKED it at the
moment work started.

Exit codes (of THIS test runner):
    0  — all assertions passed
    1  — one or more assertions failed

direction-check.py's own exit codes under test:
    0 PASS, 10 WARN, 20 BLOCK
"""
from __future__ import annotations

import pathlib
import subprocess
import sys

_REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]
SCRIPT = _REPO_ROOT / "scripts" / "direction-check.py"
FIX = _REPO_ROOT / "tests" / "fixtures" / "direction-check"

PASS_CODE, WARN_CODE, BLOCK_CODE = 0, 10, 20
failures: list[str] = []


def run(*, charter: str | None, spec: str, contract: str, branch: str | None) -> subprocess.CompletedProcess:
    argv = [
        sys.executable, str(SCRIPT),
        "--config", str(FIX / "config.json"),
        "--spec", str(FIX / spec),
        "--contract", str(FIX / contract),
    ]
    if charter is not None:
        argv += ["--charter", str(FIX / charter)]
    if branch is not None:
        argv += ["--branch", branch]
    return subprocess.run(argv, capture_output=True, text=True)


def check(name: str, got: int, want: int, proc: subprocess.CompletedProcess) -> None:
    if got == want:
        print(f"PASS: {name} (exit {got})")
    else:
        failures.append(name)
        print(f"FAIL: {name}: expected exit {want}, got {got}\n  stdout: {proc.stdout}\n  stderr: {proc.stderr}")


def main() -> int:
    # 1. THE REPLAY: pre-rescope mainline drift -> BLOCK.
    p = run(charter="charter-mainline-pre.json", spec="spec-pre-rescope.md",
            contract="contract-pre-rescope.md", branch="main")
    check("replay/pre-rescope-cmpx-writer-on-mainline -> BLOCK", p.returncode, BLOCK_CODE, p)

    # 2. Post-rescope aligned work -> PASS (no false positive on the sanctioned YAML writer).
    p = run(charter="charter-mainline-post.json", spec="spec-post-rescope.md",
            contract="contract-post-rescope.md", branch="main")
    check("post-rescope-yaml-writer -> PASS (no false positive)", p.returncode, PASS_CODE, p)

    # 3. Same drift, but declared 'competitive' WITH justification -> WARN (legitimate when declared).
    p = run(charter="charter-competitive-justified.json", spec="spec-pre-rescope.md",
            contract="contract-pre-rescope.md", branch="claude/compete-cmpx-fallback")
    check("declared-competitive-with-justification -> WARN", p.returncode, WARN_CODE, p)

    # 4. Declared 'competitive' but NO justification -> BLOCK.
    p = run(charter="charter-competitive-nojust.json", spec="spec-pre-rescope.md",
            contract="contract-pre-rescope.md", branch="claude/compete-cmpx-fallback")
    check("declared-competitive-without-justification -> BLOCK", p.returncode, BLOCK_CODE, p)

    # 5. THE SILENT SIDE-BRANCH: divergent branch with NO charter at all -> BLOCK
    #    (this is the wizardly-johnson case the gate exists to surface).
    p = run(charter=None, spec="spec-pre-rescope.md",
            contract="contract-pre-rescope.md", branch="claude/wizardly-johnson-a95216")
    check("undeclared-divergent-branch-no-charter -> BLOCK", p.returncode, BLOCK_CODE, p)

    # 6. No charter but ON mainline -> WARN (advisory, not a hard block).
    p = run(charter=None, spec="spec-post-rescope.md",
            contract="contract-post-rescope.md", branch="main")
    check("no-charter-on-mainline -> WARN", p.returncode, WARN_CODE, p)

    # 6b. REGRESSION (bay-o-net adoption): a spec that historically MENTIONS the
    #     killed workstream but a CLEAN contract must still PASS — killed-workstream
    #     detection is scoped to the proposed contract, not the spec's narrative.
    p = run(charter="charter-mainline-post.json", spec="spec-historical-mention.md",
            contract="contract-post-rescope.md", branch="main")
    check("spec-historical-mention + clean-contract -> PASS (no false positive)", p.returncode, PASS_CODE, p)

    # 7. The --emit-henka candidate must validate against the henka-record schema
    #    (so it can be piped straight to append-henka.py).
    import json as _json
    import tempfile
    try:
        import jsonschema  # type: ignore
        out = pathlib.Path(tempfile.mkdtemp()) / "henka.json"
        subprocess.run([
            sys.executable, str(SCRIPT),
            "--config", str(FIX / "config.json"),
            "--spec", str(FIX / "spec-pre-rescope.md"),
            "--contract", str(FIX / "contract-pre-rescope.md"),
            "--branch", "main", "--emit-henka", str(out),
        ], capture_output=True, text=True)
        schema = _json.loads((_REPO_ROOT / "schemas" / "henka-record.schema.json").read_text())
        errs = list(jsonschema.Draft7Validator(schema).iter_errors(_json.loads(out.read_text())))
        if errs:
            failures.append("emit-henka-candidate-valid")
            print(f"FAIL: emit-henka candidate invalid: {errs[0].message}")
        else:
            print("PASS: emit-henka candidate validates against henka-record schema")
    except ImportError:
        print("SKIP: jsonschema not installed; emit-henka validity not checked")

    regression_tests()

    if failures:
        print(f"\n{len(failures)} assertion(s) failed.")
        return 1
    print("\nAll direction-check Layer A assertions passed.")
    return 0


def run_argv(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run([sys.executable, str(SCRIPT), *args], capture_output=True, text=True)


def regression_tests() -> None:
    """Cases from the 2026-08-19 review of PR #27."""
    import json as _json
    import tempfile

    tmp = pathlib.Path(tempfile.mkdtemp())
    cfg = _json.loads((FIX / "config.json").read_text())

    # Gate off (or no config at all) -> PASS, even on a divergent branch with
    # no charter: a repo that vendors the script with the gate off is not blocked.
    off = tmp / "config-off.json"
    off.write_text(_json.dumps({"direction_check": {**cfg["direction_check"], "enabled": False}}))
    p = run_argv("--config", str(off), "--branch", "claude/side", "--ci")
    check("gate disabled -> PASS on a divergent branch", p.returncode, PASS_CODE, p)
    p = run_argv("--config", str(tmp / "missing.json"), "--branch", "claude/side", "--ci")
    check("no config file -> PASS on a divergent branch", p.returncode, PASS_CODE, p)

    # No charter: content checks still run. A mainline contract reintroducing a
    # killed workstream BLOCKs instead of stopping at the no-charter WARN.
    p = run(charter=None, spec="spec-pre-rescope.md", contract="contract-pre-rescope.md", branch="main")
    check("no charter + killed workstream in contract on mainline -> BLOCK", p.returncode, BLOCK_CODE, p)

    # The charter's strategic_anchor.locked_decisions count as citations.
    cfg2 = tmp / "config-no-locked.json"
    cfg2.write_text(_json.dumps({"direction_check": {
        "enabled": True, "anchor_path": "docs/other-anchor.md",
        "killed_workstreams": [], "mainline_branch": "main"}}))
    charter = tmp / "charter-locked.json"
    charter.write_text(_json.dumps({
        "charter_id": "WC-0060", "created_at": "2026-11-20T00:00:00Z",
        "strategic_anchor": {"path": "docs/other-anchor.md", "locked_decisions": ["ADR-0042"]},
        "workstream_scope": ["export"], "exploration_mode": "mainline"}))
    contract = tmp / "contract-cites-adr.md"
    contract.write_text("# Sprint\nHonors ADR-0042.\n")
    p = run_argv("--config", str(cfg2), "--charter", str(charter), "--contract", str(contract), "--branch", "main")
    check("charter-level locked_decisions cited -> PASS", p.returncode, PASS_CODE, p)

    # Killed-workstream keywords match whole words only.
    for text, want, label in [
        ("Cites ADR-0008. Build the syncmpx writer.", PASS_CODE, "'syncmpx writer' does not match 'cmpx writer'"),
        ("Cites ADR-0008. Build the cmpx writers module.", BLOCK_CODE, "'cmpx writers' matches 'cmpx writer' (open trailing edge)"),
        ("Cites ADR-0008. Build the `.cmpx` writer.", BLOCK_CODE, "'`.cmpx` writer' matches 'cmpx writer'"),
        ("Cites ADR-0008. Build the cmpx_writer.", BLOCK_CODE, "'cmpx_writer' matches 'cmpx writer'"),
    ]:
        c = tmp / "contract-boundary.md"
        c.write_text(text + "\n")
        p = run_argv("--config", str(FIX / "config.json"), "--charter", str(FIX / "charter-mainline-post.json"),
                     "--contract", str(c), "--branch", "main")
        check(f"word boundary: {label}", p.returncode, want, p)

    # --auto-contract resolves .harness/contracts/sprint-{NN}.md under --root.
    root = tmp / "proj"
    (root / ".harness" / "contracts").mkdir(parents=True)
    (root / ".harness" / "contracts" / "sprint-07.md").write_text(
        (FIX / "contract-pre-rescope.md").read_text())
    (root / ".harness" / "contracts" / "sprint-07.tasks.json").write_text("{}")
    ch = tmp / "charter-s7.json"
    ch.write_text(_json.dumps({**_json.loads((FIX / "charter-mainline-pre.json").read_text()), "sprint_context": 7}))
    p = run_argv("--config", str(FIX / "config.json"), "--charter", str(ch), "--branch", "claude/s7",
                 "--root", str(root), "--auto-contract")
    check("--auto-contract finds sprint-07.md from sprint_context 7 -> BLOCK", p.returncode, BLOCK_CODE, p)
    p = run_argv("--config", str(FIX / "config.json"), "--charter", str(ch), "--branch", "claude/s7",
                 "--root", str(root))
    check("without --auto-contract the contract is not read -> no content BLOCK", p.returncode, PASS_CODE, p)


if __name__ == "__main__":
    sys.exit(main())
