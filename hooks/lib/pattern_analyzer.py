"""
Common file analysis utilities shared by Boy Scout detectors.
"""
import re
from pathlib import Path
from typing import List, Optional, Tuple


LANGUAGE_MAP: dict[str, str] = {
    ".rs":   "rust",
    ".elm":  "elm",
    ".js":   "javascript",
    ".jsx":  "javascript",
    ".ts":   "typescript",
    ".tsx":  "typescript",
    ".py":   "python",
    ".go":   "go",
    ".rb":   "ruby",
    ".java": "java",
    ".c":    "c",
    ".h":    "c",
    ".cpp":  "cpp",
    ".hpp":  "cpp",
    ".cs":   "csharp",
    ".swift": "swift",
    ".kt":   "kotlin",
}

# Per-language single-line comment prefixes
COMMENT_PREFIXES: dict[str, tuple] = {
    "rust":       ("//",),
    "elm":        ("--",),
    "javascript": ("//",),
    "typescript": ("//",),
    "python":     ("#",),
    "go":         ("//",),
    "ruby":       ("#",),
    "java":       ("//",),
    "c":          ("//",),
    "cpp":        ("//",),
    "kotlin":     ("//",),
    "swift":      ("//",),
    "csharp":     ("//",),
}

# Test-ness is a property of how a file is named or where it lives, not of
# whether some test-ish word happens to appear inside its name: "latest_prices"
# contains "test" and "inspector" contains "spec".
TEST_NAME_PREFIXES = ("test_", "spec_", "mock_", "fixture_")
TEST_NAME_SUFFIXES = ("_test", "_spec", "_mock", "_fixture")
TEST_NAME_INFIXES = (".test", ".spec")  # invoice.test.ts, invoice.spec.ts
TEST_STEMS = ("test", "tests", "spec", "specs", "conftest", "mocks", "fixtures")
TEST_DIR_NAMES = frozenset(
    {"test", "tests", "spec", "specs", "__tests__", "__mocks__", "testing", "fixtures"}
)


def detect_language(file_path: str) -> str:
    ext = Path(file_path).suffix.lower()
    return LANGUAGE_MAP.get(ext, "unknown")


def read_content(file_path: str) -> Optional[str]:
    try:
        return Path(file_path).read_text(encoding="utf-8", errors="ignore")
    except Exception:
        return None


def is_test_file(file_path: str) -> bool:
    """Whether this file is test code rather than production code."""
    path = Path(file_path)
    name = path.name.lower()
    stem = path.stem.lower()

    if any(part.lower() in TEST_DIR_NAMES for part in path.parts[:-1]):
        return True
    # `invoice.test.ts` has stem `invoice.test`; strip trailing suffixes so the
    # prefix/suffix rules below see the same shape whatever the extension.
    if any(infix + "." in name for infix in TEST_NAME_INFIXES):
        return True
    if stem in TEST_STEMS:
        return True
    return stem.startswith(TEST_NAME_PREFIXES) or stem.endswith(TEST_NAME_SUFFIXES)


def is_blank_or_comment(line: str, language: str) -> bool:
    stripped = line.strip()
    if not stripped:
        return True
    prefixes = COMMENT_PREFIXES.get(language, ("//", "#", "--"))
    return any(stripped.startswith(p) for p in prefixes)


def code_only(line: str, language: str) -> str:
    """The part of a line that is code: literals emptied, trailing comment cut.

    Anything looking for identifiers has to work on this rather than on the raw
    line, or the word `tmp` inside a log message reads as a variable in need of
    a rename.
    """
    without_literals = re.sub(r'"[^"]*"', '""', line)
    without_literals = re.sub(r"'[^']*'", "''", without_literals)
    for prefix in COMMENT_PREFIXES.get(language, ("//", "#", "--")):
        head, marker, _ = without_literals.partition(prefix)
        if marker:
            without_literals = head
    return without_literals


def normalize_line(line: str) -> str:
    """Strip and collapse whitespace; replace literals and numbers for comparison."""
    line = line.strip()
    # Collapsing runs of whitespace is what makes this comparison survive
    # reformatting — `a  =  b` and `a = b` are the same line for both the
    # duplication detector and the staleness anchors.
    line = re.sub(r"\s+", " ", line)
    line = re.sub(r'"[^"]*"', '"S"', line)
    line = re.sub(r"'[^']*'", "'S'", line)
    line = re.sub(r"\b\d+\b", "N", line)
    return line.lower()


def _opens_multiline_string(line: str) -> Optional[Tuple[str, int]]:
    """The multi-line delimiter this line leaves open, and where it starts.

    Scans the line rather than searching it, because a delimiter can appear
    inside an ordinary string — `DELIMITERS = ('\"\"\"', \"'''\")` opens nothing.
    Searching finds the inner one, declares the rest of the file to be inside a
    docstring, and then reads the next real docstring as the end of it.
    """
    index, length = 0, len(line)
    while index < length:
        char = line[index]
        if char == "\\":
            index += 2
            continue
        if char not in "\"'`":
            index += 1
            continue

        triple = line[index : index + 3]
        if triple in ('"""', "'''"):
            closing = line.find(triple, index + 3)
            if closing == -1:
                return triple, index
            index = closing + 3
            continue

        cursor = index + 1
        while cursor < length and line[cursor] != char:
            cursor += 2 if line[cursor] == "\\" else 1
        if cursor >= length:
            # Only a backtick keeps a single-delimiter string open past the end
            # of the line; an unterminated quote is a syntax error, not a block.
            return (char, index) if char == "`" else None
        index = cursor + 1

    return None


def code_lines(content: str, language: str) -> List[Tuple[int, str]]:
    """(1-based line number, code part) for every line that carries code.

    Blanks, comments and the interior of multi-line strings are left out, so
    anything hunting for identifiers sees identifiers. A docstring explaining
    that `tmp` is a bad name is prose, not a variable called `tmp`.
    """
    result: List[Tuple[int, str]] = []
    open_delimiter: Optional[str] = None

    for line_number, raw_line in enumerate(content.splitlines(), start=1):
        line = raw_line
        if open_delimiter is not None:
            closing = line.find(open_delimiter)
            if closing == -1:
                continue
            line = line[closing + len(open_delimiter):]
            open_delimiter = None
        elif is_blank_or_comment(line, language):
            continue

        opened = _opens_multiline_string(line)
        if opened is not None:
            open_delimiter, start = opened
            line = line[:start]

        code = code_only(line, language)
        # What is left of a docstring opener or closer is quote characters.
        if code.strip(" \t\"'`"):
            result.append((line_number, code))

    return result


# The tokens `normalize_line` leaves behind in place of literals, with any
# string prefix attached: `f"..."` normalizes to `f"s"`, and that `f` is part
# of the literal rather than an identifier the line mentions.
_MASKED_TOKEN_RE = re.compile(r"(?:\b[a-z]{1,2})?(?:\"s\"|'s')|\bn\b")


def is_literal_only(normalized: str) -> bool:
    """Whether a normalized line carries no identifier — only masked literals.

    `normalize_line` replaces every string with `"S"` and every number with
    `N`, which is what lets near-copies survive edits. It also means unrelated
    text matches unrelated text: two halves of one prompt string, or two
    entries of one lookup table, normalize identically. A line with nothing
    left but masked literals carries no evidence either way.
    """
    return not re.search(r"[a-z_]", _MASKED_TOKEN_RE.sub("", normalized))


def significant_lines(content: str, language: str) -> List[Tuple[int, str]]:
    """Return (1-based line number, normalized content) for non-blank, non-comment lines."""
    result = []
    for i, line in enumerate(content.splitlines()):
        if not is_blank_or_comment(line, language):
            result.append((i + 1, normalize_line(line)))
    return result
