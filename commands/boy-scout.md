---
description: Show the Boy Scout backlog — what has been recorded, what has been fixed, and what is worth addressing next.
argument-hint: "[file path]"
allowed-tools: Bash(boy-scout-list:*), Bash(boy-scout-verify:*), Read, Grep, Glob
---

Show the user where their Boy Scout backlog stands. This command **reports and
proposes**. It does not change any code.

## 1. Read the backlog

```bash
boy-scout-list
```

If `$ARGUMENTS` names a file or path, scope the listing to it:
`boy-scout-list --file "$ARGUMENTS"`.

If the command is not found, the plugin's `bin/` is not on `PATH` — say so
rather than falling back to reading `.claude/boy-scout-todos.jsonl` by hand.

## 2. Say what is actually there

Show the listing, then add what the raw list does not say:

- **Where the weight is.** Several items in one file or one module is a
  stronger signal than any of them alone — that is shotgun surgery announcing
  itself, and it is worth naming as one problem rather than four.
- **What has gone stale.** The listing annotates any item whose code has moved,
  been rewritten, or had its file deleted. If it reports any, run
  `boy-scout-verify` to see what can be repaired mechanically, and offer to
  apply it — that closes findings whose file is gone and re-points ones whose
  code merely moved. Items marked as *rewritten* need a person: read the region
  and say whether the finding still holds.
- **The ratio.** The stats line says how much of what was recorded ever got
  fixed. If almost nothing has, the backlog is drifting toward being a
  graveyard, and the honest recommendation is to close items as `wontfix` or
  `stale` rather than to add more.

## 3. Propose the next move

Recommend **two or three specific items**, by id, and say why those. Rank on
what will actually help: severity, how often that file changes, whether several
items cluster in one place, and how contained each fix looks.

Then offer to address them:

> Want me to dispatch a focused agent on each? `/boy-scout-session 3` runs
> them one at a time — each gets its own context, verifies its own change, and
> commits it separately.

Do not start fixing anything from this command. If the user wants a specific
item dealt with right now, point them at `/boy-scout-session <id>`.

Keep the whole response short. This is a status check, not a report.
