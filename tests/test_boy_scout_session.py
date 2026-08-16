import importlib.util
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).parent.parent


def _load_module():
    spec = importlib.util.spec_from_file_location(
        "boy_scout_session", _REPO_ROOT / "scripts" / "boy_scout_session.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _add_todo(project_dir, **overrides):
    sys.path.insert(0, str(_REPO_ROOT / "hooks" / "lib"))
    from todo_manager import add_todo

    todo = {
        "type": "custom",
        "file_path": "f.py",
        "locations": [{"line_start": 1, "line_end": 1}],
        "description": "x",
        "severity": "low",
        "source": "hook",
    }
    todo.update(overrides)
    add_todo(project_dir, todo)


def test_build_session_prompt_returns_none_when_no_open_items(tmp_path):
    boy_scout_session = _load_module()

    assert boy_scout_session.build_session_prompt(str(tmp_path)) is None


def test_build_session_prompt_summarizes_open_items(tmp_path):
    boy_scout_session = _load_module()
    _add_todo(str(tmp_path), file_path="a.py", severity="high")
    _add_todo(str(tmp_path), file_path="b.py", severity="low",
              locations=[{"line_start": 5, "line_end": 5}])

    prompt = boy_scout_session.build_session_prompt(str(tmp_path))

    assert prompt is not None
    assert "2" in prompt  # total open count somewhere in the prompt
    assert "boy-scout-todos.jsonl" in prompt
    assert "dismissed" in prompt.lower()  # instructs marking items done
    assert "do not push" in prompt.lower() or "don't push" in prompt.lower()


def test_build_session_prompt_ignores_dismissed_items(tmp_path):
    import json

    boy_scout_session = _load_module()
    _add_todo(str(tmp_path))

    path = tmp_path / ".claude" / "boy-scout-todos.jsonl"
    entries = [json.loads(line) for line in path.read_text().splitlines()]
    entries[0]["dismissed"] = True
    path.write_text("\n".join(json.dumps(e) for e in entries) + "\n")

    assert boy_scout_session.build_session_prompt(str(tmp_path)) is None
