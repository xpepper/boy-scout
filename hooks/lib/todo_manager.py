"""
Persistence layer for Boy Scout TODO items.

TODOs are stored as line-delimited JSON in .claude/boy-scout-todos.jsonl.
File locking prevents concurrent writes from parallel hook executions.
"""
import fcntl
import json
import os
import time
import uuid
from pathlib import Path
from typing import Dict, List, Optional


DEFAULT_CONFIG: Dict = {
    "detection": {
        "enabled": True,
        "patterns": ["duplication", "naming", "test_coverage", "function_size"],
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


def add_todo(project_dir: str, todo: Dict) -> str:
    """Append a TODO entry to the JSONL file. Returns the assigned id."""
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
    return todo_id


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
