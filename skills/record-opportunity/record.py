#!/usr/bin/env python3
"""
Boy Scout record-opportunity skill handler.

Records a refactoring opportunity to .claude/boy-scout-todos.jsonl without
interrupting the current task. Invoked by Claude when it notices an
opportunity that should be addressed later.

Usage:
    python3 record.py \\
        --type duplication \\
        --file src/handler.rs \\
        --lines 42-58 \\
        --description "Logic duplicated in process_request()" \\
        --severity medium \\
        [--context "Could be extracted to a shared parse_input() helper"]
"""
import argparse
import json
import os
import sys
from pathlib import Path

# Resolve hooks/lib from CLAUDE_PLUGIN_ROOT so the script works regardless of
# where the plugin is installed.
_plugin_root = os.environ.get(
    "CLAUDE_PLUGIN_ROOT",
    str(Path(__file__).parent.parent.parent),  # …/skills/record-opportunity → plugin root
)
sys.path.insert(0, str(Path(_plugin_root) / "hooks" / "lib"))

from todo_manager import add_todo, list_todos  # noqa: E402

VALID_TYPES = {"duplication", "function_size", "naming", "test_coverage", "custom"}
VALID_SEVERITIES = {"low", "medium", "high"}


def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Record a Boy Scout refactoring opportunity")
    p.add_argument("--type",        required=True, choices=sorted(VALID_TYPES))
    p.add_argument("--file",        required=True, help="File path (relative to project root)")
    p.add_argument("--description", required=True, help="Intent-revealing description")
    p.add_argument("--severity",    default="medium", choices=sorted(VALID_SEVERITIES))
    p.add_argument("--lines",       default="",  help="Optional line range, e.g. '42' or '42-58'")
    p.add_argument("--context",     default="",  help="Optional hint for addressing the issue")
    return p.parse_args()


def _parse_lines(lines_str: str) -> tuple[int, int]:
    if not lines_str:
        return 1, 1
    parts = lines_str.split("-")
    try:
        start = int(parts[0])
        end   = int(parts[1]) if len(parts) > 1 else start
        return max(1, start), max(1, end)
    except (ValueError, IndexError):
        return 1, 1


def main() -> None:
    args = _parse_args()
    project_dir = os.environ.get("CLAUDE_PROJECT_DIR", os.getcwd())

    line_start, line_end = _parse_lines(args.lines)

    todo: dict = {
        "type":        args.type,
        "file_path":   args.file,
        "locations":   [{"line_start": line_start, "line_end": line_end}],
        "description": args.description,
        "severity":    args.severity,
        "source":      "skill",
    }
    if args.context:
        todo["context"] = args.context

    todo_id = add_todo(project_dir, todo)
    total   = len(list_todos(project_dir))

    result = {
        "id":       todo_id,
        "position": total,
        "message":  (
            f"Recorded opportunity #{total}: [{args.type}] {args.file} — "
            f"{args.description} (id: {todo_id})"
        ),
    }
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
