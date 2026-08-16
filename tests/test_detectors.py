from detectors import (
    detect_duplication,
    detect_naming_clarity,
    detect_test_coverage_gap,
)

_DUPLICATED = '''\
def load_alpha(path):
    handle = open(path)
    raw = handle.read()
    handle.close()
    parsed = raw.split(",")
    cleaned = [item.strip() for item in parsed]
    return cleaned


def load_beta(path):
    handle = open(path)
    raw = handle.read()
    handle.close()
    parsed = raw.split(",")
    cleaned = [item.strip() for item in parsed]
    return cleaned
'''

_DISTINCT = '''\
def widen(value):
    scaled = value * 3
    return scaled


def narrow(text):
    trimmed = text.strip()
    return trimmed


def combine(left, right):
    joined = f"{left}:{right}"
    return joined


def explode(payload):
    pieces = payload.split("|")
    return pieces
'''


def test_duplication_detects_a_repeated_block(tmp_path):
    source = tmp_path / "loader.py"
    source.write_text(_DUPLICATED)

    findings = detect_duplication(str(source), {})

    assert len(findings) == 1
    assert findings[0]["type"] == "duplication"
    assert len(findings[0]["locations"]) == 2


def test_duplication_reports_nothing_for_distinct_blocks(tmp_path):
    source = tmp_path / "distinct.py"
    source.write_text(_DISTINCT)

    assert detect_duplication(str(source), {}) == []


def test_duplication_verifies_block_content_before_reporting(tmp_path, monkeypatch):
    """Bucketing by hash is only a candidate filter. With every window forced
    into the same bucket, the detector must still compare the actual text and
    report nothing rather than trust the hash.
    """
    source = tmp_path / "distinct.py"
    source.write_text(_DISTINCT)
    monkeypatch.setattr("builtins.hash", lambda _obj: 0)

    assert detect_duplication(str(source), {}) == []


_SELF_SIMILAR_RUN = '''\
def flatten(row):
    parts = []
    parts.append(row[0])
    parts.append(row[1])
    parts.append(row[2])
    parts.append(row[3])
    parts.append(row[4])
    parts.append(row[5])
    parts.append(row[6])
    parts.append(row[7])
    return parts


def summarise(rows):
    flattened = [flatten(row) for row in rows]
    widest = max(len(item) for item in flattened)
    return widest
'''


def test_duplication_never_reports_a_block_as_duplicating_itself(tmp_path):
    """Consecutive lines of the same shape make a sliding window match its own
    neighbour one line down, and the overlap check only ever compared a new
    pair against pairs already reported. Reporting "lines 3-10 and 4-11" is a
    self-overlap, not a copy-paste.
    """
    source = tmp_path / "flatten.py"
    source.write_text(_SELF_SIMILAR_RUN)

    findings = detect_duplication(str(source), {})

    assert findings == []


_TABLE_LITERAL = '''\
LANGUAGE_MAP = {
    ".rs": "rust",
    ".elm": "elm",
    ".js": "javascript",
    ".jsx": "javascript",
    ".ts": "typescript",
    ".tsx": "typescript",
    ".py": "python",
    ".go": "go",
    ".rb": "ruby",
    ".java": "java",
    ".c": "c",
    ".cpp": "cpp",
    ".cs": "csharp",
    ".swift": "swift",
    ".kt": "kotlin",
}


def detect_language(file_path):
    extension = Path(file_path).suffix.lower()
    return LANGUAGE_MAP.get(extension, "unknown")
'''

_PROSE_BLOCK = '''\
def build_prompt(item):
    return (
        "You are addressing one recorded opportunity."
        "Read the entry before you touch anything."
        "Run the tests first and confirm they pass."
        "Make the smallest change that resolves it."
        "Run the tests again."
        "Commit it on its own."
        "Do not fold it into another change."
        "Back out rather than pushing through."
        "Report what you did and what you verified."
        "Close the entry with an outcome."
        "Stop there."
        "Say so if it stopped being small."
    )
'''


def test_duplication_ignores_a_table_of_unrelated_literals(tmp_path):
    """Normalisation masks every string to the same token, so two halves of one
    lookup table are indistinguishable from a copy-paste. Masking is what buys
    the recall; a window carrying nothing but masked literals is where it costs
    more than it buys.
    """
    source = tmp_path / "languages.py"
    source.write_text(_TABLE_LITERAL)

    assert detect_duplication(str(source), {}) == []


def test_duplication_ignores_consecutive_lines_of_prose(tmp_path):
    """Same cause, the shape a user meets most: any two runs of a long prompt
    string normalise identically and were reported as duplicated.
    """
    source = tmp_path / "prompt.py"
    source.write_text(_PROSE_BLOCK)

    assert detect_duplication(str(source), {}) == []


def test_duplication_still_finds_a_real_copy_past_a_self_similar_run(tmp_path):
    """Rejecting self-overlap must not throw away the genuine match that lies
    further down the same hash bucket.
    """
    source = tmp_path / "loader.py"
    source.write_text(_DUPLICATED)

    findings = detect_duplication(str(source), {})

    assert len(findings) == 1
    first, second = findings[0]["locations"]
    assert first["line_end"] < second["line_start"]


def test_naming_does_not_flag_the_builtin_type_str(tmp_path):
    """`str2?` in the abbreviation list made every `Dict[str, str]` annotation a
    naming finding. It fired in all eleven source files of this repository. A
    builtin type is not a badly named variable.
    """
    source = tmp_path / "render.py"
    source.write_text(
        "from typing import Dict\n\n\n"
        "def render(rows: Dict[str, str]) -> Dict[str, str]:\n"
        "    return {key: value for key, value in rows.items()}\n"
    )

    assert detect_naming_clarity(str(source), {}) == []


def test_naming_looks_at_code_rather_than_at_strings_and_comments(tmp_path):
    """The scan ran over raw line text, so an abbreviation inside a message or
    a trailing comment read as an identifier that needed renaming.
    """
    source = tmp_path / "announce.py"
    source.write_text(
        "def announce(message):\n"
        '    print("writing to tmp before the swap")  # the buf is flushed here\n'
        "    return message\n"
    )

    assert detect_naming_clarity(str(source), {}) == []


def test_naming_still_flags_a_genuinely_abbreviated_binding(tmp_path):
    source = tmp_path / "loader.py"
    source.write_text(
        "def load(path):\n"
        "    tmp = read_bytes(path)\n"
        "    return tmp\n"
    )

    findings = detect_naming_clarity(str(source), {})

    assert len(findings) == 1
    assert "tmp" in findings[0]["description"]


def test_test_coverage_gap_is_recorded_as_a_file_level_finding(tmp_path):
    """A missing test file is a property of the whole file, so the finding
    must carry no line anchor rather than a fabricated lines 1-1 range.
    """
    source = tmp_path / "invoice.py"
    source.write_text("def apply_discount():\n    return 0\n")

    findings = detect_test_coverage_gap(str(source), {}, str(tmp_path))

    assert len(findings) == 1
    assert findings[0]["locations"] == []


def _source(tmp_path, rel_path, body="def apply_discount():\n    return 0\n"):
    path = tmp_path / rel_path
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(body)
    return path


def test_a_production_file_whose_name_merely_contains_test_is_not_a_test_file(tmp_path):
    """`latest_prices.py` contains "test"; `inspector.py` contains "spec". A
    substring check on the stem writes both off as test files, so the one
    detector users are told to enable first never reports on them.
    """
    for name in ("latest_prices.py", "inspector.py", "manifest_loader.py"):
        source = _source(tmp_path, name)

        findings = detect_test_coverage_gap(str(source), {}, str(tmp_path))

        assert len(findings) == 1, f"{name} was mistaken for a test file"


def test_real_test_files_are_still_exempt(tmp_path):
    for name in ("test_invoice.py", "invoice_test.py", "invoice.spec.ts", "invoice.test.ts"):
        source = _source(tmp_path, name)

        assert detect_test_coverage_gap(str(source), {}, str(tmp_path)) == []


def test_files_living_in_a_test_directory_are_exempt(tmp_path):
    """A helper under tests/ is test code even when its name says nothing."""
    source = _source(tmp_path, "tests/helpers.py")

    assert detect_test_coverage_gap(str(source), {}, str(tmp_path)) == []


def test_a_test_in_a_nested_test_tree_counts_as_coverage(tmp_path):
    """Mirrored test trees are the common layout. Only looking beside the file
    and in the top level of tests/ reports a gap that isn't there.
    """
    source = _source(tmp_path, "src/billing/invoice.py")
    _source(tmp_path, "tests/billing/test_invoice.py", "def test_apply_discount():\n    pass\n")

    assert detect_test_coverage_gap(str(source), {}, str(tmp_path)) == []


def test_a_hyphenated_script_finds_its_underscored_test(tmp_path):
    """Python module names cannot contain hyphens, so the test for
    `hooks/post-tool-use.py` has to be `tests/test_post_tool_use.py`. Looking
    only for `test_post-tool-use.py` reported the hook as untested — which it
    is not, and never was.
    """
    source = _source(tmp_path, "hooks/post-tool-use.py")
    _source(tmp_path, "tests/test_post_tool_use.py", "def test_hook():\n    pass\n")

    assert detect_test_coverage_gap(str(source), {}, str(tmp_path)) == []


def test_an_empty_package_marker_is_not_reported_as_untested(tmp_path):
    """`hooks/lib/__init__.py` has nothing in it to test."""
    source = _source(tmp_path, "hooks/lib/__init__.py", "")

    assert detect_test_coverage_gap(str(source), {}, str(tmp_path)) == []


def test_a_missing_test_is_still_reported_when_the_tree_exists(tmp_path):
    """The nested search must not turn into "any test file anywhere will do"."""
    source = _source(tmp_path, "src/billing/invoice.py")
    _source(tmp_path, "tests/billing/test_shipping.py", "def test_ship():\n    pass\n")

    assert len(detect_test_coverage_gap(str(source), {}, str(tmp_path))) == 1


_LONG_ELM = """\
module Compiler.Lower exposing (lowerExpr)


lowerExpr : Expr -> Core
lowerExpr expr =
    case expr of
        Literal value ->
            Core.Lit value

        Lambda param body ->
            Core.Abs param (lowerExpr body)

        Let bindings body ->
            Core.Let
                (List.map lowerBinding bindings)
                (lowerExpr body)

        App fn arg ->
            Core.App (lowerExpr fn) (lowerExpr arg)

        If cond yes no ->
            Core.Case (lowerExpr cond)
                [ ( truePattern, lowerExpr yes )
                , ( falsePattern, lowerExpr no )
                ]


small : Int -> Int
small n =
    n + 1
"""


def test_function_size_reports_long_elm_declarations(tmp_path):
    """Elm is second in the plugin's stated language priority, and the `elm`
    entry in FUNC_PATTERNS was unreachable: the detector bailed on anything
    that was not brace-delimited, which Elm is not.
    """
    from detectors import detect_function_size

    source = tmp_path / "Lower.elm"
    source.write_text(_LONG_ELM)

    findings = detect_function_size(str(source), {"detection": {"sensitivity": "balanced"}})

    assert len(findings) == 1
    assert "lowerExpr" in findings[0]["description"]


def test_function_size_leaves_short_elm_declarations_alone(tmp_path):
    from detectors import detect_function_size

    source = tmp_path / "Small.elm"
    source.write_text("module Small exposing (add)\n\n\nadd : Int -> Int -> Int\nadd a b =\n    a + b\n")

    assert detect_function_size(str(source), {}) == []


def test_elm_declaration_size_stops_at_the_next_declaration(tmp_path):
    """The offside rule is the only boundary Elm gives you: a declaration ends
    where the next thing starts in column 0. Running past it would make every
    declaration look like it spans the rest of the file.
    """
    from detectors import detect_function_size

    source = tmp_path / "Two.elm"
    source.write_text(
        "first : Int\nfirst =\n    1\n\n\nsecond : Int\nsecond =\n    2\n"
    )

    findings = detect_function_size(str(source), {"detection": {"sensitivity": "aggressive"}})

    assert findings == []
