#!/usr/bin/env python3
"""Tests for templates/github/direction-check.yml (the Layer A GitHub Action).

1. The template parses as YAML (GitHub rejects a workflow file that does not).
2. Its "Run direction-check" step, run the way `shell: bash` runs it
   (bash -eo pipefail), fails the check only on BLOCK: PASS and WARN exit 0,
   BLOCK exits 1, and a repo with the gate off (or no config) is never blocked.
3. The step reads the sprint contract, so a killed workstream in the contract
   BLOCKs.

Linux/macOS only (needs bash); skipped elsewhere. Needs pyyaml.
Exit 0 = all assertions passed.
"""
from __future__ import annotations

import json
import os
import pathlib
import shutil
import subprocess
import sys
import tempfile

ROOT = pathlib.Path(__file__).resolve().parents[2]
TEMPLATE = ROOT / "templates" / "github" / "direction-check.yml"
SCRIPT = ROOT / "scripts" / "direction-check.py"
failures: list[str] = []


def check(name: str, ok: bool, detail: str = "") -> None:
    print(("PASS: " if ok else "FAIL: ") + name + ("" if ok else f"\n  {detail}"))
    if not ok:
        failures.append(name)


def main() -> int:
    try:
        import yaml  # type: ignore
    except ImportError:
        print("FAIL: pyyaml is not installed")
        return 1
    try:
        wf = yaml.safe_load(TEMPLATE.read_text(encoding="utf-8"))
        check("template parses as YAML", True)
    except yaml.YAMLError as exc:
        check("template parses as YAML", False, str(exc))
        return 1

    bash = shutil.which("bash")
    if os.name == "nt" or bash is None:
        print("SKIP: step execution needs a POSIX bash")
        return 1 if failures else 0

    steps = wf["jobs"]["direction-check"]["steps"]
    step = next(s for s in steps if str(s.get("name", "")).startswith("Run direction-check"))
    check("run step uses shell: bash", step.get("shell") == "bash", repr(step.get("shell")))
    run = step["run"]
    # The step calls `python`; point it at this interpreter.
    run = run.replace('python "$SCRIPT"', f'"{sys.executable}" "$SCRIPT"')

    tmp = pathlib.Path(tempfile.mkdtemp())
    (tmp / "scripts").mkdir()
    shutil.copy(SCRIPT, tmp / "scripts" / "direction-check.py")
    (tmp / ".council" / "charters").mkdir(parents=True)
    (tmp / ".harness" / "contracts").mkdir(parents=True)
    step_file = tmp / "step.sh"
    step_file.write_text(run, encoding="utf-8")
    cfg = tmp / ".council" / "config.json"

    def step_exit(branch: str) -> int:
        env = {**os.environ, "GITHUB_HEAD_REF": branch, "GITHUB_REF_NAME": branch}
        return subprocess.run([bash, "-eo", "pipefail", str(step_file)], cwd=tmp, env=env,
                              capture_output=True, text=True).returncode

    enabled = {"direction_check": {"enabled": True, "anchor_path": "docs/anchor.md",
                                   "killed_workstreams": ["cmpx writer"], "mainline_branch": "main"}}

    cfg.write_text(json.dumps({"direction_check": {"enabled": False}}))
    check("gate off: side branch, no charter -> step passes", step_exit("feat/x") == 0)
    cfg.unlink()
    check("no config: side branch, no charter -> step passes", step_exit("feat/x") == 0)

    cfg.write_text(json.dumps(enabled))
    check("gate on: mainline, no charter (WARN) -> step passes", step_exit("main") == 0)
    check("gate on: side branch, no charter (BLOCK) -> step fails", step_exit("feat/x") == 1)

    (tmp / ".council" / "charters" / "c.json").write_text(json.dumps({
        "charter_id": "WC-0001", "created_at": "2026-11-20T00:00:00Z", "branch": "feat/x",
        "sprint_context": 2, "strategic_anchor": {"path": "docs/anchor.md"},
        "workstream_scope": ["export"], "exploration_mode": "mainline"}))
    contract = tmp / ".harness" / "contracts" / "sprint-02.md"
    contract.write_text("Cites docs/anchor.md.\nAdd the cmpx writer.\n")
    check("gate on: charter + killed workstream in contract -> step fails", step_exit("feat/x") == 1)
    contract.write_text("Cites docs/anchor.md.\nAdd the YAML writer.\n")
    check("gate on: charter + clean contract -> step passes", step_exit("feat/x") == 0)

    shutil.rmtree(tmp, ignore_errors=True)
    if failures:
        print(f"\n{len(failures)} assertion(s) failed.")
        return 1
    print("\nAll direction-check Action assertions passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
