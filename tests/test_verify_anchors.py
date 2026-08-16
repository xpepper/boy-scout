"""Tests for the anchor repair pass (scripts/verify_anchors.py).

Knowing the backlog has drifted is only half of it. Two of the four answers are
mechanically safe to act on without a human: code that merely moved can be
re-pointed, and a finding whose file no longer exists cannot apply to anything.

The third — code that was rewritten in place — is exactly the case where a
machine must not decide. A rewrite can leave the original smell precisely where
it was, so closing on a fingerprint miss would delete real findings silently.
"""
import importlib.util
import os
import subprocess
from pathlib import Path

from todo_manager import add_todo, get_todo, list_todos

_REPO_ROOT = Path(__file__).parent.parent
_VERIFY = _REPO_ROOT / "scripts" / "verify_anchors.py"
_BIN = _REPO_ROOT / "bin" / "boy-scout-verify"

_ORIGINAL = "def load(path):\n    return open(path).read()\n"


def _load():
    spec = importlib.util.spec_from_file_location("boy_scout_verify", _VERIFY)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _write(tmp_path, content=_ORIGINAL, name="src/app.py"):
    path = tmp_path / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content)
    return path


def _record(tmp_path, file_path="src/app.py", start=1, end=2):
    return add_todo(str(tmp_path), {
        "type": "function_size",
        "file_path": file_path,
        "locations": [{"line_start": start, "line_end": end}],
        "description": "load does its own file handling",
        "severity": "medium",
        "source": "skill",
    })[0]


def test_a_dry_run_changes_nothing(tmp_path):
    """The default has to be safe to run out of curiosity."""
    source = _write(tmp_path)
    todo_id = _record(tmp_path)
    source.unlink()

    report = _load().verify(str(tmp_path), apply=False)

    assert "1" in report
    assert get_todo(str(tmp_path), todo_id)["dismissed"] is False


def test_applying_re_points_code_that_only_moved(tmp_path):
    _write(tmp_path)
    todo_id = _record(tmp_path)
    _write(tmp_path, "import os\nimport sys\n\n\n" + _ORIGINAL)

    _load().verify(str(tmp_path), apply=True)

    entry = get_todo(str(tmp_path), todo_id)
    assert entry["locations"] == [{"line_start": 5, "line_end": 6}]
    assert entry["dismissed"] is False


def test_a_re_pointed_item_verifies_clean_afterwards(tmp_path):
    """Relocation has to re-take the anchor too, or the same item is reported
    as moved forever and the repair never converges.
    """
    _write(tmp_path)
    _record(tmp_path)
    _write(tmp_path, "import os\nimport sys\n\n\n" + _ORIGINAL)

    _load().verify(str(tmp_path), apply=True)
    second = _load().verify(str(tmp_path), apply=True)

    assert "nothing to repair" in second.lower()


def test_applying_closes_findings_whose_file_is_gone(tmp_path):
    source = _write(tmp_path)
    todo_id = _record(tmp_path)
    source.unlink()

    _load().verify(str(tmp_path), apply=True)

    entry = get_todo(str(tmp_path), todo_id)
    assert entry["outcome"] == "stale"
    assert "no longer exists" in entry["resolution_note"]


def test_rewritten_code_is_reported_but_never_closed(tmp_path):
    """The judgment call stays with a person."""
    _write(tmp_path)
    todo_id = _record(tmp_path)
    _write(tmp_path, "def load(path):\n    with open(path) as f:\n        return f.read()\n")

    report = _load().verify(str(tmp_path), apply=True)

    assert get_todo(str(tmp_path), todo_id)["dismissed"] is False
    assert todo_id in report
    assert "re-read" in report or "review" in report.lower()


def test_closed_items_are_left_alone(tmp_path):
    """Verification is about the open backlog. Re-opening or re-closing history
    would rewrite decisions that were already made.
    """
    source = _write(tmp_path)
    todo_id = _record(tmp_path)
    from todo_manager import resolve_todo
    resolve_todo(str(tmp_path), todo_id, "wontfix", note="deliberate")
    source.unlink()

    _load().verify(str(tmp_path), apply=True)

    entry = get_todo(str(tmp_path), todo_id)
    assert entry["outcome"] == "wontfix"
    assert entry["resolution_note"] == "deliberate"


def test_a_clean_backlog_says_there_is_nothing_to_do(tmp_path):
    _write(tmp_path)
    _record(tmp_path)

    assert "nothing to repair" in _load().verify(str(tmp_path), apply=False).lower()


def test_the_wrapper_runs_without_any_claude_variables(tmp_path):
    (tmp_path / ".git").mkdir()
    source = _write(tmp_path)
    _record(tmp_path)
    source.unlink()

    result = subprocess.run(
        [str(_BIN)],
        cwd=str(tmp_path),
        capture_output=True,
        text=True,
        env={"PATH": os.environ["PATH"], "HOME": os.environ.get("HOME", "/tmp")},
    )

    assert result.returncode == 0, result.stderr
    assert "src/app.py" in result.stdout
    assert os.access(_BIN, os.X_OK)
    # Still a dry run: the wrapper must not close anything without --apply.
    assert list_todos(str(tmp_path)) != []
