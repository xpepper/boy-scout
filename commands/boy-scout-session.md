---
description: Work through the Boy Scout backlog by dispatching a focused agent per item — each one verified and committed on its own.
argument-hint: "[count | item id]"
---

Run a Boy Scout session: address recorded opportunities, one focused agent per
item, so each fix arrives verified and committed on its own.

`$ARGUMENTS` is either a number of items to work through (default **3**), or a
single item id to address on its own.

## 1. Check the ground is safe

Before dispatching anything:

```bash
git status --short
```

A dirty working tree means the agents would commit the user's work-in-progress
along with their fixes. Stop and say so; do not stash it yourself.

Also confirm which branch this is. If it is `main`, `master`, or another
protected branch, ask before proceeding rather than committing to it.

## 2. Pick the items

First clear out anything that no longer describes the code, so no agent is
dispatched at a phantom:

```bash
boy-scout-verify --apply
```

That re-points items whose code merely moved and closes ones whose file is
gone. It deliberately leaves items whose code was *rewritten* open — read those
yourself before choosing them, and close them by hand if the finding no longer
holds:

```bash
boy-scout-resolve --id <id> --outcome stale --note "<why>"
```

Then pick from what is left:

```bash
boy-scout-list --limit 10
```

Choose the requested number, highest severity first, preferring items that are
**contained** — a rename, an extraction, a missing test — over anything that
smells like a design decision. Skip, and say why, for items needing a product
or architecture call: those are for the user, not for an agent working alone.

Show the user the shortlist, with ids, before dispatching.

## 3. Dispatch one agent per item, sequentially

For each chosen item, launch the `boy-scout-refactorer` agent with the item id
and its description. **One at a time — never in parallel.** They share a working
tree and a git index; concurrent agents would interleave their commits and no
one could tell which change belonged to which item.

Wait for each agent to report before starting the next. If one comes back
having abandoned its item, that is a normal outcome: note it and move on to the
next rather than trying to rescue it yourself.

## 4. Report

When the last agent is done, give the user a short account:

- one line per item: id, what happened, the commit subject;
- anything left open, and what would have to be decided to close it;
- anything the agents recorded while they were in there;
- the closing state of the backlog (`boy-scout-list`, stats line included).

Nothing is pushed. Leave the commits for the user to review.
