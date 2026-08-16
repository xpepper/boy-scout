"""Guards on the plugin's own packaging.

Claude Code discovers skills, commands and agents by convention. A file that
looks right to a human but violates the convention fails silently: the
component is simply never loaded, and there is no error anywhere to notice.
These tests fail loudly instead.
"""
import re
from pathlib import Path

_REPO_ROOT = Path(__file__).parent.parent
_SKILLS = _REPO_ROOT / "skills"

SLUG_RE = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")


def _frontmatter(path: Path) -> dict:
    """Parse the leading YAML block far enough to read its top-level scalars.

    Deliberately not a YAML parser: the plugin has no runtime dependencies and
    the frontmatter here is flat key/value plus folded strings.
    """
    text = path.read_text()
    assert text.startswith("---\n"), f"{path} has no YAML frontmatter"
    block = text.split("---\n", 2)[1]

    fields: dict = {}
    key = None
    for line in block.splitlines():
        match = re.match(r"^([a-zA-Z_]+):\s*(.*)$", line)
        if match:
            key, value = match.group(1), match.group(2).strip()
            fields[key] = value
        elif key is not None and line.strip():
            fields[key] = (fields[key] + " " + line.strip()).strip()
    return fields


def _skill_files() -> list:
    return sorted(_SKILLS.glob("*/SKILL.md"))


def test_every_skill_declares_a_slug_name():
    """Claude Code rejects a skill whose `name` is not a lowercase, hyphenated
    slug. A title-cased name with spaces means the skill never loads at all.
    """
    assert _skill_files(), "no skills found — the guard itself is broken"

    for skill in _skill_files():
        name = _frontmatter(skill).get("name", "")
        assert SLUG_RE.match(name), f"{skill}: '{name}' is not a valid skill name"


def test_every_skill_name_matches_its_directory():
    for skill in _skill_files():
        assert _frontmatter(skill)["name"] == skill.parent.name


def test_every_skill_has_a_description():
    for skill in _skill_files():
        assert _frontmatter(skill).get("description"), f"{skill} has no description"
