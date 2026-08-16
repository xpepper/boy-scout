"""What the anchors compare against.

An entry's fingerprint is a hash of the significant lines it points at. So
whether an anchor survives a reformat, and whether it stays put through a
rename of something nearby, is decided entirely by these two functions rather
than by anything in `anchors.py`.
"""
from pattern_analyzer import (
    detect_language,
    is_blank_or_comment,
    normalize_line,
    significant_lines,
)


class TestNormalizeLine:
    def test_collapses_whitespace_so_reformatting_is_not_a_rewrite(self):
        assert normalize_line("a  =   b") == normalize_line("a = b")

    def test_ignores_leading_indentation(self):
        assert normalize_line("        return value") == normalize_line("return value")

    def test_masks_string_literals(self):
        assert normalize_line('log("started")') == normalize_line('log("finished")')

    def test_masks_numbers(self):
        assert normalize_line("retry(3)") == normalize_line("retry(17)")

    def test_still_separates_different_code(self):
        assert normalize_line("total = price * rate") != normalize_line("total = price + rate")


class TestSignificantLines:
    def test_skips_blanks_and_comments(self):
        source = "value = 1\n\n# a note\nother = 2\n"

        assert significant_lines(source, "python") == [(1, "value = n"), (4, "other = n")]

    def test_reports_one_based_line_numbers(self):
        """The numbers go straight into an entry's `locations`, which humans
        read against their editor.
        """
        assert significant_lines("first = 1\n", "python")[0][0] == 1

    def test_uses_the_comment_marker_of_the_language(self):
        """`--` is a comment in Elm and `#` is not."""
        assert significant_lines("-- a note\nvalue = 1\n", "elm") == [(2, "value = n")]
        assert significant_lines("# a note\nvalue = 1\n", "elm") != [(2, "value = n")]

    def test_an_unknown_language_falls_back_to_the_common_markers(self):
        assert significant_lines("// a note\nvalue = 1\n", "unknown") == [(2, "value = n")]


class TestDetectLanguage:
    def test_maps_a_known_extension(self):
        assert detect_language("src/billing/invoice.py") == "python"

    def test_is_case_insensitive(self):
        assert detect_language("Main.PY") == "python"

    def test_an_unknown_extension_is_not_a_language(self):
        assert detect_language("notes.xyz") == "unknown"


class TestIsBlankOrComment:
    def test_blank_and_whitespace_only_lines(self):
        assert is_blank_or_comment("", "python")
        assert is_blank_or_comment("   \t ", "python")

    def test_a_trailing_comment_is_not_a_comment_line(self):
        assert not is_blank_or_comment("value = 1  # a note", "python")
