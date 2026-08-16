# Development and debugging

The hooks are plain scripts that read JSON on stdin and write JSON on stdout,
so you can drive them by hand from the plugin directory without going through
Claude Code.

```bash
# Simulate a PostToolUse event on a specific file
echo '{"tool_input": {"file_path": "src/main.rs"}}' \
  | CLAUDE_PROJECT_DIR=$(pwd) python3 hooks/post-tool-use.py

# Simulate a Stop event
echo '{}' | CLAUDE_PROJECT_DIR=$(pwd) python3 hooks/stop-hook.py

# Record an opportunity manually
CLAUDE_PROJECT_DIR=$(pwd) CLAUDE_PLUGIN_ROOT=$(pwd) \
  python3 skills/record-opportunity/record.py \
    --type custom \
    --file src/main.rs \
    --description "Test entry" \
    --severity low
```

`CLAUDE_PROJECT_DIR` decides where `.claude/boy-scout-todos.jsonl` and the
config file are read from and written to, so point it at a scratch directory
if you do not want to pollute a real backlog.

Notes on interpreting the output:

- The PostToolUse hook prints `{"suppressOutput": true}` and nothing else, by
  design. To see whether it recorded anything, look at the JSONL file.
- The Stop hook prints `{"decision": "approve"}` with no `systemMessage` when
  there is nothing new since the last run. It also writes
  `.claude/boy-scout-meta.json` when it does surface something, so a second
  invocation will be silent. Delete that file to replay.
- The Stop hook swallows any exception and still approves the stop, so a silent
  run can mean "nothing new" or "something went wrong". Call the detectors
  directly (from `hooks/lib/`) if a finding you expect never appears.

Inside Claude Code, `claude --debug` shows hook execution logs, including
non-zero exits and timeouts (PostToolUse is capped at 15s, Stop at 10s).

## Tests

See [CONTRIBUTING.md](../CONTRIBUTING.md).
