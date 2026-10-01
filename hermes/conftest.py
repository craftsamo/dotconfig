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
from pathlib import Path

import plugins

_RUNTIME_PLUGINS = Path(plugins.__file__).parent
for _child in (Path(__file__).parent / "plugins").iterdir():
    if _child.is_dir() and (_RUNTIME_PLUGINS / _child.name).is_dir():
        importlib.import_module(f"plugins.{_child.name}")
