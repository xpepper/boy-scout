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

Apply the Boy Scout Rule — *leave every piece of code a little better than you found it* —
without derailing the current task. When Claude notices an improvement opportunity during
normal work (editing, reviewing, implementing), record it immediately so it can be
addressed in a dedicated Boy Scout session later.

This skill complements the passive hook-based detection: hooks catch structural issues
via static analysis; this skill captures the semantic opportunities that only contextual
understanding reveals.

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

Having noticed something, the next question is *when* to act on it — see **Triage**.

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
  "position": 4,
  "message": "Recorded opportunity #4: [duplication] src/routes/auth.rs — ..."
}
```

The opportunity is appended to `.claude/boy-scout-todos.jsonl` in the project's
`.claude/` directory. It will appear in the Boy Scout session summary at the
end of the current Claude session.

## Tone in the Transcript

After running the script, add a brief inline note in the current response — one line,
no interruption to the main flow:

> *(Boy Scout: noted duplication in `src/routes/auth.rs:88-104` for later.)*

Then continue with the original task.

## What Not to Record

- Issues already present in `.claude/boy-scout-todos.jsonl` (avoid duplicates)
- Opportunities in generated code, vendored dependencies, or build artifacts
- Style preferences without objective impact (formatting, brace style)
- Issues the current task is already fixing
