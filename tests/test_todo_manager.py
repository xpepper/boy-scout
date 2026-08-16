import json

from todo_manager import add_todo, list_todos, load_config


def test_default_config_has_no_enabled_detectors_by_default(tmp_path):
    """Static detection is opt-in: the subsystem is on, but no pattern is
    selected until the user explicitly enables one. record-opportunity
    (Claude's semantic judgment) is the only active channel out of the box.
    """
    config = load_config(str(tmp_path))
    assert config["detection"]["patterns"] == []
    assert config["detection"]["enabled"] is True


def test_add_todo_persists_entry(tmp_path):
    todo_id, is_new = add_todo(str(tmp_path), {
        "type": "custom",
        "file_path": "src/a.py",
        "locations": [{"line_start": 1, "line_end": 1}],
        "description": "test",
        "severity": "low",
        "source": "skill",
    })

    assert is_new is True
    todos = list_todos(str(tmp_path))
    assert len(todos) == 1
    assert todos[0]["id"] == todo_id


def test_add_todo_deduplicates_overlapping_open_finding(tmp_path):
    first = {
        "type": "naming",
        "file_path": "src/a.py",
        "locations": [{"line_start": 10, "line_end": 12}],
        "description": "first pass",
        "severity": "low",
        "source": "hook",
    }
    second = {
        "type": "naming",
        "file_path": "src/a.py",
        "locations": [{"line_start": 11, "line_end": 13}],  # overlaps 10-12
        "description": "second pass, same underlying issue",
        "severity": "low",
        "source": "hook",
    }

    first_id, first_is_new = add_todo(str(tmp_path), first)
    second_id, second_is_new = add_todo(str(tmp_path), second)

    assert first_is_new is True
    assert second_is_new is False
    assert second_id == first_id
    assert len(list_todos(str(tmp_path))) == 1


def test_add_todo_does_not_dedupe_different_files(tmp_path):
    base = {
        "type": "naming",
        "locations": [{"line_start": 1, "line_end": 1}],
        "description": "x",
        "severity": "low",
        "source": "hook",
    }
    add_todo(str(tmp_path), {**base, "file_path": "a.py"})
    _, is_new = add_todo(str(tmp_path), {**base, "file_path": "b.py"})

    assert is_new is True
    assert len(list_todos(str(tmp_path))) == 2


def test_add_todo_does_not_dedupe_non_overlapping_locations_in_same_file(tmp_path):
    base = {
        "type": "naming",
        "file_path": "a.py",
        "description": "x",
        "severity": "low",
        "source": "hook",
    }
    add_todo(str(tmp_path), {**base, "locations": [{"line_start": 1, "line_end": 2}]})
    _, is_new = add_todo(str(tmp_path), {**base, "locations": [{"line_start": 50, "line_end": 52}]})

    assert is_new is True
    assert len(list_todos(str(tmp_path))) == 2


def test_add_todo_redetects_after_dismissal(tmp_path):
    finding = {
        "type": "naming",
        "file_path": "a.py",
        "locations": [{"line_start": 1, "line_end": 1}],
        "description": "x",
        "severity": "low",
        "source": "hook",
    }
    todo_id, _ = add_todo(str(tmp_path), finding)

    path = tmp_path / ".claude" / "boy-scout-todos.jsonl"
    entries = [json.loads(line) for line in path.read_text().splitlines()]
    entries[0]["dismissed"] = True
    path.write_text("\n".join(json.dumps(e) for e in entries) + "\n")

    new_id, is_new = add_todo(str(tmp_path), finding)

    assert is_new is True
    assert new_id != todo_id
