#!/usr/bin/env python3
"""
Boy Scout PostToolUse hook.

Fires after every Write or Edit tool call. Reads the modified file path,
runs all configured refactoring detectors, and appends findings to
.claude/boy-scout-todos.jsonl. Output is always suppressed from the
Claude transcript so this runs silently in the background.
"""
import fnmatch
import json
import os
import sys
from pathlib import Path

# Resolve lib directory relative to this script so the hook works regardless
# of where $CLAUDE_PLUGIN_ROOT resolves at runtime.
_LIB = Path(__file__).parent / "lib"
sys.path.insert(0, str(_LIB))

from todo_manager import add_todo, load_config
from detectors import run_all_detectors
from pattern_analyzer import detect_language


MAX_FILE_BYTES = 500 * 1024  # 500 KB

CODE_EXTENSIONS = frozenset({
    ".rs", ".elm",
    ".js", ".jsx", ".ts", ".tsx",
    ".py",
    ".go", ".rb", ".java",
    ".c", ".h", ".cpp", ".hpp",
    ".cs", ".swift", ".kt", ".scala",
    ".sh", ".bash", ".zsh",
    ".md", ".rst", ".txt",  # documentation files are fair game
})

BINARY_EXTENSIONS = frozenset({
    ".png", ".jpg", ".jpeg", ".gif", ".svg", ".ico",
    ".woff", ".woff2", ".ttf", ".eot",
    ".zip", ".tar", ".gz", ".bz2", ".xz",
    ".bin", ".exe", ".dll", ".so", ".dylib",
    ".pdf", ".doc", ".docx", ".xls", ".xlsx",
})


def _is_binary_content(path: str) -> bool:
    try:
        with open(path, "rb") as f:
            return b"\x00" in f.read(8192)
    except OSError:
        return True


def _should_skip(file_path: str) -> bool:
    """Return True if the file should be silently ignored."""
    if not file_path:
        return True

    p = Path(file_path)
    if not p.exists() or not p.is_file():
        return True

    ext = p.suffix.lower()
    if ext in BINARY_EXTENSIONS:
        return True
    if ext and ext not in CODE_EXTENSIONS:
        return True

    try:
        if p.stat().st_size > MAX_FILE_BYTES:
            return True
    except OSError:
        return True

    return _is_binary_content(file_path)


def _matches_ignore(rel_path: str, ignore_patterns: list) -> bool:
    for pattern in ignore_patterns:
        if fnmatch.fnmatch(rel_path, pattern):
            return True
        # Also match directory prefixes: "vendor/" covers "vendor/foo/bar.rs"
        if rel_path.startswith(pattern.rstrip("/")):
            return True
    return False


def _suppress() -> None:
    print(json.dumps({"suppressOutput": True}))
    sys.exit(0)


def main() -> None:
    project_dir = os.environ.get("CLAUDE_PROJECT_DIR", os.getcwd())

    try:
        data = json.loads(sys.stdin.read())
    except (json.JSONDecodeError, ValueError):
        _suppress()

    file_path: str = data.get("tool_input", {}).get("file_path", "")

    # Resolve relative paths against the project directory
    if file_path and not Path(file_path).is_absolute():
        file_path = str(Path(project_dir) / file_path)

    if _should_skip(file_path):
        _suppress()

    config = load_config(project_dir)

    if not config.get("detection", {}).get("enabled", True):
        _suppress()

    # Build relative path for storage and pattern matching
    try:
        rel_path = str(Path(file_path).relative_to(project_dir))
    except ValueError:
        rel_path = file_path

    ignore_patterns = config.get("detection", {}).get("ignore_paths", [])
    if _matches_ignore(rel_path, ignore_patterns):
        _suppress()

    findings = run_all_detectors(file_path, config, project_dir)

    for finding in findings:
        finding["file_path"] = rel_path
        finding["source"] = "hook"
        add_todo(project_dir, finding)

    _suppress()


if __name__ == "__main__":
    main()
