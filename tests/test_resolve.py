"""End-to-end tests for the resolve CLI (skills/record-opportunity/resolve.py)."""
import json
import subprocess
import sys
from pathlib import Path

from todo_manager import add_todo, list_todos

_REPO_ROOT = Path(__file__).parent.parent
_RESOLVE = _REPO_ROOT / "skills" / "record-opportunity" / "resolve.py"


def _run(project_dir, *args):
    return subprocess.run(
        [sys.executable, str(_RESOLVE), *args],
        capture_output=True,
        text=True,
        env={
            "CLAUDE_PROJECT_DIR": str(project_dir),
            "CLAUDE_PLUGIN_ROOT": str(_REPO_ROOT),
            "PATH": "/usr/bin:/bin",
        },
    )


def _tracked(project_dir):
    return add_todo(str(project_dir), {
        "type": "naming",
        "file_path": "src/x.py",
        "locations": [{"line_start": 34, "line_end": 34}],
        "description": "tmp doesn't say what it holds",
        "severity": "low",
        "source": "skill",
    })[0]


def test_resolving_by_id_closes_the_item_with_its_outcome(tmp_path):
    todo_id = _tracked(tmp_path)

    result = _run(tmp_path, "--id", todo_id, "--outcome", "fixed")

    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout)["outcome"] == "fixed"
    closed = list_todos(str(tmp_path), include_dismissed=True)[0]
    assert closed["outcome"] == "fixed"
    assert closed["dismissed"] is True


def test_resolving_stores_the_reason(tmp_path):
    todo_id = _tracked(tmp_path)

    _run(tmp_path, "--id", todo_id, "--outcome", "wontfix", "--note", "House style, deliberate")

    closed = list_todos(str(tmp_path), include_dismissed=True)[0]
    assert closed["resolution_note"] == "House style, deliberate"


def test_unknown_id_fails_loudly_instead_of_silently_doing_nothing(tmp_path):
    _tracked(tmp_path)

    result = _run(tmp_path, "--id", "deadbeef", "--outcome", "fixed")

    assert result.returncode != 0
    assert len(list_todos(str(tmp_path))) == 1


def test_unknown_outcome_is_rejected(tmp_path):
    todo_id = _tracked(tmp_path)

    result = _run(tmp_path, "--id", todo_id, "--outcome", "sorted-out")

    assert result.returncode != 0
    assert len(list_todos(str(tmp_path))) == 1
