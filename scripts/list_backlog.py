#!/usr/bin/env python3
"""
Read the Boy Scout backlog.

Prints the open opportunities, highest severity first, each with the id needed
to close it — and one line saying how much of everything ever recorded actually
got fixed. That ratio is the plugin's own fitness function: a backlog nobody
works through is a graveyard, and this is the number that tells them apart.

Usage:
    boy-scout-list                       # open items, highest severity first
    boy-scout-list --file src/billing.py # only items about one file
    boy-scout-list --limit 5             # the top few
    boy-scout-list --stale               # only items the code has moved past
    boy-scout-list --json                # machine-readable, for agents
"""
import argparse
import json
import sys
from collections import Counter
from pathlib import Path
from typing import Dict, List, Optional

_PLUGIN_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_PLUGIN_ROOT / "hooks" / "lib"))

from anchors import NEEDS_ATTENTION, annotate  # noqa: E402
from todo_manager import find_project_dir, list_todos  # noqa: E402

SEVERITY_ORDER = {"high": 0, "medium": 1, "low": 2}
SEVERITY_BADGE = {"high": "🔴", "medium": "🟡", "low": "🟢"}


def _rank(todo: Dict) -> tuple:
    """Highest severity first, then oldest first, so long-standing items rise
    instead of being buried by whatever was noticed most recently.
    """
    return (
        SEVERITY_ORDER.get(todo.get("severity", "low"), 3),
        todo.get("detected_at", 0),
    )


def _location(todo: Dict) -> str:
    path = todo.get("file_path", "unknown")
    locations = todo.get("locations") or []
    if not locations:
        return path
    first = locations[0]
    start, end = first.get("line_start"), first.get("line_end")
    return f"{path}:{start}" if start == end else f"{path}:{start}-{end}"


def collect(
    project_dir: str,
    file_filter: Optional[str] = None,
    stale_only: bool = False,
) -> Dict:
    """Return the open items (ranked, anchor-checked) and the counts."""
    every = list_todos(project_dir, include_dismissed=True)
    outcomes = Counter(
        entry.get("outcome", "closed") for entry in every if entry.get("dismissed")
    )

    open_items = sorted((e for e in every if not e.get("dismissed")), key=_rank)
    if file_filter:
        open_items = [e for e in open_items if e.get("file_path") == file_filter]

    open_items = annotate(project_dir, open_items)
    suspect = sum(1 for e in open_items if e["anchor_status"] in NEEDS_ATTENTION)
    if stale_only:
        open_items = [e for e in open_items if e["anchor_status"] in NEEDS_ATTENTION]

    return {
        "open": open_items,
        "stats": {
            "recorded": len(every),
            "open": len(every) - sum(outcomes.values()),
            "fixed": outcomes.get("fixed", 0),
            "wontfix": outcomes.get("wontfix", 0),
            "stale": outcomes.get("stale", 0),
            "suspect": suspect,
        },
    }


def _stats_line(stats: Dict) -> str:
    parts = [
        f"{stats['recorded']} recorded",
        f"{stats['fixed']} fixed",
        f"{stats['wontfix']} wontfix",
        f"{stats['stale']} stale",
        f"{stats['open']} open",
    ]
    return " · ".join(parts)


def _anchor_note(todo: Dict) -> Optional[str]:
    """One line saying how the entry stands against the code today.

    Only the cases worth acting on say anything. Annotating every item would
    make the column noise, and the user would learn to skip past it.
    """
    status = todo.get("anchor_status")
    if status == "missing":
        return f"✖ {todo.get('file_path')} no longer exists — close it as stale"
    if status == "drifted":
        return (
            f"⚠ the code at {_location(todo)} has changed since this was "
            "recorded — re-read it before acting"
        )
    if status == "moved":
        moved = {**todo, "locations": todo.get("current_locations")}
        return f"↻ moved: now at {_location(moved)}"
    return None


def _format_item(todo: Dict) -> List[str]:
    badge = SEVERITY_BADGE.get(todo.get("severity", "low"), "•")
    head = (
        f"{badge} [{todo.get('id', '????????')}] "
        f"{todo.get('type', 'custom')}  {_location(todo)}"
    )
    lines = [head, f"     {todo.get('description', '')}"]
    if todo.get("context"):
        lines.append(f"     ↪ {todo['context']}")
    note = _anchor_note(todo)
    if note:
        lines.append(f"     {note}")
    return lines


def render(
    project_dir: str,
    file_filter: Optional[str] = None,
    limit: Optional[int] = None,
    as_json: bool = False,
    stale_only: bool = False,
) -> str:
    data = collect(project_dir, file_filter=file_filter, stale_only=stale_only)
    open_items = data["open"]

    if as_json:
        shown = open_items if limit is None else open_items[:limit]
        return json.dumps({"open": shown, "stats": data["stats"]}, indent=2)

    scope = f" for {file_filter}" if file_filter else ""
    if not open_items:
        subject = "stale opportunities" if stale_only else "open opportunities"
        return (
            f"🏕️  Boy Scout: no {subject}{scope}.\n"
            f"    {_stats_line(data['stats'])}"
        )

    shown = open_items if limit is None else open_items[:limit]
    heading = "stale" if stale_only else "open"
    lines = [f"🏕️  Boy Scout backlog{scope}: {len(open_items)} {heading}", ""]
    for todo in shown:
        lines += _format_item(todo)
    if len(open_items) > len(shown):
        lines.append(f"  … and {len(open_items) - len(shown)} more")

    lines += ["", _stats_line(data["stats"])]
    suspect = data["stats"]["suspect"]
    if suspect and not stale_only:
        lines.append(
            f"⚠  {suspect} of {data['stats']['open']} open items no longer match "
            "the code they describe (`boy-scout-list --stale`)."
        )
    return "\n".join(lines)


def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="List open Boy Scout opportunities")
    p.add_argument("--file", default=None, help="Only items recorded against this path")
    p.add_argument("--limit", type=int, default=None, help="Show at most this many items")
    p.add_argument("--json", action="store_true", help="Machine-readable output")
    p.add_argument("--stale", action="store_true",
                   help="Only items that no longer match the code they describe")
    return p.parse_args()


def main() -> None:
    args = _parse_args()
    print(render(
        find_project_dir(),
        file_filter=args.file,
        limit=args.limit,
        as_json=args.json,
        stale_only=args.stale,
    ))


if __name__ == "__main__":
    main()
