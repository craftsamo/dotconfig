"""Optional SudachiPy morphology with exact version pins.

Without the pinned packages every morphology-dependent check is reported as
unverified; nothing is installed or downloaded at runtime.
"""

from dataclasses import dataclass
from importlib import metadata

PINS = {"SudachiPy": "0.6.11", "sudachidict_core": "20260723"}
# Sudachi rejects inputs near 49 KiB; anything above this is left unverified.
MAX_SEGMENT_BYTES = 40000


class SegmentTooLarge(ValueError):
    pass


@dataclass(frozen=True)
class Token:
    surface: str
    pos: tuple
    dictionary_form: str
    normalized_form: str
    reading_form: str
    begin: int
    end: int


class Morphology:
    def __init__(self, tokenizer, info):
        self._tokenizer = tokenizer
        self.info = info
        self._cache = {}

    @property
    def available(self):
        return self._tokenizer is not None

    @property
    def reason(self):
        return self.info["reason"]

    def tokenize(self, text):
        """Split mode C tokens; offsets are character offsets into ``text``."""
        if self._tokenizer is None:
            raise RuntimeError("morphology unavailable")
        cached = self._cache.get(text)
        if cached is not None:
            return cached
        if len(text.encode("utf-8")) > MAX_SEGMENT_BYTES:
            raise SegmentTooLarge(text[:20])
        try:
            tokens = [
                Token(m.surface(), tuple(m.part_of_speech()), m.dictionary_form(),
                      m.normalized_form(), m.reading_form(), m.begin(), m.end())
                for m in self._tokenizer.tokenize(text)
            ]
        except Exception as exc:
            raise RuntimeError("morphology execution failed") from exc
        self._cache[text] = tokens
        return tokens


def load(needed):
    packages = {name: {"required": pin, "actual": None} for name, pin in PINS.items()}
    for name in PINS:
        try:
            packages[name]["actual"] = metadata.version(name)
        except metadata.PackageNotFoundError:
            pass
    info = {"available": False, "reason": "not_requested", "packages": packages}
    if not needed:
        return Morphology(None, info)
    if any(item["required"] != item["actual"] for item in packages.values()):
        info["reason"] = "missing_or_version_mismatch"
        return Morphology(None, info)
    try:
        from sudachipy import Dictionary

        tokenizer = Dictionary(dict="core").create()
    except Exception:
        info["reason"] = "initialization_failed"
        return Morphology(None, info)
    info.update(available=True, reason=None)
    return Morphology(tokenizer, info)
