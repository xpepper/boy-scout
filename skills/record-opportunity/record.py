#!/usr/bin/env python3
"""
Boy Scout record-opportunity skill handler.

Records a refactoring opportunity to .claude/boy-scout-todos.jsonl. Invoked by
Claude when it notices an opportunity while doing other work.

Usage:
    python3 record.py \\
        --type duplication \\
        --file src/handler.rs \\
        --lines 42-58 \\
        --description "Logic duplicated in process_request()" \\
        --severity medium \\
        [--context "Could be extracted to a shared parse_input() helper"]

Add --outcome fixed when the fix was already made on the spot: the item is
recorded and closed in one step, so on-the-spot cleanups still show up in the
recorded-vs-resolved ratio instead of vanishing.
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

from todo_manager import VALID_OUTCOMES, add_todo, list_todos, resolve_todo  # noqa: E402

VALID_TYPES = {
    "duplication",
    "function_size",
    "naming",
    "test_coverage",
    "dead_code",
    "wrong_abstraction",
    "custom",
}
VALID_SEVERITIES = {"low", "medium", "high"}


def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Record a Boy Scout refactoring opportunity")
    p.add_argument("--type",        required=True, choices=sorted(VALID_TYPES))
    p.add_argument("--file",        required=True, help="File path (relative to project root)")
    p.add_argument("--description", required=True, help="Intent-revealing description")
    p.add_argument("--severity",    default="medium", choices=sorted(VALID_SEVERITIES))
    p.add_argument("--lines",       default="",  help="Optional line range, e.g. '42' or '42-58'")
    p.add_argument("--context",     default="",  help="Optional hint for addressing the issue")
    p.add_argument("--outcome",     default="",  choices=("",) + tuple(sorted(VALID_OUTCOMES)),
                   help="Close the item immediately — use 'fixed' when you already made the fix")
    p.add_argument("--note",        default="",  help="Optional explanation of the outcome")
    return p.parse_args()


def _parse_locations(lines_str: str) -> list[dict]:
    """Turn a --lines argument into a locations list.

    Returns an empty list when no usable line range was given: a file-level
    finding has no line anchor, and pretending it sits on line 1 would make
    every file-level finding in a file collide with every other one during
    deduplication.
    """
    if not lines_str:
        return []
    parts = lines_str.split("-")
    try:
        start = int(parts[0])
        end   = int(parts[1]) if len(parts) > 1 else start
    except (ValueError, IndexError):
        return []
    return [{"line_start": max(1, start), "line_end": max(1, end)}]


def main() -> None:
    args = _parse_args()
    project_dir = os.environ.get("CLAUDE_PROJECT_DIR", os.getcwd())

    todo: dict = {
        "type":        args.type,
        "file_path":   args.file,
        "locations":   _parse_locations(args.lines),
        "description": args.description,
        "severity":    args.severity,
        "source":      "skill",
    }
    if args.context:
        todo["context"] = args.context

    todo_id, is_new = add_todo(project_dir, todo)

    # A fix made on the spot is recorded and closed in one step. Going through
    # add_todo first means an on-the-spot fix also closes the open entry the
    # backlog may already hold for that issue, rather than leaving a resolved
    # twin beside it.
    if args.outcome:
        resolve_todo(project_dir, todo_id, args.outcome, note=args.note or None)

    total = len(list_todos(project_dir))

    if args.outcome:
        message = (
            f"Recorded and closed as {args.outcome}: [{args.type}] {args.file} — "
            f"{args.description} (id: {todo_id})"
        )
    elif is_new:
        message = (
            f"Recorded opportunity #{total}: [{args.type}] {args.file} — "
            f"{args.description} (id: {todo_id})"
        )
    else:
        message = (
            f"Already tracked as [{args.type}] {args.file} (id: {todo_id}) — "
            "skipped duplicate, an open entry already describes this issue"
        )

    result = {
        "id":       todo_id,
        "is_new":   is_new,
        "outcome":  args.outcome or None,
        "position": total,
        "message":  message,
    }
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
