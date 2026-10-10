"""Let the Hermes runtime own the ``plugins`` package name during tests.

This repo's ``plugins/`` directory shares its name with the runtime's
``plugins`` package. Under ``--import-mode=importlib`` pytest registers each
test file's parent directories (``plugins``, ``plugins.image_gen``, ...) as
packages unless they are already imported, which shadows the runtime package
for the whole session: runtime imports such as ``plugins.browser`` or
``plugins.platforms.a2a`` then fail. Importing the runtime packages first keeps
them authoritative; plugin tests load their own code by file path anyway.
"""

import importlib
import importlib.util
import sys
import types
from pathlib import Path

import plugins
import pytest

_RUNTIME_PLUGINS = Path(plugins.__file__).parent
for _child in (Path(__file__).parent / "plugins").iterdir():
    if _child.is_dir() and (_RUNTIME_PLUGINS / _child.name).is_dir():
        importlib.import_module(f"plugins.{_child.name}")

# Plugins whose package ``__init__`` imports a Hermes runtime dependency that
# the test interpreter lacks, with the test modules that need that package.
# The same parent registration would import that ``__init__`` before any of the
# plugin's test modules and fail all of them, so without the dependency an
# empty package stands in for the plugin (its other tests load what they need
# by file path) and the listed modules are skipped at collection.
_PLUGIN_NEEDS = {"tts/irodori-tts": ("numpy", ("tests/test_plugin.py",))}
_SKIP: dict[Path, str] = {}
for _rel, (_dependency, _modules) in _PLUGIN_NEEDS.items():
    if importlib.util.find_spec(_dependency) is not None:
        continue
    _dir = Path(__file__).parent / "plugins" / _rel
    _package = types.ModuleType("plugins." + _rel.replace("/", "."))
    _package.__path__ = [str(_dir)]
    sys.modules.setdefault(_package.__name__, _package)
    for _module in _modules:
        _SKIP[_dir / _module] = f"needs {_dependency}, absent from the Hermes test environment"


class _MissingDependency(pytest.Module):
    reason = ""

    def collect(self):
        pytest.skip(self.reason)


def pytest_pycollect_makemodule(module_path, parent):
    reason = _SKIP.get(Path(module_path))
    if reason is None:
        return None
    item = _MissingDependency.from_parent(parent, path=module_path)
    item.reason = reason
    return item
