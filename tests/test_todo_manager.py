import json

import pytest

from todo_manager import add_todo, get_todo, list_todos, load_config, resolve_todo


def test_the_config_offers_only_the_triage_threshold(tmp_path):
    """`record-opportunity` is the only channel, and it is not configurable:
    what Claude records is a judgment, not a threshold. The one knob left
    governs when the Stop hook starts nudging about backlog size.
    """
    config = load_config(str(tmp_path))

    assert config == {"session": {"triage_threshold": 20}}


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


def test_add_todo_keeps_distinct_file_level_findings_of_same_type(tmp_path):
    """File-level findings carry no line anchor, so line ranges cannot be their
    identity — two different observations about the same file are two findings.
    """
    base = {
        "type": "custom",
        "file_path": "src/x.py",
        "locations": [],
        "source": "skill",
    }
    add_todo(str(tmp_path), {**base, "description": "Dead code in module header",
                             "severity": "low"})
    _, is_new = add_todo(str(tmp_path), {**base, "description": "Wrong abstraction: Repo leaks SQL",
                                         "severity": "high"})

    assert is_new is True
    assert len(list_todos(str(tmp_path))) == 2


def test_add_todo_dedupes_repeated_file_level_finding(tmp_path):
    """Re-detecting the same file-level issue (e.g. the test-coverage detector
    firing on every edit of the same file) must still reuse the open entry.
    """
    finding = {
        "type": "test_coverage",
        "file_path": "src/x.py",
        "locations": [],
        "description": "No test file found for x.py",
        "severity": "medium",
        "source": "hook",
    }
    first_id, _ = add_todo(str(tmp_path), finding)
    second_id, is_new = add_todo(str(tmp_path), dict(finding))

    assert is_new is False
    assert second_id == first_id
    assert len(list_todos(str(tmp_path))) == 1


def test_add_todo_dedupes_file_level_finding_ignoring_case_and_punctuation(tmp_path):
    base = {
        "type": "custom",
        "file_path": "src/x.py",
        "locations": [],
        "severity": "low",
        "source": "skill",
    }
    add_todo(str(tmp_path), {**base, "description": "Unused imports at top of module"})
    _, is_new = add_todo(str(tmp_path), {**base, "description": "unused imports at top of module."})

    assert is_new is False
    assert len(list_todos(str(tmp_path))) == 1


def test_add_todo_does_not_dedupe_file_level_against_line_anchored_finding(tmp_path):
    """A finding about the whole file and a finding about lines 1-1 are not the
    same claim, so neither may swallow the other.
    """
    base = {
        "type": "custom",
        "file_path": "src/x.py",
        "description": "Same words, different scope",
        "severity": "low",
        "source": "skill",
    }
    add_todo(str(tmp_path), {**base, "locations": []})
    _, is_new = add_todo(str(tmp_path), {**base, "locations": [{"line_start": 1, "line_end": 1}]})

    assert is_new is True
    assert len(list_todos(str(tmp_path))) == 2


def test_add_todo_still_dedupes_overlapping_lines_regardless_of_description(tmp_path):
    """Line-anchored findings keep line-range identity: the same region flagged
    twice with different wording is one issue.
    """
    base = {
        "type": "naming",
        "file_path": "src/x.py",
        "severity": "low",
        "source": "hook",
    }
    add_todo(str(tmp_path), {**base, "locations": [{"line_start": 10, "line_end": 12}],
                             "description": "first wording"})
    _, is_new = add_todo(str(tmp_path), {**base, "locations": [{"line_start": 11, "line_end": 13}],
                                         "description": "completely different wording"})

    assert is_new is False
    assert len(list_todos(str(tmp_path))) == 1


def _finding(**overrides):
    return {
        "type": "naming",
        "file_path": "src/a.py",
        "locations": [{"line_start": 10, "line_end": 12}],
        "description": "tmp doesn't say what it holds",
        "severity": "low",
        "source": "skill",
        **overrides,
    }


def test_resolve_todo_records_the_outcome_and_closes_the_item(tmp_path):
    """A fixed item is closed, but *how* it ended has to survive: 'fixed' is
    what makes recorded-vs-resolved computable, and `dismissed` alone can't
    tell a fix from a shrug.
    """
    todo_id, _ = add_todo(str(tmp_path), _finding())

    assert resolve_todo(str(tmp_path), todo_id, "fixed") is True

    assert list_todos(str(tmp_path)) == []
    closed = list_todos(str(tmp_path), include_dismissed=True)
    assert len(closed) == 1
    assert closed[0]["outcome"] == "fixed"
    assert closed[0]["dismissed"] is True
    assert closed[0]["resolved_at"] > 0


def test_resolve_todo_stores_an_optional_note(tmp_path):
    todo_id, _ = add_todo(str(tmp_path), _finding())

    resolve_todo(str(tmp_path), todo_id, "wontfix", note="Generated file, not ours to clean")

    closed = list_todos(str(tmp_path), include_dismissed=True)[0]
    assert closed["outcome"] == "wontfix"
    assert closed["resolution_note"] == "Generated file, not ours to clean"


def test_resolve_todo_leaves_other_entries_untouched(tmp_path):
    first_id, _ = add_todo(str(tmp_path), _finding())
    second_id, _ = add_todo(str(tmp_path), _finding(file_path="src/b.py"))

    resolve_todo(str(tmp_path), first_id, "fixed")

    still_open = list_todos(str(tmp_path))
    assert [t["id"] for t in still_open] == [second_id]
    assert "outcome" not in still_open[0]


def test_resolve_todo_preserves_lines_it_cannot_parse(tmp_path):
    """Resolution rewrites the whole store, so a line it can't read must be
    carried over rather than quietly dropped.
    """
    todo_id, _ = add_todo(str(tmp_path), _finding())
    path = tmp_path / ".claude" / "boy-scout-todos.jsonl"
    path.write_text(path.read_text() + "{ not json\n")

    resolve_todo(str(tmp_path), todo_id, "fixed")

    assert "{ not json" in path.read_text()


def test_resolve_todo_reports_an_unknown_id(tmp_path):
    add_todo(str(tmp_path), _finding())

    assert resolve_todo(str(tmp_path), "deadbeef", "fixed") is False


def test_resolve_todo_rejects_an_unknown_outcome(tmp_path):
    todo_id, _ = add_todo(str(tmp_path), _finding())

    with pytest.raises(ValueError):
        resolve_todo(str(tmp_path), todo_id, "sorted-out")


def test_resolved_item_no_longer_deduplicates_a_later_detection(tmp_path):
    """If the same smell comes back after being fixed, that is news, not a
    duplicate — the existing dismissal behaviour has to hold for outcomes too.
    """
    todo_id, _ = add_todo(str(tmp_path), _finding())
    resolve_todo(str(tmp_path), todo_id, "fixed")

    new_id, is_new = add_todo(str(tmp_path), _finding())

    assert is_new is True
    assert new_id != todo_id


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


def test_wontfix_suppresses_the_same_finding_being_recorded_again(tmp_path):
    """`wontfix` is a decision, and a decision has to stick. The detection hook
    re-runs over the whole file on every edit, so without this the item the
    project just declined comes straight back — and `wontfix` means nothing.
    """
    todo_id, _ = add_todo(str(tmp_path), _finding())
    resolve_todo(str(tmp_path), todo_id, "wontfix", note="we like it this way")

    same_id, is_new = add_todo(str(tmp_path), _finding())

    assert is_new is False
    assert same_id == todo_id
    assert list_todos(str(tmp_path), include_dismissed=True) != []
    assert len(list_todos(str(tmp_path), include_dismissed=True)) == 1


def test_wontfix_only_suppresses_the_finding_it_was_about(tmp_path):
    todo_id, _ = add_todo(str(tmp_path), _finding())
    resolve_todo(str(tmp_path), todo_id, "wontfix")

    other = {**_finding(), "file_path": "src/elsewhere.py"}
    _, is_new = add_todo(str(tmp_path), other)

    assert is_new is True


def test_get_todo_returns_the_entry_including_closed_ones(tmp_path):
    todo_id, _ = add_todo(str(tmp_path), _finding())
    resolve_todo(str(tmp_path), todo_id, "wontfix")

    entry = get_todo(str(tmp_path), todo_id)

    assert entry is not None
    assert entry["outcome"] == "wontfix"
    assert get_todo(str(tmp_path), "nosuchid") is None


def test_recorded_items_carry_an_anchor_to_the_code_they_describe(tmp_path):
    """Both channels record through add_todo, so anchoring belongs there —
    otherwise the hook's findings would be verifiable and the skill's would not.
    """
    source = tmp_path / "src" / "app.py"
    source.parent.mkdir(parents=True)
    source.write_text("def load(path):\n    return open(path).read()\n")

    add_todo(str(tmp_path), {
        "type": "function_size",
        "file_path": "src/app.py",
        "locations": [{"line_start": 1, "line_end": 2}],
        "description": "load does its own file handling",
        "severity": "low",
        "source": "skill",
    })

    entry = list_todos(str(tmp_path))[0]
    assert entry["anchor"]["fingerprint"]
    assert entry["anchor"]["file_hash"]


def test_recording_still_works_when_the_file_cannot_be_read(tmp_path):
    """A mistyped path, or one already deleted, must not fail the recording."""
    todo_id, is_new = add_todo(str(tmp_path), {
        "type": "custom",
        "file_path": "src/gone.py",
        "locations": [],
        "description": "recorded against nothing",
        "severity": "low",
        "source": "skill",
    })

    assert is_new is True
    assert "anchor" not in list_todos(str(tmp_path))[0]
