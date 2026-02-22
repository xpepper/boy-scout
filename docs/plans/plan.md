## **Plan 1: Boy Scout Plugin**

**Objective:** Create a Claude Code plugin that implements Boy Scout hook mechanics for opportunistic refactoring detection and TODO management.

**Plugin Structure:**
```
.claude-plugins/boy-scout/
├── hooks/
│   ├── hooks.json          # Hook configurations
│   ├── post-tool-use.py    # PostToolUse detection logic
│   └── stop-hook.py        # Stop hook surfacing logic
├── lib/
│   ├── detectors.py        # Refactoring pattern detection
│   ├── todo_manager.py     # TODO list persistence & management
│   └── pattern_analyzer.py # Code analysis utilities
├── schema/
│   └── todo-item.json      # Schema for TODO entries
├── plugin.json             # Plugin metadata
└── README.md               # Plugin documentation
```

**Phase 1: Core Infrastructure**

**1.1 Plugin Metadata & Configuration**
- Create `plugin.json` with:
  - Plugin name, version, description
  - Hook configuration path
  - Dependencies (Python 3.8+, jq, optional linters)
  - Configuration schema (detection sensitivity, file patterns to ignore, etc.)
- Create `.claude/boy-scout-config.json` defaults (detection rules, output paths)

**1.2 TODO List Persistence Layer**
- Implement `todo_manager.py`:
  - Store TODOs in `.claude/boy-scout-todos.jsonl` (line-delimited JSON for streaming)
  - Schema: `{id, type, file_path, line_range, description, severity, detected_at, source, dismissed}`
  - Methods: `add_todo()`, `list_todos()`, `mark_reviewed()`, `dismiss()`, `clear_session()`
  - Support querying by: type, severity, file, age
- Implement file locking to prevent concurrent writes in multi-hook scenarios

**1.3 Pattern Detectors**
- Implement `detectors.py` with modular detector functions:
  - `detect_duplication(file_path)` — Find repeated code blocks using AST/token analysis
  - `detect_function_size(file_path)` — Flag functions exceeding complexity thresholds (e.g., >15 lines, cyclomatic complexity)
  - `detect_test_coverage_gap(modified_file, test_dir)` — Check if tests exist/were updated alongside production code
  - `detect_naming_clarity(file_path)` — Basic heuristic on intention-revealing names (flags single-letter vars, abbreviations)
  - Each returns: `{type, locations[], severity, description}`
- Language-aware parsing (detect language from file extension, use appropriate analyser)

**Phase 2: Hook Implementations**

**2.1 PostToolUse Hook** (`post-tool-use.py`)
- Triggers on `Write|Edit` tool calls
- Reads modified file path from tool input
- Runs all detectors asynchronously (or with timeout)
- For each finding: create TODO item, append to `.claude/boy-scout-todos.jsonl`
- Output (exit code 0): JSON with `{"suppressOutput": true}` (no noise in transcript)
- Handle edge cases: binary files, very large files, non-code files

**2.2 Stop Hook** (`stop-hook.py`)
- Triggers at `Stop` event
- Reads `.claude/boy-scout-todos.jsonl`
- Computes session summary: `{total_items, by_type, by_severity}`
- Outputs via `additionalContext` (JSON output) with:
  - Summary text (human-readable)
  - Itemized list (type, file, description, severity)
  - Suggestion to enter "Boy Scout session"
- Exit code 0 (informational, doesn't block)

**Phase 3: Configuration & Customization**

**3.1 User Configuration**
- `.claude/boy-scout-config.json`:
  - `detection.enabled`: true/false
  - `detection.patterns`: list of enabled detectors (duplication, size, coverage, naming)
  - `detection.sensitivity`: "aggressive" | "balanced" | "conservative"
  - `detection.ignore_paths`: glob patterns (e.g., `["vendor/", "dist/", "*.generated.ts"]`)
  - `detection.ignore_tests`: true/false (skip flagging test files)
  - `output.suppress_transcript`: true (don't show in verbose mode)
  - `session.auto_clear`: false (keep TODOs across sessions) | true (clear after Boy Scout session)
  - `language_config`: language-specific thresholds (e.g., Rust function size)

**3.2 hooks.json Configuration**
- Wire up hooks with matchers and timeouts
- Example:
  ```json
  {
    "PostToolUse": [{
      "matcher": "Write|Edit",
      "hooks": [{
        "type": "command",
        "command": "${CLAUDE_PLUGIN_ROOT}/hooks/post-tool-use.py",
        "timeout": 10
      }]
    }],
    "Stop": [{
      "hooks": [{
        "type": "command",
        "command": "${CLAUDE_PLUGIN_ROOT}/hooks/stop-hook.py",
        "timeout": 5
      }]
    }]
  }
  ```

**Phase 4: Documentation & Testing**

**4.1 Plugin Documentation**
- `README.md`: overview, setup, configuration, examples
- Comment detection logic with intent and assumptions
- Examples of TODO list output

**4.2 Schema Definition**
- `schema/todo-item.json`: JSON schema for TODO entries (useful for validation)

---

## **Plan 2: Boy Scout Agent Skill**

**Objective:** Create an agent skill that allows Claude to explicitly record refactoring opportunities it observes during work, complementing passive hook detection.

**Skill Structure:**
```
.claude-plugins/boy-scout-skill/
├── skill.json              # Skill definition (name, description, parameters)
├── handler.py             # Skill invocation handler
└── README.md              # Skill documentation
```

**Phase 1: Skill Definition**

**1.1 Skill Metadata** (`skill.json`)
- Name: `record_boy_scout_opportunity`
- Description: "Record an opportunistic refactoring opportunity without interrupting current task"
- Input parameters:
  - `type` (enum): "duplication" | "complexity" | "naming" | "testing" | "performance" | "custom"
  - `location` (string): file path and optional line range, e.g., `"src/handler.rs:42-58"`
  - `description` (string): intent-revealing explanation of the opportunity
  - `severity` (enum): "low" | "medium" | "high"
  - `context` (string, optional): additional context or suggestion
- Output: confirmation (TODO ID, position in list)

**1.2 Skill Parameters Schema**
- Document parameter validation rules
- Provide examples for each type

**Phase 2: Implementation**

**2.1 Skill Handler** (`handler.py`)
- Invoked when Claude calls the skill
- Validate input parameters
- Call `todo_manager.add_todo()` from the plugin (shared dependency)
- Return: `{id, position_in_list, total_items, message}`
- Non-blocking; logs to `.claude/boy-scout-skills.log` for audit

**2.2 Integration with Plugin**
- Skill handler imports `todo_manager` from plugin's `lib/`
- Both write to same `.claude/boy-scout-todos.jsonl` (managed by locking)
- Source field distinguishes: `"hook"` vs `"skill"`

**Phase 3: Usage Patterns & Documentation**

**3.1 When Claude Would Use This Skill**
- During code review of own output: "This duplication could be extracted"
- While writing tests: "We should also test the error path"
- During refactoring: "This function is doing too much; composed-method opportunity"

**3.2 Documentation**
- `README.md`:
  - Skill purpose and when to use (vs when hooks detect)
  - Parameter guide with examples
  - Integration notes with plugin
  - Example: Claude explicitly recording a semantic refactoring Claude wouldn't catch with static analysis

**Phase 4: Testing & Refinement**

**4.1 Manual Testing**
- Test skill invocation from Claude Code
- Verify TODO list updates correctly
- Check output format

---

## **Next Steps (After Plans)**

Once these plans are built out:

1. **Create plugin** — Follow Plan 1 to implementation
2. **Create skill** — Follow Plan 2, ensuring integration with plugin
3. **Integration test** — Run both together; verify hooks + skill recording work in tandem
4. **Session workflow** — Test the full loop: main task → Boy Scout detection → Stop hook surfaces TODO → user enters Boy Scout session → skill/hooks continue improving code
5. **Documentation** — Walkthrough guide for using both together
