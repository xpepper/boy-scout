"""
Persistence layer for Boy Scout TODO items.

TODOs are stored as line-delimited JSON in .claude/boy-scout-todos.jsonl.
File locking prevents concurrent writes from parallel hook executions.
"""
import fcntl
import json
import os
import re
import time
import uuid
from pathlib import Path
from typing import Dict, List, Optional, Tuple


DEFAULT_CONFIG: Dict = {
    "detection": {
        "enabled": True,
        # Static detectors are opt-in: record-opportunity (Claude's semantic
        # judgment) is the sole active channel until the user explicitly
        # enables one or more of duplication/naming/test_coverage/function_size
        # here. Mechanical thresholds are noisy signal; see README.
        "patterns": [],
        "sensitivity": "balanced",
        "ignore_paths": [
            "vendor/",
            "dist/",
            "*.generated.ts",
            "node_modules/",
            "target/",
            ".git/",
        ],
        "ignore_tests": False,
    },
    "output": {
        "suppress_transcript": True,
    },
    "session": {
        "auto_clear": False,
        # When the open (non-dismissed) backlog exceeds this size, the Stop
        # hook adds a triage nudge to its summary instead of letting the
        # backlog grow silently forever.
        "triage_threshold": 20,
    },
}


def _claude_dir(project_dir: str) -> Path:
    d = Path(project_dir) / ".claude"
    d.mkdir(exist_ok=True)
    return d


def _todos_path(project_dir: str) -> Path:
    return _claude_dir(project_dir) / "boy-scout-todos.jsonl"


def _meta_path(project_dir: str) -> Path:
    return _claude_dir(project_dir) / "boy-scout-meta.json"


def _config_path(project_dir: str) -> Path:
    return _claude_dir(project_dir) / "boy-scout-config.json"


def load_config(project_dir: str) -> Dict:
    """Load config, auto-creating defaults if absent."""
    path = _config_path(project_dir)
    if not path.exists():
        with open(path, "w") as f:
            json.dump(DEFAULT_CONFIG, f, indent=2)
        return _deep_copy(DEFAULT_CONFIG)

    try:
        with open(path) as f:
            user = json.load(f)
    except (json.JSONDecodeError, OSError):
        return _deep_copy(DEFAULT_CONFIG)

    # Deep merge: user values override defaults section-by-section
    config = _deep_copy(DEFAULT_CONFIG)
    for section, value in user.items():
        if isinstance(value, dict) and section in config and isinstance(config[section], dict):
            config[section] = {**config[section], **value}
        else:
            config[section] = value
    return config


def _deep_copy(d: Dict) -> Dict:
    return json.loads(json.dumps(d))


def _locations_overlap(a: List[Dict], b: List[Dict]) -> bool:
    return any(
        loc_a["line_start"] <= loc_b["line_end"] and loc_b["line_start"] <= loc_a["line_end"]
        for loc_a in a
        for loc_b in b
    )


_NON_ALNUM = re.compile(r"[^0-9a-z]+")


def _normalize_description(text: str) -> str:
    """Reduce a description to its words, so that trivial differences in case,
    punctuation or spacing don't make the same observation look like a new one.
    """
    return _NON_ALNUM.sub(" ", str(text).casefold()).strip()


def _same_finding(entry: Dict, todo: Dict) -> bool:
    """Whether two findings for the same type + file describe the same issue.

    Line-anchored findings are identified by their line range: the same region
    flagged again is the same issue however it is worded. File-level findings
    have no line anchor to compare, so they are identified by their
    description instead — otherwise every file-level finding in a file would
    collide with every other one of the same type.
    """
    entry_locations = entry.get("locations") or []
    todo_locations = todo.get("locations") or []

    if not entry_locations and not todo_locations:
        return _normalize_description(entry.get("description", "")) == _normalize_description(
            todo.get("description", "")
        )
    if not entry_locations or not todo_locations:
        return False
    return _locations_overlap(entry_locations, todo_locations)


def _find_open_duplicate(project_dir: str, todo: Dict) -> Optional[str]:
    """Return the id of an existing, open (non-dismissed) TODO describing the
    same issue in the same file, if any.
    """
    for entry in list_todos(project_dir):
        if entry.get("type") != todo.get("type"):
            continue
        if entry.get("file_path") != todo.get("file_path"):
            continue
        if _same_finding(entry, todo):
            return entry.get("id")
    return None


def add_todo(project_dir: str, todo: Dict) -> Tuple[str, bool]:
    """Append a TODO entry to the JSONL file, unless an equivalent open entry
    already exists (same type + file, and either an overlapping line range or —
    for file-level findings — the same description) — repeated detections of
    the same underlying issue shouldn't bloat the backlog.

    Returns (id, is_new): is_new is False when an existing entry was reused.
    """
    existing_id = _find_open_duplicate(project_dir, todo)
    if existing_id is not None:
        return existing_id, False

    path = _todos_path(project_dir)
    todo_id = uuid.uuid4().hex[:8]
    entry = {
        "id": todo_id,
        "detected_at": time.time(),
        "dismissed": False,
        **todo,
    }
    with open(path, "a") as f:
        fcntl.flock(f, fcntl.LOCK_EX)
        try:
            f.write(json.dumps(entry) + "\n")
        finally:
            fcntl.flock(f, fcntl.LOCK_UN)
    return todo_id, True


VALID_OUTCOMES = ("fixed", "wontfix", "stale")


def resolve_todo(
    project_dir: str,
    todo_id: str,
    outcome: str,
    note: Optional[str] = None,
) -> bool:
    """Close a TODO entry, recording *how* it ended.

    `dismissed` alone cannot tell a fix from a shrug, so the plugin cannot say
    what fraction of what it recorded actually got improved. `outcome` is that
    missing half:

      fixed    the code was changed and verified
      wontfix  a real observation the project has decided not to act on
      stale    no longer applies (the code moved on, or the finding was wrong)

    `dismissed` is set too, so every existing reader keeps treating a resolved
    item as closed without knowing about outcomes.

    Returns True if the entry was found and updated, False if no entry has that
    id. Raises ValueError for an unknown outcome.
    """
    if outcome not in VALID_OUTCOMES:
        raise ValueError(
            f"unknown outcome {outcome!r}; expected one of {', '.join(VALID_OUTCOMES)}"
        )

    path = _todos_path(project_dir)
    if not path.exists():
        return False

    # Read-modify-write under the same exclusive lock add_todo appends with, so
    # a concurrent hook can't lose an entry. The file is rewritten in place
    # (never replaced) to keep the lock meaningful.
    with open(path, "r+") as f:
        fcntl.flock(f, fcntl.LOCK_EX)
        try:
            # Lines that don't parse are carried over untouched: rewriting the
            # store is no excuse for dropping data we merely failed to read.
            lines = [line for line in f.read().splitlines() if line.strip()]
            found = False
            for i, line in enumerate(lines):
                try:
                    entry = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if entry.get("id") != todo_id:
                    continue
                entry["dismissed"] = True
                entry["outcome"] = outcome
                entry["resolved_at"] = time.time()
                if note:
                    entry["resolution_note"] = note
                lines[i] = json.dumps(entry)
                found = True

            if found:
                f.seek(0)
                f.write("".join(line + "\n" for line in lines))
                f.truncate()
        finally:
            fcntl.flock(f, fcntl.LOCK_UN)
    return found


def list_todos(
    project_dir: str,
    since: Optional[float] = None,
    include_dismissed: bool = False,
) -> List[Dict]:
    """Return TODO entries, optionally filtered by timestamp and dismissed status."""
    path = _todos_path(project_dir)
    if not path.exists():
        return []

    todos = []
    with open(path) as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                entry = json.loads(line)
            except json.JSONDecodeError:
                continue
            if not include_dismissed and entry.get("dismissed"):
                continue
            if since is not None and entry.get("detected_at", 0) <= since:
                continue
            todos.append(entry)
    return todos


def get_last_surfaced(project_dir: str) -> float:
    """Return the Unix timestamp of the last Stop hook run (0.0 if never)."""
    path = _meta_path(project_dir)
    if not path.exists():
        return 0.0
    try:
        with open(path) as f:
            return json.load(f).get("last_surfaced_at", 0.0)
    except (json.JSONDecodeError, OSError):
        return 0.0


def set_last_surfaced(project_dir: str) -> None:
    """Record the current time as the last surface timestamp."""
    path = _meta_path(project_dir)
    with open(path, "w") as f:
        json.dump({"last_surfaced_at": time.time()}, f)
