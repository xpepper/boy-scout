# Boy Scout Plugin for Claude Code

> *"Leave every piece of code a little better than you found it."*
> — Robert C. Martin, [97 Things Every Programmer Should Know, ch. 8](https://learning.oreilly.com/library/view/97-things-every/9780596809515/ch08.html)

A Claude Code plugin that implements Boy Scout Rule mechanics: passively detects refactoring opportunities as you work, then surfaces them at the end of each session so nothing gets lost and nothing interrupts your flow.

⚠️ Pre-alpha version, use it at your own risk ⚠️

---

## How It Works

```
During your task                    End of session
─────────────────                   ──────────────
Write / Edit a file                 Claude finishes responding
       │                                    │
       ▼                                    ▼
PostToolUse hook fires              Stop hook fires
       │                                    │
       ▼                                    ▼
Detectors run on the file           Reads new TODOs since last run
       │                                    │
       ▼                                    ▼
Findings → .claude/boy-scout-       Injects summary into Claude's
           todos.jsonl              context via systemMessage
           (silent, no transcript)  (inform-only, doesn't block)
```

Claude also records **semantic** opportunities it notices during work (via the `record-opportunity` skill). This is the primary channel: static detectors are mechanical proxies (line counts, regexes) that trade precision for recall, so they're **opt-in** and disabled by default — see [Configuration](#configuration).

---

## Detectors

⚠️ **Disabled by default.** These are threshold-based heuristics (line counts, regexes) — high recall, low precision. A fine 22-line function gets flagged as often as a genuinely tangled one. Enable individual detectors in `.claude/boy-scout-config.json` if you want mechanical detection on top of Claude's own semantic judgment (`record-opportunity`, which is always active).

Ordered by priority:

| Detector | What it finds | Languages |
|----------|--------------|-----------|
| **Duplication** | Copy-pasted code blocks (≥6 lines by default) | All supported |
| **Naming clarity** | Single-char identifiers, cryptic abbreviations | Rust, Elm, JS/TS, Python, Go |
| **Test coverage gap** | Source file changed but no test file found | Rust, Elm, JS/TS, Python, Go, Java, Kotlin |
| **Function size** | Functions exceeding line threshold | Python (AST), Rust, Elm, JS/TS, Go (regex) |

Language support priority: **Rust → Elm → JavaScript/TypeScript → Python** (others best-effort).

---

## Installation

Copy or symlink this directory into your Claude Code plugin path, then enable the plugin in Claude Code settings.

```bash
# Option A: symlink
ln -s /path/to/boy-scout ~/.claude/plugins/boy-scout

# Option B: copy
cp -r /path/to/boy-scout ~/.claude/plugins/
```

Requires **Python 3.10+** (no third-party dependencies).

> **Platform:** Unix/macOS only. The plugin uses `fcntl` for file locking, which is not available on Windows.

---

## Configuration

The plugin auto-creates `.claude/boy-scout-config.json` with defaults on first run. To customise, create or edit the file before that:

```json
{
  "detection": {
    "enabled": true,
    "patterns": [],
    "sensitivity": "balanced",
    "ignore_paths": [
      "vendor/",
      "dist/",
      "*.generated.ts",
      "node_modules/",
      "target/",
      ".git/"
    ],
    "ignore_tests": false
  },
  "output": {
    "suppress_transcript": true
  },
  "session": {
    "auto_clear": false,
    "triage_threshold": 20
  }
}
```

`patterns` defaults to `[]` — no static detector runs until you add one, e.g.
`"patterns": ["test_coverage"]`. `session.triage_threshold` controls when the
Stop hook adds a "backlog has grown" nudge to its summary (see
[How the Stop Hook Fires](#how-the-stop-hook-fires)).

### Sensitivity levels

| Level | Min dup lines | Max function lines |
|-------|--------------|-------------------|
| `aggressive` | 4 | 10 |
| `balanced` *(default)* | 6 | 20 |
| `conservative` | 10 | 35 |

---

## TODO Storage

Opportunities are persisted in `.claude/boy-scout-todos.jsonl` (line-delimited JSON, one entry per line). Each entry follows the schema in `schema/todo-item.json`:

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

`source` is either `"hook"` (static detection) or `"skill"` (Claude's semantic observation).

**Deduplication:** before appending, a new finding is checked against existing
*open* (non-dismissed) entries with the same `type`, `file_path`, and an
overlapping line range. If one matches, its `id` is reused and nothing new is
written — repeatedly touching the same file doesn't re-record the same issue
on every edit. Once an entry is dismissed, the same issue can be recorded
again if it resurfaces.

---

## The `record-opportunity` Skill

Claude uses this skill proactively whenever it notices an improvement during normal work. No user prompt needed — Claude silently invokes it and adds a one-line note in its response:

> *(Boy Scout: noted missing tests for `Invoice.apply_discount()` for later.)*

---

## How the Stop Hook Fires

The **Stop hook fires at the end of every Claude response** — not when you close the terminal. Whenever Claude finishes answering and hands control back to you, the Stop event triggers.

This means no special action is needed. The workflow is:

1. **Work normally** — ask Claude to write or edit files
2. **PostToolUse runs silently** on each modified file, appending any findings to `.claude/boy-scout-todos.jsonl`
3. **Stop hook fires** after Claude's response — if new findings exist since the last run, Claude's reply will end with a Boy Scout summary:
   ```
   🏕️  Boy Scout report: 4 refactoring opportunities detected this session.

     🟡 [Duplication] src/routes/auth.rs: Duplicated block (6+ lines): lines 88–104 and 45–61
     🟢 [Naming]      src/pipeline/process.ts: Abbreviated identifier 'tmp' …
     🟡 [No tests]    src/billing/invoice.py: No test file found for invoice.py …
     🟢 [Long fn]     src/compiler/lower.elm: Function 'lowerExpr' spans 80 lines …

   💡 All items are saved in .claude/boy-scout-todos.jsonl.
      Start a Boy Scout session whenever you're ready to address them incrementally.
   ```
   If the **open** (non-dismissed) backlog has reached `session.triage_threshold`
   (default 20), the summary gains one more block:
   ```
   ⚠️  Backlog has grown to 25 open items (triage threshold: 20).
      Run a Boy Scout session — or dismiss stale items — before it stops being trustworthy.
   ```
   This nudge only ever rides along with an actual new-findings summary — it
   never fires on an idle Stop event by itself, so it can't turn into a nag.
4. **Boy Scout session** — when ready, ask Claude to work through `.claude/boy-scout-todos.jsonl`, addressing each opportunity one at a time, or run one headlessly on a schedule — see [Scheduled Resolution](#scheduled-resolution)

---

## Scheduled Resolution

Manually starting a "Boy Scout session" still depends on remembering to do
it — which just relocates the forgetting problem from *the finding* to *the
backlog file*. `scripts/run-boy-scout-session.sh` closes that loop: it runs
a headless session (`claude -p`) against the open backlog and exits cleanly
if there's nothing to do.

```bash
CLAUDE_PROJECT_DIR=/path/to/project ./scripts/run-boy-scout-session.sh
```

Each run addresses up to 5 of the highest-severity open items, verifying and
committing each individually, marking its entry `"dismissed": true` when
done. It never pushes.

**Wiring it to a schedule:**

- **cron** —
  ```cron
  0 9 * * 1-5 CLAUDE_PROJECT_DIR=/path/to/project /path/to/boy-scout/scripts/run-boy-scout-session.sh >> /tmp/boy-scout.log 2>&1
  ```
- **launchd** (macOS) — wrap the same command in a `LaunchAgent` plist with a `StartCalendarInterval`.
- **Superpowers' `schedule` skill** — if you use the [Superpowers](https://github.com/obra/superpowers) plugin, `/schedule` can create a cron-driven cloud agent that runs this script on a recurring cadence without you managing cron yourself.

Review what a scheduled session actually did (`git log`, the updated
`.claude/boy-scout-todos.jsonl`) before trusting it unattended — start with a
manual run first.

---

## Plugin Structure

```
boy-scout/
├── .claude-plugin/
│   └── plugin.json              # Plugin manifest
├── hooks/
│   ├── hooks.json               # PostToolUse + Stop hook configuration
│   ├── post-tool-use.py         # Runs detectors on modified files
│   ├── stop-hook.py             # Surfaces new TODOs at session end
│   └── lib/
│       ├── pattern_analyzer.py  # Shared file analysis utilities
│       ├── todo_manager.py      # JSONL persistence + file locking
│       └── detectors.py        # Duplication, naming, coverage, size detectors
├── skills/
│   └── record-opportunity/
│       ├── SKILL.md             # Skill definition (proactive semantic recording)
│       └── record.py            # CLI handler invoked by Claude
├── scripts/
│   ├── boy_scout_session.py     # Builds/runs a headless session prompt
│   └── run-boy-scout-session.sh # Cron/launchd-friendly wrapper
├── schema/
│   └── todo-item.json           # JSON schema for TODO entries
├── tests/                       # pytest suite for lib/scripts behavior
└── README.md
```

---

## Testing

```bash
python3 -m pytest tests/
```

No third-party test dependencies beyond `pytest` itself (dev-only; the
plugin remains zero-dependency at runtime).

---

## Debugging

Run hooks manually to test them:

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

Enable debug mode in Claude Code with `claude --debug` to see hook execution logs.
