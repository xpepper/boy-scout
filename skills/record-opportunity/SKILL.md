---
name: Record Boy Scout Opportunity
description: >
  This skill should be used proactively—without waiting for the user to ask—whenever
  Claude notices a refactoring opportunity, code smell, or improvement while working
  on any task. Trigger on observations like "this function is getting long",
  "this logic appears to be duplicated elsewhere", "this variable name doesn't
  reveal its intent", "there's no test for this module", or "this abstraction
  is doing too much". The skill records the opportunity silently without
  interrupting the current task, so Claude can stay focused while nothing goes
  unnoticed.
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

Record an opportunity whenever noticing **any** of the following while doing other work:

- **Duplication**: Two blocks of logic that do the same thing, even if named differently
- **Complexity**: A function juggling multiple responsibilities, or too long to read at a glance
- **Naming**: An identifier that doesn't reveal its intent (single letters, abbreviations, misleading names)
- **Missing tests**: Production code that was touched but has no corresponding test
- **Wrong abstraction**: An interface or type that leaks implementation details or mixes concerns
- **Dead code**: Commented-out blocks, unused imports, unreachable branches
- **Custom**: Any other improvement worth revisiting

Do **not** stop the current task to fix the issue. Record and continue.

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
| `--type` | ✅ | `duplication`, `function_size`, `naming`, `test_coverage`, `custom` | Pick the closest category |
| `--file` | ✅ | string | Relative to project root |
| `--description` | ✅ | string | Explain *what* the issue is and *why* it matters |
| `--severity` | ✅ | `low`, `medium`, `high` | See severity guide below |
| `--lines` | optional | `42` or `42-58` | Omit for file-level issues |
| `--context` | optional | string | Suggest an approach or name a pattern |

### Severity Guide

| Severity | Use when… |
|----------|-----------|
| `high` | The issue actively hinders understanding or is likely to cause bugs |
| `medium` | The issue adds friction; addressing it would clearly improve the code |
| `low` | Minor polish — nice to have but not urgent |

## Examples

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
