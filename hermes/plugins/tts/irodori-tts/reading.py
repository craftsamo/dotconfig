"""Text side of the Irodori-TTS provider: what the model is asked to read.

Irodori has no reading frontend. The server only normalises characters (NFKC,
a few symbol deletions), then a subword tokenizer hands raw kanji, digits and
Latin letters to the model, which guesses the reading. Everything that makes a
reading deterministic therefore has to happen here, before the request.

Kept free of numpy and of Hermes imports on purpose, so it can be loaded and
tested on its own.
"""

from __future__ import annotations

import json
import logging
import os
import re
from pathlib import Path
from typing import Dict, Optional, Tuple

logger = logging.getLogger(__name__)


# --------------------------------------------------------------------------
# Pronunciation lexicon
# --------------------------------------------------------------------------

# The lexicon is DATA, not code, and a pronunciation dictionary tends to
# accumulate names the owner would rather not publish. This repo is public, so
# the file is read from the gitignored runtime directory instead of shipping
# beside the plugin -- the same split qwen3-tts uses for its voice catalog.
# Install it with `launchd/irodori-tts-launchctl.sh register-lexicon --file PATH`.
# No path is read from config.yaml on purpose: config.yaml is tracked, and a
# path into a private tree must not land there.
LEXICON_ENV = "IRODORI_TTS_LEXICON"
_lexicon_cache: Optional[Tuple[Dict[str, str], Optional[re.Pattern]]] = None


def _runtime_dir() -> Path:
    """Locate hermes/local/irodori-tts/ from wherever this plugin was loaded.

    Hermes reads plugins through ~/.hermes/plugins, which is a symlink into the
    config repo, so the path is resolved before walking up. The walk looks for
    the directory that owns config.yaml rather than counting parents, which
    survives the plugin being nested differently.
    """
    here = Path(__file__).resolve()
    for parent in here.parents:
        if (parent / "config.yaml").exists() and (parent / "plugins").is_dir():
            return parent / "local" / "irodori-tts"
    return here.parents[3] / "local" / "irodori-tts"


def lexicon_path() -> Path:
    override = os.environ.get(LEXICON_ENV)
    if override:
        return Path(override).expanduser()
    return _runtime_dir() / "lexicon.json"


def compile_lexicon(terms: Dict[str, str]) -> Optional[re.Pattern]:
    """One alternation, longest key first so "Claude Code" beats "Claude".

    ASCII keys are fenced by ASCII letters and digits only, so "Gemini" does
    not fire inside "GeminiFooBar" yet does fire in "Geminiで". (A plain \b
    would not: Python counts kana and kanji as word characters, so a Latin
    name glued to Japanese -- the normal case -- never matched.) Keys need not
    be Latin: a kanji surface works the same way and pins a reading the model
    keeps guessing wrong.
    """
    if not terms:
        return None
    parts = []
    for key in sorted(terms, key=len, reverse=True):
        esc = re.escape(key)
        if key[0].isascii() and key[0].isalnum():
            esc = r"(?<![A-Za-z0-9])" + esc
        if key[-1].isascii() and key[-1].isalnum():
            esc = esc + r"(?![A-Za-z0-9])"
        parts.append(esc)
    return re.compile("|".join(parts))


def read_lexicon(path: Path) -> Dict[str, str]:
    """Parse ``{"terms": {surface: reading}}``; anything else is ignored."""
    raw = json.loads(path.read_text(encoding="utf-8"))
    candidate = raw.get("terms") if isinstance(raw, dict) else None
    if not isinstance(candidate, dict):
        return {}
    return {
        str(k): str(v)
        for k, v in candidate.items()
        if isinstance(k, str) and isinstance(v, str) and k
    }


def load_lexicon() -> Tuple[Dict[str, str], Optional[re.Pattern]]:
    global _lexicon_cache
    if _lexicon_cache is not None:
        return _lexicon_cache
    terms: Dict[str, str] = {}
    path = lexicon_path()
    try:
        terms = read_lexicon(path)
        logger.debug("irodori-tts: loaded %d lexicon term(s)", len(terms))
    except FileNotFoundError:
        # Optional: without it, proper nouns are simply read as the model sees
        # them.
        logger.debug("irodori-tts: no lexicon at %s; skipping substitution", path)
    except Exception as exc:  # noqa: BLE001 - the lexicon is an optimisation
        logger.warning("irodori-tts: lexicon at %s unreadable (%s); skipping", path, exc)
    _lexicon_cache = (terms, compile_lexicon(terms))
    return _lexicon_cache


def apply_lexicon(
    text: str,
    lexicon: Optional[Tuple[Dict[str, str], Optional[re.Pattern]]] = None,
) -> str:
    """Rewrite known surfaces (Latin proper nouns, stubborn kanji) as kana."""
    terms, pattern = lexicon if lexicon is not None else load_lexicon()
    if not pattern:
        return text
    return pattern.sub(lambda m: terms.get(m.group(0), m.group(0)), text)
