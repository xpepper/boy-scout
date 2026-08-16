"""Tests for the backlog reader (scripts/list_backlog.py).

Everything that acts on the backlog — the slash commands, the refactoring
agent, a human at a terminal — needs to read it without parsing JSONL by hand.
Reading it by hand is how the wrong item gets addressed and how the wrong id
gets closed.
"""
import importlib.util
import json
import os
import subprocess
import sys
from pathlib import Path

from todo_manager import add_todo, resolve_todo

_REPO_ROOT = Path(__file__).parent.parent
_LIST = _REPO_ROOT / "scripts" / "list_backlog.py"
_BIN = _REPO_ROOT / "bin" / "boy-scout-list"


def _load():
    spec = importlib.util.spec_from_file_location("boy_scout_list", _LIST)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _add(project_dir, severity="medium", file_path="src/a.py", description="something", **extra):
    todo = {
        "type": "duplication",
        "file_path": file_path,
        "locations": [{"line_start": 10, "line_end": 20}],
        "description": description,
        "severity": severity,
        "source": "skill",
        **extra,
    }
    return add_todo(str(project_dir), todo)[0]


def test_empty_backlog_says_so_rather_than_printing_nothing(tmp_path):
    report = _load().render(str(tmp_path))

    assert "no open" in report.lower()


def test_open_items_are_listed_with_the_id_needed_to_close_them(tmp_path):
    todo_id = _add(tmp_path, description="JSON body parsing duplicated")

    report = _load().render(str(tmp_path))

    assert todo_id in report
    assert "JSON body parsing duplicated" in report
    assert "src/a.py" in report


def test_highest_severity_comes_first(tmp_path):
    _add(tmp_path, severity="low", file_path="src/low.py")
    _add(tmp_path, severity="high", file_path="src/high.py")
    _add(tmp_path, severity="medium", file_path="src/medium.py")

    report = _load().render(str(tmp_path))

    assert report.index("src/high.py") < report.index("src/medium.py") < report.index("src/low.py")


def test_closed_items_are_left_out_of_the_listing(tmp_path):
    todo_id = _add(tmp_path, file_path="src/done.py")
    resolve_todo(str(tmp_path), todo_id, "fixed")
    _add(tmp_path, file_path="src/open.py")

    report = _load().render(str(tmp_path))

    assert "src/open.py" in report
    assert "src/done.py" not in report


def test_the_report_answers_how_much_of_what_was_recorded_got_fixed(tmp_path):
    """The plugin's own fitness function. A backlog that cannot say what
    fraction of it was ever acted on is a graveyard with good intentions.
    """
    fixed = _add(tmp_path, file_path="src/one.py")
    declined = _add(tmp_path, file_path="src/two.py")
    _add(tmp_path, file_path="src/three.py")
    resolve_todo(str(tmp_path), fixed, "fixed")
    resolve_todo(str(tmp_path), declined, "wontfix")

    report = _load().render(str(tmp_path))

    assert "3 recorded" in report
    assert "1 fixed" in report
    assert "1 wontfix" in report
    assert "1 open" in report


def test_a_single_file_can_be_asked_about(tmp_path):
    """So a just-in-time check ("anything open in the file I am about to
    edit?") does not have to read the whole backlog.
    """
    _add(tmp_path, file_path="src/wanted.py")
    _add(tmp_path, file_path="src/other.py")

    report = _load().render(str(tmp_path), file_filter="src/wanted.py")

    assert "src/wanted.py" in report
    assert "src/other.py" not in report


def test_limit_caps_the_listing_without_hiding_that_it_did(tmp_path):
    for i in range(5):
        _add(tmp_path, file_path=f"src/f{i}.py")

    report = _load().render(str(tmp_path), limit=2)

    assert "3 more" in report


def test_json_output_is_machine_readable(tmp_path):
    todo_id = _add(tmp_path)

    payload = json.loads(_load().render(str(tmp_path), as_json=True))

    assert [item["id"] for item in payload["open"]] == [todo_id]
    assert payload["stats"]["recorded"] == 1
    assert payload["stats"]["open"] == 1


def test_wrapper_runs_without_any_claude_variables(tmp_path):
    (tmp_path / ".git").mkdir()
    _add(tmp_path, description="findable from a bare shell")

    result = subprocess.run(
        [str(_BIN)],
        cwd=str(tmp_path),
        capture_output=True,
        text=True,
        env={"PATH": os.environ["PATH"], "HOME": os.environ.get("HOME", "/tmp")},
    )

    assert result.returncode == 0, result.stderr
    assert "findable from a bare shell" in result.stdout
    assert os.access(_BIN, os.X_OK)


def _anchored_project(tmp_path, content="def load(path):\n    return open(path).read()\n"):
    source = tmp_path / "src" / "app.py"
    source.parent.mkdir(parents=True, exist_ok=True)
    source.write_text(content)
    return source


def test_an_item_whose_code_is_untouched_is_not_annotated(tmp_path):
    """Annotating everything is the same as annotating nothing."""
    _anchored_project(tmp_path)
    _add(tmp_path, file_path="src/app.py", description="load does its own IO")

    report = _load().render(str(tmp_path))

    assert "drifted" not in report
    assert "no longer" not in report


def test_an_item_whose_file_is_gone_says_so(tmp_path):
    source = _anchored_project(tmp_path)
    _add(tmp_path, file_path="src/app.py", description="load does its own IO")
    source.unlink()

    report = _load().render(str(tmp_path))

    assert "src/app.py" in report
    assert "no longer exists" in report


def test_an_item_whose_code_was_rewritten_is_flagged_but_not_closed(tmp_path):
    """Changed code is evidence, not proof: a rewrite can leave the smell right
    where it was. The item stays open and stays listed.
    """
    _anchored_project(tmp_path)
    todo_id = _add(tmp_path, file_path="src/app.py", description="load does its own IO",
                   locations=[{"line_start": 1, "line_end": 2}])
    _anchored_project(tmp_path, "def load(path):\n    with open(path) as f:\n        return f.read()\n")

    report = _load().render(str(tmp_path))

    assert todo_id in report
    assert "changed since" in report


def test_an_item_whose_code_moved_shows_where_it_is_now(tmp_path):
    _anchored_project(tmp_path)
    _add(tmp_path, file_path="src/app.py", description="load does its own IO",
         locations=[{"line_start": 1, "line_end": 2}])
    _anchored_project(tmp_path, "import os\nimport sys\n\n\ndef load(path):\n    return open(path).read()\n")

    report = _load().render(str(tmp_path))

    assert "moved" in report
    assert "5-6" in report


def test_the_report_counts_how_much_of_the_backlog_is_suspect(tmp_path):
    source = _anchored_project(tmp_path)
    _add(tmp_path, file_path="src/app.py", description="load does its own IO")
    source.unlink()

    report = _load().render(str(tmp_path))

    assert "1 of 1" in report


def test_stale_narrows_the_listing_to_what_needs_a_decision(tmp_path):
    source = _anchored_project(tmp_path)
    (tmp_path / "src" / "other.py").write_text("def fine():\n    return 1\n")
    _add(tmp_path, file_path="src/app.py", description="gone with the file")
    _add(tmp_path, file_path="src/other.py", description="never anchored at all")
    source.unlink()

    report = _load().render(str(tmp_path), stale_only=True)

    assert "gone with the file" in report
    assert "never anchored at all" not in report


def test_json_output_carries_the_anchor_status(tmp_path):
    source = _anchored_project(tmp_path)
    _add(tmp_path, file_path="src/app.py", description="load does its own IO")
    source.unlink()

    payload = json.loads(_load().render(str(tmp_path), as_json=True))

    assert payload["open"][0]["anchor_status"] == "missing"
    assert payload["stats"]["suspect"] == 1
