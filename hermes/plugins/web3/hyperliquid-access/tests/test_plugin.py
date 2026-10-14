import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


plugin = _load("web3_hyperliquid_access_plugin_test", ROOT / "__init__.py")


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


def test_the_plugin_registers_the_hyperliquid_tool_from_the_shared_logic():
    for profile in ("assistant", "researcher", "searcher", "marketer"):
        ctx = Ctx(profile)
        plugin.register(ctx)
        assert set(ctx.tools) == {"hyperliquid"} and ctx.tools["hyperliquid"]["toolset"] == "hyperliquid_access"
        assert "review" in ctx.tools["hyperliquid"]["schema"]["parameters"]["properties"]["action"]["enum"]
    ctx = Ctx("creator")
    plugin.register(ctx)
    assert ctx.tools == {} and ctx.skills == {}


def test_the_trade_skill_reaches_only_the_profile_that_signs():
    expected = {"assistant": {"hyperliquid", "hyperliquid-trade"}, "researcher": {"hyperliquid"},
                "searcher": {"hyperliquid"}, "marketer": {"hyperliquid"}, "creator": set()}
    for profile, names in expected.items():
        ctx = Ctx(profile)
        plugin.register(ctx)
        assert set(ctx.skills) == names
        if not ctx.tools:
            continue
        description = ctx.tools["hyperliquid"]["description"]
        assert 'hyperliquid-access:hyperliquid"' in description
        assert ('hyperliquid-access:hyperliquid-trade"' in description) == (profile == "assistant")
        actions = ctx.tools["hyperliquid"]["schema"]["parameters"]["properties"]["action"]["enum"]
        assert ("submit" in actions) == (profile == "assistant")
    for profile in ("researcher", "searcher", "marketer"):
        ctx = Ctx(profile)
        plugin.register(ctx)
        body = ctx.skills["hyperliquid"].read_text().lower()
        assert not any(word in body for word in ("`quote`", "`submit`", "mandate", "approval card", "use: sign"))
        assert "trading" not in ctx.tools["hyperliquid"]["description"].lower()
