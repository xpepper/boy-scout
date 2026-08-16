# Development and debugging

The Stop hook is a plain script that reads JSON on stdin and writes JSON on
stdout, so you can drive it by hand from the plugin directory without going
through Claude Code.

```bash
# Simulate a Stop event
echo '{}' | CLAUDE_PROJECT_DIR=$(pwd) python3 hooks/stop-hook.py

# Record an opportunity manually
CLAUDE_PROJECT_DIR=$(pwd) bin/boy-scout-record \
  --type custom \
  --file src/main.rs \
  --description "Test entry" \
  --severity low
```

`CLAUDE_PROJECT_DIR` decides where `.claude/boy-scout-todos.jsonl` and the
config file are read from and written to, so point it at a scratch directory
if you do not want to pollute a real backlog.

## Why the CLIs live in `bin/`

Claude Code exports `$CLAUDE_PLUGIN_ROOT` and `$CLAUDE_PROJECT_DIR` to *hooks*.
It does not export them to the Bash tool, which is where the
`record-opportunity` skill runs its commands — a command written as
`python3 "$CLAUDE_PLUGIN_ROOT/…/record.py"` expands to a path with an empty
first segment and fails.

Claude Code does put every installed plugin's `bin/` directory on `PATH`, so
the wrappers there are callable by bare name. Each one resolves the plugin from
its own location, and `todo_manager.find_project_dir()` resolves the project by
walking up from the working directory to the nearest `.git` or `.claude`, with
`$CLAUDE_PROJECT_DIR` overriding both when it is set.

Notes on interpreting the output:

- The Stop hook prints `{"decision": "approve"}` with no `systemMessage` when
  there is nothing new since the last run. It also writes
  `.claude/boy-scout-meta.json` when it does surface something, so a second
  invocation will be silent. Delete that file to replay.
- The Stop hook swallows any exception and still approves the stop, so a silent
  run can mean "nothing new" or "something went wrong". Import `todo_manager`
  directly (from `hooks/lib/`) if an entry you expect never appears.

Inside Claude Code, `claude --debug` shows hook execution logs, including
non-zero exits and timeouts (Stop is capped at 10s).

## Tests

See [CONTRIBUTING.md](../CONTRIBUTING.md).
