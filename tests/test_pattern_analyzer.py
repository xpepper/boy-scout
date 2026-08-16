"""The line-level scanners every detector reads through.

They decide what counts as code, and each of the false positives that made
static detection too noisy to recommend came from one of them getting that
wrong. They were covered only through the detectors until now, which meant an
edge case could only be described in terms of a finding it happened to cause.
"""
from pattern_analyzer import code_lines, code_only, is_literal_only, normalize_line


def _numbered(source: str, language: str = "python"):
    return [line_number for line_number, _ in code_lines(source, language)]


class TestCodeOnly:
    def test_empties_string_literals(self):
        assert "tmp" not in code_only('log("writing to tmp")', "python")

    def test_cuts_a_trailing_comment(self):
        assert code_only("value = 1  # the buf is flushed", "python").strip() == "value = 1"

    def test_keeps_the_code_around_them(self):
        assert "staged" in code_only('staged = write("tmp")  # here', "python")

    def test_uses_the_comment_marker_of_the_language(self):
        """`--` opens a comment in Elm and nothing in Python."""
        assert code_only("value = 1 -- a note", "elm").strip() == "value = 1"
        assert code_only("value = 1 -- a note", "python").strip() == "value = 1 -- a note"


class TestCodeLines:
    def test_skips_blanks_and_comments(self):
        assert _numbered("value = 1\n\n# a note\nother = 2\n") == [1, 4]

    def test_skips_the_interior_of_a_docstring(self):
        source = (
            "def stage(path):\n"
            '    """Write to a tmp file.\n'
            "\n"
            "    The buf is flushed first.\n"
            '    """\n'
            "    return path\n"
        )

        assert _numbered(source) == [1, 6]

    def test_a_single_line_docstring_leaves_the_scanner_closed(self):
        source = 'def stage(path):\n    """Write it."""\n    return path\n\n\nother = 1\n'

        assert _numbered(source) == [1, 3, 6]

    def test_a_quote_inside_a_string_does_not_open_a_block(self):
        """`DELIMITERS = ('\"\"\"',)` is a tuple, not an unterminated docstring.
        Reading it as one swallows the rest of the file.
        """
        source = 'DELIMITERS = (\'"""\', "`")\nvalue = 1\nother = 2\n'

        assert _numbered(source) == [1, 2, 3]

    def test_a_backtick_block_spans_lines_in_javascript(self):
        """Line 3 closes the template literal and still carries the `;`."""
        source = "const query = `\n  SELECT 1\n`;\nconst total = 2;\n"

        assert _numbered(source, "javascript") == [1, 3, 4]

    def test_reports_one_based_line_numbers(self):
        assert _numbered("first = 1\n") == [1]


class TestIsLiteralOnly:
    def test_a_table_entry_carries_no_identifier(self):
        assert is_literal_only(normalize_line('    ".rs": "rust",'))

    def test_a_line_of_prose_carries_no_identifier(self):
        assert is_literal_only(normalize_line('    "Run the tests first."'))

    def test_an_interpolation_prefix_is_part_of_the_literal(self):
        assert is_literal_only(normalize_line('    f"There are {count} entries."'))

    def test_a_call_is_not_literal_only(self):
        assert not is_literal_only(normalize_line('    log("writing to tmp")'))

    def test_an_assignment_of_a_literal_is_not_literal_only(self):
        assert not is_literal_only(normalize_line('    name = "rust"'))
