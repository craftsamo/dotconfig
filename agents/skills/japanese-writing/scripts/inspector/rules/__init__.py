"""Inspection modes. Each module exposes MODE, MORPHOLOGY and run(inspection)."""

from . import expression, naturalness, notation, outline, reading_load, revision, structure, terms

ORDER = (naturalness, expression, notation, reading_load, outline, terms, structure, revision)
BY_MODE = {module.MODE: module for module in ORDER}
MODES = tuple(module.MODE for module in ORDER)
