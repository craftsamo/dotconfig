"""Profile plugin settings must name plugins the way Hermes keys them.

Hermes keys a grouped plugin ``group/name``. ``plugins.enabled`` also accepts the
bare name, but ``plugins.entries`` (e.g. ``allow_tool_override``) does not: a bare
key is silently ignored and the plugin then fails to load.

Only public plugins are checked, so a profile that carries an entry for a private
overlay plugin is not held to a plugin this checkout cannot see.
"""

from __future__ import annotations

from pathlib import Path

import hermes_yaml as yaml
import pytest

from hermes_cli.plugins_discovery import scan_directory
from hermes_cli.plugins_manifest import manifest_key


HERMES = Path(__file__).resolve().parents[2]
CONFIGS = [c for c in sorted(HERMES.glob("profiles/*/config.yaml")) + [HERMES / "config.yaml"] if c.is_file()]


@pytest.fixture(scope="module")
def plugin_keys():
    return {manifest_key(m) for m in scan_directory(HERMES / "plugins", "user")}


@pytest.mark.parametrize("config", CONFIGS, ids=lambda c: c.parent.name)
def test_entries_use_the_group_qualified_key(config, plugin_keys):
    section = (yaml.safe_load(config.read_text()) or {}).get("plugins")
    entries = section.get("entries") if isinstance(section, dict) else None
    bare = sorted(name for name in (entries or {}) if "/" not in name and name not in plugin_keys)
    grouped = {key.split("/", 1)[1]: key for key in plugin_keys if "/" in key}
    assert not [n for n in bare if n in grouped], (
        "plugins.entries must use the group/name key: "
        + ", ".join(f"{n} -> {grouped[n]}" for n in bare if n in grouped))
