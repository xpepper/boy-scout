# Boy Scout — Improvement Opportunities

Review date: 2026-08-16. Reviewed at commit `03c48c0`.

The plugin's stated goal is **opportunistic refactoring** — the thing TDD skills
(Superpowers included) skip, because they optimise the red-green-refactor loop
of the *current* task and have no memory of what they noticed along the way.

This review found that the current implementation solves the *capture* half of
that problem well, and does not yet solve the *act on it* half at all. That gap
is the theme running through most of what follows.

Items are ordered by leverage, not by effort.

---

## 0. The framing gap: this is a capture system, not a Boy Scout system

The Boy Scout Rule is **"leave the campground cleaner than you found it"** — fix
the small thing *while you are standing there*. The plugin currently says the
opposite, explicitly:

> `SKILL.md`: "Do **not** stop the current task to fix the issue. Record and continue."

Every finding, without exception, is deferred to a JSONL backlog. There is no
"fix it now" path anywhere in the codebase. That converts the Boy Scout Rule
into a TODO graveyard, which is the well-known failure mode it was invented to
avoid.

The user's own global working rules already encode the correct gate (`~/.claude/CLAUDE.md` §6):
address an opportunity *now* when **all** of — you are already editing the file,
the fix is small and mechanically safe, it doesn't meaningfully expand the diff,
and it's uncontroversial. Otherwise record it.

**The plugin has the single hardest input to that gate already in hand and throws
it away:** the PostToolUse hook knows exactly which file was just edited. A
finding in a file Claude is *currently modifying* is a "now" candidate. A finding
in a file Claude merely read is a "later" candidate. Nothing distinguishes them
today.

**Opportunity:** introduce a triage decision at record time — `now` / `next` /
`never` — with the four conditions as the explicit test, and make `now` a real,
supported path (a small verified fix folded into the current work, called out in
one line of the transcript). This is the single highest-leverage change in this
document.

---

## 1. Correctness bugs (found and reproduced)

### 1.1 Distinct file-level findings are silently discarded — **data loss**

`todo_manager._find_open_duplicate()` treats `type + file_path + overlapping
line range` as identity. Findings recorded without `--lines` default to
`{"line_start": 1, "line_end": 1}` (`record.py:_parse_lines`). Every file-level
finding in a given file therefore collides with every other one of the same type.

Reproduced:

```
$ record.py --type custom --file src/x.py --description "Dead code in module header" --severity low
  → recorded
$ record.py --type custom --file src/x.py --description "Wrong abstraction: Repo leaks SQL" --severity high
  → {"is_new": false, "message": "Already tracked ... skipped duplicate"}
```

The second, higher-severity, semantically unrelated finding is gone. Since
`custom` is the catch-all type (see 1.2), and `test_coverage` is always
file-level, this fires often in normal use.

**Fix direction:** identity for file-level findings should not be line-based.
Use a description-similarity or content-hash component, or make "no line range"
a distinct identity space rather than an alias for line 1.

### 1.2 `SKILL.md` instructs Claude to record types the CLI rejects

`SKILL.md` "When to Trigger" lists **Wrong abstraction** and **Dead code** as
first-class categories. `record.py:VALID_TYPES` is
`{duplication, function_size, naming, test_coverage, custom}` — neither exists.
Both are forced into `custom`, where they then collide with each other per 1.1,
and where `stop-hook.TYPE_LABEL` renders them as a generic "Opportunity".

The taxonomy the skill teaches and the taxonomy the tool accepts have drifted apart.

### 1.3 `_matches_ignore` prefix matching is too eager

`post-tool-use.py:85` — `rel_path.startswith(pattern.rstrip("/"))` means the
default ignore entry `"target/"` also silently ignores `targeting.py`,
`targets/`, `target_resolver.rs`. Should be a path-segment-aware prefix match.

### 1.4 Duplication buckets trust hash equality without verifying content

`detectors.detect_duplication` buckets windows by `hash(block_text)` and then
assumes `occurrences[0]` and `occurrences[1]` are identical blocks without
comparing the text. Collision probability is negligible at 64 bits, but the
check is one line and its absence is a latent false-positive source.

### 1.5 Function-size detection is dead for Elm, a stated priority language

`detectors.py:346` bails with `if func_re is None or language not in
BRACE_LANGUAGES`. `BRACE_LANGUAGES` does not contain `"elm"` (Elm is not
brace-delimited), so `detect_function_size` returns `[]` for every Elm file and
the `"elm"` entry in `FUNC_PATTERNS` (line 278) is unreachable. Elm is listed
second in the plugin's own language priority order, and the README advertised
Elm function-size support that has never worked.

Verified: `elm` appears in `BINDING_PATTERNS`, `TESTABLE_LANGUAGES`, and
`FUNC_PATTERNS`, but not in `BRACE_LANGUAGES`.

Fixing it needs an indentation-based (offside-rule) size strategy rather than
brace counting, which is a genuine piece of work, not a one-liner. Python
already needs a non-brace strategy and uses the AST; Elm needs a third path.

*(Found by the docs agent while checking the README's detector table against
the code, and confirmed independently.)*

### 1.6 Two config keys are documented but read by nothing

`output.suppress_transcript` and `session.auto_clear` exist in
`todo_manager.DEFAULT_CONFIG`, are written into every auto-created config file,
and were presented in the README as live settings. Neither is read anywhere:
`post-tool-use.py` calls `_suppress()` unconditionally, and no code path clears
a session.

Verified: both strings appear only at `todo_manager.py:36` and `:39` across
`hooks/`, `scripts/`, `skills/`, and `tests/`.

Either wire them up or drop them from `DEFAULT_CONFIG`. Shipping settings that
silently do nothing trains users not to trust the config file. The docs now mark
them as reserved, which is a holding position, not a fix.

---

## 2. The backlog has no lifecycle, so it decays into fiction

### 2.1 Findings go stale and nothing notices

A finding says `src/routes/auth.rs:88-104`. Two commits later those lines are
something else entirely. Nothing re-validates. The backlog accumulates entries
that point at code that no longer exists, and the user has no way to tell the
live ones from the rotted ones — which is precisely how a backlog stops being
trustworthy.

**Opportunity:** record a content fingerprint (hash of the referenced lines) or
the file's blob SHA at detection time; on read, mark entries whose anchor no
longer matches as `stale` and offer to drop them. Git makes this cheap.

### 2.2 Only one terminal state: `dismissed`

There is no distinction between *fixed*, *won't fix*, *no longer applies*, and
*was wrong*. So the plugin cannot answer the one question that determines whether
it is working: **of what it recorded, what actually got improved?** A "recorded
214, resolved 6" ratio would be the most valuable number this plugin could print,
and it is currently uncomputable.

### 2.3 No programmatic way to close an item

`boy_scout_session.py` instructs the model to *hand-edit the JSONL file* to flip
`"dismissed": true`. Text-editing a line-delimited JSON store, unattended, on a
cron, concurrently with a PostToolUse hook that appends to the same file under
`flock` — the writer respects the lock, the model's `Edit` does not.

**Opportunity:** a `resolve.py` / `dismiss.py` CLI counterpart to `record.py`,
taking an id and an outcome, going through the same locking path. And a
corresponding skill so Claude can close items during any session, not just a
scheduled one.

---

## 3. What's missing that TDD skills genuinely don't cover

This is the plugin's differentiator, and `SKILL.md`'s trigger list currently
under-uses it. The listed triggers (duplication, long function, bad name,
missing test, wrong abstraction, dead code) are the standard smell taxonomy —
they are exactly what a linter or a code-review skill already covers, and mostly
what the static detectors already attempt.

The signals that **only** an agent doing the work can produce, and that nothing
else in the ecosystem captures:

- **Skipped refactor step.** The TDD loop reached green and moved on without
  step 5. That is the canonical missed opportunistic refactoring, and the agent
  knows it happened.
- **Comprehension cost.** "I had to read three files to understand what this
  function returns." Time-to-understand is the strongest refactoring signal in
  existence and is completely invisible to static analysis. Only the reader knows.
- **Self-inflicted debt.** "I inlined this rather than threading the parameter
  through, to keep the diff small." The agent introduced it, knows it's a
  compromise, and currently has nowhere to say so.
- **Test smells.** Slow, order-dependent, over-mocked, behaviour-coupled tests.
  The `test-desiderata` skill has a whole framework for this; Boy Scout records
  only "no test file exists".
- **Change hotspots.** A finding in a file touched 40 times in three months
  matters an order of magnitude more than one in a file touched twice. `git log`
  is free, sitting right there, and unused (see 4).
- **Repeated friction.** The same region edited across three separate sessions
  is shotgun surgery announcing itself. The backlog spans sessions and could see
  this; it doesn't look.

### 3.1 Severity is asserted, never derived

`--severity` is Claude's unanchored judgment, and the static detectors hardcode
`"medium"` / `"low"` by line count. Nothing incorporates blast radius, churn, or
whether anyone actually depends on the code. Two findings marked `high` are not
comparable, which makes "pick the 5 highest-severity items" a coin flip.

---

## 4. Git history is free prioritisation signal, entirely unused

Behavioural code analysis (Tornhill) is the mature version of this idea: rank by
*change frequency × complexity*, not by complexity alone. Concretely available
today, at zero infrastructure cost:

- `git log --format= --name-only | sort | uniq -c` → churn per file, for hotspot
  ranking and for severity that means something.
- Files that repeatedly change *together* but live apart → hidden coupling, a
  refactoring opportunity no single-file detector can ever see.
- `git blame` age on a flagged region → distinguishes fresh code (cheap to fix,
  author context still warm) from decade-old code (expensive, riskier).
- Whether the flagged region is inside the current branch's diff → the strongest
  possible "you are already standing here" signal for the §0 triage gate.

---

## 5. Timing: findings surface at the wrong moment

The Stop hook reports at the end of a response — *after* the moment when acting
was cheap. By then the file is closed, the context has moved on, and the finding
is deferred by construction.

**Opportunity:** surface *just in time* instead. A `PreToolUse` (or
`SessionStart`) hook that sees Claude is about to edit `src/billing/invoice.py`
and injects "2 open Boy Scout items in this file" converts a passive backlog
into active, in-the-moment context. That is what makes a refactoring
*opportunistic* rather than *scheduled*. It reuses the existing store and hook
infrastructure entirely.

---

## 6. The scheduled runner is doing something risky, unsupervised

`boy_scout_session.py:78`:

```python
os.execvp("claude", ["claude", "-p", prompt, "--allowedTools", "Read,Edit,Write,Bash"])
```

Unrestricted `Bash`, running unattended on a cron, editing and committing to a
repository. Specific gaps:

- **No baseline check.** If the suite was already red before the session started,
  the session cannot distinguish "I broke it" from "it was broken". Verification
  is meaningless without a recorded baseline.
- **No revert on failure.** If verification fails mid-item, nothing restores the
  working tree. The next scheduled run starts from a dirty, broken state.
- **No blast-radius cap.** Nothing bounds diff size, files touched, or refuses
  to proceed on a dirty working tree.
- **No dry-run default.** The README suggests a manual run first; the tool
  doesn't enforce or support it (`--print-only` prints the prompt, which is not
  the same thing).
- **`--allowedTools Bash` is broader than the task needs.** The job is: run
  tests, `git add`, `git commit`. That's an allowlist, not a blank cheque.

---

## 7. Ergonomics and adoption

- **No slash commands at all.** `/boy-scout` (status), `/boy-scout-list`,
  `/boy-scout-session`, `/boy-scout-dismiss <id>`. Today every interaction
  requires the user to remember the JSONL path and ask in prose. This is the
  cheapest adoption win available.
- **No dedicated agent.** Resolution work belongs in a narrow-toolset subagent
  so a Boy Scout session can't balloon into the main context.
- **Shared or personal?** `.gitignore` excludes `boy-scout-todos.jsonl`, making
  the backlog private by default — but the whole concept works better as a
  *team* refactoring backlog, and JSONL-append conflicts are trivially resolvable
  (union merge, `.gitattributes`). This is a genuine product decision that is
  currently made silently by a `.gitignore` line and never discussed.
- **No metrics surface.** See 2.2 — recorded vs. resolved is the plugin's own
  fitness function and nobody can see it.

---

## 8. README is ~3× too long for its audience

289 lines for a pre-alpha plugin. A prospective user needs four things: what it
does, how to install it, the minimum config, how to run a session. The rest is
maintainer material competing for attention with it.

**Belongs in the README (target ≈ 100 lines):** the quote and one-paragraph
pitch, the pre-alpha warning, the flow diagram, install, minimal config with a
pointer to full reference, `record-opportunity` in three sentences, a short
"how a session works", scheduled resolution in five lines.

**Belongs elsewhere:** full config reference and sensitivity table → `docs/configuration.md`.
TODO storage schema and dedup semantics → `docs/storage.md` (or just point at
`schema/todo-item.json`). Plugin structure tree → delete; it duplicates the
filesystem and will drift. Debugging → `docs/development.md`. Contributing →
`CONTRIBUTING.md` (GitHub surfaces it automatically). Testing → two lines under
Contributing.

Also: the "How the Stop Hook Fires" section is 30 lines explaining that the Stop
event fires when Claude stops responding. That's one sentence.

---

## Suggested sequencing

1. **Fix 1.1 and 1.2 first.** Silent data loss undermines every other feature —
   there is no point improving what gets recorded while records vanish.
2. **Ship §0 (the `now` path).** It's the plugin's reason to exist.
3. **Then §5 (just-in-time surfacing)** — same store, same hooks, large behaviour change.
4. **Then §2 (lifecycle) and §4 (git signal)**, which together make the backlog
   trustworthy and rankable.
5. **§7 (commands) and §8 (README)** are independent and can land at any time.
6. **§6 (runner safety)** before anyone is encouraged to actually cron this.
