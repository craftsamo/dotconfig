"""Skills a plugin ships reach only the profiles that can do what they describe.

Plugin skills are registered as ``<plugin>:<skill>`` and are read-only to Hermes. A profile
that can only read must not be shown the procedure for writing, so this table is the review
point: a new skill or a wider audience has to be added here on purpose.

A registered skill's description is also read on every turn by every profile in its audience
(the available-skills index), so it carries only when to use the skill and where it stops;
what the skill does is the body's. ``DESCRIPTION_BUDGET`` keeps it that way.
"""

import importlib.util
from pathlib import Path

import pytest

HERMES = Path(__file__).resolve().parents[2]
PROFILES_DIR = HERMES / "profiles"
DESCRIPTION_BUDGET = 260

ALL_READERS = {"assistant", "marketer", "searcher"}
EXPECTED = {
    "social/x-access": {
        "x-twitter": ALL_READERS,
        "draft-post": {"assistant"},
        "draft-article": {"assistant"},
    },
    "social/youtube-access": {
        "youtube": ALL_READERS,
        "youtube-manage": {"assistant"},
        "configure-studio": {"assistant"},
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
    "web3/hyperliquid-access": {
        "hyperliquid": {"assistant", "researcher", "searcher", "marketer"},
        "hyperliquid-trade": {"assistant"},
        "configure-strategy": {"assistant"},
        "run-strategy": {"assistant"},
        "manage-strategy": {"assistant"},
    },
    "social/substack-access": {
        "substack": ALL_READERS,
        "substack-drafts": {"assistant"},
    },
    "google-access": {"google-sheets": {"assistant"}, "run-apps-script": {"assistant"}},
    "stripe-access": {"stripe": {"assistant", "researcher", "marketer"}, "stripe-manage": {"assistant"}},
    "cloudflare-access": {"cloudflare": {"assistant", "researcher", "marketer"}, "cloudflare-manage": {"assistant"}},
    "github-access": {"github": {"assistant"}, "github-tracking": {"assistant"}, "github-repo": {"assistant"},
                      "github-pr": {"assistant"}},
    "workspace/workspace-drafts": {"workspace-drafts": {"assistant"}},
    "workspace/workspace-registry": {"workspace-registry": {"assistant"}},
    "messaging/discord-access": {
        "discord-account": {"assistant"},
        "collect-history": {"assistant"},
        "manage-roles": {"assistant"},
    },
    "inspection/screen-listen": {"live": {"assistant"}, "attend-discord": {"assistant"}},
    "messaging/signal-access": {"signal": {"assistant"}},
    "messaging/telegram-access": {"telegram-account": {"assistant"}},
    "messaging/whatsapp-access": {"whatsapp": {"assistant"}, "count-activity": {"assistant"}},
    "orchestration/opencode": {"opencode": {"assistant"}},
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


def shipped_skills():
    return sorted(
        path for path in (HERMES / "plugins").rglob("skills/*/SKILL.md") if "tests" not in path.parts
    )


@pytest.mark.parametrize("path", shipped_skills(), ids=lambda p: p.parent.name)
def test_the_description_stays_within_the_index_budget(path):
    from agent.skill_utils import parse_frontmatter

    meta, _ = parse_frontmatter(path.read_text(encoding="utf-8"))
    assert len(meta["description"]) <= DESCRIPTION_BUDGET, len(meta["description"])
    # The runtime files every plugin skill under the "plugin" category; a category in the
    # frontmatter is never read and would only suggest a shelf the skill is not on.
    assert "category" not in ((meta.get("metadata") or {}).get("hermes") or {})


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
