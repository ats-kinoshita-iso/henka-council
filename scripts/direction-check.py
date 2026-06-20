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
        [--emit-henka -]   # write a henka-record candidate to stdout/path
        [--ci]             # terse, CI-annotation-friendly output
"""
from __future__ import annotations

import argparse
import json
import pathlib
import re
import sys
from typing import Optional

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
    overrides = direction_cfg.get("tier_overrides", {})  # check_id -> "pass|warn|block"
    haystack = f"{spec_text}\n{contract_text}"

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
        # No charter -> nothing else to evaluate; return early.
        return {
            "result": verdict,
            "impact_level": _IMPACT[verdict],
            "findings": findings,
        }

    mode = charter.get("exploration_mode")
    if mode not in _MODES:
        findings.append(
            f"check1/mode: charter exploration_mode '{mode}' is missing or invalid "
            f"(must be one of {sorted(_MODES)})."
        )
        verdict = _max_severity(verdict, tier("mode_missing", BLOCK))
        mode = "mainline"  # treat as strictest for downstream checks

    declared_divergent = mode in {"parallel-exploration", "competitive"}

    # --- Check 2: strategic-anchor citation in the contract -----------------
    anchor_tokens = [t for t in ([pathlib.Path(anchor_path).name] if anchor_path else []) + locked if t]
    if anchor_tokens:
        cited = any(tok and tok in haystack for tok in anchor_tokens)
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
        pattern = re.compile(re.escape(kw).replace(r"\ ", r"[-_\s]+"), re.IGNORECASE)
        if pattern.search(haystack):
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
            just = (charter.get("divergence_justification") or "").strip()
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
    if declared_divergent:
        just = (charter.get("divergence_justification") or "").strip()
        if len(just) < 20:
            findings.append(
                f"check4/justification: exploration_mode '{mode}' requires a "
                f"divergence_justification (>= 20 chars)."
            )
            verdict = _max_severity(verdict, tier("declared_without_justification", BLOCK))

    if verdict == PASS and not findings:
        findings.append("no direction drift detected (Layer A).")

    return {
        "result": verdict,
        "impact_level": _IMPACT[verdict],
        "findings": findings,
    }


def build_henka_candidate(verdict: dict, charter: Optional[dict], branch: Optional[str]) -> dict:
    """Shape a henka-record candidate for append-henka.py (Method-axis scope-change)."""
    return {
        "fourM_axis": "Method",
        "category": "scope-change",
        "change_origin": "active",
        "impact_level": verdict["impact_level"],
        "description": "direction-check (Layer A): " + " | ".join(verdict["findings"]),
        "affected_artifacts": [a for a in [
            (charter or {}).get("strategic_anchor", {}).get("path"),
        ] if a],
        "evidence": [
            {
                "claim": f"Direction-check Layer A verdict: {verdict['result'].upper()}"
                + (f" on branch '{branch}'" if branch else ""),
                "evidence_class": "observed",
                "confidence": 4,
            }
        ],
    }


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=pathlib.Path, help="council config.json (or a bare direction_check block).")
    parser.add_argument("--charter", type=pathlib.Path, help="work-charter JSON for this work.")
    parser.add_argument("--spec", type=pathlib.Path, help=".harness/spec.md.")
    parser.add_argument("--contract", type=pathlib.Path, help="proposed sprint contract .md.")
    parser.add_argument("--branch", help="current git branch name.")
    parser.add_argument("--emit-henka", help="write a henka-record candidate JSON to this path ('-' for stdout).")
    parser.add_argument("--ci", action="store_true", help="terse, CI-annotation-friendly output.")
    args = parser.parse_args(argv)

    direction_cfg = _load_direction_config(_read_json(args.config))
    charter = _read_json(args.charter)
    verdict = evaluate(
        charter=charter,
        direction_cfg=direction_cfg,
        spec_text=_read_text(args.spec),
        contract_text=_read_text(args.contract),
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
