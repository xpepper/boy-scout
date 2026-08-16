"""Every shipped setting has to do something.

`boy-scout-config.json` is auto-created from DEFAULT_CONFIG, so anything left
in there is presented to the user as a knob they can turn. A knob wired to
nothing is worse than a missing feature: it teaches people the config file
cannot be trusted, and it costs a support round-trip to discover.
"""
import re
from pathlib import Path

from todo_manager import DEFAULT_CONFIG

_REPO_ROOT = Path(__file__).parent.parent
_SOURCE_DIRS = ("hooks", "scripts", "skills")


def _source_text() -> str:
    chunks = []
    for directory in _SOURCE_DIRS:
        for path in (_REPO_ROOT / directory).rglob("*.py"):
            if "__pycache__" in path.parts:
                continue
            chunks.append(path.read_text())
    return "\n".join(chunks)


def _config_keys(config, prefix=""):
    for key, value in config.items():
        yield f"{prefix}{key}"
        if isinstance(value, dict):
            yield from _config_keys(value, prefix=f"{prefix}{key}.")


def test_every_default_config_key_is_read_somewhere():
    source = _source_text()

    for dotted in _config_keys(DEFAULT_CONFIG):
        leaf = dotted.rsplit(".", 1)[-1]
        assert re.search(rf'get\(\s*"{re.escape(leaf)}"', source), (
            f"config key '{dotted}' is offered to users but nothing reads it"
        )
