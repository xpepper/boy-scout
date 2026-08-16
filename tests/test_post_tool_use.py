import importlib.util
from pathlib import Path

_REPO_ROOT = Path(__file__).parent.parent


def _load_post_tool_use():
    """post-tool-use.py has a hyphen in its filename, so it can't be imported
    with a normal `import` statement — load it by file path instead.
    """
    spec = importlib.util.spec_from_file_location(
        "boy_scout_post_tool_use", _REPO_ROOT / "hooks" / "post-tool-use.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_directory_pattern_ignores_the_directory_and_its_contents():
    matches = _load_post_tool_use()._matches_ignore

    assert matches("target/debug/main.rs", ["target/"]) is True
    assert matches("target", ["target/"]) is True


def test_directory_pattern_does_not_ignore_similarly_named_siblings():
    """"target/" must not swallow targeting.py, targets/ or target_resolver.rs —
    a prefix match has to stop at a path separator.
    """
    matches = _load_post_tool_use()._matches_ignore

    assert matches("targeting.py", ["target/"]) is False
    assert matches("targets/index.ts", ["target/"]) is False
    assert matches("target_resolver.rs", ["target/"]) is False


def test_glob_patterns_still_match():
    matches = _load_post_tool_use()._matches_ignore

    assert matches("src/api.generated.ts", ["*.generated.ts"]) is True
    assert matches("src/api.ts", ["*.generated.ts"]) is False


def test_unrelated_path_is_not_ignored():
    matches = _load_post_tool_use()._matches_ignore

    assert matches("src/main.rs", ["vendor/", "dist/", "node_modules/"]) is False
