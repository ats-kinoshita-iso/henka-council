"""Self-contained test for scripts/measure-projection-cost.py.

Exercises:
  1. --help exits 0
  2. Default invocation (against this repo) exits 0 and reports total_tokens > 0
  3. --json output contains the expected fields with correct types
  4. --strict --budget 0 against a non-empty repo exits 1
  5. Front-matter projection_cost_tokens override is honored over word-count
     estimation (uses a self-contained fixture)
  6. --repo-root pointing at a fixture with known files produces a predictable
     non-zero total
  7. Over budget WITHOUT --strict still exits 0 (over_budget: true)
  8. --ci emits a ::warning:: annotation when over budget
  9. --ci --json still emits the ::warning:: annotation (not dropped in JSON mode)
 10. Entry paths are normalized to forward slashes (no backslash)
 11. A UTF-8 BOM in plugin.json / CLAUDE.md is tolerated (no crash)

Exit codes:
    0  — all assertions passed
    1  — one or more assertions failed
"""
from __future__ import annotations

import json
import pathlib
import subprocess
import sys
import tempfile

_REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent.parent
_SCRIPT = _REPO_ROOT / "scripts" / "measure-projection-cost.py"


def run(args: list[str]) -> subprocess.CompletedProcess:
    """Run scripts/measure-projection-cost.py with *args*; return CompletedProcess."""
    return subprocess.run(
        [sys.executable, str(_SCRIPT)] + args,
        capture_output=True,
        text=True,
    )


def _pass(n: int, total: int, msg: str) -> None:
    print(f"[{n}/{total}] PASS: {msg}")


def _fail(n: int, total: int, msg: str) -> None:
    print(f"[{n}/{total}] FAIL: {msg}")


def _make_fixture_repo(
    tmpdir: pathlib.Path,
    claude_md_text: str,
    skill_text: str,
    agent_text: str,
) -> None:
    """Build a minimal plugin-shaped fixture inside tmpdir."""
    (tmpdir / ".claude-plugin").mkdir()
    (tmpdir / ".claude-plugin" / "plugin.json").write_text(
        json.dumps(
            {
                "name": "fixture",
                "skills": ["skills/test/SKILL.md"],
                "agents": ["agents/test.md"],
            }
        ),
        encoding="utf-8",
    )
    (tmpdir / "CLAUDE.md").write_text(claude_md_text, encoding="utf-8")
    (tmpdir / "skills" / "test").mkdir(parents=True)
    (tmpdir / "skills" / "test" / "SKILL.md").write_text(skill_text, encoding="utf-8")
    (tmpdir / "agents").mkdir()
    (tmpdir / "agents" / "test.md").write_text(agent_text, encoding="utf-8")


def main() -> int:
    total = 11
    failures: list[str] = []

    # -----------------------------------------------------------------------
    # Assertion 1: --help exits 0
    # -----------------------------------------------------------------------
    n = 1
    r = run(["--help"])
    if r.returncode == 0:
        _pass(n, total, "--help exits 0")
    else:
        msg = f"--help exited {r.returncode}; stderr={r.stderr.strip()!r}"
        _fail(n, total, msg)
        failures.append(msg)

    # -----------------------------------------------------------------------
    # Assertion 2: default invocation against this repo reports total_tokens > 0
    # -----------------------------------------------------------------------
    n = 2
    r = run(["--json"])
    if r.returncode != 0:
        msg = f"default invocation exited {r.returncode}; stderr={r.stderr.strip()!r}"
        _fail(n, total, msg)
        failures.append(msg)
    else:
        try:
            data = json.loads(r.stdout)
            if data.get("total_tokens", 0) > 0:
                _pass(
                    n,
                    total,
                    f"default invocation reports total_tokens={data['total_tokens']}",
                )
            else:
                msg = f"total_tokens not > 0: {data!r}"
                _fail(n, total, msg)
                failures.append(msg)
        except json.JSONDecodeError as exc:
            msg = f"--json output not parseable: {exc}; stdout={r.stdout[:200]!r}"
            _fail(n, total, msg)
            failures.append(msg)

    # -----------------------------------------------------------------------
    # Assertion 3: --json output schema (fields + types)
    # -----------------------------------------------------------------------
    n = 3
    r = run(["--json"])
    try:
        data = json.loads(r.stdout)
        required = {
            "files": list,
            "total_tokens": int,
            "budget": int,
            "headroom_tokens": int,
            "over_budget": bool,
        }
        wrong: list[str] = []
        for key, typ in required.items():
            if key not in data:
                wrong.append(f"missing key {key!r}")
            elif not isinstance(data[key], typ):
                wrong.append(f"key {key!r} is {type(data[key]).__name__}, expected {typ.__name__}")
        if data.get("files"):
            for entry in data["files"]:
                for sub_key, sub_typ in (("path", str), ("tokens", int), ("source", str)):
                    if sub_key not in entry or not isinstance(entry[sub_key], sub_typ):
                        wrong.append(f"file entry missing or wrong-typed {sub_key!r}")
                        break
        if wrong:
            msg = "JSON schema problems: " + "; ".join(wrong)
            _fail(n, total, msg)
            failures.append(msg)
        else:
            _pass(n, total, "JSON output has expected fields with correct types")
    except json.JSONDecodeError as exc:
        msg = f"--json output not parseable: {exc}"
        _fail(n, total, msg)
        failures.append(msg)

    # -----------------------------------------------------------------------
    # Assertion 4: --strict --budget 0 exits 1 against this non-empty repo
    # -----------------------------------------------------------------------
    n = 4
    r = run(["--strict", "--budget", "0"])
    if r.returncode == 1:
        _pass(n, total, "--strict --budget 0 exits 1")
    else:
        msg = (
            f"--strict --budget 0 exited {r.returncode} (expected 1); "
            f"stderr={r.stderr.strip()!r}"
        )
        _fail(n, total, msg)
        failures.append(msg)

    # -----------------------------------------------------------------------
    # Assertion 5: front-matter projection_cost_tokens override is honored
    # -----------------------------------------------------------------------
    n = 5
    with tempfile.TemporaryDirectory() as td:
        tmpdir = pathlib.Path(td)
        skill_with_override = (
            "---\n"
            "name: test-skill\n"
            "projection_cost_tokens: 99999\n"
            "---\n"
            "Body of the skill: just a few words.\n"
        )
        _make_fixture_repo(
            tmpdir,
            claude_md_text="hello world\n",
            skill_text=skill_with_override,
            agent_text="agent body, three words\n",
        )
        r = run(["--repo-root", str(tmpdir), "--json"])
        try:
            data = json.loads(r.stdout)
            skill_entry = next(
                (f for f in data["files"] if f["path"].endswith("SKILL.md")), None
            )
            if (
                skill_entry is not None
                and skill_entry["tokens"] == 99999
                and skill_entry["source"] == "override"
            ):
                _pass(n, total, "front-matter projection_cost_tokens override honored")
            else:
                msg = f"override not honored; skill_entry={skill_entry!r}"
                _fail(n, total, msg)
                failures.append(msg)
        except (json.JSONDecodeError, StopIteration, KeyError) as exc:
            msg = f"override-fixture run failed: {exc}; stdout={r.stdout[:200]!r}"
            _fail(n, total, msg)
            failures.append(msg)

    # -----------------------------------------------------------------------
    # Assertion 6: --repo-root with predictable content produces predictable total
    # -----------------------------------------------------------------------
    n = 6
    with tempfile.TemporaryDirectory() as td:
        tmpdir = pathlib.Path(td)
        # 10 words each in CLAUDE.md, SKILL.md, agent.md => 30 words total
        # 30 words * 1.3 ratio = 39 tokens (rounded)
        ten_words = " ".join(["word"] * 10) + "\n"
        _make_fixture_repo(
            tmpdir,
            claude_md_text=ten_words,
            skill_text=ten_words,
            agent_text=ten_words,
        )
        r = run(["--repo-root", str(tmpdir), "--json"])
        try:
            data = json.loads(r.stdout)
            # 30 words * 1.3 = 39
            if data["total_tokens"] == 39:
                _pass(n, total, "fixture with 30 words yields predicted 39 tokens")
            else:
                msg = (
                    f"expected total_tokens=39 (30 words * 1.3); "
                    f"got {data['total_tokens']}"
                )
                _fail(n, total, msg)
                failures.append(msg)
        except (json.JSONDecodeError, KeyError) as exc:
            msg = f"predictable-total fixture run failed: {exc}"
            _fail(n, total, msg)
            failures.append(msg)

    # -----------------------------------------------------------------------
    # Assertion 7: over budget WITHOUT --strict exits 0 (over_budget true)
    # -----------------------------------------------------------------------
    n = 7
    r = run(["--json", "--budget", "0"])
    if r.returncode == 0:
        try:
            data = json.loads(r.stdout)
            if data.get("over_budget") is True:
                _pass(n, total, "over budget without --strict exits 0 (over_budget=true)")
            else:
                msg = f"over_budget not true with --budget 0: {data!r}"
                _fail(n, total, msg)
                failures.append(msg)
        except json.JSONDecodeError as exc:
            msg = f"--json --budget 0 not parseable: {exc}"
            _fail(n, total, msg)
            failures.append(msg)
    else:
        msg = f"over budget without --strict exited {r.returncode} (expected 0)"
        _fail(n, total, msg)
        failures.append(msg)

    # -----------------------------------------------------------------------
    # Assertion 8: --ci emits a ::warning:: annotation when over budget
    # -----------------------------------------------------------------------
    n = 8
    r = run(["--ci", "--budget", "0"])
    if r.returncode == 0 and "::warning::" in r.stdout:
        _pass(n, total, "--ci over budget emits ::warning:: annotation")
    else:
        msg = (
            f"--ci --budget 0: rc={r.returncode}, "
            f"warning_present={'::warning::' in r.stdout}; stdout={r.stdout[-120:]!r}"
        )
        _fail(n, total, msg)
        failures.append(msg)

    # -----------------------------------------------------------------------
    # Assertion 9: --ci --json still emits ::warning:: (annotation not dropped)
    # -----------------------------------------------------------------------
    n = 9
    r = run(["--ci", "--json", "--budget", "0"])
    has_warning = "::warning::" in r.stdout
    json_part = r.stdout.split("::warning::", 1)[0].strip()
    json_ok = False
    try:
        json_ok = json.loads(json_part).get("over_budget") is True
    except json.JSONDecodeError:
        json_ok = False
    if r.returncode == 0 and has_warning and json_ok:
        _pass(n, total, "--ci --json emits ::warning:: alongside valid JSON")
    else:
        msg = (
            f"--ci --json: rc={r.returncode}, has_warning={has_warning}, "
            f"json_ok={json_ok}"
        )
        _fail(n, total, msg)
        failures.append(msg)

    # -----------------------------------------------------------------------
    # Assertion 10: nested entry paths are normalized to forward slashes
    # -----------------------------------------------------------------------
    n = 10
    with tempfile.TemporaryDirectory() as td:
        tmpdir = pathlib.Path(td)
        _make_fixture_repo(
            tmpdir,
            claude_md_text="root file\n",
            skill_text="skill body\n",
            agent_text="agent body\n",
        )
        r = run(["--repo-root", str(tmpdir), "--json"])
        try:
            data = json.loads(r.stdout)
            backslashed = [f["path"] for f in data["files"] if "\\" in f["path"]]
            has_nested = any(f["path"] == "skills/test/SKILL.md" for f in data["files"])
            if not backslashed and has_nested:
                _pass(n, total, "nested entry paths use forward slashes")
            else:
                msg = f"path normalization: backslashed={backslashed}, has_nested={has_nested}"
                _fail(n, total, msg)
                failures.append(msg)
        except (json.JSONDecodeError, KeyError) as exc:
            msg = f"path-normalization fixture run failed: {exc}"
            _fail(n, total, msg)
            failures.append(msg)

    # -----------------------------------------------------------------------
    # Assertion 11: a UTF-8 BOM in plugin.json / CLAUDE.md is tolerated
    # -----------------------------------------------------------------------
    n = 11
    with tempfile.TemporaryDirectory() as td:
        tmpdir = pathlib.Path(td)
        _make_fixture_repo(
            tmpdir,
            claude_md_text="root file\n",
            skill_text="skill body\n",
            agent_text="agent body\n",
        )
        bom = b"\xef\xbb\xbf"
        for rel in (".claude-plugin/plugin.json", "CLAUDE.md"):
            p = tmpdir / rel
            p.write_bytes(bom + p.read_bytes())
        r = run(["--repo-root", str(tmpdir), "--json"])
        if r.returncode == 0:
            try:
                data = json.loads(r.stdout)
                if data.get("total_tokens", 0) > 0:
                    _pass(n, total, "UTF-8 BOM in plugin.json / CLAUDE.md tolerated")
                else:
                    msg = f"BOM fixture produced no tokens: {data!r}"
                    _fail(n, total, msg)
                    failures.append(msg)
            except json.JSONDecodeError as exc:
                msg = f"BOM fixture --json not parseable: {exc}"
                _fail(n, total, msg)
                failures.append(msg)
        else:
            msg = f"BOM fixture crashed: rc={r.returncode}; stderr={r.stderr.strip()!r}"
            _fail(n, total, msg)
            failures.append(msg)

    # -----------------------------------------------------------------------
    # Summary
    # -----------------------------------------------------------------------
    n_fail = len(failures)
    if n_fail == 0:
        print(f"test-measure-projection-cost: ALL {total} ASSERTIONS PASS")
        return 0
    print(f"test-measure-projection-cost: {n_fail} ASSERTIONS FAILED")
    return 1


if __name__ == "__main__":
    sys.exit(main())
