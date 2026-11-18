# Recorded hook payloads

`pretooluse-native.jsonl` holds three PreToolUse payloads (Write, Edit, Bash)
recorded from Claude Code 2.1.318 on 2026-11-04 by a probe hook that saved its
stdin verbatim. Only machine-specific paths were normalized (the project to
`/work/proj`, plus `transcript_path` and `scratchpad_dir`); every key and the
shape of `tool_input` are exactly what Claude Code sent.

The guard tests start from these payloads and change only `tool_input.file_path`,
`tool_input.command` or `cwd`, so they exercise the field names Claude Code really
uses. Note what is absent: there is no `tool_args` key. Re-record the file when
Claude Code changes its hook input, rather than editing shapes by hand.
