"""Word lists and patterns kept as data under ``data/``."""

from functools import lru_cache
import json
from pathlib import Path

_DATA = Path(__file__).resolve().parent / "data"


@lru_cache(maxsize=None)
def load(name):
    return json.loads((_DATA / f"{name}.json").read_text(encoding="utf-8"))
