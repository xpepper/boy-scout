# How it works

Two channels feed one backlog, and one command drains it.

```
During your task                    End of session
─────────────────                   ──────────────
Write / Edit a file                 Claude finishes responding
       │                                    │
       ▼                                    ▼
PostToolUse hook fires              Stop hook fires
       │                                    │
       ▼                                    ▼
Detectors run on the file           Reads new items since last run
       │                                    │
       ▼                                    ▼
Findings → .claude/boy-scout-       Injects a summary into Claude's
           todos.jsonl              context via systemMessage
           (silent, no transcript)  (inform-only, doesn't block)
```

## Channel 1: what Claude noticed (the primary one)

Claude records semantic opportunities through the `record-opportunity` skill,
proactively, while doing something else. This is the channel that matters,
because it captures what only having done the work reveals: a refactor step
skipped to keep a change small, three files read to answer one question, a
compromise made deliberately in this very diff.

Each observation is triaged into `now`, `next` or `never`. Most become `next`.
A small, obvious, uncontroversial fix in a file Claude is **already editing**
is done `now`, on green, as its own commit — that is the actual Boy Scout Rule,
rather than filing a report about the litter. The full gate, and the rules an
on-the-spot fix has to obey, are in
[`skills/record-opportunity/SKILL.md`](../skills/record-opportunity/SKILL.md).

## Channel 2: what the static detectors found (opt-in)

Mechanical proxies — line counts and regexes — that trade precision for recall.
They are disabled by default; see [configuration.md](configuration.md) to turn
one on.

| Detector | What it finds | Languages |
|----------|--------------|-----------|
| `duplication` | Copy-pasted blocks (≥6 lines by default) | Any file the hook reads |
| `naming` | Single-char identifiers, cryptic abbreviations | Rust, Elm, JS/TS, Python, Go |
| `test_coverage` | Source file changed but no test file found | Rust, Elm, JS/TS, Python, Go, Ruby, Java, Kotlin, Swift |
| `function_size` | Functions exceeding the line threshold | Python, Elm, Rust, JS/TS, Go |

## Surfacing: the Stop hook

The Stop hook fires whenever Claude finishes a response and hands control back
to you — not when you close the terminal, so there is nothing to trigger by
hand. When items have piled up since the last summary, the reply ends with:

```
🏕️  Boy Scout report: 4 new refactoring opportunities detected.

  🟡 [Duplication] src/routes/auth.rs: Duplicated block (17 lines): lines 88–104 and 45–61
  🟢 [Naming]      src/pipeline/process.ts: Abbreviated identifier 'tmp' …
  🟡 [No tests]    src/billing/invoice.py: No test file found for invoice.py …
  🟢 [Long function] src/compiler/lower.ts: Function 'lowerExpr' spans 80 lines …

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
