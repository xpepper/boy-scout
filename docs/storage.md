# TODO storage

Opportunities are persisted in `.claude/boy-scout-todos.jsonl`: line-delimited
JSON, one entry per line, appended under an exclusive `fcntl` lock so parallel
hook runs cannot interleave. Nothing else in the plugin rewrites the file, so
it is safe to edit by hand.

The authoritative shape of an entry is [`schema/todo-item.json`](../schema/todo-item.json).
An example:

```json
{
  "id": "a3f9c12e",
  "type": "duplication",
  "file_path": "src/routes/auth.rs",
  "locations": [{"line_start": 88, "line_end": 104}],
  "description": "Block duplicated from src/routes/users.rs:45-61",
  "severity": "medium",
  "detected_at": 1713200000.0,
  "source": "hook",
  "dismissed": false
}
```

| Field | Notes |
|-------|-------|
| `id` | 8 hex characters, generated on insert |
| `type` | Category of the opportunity. The accepted values live in the schema; the `record-opportunity` CLI validates against the same set. |
| `file_path` | Relative to the project root |
| `locations` | Zero or more `{line_start, line_end}` ranges. File-level findings (a missing test file, say) carry an empty list, not a placeholder range. |
| `severity` | `low`, `medium`, or `high` |
| `detected_at` | Unix timestamp, used by the Stop hook to work out what is new |
| `source` | `"hook"` for static detection, `"skill"` for Claude's own semantic observation via `record-opportunity` |
| `dismissed` | `false` until the item is resolved or written off |
| `context` | Optional. A suggested approach, recorded by the skill when Claude has one. |

## What "open" means

Everything that reads the backlog (the Stop hook's counts, the scheduled
session runner, the deduplication check) considers only entries with
`"dismissed": false`. Closing an item means setting that field to `true`: there
is no separate "done" state and nothing removes lines from the file.

## Deduplication

Before appending, a new finding is checked against existing **open** entries
with the same `type` and the same `file_path`. If one matches, its `id` is
reused and nothing new is written, so repeatedly touching the same file does
not re-record the same issue on every edit.

What counts as a match depends on whether the finding is anchored to lines:

| Both findings | Match when |
|---------------|-----------|
| Line-anchored | Their line ranges overlap. The same region flagged again is the same issue however it happens to be worded. |
| File-level (empty `locations`) | Their descriptions match once normalised (case, punctuation, and whitespace collapsed). |
| One of each | Never. A file-level finding and a line-anchored one are different claims about the file. |

Keeping the two apart matters: file-level findings once shared a placeholder
range of `1-1`, which made every file-level finding in a file collide with
every other one of the same type, and the loser was silently discarded.

Once an entry is dismissed it no longer blocks anything: if the same issue
resurfaces later, it is recorded again as a new entry.

When the `record-opportunity` skill hits an existing entry this way, it reports
`"is_new": false` and says the item is already tracked rather than pretending to
have recorded something.

## Related state files

| File | Purpose |
|------|---------|
| `.claude/boy-scout-todos.jsonl` | The backlog |
| `.claude/boy-scout-meta.json` | `last_surfaced_at`, the timestamp of the last Stop hook summary. Deleting it makes the next Stop hook re-surface everything. |
| `.claude/boy-scout-config.json` | Configuration, see [configuration.md](configuration.md) |
