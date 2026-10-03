"""Shared test helpers for the inspector package.

The scripts package is loaded under an alias so the tests do not depend on
``sys.path`` order. Relative imports inside the package keep working.
"""

import importlib
import importlib.util
from pathlib import Path
import sys

SCRIPTS = Path(__file__).resolve().parents[2] / "curated" / "japanese-writing" / "scripts"
ALIAS = "japanese_writing_inspector"


def _load_package():
    if ALIAS in sys.modules:
        return sys.modules[ALIAS]
    root = SCRIPTS / "inspector"
    spec = importlib.util.spec_from_file_location(
        ALIAS, root / "__init__.py", submodule_search_locations=[str(root)],
    )
    package = importlib.util.module_from_spec(spec)
    sys.modules[ALIAS] = package
    spec.loader.exec_module(package)
    return package


package = _load_package()


def module(name):
    """Import ``inspector.<name>`` from the scripts package, e.g. ``module("rules.terms")``."""
    return importlib.import_module(f"{ALIAS}.{name}")


document = module("document")
morphology = module("morphology")
reporting = module("report")
Document = document.Document
MORPH_AVAILABLE = morphology.load(True).available


def unavailable_morphology():
    info = {"available": False, "reason": "missing_or_version_mismatch", "packages": {}}
    return morphology.Morphology(None, info)


def inspection(text, morph=None, genre="default", experimental=False, original=None, stance=None):
    """An ``Inspection`` over ``text``; ``morph`` defaults to the real (possibly unavailable) loader."""
    morph = morph if morph is not None else morphology.load(True)
    previous = Document(original) if original is not None else None
    return reporting.Inspection(Document(text), morph, genre, experimental, previous, stance)


def run(mode_module, text, morph=None, finish=True, **options):
    """Run one mode module over ``text`` and return the report dict."""
    state = inspection(text, morph, **options)
    mode_module.run(state)
    return reporting.finish(state.report) if finish else state.report
