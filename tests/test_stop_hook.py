import importlib.util
import json
import re
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


def test_summary_labels_every_recordable_type_distinctly():
    """Every type the record CLI accepts needs its own label — otherwise the
    Stop hook renders it as a generic "Opportunity".
    """
    stop_hook = _load_stop_hook()
    spec = importlib.util.spec_from_file_location(
        "boy_scout_record", _REPO_ROOT / "skills" / "record-opportunity" / "record.py"
    )
    record = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(record)

    assert set(stop_hook.TYPE_LABEL) == record.VALID_TYPES
    assert len(set(stop_hook.TYPE_LABEL.values())) == len(stop_hook.TYPE_LABEL)


def test_summary_renders_new_types_with_their_own_label():
    stop_hook = _load_stop_hook()
    todos = [
        {**_todo(0), "type": "dead_code"},
        {**_todo(1), "type": "wrong_abstraction"},
    ]

    summary = stop_hook._format_summary(todos, open_count=2, triage_threshold=20)

    assert "[Dead code]" in summary
    assert "[Wrong abstraction]" in summary


def test_summary_names_agent_only_signals_for_what_they_are():
    """A skipped refactor step and a comprehension cost read very differently
    in a report; rendering either as a generic "Opportunity" throws away the
    only information the agent could contribute.
    """
    stop_hook = _load_stop_hook()
    todos = [
        {**_todo(0), "type": "skipped_refactor"},
        {**_todo(1), "type": "comprehension_cost"},
        {**_todo(2), "type": "self_inflicted_debt"},
        {**_todo(3), "type": "test_smell"},
        {**_todo(4), "type": "repeated_friction"},
    ]

    summary = stop_hook._format_summary(todos, open_count=5, triage_threshold=20)

    assert "[Skipped refactor]" in summary
    assert "[Comprehension cost]" in summary
    assert "[Self-inflicted debt]" in summary
    assert "[Test smell]" in summary
    assert "[Repeated friction]" in summary


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


def test_summary_names_the_command_that_acts_on_the_findings():
    """The report is the only moment the user is looking at the backlog. Ending
    it with "start a session whenever you're ready" leaves them to work out
    what that means; naming the command makes the next step one keystroke.
    """
    stop_hook = _load_stop_hook()

    summary = stop_hook._format_summary([_todo(0)], open_count=1, triage_threshold=20)

    assert "/boy-scout-session" in summary


def test_the_commands_the_summary_advertises_exist():
    commands = {path.stem for path in (_REPO_ROOT / "commands").glob("*.md")}
    stop_hook = _load_stop_hook()

    summary = stop_hook._format_summary([_todo(0)], open_count=99, triage_threshold=20)

    advertised = set(re.findall(r"/(boy-scout[a-z-]*)", summary))
    assert advertised, "the summary advertises no command at all"
    assert advertised <= commands, f"summary points at missing commands: {advertised - commands}"
