#!/usr/bin/env python3
"""
Builds the prompt for a headless, scheduled Boy Scout session and (unless
--print-only) hands it to `claude -p`.

Meant to be invoked by run-boy-scout-session.sh via cron/launchd, or by
Superpowers' schedule/loop skill — see README.md "Scheduled Resolution".

Exit codes:
  0  a session ran (or the prompt was printed with --print-only)
  1  nothing to do (no open, non-dismissed items) — caller should skip
"""
import argparse
import os
import sys
from collections import Counter
from pathlib import Path
from typing import Optional

_REPO_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(_REPO_ROOT / "hooks" / "lib"))

from todo_manager import list_todos  # noqa: E402

MAX_ITEMS_PER_SESSION = 5


def build_session_prompt(project_dir: str) -> Optional[str]:
    """Return the prompt for a scheduled Boy Scout session, or None if the
    open (non-dismissed) backlog is empty.
    """
    todos = list_todos(project_dir)
    if not todos:
        return None

    by_severity = Counter(t.get("severity", "low") for t in todos)
    breakdown = ", ".join(
        f"{by_severity[s]} {s}" for s in ("high", "medium", "low") if by_severity.get(s)
    )

    plural = "y" if len(todos) == 1 else "ies"
    return (
        f"You are running a scheduled Boy Scout session. There are {len(todos)} open "
        f"refactoring opportunit{plural} in .claude/boy-scout-todos.jsonl ({breakdown}).\n\n"
        f"Pick up to {MAX_ITEMS_PER_SESSION} of the highest-severity open (non-dismissed) "
        "entries. For each one, using this project's normal TDD and verification practices:\n"
        "  1. Make the smallest safe change that addresses it.\n"
        "  2. Verify it (run the relevant tests).\n"
        "  3. Commit it individually with a conventional commit message.\n"
        "  4. Close that entry once committed, by id:\n"
        "       python3 \"$CLAUDE_PLUGIN_ROOT/skills/record-opportunity/resolve.py\" "
        "--id <id> --outcome fixed\n"
        "     Never edit .claude/boy-scout-todos.jsonl by hand: the detection hook "
        "appends to it under a lock while you work.\n\n"
        "Work one item at a time — do not batch unrelated fixes into a single commit. "
        f"Stop after {MAX_ITEMS_PER_SESSION} items and leave the rest for the next session. "
        "Do not push."
    )


def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Run or print a scheduled Boy Scout session prompt")
    p.add_argument("--project-dir", default=os.environ.get("CLAUDE_PROJECT_DIR", os.getcwd()))
    p.add_argument("--print-only", action="store_true",
                    help="Print the prompt to stdout instead of invoking `claude -p`")
    return p.parse_args()


def main() -> None:
    args = _parse_args()
    prompt = build_session_prompt(args.project_dir)

    if prompt is None:
        print("Boy Scout: no open opportunities. Nothing to do.")
        sys.exit(1)

    if args.print_only:
        print(prompt)
        sys.exit(0)

    os.execvp("claude", ["claude", "-p", prompt, "--allowedTools", "Read,Edit,Write,Bash"])


if __name__ == "__main__":
    main()
