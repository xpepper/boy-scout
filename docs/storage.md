# TODO storage

Opportunities are persisted in `.claude/boy-scout-todos.jsonl`: line-delimited
JSON, one entry per line, appended under an exclusive `fcntl` lock so parallel
hook runs cannot interleave.

**Do not edit it by hand.** Two writers share it: `boy-scout-record` appends
while you work, and closing an item rewrites the file in place. Both take the
same lock; a text editor takes nothing, so a hand-edit can silently drop a
concurrent write. Close items with
`boy-scout-resolve` instead.

The authoritative shape of an entry is [`schema/todo-item.json`](../schema/todo-item.json).
An example:

```json
{
  "id": "a3f9c12e",
  "type": "self_inflicted_debt",
  "file_path": "src/routes/auth.rs",
  "locations": [{"line_start": 88, "line_end": 104}],
  "description": "Copied parse_json_body from users.rs rather than extracting it, to keep this diff to one file",
  "severity": "medium",
  "detected_at": 1713200000.0,
  "source": "skill",
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
| `source` | Always `"skill"` on new entries. `"hook"` appears on entries written by the static detectors that earlier versions shipped, and is still read. |
| `dismissed` | `false` until the item is resolved or written off |
| `context` | Optional. A suggested approach, recorded by the skill when Claude has one. |
| `outcome` | Absent while the item is open. On closing: `fixed`, `wontfix`, or `stale`. |
| `resolved_at` | Unix timestamp, written when the item is closed |
| `resolution_note` | Optional. Why it was closed that way. |
| `anchor` | Optional. What the entry pointed at when it was recorded — see below. |

## What "open" means

Everything that reads the backlog (the Stop hook's counts, the scheduled
session runner, the deduplication check) considers only entries with
`"dismissed": false`. Nothing ever removes lines from the file.

`dismissed` records *that* an item is closed; `outcome` records *how*. Keeping
both means every reader that predates outcomes still works unchanged, while the
question that actually matters stays answerable: of everything recorded, how
much got fixed rather than written off. A backlog that cannot answer that is
not a backlog, it is a graveyard.

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

Closing an entry usually stops it blocking anything: if the same issue
resurfaces after being `fixed` or going `stale`, that is news, and it is
recorded again as a new entry.

`wontfix` is the exception. It keeps suppressing matching findings for good,
because it is a decision rather than an observation. The detection hook re-runs
over the whole file on every edit, so without that a declined item would
reappear on the very next keystroke and `wontfix` would mean nothing. Recording
against a `wontfix` entry reports it as declined rather than as tracked.

When the `record-opportunity` skill hits an existing entry this way, it reports
`"is_new": false` and says the item is already tracked rather than pretending to
have recorded something.

## Anchors: keeping an entry honest

An entry is a claim about code. Without something to check it against, the claim
silently stops being true: the lines it names become different lines, or the file
goes away, and nothing notices. A backlog whose live entries cannot be told from
its rotted ones is one nobody drains.

So each entry carries an `anchor`, captured at record time:

```json
"anchor": {
  "file_hash": "3f2a9c1e77b04d55",
  "fingerprint": "b81c04ee2a7f1930",
  "line_count": 5
}
```

`file_hash` covers the whole file, so an unchanged file needs no further work.
`fingerprint` covers only the significant lines the entry points at — blanks and
comments are skipped, and whitespace is collapsed, so reformatting does not read
as a rewrite. Both are SHA-256 prefixes rather than Python's built-in `hash()`,
which is randomised per process and would stop matching the moment it was read
back from disk.

Reading the backlog re-checks both and yields one of:

| Status | Meaning |
|--------|---------|
| `current` | The code the entry describes is still there |
| `moved` | Still there, at a different line range (the fingerprint was found elsewhere) |
| `drifted` | Not there any more — the region was rewritten |
| `missing` | The file itself is gone |
| `unverifiable` | Nothing to check: a file-level finding, or an entry recorded before anchors existed |

`boy-scout-list` annotates the actionable ones and counts them;
`boy-scout-list --stale` narrows to them. `boy-scout-verify` reports what can be
repaired, and `--apply` re-points `moved` entries (re-taking their anchor as it
goes, so the pass converges) and closes `missing` ones as `stale`.

**`drifted` is never closed automatically.** Changed code is evidence that an
entry may be obsolete, not proof: a rewrite can leave the original smell exactly
where it was. Closing on a fingerprint miss would delete real findings silently,
so that decision stays with a person or an agent that can read the code.

## Related state files

| File | Purpose |
|------|---------|
| `.claude/boy-scout-todos.jsonl` | The backlog |
| `.claude/boy-scout-meta.json` | `last_surfaced_at`, the timestamp of the last Stop hook summary. Deleting it makes the next Stop hook re-surface everything. |
| `.claude/boy-scout-config.json` | Configuration, see [configuration.md](configuration.md) |
