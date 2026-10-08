"""Skills a plugin ships reach only the profiles that can do what they describe.

Plugin skills are registered as ``<plugin>:<skill>`` and are read-only to Hermes. A profile
that can only read must not be shown the procedure for writing, so this table is the review
point: a new skill or a wider audience has to be added here on purpose.
"""

import importlib.util
from pathlib import Path

import pytest

HERMES = Path(__file__).resolve().parents[2]
PROFILES_DIR = HERMES / "profiles"

ALL_READERS = {"assistant", "marketer", "searcher"}
EXPECTED = {
    "social/x-access": {
        "x-twitter": ALL_READERS,
        "x-twitter-drafts": {"assistant"},
    },
    "social/youtube-access": {
        "youtube": ALL_READERS,
        "youtube-manage": {"assistant"},
    },
    "social/note-access": {
        "note-com": ALL_READERS,
        "note-com-format": {"assistant", "marketer", "writer"},
        "note-com-drafts": {"assistant"},
    },
    "web3/evm-access": {
        "evm": {"assistant", "researcher", "searcher", "marketer"},
        "evm-wallet": {"assistant"},
    },
    "web3/solana-access": {
        "solana": {"assistant", "researcher", "searcher", "marketer"},
        "solana-wallet": {"assistant"},
    },
    "social/substack-access": {
        "substack": ALL_READERS,
        "substack-drafts": {"assistant"},
    },
    "google-access": {"google-sheets": {"assistant"}},
    "messaging/discord-access": {"discord-account": {"assistant"}},
    "messaging/signal-access": {"signal": {"assistant"}},
    "messaging/telegram-access": {"telegram-account": {"assistant"}},
    "messaging/whatsapp-access": {"whatsapp": {"assistant"}},
}


class Ctx:
    def __init__(self, profile):
        self.profile_name = profile
        self.skills = {}

    def register_skill(self, name, path, description="", frontmatter=None):
        assert path.is_file() and frontmatter["name"] == name and description
        self.skills[name] = path


def load(plugin):
    spec = importlib.util.spec_from_file_location(
        "plugin_skills_" + plugin.replace("/", "_").replace("-", "_"), HERMES / "plugins" / plugin / "__init__.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def profiles():
    return sorted(p.name for p in PROFILES_DIR.iterdir() if (p / "config.yaml").is_file() or (p / "config.example.yaml").is_file())


def test_every_shipped_skill_is_in_the_table():
    shipped = {
        f"{path.parents[2].relative_to(HERMES / 'plugins')}": set()
        for path in (HERMES / "plugins").rglob("skills/*/SKILL.md")
        if "tests" not in path.parts
    }
    for path in (HERMES / "plugins").rglob("skills/*/SKILL.md"):
        if "tests" not in path.parts:
            shipped[str(path.parents[2].relative_to(HERMES / "plugins"))].add(path.parent.name)
    assert shipped == {plugin: set(skills) for plugin, skills in EXPECTED.items()}


@pytest.mark.parametrize("plugin", sorted(EXPECTED))
def test_each_profile_gets_exactly_its_skills(plugin):
    module = load(plugin)
    assert set(profiles()) >= set().union(*EXPECTED[plugin].values())
    for profile in profiles():
        ctx = Ctx(profile)
        module.register_skills(ctx, profile)
        assert set(ctx.skills) == {n for n, who in EXPECTED[plugin].items() if profile in who}, (plugin, profile)


@pytest.mark.parametrize("plugin", sorted(EXPECTED))
def test_a_skill_never_reaches_a_profile_without_the_tool(plugin):
    module = load(plugin)
    profiles_with_tool = set(getattr(module, "PROFILES", None) or module.access.PROFILES)
    for name, who in EXPECTED[plugin].items():
        assert who <= profiles_with_tool, (plugin, name)
