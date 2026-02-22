#!/usr/bin/env python3
"""
Boy Scout Stop hook.

Fires when Claude finishes a response. Reads refactoring opportunities
detected since the last time this hook ran, injects a summary into
Claude's context via systemMessage (inform-only: does not block the stop),
then records the current timestamp so the same items aren't repeated next time.
"""
import json
import os
import sys
from pathlib import Path

_LIB = Path(__file__).parent / "lib"
sys.path.insert(0, str(_LIB))

from todo_manager import list_todos, get_last_surfaced, set_last_surfaced


SEVERITY_BADGE = {"high": "🔴", "medium": "🟡", "low": "🟢"}

TYPE_LABEL = {
    "duplication":   "Duplication",
    "naming":        "Naming",
    "test_coverage": "No tests",
    "function_size": "Long function",
    "custom":        "Opportunity",
}

MAX_ITEMS_IN_SUMMARY = 12


def _format_summary(todos: list) -> str:
    count = len(todos)
    plural = "y" if count == 1 else "ies"

    lines = [
        f"🏕️  Boy Scout report: {count} new refactoring opportunit{plural} detected.",
        "",
    ]

    for todo in todos[:MAX_ITEMS_IN_SUMMARY]:
        badge   = SEVERITY_BADGE.get(todo.get("severity", "low"), "•")
        label   = TYPE_LABEL.get(todo.get("type", "custom"), "Opportunity")
        path    = todo.get("file_path", "unknown")
        desc    = todo.get("description", "")
        lines.append(f"  {badge} [{label}] {path}: {desc}")

    if count > MAX_ITEMS_IN_SUMMARY:
        lines.append(f"  … and {count - MAX_ITEMS_IN_SUMMARY} more (see .claude/boy-scout-todos.jsonl)")

    lines += [
        "",
        "💡 All items are saved in .claude/boy-scout-todos.jsonl.",
        "   Start a Boy Scout session whenever you're ready to address them incrementally.",
    ]
    return "\n".join(lines)


def main() -> None:
    project_dir = os.environ.get("CLAUDE_PROJECT_DIR", os.getcwd())

    last_surfaced = get_last_surfaced(project_dir)
    todos = list_todos(project_dir, since=last_surfaced)

    if not todos:
        print(json.dumps({"decision": "approve"}))
        sys.exit(0)

    set_last_surfaced(project_dir)

    summary = _format_summary(todos)
    print(json.dumps({
        "decision": "approve",
        "systemMessage": summary,
    }))


if __name__ == "__main__":
    try:
        main()
    except Exception:
        # Never let an unhandled exception block the session from stopping.
        print(json.dumps({"decision": "approve"}))
        sys.exit(0)
