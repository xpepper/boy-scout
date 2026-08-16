# Boy Scout — Improvement Opportunities

Last reviewed 2026-08-16, on branch `fix/detector-precision`.

The plugin's goal is **opportunistic refactoring**: the thing TDD skills skip,
because they optimise the red-green-refactor loop of the *current* task and keep
no memory of what they noticed along the way.

The capture half is solid, the act-on-it half now exists (focused agents, one per
item), entries no longer quietly stop describing their code, and the static
detectors are no longer reporting mostly noise. What is left falls in two
groups: findings still surface after the cheap moment to act has passed, and
they are ranked by an asserted severity rather than anything measured.

---

## Done

| Was | Now |
|-----|-----|
| Every finding deferred; no fix-it-now path | `now` / `next` / `never` triage, with the four conditions as the gate |
| Distinct file-level findings silently collided | File-level findings identified by description, line-anchored ones by range |
| `SKILL.md` taught types the CLI rejected | One taxonomy, pinned by a test across CLI, schema and skill |
| `dismissed` was the only terminal state | `fixed` / `wontfix` / `stale`, and `boy-scout-list` prints the ratio |
| Items closed by hand-editing the JSONL | `boy-scout-resolve`, through the same lock |
| Nothing turned a recorded item back into a change | `boy-scout-refactorer` agent, `/boy-scout` and `/boy-scout-session` |
| `$CLAUDE_PLUGIN_ROOT` in skill commands (never set in Bash) | `bin/` wrappers on `PATH`, self-locating |
| Skill `name` was not a loadable slug | `record-opportunity`, guarded by a test |
| `wontfix` was re-recorded on the next edit | `wontfix` suppresses re-recording for good |
| `latest_prices.py` and `inspector.py` counted as test files | Test-ness from naming convention and directory |
| Mirrored test trees read as "no tests at all" | Test directories are walked as a fallback |
| Two config keys nothing read | Removed, with a test that every key is read |
| `function_size` silently dead for Elm | Offside-rule sizing for Elm |
| README carried the mechanics | README is the pitch; mechanics in `docs/how-it-works.md` |
| Entries silently stopped describing their code | Anchored at record time; `boy-scout-list` flags drift, `boy-scout-verify --apply` repairs it |
| Install meant symlinking into `~/.claude/plugins` by hand | The repo is its own marketplace: `/plugin marketplace add xpepper/boy-scout` |
| Detectors read prose, layout and builtins as code | Scanning runs on code lines; 57 findings on this repo's own source became 29 |

---

## From running the plugin on its own source

Installed into this repository and pointed at `hooks/`, `scripts/` and `skills/`
with every static detector enabled. The first run gave **57 findings across
~1,500 lines**, the large majority of them false; that ratio was the finding.
Six causes turned out to account for almost all of it, and all six are now
fixed — see the table below and the `fix/detector-precision` commits.

| | Was | Now |
|---|-----|-----|
| D1 | `str2?` in `ABBREVIATION_RE` made every `Dict[str, str]` a naming finding, in all eleven source files | `str` is gone from the list |
| D1b | The scan ran on raw line text, so `tmp` in a log message or a trailing comment counted | `code_lines` yields the code part of the lines that carry code, docstrings and template literals included |
| D2 | The overlap check never compared the two halves of a pair to each other, so a table literal matched itself shifted one line down | A pair must be disjoint, and extension stops before the halves meet |
| D3 | `normalize_line` masks strings, so two runs of prose or two table entries were indistinguishable | Windows of nothing but masked literals are not indexed; a string prefix counts as part of the literal |
| D4 | `test_post-tool-use.py` was looked for and never found, because Python module names cannot carry hyphens | Hyphens and underscores are interchangeable in the stem; empty files are exempt |
| D5 | `end_lineno - lineno` counted the docstring, blank lines and comments, and fired on 20 of ~60 functions | Python size is the count of code lines in the range; the finding says which unit it measured |

Verified separately, and working: `bin/` really is on `PATH` in a live session,
`boy-scout-record` runs by bare name from the skill, the entry lands anchored,
and the Stop hook fires and writes its timestamp.

### What the same scan reports now

**29 findings**, and the shape of them is different:

- **duplication: 1**, down from 8, and it is real — the two branches of
  `detect_naming_clarity` still rhyme after the finding builder was extracted.
  Real but not worth acting on is exactly what `wontfix` is for.
- **test_coverage: 0**, down from 4. The one true positive it found —
  `pattern_analyzer.py` had no test file of its own — was closed by writing
  `tests/test_pattern_analyzer.py`, which immediately surfaced a bug of its own.
- **naming: 11**, down from 23. What is left is `p = Path(...)` bindings and a
  handful of bare `d`, `h`, `m`, `idx` — weak names, fairly flagged.
- **function_size: 17**, down from 22, and now measuring code rather than
  layout. These are functions of 21–75 code lines against a threshold of 20.
  Whether 20 is the right default for Python is a tuning question, not a bug.

### D6. `record-opportunity` costs ~330 tokens of every session

`claude plugin details` puts the plugin's always-on cost at ~792 tokens, ~330 of
which is the `record-opportunity` description — it is long because it lists
trigger phrases, and that length is what makes the skill fire at the right
moments. Worth knowing and worth watching; not obviously worth cutting.

---

## Open, roughly by leverage

### 1. Just-in-time surfacing

The Stop hook reports *after* the moment acting was cheap. A `PreToolUse` hook
that sees Claude about to edit `src/billing/invoice.py` and injects "2 open Boy
Scout items in this file" turns a passive backlog into in-the-moment context —
which is what makes a refactoring *opportunistic* rather than *scheduled*.

`boy-scout-list --file <path>` already exists and is the whole data layer this
needs. The open question is noise: it fires on every edit, so it wants a
per-session dedup and probably a severity floor.

### 2. Anchors do not follow a file that was renamed

`git mv src/auth.py src/authentication.py` and every entry about that file
reports `missing`, then gets closed as stale by `boy-scout-verify --apply` —
even though the code, and the finding, are both perfectly alive.

The fix is the same fingerprint machinery, widened: before declaring a file
gone, ask git whether it was renamed (`git log --diff-filter=R --name-status`),
or search the repository for the fingerprint. Until then, `--apply` on a branch
that renamed files will close entries it should have re-pointed.

### 3. Git history is free prioritisation signal, still unused

Behavioural code analysis (Tornhill): rank by *change frequency × complexity*,
not complexity alone. Available today at zero infrastructure cost:

- `git log --format= --name-only | sort | uniq -c` → churn per file, for hotspot
  ranking and for a severity that means something.
- Files that repeatedly change *together* but live apart → hidden coupling that
  no single-file detector can ever see.
- `git blame` age on a flagged region → fresh code (cheap to fix) versus
  decade-old code (riskier).
- Whether the region is inside the current branch's diff → the strongest
  possible "you are already standing here" signal for the `now` gate.

### 4. Severity is asserted, never derived

`--severity` is Claude's unanchored judgment, and the static detectors hardcode
`medium`/`low` by line count. Nothing incorporates blast radius, churn, or
whether anything depends on the code. Two items marked `high` are not
comparable, which makes "address the highest-severity items" close to arbitrary.
Depends on 3.

### 5. Detectors re-scan the whole file, not the changed region

The PostToolUse hook runs every enabled detector over the entire file on every
edit, so Claude gets flagged for code it never touched. Deduplication hides the
repetition but not the mismatch: an opportunistic refactoring plugin should
weight what is in the current diff. `git diff` on the touched file would bound
it.

### 6. The scheduled runner still holds a blank cheque

`boy_scout_session.py` runs `claude -p --allowedTools Read,Edit,Write,Bash`
unattended. The prompt now demands a green baseline, a clean tree, and backing
out rather than pushing through — but nothing *enforces* any of that, and
nothing bounds diff size or files touched. The job is: run tests, `git add`,
`git commit`. That is an allowlist, not `Bash`.

It also runs the work inline rather than through `boy-scout-refactorer`, so the
contract exists in two places and can drift. Sharing one source would be better
than keeping them in sync by hand.

### 7. Smaller things

- **Duplication matching is case-insensitive.** `normalize_line` lowercases, so
  two blocks differing only in case read as copies.
- **The hook matches `Write|Edit` only.** Other edit-shaped tools go unseen.
- **Duplication still reads inside multi-line strings.** `significant_lines`
  predates `code_lines` and does not track them, so two runs of prose inside one
  triple-quoted block can still match. The literal-only rule catches the
  adjacent-string shape; this one it does not. Reusing `code_lines` would fix
  it, at the cost of never seeing duplicated SQL in two heredocs.
- **`function_size` measures two different things.** Python counts lines of
  code; the other languages count the lines a declaration spans, because there
  is no AST to lean on. The finding says which, but one `max_func_lines`
  threshold is being compared against both.
- **Shared or personal?** `.gitignore` excludes the backlog, making it private
  by default — but the concept works better as a *team* refactoring backlog, and
  JSONL-append conflicts resolve trivially (union merge via `.gitattributes`).
  That is a product decision currently made silently by one `.gitignore` line.

---

## Suggested sequencing

1. **Just-in-time surfacing (1)** — largest behaviour change for the least new
   machinery, and the data layer is already built.
2. **Renames (2)** — small, and it stops `--apply` closing entries it should
   have re-pointed.
3. **Git signal (3), then derived severity (4)** — together they make the
   backlog rankable rather than merely sorted.
4. **Runner safety (6)** before anyone is encouraged to cron this.
5. **(5) and (7)** are independent and can land at any time.
