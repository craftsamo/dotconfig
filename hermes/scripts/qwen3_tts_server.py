#!/usr/bin/env python3
"""Serve registered Qwen3-TTS cloned voices over a loopback HTTP API."""

from __future__ import annotations

import argparse
import hashlib
import io
import json
import logging
import os
import re
import tempfile
import threading
import wave
from collections import OrderedDict
from dataclasses import dataclass
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlparse

logger = logging.getLogger("qwen3-tts-server")

_MAX_REQUEST_BYTES = 1_000_000
_MAX_TEXT_CHARS = 10_000
_SHA256_PATTERN = re.compile(r"[0-9a-f]{64}")
_REVISION_PATTERN = re.compile(r"[0-9a-f]{40}")
_VOICE_ID_PATTERN = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,63}")

_CHUNK_MAX_CHARS = 200
_CHUNK_GAP_SECONDS = 0.15
_SENTENCE_PATTERN = re.compile(r"[^。！？!?]+(?:[。！？!?]+[」』）】]*)?")
_CLAUSE_PATTERN = re.compile(r"[^、]+(?:、)?")


def normalize_text(text: str) -> str:
    """Collapse whitespace runs (incl. newlines) into single spaces."""
    return re.sub(r"\s+", " ", text).strip()


def apply_lexicon(text: str, lexicon: dict[str, str]) -> str:
    """Replace surface forms with pronunciation readings, longest match first."""
    for surface in sorted(lexicon, key=len, reverse=True):
        text = text.replace(surface, lexicon[surface])
    return text


def _split_long_sentence(sentence: str, max_chars: int) -> list[str]:
    pieces: list[str] = []
    for clause in _CLAUSE_PATTERN.findall(sentence):
        while len(clause) > max_chars:
            pieces.append(clause[:max_chars])
            clause = clause[max_chars:]
        if clause:
            pieces.append(clause)
    return pieces or [sentence]


def split_text_into_chunks(text: str, max_chars: int = _CHUNK_MAX_CHARS) -> list[str]:
    """Split text into sentence-aligned chunks no longer than max_chars.

    Sentences are kept whole (with their terminators) and packed greedily;
    an overlong sentence falls back to clause boundaries, then hard slices.
    """
    if max_chars < 1:
        raise ValueError("max_chars must be positive")
    chunks: list[str] = []
    current = ""
    for sentence in _SENTENCE_PATTERN.findall(text):
        pieces = (
            [sentence]
            if len(sentence) <= max_chars
            else _split_long_sentence(sentence, max_chars)
        )
        for piece in pieces:
            if not current:
                current = piece
            elif len(current) + len(piece) <= max_chars:
                current += piece
            else:
                chunks.append(current)
                current = piece
    if current:
        chunks.append(current)
    return [chunk for chunk in (c.strip() for c in chunks) if chunk] or [text]


def parse_lexicon(payload: Any) -> dict[str, str]:
    if not isinstance(payload, dict):
        raise ValueError("pronunciation lexicon must be a JSON object")
    lexicon: dict[str, str] = {}
    for surface, reading in payload.items():
        if not isinstance(surface, str) or not surface:
            raise ValueError("pronunciation lexicon keys must be non-empty strings")
        if not isinstance(reading, str) or not reading.strip():
            raise ValueError(
                "pronunciation lexicon values must be non-empty strings"
            )
        lexicon[surface] = reading
    return lexicon


@dataclass(frozen=True)
class VoiceManifest:
    manifest_sha256: str
    voice_id: str
    display_name: str
    language: str
    locale: str
    model_name: str
    model_revision: str
    reference_audio: Path
    reference_audio_sha256: str
    reference_text_file: Path
    reference_text_sha256: str
    seed: int
    lexicon_file: Path | None = None
    lexicon_sha256: str | None = None


@dataclass(frozen=True)
class VoiceCatalog:
    catalog_sha256: str
    default_voice_id: str
    voices: dict[str, VoiceManifest]
    manifest_paths: dict[str, Path]


def load_voice_manifest(path: Path) -> VoiceManifest:
    manifest_path = path.expanduser().resolve()
    try:
        manifest_bytes = manifest_path.read_bytes()
        payload = json.loads(manifest_bytes.decode("utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError(f"cannot read voice manifest {manifest_path}: {exc}") from exc
    if not isinstance(payload, dict) or payload.get("schema_version") != 1:
        raise ValueError("voice manifest schema_version must be 1")

    def require_string(mapping: Any, key: str, section: str) -> str:
        value = mapping.get(key) if isinstance(mapping, dict) else None
        if not isinstance(value, str) or not value.strip():
            raise ValueError(f"voice manifest {section}.{key} must be a string")
        return value.strip()

    voice_id = require_string(payload, "id", "root")
    if not _VOICE_ID_PATTERN.fullmatch(voice_id):
        raise ValueError(
            "voice manifest id must contain only letters, numbers, dot, underscore, "
            "or hyphen"
        )
    display_name = require_string(payload, "display_name", "root")
    language = payload.get("language")
    language_name = require_string(language, "name", "language")
    locale = require_string(language, "locale", "language")
    model = payload.get("model")
    reference = payload.get("reference")
    generation = payload.get("generation")
    model_name = require_string(model, "name", "model")
    model_revision = require_string(model, "revision", "model")
    if not model_name.endswith("-Base"):
        raise ValueError("voice manifest model.name must select a Qwen3-TTS Base model")
    if not _REVISION_PATTERN.fullmatch(model_revision):
        raise ValueError("voice manifest model.revision must be a 40-character commit")

    def resolve_reference(entry: Any, key: str) -> Path:
        value = require_string(entry, "path", f"reference.{key}")
        candidate = Path(value).expanduser()
        if not candidate.is_absolute():
            candidate = manifest_path.parent / candidate
        resolved = candidate.resolve()
        if not resolved.is_file():
            raise ValueError(f"voice reference not found: {resolved}")
        return resolved

    def validate_digest(entry: Any, key: str, source: Path) -> str:
        expected = require_string(entry, "sha256", f"reference.{key}").lower()
        if not _SHA256_PATTERN.fullmatch(expected):
            raise ValueError(f"voice manifest reference.{key}.sha256 is invalid")
        digest = hashlib.sha256()
        with source.open("rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(chunk)
        if digest.hexdigest() != expected:
            raise ValueError(f"voice reference digest mismatch: {source}")
        return expected

    audio_entry = reference.get("audio") if isinstance(reference, dict) else None
    text_entry = reference.get("text") if isinstance(reference, dict) else None
    reference_audio = resolve_reference(audio_entry, "audio")
    reference_text_file = resolve_reference(text_entry, "text")
    reference_audio_sha256 = validate_digest(audio_entry, "audio", reference_audio)
    reference_text_sha256 = validate_digest(
        text_entry, "text", reference_text_file
    )

    if require_string(audio_entry, "format", "reference.audio").lower() != "wav":
        raise ValueError("voice manifest reference.audio.format must be wav")
    try:
        with wave.open(str(reference_audio), "rb") as audio:
            actual_audio = {
                "sample_rate": audio.getframerate(),
                "channels": audio.getnchannels(),
                "sample_width_bits": audio.getsampwidth() * 8,
                "frames": audio.getnframes(),
            }
    except (EOFError, OSError, wave.Error) as exc:
        raise ValueError(f"voice reference is not a readable PCM WAV: {exc}") from exc
    for key, actual in actual_audio.items():
        expected = audio_entry.get(key) if isinstance(audio_entry, dict) else None
        if isinstance(expected, bool) or not isinstance(expected, int):
            raise ValueError(f"voice manifest reference.audio.{key} must be an integer")
        if expected != actual:
            raise ValueError(
                f"voice reference {key} mismatch: expected {expected}, got {actual}"
            )

    try:
        reference_text = reference_text_file.read_text(encoding="utf-8").strip()
    except UnicodeDecodeError as exc:
        raise ValueError("voice reference text must be UTF-8") from exc
    if not reference_text:
        raise ValueError("voice reference text is empty")

    seed = generation.get("seed") if isinstance(generation, dict) else None
    if isinstance(seed, bool) or not isinstance(seed, int):
        raise ValueError("voice manifest generation.seed must be an integer")

    lexicon_file: Path | None = None
    lexicon_sha256: str | None = None
    pronunciation = payload.get("pronunciation")
    if pronunciation is not None:
        if not isinstance(pronunciation, dict):
            raise ValueError("voice manifest pronunciation must be an object")
        lexicon_entry = pronunciation.get("lexicon")
        if lexicon_entry is not None:
            lexicon_value = require_string(
                lexicon_entry, "path", "pronunciation.lexicon"
            )
            lexicon_candidate = Path(lexicon_value).expanduser()
            if not lexicon_candidate.is_absolute():
                lexicon_candidate = manifest_path.parent / lexicon_candidate
            lexicon_file = lexicon_candidate.resolve()
            if not lexicon_file.is_file():
                raise ValueError(f"pronunciation lexicon not found: {lexicon_file}")
            expected_lexicon = require_string(
                lexicon_entry, "sha256", "pronunciation.lexicon"
            ).lower()
            if not _SHA256_PATTERN.fullmatch(expected_lexicon):
                raise ValueError(
                    "voice manifest pronunciation.lexicon.sha256 is invalid"
                )
            lexicon_bytes = lexicon_file.read_bytes()
            if hashlib.sha256(lexicon_bytes).hexdigest() != expected_lexicon:
                raise ValueError(
                    f"pronunciation lexicon digest mismatch: {lexicon_file}"
                )
            lexicon_sha256 = expected_lexicon
            try:
                parse_lexicon(json.loads(lexicon_bytes.decode("utf-8")))
            except (UnicodeDecodeError, json.JSONDecodeError) as exc:
                raise ValueError(
                    "pronunciation lexicon must be UTF-8 JSON"
                ) from exc

    return VoiceManifest(
        manifest_sha256=hashlib.sha256(manifest_bytes).hexdigest(),
        voice_id=voice_id,
        display_name=display_name,
        language=language_name,
        locale=locale,
        model_name=model_name,
        model_revision=model_revision,
        reference_audio=reference_audio,
        reference_audio_sha256=reference_audio_sha256,
        reference_text_file=reference_text_file,
        reference_text_sha256=reference_text_sha256,
        seed=seed,
        lexicon_file=lexicon_file,
        lexicon_sha256=lexicon_sha256,
    )


def _resolve_catalog_manifest(catalog_path: Path, value: Any, voice_id: str) -> Path:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"voice catalog voices.{voice_id} must be a path string")
    candidate = Path(value).expanduser()
    if not candidate.is_absolute():
        candidate = catalog_path.parent / candidate
    resolved = candidate.resolve()
    if not resolved.is_file():
        raise ValueError(f"voice catalog manifest not found for {voice_id}")
    return resolved


def load_voice_catalog(path: Path) -> VoiceCatalog:
    catalog_path = path.expanduser().resolve()
    try:
        payload = json.loads(catalog_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError(f"cannot read voice catalog {catalog_path}: {exc}") from exc
    if not isinstance(payload, dict) or payload.get("schema_version") != 1:
        raise ValueError("voice catalog schema_version must be 1")
    default_voice_id = payload.get("default_voice")
    if not isinstance(default_voice_id, str) or not _VOICE_ID_PATTERN.fullmatch(
        default_voice_id
    ):
        raise ValueError("voice catalog default_voice is invalid")
    entries = payload.get("voices")
    if not isinstance(entries, dict) or not entries:
        raise ValueError("voice catalog voices must be a non-empty object")

    voices: dict[str, VoiceManifest] = {}
    manifest_paths: dict[str, Path] = {}
    for voice_id, manifest_value in sorted(entries.items()):
        if not isinstance(voice_id, str) or not _VOICE_ID_PATTERN.fullmatch(voice_id):
            raise ValueError("voice catalog contains an invalid voice id")
        manifest_path = _resolve_catalog_manifest(
            catalog_path, manifest_value, voice_id
        )
        manifest = load_voice_manifest(manifest_path)
        if manifest.voice_id != voice_id:
            raise ValueError(
                f"voice catalog key {voice_id!r} does not match manifest id "
                f"{manifest.voice_id!r}"
            )
        voices[voice_id] = manifest
        manifest_paths[voice_id] = manifest_path

    if default_voice_id not in voices:
        raise ValueError("voice catalog default_voice is not registered")
    model_identities = {
        (manifest.model_name, manifest.model_revision) for manifest in voices.values()
    }
    if len(model_identities) != 1:
        raise ValueError("all registered voices must use the same model and revision")

    identity = {
        "schema_version": 1,
        "default_voice": default_voice_id,
        "voices": {
            voice_id: voices[voice_id].manifest_sha256 for voice_id in sorted(voices)
        },
    }
    identity_bytes = json.dumps(
        identity, ensure_ascii=True, separators=(",", ":"), sort_keys=True
    ).encode("utf-8")
    return VoiceCatalog(
        catalog_sha256=hashlib.sha256(identity_bytes).hexdigest(),
        default_voice_id=default_voice_id,
        voices=voices,
        manifest_paths=manifest_paths,
    )


def write_voice_catalog(
    output_path: Path,
    *,
    base_catalog_path: Path | None = None,
    register_manifest_path: Path | None = None,
    set_default: bool = False,
    unregister_voice_id: str | None = None,
) -> VoiceCatalog:
    manifest_paths: dict[str, Path] = {}
    default_voice_id: str | None = None
    if base_catalog_path is not None:
        base = load_voice_catalog(base_catalog_path)
        manifest_paths.update(base.manifest_paths)
        default_voice_id = base.default_voice_id

    if register_manifest_path is not None:
        manifest_path = register_manifest_path.expanduser().resolve()
        manifest = load_voice_manifest(manifest_path)
        manifest_paths[manifest.voice_id] = manifest_path
        if default_voice_id is None or set_default:
            default_voice_id = manifest.voice_id

    if unregister_voice_id is not None:
        if unregister_voice_id == default_voice_id:
            raise ValueError("cannot unregister the default voice")
        if unregister_voice_id not in manifest_paths:
            raise ValueError(f"voice is not registered: {unregister_voice_id}")
        del manifest_paths[unregister_voice_id]

    if not manifest_paths or default_voice_id is None:
        raise ValueError("voice catalog must retain at least one default voice")
    payload = {
        "schema_version": 1,
        "default_voice": default_voice_id,
        "voices": {
            voice_id: str(manifest_paths[voice_id])
            for voice_id in sorted(manifest_paths)
        },
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return load_voice_catalog(output_path)


def resolve_model_snapshot(model_name: str, revision: str) -> Path:
    from huggingface_hub import snapshot_download

    return Path(snapshot_download(repo_id=model_name, revision=revision)).resolve()


class QwenSynthesizer:
    """Share one Base model across a bounded cache of cloned voice prompts."""

    def __init__(
        self,
        *,
        catalog: VoiceCatalog,
        release_id: str,
        device: str,
        dtype_name: str,
        prompt_cache_size: int,
    ) -> None:
        import torch
        from qwen_tts import Qwen3TTSModel

        dtype = {
            "bfloat16": torch.bfloat16,
            "float16": torch.float16,
            "float32": torch.float32,
        }[dtype_name]
        if prompt_cache_size < 1:
            raise ValueError("prompt cache size must be positive")
        default_voice = catalog.voices[catalog.default_voice_id]
        self.model_name = default_voice.model_name
        self.model_revision = default_voice.model_revision
        self.release_id = release_id
        self.catalog_sha256 = catalog.catalog_sha256
        self.default_voice_id = catalog.default_voice_id
        self.voices = catalog.voices
        self._torch = torch
        self._prompt_cache_size = prompt_cache_size
        self._voice_prompts: OrderedDict[str, Any] = OrderedDict()
        self._reference_snapshots: dict[str, tuple[Path, str]] = {}
        self._lexicons: dict[str, dict[str, str]] = {}
        self._reference_snapshot_dir = tempfile.TemporaryDirectory(
            prefix="qwen3_tts_refs_"
        )
        logger.info(
            "loading %s at %s on %s (%s)",
            self.model_name,
            self.model_revision,
            device,
            dtype_name,
        )
        model_snapshot = resolve_model_snapshot(
            self.model_name, self.model_revision
        )
        self._model = Qwen3TTSModel.from_pretrained(
            str(model_snapshot),
            device_map=device,
            dtype=dtype,
            attn_implementation=None,
        )
        supported_languages = self._model.get_supported_languages() or []
        supported = {str(language).casefold() for language in supported_languages}
        unsupported = sorted(
            manifest.language
            for manifest in self.voices.values()
            if supported and manifest.language.casefold() not in supported
        )
        if unsupported:
            raise ValueError(
                f"catalog contains unsupported model languages: {', '.join(unsupported)}"
            )
        logger.info("model ready with %d registered voices", len(self.voices))

    def list_voices(self) -> list[dict[str, str]]:
        return [
            {
                "id": manifest.voice_id,
                "display": manifest.display_name,
                "language": manifest.locale,
            }
            for manifest in self.voices.values()
        ]

    def _voice_prompt(self, voice_id: str) -> Any:
        if voice_id in self._voice_prompts:
            prompt = self._voice_prompts.pop(voice_id)
            self._voice_prompts[voice_id] = prompt
            return prompt
        reference_audio, reference_text = self._snapshot_reference(voice_id)
        logger.info("building voice prompt for %s", voice_id)
        prompt = self._model.create_voice_clone_prompt(
            ref_audio=str(reference_audio),
            ref_text=reference_text,
            x_vector_only_mode=False,
        )
        self._voice_prompts[voice_id] = prompt
        while len(self._voice_prompts) > self._prompt_cache_size:
            evicted_voice, _ = self._voice_prompts.popitem(last=False)
            logger.info("evicted voice prompt for %s", evicted_voice)
        return prompt

    def _snapshot_reference(self, voice_id: str) -> tuple[Path, str]:
        if voice_id in self._reference_snapshots:
            return self._reference_snapshots[voice_id]
        manifest = self.voices[voice_id]
        try:
            audio_bytes = manifest.reference_audio.read_bytes()
            text_bytes = manifest.reference_text_file.read_bytes()
        except OSError as exc:
            raise ValueError("registered voice reference cannot be read") from exc
        if hashlib.sha256(audio_bytes).hexdigest() != manifest.reference_audio_sha256:
            raise ValueError("registered voice audio digest mismatch")
        if hashlib.sha256(text_bytes).hexdigest() != manifest.reference_text_sha256:
            raise ValueError("registered voice text digest mismatch")
        try:
            reference_text = text_bytes.decode("utf-8").strip()
        except UnicodeDecodeError as exc:
            raise ValueError("registered voice reference text must be UTF-8") from exc
        if not reference_text:
            raise ValueError("registered voice reference text is empty")
        snapshot_path = (
            Path(self._reference_snapshot_dir.name) / f"{voice_id}.wav"
        )
        snapshot_path.write_bytes(audio_bytes)
        snapshot = (snapshot_path, reference_text)
        self._reference_snapshots[voice_id] = snapshot
        return snapshot

    def _lexicon(self, voice_id: str) -> dict[str, str]:
        if voice_id in self._lexicons:
            return self._lexicons[voice_id]
        manifest = self.voices[voice_id]
        if manifest.lexicon_file is None:
            lexicon: dict[str, str] = {}
        else:
            try:
                lexicon_bytes = manifest.lexicon_file.read_bytes()
            except OSError as exc:
                raise ValueError("registered voice lexicon cannot be read") from exc
            if hashlib.sha256(lexicon_bytes).hexdigest() != manifest.lexicon_sha256:
                raise ValueError("registered voice lexicon digest mismatch")
            try:
                lexicon = parse_lexicon(json.loads(lexicon_bytes.decode("utf-8")))
            except (UnicodeDecodeError, json.JSONDecodeError) as exc:
                raise ValueError(
                    "registered voice lexicon must be UTF-8 JSON"
                ) from exc
        self._lexicons[voice_id] = lexicon
        return lexicon

    def preprocess(self, text: str, voice_id: str) -> list[str]:
        """Normalize, apply the voice lexicon, and chunk into sentences."""
        processed = apply_lexicon(normalize_text(text), self._lexicon(voice_id))
        return split_text_into_chunks(processed)

    def _generate_segments(
        self, chunks: list[str], voice_id: str
    ) -> tuple[list[Any], int]:
        manifest = self.voices[voice_id]
        prompt = self._voice_prompt(voice_id)
        segments: list[Any] = []
        sample_rate = 0
        for chunk in chunks:
            self._torch.manual_seed(manifest.seed)
            wavs, sample_rate = self._model.generate_voice_clone(
                text=chunk,
                language=manifest.language,
                voice_clone_prompt=prompt,
            )
            segments.append(wavs[0])
        return segments, sample_rate

    def synthesize(self, text: str, voice_id: str) -> bytes:
        import numpy as np
        import soundfile as sf

        chunks = self.preprocess(text, voice_id)
        if len(chunks) > 1:
            logger.info("synthesizing %d chunks for %s", len(chunks), voice_id)
        segments, sample_rate = self._generate_segments(chunks, voice_id)

        arrays = [np.asarray(segment) for segment in segments]
        if len(arrays) == 1:
            audio = arrays[0]
        else:
            gap = np.zeros(
                int(sample_rate * _CHUNK_GAP_SECONDS), dtype=arrays[0].dtype
            )
            joined: list[Any] = []
            for index, array in enumerate(arrays):
                if index:
                    joined.append(gap)
                joined.append(array)
            audio = np.concatenate(joined)

        output = io.BytesIO()
        sf.write(output, audio, sample_rate, format="WAV", subtype="PCM_16")
        return output.getvalue()

    def close(self) -> None:
        self._reference_snapshot_dir.cleanup()


class QwenHTTPServer(ThreadingHTTPServer):
    daemon_threads = True

    def __init__(self, address: tuple[str, int], synthesizer: Any) -> None:
        super().__init__(address, QwenRequestHandler)
        self.synthesizer = synthesizer
        self.synthesis_lock = threading.Lock()


class QwenRequestHandler(BaseHTTPRequestHandler):
    server: QwenHTTPServer

    def log_message(self, format: str, *args: Any) -> None:
        logger.info("%s - %s", self.address_string(), format % args)

    def _send_json(self, status: int, payload: dict[str, Any]) -> None:
        data = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self) -> None:  # noqa: N802 - BaseHTTPRequestHandler API
        parsed = urlparse(self.path)
        if parsed.path == "/health":
            query = parse_qs(parsed.query)
            expected_release = query.get("release_id", [None])[0]
            expected_catalog = query.get("catalog_sha256", [None])[0]
            if expected_release not in (None, self.server.synthesizer.release_id):
                self._send_json(409, {"error": "release id mismatch"})
                return
            if expected_catalog not in (
                None,
                self.server.synthesizer.catalog_sha256,
            ):
                self._send_json(409, {"error": "catalog digest mismatch"})
                return
            self._send_json(
                200,
                {
                    "status": "ok",
                    "model": self.server.synthesizer.model_name,
                    "revision": self.server.synthesizer.model_revision,
                    "release_id": self.server.synthesizer.release_id,
                    "catalog_sha256": self.server.synthesizer.catalog_sha256,
                    "default_voice": self.server.synthesizer.default_voice_id,
                    "voice_count": len(self.server.synthesizer.voices),
                },
            )
            return
        if parsed.path == "/v1/audio/voices":
            self._send_json(
                200,
                {"voices": self.server.synthesizer.list_voices()},
            )
            return
        self._send_json(404, {"error": "not found"})

    def do_POST(self) -> None:  # noqa: N802 - BaseHTTPRequestHandler API
        if self.path != "/v1/audio/speech":
            self._send_json(404, {"error": "not found"})
            return

        try:
            length = int(self.headers.get("Content-Length", "0"))
        except ValueError:
            self._send_json(400, {"error": "invalid Content-Length"})
            return
        if length <= 0 or length > _MAX_REQUEST_BYTES:
            self._send_json(413, {"error": "request body is empty or too large"})
            return

        try:
            payload = json.loads(self.rfile.read(length).decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            self._send_json(400, {"error": "request body must be UTF-8 JSON"})
            return

        text = payload.get("input") if isinstance(payload, dict) else None
        if not isinstance(text, str) or not text.strip():
            self._send_json(400, {"error": "input must be a non-empty string"})
            return
        text = text.strip()
        if len(text) > _MAX_TEXT_CHARS:
            self._send_json(413, {"error": "input is too long"})
            return
        requested_voice = payload.get("voice")
        if requested_voice is None:
            voice_id = self.server.synthesizer.default_voice_id
        elif not isinstance(requested_voice, str) or not _VOICE_ID_PATTERN.fullmatch(
            requested_voice
        ):
            self._send_json(400, {"error": "requested voice id is invalid"})
            return
        elif requested_voice not in self.server.synthesizer.voices:
            self._send_json(400, {"error": "requested voice is not registered"})
            return
        else:
            voice_id = requested_voice
        voice = self.server.synthesizer.voices[voice_id]
        requested_model = payload.get("model")
        if requested_model not in (None, self.server.synthesizer.model_name):
            self._send_json(400, {"error": "requested model is not loaded"})
            return
        language = payload.get("language", voice.language)
        if not isinstance(language, str) or not language.strip():
            language = voice.language
        if language != voice.language:
            self._send_json(400, {"error": "requested language does not match voice"})
            return

        if not self.server.synthesis_lock.acquire(blocking=False):
            self._send_json(503, {"error": "synthesizer is busy"})
            return
        try:
            audio = self.server.synthesizer.synthesize(text, voice_id)
        except Exception as exc:  # noqa: BLE001 - return a useful HTTP error
            logger.exception("synthesis failed")
            self._send_json(500, {"error": f"synthesis failed: {exc}"})
            return
        finally:
            self.server.synthesis_lock.release()

        self.send_response(200)
        self.send_header("Content-Type", "audio/wav")
        self.send_header("Content-Length", str(len(audio)))
        self.end_headers()
        self.wfile.write(audio)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)

    check_manifest = commands.add_parser("check-manifest")
    check_manifest.add_argument("manifest", type=Path)

    check_catalog = commands.add_parser("check-catalog")
    check_catalog.add_argument("catalog", type=Path)
    check_catalog.add_argument("--digest", action="store_true")

    register = commands.add_parser("catalog-register")
    register.add_argument("--output", type=Path, required=True)
    register.add_argument("--catalog", type=Path)
    register.add_argument("--manifest", type=Path, required=True)
    register.add_argument("--default", action="store_true")

    unregister = commands.add_parser("catalog-unregister")
    unregister.add_argument("--output", type=Path, required=True)
    unregister.add_argument("--catalog", type=Path, required=True)
    unregister.add_argument("--voice", required=True)

    list_catalog = commands.add_parser("catalog-list")
    list_catalog.add_argument("catalog", type=Path)

    serve = commands.add_parser("serve")
    serve.add_argument("--host", default="127.0.0.1")
    serve.add_argument("--port", type=int, default=10102)
    serve.add_argument("--voice-catalog", type=Path, required=True)
    serve.add_argument("--release-id", required=True)
    serve.add_argument("--device", default="mps")
    serve.add_argument(
        "--dtype",
        choices=("bfloat16", "float16", "float32"),
        default="bfloat16",
    )
    serve.add_argument("--prompt-cache-size", type=int, default=8)
    return parser


def main() -> None:
    args = build_parser().parse_args()
    try:
        if args.command == "check-manifest":
            manifest = load_voice_manifest(args.manifest)
            print(
                json.dumps(
                    {
                        "status": "ok",
                        "voice": manifest.voice_id,
                        "model": manifest.model_name,
                        "revision": manifest.model_revision,
                    }
                )
            )
            return
        if args.command == "check-catalog":
            catalog = load_voice_catalog(args.catalog)
            if args.digest:
                print(catalog.catalog_sha256)
            else:
                print(
                    json.dumps(
                        {
                            "status": "ok",
                            "default_voice": catalog.default_voice_id,
                            "voice_count": len(catalog.voices),
                            "catalog_sha256": catalog.catalog_sha256,
                        }
                    )
                )
            return
        if args.command == "catalog-register":
            catalog = write_voice_catalog(
                args.output,
                base_catalog_path=args.catalog,
                register_manifest_path=args.manifest,
                set_default=args.default,
            )
            print(
                json.dumps(
                    {
                        "status": "ok",
                        "default_voice": catalog.default_voice_id,
                        "voice_count": len(catalog.voices),
                        "catalog_sha256": catalog.catalog_sha256,
                    }
                )
            )
            return
        if args.command == "catalog-unregister":
            catalog = write_voice_catalog(
                args.output,
                base_catalog_path=args.catalog,
                unregister_voice_id=args.voice,
            )
            print(
                json.dumps(
                    {
                        "status": "ok",
                        "default_voice": catalog.default_voice_id,
                        "voice_count": len(catalog.voices),
                        "catalog_sha256": catalog.catalog_sha256,
                    }
                )
            )
            return
        if args.command == "catalog-list":
            catalog = load_voice_catalog(args.catalog)
            print(
                json.dumps(
                    {
                        "default_voice": catalog.default_voice_id,
                        "voices": [
                            {
                                "id": voice.voice_id,
                                "display": voice.display_name,
                                "language": voice.locale,
                                "default": voice.voice_id
                                == catalog.default_voice_id,
                            }
                            for voice in catalog.voices.values()
                        ],
                    },
                    ensure_ascii=False,
                    indent=2,
                )
            )
            return
        if args.host not in {"127.0.0.1", "localhost", "::1"}:
            raise ValueError("refusing non-loopback bind")
        catalog = load_voice_catalog(args.voice_catalog)
    except ValueError as exc:
        raise SystemExit(str(exc)) from exc

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    synthesizer = QwenSynthesizer(
        catalog=catalog,
        release_id=args.release_id,
        device=args.device,
        dtype_name=args.dtype,
        prompt_cache_size=args.prompt_cache_size,
    )
    server = QwenHTTPServer((args.host, args.port), synthesizer)
    logger.info("listening on http://%s:%d", args.host, args.port)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
        synthesizer.close()


if __name__ == "__main__":
    main()
