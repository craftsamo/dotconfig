import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


plugin = _load("web3_evm_access_plugin_test", ROOT / "__init__.py")


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


def test_the_plugin_registers_the_evm_tool_from_the_shared_logic():
    ctx = Ctx("assistant")
    plugin.register(ctx)
    assert set(ctx.tools) == {"evm"} and ctx.tools["evm"]["toolset"] == "evm_access"
    actions = ctx.tools["evm"]["schema"]["parameters"]["properties"]["action"]["enum"]
    assert "logs" in actions and "transfer" in actions
    ctx = Ctx("researcher")
    plugin.register(ctx)
    assert "transfer" not in ctx.tools["evm"]["schema"]["parameters"]["properties"]["action"]["enum"]
    ctx = Ctx("creator")
    plugin.register(ctx)
    assert ctx.tools == {}


def test_the_wallet_skill_reaches_only_the_profile_that_signs():
    expected = {"assistant": {"evm", "evm-wallet"}, "researcher": {"evm"}, "searcher": {"evm"},
                "marketer": {"evm"}, "creator": set()}
    for profile, names in expected.items():
        ctx = Ctx(profile)
        plugin.register(ctx)
        assert set(ctx.skills) == names
        if ctx.tools:
            assert 'evm-access:evm"' in ctx.tools["evm"]["description"]
    for profile in ("researcher", "searcher", "marketer"):
        ctx = Ctx(profile)
        plugin.register(ctx)
        body = ctx.skills["evm"].read_text().lower()
        assert not any(word in body for word in ("`quote`", "`transfer`", "`accounts`", "approval card", "use: sign"))
        assert "wallet" not in ctx.tools["evm"]["description"].lower()
