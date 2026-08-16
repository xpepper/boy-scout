# How it works

One channel feeds the backlog, and one command drains it.

```
During your task                    End of session
─────────────────                   ──────────────
Claude notices something            Claude finishes responding
       │                                    │
       ▼                                    ▼
record-opportunity triages it       Stop hook fires
  now / next / never                        │
       │                                    ▼
       ▼                            Reads new items since last run
`now`  → fixed here, own commit             │
`next` → .claude/boy-scout-                 ▼
          todos.jsonl              Injects a summary into Claude's
`never`→ dropped, silently         context via systemMessage
                                   (inform-only, doesn't block)
```

## Recording: what Claude noticed

Claude records opportunities through the `record-opportunity` skill,
proactively, while doing something else. This captures what only having done
the work reveals: a refactor step skipped to keep a change small, three files
read to answer one question, a compromise made deliberately in this very diff.

Each observation is triaged into `now`, `next` or `never`. Most become `next`.
A small, obvious, uncontroversial fix in a file Claude is **already editing**
is done `now`, on green, as its own commit — that is the actual Boy Scout Rule,
rather than filing a report about the litter. The full gate, and the rules an
on-the-spot fix has to obey, are in
[`skills/record-opportunity/SKILL.md`](../skills/record-opportunity/SKILL.md).

### Why there is no static analysis here

Earlier versions ran detectors on every file write — duplication by line
hashing, naming by regex, function size by line count. That channel is gone.

It produced what a linter produces, and the skill's own `never` rule says to
drop "a restatement of what the project's linter or type checker already
reports". So the plugin was recording exactly what it told itself not to.
Worse, it competed on ground it could never win: ruff, clippy, ESLint and
jscpd have years of tuning, per-rule configuration, autofix and editor
integration behind them.

A precision pass fixed six real bugs in those detectors and cut false
positives on this repository's own source from 57 to 29. What survived was
`p = Path(...)` and "this function is 21 lines" — rules you would disable in
ruff. That measurement is why the channel was removed rather than tuned
further.

The signal that is genuinely unavailable to a linter is what an agent knows
from having done the work, and that is what is left.

## Surfacing: the Stop hook

The Stop hook fires whenever Claude finishes a response and hands control back
to you — not when you close the terminal, so there is nothing to trigger by
hand. When items have piled up since the last summary, the reply ends with:

```
🏕️  Boy Scout report: 4 new refactoring opportunities detected.

  🔴 [Self-inflicted debt] src/billing/invoice.py: inlined the tax lookup rather than
     threading `rates` through three call sites, to keep this diff reviewable
  🟡 [Comprehension cost]  src/auth/session.rs: read Session, TokenStore and Clock to
     find out what refresh() returns on expiry — the answer is in none of them
  🟡 [Skipped refactor]    src/pipeline/process.ts: green without step 5; parseBody and
     parseHeaders ended up the same function with different names
  🟢 [Test smell]          tests/test_orders.py: passes alone, fails after test_refunds —
     shared module-level fixture

💡 /boy-scout to review the backlog · /boy-scout-session to have a focused
   agent address items one at a time, each verified and committed on its own.
```

Once the open backlog reaches `session.triage_threshold` (default 20), the
summary gains a nudge to triage it before it stops being trustworthy.

## Draining: focused agents

`/boy-scout-session` picks the top items, then dispatches one
`boy-scout-refactorer` agent per item, **sequentially** — they share a working
tree and a git index, so parallel agents would interleave their commits.

Each agent works on exactly one item:

1. Refuses to start unless the suite is green and the tree is clean, so
   "the tests pass" afterwards actually means something.
2. Makes the change test-first, keeping inside the region the item describes.
3. Abandons and reverts if it stops being small — a design decision appears,
   it spreads past about three files, or verification fails.
4. Commits on its own, closes the entry with an outcome, never pushes.

An abandoned item is a normal outcome. An opportunistic refactoring that has
stopped being small has already cost more than it was worth.

## Staying true: anchors

An entry recorded against `auth.rs:88-104` still says that two commits later,
when those lines are something else. So each entry stores a fingerprint of the
code it points at, and every read re-checks it: the code is unchanged, it moved
(and where to), it was rewritten, or the file is gone.

`boy-scout-verify` repairs the two cases that need no judgment — re-pointing
what moved, closing what has no file left. Rewritten code is reported and left
open on purpose: a rewrite can leave the original smell exactly where it was, so
closing on a fingerprint miss would quietly delete real findings.

## The backlog itself

Everything lands in `.claude/boy-scout-todos.jsonl`. Read it with
`boy-scout-list`, repair it with `boy-scout-verify`, close items with
`boy-scout-resolve`, and never edit it by hand — see [storage.md](storage.md)
for why, and for the entry shape.
