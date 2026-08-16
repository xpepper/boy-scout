# Configuration reference

The plugin auto-creates `.claude/boy-scout-config.json` with defaults the first
time a hook runs in a project. You can also write the file yourself beforehand.
User values are merged over the defaults section by section, so a partial file
is fine: anything you leave out keeps its default.

Full defaults:

```json
{
  "detection": {
    "enabled": true,
    "patterns": [],
    "sensitivity": "balanced",
    "ignore_paths": [
      "vendor/",
      "dist/",
      "*.generated.ts",
      "node_modules/",
      "target/",
      ".git/"
    ],
    "ignore_tests": false
  },
  "output": {
    "suppress_transcript": true
  },
  "session": {
    "auto_clear": false,
    "triage_threshold": 20
  }
}
```

## `detection`

| Key | Default | What it does |
|-----|---------|--------------|
| `enabled` | `true` | Master switch for the PostToolUse detection hook. Set it to `false` and no static detector runs at all. The `record-opportunity` skill is unaffected. |
| `patterns` | `[]` | Which static detectors run. Empty (the default) means none of them do. Accepted values: `duplication`, `naming`, `test_coverage`, `function_size`. |
| `sensitivity` | `"balanced"` | Threshold preset for the detectors that have thresholds. See below. |
| `ignore_paths` | see above | Patterns matched against the project-relative path of the modified file. A trailing slash marks a directory prefix (`vendor/` covers everything under it); other entries are matched as globs (`*.generated.ts`). Matching files are skipped silently. |
| `ignore_tests` | `false` | When `true`, the test-coverage-gap detector never reports. (Test files themselves are always exempt from it, regardless of this setting.) |

Static detectors are opt-in because they are threshold-based heuristics: high
recall, low precision. Turning one on is a decision to accept some noise in
exchange for mechanical coverage. Start with a single pattern:

```json
{ "detection": { "patterns": ["test_coverage"] } }
```

### Sensitivity levels

| Level | Min duplicate lines | Max function lines | Max naming findings per file |
|-------|--------------------|--------------------|------------------------------|
| `aggressive` | 4 | 10 | 3 |
| `balanced` *(default)* | 6 | 20 | 5 |
| `conservative` | 10 | 35 | 8 |

An unrecognised level falls back to `balanced`.

## `output`

| Key | Default | What it does |
|-----|---------|--------------|
| `suppress_transcript` | `true` | Reserved. The PostToolUse hook currently suppresses its output unconditionally, so changing this has no effect today. |

## `session`

| Key | Default | What it does |
|-----|---------|--------------|
| `auto_clear` | `false` | Reserved. Nothing reads it yet. |
| `triage_threshold` | `20` | When the open (non-dismissed) backlog has reached this many items, the Stop hook appends a "backlog has grown" nudge to its summary. The nudge only ever rides along with an actual new-findings summary, so it cannot turn into a nag on idle stops. |

## Detectors in detail

| Detector (`patterns` value) | What it finds | Where it works |
|-----------------------------|---------------|----------------|
| `duplication` | Copy-pasted blocks, found by hashing a sliding window over normalised lines (literals and numbers are masked, so near-copies still match) | Any file the hook accepts; accuracy is best where comment syntax is known (Rust, Elm, JS/TS, Python, Go, and friends) |
| `naming` | Single-character identifiers, plus a list of cryptic abbreviations (`tmp`, `buf`, `mgr`, `res`, …) | Single-character detection: Rust, Elm, JS/TS, Python, Go. The abbreviation scan runs on any file. |
| `test_coverage` | A source file was modified and no matching test file exists next to it or under `tests/`, `test/`, `spec/`, `__tests__/`, `specs/`, `src/tests/` | Rust, Elm, JS/TS, Python, Go, Ruby, Java, Kotlin, Swift |
| `function_size` | Functions longer than the sensitivity threshold | Python (via the `ast` module), Rust, JS/TS, Go (regex plus brace counting) |

When several are enabled, they run in priority order: duplication, naming,
test coverage, function size. Language support is prioritised in the order
Rust, Elm, JavaScript/TypeScript, Python; anything else is best-effort.

The hook only looks at files it recognises as source or documentation, skips
anything over 500 KB, and skips anything that looks binary.
