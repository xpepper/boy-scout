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

TEST_INDICATORS = ("test", "spec", "mock", "fixture", "_test", ".test", ".spec")


def detect_language(file_path: str) -> str:
    ext = Path(file_path).suffix.lower()
    return LANGUAGE_MAP.get(ext, "unknown")


def read_content(file_path: str) -> Optional[str]:
    try:
        return Path(file_path).read_text(encoding="utf-8", errors="ignore")
    except Exception:
        return None


def is_test_file(file_path: str) -> bool:
    stem = Path(file_path).stem.lower()
    return any(indicator in stem for indicator in TEST_INDICATORS)


def is_blank_or_comment(line: str, language: str) -> bool:
    stripped = line.strip()
    if not stripped:
        return True
    prefixes = COMMENT_PREFIXES.get(language, ("//", "#", "--"))
    return any(stripped.startswith(p) for p in prefixes)


def normalize_line(line: str) -> str:
    """Strip and collapse whitespace; replace literals and numbers for comparison."""
    line = line.strip()
    line = re.sub(r'"[^"]*"', '"S"', line)
    line = re.sub(r"'[^']*'", "'S'", line)
    line = re.sub(r"\b\d+\b", "N", line)
    return line.lower()


def significant_lines(content: str, language: str) -> List[Tuple[int, str]]:
    """Return (1-based line number, normalized content) for non-blank, non-comment lines."""
    result = []
    for i, line in enumerate(content.splitlines()):
        if not is_blank_or_comment(line, language):
            result.append((i + 1, normalize_line(line)))
    return result
