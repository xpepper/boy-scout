# Scheduled resolution

Manually starting a "Boy Scout session" still depends on remembering to do it,
which just relocates the forgetting problem from the finding to the backlog
file. `scripts/run-boy-scout-session.sh` closes that loop: it runs a headless
session (`claude -p`) against the open backlog and exits cleanly if there is
nothing to do.

```bash
CLAUDE_PROJECT_DIR=/path/to/project ./scripts/run-boy-scout-session.sh
```

The wrapper always exits 0, including when the `claude` CLI is missing or the
backlog is empty, so it is safe to wire into cron without extra error handling.

## What a session is told to do

`scripts/boy_scout_session.py` builds the prompt from the open backlog: how
many items there are, the breakdown by severity, and instructions to

1. pick up to 5 of the highest-severity open entries,
2. make the smallest safe change for each, one at a time,
3. verify it with the project's tests,
4. commit each individually with a conventional commit message,
5. close that entry once committed, by id, with
   `resolve.py --id <id> --outcome fixed`.

It is told explicitly not to edit `.claude/boy-scout-todos.jsonl` by hand: the
detection hook appends to it under a lock while the session works.

It is told not to batch unrelated fixes and not to push. The session runs with
`--allowedTools Read,Edit,Write,Bash`.

To see the exact prompt without running anything:

```bash
python3 scripts/boy_scout_session.py --project-dir /path/to/project --print-only
```

## Wiring it to a schedule

**cron:**

```cron
0 9 * * 1-5 CLAUDE_PROJECT_DIR=/path/to/project /path/to/boy-scout/scripts/run-boy-scout-session.sh >> /tmp/boy-scout.log 2>&1
```

**launchd (macOS):** wrap the same command in a `LaunchAgent` plist with a
`StartCalendarInterval`.

**Superpowers' `schedule` skill:** if you use the
[Superpowers](https://github.com/obra/superpowers) plugin, `/schedule` can
create a cron-driven cloud agent that runs this script on a recurring cadence
without you managing cron yourself.

## Before you trust it unattended

Run it manually first, and review what a scheduled session actually did
(`git log`, the updated `.claude/boy-scout-todos.jsonl`) before leaving it to
its own devices. It commits on its own; it never pushes.
