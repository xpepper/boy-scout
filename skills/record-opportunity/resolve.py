#!/usr/bin/env python3
"""
Boy Scout resolve handler: close an item that is already in the backlog.

Use this when you address (or decide against) an opportunity that was recorded
earlier. To record and close in one step — an on-the-spot fix that wasn't in
the backlog yet — use `record.py --outcome fixed` instead.

Writing the outcome through this script rather than hand-editing
.claude/boy-scout-todos.jsonl matters: the store is appended to by hooks under
a file lock, and an editor does not respect that lock.

Usage:
    python3 resolve.py --id a3f9c12e --outcome fixed \\
        [--note "Extracted parse_json_body(); tests green"]
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

from todo_manager import VALID_OUTCOMES, list_todos, resolve_todo  # noqa: E402


def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Close a Boy Scout opportunity with an outcome")
    p.add_argument("--id",      required=True, help="Item id, as printed when it was recorded")
    p.add_argument("--outcome", required=True, choices=sorted(VALID_OUTCOMES))
    p.add_argument("--note",    default="", help="Optional explanation of the outcome")
    return p.parse_args()


def main() -> None:
    args = _parse_args()
    project_dir = os.environ.get("CLAUDE_PROJECT_DIR", os.getcwd())

    if not resolve_todo(project_dir, args.id, args.outcome, note=args.note or None):
        print(
            f"No Boy Scout item with id {args.id} — nothing was changed.",
            file=sys.stderr,
        )
        sys.exit(1)

    remaining = len(list_todos(project_dir))
    print(json.dumps({
        "id":        args.id,
        "outcome":   args.outcome,
        "remaining": remaining,
        "message":   f"Closed {args.id} as {args.outcome}; {remaining} open item(s) left.",
    }, indent=2))


if __name__ == "__main__":
    main()
