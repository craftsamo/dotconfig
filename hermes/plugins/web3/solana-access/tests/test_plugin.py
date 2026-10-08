import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


plugin = _load("web3_solana_access_plugin_test", ROOT / "__init__.py")


class Ctx:
    def __init__(self, profile):
        self.profile_name = profile
        self.tools = {}
        self.hooks = []
        self.skills = {}

    def register_skill(self, name, path, description="", frontmatter=None):
        assert path.is_file() and frontmatter["name"] == name and description
        self.skills[name] = path

    def register_tool(self, **kwargs):
        self.tools[kwargs["name"]] = kwargs

    def register_hook(self, name, callback):
        self.hooks.append((name, callback))


def test_the_plugin_registers_the_solana_tool_from_the_shared_logic():
    ctx = Ctx("assistant")
    plugin.register(ctx)
    assert set(ctx.tools) == {"solana"} and ctx.tools["solana"]["toolset"] == "solana_access"
    schema = ctx.tools["solana"]["schema"]["parameters"]
    assert "logs" not in schema["properties"]["action"]["enum"] and "transfer" in schema["properties"]["action"]["enum"]
    assert schema["properties"]["chain"]["enum"] == ["solana", "solana-devnet"]
    ctx = Ctx("searcher")
    plugin.register(ctx)
    assert "transfer" not in ctx.tools["solana"]["schema"]["parameters"]["properties"]["action"]["enum"]


def test_the_wallet_skill_reaches_only_the_profile_that_signs():
    expected = {"assistant": {"solana", "solana-wallet"}, "researcher": {"solana"}, "searcher": {"solana"},
                "marketer": {"solana"}, "creator": set()}
    for profile, names in expected.items():
        ctx = Ctx(profile)
        plugin.register(ctx)
        assert set(ctx.skills) == names
        if ctx.tools:
            assert 'solana-access:solana"' in ctx.tools["solana"]["description"]
    for profile in ("researcher", "searcher", "marketer"):
        ctx = Ctx(profile)
        plugin.register(ctx)
        body = ctx.skills["solana"].read_text().lower()
        assert not any(word in body for word in ("`quote`", "`transfer`", "`accounts`", "approval card", "use: sign"))
        assert "wallet" not in ctx.tools["solana"]["description"].lower()
