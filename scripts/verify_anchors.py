#!/usr/bin/env python3
"""
Check the backlog against the code, and repair what can be repaired safely.

Each open entry is re-checked against the anchor taken when it was recorded:

    moved     the code is intact, at a different line range  → re-point it
    missing   the file itself is gone                        → close it as stale
    drifted   the described code was rewritten in place      → report it, only

`drifted` is where a machine has to stop. Changed code is evidence an entry may
be obsolete, never proof — a rewrite can leave the original smell exactly where
it was — so closing on a fingerprint miss would delete real findings silently.
That call stays with a person, or with an agent that can read the code.

Usage:
    boy-scout-verify              # report what would change (default, safe)
    boy-scout-verify --apply      # re-point what moved, close what is gone
"""
import argparse
import sys
from pathlib import Path
from typing import Dict, List

_PLUGIN_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_PLUGIN_ROOT / "hooks" / "lib"))

from anchors import annotate  # noqa: E402
from todo_manager import (  # noqa: E402
    find_project_dir,
    list_todos,
    relocate_todo,
    resolve_todo,
)


def _describe(todo: Dict) -> str:
    return f"[{todo.get('id')}] {todo.get('file_path')} — {todo.get('description', '')}"


def verify(project_dir: str, apply: bool = False) -> str:
    """Re-check every open entry; repair the safe cases when `apply` is set."""
    checked = annotate(project_dir, list_todos(project_dir))

    moved = [t for t in checked if t["anchor_status"] == "moved"]
    missing = [t for t in checked if t["anchor_status"] == "missing"]
    drifted = [t for t in checked if t["anchor_status"] == "drifted"]

    if not (moved or missing or drifted):
        return (
            f"🏕️  Boy Scout: {len(checked)} open item(s) all still match the code "
            "they describe. Nothing to repair."
        )

    lines: List[str] = []
    verb_moved = "Re-pointed" if apply else "Would re-point"
    verb_closed = "Closed as stale" if apply else "Would close as stale"

    if moved:
        lines.append(f"↻ {verb_moved} {len(moved)} item(s) whose code moved:")
        for todo in moved:
            new_range = todo["current_locations"][0]
            lines.append(
                f"   {_describe(todo)}"
                f"\n     → lines {new_range['line_start']}-{new_range['line_end']}"
            )
            if apply:
                relocate_todo(project_dir, todo["id"], todo["current_locations"])

    if missing:
        if lines:
            lines.append("")
        lines.append(f"✖ {verb_closed} {len(missing)} item(s) whose file is gone:")
        for todo in missing:
            lines.append(f"   {_describe(todo)}")
            if apply:
                resolve_todo(
                    project_dir,
                    todo["id"],
                    "stale",
                    note=f"{todo.get('file_path')} no longer exists",
                )

    if drifted:
        if lines:
            lines.append("")
        lines.append(
            f"⚠ {len(drifted)} item(s) describe code that has been rewritten. "
            "Left open on purpose — a rewrite can leave the smell in place, so "
            "re-read each one and close it yourself if it no longer applies:"
        )
        for todo in drifted:
            lines.append(f"   {_describe(todo)}")

    if not apply and (moved or missing):
        lines += ["", "Run with --apply to make the safe repairs above."]

    return "\n".join(lines)


def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Check Boy Scout entries against the code")
    p.add_argument("--apply", action="store_true",
                   help="Make the safe repairs instead of only reporting them")
    return p.parse_args()


def main() -> None:
    print(verify(find_project_dir(), apply=_parse_args().apply))


if __name__ == "__main__":
    main()
