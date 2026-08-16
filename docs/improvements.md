# Boy Scout — Improvement Opportunities

Last reviewed 2026-08-16, on branch `feat/install-and-dogfood`.

The plugin's goal is **opportunistic refactoring**: the thing TDD skills skip,
because they optimise the red-green-refactor loop of the *current* task and keep
no memory of what they noticed along the way.

The capture half is solid, the act-on-it half now exists (focused agents, one per
item), and entries no longer quietly stop describing their code. What is left
falls in three groups: the static detectors are too noisy to recommend turning
on, findings still surface after the cheap moment to act has passed, and they
are ranked by an asserted severity rather than anything measured.

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

---

## From running the plugin on its own source

Installed into this repository and pointed at `hooks/`, `scripts/` and
`skills/` with every static detector enabled: **57 findings across ~1,500 lines**,
the large majority of them false. That ratio is the finding. The causes below
are what a user turning `patterns` on for the first time would actually meet,
and they are why the detectors are still opt-in.

Verified separately, and working: `bin/` really is on `PATH` in a live session,
`boy-scout-record` runs by bare name from the skill, the entry lands anchored,
and the Stop hook fires and writes its timestamp.

### D1. `str` is flagged as a cryptic abbreviation, in every Python file

`ABBREVIATION_RE` contains `str2?`, so every `Dict[str, str]` annotation is a
naming finding. It fired in **all eleven** source files. A builtin type is not a
badly named variable.

The same list contains `res`, `num`, `idx`, `cnt` — plausible as variable names,
but the regex matches them anywhere on the line, including inside string
literals and comments (already recorded as 7.1). Both want the scan to run on
identifiers rather than on raw line text.

### D2. Duplication reports a block as duplicating itself

```
pattern_analyzer.py: Duplicated block (16 lines): lines 10–25 and 11–26
stop-hook.py:        Duplicated block (11 lines): lines 24–34 and 25–35
record.py:           Duplicated block (12 lines): lines 44–55 and 45–56
```

Every one of those is a single dict or set literal — `LANGUAGE_MAP`,
`TYPE_LABEL`, `VALID_TYPES` — matching itself shifted by one line. After
normalisation each entry line becomes the same shape (`".S": "S",`), so the
sliding window matches its own neighbour.

`detect_duplication` checks that a *new* pair does not overlap pairs already
reported, but never checks that the two halves of a pair do not overlap **each
other**. Requiring `second_start > first_end` would remove five of the six
duplication findings here. This is a bug, not a tuning problem.

### D3. Normalised literals make any two runs of strings look identical

`boy_scout_session.py: Duplicated block (9 lines): lines 44–52 and 53–61` — two
disjoint halves of one prompt string. `normalize_line` masks every string
literal to `"S"`, so consecutive lines of prose are indistinguishable. Masking
is what lets near-copies match; it also means data and text match each other.
Skipping windows whose normalised lines are all literal-only would keep the
recall that masking buys without the false positives.

### D4. Test discovery does not bridge `-` and `_`

`hooks/post-tool-use.py` is reported as untested. Its tests are in
`tests/test_post_tool_use.py` — Python module names cannot contain hyphens, so
the test file underscores what the script hyphenates. `_find_test_file` looks
for `test_post-tool-use.py` and finds nothing.

Also flagged: `hooks/lib/__init__.py`, an empty package marker with nothing to
test.

### D5. Docstrings count toward function size

`function_size` fired on 20 of roughly 60 functions at the default threshold.
The Python path measures `end_lineno - lineno`, which includes the docstring, so
a 9-line function carrying a 12-line docstring reads as 22 lines and gets
flagged for decomposition. Punishing documentation is the wrong incentive, and
it is what makes the default threshold look badly chosen. Subtract the docstring
node before comparing.

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

- **Abbreviation scan is line-wide.** `ABBREVIATION_RE` matches inside string
  literals and trailing comments, so `"tmp"` in a message is a naming finding.
- **Duplication matching is case-insensitive.** `normalize_line` lowercases, so
  two blocks differing only in case read as copies.
- **The hook matches `Write|Edit` only.** Other edit-shaped tools go unseen.
- **Shared or personal?** `.gitignore` excludes the backlog, making it private
  by default — but the concept works better as a *team* refactoring backlog, and
  JSONL-append conflicts resolve trivially (union merge via `.gitattributes`).
  That is a product decision currently made silently by one `.gitignore` line.

---

## Suggested sequencing

0. **The detector precision bugs (D1, D2, D4, D5)** — all four are small and
   mechanical, and together they are most of the noise a first-time user meets
   when they enable `patterns`. Until they are fixed, the honest advice about
   static detection is "leave it off", which makes half the plugin decorative.
1. **Just-in-time surfacing (1)** — largest behaviour change for the least new
   machinery, and the data layer is already built.
2. **Renames (2)** — small, and it stops `--apply` closing entries it should
   have re-pointed.
3. **Git signal (3), then derived severity (4)** — together they make the
   backlog rankable rather than merely sorted.
4. **Runner safety (6)** before anyone is encouraged to cron this.
5. **(5) and (7)** are independent and can land at any time.
