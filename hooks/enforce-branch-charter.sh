#!/usr/bin/env bash
# PreToolUse hook — flag work that starts on a divergent branch without a
# declared work charter (the silent side-branch case, e.g. the bay-o-net
# wizardly-johnson branch that carried three sprints of wrong-direction work).
#
# Intercepts `git commit` / `git checkout -b` Bash tool calls. If the branch
# diverges from the configured mainline and Layer A (scripts/direction-check.py)
# returns BLOCK, the commit is blocked. Declared parallel/competitive charters
# (with a justification) only WARN. Fails OPEN whenever it cannot decide.
#
# Reads the Claude Code tool-call envelope JSON from stdin.
# Exit 0 = allow. Non-zero = block.

set -uo pipefail

envelope=$(cat 2>/dev/null || true)
[[ -z "$envelope" ]] && exit 0  # no envelope — fail open

_json_get() {
    local json="$1" dotpath="$2"
    if command -v jq &>/dev/null; then
        printf '%s' "$json" | jq -r "${dotpath} // empty" 2>/dev/null || true
    elif command -v python3 &>/dev/null; then
        _JSON_INPUT="$json" _JSON_PATH="$dotpath" python3 -c "
import json, os
try:
    d = json.loads(os.environ['_JSON_INPUT'])
    v = d
    for k in os.environ['_JSON_PATH'].lstrip('.').split('.'):
        v = v.get(k, '') if isinstance(v, dict) else ''
    print('' if v is None else str(v))
except Exception:
    print('')
" 2>/dev/null || true
    else
        exit 0  # neither jq nor python3 — fail open
    fi
}

_council_project_root() {
    local start="${1:-$PWD}" dir parent
    if [[ -n "${CLAUDE_PROJECT_DIR:-}" ]]; then
        printf '%s' "${CLAUDE_PROJECT_DIR%/}"; return 0
    fi
    dir="${start%/}"
    while [[ -n "$dir" && "$dir" != "/" ]]; do
        [[ -e "$dir/.git" ]] && { printf '%s' "$dir"; return 0; }
        parent=$(dirname "$dir"); [[ "$parent" == "$dir" ]] && break; dir="$parent"
    done
    printf '%s' "${start%/}"
}

tool_name=$(_json_get "$envelope" ".tool_name")
[[ "$tool_name" != "Bash" ]] && exit 0

command_str=$(_json_get "$envelope" ".tool_args.command")
# Only inspect commit / new-branch operations.
echo "$command_str" | grep -qE 'git[[:space:]]+(commit|checkout[[:space:]]+-b|switch[[:space:]]+-c)' || exit 0

root="$(_council_project_root "$(_json_get "$envelope" ".cwd")")"
config="${DIRECTION_CHECK_CONFIG:-$root/.council/config.json}"
script="${DIRECTION_CHECK_SCRIPT:-${CLAUDE_PLUGIN_ROOT:-$root}/scripts/direction-check.py}"

# Gate inert unless configured + enabled.
[[ -f "$config" ]] || exit 0
[[ -f "$script" ]] || exit 0
command -v python3 &>/dev/null || exit 0
enabled=$(_JSON_FILE="$config" python3 -c "
import json, os
try:
    d = json.load(open(os.environ['_JSON_FILE'], encoding='utf-8')).get('direction_check', {})
    print('1' if d.get('enabled') else '')
except Exception:
    print('')
" 2>/dev/null || true)
[[ -z "$enabled" ]] && exit 0

# Resolve the current branch (best effort) and the configured mainline.
# DIRECTION_CHECK_BRANCH overrides for testability.
branch="${DIRECTION_CHECK_BRANCH:-$(git -C "$root" branch --show-current 2>/dev/null || true)}"
mainline=$(_JSON_FILE="$config" python3 -c "
import json, os
try:
    print(json.load(open(os.environ['_JSON_FILE'], encoding='utf-8')).get('direction_check', {}).get('mainline_branch', 'main'))
except Exception:
    print('main')
" 2>/dev/null || true)
[[ -z "$branch" || "$branch" == "$mainline" ]] && exit 0  # on mainline — nothing to enforce here

# Best-effort: find a charter whose 'branch' matches, else branch-<slug>.json, else none.
charters_dir="$root/.council/charters"
charter_arg=()
if [[ -d "$charters_dir" ]]; then
    match=$(_BRANCH="$branch" _DIR="$charters_dir" python3 -c "
import json, os, glob, re
branch = os.environ['_BRANCH']
for p in sorted(glob.glob(os.path.join(os.environ['_DIR'], '*.json'))):
    try:
        if json.load(open(p, encoding='utf-8')).get('branch') == branch:
            print(p); break
    except Exception:
        pass
else:
    slug = re.sub(r'[^A-Za-z0-9._-]+', '-', branch).strip('-')
    cand = os.path.join(os.environ['_DIR'], f'branch-{slug}.json')
    print(cand if os.path.exists(cand) else '')
" 2>/dev/null || true)
    [[ -n "$match" ]] && charter_arg=(--charter "$match")
fi

python3 "$script" --config "$config" --branch "$branch" "${charter_arg[@]}" >/dev/null 2>&1
rc=$?

if (( rc >= 20 )); then
    echo "BLOCKED: branch '${branch}' diverges from mainline '${mainline}' without a sanctioned work charter." >&2
    echo "  Declare intent with: /henkaten-council:council-charter --mode parallel-exploration|competitive" >&2
    echo "  (Direction-check Layer A returned BLOCK. Set direction_check.tier_overrides to soften.)" >&2
    exit 1
elif (( rc >= 10 )); then
    echo "WARN: branch '${branch}' diverges from mainline '${mainline}'; declared exploration recorded." >&2
fi
exit 0
