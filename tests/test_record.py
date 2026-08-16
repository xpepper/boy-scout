"""End-to-end tests for the record-opportunity CLI (skills/record-opportunity/record.py)."""
import importlib.util
import json
import re
import subprocess
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).parent.parent
_RECORD = _REPO_ROOT / "skills" / "record-opportunity" / "record.py"
_RESOLVE = _REPO_ROOT / "skills" / "record-opportunity" / "resolve.py"
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


def _resolve(project_dir, **kwargs):
    """Invoke resolve.py as a subprocess and return its parsed JSON output."""
    argv = [sys.executable, str(_RESOLVE)]
    for key, value in kwargs.items():
        argv += [f"--{key.replace('_', '-')}", value]

    result = subprocess.run(
        argv,
        capture_output=True,
        text=True,
        env={"CLAUDE_PROJECT_DIR": str(project_dir), "PATH": "/usr/bin:/bin"},
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


def test_recording_a_now_fix_closes_the_item_it_creates(tmp_path):
    """A fix made on the spot is still recorded: it is the numerator of the
    recorded-vs-resolved ratio, and skipping it would make the plugin look
    like it only ever defers.
    """
    result = _record(
        tmp_path,
        type="naming",
        file="src/x.py",
        lines="34",
        description="tmp holds a validated Invoice; renamed to pending_invoice",
        severity="low",
        outcome="fixed",
    )

    assert result["is_new"] is True
    assert result["outcome"] == "fixed"
    entry = _read_entries(tmp_path)[0]
    assert entry["outcome"] == "fixed"
    assert entry["dismissed"] is True


def test_fixing_an_already_tracked_item_closes_that_item(tmp_path):
    """Cleaning up something the backlog already knows about must close the
    open entry, not leave it open beside a resolved twin.
    """
    recorded = _record(
        tmp_path,
        type="naming",
        file="src/x.py",
        lines="34",
        description="tmp doesn't say what it holds",
        severity="low",
    )
    fixed = _record(
        tmp_path,
        type="naming",
        file="src/x.py",
        lines="34",
        description="renamed tmp to pending_invoice",
        severity="low",
        outcome="fixed",
    )

    assert fixed["id"] == recorded["id"]
    entries = _read_entries(tmp_path)
    assert len(entries) == 1
    assert entries[0]["outcome"] == "fixed"


def test_outcome_note_is_stored(tmp_path):
    _record(
        tmp_path,
        type="dead_code",
        file="src/x.py",
        description="Commented-out v1 parser left below the v2 implementation",
        severity="low",
        outcome="fixed",
        note="Deleted the commented block; suite green",
    )

    entry = _read_entries(tmp_path)[0]
    assert entry["resolution_note"] == "Deleted the commented block; suite green"


def test_recording_without_an_outcome_leaves_the_item_open(tmp_path):
    _record(
        tmp_path,
        type="naming",
        file="src/x.py",
        description="tmp doesn't say what it holds",
        severity="low",
    )

    entry = _read_entries(tmp_path)[0]
    assert entry["dismissed"] is False
    assert "outcome" not in entry


AGENT_ONLY_SIGNALS = {
    "skipped_refactor",
    "comprehension_cost",
    "self_inflicted_debt",
    "test_smell",
    "repeated_friction",
}


def test_agent_only_signals_are_first_class_types():
    """These are the plugin's reason to exist: observations that only an agent
    that did the work can make, and that no linter or static detector can. If
    they collapse back into `custom` the plugin is just another smell scanner.
    """
    assert AGENT_ONLY_SIGNALS <= _load_record_module().VALID_TYPES


def test_agent_only_signals_are_recordable(tmp_path):
    for signal in sorted(AGENT_ONLY_SIGNALS):
        result = _record(
            tmp_path,
            type=signal,
            file=f"src/{signal}.py",
            description=f"Observation of kind {signal}",
            severity="low",
        )
        assert result["is_new"] is True


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


def test_skill_md_documents_every_flag_the_clis_accept():
    """A flag Claude is never told about may as well not exist."""
    skill_md = _SKILL_MD.read_text()

    for script in (_RECORD, _RESOLVE):
        flags = set(re.findall(r'add_argument\("(--[a-z-]+)"', script.read_text()))
        assert flags, f"no flags found in {script.name} — the pin itself is broken"
        for flag in flags:
            assert flag in skill_md, f"{script.name}'s {flag} is not documented in SKILL.md"


def test_skill_md_keeps_all_three_triage_decisions():
    """The gate is the point of the skill: recording everything makes a TODO
    graveyard, fixing everything derails the user's task. Losing any one of the
    three branches breaks the balance.
    """
    skill_md = _SKILL_MD.read_text()

    for decision in ("now", "next", "never"):
        assert f"`{decision}`" in skill_md, f"triage decision '{decision}' is not documented"


def test_skill_md_guards_the_now_path():
    """An on-the-spot fix is only safe under conditions the skill has to state:
    it happens on green, as its own commit, re-verified, and abandoned if it
    turns out not to be small.
    """
    skill_md = _SKILL_MD.read_text().lower()

    assert "on green" in skill_md
    assert "refactor(" in skill_md          # its own conventional commit
    assert "revert" in skill_md             # the escape hatch when it grows
    assert "--outcome fixed" in skill_md    # a now fix is still recorded


def _read_entries(project_dir):
    path = Path(project_dir) / ".claude" / "boy-scout-todos.jsonl"
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def test_recording_something_already_written_off_says_so(tmp_path):
    """Reusing the "already tracked" wording would tell Claude the item is
    sitting in the backlog when it was in fact declined — and Claude would
    keep re-recording it, or worse, go and fix it.
    """
    first = _record(
        tmp_path,
        type="naming",
        file="src/x.py",
        lines="12",
        description="single-letter loop variable",
        severity="low",
    )
    _resolve(tmp_path, id=first["id"], outcome="wontfix", note="idiomatic here")

    again = _record(
        tmp_path,
        type="naming",
        file="src/x.py",
        lines="12",
        description="single-letter loop variable",
        severity="low",
    )

    assert again["is_new"] is False
    assert again["id"] == first["id"]
    assert "wontfix" in again["message"]
