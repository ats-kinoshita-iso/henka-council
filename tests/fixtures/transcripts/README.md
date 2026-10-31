# Transcript fixtures

`session-fixture.jsonl` is a hand-built Claude Code session transcript used by
`tests/scripts/test-session-diagnostics.py` and `tests/hooks/test-session-diagnostics.sh`.
It reproduces the shapes that matter for the SessionEnd diagnostics hook: one assistant
entry per content block that repeats the same `message.usage` under one `requestId`
(so sums must deduplicate), a sidechain (subagent) entry, tool_use blocks, a failed
tool_result, a denied permission, a compaction boundary, an API retry, and a final
`cost-state` entry. The prompt contains the string `PROMPT-CANARY-7731`, which must
never appear in an event.
