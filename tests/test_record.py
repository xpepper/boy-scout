"""End-to-end tests for the record-opportunity CLI (skills/record-opportunity/record.py)."""
import importlib.util
import json
import subprocess
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).parent.parent
_RECORD = _REPO_ROOT / "skills" / "record-opportunity" / "record.py"
_SKILL_MD = _REPO_ROOT / "skills" / "record-opportunity" / "SKILL.md"
_SCHEMA = _REPO_ROOT / "schema" / "todo-item.json"


def _load_record_module():
    spec = importlib.util.spec_from_file_location("boy_scout_record", _RECORD)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _record(project_dir, **kwargs):
    """Invoke record.py as a subprocess and return its parsed JSON output."""
    argv = [sys.executable, str(_RECORD)]
    for key, value in kwargs.items():
        argv += [f"--{key.replace('_', '-')}", value]

    result = subprocess.run(
        argv,
        capture_output=True,
        text=True,
        env={
            "CLAUDE_PROJECT_DIR": str(project_dir),
            "CLAUDE_PLUGIN_ROOT": str(_REPO_ROOT),
            "PATH": "/usr/bin:/bin",
        },
    )
    assert result.returncode == 0, result.stderr
    return json.loads(result.stdout)


def test_distinct_file_level_findings_are_both_recorded(tmp_path):
    """Two unrelated file-level findings of the same type in the same file are
    two findings, not one. Without --lines there is no line anchor to tell them
    apart, so identity must fall back to the description.
    """
    first = _record(
        tmp_path,
        type="custom",
        file="src/x.py",
        description="Dead code in module header",
        severity="low",
    )
    second = _record(
        tmp_path,
        type="custom",
        file="src/x.py",
        description="Wrong abstraction: Repo leaks SQL",
        severity="high",
    )

    assert first["is_new"] is True
    assert second["is_new"] is True
    assert second["id"] != first["id"]


def test_repeating_the_same_file_level_finding_is_deduplicated(tmp_path):
    """The dedup feature still has to hold: re-recording the same observation
    must reuse the existing entry rather than bloat the backlog.
    """
    first = _record(
        tmp_path,
        type="test_coverage",
        file="src/x.py",
        description="No tests for Invoice.apply_discount()",
        severity="high",
    )
    second = _record(
        tmp_path,
        type="test_coverage",
        file="src/x.py",
        description="No tests for Invoice.apply_discount()",
        severity="high",
    )

    assert first["is_new"] is True
    assert second["is_new"] is False
    assert second["id"] == first["id"]


def test_file_level_finding_is_stored_without_a_line_anchor(tmp_path):
    """Omitting --lines must not fabricate a lines 1-1 anchor."""
    _record(
        tmp_path,
        type="custom",
        file="src/x.py",
        description="Module is a grab bag of unrelated helpers",
        severity="medium",
    )

    entries = _read_entries(tmp_path)
    assert entries[0]["locations"] == []


def test_line_range_is_preserved_when_given(tmp_path):
    _record(
        tmp_path,
        type="duplication",
        file="src/x.py",
        lines="42-58",
        description="Duplicated parsing logic",
        severity="medium",
    )

    entries = _read_entries(tmp_path)
    assert entries[0]["locations"] == [{"line_start": 42, "line_end": 58}]


def test_dead_code_and_wrong_abstraction_are_recordable_types(tmp_path):
    """SKILL.md tells Claude to record these; the CLI must accept them rather
    than force them into `custom`.
    """
    dead_code = _record(
        tmp_path,
        type="dead_code",
        file="src/x.py",
        description="Commented-out fallback branch left from the old parser",
        severity="low",
    )
    wrong_abstraction = _record(
        tmp_path,
        type="wrong_abstraction",
        file="src/x.py",
        description="Repo leaks SQL through its public interface",
        severity="high",
    )

    assert dead_code["is_new"] is True
    assert wrong_abstraction["is_new"] is True
    entries = _read_entries(tmp_path)
    assert {e["type"] for e in entries} == {"dead_code", "wrong_abstraction"}


def test_schema_enumerates_exactly_the_valid_types():
    """Guard against the taxonomy drifting apart across the repo again."""
    schema = json.loads(_SCHEMA.read_text())

    assert set(schema["properties"]["type"]["enum"]) == _load_record_module().VALID_TYPES


def test_schema_enumerates_exactly_the_valid_outcomes():
    """Same guard, one level down: the outcomes the store can hold and the
    outcomes the schema advertises must not drift apart either.
    """
    import todo_manager

    schema = json.loads(_SCHEMA.read_text())

    assert set(schema["properties"]["outcome"]["enum"]) == set(todo_manager.VALID_OUTCOMES)


def test_skill_md_documents_every_valid_type():
    skill_md = _SKILL_MD.read_text()

    for type_name in _load_record_module().VALID_TYPES:
        assert f"`{type_name}`" in skill_md, f"{type_name} is not documented in SKILL.md"


def _read_entries(project_dir):
    path = Path(project_dir) / ".claude" / "boy-scout-todos.jsonl"
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]
