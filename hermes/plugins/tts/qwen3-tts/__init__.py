"""Hermes provider and Creator tools for local registered Qwen3-TTS voices."""

from __future__ import annotations

import json
import logging
import math
import os
import shutil
import subprocess
import tempfile
import urllib.error
import urllib.request
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from agent.tts_provider import TTSProvider

logger = logging.getLogger(__name__)

_FALLBACK_BASE_URL = "http://127.0.0.1:10102"
_AVAILABILITY_TIMEOUT = 3
_VOICES_TIMEOUT = 5
_SYNTHESIS_TIMEOUT = 600
_FFMPEG_TIMEOUT = 120


class Qwen3TTSProvider(TTSProvider):
    @property
    def name(self) -> str:
        return "qwen3-tts"

    @property
    def display_name(self) -> str:
        return "Qwen3-TTS (local)"

    @property
    def voice_compatible(self) -> bool:
        return True

    def _config(self) -> Dict[str, Any]:
        try:
            from hermes_cli.config import load_config

            tts = load_config().get("tts", {}) or {}
            block = tts.get("qwen3_tts", {})
            return block if isinstance(block, dict) else {}
        except Exception as exc:  # noqa: BLE001 - config is best-effort
            logger.debug("qwen3-tts: config load failed (%s); using defaults", exc)
            return {}

    def _base_url(self) -> str:
        return str(self._config().get("base_url") or _FALLBACK_BASE_URL).rstrip("/")

    def _timeout(self) -> int:
        try:
            timeout = int(self._config().get("synthesis_timeout"))
        except (TypeError, ValueError):
            return _SYNTHESIS_TIMEOUT
        return timeout if timeout > 0 else _SYNTHESIS_TIMEOUT

    def is_available(self) -> bool:
        try:
            req = urllib.request.Request(self._base_url() + "/health")
            with urllib.request.urlopen(req, timeout=_AVAILABILITY_TIMEOUT) as resp:
                return 200 <= resp.status < 300
        except Exception:
            return False

    def list_voices(self) -> List[Dict[str, Any]]:
        try:
            req = urllib.request.Request(self._base_url() + "/v1/audio/voices")
            with urllib.request.urlopen(req, timeout=_VOICES_TIMEOUT) as resp:
                payload = json.loads(resp.read().decode("utf-8"))
        except Exception as exc:  # noqa: BLE001
            logger.debug("qwen3-tts: list_voices failed: %s", exc)
            return []
        voices = payload.get("voices", []) if isinstance(payload, dict) else []
        return [voice for voice in voices if isinstance(voice, dict)]

    def get_setup_schema(self) -> Dict[str, Any]:
        return {
            "name": self.display_name,
            "badge": "local",
            "tag": "Qwen3-TTS registered voices on a loopback server (no API key)",
            "env_vars": [],
        }

    @staticmethod
    def _codec_args(ext: str) -> List[str]:
        ext = ext.lower().lstrip(".")
        if ext == "mp3":
            return ["-codec:a", "libmp3lame", "-q:a", "2"]
        if ext in ("ogg", "oga", "opus"):
            return ["-codec:a", "libopus", "-ac", "1", "-b:a", "64k", "-vbr", "off"]
        if ext in ("m4a", "aac"):
            return ["-codec:a", "aac", "-b:a", "128k"]
        return []

    @staticmethod
    def _atempo_filter(speed: float) -> Optional[str]:
        if abs(speed - 1.0) <= 0.001:
            return None
        factors: List[float] = []
        remaining = speed
        while remaining < 0.5:
            factors.append(0.5)
            remaining /= 0.5
        while remaining > 2.0:
            factors.append(2.0)
            remaining /= 2.0
        if abs(remaining - 1.0) > 0.001 or not factors:
            factors.append(remaining)
        return ",".join(f"atempo={factor:.6g}" for factor in factors)

    @staticmethod
    def _normalize_speed(speed: Optional[float]) -> float:
        if speed is None:
            return 1.0
        value = float(speed)
        if not math.isfinite(value) or value <= 0:
            raise ValueError("Qwen3-TTS speed must be a positive finite number")
        return max(0.25, min(4.0, value))

    def _write_audio(
        self,
        wav_bytes: bytes,
        output_path: str,
        speed: Optional[float],
        fmt_hint: Optional[str],
    ) -> str:
        ext = os.path.splitext(output_path)[1].lower()
        if not ext and fmt_hint:
            ext = "." + str(fmt_hint).lower().lstrip(".")
        speed_value = self._normalize_speed(speed)
        needs_transcode = ext not in ("", ".wav") or abs(speed_value - 1.0) > 0.001

        if not needs_transcode:
            with open(output_path, "wb") as output:
                output.write(wav_bytes)
            return output_path

        ffmpeg = shutil.which("ffmpeg")
        if not ffmpeg:
            raise RuntimeError("ffmpeg is required to encode or retime Qwen3-TTS audio")

        tmp_wav = None
        try:
            fd, tmp_wav = tempfile.mkstemp(suffix=".wav", prefix="qwen3_tts_src_")
            with os.fdopen(fd, "wb") as output:
                output.write(wav_bytes)
            command = [ffmpeg, "-nostdin", "-y", "-loglevel", "error", "-i", tmp_wav]
            if atempo_filter := self._atempo_filter(speed_value):
                command += ["-filter:a", atempo_filter]
            command += self._codec_args(ext)
            command.append(output_path)
            result = subprocess.run(
                command,
                capture_output=True,
                timeout=_FFMPEG_TIMEOUT,
                stdin=subprocess.DEVNULL,
            )
            if result.returncode != 0:
                detail = result.stderr.decode("utf-8", "replace")[:300]
                raise RuntimeError(f"ffmpeg failed to encode Qwen3-TTS audio: {detail}")
            if not os.path.exists(output_path) or os.path.getsize(output_path) <= 0:
                raise RuntimeError("ffmpeg produced no Qwen3-TTS audio")
            return output_path
        finally:
            if tmp_wav:
                try:
                    os.unlink(tmp_wav)
                except OSError:
                    pass

    def synthesize(
        self,
        text: str,
        output_path: str,
        *,
        voice: Optional[str] = None,
        model: Optional[str] = None,
        speed: Optional[float] = None,
        format: str = "wav",
        **extra: Any,
    ) -> str:
        request_payload = {"input": text}
        if isinstance(voice, str) and voice.strip():
            request_payload["voice"] = voice.strip()
        if isinstance(model, str) and model.strip():
            request_payload["model"] = model.strip()
        payload = json.dumps(request_payload).encode("utf-8")
        req = urllib.request.Request(
            self._base_url() + "/v1/audio/speech",
            data=payload,
            method="POST",
            headers={"Content-Type": "application/json", "Accept": "audio/wav"},
        )
        try:
            with urllib.request.urlopen(req, timeout=self._timeout()) as resp:
                audio = resp.read()
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", "replace")[:300]
            raise RuntimeError(
                f"Qwen3-TTS synthesis failed: HTTP {exc.code} {exc.reason}. {detail}"
            ) from exc
        except urllib.error.URLError as exc:
            raise RuntimeError(
                f"Qwen3-TTS server not reachable at {self._base_url()}: {exc.reason}"
            ) from exc
        if not audio:
            raise RuntimeError("Qwen3-TTS server returned empty audio")
        return self._write_audio(audio, output_path, speed, format)


CHARACTER_VOICES_SCHEMA = {
    "name": "character_voices",
    "description": (
        "List the locally registered character voice IDs available to Creator. "
        "Use an ID from this list with character_text_to_speech."
    ),
    "parameters": {"type": "object", "properties": {}},
}

CHARACTER_TTS_SCHEMA = {
    "name": "character_text_to_speech",
    "description": (
        "Render a character voice asset with an explicitly registered local voice ID. "
        "Use only for user-requested creative or scripted character audio. This tool "
        "does not silently fall back to a different voice."
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
                "description": "Registered voice ID returned by character_voices.",
            },
            "output_path": {
                "type": "string",
                "description": (
                    "Optional output path. Defaults to a timestamped Ogg/Opus file "
                    "under ~/voice-memos/."
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


def _character_voices() -> str:
    voices = Qwen3TTSProvider().list_voices()
    return json.dumps(
        {"success": True, "voices": voices}, ensure_ascii=False
    )


def _character_text_to_speech(
    text: str,
    voice: str,
    output_path: Optional[str] = None,
    speed: Optional[float] = None,
) -> str:
    try:
        if not isinstance(text, str) or not text.strip():
            raise ValueError("text is required")
        if not isinstance(voice, str) or not voice.strip():
            raise ValueError("voice is required")
        try:
            from tools.tts_text_normalize import prepare_spoken_text

            normalized_text = prepare_spoken_text(text, max_chars=None)
        except Exception:
            normalized_text = text.strip()
        if not normalized_text:
            raise ValueError("text is empty after TTS cleanup")

        if output_path:
            from tools.path_security import has_traversal_component

            if has_traversal_component(output_path):
                raise ValueError("output_path must not contain '..' components")
            file_path = Path(output_path).expanduser()
            from agent.file_safety import is_write_denied

            if is_write_denied(str(file_path)):
                raise ValueError("output_path targets a protected path")
            if not file_path.suffix:
                file_path = file_path.with_suffix(".ogg")
        else:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
            file_path = Path.home() / "voice-memos" / f"character_{timestamp}.ogg"
        file_path.parent.mkdir(parents=True, exist_ok=True)

        result = Qwen3TTSProvider().synthesize(
            normalized_text,
            str(file_path),
            voice=voice.strip(),
            speed=speed,
            format=file_path.suffix.lstrip(".") or "ogg",
        )
        voice_compatible = result.lower().endswith((".ogg", ".oga", ".opus"))
        media_tag = f"MEDIA:{result}"
        if voice_compatible:
            media_tag = f"[[audio_as_voice]]\n{media_tag}"
        return json.dumps(
            {
                "success": True,
                "file_path": result,
                "media_tag": media_tag,
                "provider": "qwen3-tts",
                "voice": voice.strip(),
                "voice_compatible": voice_compatible,
            },
            ensure_ascii=False,
        )
    except Exception as exc:  # noqa: BLE001 - tool errors are structured results
        logger.error("character_text_to_speech failed: %s", exc, exc_info=True)
        return json.dumps(
            {"success": False, "error": str(exc), "voice": voice},
            ensure_ascii=False,
        )


def register(ctx) -> None:
    ctx.register_tts_provider(Qwen3TTSProvider())
    if ctx.profile_name == "creator":
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
