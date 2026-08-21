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

Handlers take the model's JSON object as one positional dict, which is how the
registry dispatches every tool (``handler(args, **kwargs)``).
"""

from __future__ import annotations

import json
import logging
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


CHARACTER_VOICES_SCHEMA = {
    "name": "character_voices",
    "description": (
        "List the character voices registered on the local TTS engines. Every "
        "id is qualified as <engine>:<voice>; pass one verbatim to "
        "character_text_to_speech."
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
                "description": "Text to render with the selected character voice.",
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
            {"name": engine, "status": "ready" if ready else "unavailable", "note": note}
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


def _spoken(text: str) -> str:
    try:
        from tools.tts_text_normalize import prepare_spoken_text

        normalized = prepare_spoken_text(text, max_chars=None)
    except Exception:  # noqa: BLE001 - normalization is best-effort
        normalized = text.strip()
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

        spoken = _spoken(text)
        file_path = _output_path(args.get("output_path"))
        preexisting = file_path.exists()

        try:
            result = provider.synthesize(
                spoken,
                str(file_path),
                voice=entry["voice"],
                speed=args.get("speed"),
                format=file_path.suffix.lstrip(".") or _OUTPUT_FORMAT,
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
        return json.dumps(
            {
                "success": True,
                "file_path": result,
                "media_tag": media_tag,
                "id": entry["id"],
                "engine": entry["engine"],
                "voice": entry["voice"],
                "voice_compatible": voice_compatible,
            },
            ensure_ascii=False,
        )
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
