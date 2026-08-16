"""A backlog entry is a claim about code. Nothing checked whether it still held.

An item recorded against `auth.rs:88-104` still says that two commits later,
when those lines are something else entirely. The backlog therefore drifts into
fiction, and the tell is that nobody can distinguish the live entries from the
rotted ones — which is exactly when people stop trusting it and stop draining it.

These tests pin the four answers worth having: the file is gone, the code is
untouched, the code moved, or the code the entry described is no longer there.
"""
from pathlib import Path

from anchors import capture_anchor, check_anchor

_REPO_LIB = Path(__file__).parent.parent / "hooks" / "lib"

_MODULE = """\
import os


def load_config(path):
    handle = open(path)
    raw = handle.read()
    handle.close()
    return raw


def unrelated(value):
    return value * 2
"""


def _project(tmp_path, content=_MODULE, name="src/app.py"):
    path = tmp_path / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content)
    return path


def _todo(line_start=4, line_end=8, file_path="src/app.py"):
    return {
        "type": "function_size",
        "file_path": file_path,
        "locations": [{"line_start": line_start, "line_end": line_end}],
        "description": "load_config does its own file handling",
        "severity": "medium",
    }


def _anchored(tmp_path, todo=None):
    todo = todo or _todo()
    return {**todo, "anchor": capture_anchor(str(tmp_path), todo)}


def test_an_untouched_file_leaves_the_anchor_current(tmp_path):
    _project(tmp_path)

    assert check_anchor(str(tmp_path), _anchored(tmp_path))["status"] == "current"


def test_an_edit_elsewhere_in_the_file_leaves_the_anchor_current(tmp_path):
    """Any edit changes the file hash, so the fingerprint is what decides. A
    finding must not be called suspect because something unrelated moved.
    """
    _project(tmp_path)
    anchored = _anchored(tmp_path)

    _project(tmp_path, _MODULE.replace("return value * 2", "return value * 3"))

    assert check_anchor(str(tmp_path), anchored)["status"] == "current"


def test_code_pushed_down_the_file_is_reported_as_moved_with_its_new_range(tmp_path):
    """Insertion above a finding is the single most common way an anchor goes
    out of date, and the finding itself is still perfectly valid.
    """
    _project(tmp_path)
    anchored = _anchored(tmp_path)

    _project(tmp_path, "# a new header comment\nimport sys\n\n\n" + _MODULE)

    result = check_anchor(str(tmp_path), anchored)

    assert result["status"] == "moved"
    assert result["locations"] == [{"line_start": 8, "line_end": 12}]


def test_rewriting_the_described_code_is_reported_as_drifted(tmp_path):
    _project(tmp_path)
    anchored = _anchored(tmp_path)

    _project(tmp_path, _MODULE.replace(
        "    handle = open(path)\n    raw = handle.read()\n    handle.close()\n    return raw\n",
        "    with open(path) as handle:\n        return handle.read()\n",
    ))

    assert check_anchor(str(tmp_path), anchored)["status"] == "drifted"


def test_a_deleted_file_is_reported_as_missing(tmp_path):
    path = _project(tmp_path)
    anchored = _anchored(tmp_path)

    path.unlink()

    assert check_anchor(str(tmp_path), anchored)["status"] == "missing"


def test_a_deleted_file_is_missing_even_without_an_anchor(tmp_path):
    """Entries recorded before anchors existed still deserve the one check that
    needs no anchor at all.
    """
    path = _project(tmp_path)
    path.unlink()

    assert check_anchor(str(tmp_path), _todo())["status"] == "missing"


def test_an_entry_recorded_before_anchors_existed_is_not_called_suspect(tmp_path):
    """Old entries have no fingerprint. Flagging them all would bury the real
    ones on the first run and teach the user to ignore the whole column.
    """
    _project(tmp_path)

    assert check_anchor(str(tmp_path), _todo())["status"] == "unverifiable"


def test_a_file_level_finding_is_only_checked_for_existence(tmp_path):
    """"No test file for invoice.py" has no line anchor to verify. Saying it
    drifted because the file changed would be a guess dressed as a fact.
    """
    _project(tmp_path)
    todo = {**_todo(), "locations": []}
    anchored = {**todo, "anchor": capture_anchor(str(tmp_path), todo)}

    _project(tmp_path, _MODULE + "\n\ndef added():\n    pass\n")

    assert check_anchor(str(tmp_path), anchored)["status"] == "unverifiable"


def test_capturing_an_anchor_for_a_file_that_is_not_there_yields_nothing(tmp_path):
    """Claude can record against a path it mistyped, or one already deleted.
    That must not raise in the middle of recording.
    """
    assert capture_anchor(str(tmp_path), _todo(file_path="src/nope.py")) is None


def test_reformatting_alone_does_not_disturb_the_anchor(tmp_path):
    """Whitespace is not the claim; the code is. Reindenting a file must not
    light up the entire backlog.
    """
    _project(tmp_path)
    anchored = _anchored(tmp_path)

    _project(tmp_path, _MODULE.replace(
        "    handle = open(path)\n", "    handle  =  open(path)\n",
    ))

    assert check_anchor(str(tmp_path), anchored)["status"] == "current"


def test_a_comment_added_inside_the_block_moves_it_rather_than_breaking_it(tmp_path):
    """Comments are skipped when fingerprinting, so the code is still found —
    but it now ends a line lower, and saying so is the point.
    """
    _project(tmp_path)
    anchored = _anchored(tmp_path)

    _project(tmp_path, _MODULE.replace(
        "    handle = open(path)\n", "    # open it\n    handle = open(path)\n",
    ))

    result = check_anchor(str(tmp_path), anchored)

    assert result["status"] == "moved"
    assert result["locations"] == [{"line_start": 4, "line_end": 9}]


def test_the_anchor_is_stable_across_processes(tmp_path):
    """Anchors are written to disk and read back in another run, so the hash
    cannot be Python's built-in one — that is randomised per process.
    """
    import subprocess
    import sys

    _project(tmp_path)
    here = str(_REPO_LIB)
    script = (
        "import sys; sys.path.insert(0, %r);"
        "from anchors import capture_anchor;"
        "print(capture_anchor(%r, %r)['fingerprint'])"
        % (here, str(tmp_path), _todo())
    )
    first = subprocess.run([sys.executable, "-c", script], capture_output=True, text=True)
    second = subprocess.run([sys.executable, "-c", script], capture_output=True, text=True)

    assert first.returncode == 0, first.stderr
    assert first.stdout.strip() == second.stdout.strip()
    assert first.stdout.strip()
