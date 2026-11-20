"""Direction-check engine — Layer A (deterministic tripwires).

Catches *direction drift*: work that contradicts the project's strategic-anchor
document, of the kind that compounded across three sprints on the bay-o-net
project before anyone noticed (the .cmpx-writer-against-"no-writer" episode,
ADR 0008).

This is LAYER A only: cheap, high-precision, NO LLM. It runs on every surface
that cannot sanely call a model synchronously — the branch git hook (Surface 2)
and CI (Surface 3) — and it does the highest-value catch of all: a divergent
branch with *no declared charter* (the silent side-branch case). The semantic
verdict for paraphrased/novel drift is LAYER B (the direction-guardian agent),
which runs in-session and is intentionally not implemented here.

Determinism alone is insufficient (false negatives on paraphrase, false
positives -> alarm fatigue), which is exactly why Layer A is scoped to
presence/declaration/known-killed-workstream tripwires and defers the semantic
call to Layer B.

Checks (each yields a severity; the verdict is the max):
  1. charter presence / exploration_mode declared
  2. strategic-anchor citation present in the contract
  3. known-killed-workstream reintroduction (config keyword list)
  4. mode/divergence consistency (non-mainline modes need a justification)

The gate is inert unless the config's direction_check.enabled is true: with no
config, or with the gate off, the CLI prints a notice and exits 0 (PASS), so a
repo that vendors this script with the gate off is never blocked.

Tier severities map to exit codes so hooks/CI can branch without a model:
    PASS  -> 0
    WARN  -> 10
    BLOCK -> 20

Usage:
    python scripts/direction-check.py \
        --config .council/config.json \
        --charter .council/charters/sprint-12.json \
        --spec .harness/spec.md \
        --contract .harness/contracts/sprint-12.md \
        --branch "$(git branch --show-current)" \
        [--root . --auto-contract]  # resolve the contract when --contract is absent
        [--charters-dir .council/charters]  # resolve the charter when --charter is absent
        [--emit-henka -]   # write a henka-record candidate to stdout/path
        [--ci]             # terse, CI-annotation-friendly output
"""
from __future__ import annotations

import argparse
import datetime
import json
import pathlib
import re
import sys
from typing import Optional


def _now_iso() -> str:
    return datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

PASS, WARN, BLOCK = "pass", "warn", "block"
_SEVERITY = {PASS: 0, WARN: 10, BLOCK: 20}
_IMPACT = {PASS: "informational", WARN: "actionable", BLOCK: "blocking"}
_MODES = {"mainline", "parallel-exploration", "competitive"}


def _read_text(path: Optional[pathlib.Path]) -> str:
    if path is None:
        return ""
    try:
        return path.read_text(encoding="utf-8")
    except OSError:
        return ""


def _read_json(path: Optional[pathlib.Path]) -> Optional[dict]:
    if path is None or not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def _load_direction_config(config: Optional[dict]) -> dict:
    """Extract the direction_check block from a council config (or accept a bare block)."""
    if not config:
        return {}
    if "direction_check" in config and isinstance(config["direction_check"], dict):
        return config["direction_check"]
    # Allow passing the bare block directly (testability).
    return config


_CONTRACT_RE = re.compile(r"^sprint-(\d+)\.md$")


def resolve_contract(root: pathlib.Path, charter: Optional[dict]) -> Optional[pathlib.Path]:
    """Find the sprint contract under <root>/.harness/contracts/ by convention.

    With a charter whose sprint_context is an integer, return sprint-{NN}.md for
    that sprint (any zero-padding). Otherwise return the highest-numbered
    sprint-{NN}.md, the most recent contract. None when nothing matches.
    """
    contracts_dir = root / ".harness" / "contracts"
    if not contracts_dir.is_dir():
        return None
    found: dict[int, pathlib.Path] = {}
    for p in contracts_dir.iterdir():
        m = _CONTRACT_RE.match(p.name)
        if m and p.is_file():
            found[int(m.group(1))] = p
    if not found:
        return None
    sprint = (charter or {}).get("sprint_context")
    if isinstance(sprint, int) and not isinstance(sprint, bool):
        return found.get(sprint)
    return found[max(found)]


def resolve_charter(charters_dir: pathlib.Path, branch: Optional[str]) -> Optional[pathlib.Path]:
    """Find the charter for a branch: the first *.json whose "branch" field
    equals it (sorted by name), else branch-<slug>.json. None when neither exists."""
    if not branch or not charters_dir.is_dir():
        return None
    for p in sorted(charters_dir.glob("*.json")):
        data = _read_json(p)
        if isinstance(data, dict) and data.get("branch") == branch:
            return p
    slug = re.sub(r"[^A-Za-z0-9._-]+", "-", branch).strip("-")
    cand = charters_dir / f"branch-{slug}.json"
    return cand if cand.is_file() else None


def _keyword_pattern(kw: str) -> "re.Pattern[str]":
    """Match a killed-workstream keyword as whole words.

    Any non-alphanumeric run may sit between the keyword's words, so
    "`.cmpx` writer", "cmpx-writer" and "cmpx_writer" all match "cmpx writer".
    The match may not start inside a longer alphanumeric token, so
    "syncmpx writer" does not match. The trailing edge is left open so plurals
    and suffixes ("cmpx writers") still match.
    """
    body = re.escape(kw).replace(r"\ ", r"[^A-Za-z0-9]+")
    return re.compile(rf"(?<![A-Za-z0-9]){body}", re.IGNORECASE)


def _max_severity(a: str, b: str) -> str:
    return a if _SEVERITY[a] >= _SEVERITY[b] else b


def evaluate(
    *,
    charter: Optional[dict],
    direction_cfg: dict,
    spec_text: str,
    contract_text: str,
    branch: Optional[str],
) -> dict:
    """Run Layer A checks; return a verdict dict {result, impact_level, findings}."""
    findings: list[str] = []
    verdict = PASS

    mainline_branch = direction_cfg.get("mainline_branch", "main")
    killed = [str(k) for k in direction_cfg.get("killed_workstreams", [])]
    locked = [str(d) for d in direction_cfg.get("locked_decisions", [])]
    anchor_path = direction_cfg.get("anchor_path", "")
    # The charter's own strategic_anchor (path + locked_decisions) counts as an
    # anchor citation token alongside the config-level ones.
    charter_anchor = (charter or {}).get("strategic_anchor") or {}
    if not isinstance(charter_anchor, dict):
        charter_anchor = {}
    charter_locked = [str(d) for d in charter_anchor.get("locked_decisions", []) or []]
    charter_anchor_path = str(charter_anchor.get("path") or "")
    overrides = direction_cfg.get("tier_overrides", {})  # check_id -> "pass|warn|block"
    # The anchor citation may appear in either the spec or the contract.
    citation_haystack = f"{spec_text}\n{contract_text}"
    # Killed-workstream reintroduction is judged against the CONTRACT (the
    # *proposed* work) only — NOT the spec, which legitimately documents retired
    # workstreams in its history (a real false-positive source: bay-o-net's spec
    # mentions the deprecated cmpx writer 10+ times). Scoping to the contract is
    # what keeps Layer A from crying wolf; semantic spec drift is Layer B's job.
    proposed_text = contract_text

    def tier(check_id: str, default: str) -> str:
        ov = overrides.get(check_id)
        return ov if ov in _SEVERITY else default

    on_divergent_branch = bool(branch) and branch != mainline_branch

    # --- Check 1: charter presence + exploration_mode declared --------------
    if charter is None:
        # The headline catch: a divergent branch with NO declared charter is
        # exactly the silent side-branch (wizardly-johnson) case -> BLOCK.
        if on_divergent_branch:
            findings.append(
                f"check1/no-charter: divergent branch '{branch}' has no work charter "
                f"declaring exploration_mode (mainline is '{mainline_branch}')."
            )
            verdict = _max_severity(verdict, tier("no_charter_divergent_branch", BLOCK))
        else:
            findings.append(
                "check1/no-charter: no work charter found for this work (on mainline)."
            )
            verdict = _max_severity(verdict, tier("no_charter_mainline", WARN))
        # No charter: the content checks (2 and 3) still run, treating the work
        # as undeclared mainline work. Check 4 needs a declared mode, so it
        # cannot fire.
        mode = "mainline"
    else:
        mode = charter.get("exploration_mode")
    if charter is not None and mode not in _MODES:
        findings.append(
            f"check1/mode: charter exploration_mode '{mode}' is missing or invalid "
            f"(must be one of {sorted(_MODES)})."
        )
        verdict = _max_severity(verdict, tier("mode_missing", BLOCK))
        mode = "mainline"  # treat as strictest for downstream checks

    declared_divergent = mode in {"parallel-exploration", "competitive"}

    # --- Check 2: strategic-anchor citation in the contract -----------------
    anchor_tokens: list[str] = []
    for tok in (
        [pathlib.Path(anchor_path).name if anchor_path else "",
         pathlib.Path(charter_anchor_path).name if charter_anchor_path else ""]
        + locked + charter_locked
    ):
        if tok and tok not in anchor_tokens:
            anchor_tokens.append(tok)
    if anchor_tokens and not citation_haystack.strip():
        # Nothing to search (no spec or contract was supplied or found): say so
        # rather than report a missing citation in text that does not exist.
        findings.append(
            "check2/anchor-citation: skipped, no spec or contract text supplied."
        )
    elif anchor_tokens:
        cited = any(tok and tok in citation_haystack for tok in anchor_tokens)
        if not cited and not declared_divergent:
            findings.append(
                f"check2/anchor-citation: contract does not cite the strategic anchor "
                f"({', '.join(anchor_tokens)})."
            )
            verdict = _max_severity(verdict, tier("missing_anchor_citation", WARN))

    # --- Check 3: known-killed-workstream reintroduction --------------------
    hits = []
    for kw in killed:
        if not kw:
            continue
        if _keyword_pattern(kw).search(proposed_text):
            hits.append(kw)
    if hits:
        if not declared_divergent:
            # Drift on mainline / undeclared -> BLOCK. This is the bay-o-net catch.
            findings.append(
                f"check3/killed-workstream: reintroduces killed workstream(s) "
                f"{hits} on mainline/undeclared work."
            )
            verdict = _max_severity(verdict, tier("killed_workstream_mainline", BLOCK))
        else:
            # Declared exploration/competitive: legitimate WHEN justified.
            just = ((charter or {}).get("divergence_justification") or "").strip()
            if len(just) >= 20:
                findings.append(
                    f"check3/killed-workstream: touches killed workstream(s) {hits}, "
                    f"but declared as '{mode}' with justification -> WARN."
                )
                verdict = _max_severity(verdict, tier("killed_workstream_declared", WARN))
            else:
                findings.append(
                    f"check3/killed-workstream: touches killed workstream(s) {hits} "
                    f"under mode '{mode}' but has no divergence_justification -> BLOCK."
                )
                verdict = _max_severity(verdict, tier("declared_without_justification", BLOCK))

    # --- Check 4: mode/divergence consistency -------------------------------
    if declared_divergent and charter is not None:
        just = (charter.get("divergence_justification") or "").strip()
        if len(just) < 20:
            findings.append(
                f"check4/justification: exploration_mode '{mode}' requires a "
                f"divergence_justification (>= 20 chars)."
            )
            verdict = _max_severity(verdict, tier("declared_without_justification", BLOCK))

    if verdict == PASS and all(f.startswith("check2/anchor-citation: skipped") for f in findings):
        findings.append("no direction drift detected (Layer A).")

    return {
        "result": verdict,
        "impact_level": _IMPACT[verdict],
        "findings": findings,
    }


def build_henka_candidate(verdict: dict, charter: Optional[dict], branch: Optional[str]) -> dict:
    """Shape a henka-record candidate for append-henka.py (Method-axis scope-change).

    Schema-valid so it can be piped straight to append-henka.py. henka_id and
    detected_at are sentinels ('HK-0000' / a UTC stamp) that the Orchestrator —
    the only sanctioned writer — (re)assigns at persist time.
    """
    confidence = {BLOCK: "high", WARN: "medium", PASS: "low"}[verdict["result"]]
    response_type = {BLOCK: "andon-stop", WARN: "propose-to-user", PASS: "log-only"}[verdict["result"]]
    sprint_context = (charter or {}).get("sprint_context")
    return {
        "henka_id": "HK-0000",
        "sprint_context": sprint_context if isinstance(sprint_context, int) else 0,
        "fourM_axis": "Method",
        "category": "scope-change",
        "change_origin": "active",
        "impact_level": verdict["impact_level"],
        "description": "direction-check (Layer A): " + " | ".join(verdict["findings"]),
        "affected_artifacts": [a for a in [
            (charter or {}).get("strategic_anchor", {}).get("path"),
        ] if a],
        "response_type": response_type,
        "evidence": [
            {
                "claim": f"Direction-check Layer A verdict: {verdict['result'].upper()}"
                + (f" on branch '{branch}'" if branch else ""),
                "evidence_class": "observed",
                "confidence": confidence,
            }
        ],
        "status": "classified",
        "detected_at": _now_iso(),
    }


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=pathlib.Path, help="council config.json (or a bare direction_check block).")
    parser.add_argument("--charter", type=pathlib.Path, help="work-charter JSON for this work.")
    parser.add_argument("--spec", type=pathlib.Path, help=".harness/spec.md.")
    parser.add_argument("--contract", type=pathlib.Path, help="proposed sprint contract .md.")
    parser.add_argument("--branch", help="current git branch name.")
    parser.add_argument("--charters-dir", type=pathlib.Path,
                        help="when --charter is absent, use the charter in this directory whose 'branch' "
                             "matches --branch, else branch-<slug>.json.")
    parser.add_argument("--root", type=pathlib.Path, default=pathlib.Path("."),
                        help="project root for --auto-contract (default: current directory).")
    parser.add_argument("--auto-contract", action="store_true",
                        help="when --contract is absent, resolve <root>/.harness/contracts/sprint-{NN}.md "
                             "from the charter's sprint_context, else the highest-numbered contract.")
    parser.add_argument("--emit-henka", help="write a henka-record candidate JSON to this path ('-' for stdout).")
    parser.add_argument("--ci", action="store_true", help="terse, CI-annotation-friendly output.")
    args = parser.parse_args(argv)

    direction_cfg = _load_direction_config(_read_json(args.config))
    if not direction_cfg.get("enabled"):
        # Off by default: no config, or direction_check.enabled not true.
        msg = "direction_check is not enabled in the config; skipping (PASS)."
        if args.ci:
            print(f"::notice::direction-check: {msg}")
            print("direction-check: PASS")
        else:
            print(json.dumps({"result": PASS, "impact_level": _IMPACT[PASS], "findings": [msg]}, indent=2))
        return _SEVERITY[PASS]
    charter_path = args.charter
    if charter_path is None and args.charters_dir is not None:
        charter_path = resolve_charter(args.charters_dir, args.branch)
    charter = _read_json(charter_path)
    contract_path = args.contract
    if contract_path is None and args.auto_contract:
        contract_path = resolve_contract(args.root, charter)
    verdict = evaluate(
        charter=charter,
        direction_cfg=direction_cfg,
        spec_text=_read_text(args.spec),
        contract_text=_read_text(contract_path),
        branch=args.branch,
    )

    if args.emit_henka:
        candidate = build_henka_candidate(verdict, charter, args.branch)
        payload = json.dumps(candidate, indent=2)
        if args.emit_henka == "-":
            sys.stderr.write(payload + "\n")
        else:
            pathlib.Path(args.emit_henka).write_text(payload + "\n", encoding="utf-8")

    if args.ci:
        level = {PASS: "notice", WARN: "warning", BLOCK: "error"}[verdict["result"]]
        for f in verdict["findings"]:
            print(f"::{level}::direction-check: {f}")
        print(f"direction-check: {verdict['result'].upper()}")
    else:
        print(json.dumps(verdict, indent=2))

    return _SEVERITY[verdict["result"]]


if __name__ == "__main__":
    sys.exit(main())
