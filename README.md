# Boy Scout Plugin for Claude Code

[![Tests](https://github.com/xpepper/boy-scout/actions/workflows/tests.yml/badge.svg)](https://github.com/xpepper/boy-scout/actions/workflows/tests.yml)

> *"Leave every piece of code a little better than you found it."*
> — Robert C. Martin, [97 Things Every Programmer Should Know, ch. 8](https://learning.oreilly.com/library/view/97-things-every/9780596809515/ch08.html)

Opportunistic refactoring for Claude Code. TDD skills optimise the
red-green-refactor loop of the task in front of them and keep no memory of what
they noticed along the way. This plugin keeps that memory: Claude records
improvement opportunities while working, they survive the session, and focused
agents turn them back into commits.

⚠️ Pre-alpha version, use it at your own risk ⚠️

---

## The loop

1. **Notice.** While doing anything else, Claude records what it sees — a refactor
   step it skipped, three files it had to read to answer one question, a compromise
   it made to keep a diff small. Small, safe, uncontroversial fixes in a file it is
   *already editing* get made on the spot instead, as their own commit.
2. **Surface.** When Claude finishes responding, a Stop hook reports what is new.
   Nothing interrupts you mid-task.
3. **Address.** `/boy-scout-session` dispatches one focused agent per item: each
   verifies its own change, commits it separately, and abandons it rather than
   pushing through if it stops being small.

[How it works in detail →](docs/how-it-works.md)

## Install

The repository is its own marketplace, so it installs the standard way — inside
Claude Code:

```
/plugin marketplace add xpepper/boy-scout
/plugin install boy-scout@boy-scout
```

or from a terminal:

```bash
claude plugin marketplace add xpepper/boy-scout
claude plugin install boy-scout@boy-scout
```

Restart the session to pick it up. To keep it to a single project rather than
every session on the machine, pass `--scope project` to both commands (or
`--scope local` for just you, untracked by git).

Requires **Python 3.10+**, no third-party dependencies. Unix/macOS only: file
locking uses `fcntl`.

Updating and removing:

```bash
claude plugin update boy-scout@boy-scout
claude plugin uninstall boy-scout@boy-scout
```

## Use

Just work normally — recording happens on its own. When you want to act on what
has piled up:

| Command | What it does |
|---------|--------------|
| `/boy-scout` | Show the backlog, what has been fixed, and what is worth doing next |
| `/boy-scout-session [n\|id]` | Address items with one focused agent each, verified and committed separately |
| `boy-scout-list` | The same backlog, from a terminal |
| `boy-scout-verify` | Re-check entries against the code; `--apply` repairs what moved or vanished |

Items stay open until closed with an outcome — `fixed`, `wontfix` or `stale` — so
the backlog can answer the only question that matters about it: how much of what
was recorded ever got improved. Each one is anchored to the code it describes, so
entries that the code has moved past are flagged rather than quietly turning into
fiction.

Sessions can also run on a schedule, unattended:
[scheduled resolution](docs/scheduled-resolution.md).

## Configure

There is almost nothing to configure, deliberately: what gets recorded is
Claude's judgment, not a threshold. The plugin auto-creates
`.claude/boy-scout-config.json` on first run with the one knob there is — when
the Stop hook starts nudging you that the backlog has grown.

```json
{ "session": { "triage_threshold": 20 } }
```

[Full reference →](docs/configuration.md)

> **Note.** Versions before this one also shipped opt-in static detectors that
> ran on every file write. They have been removed: they reported what a linter
> reports, and your linter does it better. See
> [how it works](docs/how-it-works.md#why-there-is-no-static-analysis-here).

---

[How it works](docs/how-it-works.md) ·
[Configuration](docs/configuration.md) ·
[TODO storage](docs/storage.md) ·
[Scheduled resolution](docs/scheduled-resolution.md) ·
[Development and debugging](docs/development.md) ·
[Contributing and tests](CONTRIBUTING.md)
