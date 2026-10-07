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
