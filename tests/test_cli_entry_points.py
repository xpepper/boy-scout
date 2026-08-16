"""The CLIs have to work in the environment Claude actually runs them in.

`$CLAUDE_PLUGIN_ROOT` and `$CLAUDE_PROJECT_DIR` are exported to *hooks*. They
are not exported to the Bash tool, which is where the `record-opportunity`
skill runs its commands. A command written as
`python3 "$CLAUDE_PLUGIN_ROOT/…/record.py"` therefore expands to
`python3 "/…/record.py"` and fails — silently, from the user's point of view,
because the skill only prints one understated line either way.

So the entry points must locate both the plugin and the project themselves.
"""
import json
import os
import subprocess
import sys
from pathlib import Path

import todo_manager

_REPO_ROOT = Path(__file__).parent.parent
_BIN = _REPO_ROOT / "bin"

# The Bash tool's environment, near enough: no CLAUDE_* variables at all.
_BARE_ENV = {"PATH": os.environ["PATH"], "HOME": os.environ.get("HOME", "/tmp")}


def _run(argv, cwd, env=None):
    return subprocess.run(
        argv, cwd=str(cwd), capture_output=True, text=True, env=env or _BARE_ENV
    )


def _entries(project_dir):
    path = Path(project_dir) / ".claude" / "boy-scout-todos.jsonl"
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def test_wrappers_are_executable():
    for wrapper in ("boy-scout-record", "boy-scout-resolve"):
        path = _BIN / wrapper
        assert path.exists(), f"{wrapper} is missing from bin/"
        assert os.access(path, os.X_OK), f"{wrapper} is not executable"


def test_record_wrapper_works_without_any_claude_variables(tmp_path):
    """The whole point: a bare `boy-scout-record` call from the project root."""
    (tmp_path / ".git").mkdir()

    result = _run(
        [
            str(_BIN / "boy-scout-record"),
            "--type", "naming",
            "--file", "src/x.py",
            "--description", "tmp holds a validated PendingInvoice",
            "--severity", "low",
        ],
        cwd=tmp_path,
    )

    assert result.returncode == 0, result.stderr
    assert len(_entries(tmp_path)) == 1


def test_record_wrapper_writes_to_the_project_root_from_a_subdirectory(tmp_path):
    """Claude's shell is not always sitting at the project root. Falling back to
    the working directory would scatter a second backlog under src/.
    """
    (tmp_path / ".git").mkdir()
    nested = tmp_path / "src" / "billing"
    nested.mkdir(parents=True)

    result = _run(
        [
            str(_BIN / "boy-scout-record"),
            "--type", "test_coverage",
            "--file", "src/billing/invoice.py",
            "--description", "apply_discount() has no tests",
            "--severity", "high",
        ],
        cwd=nested,
    )

    assert result.returncode == 0, result.stderr
    assert len(_entries(tmp_path)) == 1
    assert not (nested / ".claude").exists()


def test_resolve_wrapper_closes_an_item_without_any_claude_variables(tmp_path):
    (tmp_path / ".git").mkdir()
    recorded = _run(
        [
            str(_BIN / "boy-scout-record"),
            "--type", "duplication",
            "--file", "src/a.py",
            "--lines", "10-20",
            "--description", "duplicated parsing",
            "--severity", "medium",
        ],
        cwd=tmp_path,
    )
    assert recorded.returncode == 0, recorded.stderr
    todo_id = json.loads(recorded.stdout)["id"]

    result = _run(
        [str(_BIN / "boy-scout-resolve"), "--id", todo_id, "--outcome", "fixed"],
        cwd=tmp_path,
    )

    assert result.returncode == 0, result.stderr
    assert _entries(tmp_path)[0]["outcome"] == "fixed"


def test_explicit_project_dir_still_wins(tmp_path):
    """Hooks do export CLAUDE_PROJECT_DIR, and it has to keep taking priority
    over anything inferred from the working directory.
    """
    project = tmp_path / "project"
    project.mkdir()
    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()
    (elsewhere / ".git").mkdir()

    env = {**_BARE_ENV, "CLAUDE_PROJECT_DIR": str(project)}
    result = _run(
        [
            str(_BIN / "boy-scout-record"),
            "--type", "custom",
            "--file", "x.py",
            "--description", "somewhere specific",
            "--severity", "low",
        ],
        cwd=elsewhere,
        env=env,
    )

    assert result.returncode == 0, result.stderr
    assert len(_entries(project)) == 1
    assert not (elsewhere / ".claude").exists()


def test_project_dir_falls_back_to_the_working_directory(tmp_path):
    """No marker anywhere up the tree is not a reason to fail or to walk up to
    the filesystem root: record where the caller is standing.
    """
    assert todo_manager.find_project_dir(str(tmp_path)) in (
        str(tmp_path), str(tmp_path.resolve())
    )


def test_project_dir_prefers_the_nearest_marker(tmp_path):
    (tmp_path / ".git").mkdir()
    inner = tmp_path / "packages" / "web"
    inner.mkdir(parents=True)
    (inner / ".claude").mkdir()

    assert todo_manager.find_project_dir(str(inner)) == str(inner.resolve())
