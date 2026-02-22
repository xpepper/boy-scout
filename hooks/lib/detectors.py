"""
Refactoring pattern detectors for Boy Scout plugin.

Priority order (per design): duplication > naming clarity > test coverage > function size.

Inspired by the Boy Scout Rule (97 Things Every Programmer Should Know, ch. 8):
leave every module a little better than you found it.

Language priority: Rust, Elm, JavaScript/TypeScript, Python (others best-effort).
"""
import ast
import fnmatch
import os
import re
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from pattern_analyzer import (
    detect_language,
    is_blank_or_comment,
    is_test_file,
    normalize_line,
    read_content,
    significant_lines,
)


# ---------------------------------------------------------------------------
# Sensitivity thresholds
# ---------------------------------------------------------------------------

SENSITIVITY: Dict[str, Dict] = {
    "aggressive":   {"min_dup_lines": 4,  "max_func_lines": 10, "max_naming_issues": 3},
    "balanced":     {"min_dup_lines": 6,  "max_func_lines": 20, "max_naming_issues": 5},
    "conservative": {"min_dup_lines": 10, "max_func_lines": 35, "max_naming_issues": 8},
}


def _thresholds(config: Dict) -> Dict:
    level = config.get("detection", {}).get("sensitivity", "balanced")
    return SENSITIVITY.get(level, SENSITIVITY["balanced"])


# ---------------------------------------------------------------------------
# 1. Duplication detector
# ---------------------------------------------------------------------------

def detect_duplication(file_path: str, config: Dict) -> List[Dict]:
    """
    Detect copy-pasted blocks using a sliding-window hash over normalized lines.

    Works across all supported languages; accuracy improves for those with
    well-defined comment syntax (Rust, Elm, JS/TS, Python).
    """
    content = read_content(file_path)
    if content is None:
        return []

    language = detect_language(file_path)
    min_lines = _thresholds(config)["min_dup_lines"]
    sig = significant_lines(content, language)

    if len(sig) < min_lines * 2:
        return []

    # Index: sig position → (line_num, normalized_content)
    # We also need reverse: line_num → sig index for extend logic.
    line_to_sig_idx = {line_num: idx for idx, (line_num, _) in enumerate(sig)}

    # Sliding window: hash(normalized block) → [(sig_idx_start, line_start, line_end), ...]
    buckets: Dict[int, List[Tuple[int, int, int]]] = {}
    for i in range(len(sig) - min_lines + 1):
        window = sig[i : i + min_lines]
        block_text = "\n".join(norm for _, norm in window)
        h = hash(block_text)
        buckets.setdefault(h, []).append((i, window[0][0], window[-1][0]))

    def _extend_match(i: int, j: int) -> Tuple[int, int, int, int]:
        """Extend a matched pair (sig indices i, j) as far forward as possible."""
        while i < len(sig) and j < len(sig) and sig[i][1] == sig[j][1]:
            i += 1
            j += 1
        first_end  = sig[i - 1][0]
        second_end = sig[j - 1][0]
        return first_end, second_end

    # Collect all duplicate pairs (extended to max coverage), sort by first start.
    all_pairs: List[Tuple[int, int, int, int]] = []  # (fs, fe, ss, se)
    for h, occurrences in buckets.items():
        if len(occurrences) >= 2:
            i_idx, fs, _ = occurrences[0]
            j_idx, ss, _ = occurrences[1]
            fe, se = _extend_match(i_idx, j_idx)
            all_pairs.append((fs, fe, ss, se))
    all_pairs.sort()

    findings = []
    used: List[Tuple[int, int]] = []  # intervals already covered

    def _overlaps(start: int, end: int) -> bool:
        return any(s <= end and e >= start for s, e in used)

    for first_start, first_end, second_start, second_end in all_pairs:
        if _overlaps(first_start, first_end) or _overlaps(second_start, second_end):
            continue
        used.append((first_start, first_end))
        used.append((second_start, second_end))
        dup_lines = first_end - first_start + 1
        findings.append({
            "type": "duplication",
            "locations": [
                {"line_start": first_start,  "line_end": first_end},
                {"line_start": second_start, "line_end": second_end},
            ],
            "severity": "medium",
            "description": (
                f"Duplicated block ({dup_lines} lines): "
                f"lines {first_start}–{first_end} and {second_start}–{second_end}"
            ),
        })

    return findings


# ---------------------------------------------------------------------------
# 2. Naming clarity detector
# ---------------------------------------------------------------------------

# Identifiers that are conventionally short and acceptable
ALLOWED_SHORT: frozenset = frozenset(
    "i j k n x y z e f t v ok _ err".split()
)

# Common cryptic abbreviations worth flagging
ABBREVIATION_RE = re.compile(
    r"\b(tmp|temp|buf|str2?|obj|arr|lst|dct|cnt|num|idx|ptr|"
    r"mgr|svc|ctrl|util|misc|res|ret|cb|fn2?|d[0-9]?)\b",
    re.IGNORECASE,
)

# Language-specific variable-binding patterns
BINDING_PATTERNS: Dict[str, re.Pattern] = {
    "rust":       re.compile(r"\blet(?:\s+mut)?\s+([a-zA-Z_][a-zA-Z0-9_]*)"),
    "elm":        re.compile(r"^([a-z][a-zA-Z0-9_]*)\s*(?:::\s*\S+\s*)?=(?!=)"),
    "javascript": re.compile(r"\b(?:let|const|var)\s+([a-zA-Z_$][a-zA-Z0-9_$]*)"),
    "typescript": re.compile(r"\b(?:let|const|var)\s+([a-zA-Z_$][a-zA-Z0-9_$]*)"),
    "python":     re.compile(r"^[ \t]*([a-zA-Z_][a-zA-Z0-9_]*)\s*(?::[^=]+)?=(?!=)"),
    "go":         re.compile(r"\b([a-zA-Z_][a-zA-Z0-9_]*)\s*:="),
}


def detect_naming_clarity(file_path: str, config: Dict) -> List[Dict]:
    """Flag single-character identifiers and cryptic abbreviations."""
    content = read_content(file_path)
    if content is None:
        return []

    language = detect_language(file_path)
    max_issues = _thresholds(config)["max_naming_issues"]
    binding_re = BINDING_PATTERNS.get(language)
    lines = content.splitlines()
    findings = []
    seen: set = set()

    for i, line in enumerate(lines):
        line_num = i + 1
        if is_blank_or_comment(line, language):
            continue

        # Single-character identifiers via binding pattern
        if binding_re:
            for m in binding_re.finditer(line):
                name = m.group(1)
                if len(name) == 1 and name.lower() not in ALLOWED_SHORT and name not in seen:
                    seen.add(name)
                    findings.append({
                        "type": "naming",
                        "locations": [{"line_start": line_num, "line_end": line_num}],
                        "severity": "low",
                        "description": (
                            f"Single-character identifier '{name}' — "
                            "consider a name that reveals intent"
                        ),
                    })

        # Cryptic abbreviations (language-agnostic scan)
        for m in ABBREVIATION_RE.finditer(line):
            name = m.group(1).lower()
            if name not in seen:
                seen.add(name)
                findings.append({
                    "type": "naming",
                    "locations": [{"line_start": line_num, "line_end": line_num}],
                    "severity": "low",
                    "description": (
                        f"Abbreviated identifier '{m.group(1)}' — "
                        "consider a more descriptive name"
                    ),
                })

        if len(findings) >= max_issues:
            break

    return findings[:max_issues]


# ---------------------------------------------------------------------------
# 3. Test coverage gap detector
# ---------------------------------------------------------------------------

TEST_DIRS = ("tests", "test", "spec", "__tests__", "specs", "src/tests")
TEST_SUFFIXES = ("_test", ".test", ".spec", "_spec")
TEST_PREFIXES = ("test_",)

TESTABLE_LANGUAGES = {
    "rust", "elm", "javascript", "typescript", "python",
    "go", "ruby", "java", "kotlin", "swift",
}


def _find_test_file(file_path: str, project_dir: str) -> Optional[str]:
    src = Path(file_path)
    stem = src.stem
    suffix = src.suffix
    root = Path(project_dir)

    candidates = (
        [f"{stem}_test{suffix}", f"test_{stem}{suffix}",
         f"{stem}.test{suffix}", f"{stem}.spec{suffix}", f"{stem}_spec{suffix}"]
    )

    search_dirs = [src.parent] + [root / d for d in TEST_DIRS]
    for directory in search_dirs:
        for name in candidates:
            candidate = directory / name
            if candidate.exists():
                return str(candidate)
    return None


def detect_test_coverage_gap(
    file_path: str, config: Dict, project_dir: str
) -> List[Dict]:
    """Detect source files modified without a corresponding test file."""
    if is_test_file(file_path):
        return []

    if config.get("detection", {}).get("ignore_tests", False):
        return []

    language = detect_language(file_path)
    if language not in TESTABLE_LANGUAGES:
        return []

    if _find_test_file(file_path, project_dir):
        return []

    rel = _rel_path(file_path, project_dir)
    return [{
        "type": "test_coverage",
        "locations": [{"line_start": 1, "line_end": 1}],
        "severity": "medium",
        "description": (
            f"No test file found for {Path(file_path).name} — "
            "consider adding tests alongside production changes"
        ),
    }]


# ---------------------------------------------------------------------------
# 4. Function size detector
# ---------------------------------------------------------------------------

FUNC_PATTERNS: Dict[str, re.Pattern] = {
    "rust": re.compile(
        r"^\s*(?:pub(?:\([^)]*\))?\s+)?(?:async\s+)?fn\s+(\w+)"
    ),
    "elm": re.compile(
        r"^([a-z]\w*)\s*(?:[a-zA-Z_]\w*\s*)*="
    ),
    "javascript": re.compile(
        r"^\s*(?:export\s+)?(?:default\s+)?(?:async\s+)?"
        r"(?:function\s+(\w+)|(?:const|let|var)\s+(\w+)\s*=)"
    ),
    "typescript": re.compile(
        r"^\s*(?:export\s+)?(?:default\s+)?(?:async\s+)?"
        r"(?:function\s+(\w+)|(?:const|let|var)\s+(\w+)\s*=)"
    ),
    "go": re.compile(r"^\s*func\s+(?:\([^)]+\)\s+)?(\w+)"),
}

# Languages that use brace-delimited blocks
BRACE_LANGUAGES = {
    "rust", "javascript", "typescript", "go",
    "java", "c", "cpp", "csharp", "kotlin", "swift",
}


def _count_brace_func_lines(
    raw_lines: List[str], start_idx: int
) -> int:
    """Return number of lines until brace-delimited function closes."""
    depth = 0
    for i, line in enumerate(raw_lines[start_idx:], start_idx):
        depth += line.count("{") - line.count("}")
        if i > start_idx and depth <= 0:
            return i - start_idx + 1
    return len(raw_lines) - start_idx


def detect_function_size(file_path: str, config: Dict) -> List[Dict]:
    """Flag functions whose body exceeds the configured line threshold."""
    max_lines = _thresholds(config)["max_func_lines"]
    language = detect_language(file_path)
    content = read_content(file_path)
    if content is None:
        return []

    findings = []

    # Python: use the built-in AST for accurate analysis
    if language == "python":
        try:
            tree = ast.parse(content)
        except SyntaxError:
            return []
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                start = node.lineno
                end = getattr(node, "end_lineno", start)
                size = end - start + 1
                if size > max_lines:
                    findings.append({
                        "type": "function_size",
                        "locations": [{"line_start": start, "line_end": end}],
                        "severity": "medium" if size > max_lines * 2 else "low",
                        "description": (
                            f"Function '{node.name}' spans {size} lines "
                            f"(threshold: {max_lines}) — consider decomposing"
                        ),
                    })
        return findings

    # Brace-based languages: regex function header + brace counting
    func_re = FUNC_PATTERNS.get(language)
    if func_re is None or language not in BRACE_LANGUAGES:
        return []

    raw_lines = content.splitlines()
    i = 0
    while i < len(raw_lines):
        m = func_re.search(raw_lines[i])
        if m:
            name = next((g for g in m.groups() if g), "anonymous")
            func_start = i + 1  # 1-based
            # Skip forward until we hit the opening brace
            j = i
            while j < len(raw_lines) and "{" not in raw_lines[j]:
                j += 1
            if j >= len(raw_lines):
                i += 1
                continue
            size = _count_brace_func_lines(raw_lines, j)
            func_end = j + size  # 1-based
            if size > max_lines:
                findings.append({
                    "type": "function_size",
                    "locations": [{"line_start": func_start, "line_end": func_end}],
                    "severity": "medium" if size > max_lines * 2 else "low",
                    "description": (
                        f"Function '{name}' spans {size} lines "
                        f"(threshold: {max_lines}) — consider decomposing"
                    ),
                })
            i = j + size
        else:
            i += 1

    return findings


# ---------------------------------------------------------------------------
# Orchestrator
# ---------------------------------------------------------------------------

def run_all_detectors(
    file_path: str, config: Dict, project_dir: str = ""
) -> List[Dict]:
    """Run all enabled detectors and return combined findings."""
    enabled = set(
        config.get("detection", {}).get(
            "patterns",
            ["duplication", "naming", "test_coverage", "function_size"],
        )
    )

    findings: List[Dict] = []

    # Priority order: duplication > naming > test_coverage > function_size
    if "duplication" in enabled:
        findings.extend(detect_duplication(file_path, config))

    if "naming" in enabled:
        findings.extend(detect_naming_clarity(file_path, config))

    if "test_coverage" in enabled:
        findings.extend(detect_test_coverage_gap(file_path, config, project_dir))

    if "function_size" in enabled:
        findings.extend(detect_function_size(file_path, config))

    return findings


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _rel_path(file_path: str, project_dir: str) -> str:
    try:
        return str(Path(file_path).relative_to(project_dir))
    except ValueError:
        return file_path
