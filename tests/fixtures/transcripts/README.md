# Transcript fixtures

Recorded Claude Code transcripts (2.1.316 and 2.1.318, Linux), redacted for a public
repository by [`redact.py`](redact.py), for the session-lifetime deriver
(`scripts/session_lifetimes.py`, cloud-catcher ADR-0006 amendment A1). They replace the
hand-built `session-fixture.jsonl` of henka-council #28 (review finding C13).

Each fixture is a Claude Code projects directory: `projects/<slug>/<session_id>.jsonl`, the
session's subagent files under `projects/<slug>/<session_id>/subagents/`, and, where the
probe captured them, `snapshots/` with the transcript as each SessionEnd hook saw it plus
`snapshots/manifest.json` (session, reason, prompt id and process placeholder per snapshot).
Sessions are numbered `00000000-0000-4000-8000-00000000000N` in the order of their first entry.

What redaction keeps, unchanged: entry types and order, parentUuid links, isSidechain,
timestamps, every usage number and every cost-state number. What it replaces consistently
within a fixture: session ids, uuids, requestIds, tool, prompt, agent and workflow ids (by
placeholders); model ids (by `model-a`, `model-b`, ...; `<synthetic>` stays); MCP tool names
(by `mcp__srvN__toolN`); prompt, response, thinking and tool text (by `*-CANARY-*` strings that
the tests assert never reach an event). Everything else (paths, cwd, URLs, titles,
attachments, queued text) is dropped.

| Fixture | Recorded probe | Covers |
|---|---|---|
| `p01-resume-compact-clear-fork` | lifecycle-facts P1 | startup, `--resume`, `--continue`, `--resume '/compact'`, `-p /clear` (empty lifetimes), a fork of the compacted session, the session `/clear` created and its `--continue` |
| `p02-fork` | P2 | `-p --fork-session` of an uncompacted session |
| `p03-clear-interactive` | P3 | interactive `/clear` (closing cost-state written after SessionEnd), a later resume with no turn (equal-total re-writes) |
| `p04-sigkill-resume` | P4 | a lifetime SIGKILLed mid-turn, then resumed (Stage 1: one event, shortfall) |
| `p05-fork-subagent` | P5 | a background subagent file, a fork, a resume of the parent |
| `p06-resume-other-dir` | P6 | a resume from another directory (entries stay in the original project dir) |
| `p07-sigterm` | P7 | SIGTERM mid-request (a lifetime with a cost-state and no spend: no event) |
| `p08-stream-json-sigterm` | P8 | stream-json input ended by EOF, then by SIGTERM |
| `p09-fork-cmdline` | P9 | `-p` fork (the probe that read the fork's command line) |
| `p10-clear-after-resume` | P10 | startup, resume, `-p /clear`, interactive resume ended by `/clear` |
| `p11-concurrent-resumes` | P11 | two processes resuming one session at once |
| `if-interactive-fork` | judge-correctness IF | interactive fork (no queue-operation entries) |
| `r-c03-subagent` | review C03 p1 | a foreground subagent with its own tool call |
| `r-c08-config-denial`, `r-c08-hook-denial` | review C08 p1, p2 | permission denials by config and by a PreToolUse hook |
| `r-c18-api-retries` | review C18 | retried API errors (`system` `api_error` with `retryAttempt`) |
| `r-c36-synthetic` | review C36 | `<synthetic>` replies, all-failure and mixed |
| `real-session` (gzip) | the cloud session of 2026-10-31 to 2026-11-05 | six settled lifetimes, workflow subagent files, a compaction; cut before the seventh lifetime's first entry |

Expected values live in `tests/scripts/test-session-diagnostics.py`, computed from each
fixture's own cost-state entries and requestId-deduplicated token sums.
