import importlib.util
import json
import subprocess
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).parent.parent


def _load_stop_hook():
    """stop-hook.py has a hyphen in its filename, so it can't be imported
    with a normal `import` statement — load it by file path instead.
    """
    spec = importlib.util.spec_from_file_location(
        "boy_scout_stop_hook", _REPO_ROOT / "hooks" / "stop-hook.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _todo(i):
    return {"type": "custom", "file_path": f"f{i}.py", "description": "x", "severity": "low"}


def test_summary_adds_triage_nudge_when_backlog_exceeds_threshold():
    stop_hook = _load_stop_hook()
    new_todos = [_todo(i) for i in range(3)]

    summary = stop_hook._format_summary(new_todos, open_count=25, triage_threshold=20)

    assert "25" in summary
    assert "triage" in summary.lower() or "grown" in summary.lower()


def test_summary_omits_triage_nudge_below_threshold():
    stop_hook = _load_stop_hook()
    new_todos = [_todo(0)]

    summary = stop_hook._format_summary(new_todos, open_count=5, triage_threshold=20)

    assert "grown" not in summary.lower()
    assert "triage" not in summary.lower()


def test_stop_hook_stays_silent_when_no_new_todos_even_over_threshold(tmp_path):
    """Regression guard: the nudge must not turn into a nag on every Stop
    event once the backlog crosses the threshold — it should only ride
    along with an actual new-findings summary.
    """
    sys.path.insert(0, str(_REPO_ROOT / "hooks" / "lib"))
    from todo_manager import add_todo, set_last_surfaced  # noqa: E402

    for i in range(25):
        add_todo(str(tmp_path), {
            "type": "custom",
            "file_path": f"f{i}.py",
            "locations": [{"line_start": 1, "line_end": 1}],
            "description": "x",
            "severity": "low",
            "source": "hook",
        })
    set_last_surfaced(str(tmp_path))  # mark all 25 as already surfaced

    result = subprocess.run(
        [sys.executable, str(_REPO_ROOT / "hooks" / "stop-hook.py")],
        input="{}",
        capture_output=True,
        text=True,
        env={"CLAUDE_PROJECT_DIR": str(tmp_path), "PATH": "/usr/bin:/bin"},
    )

    output = json.loads(result.stdout)
    assert "systemMessage" not in output
