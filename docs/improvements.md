# Boy Scout — Improvement Opportunities

Last reviewed 2026-08-16, on branch `feat/remove-static-detectors`.

The plugin's goal is **opportunistic refactoring**: the thing TDD skills skip,
because they optimise the red-green-refactor loop of the *current* task and keep
no memory of what they noticed along the way.

The capture half is solid, the act-on-it half exists (focused agents, one per
item), entries no longer quietly stop describing their code, and the plugin now
does one thing instead of one thing plus a worse linter. What is left falls in
two groups: findings still surface after the cheap moment to act has passed,
and they are ranked by an asserted severity rather than anything measured.

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
| Detectors read prose, layout and builtins as code | Scanning ran on code lines; 57 findings on this repo's own source became 29 |
| The plugin shipped its own worse linter | Static detection removed; `record-opportunity` is the only channel |

---

## The static detectors, and why they are gone

Kept here because it is the most useful thing this document records: an
experiment that was run properly and then acted on.

Installed into this repository and pointed at `hooks/`, `scripts/` and `skills/`
with every static detector enabled. The first run gave **57 findings across
~1,500 lines**, the large majority of them false; that ratio was the finding.
Six causes accounted for almost all of it, and all six were fixed (#11).

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

### What the fixed detectors reported, and what that settled

**29 findings**, down from 57:

- **duplication: 1**, from 8, and real — the two branches of
  `detect_naming_clarity` still rhymed after the finding builder was extracted.
- **test_coverage: 0**, from 4. Its one true positive — `pattern_analyzer.py`
  had no test file — was closed by writing one, which surfaced a bug of its own.
- **naming: 11**, from 23. What survived was `p = Path(...)` and a handful of
  bare `d`, `h`, `m`, `idx`.
- **function_size: 17**, from 22, now measuring code rather than layout:
  functions of 21–75 code lines against a threshold of 20.

That last list is the argument for removal. `p = Path(...)` and "this function
is 21 lines" are rules you *disable* in ruff, and the detectors had no per-rule
config, no autofix and no editor integration to make them worth the friction.

The sharper point is that the plugin's own skill says to drop these on sight.
`SKILL.md` lists under `never`: "a restatement of what the project's linter or
type checker already reports". The hook produced nothing else. Two channels
were disagreeing about what belongs in the backlog, and the inferential one had
the better argument — it is the only one that can see a compromise made in this
very diff, which no static analyser can ever recover because the evidence was
never written to disk.

Removed in `feat/remove-static-detectors`: ~1,500 lines, the `detection` config
section, and the PostToolUse hook.

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
  is invisible to anything reading one file at a time, linters included.
- `git blame` age on a recorded region → fresh code (cheap to fix) versus
  decade-old code (riskier).
- Whether the region is inside the current branch's diff → the strongest
  possible "you are already standing here" signal for the `now` gate.

### 4. Severity is asserted, never derived

`--severity` is Claude's unanchored judgment on a three-point scale, applied
once, at the moment of noticing. Nothing incorporates blast radius, churn, or
whether anything depends on the code. Two items marked `high` are not
comparable, which makes "address the highest-severity items" close to
arbitrary. Depends on 3, which is the only source of evidence available.

### 5. The scheduled runner still holds a blank cheque

`boy_scout_session.py` runs `claude -p --allowedTools Read,Edit,Write,Bash`
unattended. The prompt now demands a green baseline, a clean tree, and backing
out rather than pushing through — but nothing *enforces* any of that, and
nothing bounds diff size or files touched. The job is: run tests, `git add`,
`git commit`. That is an allowlist, not `Bash`.

It also runs the work inline rather than through `boy-scout-refactorer`, so the
contract exists in two places and can drift. Sharing one source would be better
than keeping them in sync by hand.

### 6. Smaller things

- **Anchor fingerprints are case-insensitive.** `normalize_line` lowercases, so
  a rename that only changes case reads as no change at all and the anchor
  stays `current`. Inherited from the duplication detector, where masking
  aggressively was the point; for anchors it is a small blind spot.
- **Nothing prunes closed entries.** The JSONL grows forever, and every read
  walks all of it. Fine at hundreds, not at tens of thousands.
- **Shared or personal?** `.gitignore` excludes the backlog, making it private
  by default — but the concept works better as a *team* refactoring backlog, and
  JSONL-append conflicts resolve trivially (union merge via `.gitattributes`).
  That is a product decision currently made silently by one `.gitignore` line.

---

## Suggested sequencing

1. **Just-in-time surfacing (1)** — largest behaviour change for the least new
   machinery, the data layer is already built, and with the detectors gone it is
   the only thing left that makes a refactoring *opportunistic* rather than
   merely *recorded*.
2. **Renames (2)** — small, and it stops `--apply` closing entries it should
   have re-pointed.
3. **Git signal (3), then derived severity (4)** — together they make the
   backlog rankable rather than merely sorted. Worth noting that (3) is the one
   deterministic signal that survives the removal on principle: churn,
   co-change and blame age are not in the source text, so no linter competes
   for them.
4. **Runner safety (5)** before anyone is encouraged to cron this.
5. **(6)** is independent and can land at any time.
