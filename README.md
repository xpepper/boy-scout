# Boy Scout Plugin for Claude Code

[![Tests](https://github.com/xpepper/boy-scout/actions/workflows/tests.yml/badge.svg)](https://github.com/xpepper/boy-scout/actions/workflows/tests.yml)

> *"Leave every piece of code a little better than you found it."*
> — Robert C. Martin, [97 Things Every Programmer Should Know, ch. 8](https://learning.oreilly.com/library/view/97-things-every/9780596809515/ch08.html)

A Claude Code plugin that implements Boy Scout Rule mechanics: passively detects refactoring opportunities as you work, then surfaces them at the end of each session so nothing gets lost and nothing interrupts your flow.

⚠️ Pre-alpha version, use it at your own risk ⚠️

---

## How it works

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

Claude also records **semantic** opportunities it notices during work, via the `record-opportunity` skill. That is the primary channel. The static detectors below are mechanical proxies (line counts, regexes) that trade precision for recall, so they are opt-in and disabled by default.

| Detector | What it finds | Languages |
|----------|--------------|-----------|
| **Duplication** | Copy-pasted blocks (≥6 lines by default) | Any file the hook reads |
| **Naming clarity** | Single-char identifiers, cryptic abbreviations | Rust, Elm, JS/TS, Python, Go |
| **Test coverage gap** | Source file changed but no test file found | Rust, Elm, JS/TS, Python, Go, Ruby, Java, Kotlin, Swift |
| **Function size** | Functions exceeding the line threshold | Python, Rust, JS/TS, Go |

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

The plugin auto-creates `.claude/boy-scout-config.json` on first run. Everything has a working default, so you only need the file to turn something on:

```json
{
  "detection": {
    "patterns": ["test_coverage"]
  }
}
```

`patterns` defaults to `[]`, meaning no static detector runs until you list one. Full reference, including sensitivity thresholds and ignore rules: [docs/configuration.md](docs/configuration.md).

---

## The `record-opportunity` skill

Claude uses this skill proactively whenever it notices an improvement during normal work. No user prompt is needed: Claude invokes it silently and adds a one-line note to its response.

Each observation is triaged into one of three outcomes. Most become **next**: recorded for a later session, which is the note you will usually see.

> *(Boy Scout: noted missing tests for `Invoice.apply_discount()` for later.)*

A small, obvious, uncontroversial fix in a file Claude is **already editing** is instead done **now**, on green, as its own separate commit, and recorded as already resolved. That is the actual Boy Scout Rule: leave the campground cleaner than you found it, rather than filing a report about the litter.

> *(Boy Scout: renamed `tmp` to `pending_invoice` while here.)*

Anything failing all four conditions, or not worth carrying at all, is **never** recorded. The gate is deliberately biased toward deferring: derailing your task is worse than a slightly longer backlog.

---

## How a session works

Just work normally. The Stop hook fires whenever Claude finishes a response and hands control back to you, not when you close the terminal, so there is nothing to trigger by hand. When findings have piled up since the last summary, Claude's reply ends with:

```
🏕️  Boy Scout report: 4 new refactoring opportunities detected.

  🟡 [Duplication] src/routes/auth.rs: Duplicated block (17 lines): lines 88–104 and 45–61
  🟢 [Naming]      src/pipeline/process.ts: Abbreviated identifier 'tmp' …
  🟡 [No tests]    src/billing/invoice.py: No test file found for invoice.py …
  🟢 [Long function] src/compiler/lower.ts: Function 'lowerExpr' spans 80 lines …

💡 All items are saved in .claude/boy-scout-todos.jsonl.
   Start a Boy Scout session whenever you're ready to address them incrementally.
```

Once the open backlog reaches `session.triage_threshold` (default 20), the summary gains a nudge to triage it. When you are ready, ask Claude to work through `.claude/boy-scout-todos.jsonl` one item at a time. Items stay open until closed with `resolve.py`, which also records whether they were fixed or written off: see [docs/storage.md](docs/storage.md).

---

## Scheduled resolution

Remembering to start a session is its own forgetting problem. `scripts/run-boy-scout-session.sh` runs a headless session against the open backlog and exits cleanly if there is nothing to do:

```bash
CLAUDE_PROJECT_DIR=/path/to/project ./scripts/run-boy-scout-session.sh
```

Each run addresses up to 5 of the highest-severity open items, verifying and committing each one individually. It never pushes. Cron, launchd, and the caveats before trusting it unattended: [docs/scheduled-resolution.md](docs/scheduled-resolution.md).

---

## More

[Configuration](docs/configuration.md) ·
[TODO storage](docs/storage.md) ·
[Scheduled resolution](docs/scheduled-resolution.md) ·
[Development and debugging](docs/development.md) ·
[Contributing and tests](CONTRIBUTING.md)
