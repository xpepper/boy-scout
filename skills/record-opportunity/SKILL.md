---
name: Record Boy Scout Opportunity
description: >
  This skill should be used proactively, without waiting for the user to ask, whenever
  Claude notices a refactoring opportunity, code smell, or improvement while working
  on any task. Trigger hardest on observations only an agent doing the work can make:
  "tests are green but I skipped the refactor step", "I had to read three files to
  work out what this returns", "I inlined this instead of threading the parameter
  through, to keep the diff small", "this test is slow / order-dependent / mocks
  everything", "I've now worked around this same region twice". Also trigger on
  "this function is getting long", "this logic is duplicated elsewhere", "this name
  doesn't reveal its intent", "there's no test for this module", "this abstraction
  is doing too much". The skill triages each observation into fix-it-now, record-for-later,
  or drop-it, so small safe cleanups happen while Claude is standing there and
  everything else is recorded without derailing the current task.
version: 0.1.0
---

# Record Boy Scout Opportunity

## Purpose

Apply the Boy Scout Rule — *leave the campground cleaner than you found it* — while
staying on the task at hand.

The rule is about fixing the small thing **while you are standing there**. Deferring
everything to a list is the failure mode the rule exists to prevent: a backlog nobody
works through is worse than no backlog, because it looks like progress. But stopping a
task to rename a variable is worse still.

So this skill does two things, in this order:

1. **Triage** the observation — `now`, `next`, or `never`.
2. **Act**: make the fix (rare), record it for later (usual), or drop it.

It complements the passive hook-based detection: hooks catch structural issues via
static analysis; this skill captures what only having done the work reveals.

## When to Trigger

### The signals worth reaching for first

These come from **having done the work**. A linter cannot see any of them, and
neither can a reviewer reading the finished diff — the evidence exists only in
the working session that just happened. They are the most valuable thing this
skill can capture, so check for them before reaching for the generic categories
below.

- **Skipped refactor step** (`skipped_refactor`): The TDD loop reached green and moved
  on without step 5. Trigger the moment tests pass and the thought *"this works, but
  I'd have written it differently with more time"* appears. Say what the refactor would be.
- **Comprehension cost** (`comprehension_cost`): Understanding something cost more than
  it should — several files opened to answer one question, a name that had to be
  checked against its definition, control flow that needed re-reading. Record *what
  you had to do to understand it*, because that is the measurement: "had to read
  `Session`, `TokenStore` and `Clock` to find out what `refresh()` returns on expiry".
- **Self-inflicted debt** (`self_inflicted_debt`): A compromise made in *this* task —
  inlining instead of threading a parameter through, copying a helper to keep the
  diff small, widening a type to avoid a cascade, a `TODO` left in the code. Nothing
  else in the ecosystem can record this, because nobody else knows a choice was made.
  Record it at the moment of the compromise, and say what the uncompromised version is.
- **Test smell** (`test_smell`): A test that is slow, order-dependent, over-mocked,
  coupled to implementation detail rather than behaviour, or that fails for reasons
  unrelated to what it names. Usually noticed *while running the suite*, which is
  precisely when it can be recorded.
- **Repeated friction** (`repeated_friction`): The same region worked around again —
  this session, or in a previous one. Before recording, check the existing backlog
  for entries on the same file: a second or third finding in one region is shotgun
  surgery announcing itself, and is worth more than any of the findings alone.

### The generic categories

Static analysis and code-review skills cover these too, so record them when the
observation is genuinely yours and specific — not as a restatement of what a
linter already reports.

- **Duplication** (`duplication`): Two blocks of logic that do the same thing, even if named differently
- **Complexity** (`function_size`): A function juggling multiple responsibilities, or too long to read at a glance
- **Naming** (`naming`): An identifier that doesn't reveal its intent (single letters, abbreviations, misleading names)
- **Missing tests** (`test_coverage`): Production code that was touched but has no corresponding test
- **Wrong abstraction** (`wrong_abstraction`): An interface or type that leaks implementation details or mixes concerns
- **Dead code** (`dead_code`): Commented-out blocks, unused imports, unreachable branches
- **Custom** (`custom`): Any other improvement worth revisiting

Having noticed something, the next question is *when* to act on it.

## Triage: `now`, `next`, `never`

Every observation gets exactly one of three decisions. Make the decision explicitly —
do not let "record it" be the automatic answer.

### `now` — fix it while standing here

Choose `now` only when **all four** of these hold:

1. **You are already editing this file** in the current task.
2. The fix is **small, obvious and mechanically safe** — a rename, an unused import,
   a dead branch, an extracted local, a misleading comment.
3. It **does not meaningfully expand the diff** or the review surface.
4. It is **uncontroversial** — no judgment call a reviewer might disagree with.

Condition 1 is **non-negotiable and decides most cases**. If the current task is not
already modifying that file, the answer is never `now` — not even for a one-word
rename, not even if the file is open in context because it was read. "I am standing
here" means "this file is in my diff".

**When in doubt, choose `next`.** Deferring too much is a cost the user can see and
work through; hijacking their task to clean something up is a cost they cannot. If
the four conditions require any argument at all to satisfy, they are not satisfied.

Then follow **The `now` Path** below.

### `next` — record it and carry on

The default, and where the large majority of observations belong. Everything real
that isn't a `now`: anything in a file this task isn't touching, anything needing a
design decision, anything bigger than a few lines, anything a reviewer might want to
discuss.

Record it with `record.py` (see **How to Record**) and continue the task. Do **not**
stop the current work to fix it.

### `never` — don't carry it at all

Not everything noticed is worth a line in a backlog. A backlog full of items nobody
will ever action is exactly the graveyard this skill exists to avoid, and each entry
costs attention on every future read. Drop it silently — no record, no transcript
note — when it is:

- In generated code, vendored dependencies, or build artifacts
- A style preference with no objective impact (formatting, brace style, import order)
- Something the current task is already fixing
- Already recorded in `.claude/boy-scout-todos.jsonl` (the recorder deduplicates, but
  a near-duplicate reworded slightly will get through — check first)
- A restatement of what the project's linter or type checker already reports
- Speculative ("this might need to scale one day") rather than observed

If an item **already in the backlog** turns out to be one of these, close it rather
than leaving it to rot — see **Closing an Item Already Recorded**.

## The `now` Path

A `now` fix is a real refactoring, so it obeys the same rules as any other one.

1. **Only on green.** Finish and verify the current behavioural change first. Never
   interrupt a red-green cycle to clean something up — a failing test must fail for
   one reason at a time.
2. **Make the fix.**
3. **Hard stop if it grows.** If the fix turns out not to be small once started — it
   touches a second file, needs a test change, or you find yourself making a judgment
   call — `git checkout` the cleanup, record it as `next`, and move on. This is the
   main failure mode of the `now` path, and abandoning is always the right call.
   Backing out is not a failure; it is the gate working late.
4. **Re-verify.** Run the relevant tests again. If they fail, **revert the fix** and
   record it as `next` instead. Do not debug an opportunistic cleanup; it has already
   cost more than it was worth.
5. **Commit it separately**, never folded into the feature commit:

   ```
   refactor(billing): rename tmp to pending_invoice
   ```

   Its own commit keeps the feature diff clean and keeps the cleanup independently
   revertable. If the current work isn't being committed at all, leave the fix in the
   working tree — but keep it a separate, described change.
6. **Record it, marked fixed.** An on-the-spot fix is still recorded: what got
   recorded versus what got resolved is how this plugin knows whether it is working,
   and `now` fixes are the only entries on the good side of that ratio.

   ```bash
   python3 "$CLAUDE_PLUGIN_ROOT/skills/record-opportunity/record.py" \
     --type naming \
     --file src/billing/invoice.py \
     --lines 34 \
     --description "tmp held a validated PendingInvoice; renamed to pending_invoice" \
     --severity low \
     --outcome fixed
   ```

   If the backlog already had an entry for this issue, `--outcome fixed` closes that
   entry instead of adding a second one.
7. **One line in the transcript**, in the same understated tone as a deferral:

   > *(Boy Scout: renamed `tmp` to `pending_invoice` while here.)*

   Not a section, not a list, not a celebration. Then continue the original task.

## How to Record

Run the `record.py` script via Bash, filling in the appropriate arguments:

```bash
python3 "$CLAUDE_PLUGIN_ROOT/skills/record-opportunity/record.py" \
  --type      <type>         \
  --file      <relative/path/to/file.rs> \
  --description "<intent-revealing description>" \
  --severity  <low|medium|high> \
  [--lines    <start>-<end>]  \
  [--context  "<suggested approach>"]
```

### Arguments

| Argument | Required | Values | Notes |
|----------|----------|--------|-------|
| `--type` | ✅ | `skipped_refactor`, `comprehension_cost`, `self_inflicted_debt`, `test_smell`, `repeated_friction`, `duplication`, `function_size`, `naming`, `test_coverage`, `dead_code`, `wrong_abstraction`, `custom` | Pick the closest category |
| `--file` | ✅ | string | Relative to project root |
| `--description` | ✅ | string | Explain *what* the issue is and *why* it matters |
| `--severity` | ✅ | `low`, `medium`, `high` | See severity guide below |
| `--lines` | optional | `42` or `42-58` | Omit for file-level issues |
| `--context` | optional | string | Suggest an approach or name a pattern |
| `--outcome` | optional | `fixed`, `wontfix`, `stale` | Closes the item immediately — see **Triage: now** |
| `--note` | optional | string | Why it ended that way |

### Severity Guide

| Severity | Use when… |
|----------|-----------|
| `high` | The issue actively hinders understanding or is likely to cause bugs |
| `medium` | The issue adds friction; addressing it would clearly improve the code |
| `low` | Minor polish — nice to have but not urgent |

## Examples

**Reached green, skipped the refactor:**
```bash
python3 "$CLAUDE_PLUGIN_ROOT/skills/record-opportunity/record.py" \
  --type skipped_refactor \
  --file src/billing/invoice.py \
  --lines 120-165 \
  --description "apply_discount() passed its new test as a fourth branch in the same if-chain; the chain wants to be a strategy lookup but the change was already large" \
  --severity medium \
  --context "Replace the if-chain with a DISCOUNT_RULES dict keyed by discount kind"
```

**Understanding it cost too much:**
```bash
python3 "$CLAUDE_PLUGIN_ROOT/skills/record-opportunity/record.py" \
  --type comprehension_cost \
  --file src/auth/session.rs \
  --lines 44-70 \
  --description "Had to read session.rs, token_store.rs and clock.rs to find out that refresh() returns None on an expired token rather than an error" \
  --severity high \
  --context "Return an explicit Result<Token, SessionExpired> so the outcome is readable at the call site"
```

**A compromise made in this task:**
```bash
python3 "$CLAUDE_PLUGIN_ROOT/skills/record-opportunity/record.py" \
  --type self_inflicted_debt \
  --file src/report/render.ts \
  --lines 88 \
  --description "Read the locale from the module-level config instead of threading it through renderRow(), to keep this diff to one file" \
  --severity medium \
  --context "Thread locale from buildReport() down to renderRow() and drop the module-level read"
```

**A test that is a problem in itself:**
```bash
python3 "$CLAUDE_PLUGIN_ROOT/skills/record-opportunity/record.py" \
  --type test_smell \
  --file tests/test_checkout.py \
  --lines 30-95 \
  --description "test_checkout_flow mocks the repository, the clock and the mailer, so it asserts on call order rather than on the order being placed; it passes when the behaviour is wrong" \
  --severity high \
  --context "Use a real in-memory repository and a fixed clock; assert on the resulting order"
```

**The same region, again:**
```bash
python3 "$CLAUDE_PLUGIN_ROOT/skills/record-opportunity/record.py" \
  --type repeated_friction \
  --file src/api/handlers.go \
  --description "Third session in a row that adding an endpoint required editing this file plus routes.go plus errors.go in lockstep" \
  --severity high \
  --context "The three files share one concept; consider a per-endpoint module that owns its route, handler and errors"
```

**Duplicated parsing logic:**
```bash
python3 "$CLAUDE_PLUGIN_ROOT/skills/record-opportunity/record.py" \
  --type duplication \
  --file src/routes/auth.rs \
  --lines 88-104 \
  --description "JSON body parsing logic duplicated from src/routes/users.rs:45-61" \
  --severity medium \
  --context "Extract to a shared parse_json_body<T>() helper in src/util/http.rs"
```

**Function doing too much:**
```bash
python3 "$CLAUDE_PLUGIN_ROOT/skills/record-opportunity/record.py" \
  --type function_size \
  --file src/compiler/lower.elm \
  --lines 200-280 \
  --description "lowerExpr handles literals, lambdas, and let-bindings in a single 80-line match" \
  --severity medium \
  --context "Split into lowerLiteral, lowerLambda, lowerLet following the existing pattern"
```

**Misleading name:**
```bash
python3 "$CLAUDE_PLUGIN_ROOT/skills/record-opportunity/record.py" \
  --type naming \
  --file src/pipeline/process.ts \
  --lines 34 \
  --description "Variable 'data' holds a validated UserProfile, not raw data — rename to userProfile" \
  --severity low
```

**Missing tests:**
```bash
python3 "$CLAUDE_PLUGIN_ROOT/skills/record-opportunity/record.py" \
  --type test_coverage \
  --file src/billing/invoice.py \
  --description "Invoice.apply_discount() has no tests; edge cases around negative discounts are untested" \
  --severity high
```

**Leaky abstraction:**
```bash
python3 "$CLAUDE_PLUGIN_ROOT/skills/record-opportunity/record.py" \
  --type wrong_abstraction \
  --file src/storage/repo.rs \
  --lines 12-40 \
  --description "UserRepo returns raw SQL rows, so callers depend on the schema" \
  --severity high \
  --context "Map rows to a User domain type at the repo boundary"
```

**Dead code:**
```bash
python3 "$CLAUDE_PLUGIN_ROOT/skills/record-opportunity/record.py" \
  --type dead_code \
  --file src/legacy/parser.js \
  --description "Commented-out v1 parser left below the v2 implementation" \
  --severity low
```

## Output

On success, the script prints a confirmation JSON and exits 0:

```json
{
  "id": "a3f9c12e",
  "is_new": true,
  "outcome": null,
  "position": 4,
  "message": "Recorded opportunity #4: [duplication] src/routes/auth.rs — ..."
}
```

The opportunity is appended to `.claude/boy-scout-todos.jsonl` in the project's
`.claude/` directory. Open items appear in the Boy Scout summary at the end of the
current Claude session; items closed with an outcome do not.

## Closing an Item Already Recorded

When an earlier opportunity is dealt with — fixed during a Boy Scout session, decided
against, or overtaken by events — close it by id:

```bash
python3 "$CLAUDE_PLUGIN_ROOT/skills/record-opportunity/resolve.py" \
  --id a3f9c12e \
  --outcome fixed \
  [--note "Extracted parse_json_body(); suite green"]
```

| Outcome | Use when… |
|---------|-----------|
| `fixed` | The code was changed and the change was verified |
| `wontfix` | A real observation the project has decided not to act on (say why in `--note`) |
| `stale` | It no longer applies — the code moved on, or the finding was wrong |

Always close items with this script. Never hand-edit
`.claude/boy-scout-todos.jsonl`: hooks append to it under a file lock that an editor
does not respect, so an edit can silently drop a concurrently recorded item.

## Tone in the Transcript

After running the script, add a brief inline note in the current response — one line,
no interruption to the main flow:

> *(Boy Scout: noted duplication in `src/routes/auth.rs:88-104` for later.)*

For a `now` fix, the same understatement, in the past tense:

> *(Boy Scout: renamed `tmp` to `pending_invoice` while here.)*

One line either way. Then continue with the original task.
