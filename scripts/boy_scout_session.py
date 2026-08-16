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
        f"You are running a scheduled Boy Scout session, unattended. There are "
        f"{len(todos)} open refactoring opportunit{plural} ({breakdown}). Read them "
        "with `boy-scout-list`.\n\n"
        "Before changing anything, establish a baseline:\n"
        "  - Run the project's test suite. If it is already failing, STOP: report "
        "which tests were red and change nothing. Without a green before-picture "
        "you cannot tell 'I broke it' from 'it was already broken', and you are "
        "about to commit either way.\n"
        "  - Run `git status --short`. If the working tree is dirty, STOP: those "
        "changes are someone else's, and committing would sweep them up.\n\n"
        f"Then pick up to {MAX_ITEMS_PER_SESSION} of the highest-severity open "
        "entries, preferring contained ones — a rename, an extraction, a missing "
        "test — over anything needing a design decision. For each, one at a time, "
        "using this project's normal TDD and verification practices:\n"
        "  1. Make the smallest safe change that addresses it.\n"
        "  2. Verify it (run the relevant tests).\n"
        "  3. Commit it individually with a conventional commit message.\n"
        "  4. Close that entry once committed, by id:\n"
        "       boy-scout-resolve --id <id> --outcome fixed\n"
        "     Never edit .claude/boy-scout-todos.jsonl by hand: boy-scout-record "
        "appends to it under a lock while you work.\n\n"
        "Abandon an item — `git restore` your changes, leave the entry open, and "
        "move to the next — as soon as it stops being small: it needs a design "
        "decision, it has grown past about three files, or verification fails for "
        "any reason that is not an obvious slip in your own edit. Backing out is "
        "the correct outcome, not a failure; nobody is watching to rescue it.\n\n"
        "If an entry no longer describes the code, close it as stale with a note "
        "rather than inventing work: boy-scout-resolve --id <id> --outcome stale "
        "--note '<why>'.\n\n"
        "Do not batch unrelated fixes into a single commit. "
        f"Stop after {MAX_ITEMS_PER_SESSION} items and leave the rest for the next "
        "session. Do not push."
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
