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
_AGENTS = _REPO_ROOT / "agents"
_COMMANDS = _REPO_ROOT / "commands"
_BIN = _REPO_ROOT / "bin"

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


def test_every_agent_declares_a_slug_name_matching_its_file():
    agents = sorted(_AGENTS.glob("*.md"))
    assert agents, "no agents found — the guard itself is broken"

    for agent in agents:
        name = _frontmatter(agent).get("name", "")
        assert SLUG_RE.match(name), f"{agent}: '{name}' is not a valid agent name"
        assert name == agent.stem


def test_every_agent_and_command_describes_itself():
    """The description is the whole basis on which one gets picked."""
    for component in sorted(_AGENTS.glob("*.md")) + sorted(_COMMANDS.glob("*.md")):
        assert _frontmatter(component).get("description"), f"{component} has no description"


def test_the_refactoring_agent_is_dispatched_by_the_session_command():
    """A command naming an agent that does not exist fails at the moment of
    use, in front of the user, with the backlog half triaged.
    """
    session = (_COMMANDS / "boy-scout-session.md").read_text()
    agent_names = {_frontmatter(a)["name"] for a in _AGENTS.glob("*.md")}

    assert any(name in session for name in agent_names)


def test_components_only_invoke_clis_the_plugin_ships():
    """Every `boy-scout-*` command named in a skill, command or agent has to
    exist in bin/, or the instruction is a dead end at runtime.
    """
    shipped = {path.name for path in _BIN.iterdir() if path.is_file()}
    referenced = set()
    for component in (
        list(_SKILLS.glob("*/SKILL.md"))
        + list(_AGENTS.glob("*.md"))
        + list(_COMMANDS.glob("*.md"))
    ):
        # Only shell blocks: prose mentions slash commands and agent names,
        # which are not executables and have no business in bin/.
        for block in re.findall(r"```bash\n(.*?)```", component.read_text(), re.S):
            referenced |= {
                line.split()[0]
                for line in block.splitlines()
                if line.strip().startswith("boy-scout-")
            }

    assert referenced, "no CLI references found — the guard itself is broken"
    assert referenced <= shipped, f"referenced but not shipped: {referenced - shipped}"
