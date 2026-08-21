"""Creator tools for rendering an explicitly chosen local character voice.

These tools belong to neither engine, so they live in neither engine plugin:
they resolve a provider out of the TTS registry and call it directly. Two
properties follow from that and are the whole point of the plugin.

*The engine is part of the voice identity.* The same reference voice renders
309 cents apart on irodori-tts and qwen3-tts (against 20-40 cents of
seed-to-seed variation), so a bare voice id does not describe a sound. Ids are
therefore qualified as ``<engine>:<voice>`` and a bare id is refused rather
than resolved to a default engine.

*Nothing here routes.* Ordinary speech routes by language through
``tts.fallback.chain`` -- irodori-tts declines English-dominant text and the
chain advances. A character asset is the opposite contract: the caller named
one engine and one voice, so a decline is an error, never a hand-off. The
engine list below is fixed for that reason and must not be read from the chain.

*Style controls are asked for, not assumed.* An engine may perform an emoji as
a non-verbal vocalisation, accept a caption describing delivery, or take a seed;
another engine would read the emoji out as "smiling face" and ignore the rest.
So this plugin holds no engine-specific style knowledge: it reads
``provider.style_features`` and refuses a control the named engine does not
advertise, because silently dropping one would hand back a file that is not
what was asked for -- the same reason a refused render deletes its output.

*A character render can be rebuilt.* ``seed`` in an engine's features means the
CALLER can pin one, not that the engine is otherwise random. Irodori draws a
fresh seed per request when left alone, so one is always sent here -- generated
when the caller did not supply it -- and returned with the result, because an
approved take that cannot be rebuilt is not an asset. Qwen3 exposes no seed
because its server already fixes one per voice; an identical request reproduces
there on its own, and the result carries no seed field because there is nothing
to vary. What a seed buys is rebuilding THAT take from the same request -- it
does not make a different line match an approved one. Rebuilt means the same
audio, not the same file: the Ogg container carries a random bitstream serial,
so compare decoded samples.

*Explicit ``null`` reads as "not supplied", on purpose.* A model emitting
``{"style": null}`` means it wants none, and refusing that would reject a
well-formed call. Strictness applies to a value that looks like a direction but
cannot be used -- ``[]``, ``""``, a number -- which is refused rather than read
as absence.

Handlers take the model's JSON object as one positional dict, which is how the
registry dispatches every tool (``handler(args, **kwargs)``).
"""

from __future__ import annotations

import json
import logging
import random
import re
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

# Engines that can hold a character voice, in listing order, with the caveat
# the model needs in order to pick one. Deliberately not derived from
# tts.fallback.chain: this tool renders what it is told, and reading the chain
# would smuggle the language routing into an explicit contract.
_ENGINES: Tuple[Tuple[str, str], ...] = (
    (
        "irodori-tts",
        "Japanese only. Refuses English-dominant text instead of rendering it.",
    ),
    ("qwen3-tts", "Multilingual."),
)

_SEPARATOR = ":"
_OUTPUT_DIR = "voice-memos"
_OUTPUT_FORMAT = "ogg"
_VOICE_FORMATS = (".ogg", ".oga", ".opus")

# The ranges the shared cleaner strips, so exactly what it would remove is what
# gets parked. Kept as one class because a cluster may join several of them.
_EMOJI_RANGES = (
    "\U0001F1E6-\U0001F1FF"
    "\U0001F300-\U0001F5FF"
    "\U0001F600-\U0001F64F"
    "\U0001F680-\U0001F6FF"
    "\U0001F700-\U0001F77F"
    "\U0001F780-\U0001F7FF"
    "\U0001F800-\U0001F8FF"
    "\U0001F900-\U0001F9FF"
    "\U0001FA00-\U0001FAFF"
    "\u2600-\u27BF"
)
# Whole grapheme cluster, not a bare code point: a zero-width joiner sequence
# such as U+1F62E U+200D U+1F4A8 is one gesture to the model, and parking only
# its first half would leave the cleaner to delete the rest.
_EMOJI_CLUSTER = re.compile(
    f"[{_EMOJI_RANGES}](?:[\uFE0E\uFE0F]|\u200D[{_EMOJI_RANGES}])*"
)
# ASCII letters and digits with no underscore: every rule in the shared cleaner
# keys on markdown punctuation, symbols or digit-adjacency, so a token shaped
# like this passes through it untouched. Extended until it does not occur in the
# script, because restoration is a plain replace and a script that happened to
# contain the literal token would have an emoji spliced into it.
_EMOJI_SLOT_SEED = "zqxjemoji"

_SEED_MAX = 2**31 - 1


CHARACTER_VOICES_SCHEMA = {
    "name": "character_voices",
    "description": (
        "List the character voices registered on the local TTS engines. Every "
        "id is qualified as <engine>:<voice>; pass one verbatim to "
        "character_text_to_speech. Each engine also reports the style controls "
        "it honours: 'emoji' performs an emoji in the text as a non-verbal "
        "vocalisation, 'caption' accepts a delivery direction, 'seed' lets the "
        "caller pin the take (an engine without it fixes its own, so an "
        "identical request already reproduces there)."
    ),
    "parameters": {"type": "object", "properties": {}},
}

CHARACTER_TTS_SCHEMA = {
    "name": "character_text_to_speech",
    "description": (
        "Render a character voice asset with an explicitly registered voice. "
        "Use only for user-requested creative or scripted character audio. The "
        "qualified id fixes the engine as well as the voice, and this tool "
        "never substitutes either one, never falls back to the ordinary TTS "
        "chain, and writes no file when the render is refused."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "text": {
                "type": "string",
                "description": (
                    "Text to render with the selected character voice. On an "
                    "engine listing 'emoji' support, an emoji is performed as a "
                    "non-verbal vocalisation at the point it appears rather than "
                    "read out -- U+1F92D a stifled laugh, U+1F62D sobbing, "
                    "U+1F3B5 humming, U+1F620 a sulk -- so place one where the "
                    "sound belongs and use it sparingly; each costs real seconds "
                    "of audio. Other engines have them stripped as before."
                ),
            },
            "style": {
                "type": "string",
                "description": (
                    "Optional delivery direction in the language of the script, "
                    "e.g. 落ち着いた低い声で、ゆっくりと話す. Shapes pace and "
                    "manner across the whole take while the voice keeps its "
                    "identity. Rejected on an engine that does not list "
                    "'caption' support rather than being ignored."
                ),
            },
            "seed": {
                "type": "integer",
                "description": (
                    "Optional seed, on an engine listing 'seed' support. There, "
                    "omitting it still pins one and reports it back, and passing "
                    "a reported one rebuilds that exact take from the same "
                    "request — it does not make a different line match one. An "
                    "engine that does not list 'seed' rejects this because it "
                    "fixes its own; an identical request already reproduces "
                    "there and no seed is returned."
                ),
            },
            "voice": {
                "type": "string",
                "description": (
                    "Qualified voice id from character_voices, shaped "
                    "<engine>:<voice-id>. A bare voice id is rejected: the same "
                    "voice sounds different on each engine."
                ),
            },
            "output_path": {
                "type": "string",
                "description": (
                    "Optional output path. Defaults to a timestamped Ogg/Opus "
                    "file under ~/voice-memos/."
                ),
            },
            "speed": {
                "type": "number",
                "description": "Playback speed from 0.25 to 4.0. Defaults to 1.0.",
            },
        },
        "required": ["text", "voice"],
    },
}


def _provider(engine: str):
    from agent import tts_registry

    return tts_registry.get_provider(engine)


def _features(provider) -> frozenset:
    """Style controls a provider advertises; nothing when it advertises none."""
    try:
        declared = getattr(provider, "style_features", None) or ()
        return frozenset(str(item) for item in declared)
    except Exception as exc:  # noqa: BLE001 - a malformed property is "no support"
        logger.debug("character-voice: style_features unreadable: %s", exc)
        return frozenset()


def _voices_of(engine: str, provider) -> List[Dict[str, Any]]:
    entries: List[Dict[str, Any]] = []
    for raw in provider.list_voices():
        if not isinstance(raw, dict):
            continue
        voice = str(raw.get("id") or "").strip()
        if not voice:
            continue
        # irodori-tts advertises a synthetic reference-free entry whose timbre
        # is arbitrary. It is not a character, so it must never be offered as
        # one -- a card that picked it would render a different voice per run.
        if raw.get("no_ref") is True:
            continue
        entry: Dict[str, Any] = {
            "id": f"{engine}{_SEPARATOR}{voice}",
            "engine": engine,
            "voice": voice,
        }
        for key in ("display", "language"):
            value = raw.get(key)
            if isinstance(value, str) and value.strip():
                entry[key] = value.strip()
        entries.append(entry)
    return entries


def _catalog() -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """Return (voices, engines). Only a live engine contributes voices."""
    voices: List[Dict[str, Any]] = []
    engines: List[Dict[str, Any]] = []
    for engine, note in _ENGINES:
        provider = _provider(engine)
        if provider is None:
            engines.append({"name": engine, "status": "not enabled", "note": note})
            continue
        try:
            ready = bool(provider.is_available())
        except Exception as exc:  # noqa: BLE001 - a probe must not break listing
            logger.debug("character-voice: %s availability probe failed: %s", engine, exc)
            ready = False
        engines.append(
            {
                "name": engine,
                "status": "ready" if ready else "unavailable",
                "note": note,
                "style": sorted(_features(provider)),
            }
        )
        if ready:
            voices.extend(_voices_of(engine, provider))
    return voices, engines


def _engine_status(engines: List[Dict[str, Any]], name: str) -> Optional[str]:
    for engine in engines:
        if engine["name"] == name:
            return str(engine["status"])
    return None


def _resolve(voice_id: str) -> Dict[str, Any]:
    """Resolve a qualified id to a catalog entry, or raise with the reason."""
    voices, engines = _catalog()
    known = sorted(entry["id"] for entry in voices)

    if _SEPARATOR not in voice_id:
        raise ValueError(
            f"voice must be a qualified <engine>:<voice-id>, not {voice_id!r}. "
            f"Registered: {known or 'none'}"
        )

    engine, _, voice = voice_id.partition(_SEPARATOR)
    engine, voice = engine.strip(), voice.strip()
    status = _engine_status(engines, engine)
    if status is None:
        raise ValueError(
            f"unknown TTS engine {engine!r}. Engines: "
            f"{[item[0] for item in _ENGINES]}"
        )
    if status != "ready":
        raise ValueError(
            f"TTS engine {engine!r} is {status}; not rendering with another "
            "engine. Start it, or ask for a voice on a ready engine."
        )

    for entry in voices:
        if entry["engine"] == engine and entry["voice"] == voice:
            return entry
    raise ValueError(
        f"voice {voice!r} is not registered on {engine!r}. Registered: {known}"
    )


def _spoken(text: str, *, keep_emoji: bool = False) -> str:
    """Normalise a script for speech, keeping emoji when the engine performs them.

    The shared cleaner deletes emoji, which is right for an engine that would
    otherwise say "smiling face" and wrong for one that acts them out. Rather
    than fork it -- it also strips markdown, expands units and flattens newlines,
    all of which a character script still wants -- the clusters are parked behind
    ASCII placeholders that survive every rule in it, and restored afterwards.
    """
    parked: List[str] = []
    slot = _EMOJI_SLOT_SEED

    if keep_emoji:
        while slot in text:
            slot += "q"

        def park(match: "re.Match[str]") -> str:
            parked.append(match.group(0))
            return f"{slot}{len(parked) - 1}{slot}"

        text = _EMOJI_CLUSTER.sub(park, text)

    try:
        from tools.tts_text_normalize import prepare_spoken_text

        normalized = prepare_spoken_text(text, max_chars=None)
    except Exception:  # noqa: BLE001 - normalization is best-effort
        normalized = text.strip()

    for index, cluster in enumerate(parked):
        normalized = normalized.replace(f"{slot}{index}{slot}", cluster)

    if not normalized:
        raise ValueError("text is empty after TTS cleanup")
    return normalized


def _output_path(raw: Any) -> Path:
    if isinstance(raw, str) and raw.strip():
        from tools.path_security import has_traversal_component

        if has_traversal_component(raw):
            raise ValueError("output_path must not contain '..' components")
        file_path = Path(raw).expanduser()

        from agent.file_safety import is_write_denied

        if is_write_denied(str(file_path)):
            raise ValueError("output_path targets a protected path")
        if not file_path.suffix:
            file_path = file_path.with_suffix("." + _OUTPUT_FORMAT)
    else:
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
        file_path = Path.home() / _OUTPUT_DIR / f"character_{stamp}.{_OUTPUT_FORMAT}"
    file_path.parent.mkdir(parents=True, exist_ok=True)
    return file_path


def _character_voices(args: Optional[Dict[str, Any]] = None, **_kwargs: Any) -> str:
    voices, engines = _catalog()
    return json.dumps(
        {"success": True, "voices": voices, "engines": engines}, ensure_ascii=False
    )


def _character_text_to_speech(
    args: Optional[Dict[str, Any]] = None,
    **_kwargs: Any,
) -> str:
    args = args or {}
    requested = args.get("voice")
    requested = requested.strip() if isinstance(requested, str) else ""
    file_path: Optional[Path] = None
    preexisting = False
    try:
        text = args.get("text")
        if not isinstance(text, str) or not text.strip():
            raise ValueError("text is required")
        if not requested:
            raise ValueError("voice is required")

        entry = _resolve(requested)
        provider = _provider(entry["engine"])
        if provider is None:  # config changed between resolve and render
            raise ValueError(f"TTS engine {entry['engine']!r} is no longer registered")

        features = _features(provider)
        style_kwargs: Dict[str, Any] = {}

        # A malformed control is refused for the same reason an unsupported one
        # is: quietly reading it as "no style" would render a different
        # performance and report success.
        caption = args.get("style")
        if caption is not None:
            if not isinstance(caption, str) or not caption.strip():
                raise ValueError(
                    f"style must be a non-empty string, got {caption!r}"
                )
            if "caption" not in features:
                raise ValueError(
                    f"{entry['engine']} takes no style direction; rendering it "
                    "without one would not be the take you asked for. Drop "
                    "'style', or pick a voice on an engine that lists it."
                )
            style_kwargs["caption"] = caption.strip()

        seed = args.get("seed")
        if seed is not None:
            # bool is an int in Python, and True would silently pin seed 1.
            if isinstance(seed, bool) or not isinstance(seed, int):
                raise ValueError(f"seed must be an integer, got {seed!r}")
            if "seed" not in features:
                raise ValueError(
                    f"{entry['engine']} takes no caller seed because it fixes its "
                    "own; an identical request already reproduces there. Drop "
                    "'seed', or pick a voice on an engine that lists it."
                )
        if "seed" in features:
            # Always pinned: this engine draws a fresh seed per request, so an
            # unpinned take could never be rebuilt, and the caller can only
            # reuse a seed it was told.
            style_kwargs["seed"] = (
                int(seed) if seed is not None else random.randint(0, _SEED_MAX)
            )

        spoken = _spoken(text, keep_emoji="emoji" in features)
        file_path = _output_path(args.get("output_path"))
        preexisting = file_path.exists()

        try:
            result = provider.synthesize(
                spoken,
                str(file_path),
                voice=entry["voice"],
                speed=args.get("speed"),
                format=file_path.suffix.lstrip(".") or _OUTPUT_FORMAT,
                **style_kwargs,
            )
        except Exception as exc:  # noqa: BLE001 - reframed, never routed onward
            # An engine raising inside the chain means "let the next tier try",
            # and irodori-tts words its Japanese-only refusal that way. Here the
            # caller pinned the engine, so nothing follows: say so, or the
            # borrowed wording reads as a hand-off that already happened.
            raise RuntimeError(
                f"{entry['id']} rendered nothing and no other engine was tried: {exc}"
            ) from exc
        voice_compatible = result.lower().endswith(_VOICE_FORMATS)
        media_tag = f"MEDIA:{result}"
        if voice_compatible:
            media_tag = f"[[audio_as_voice]]\n{media_tag}"
        payload = {
            "success": True,
            "file_path": result,
            "media_tag": media_tag,
            "id": entry["id"],
            "engine": entry["engine"],
            "voice": entry["voice"],
            "voice_compatible": voice_compatible,
        }
        # Reported so the take can be reproduced or deliberately re-rolled.
        if "seed" in style_kwargs:
            payload["seed"] = style_kwargs["seed"]
        if "caption" in style_kwargs:
            payload["style"] = style_kwargs["caption"]
        return json.dumps(payload, ensure_ascii=False)
    except Exception as exc:  # noqa: BLE001 - tool errors are structured results
        # A refused render must leave nothing behind: half a file would read as
        # a delivered asset to whatever consumes the path next.
        if file_path is not None and not preexisting and file_path.exists():
            try:
                file_path.unlink()
            except OSError:
                logger.warning("character-voice: could not remove partial output")
        logger.error("character_text_to_speech failed: %s", exc, exc_info=True)
        return json.dumps(
            {"success": False, "error": str(exc), "id": requested},
            ensure_ascii=False,
        )


def register(ctx) -> None:
    # Creator owns character assets; nothing else should be able to spend an
    # engine on one, so the tools are not registered elsewhere at all.
    if ctx.profile_name != "creator":
        return
    ctx.register_tool(
        name="character_voices",
        toolset="tts",
        schema=CHARACTER_VOICES_SCHEMA,
        handler=_character_voices,
        description=CHARACTER_VOICES_SCHEMA["description"],
    )
    ctx.register_tool(
        name="character_text_to_speech",
        toolset="tts",
        schema=CHARACTER_TTS_SCHEMA,
        handler=_character_text_to_speech,
        description=CHARACTER_TTS_SCHEMA["description"],
    )
