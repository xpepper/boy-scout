# Boy Scout — Improvement Opportunities

Last reviewed 2026-08-16, on branch `feat/anchor-staleness`.

The plugin's goal is **opportunistic refactoring**: the thing TDD skills skip,
because they optimise the red-green-refactor loop of the *current* task and keep
no memory of what they noticed along the way.

The capture half is solid, the act-on-it half now exists (focused agents, one per
item), and entries no longer quietly stop describing their code. What is left is
mostly about *timing* — surfacing a finding while acting on it is still cheap —
and about ranking findings by something better than an asserted severity.

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

1. **Just-in-time surfacing (1)** — largest behaviour change for the least new
   machinery, and the data layer is already built.
2. **Renames (2)** — small, and it stops `--apply` closing entries it should
   have re-pointed.
3. **Git signal (3), then derived severity (4)** — together they make the
   backlog rankable rather than merely sorted.
4. **Runner safety (6)** before anyone is encouraged to cron this.
5. **(5) and (7)** are independent and can land at any time.
