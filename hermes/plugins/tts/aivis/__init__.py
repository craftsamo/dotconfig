"""AivisSpeech text-to-speech provider plugin.

AivisSpeech (https://aivis-project.github.io/AivisSpeech-Engine/api/) is a
Japanese TTS engine whose local HTTP API is broadly VOICEVOX-compatible: the
default endpoint is ``http://127.0.0.1:10101`` and synthesis is a two-step
flow — ``POST /audio_query?speaker=<style_id>&text=...`` returns an AudioQuery
JSON, which is then ``POST /synthesis?speaker=<style_id>`` to receive WAV bytes.

This registers a Hermes ``TTSProvider`` (see ``agent/tts_provider.py``) named
``aivis``. It is selected per profile via ``tts.provider: aivis`` and enabled
via ``plugins.enabled: [aivis]``. Stdlib-only (urllib) so it adds no
dependency to the Hermes venv. The engine must be running locally — this
plugin does not manage its lifecycle.

Config (optional, read from the active profile's ``config.yaml``)::

    tts:
      provider: aivis
      aivis:
        base_url: http://127.0.0.1:10101
        speaker: "888753760"   # Anneli / ノーマル (see GET /speakers)

The dispatcher also passes ``voice`` (from ``tts.voice``); when set it wins
over ``tts.aivis.speaker``. ``voice_compatible`` is True so the gateway will
transcode the WAV to Opus for voice delivery (Telegram voice notes / Discord
voice channels).
"""

from __future__ import annotations

import json
import logging
import urllib.parse
import urllib.request
from typing import Any, Dict, List, Optional

from agent.tts_provider import TTSProvider

logger = logging.getLogger(__name__)

# Fallbacks used when neither the config block nor the call args supply a value.
_FALLBACK_BASE_URL = "http://127.0.0.1:10101"
_FALLBACK_SPEAKER = "888753760"  # Anneli / ノーマル — AivisSpeech default voice

_AUDIO_QUERY_TIMEOUT = 30
_SYNTHESIS_TIMEOUT = 120
_AVAILABILITY_TIMEOUT = 3
_VOICES_TIMEOUT = 5


class AivisProvider(TTSProvider):
    """TTS backend that drives a local AivisSpeech Engine over HTTP."""

    @property
    def name(self) -> str:
        return "aivis"

    @property
    def display_name(self) -> str:
        return "AivisSpeech (local)"

    @property
    def voice_compatible(self) -> bool:
        # WAV output; the gateway runs ffmpeg -> Opus for voice delivery.
        return True

    # -- config -----------------------------------------------------------
    def _config(self) -> Dict[str, Any]:
        """Return the ``tts.aivis`` block from the active profile config."""
        try:
            from hermes_cli.config import load_config

            tts = load_config().get("tts", {}) or {}
            block = tts.get("aivis", {})
            return block if isinstance(block, dict) else {}
        except Exception as exc:  # noqa: BLE001 — config is best-effort
            logger.debug("aivis: config load failed (%s); using fallbacks", exc)
            return {}

    def _base_url(self) -> str:
        return str(self._config().get("base_url") or _FALLBACK_BASE_URL).rstrip("/")

    def _speaker(self, voice: Optional[str]) -> str:
        if isinstance(voice, str) and voice.strip():
            return voice.strip()
        return str(self._config().get("speaker") or _FALLBACK_SPEAKER)

    # -- introspection (optional) ----------------------------------------
    def is_available(self) -> bool:
        try:
            req = urllib.request.Request(self._base_url() + "/version")
            with urllib.request.urlopen(req, timeout=_AVAILABILITY_TIMEOUT) as resp:
                return 200 <= resp.status < 300
        except Exception:
            return False

    def list_voices(self) -> List[Dict[str, Any]]:
        try:
            req = urllib.request.Request(self._base_url() + "/speakers")
            with urllib.request.urlopen(req, timeout=_VOICES_TIMEOUT) as resp:
                speakers = json.loads(resp.read().decode("utf-8"))
        except Exception as exc:  # noqa: BLE001
            logger.debug("aivis: list_voices failed: %s", exc)
            return []
        voices: List[Dict[str, Any]] = []
        for sp in speakers or []:
            sp_name = sp.get("name", "")
            for style in sp.get("styles", []) or []:
                sid = style.get("id")
                if sid is None:
                    continue
                voices.append(
                    {
                        "id": str(sid),
                        "display": f"{sp_name} — {style.get('name', '')}".strip(" —"),
                        "language": "ja",
                    }
                )
        return voices

    def get_setup_schema(self) -> Dict[str, Any]:
        return {
            "name": self.display_name,
            "badge": "local",
            "tag": "VOICEVOX-compatible local engine (no API key)",
            "env_vars": [],
        }

    # -- synthesis --------------------------------------------------------
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
        base = self._base_url()
        speaker = self._speaker(voice)

        # 1) text -> AudioQuery (speaker + text are query params; empty body POST)
        aq_url = f"{base}/audio_query?" + urllib.parse.urlencode(
            {"speaker": speaker, "text": text}
        )
        aq_req = urllib.request.Request(aq_url, data=b"", method="POST")
        with urllib.request.urlopen(aq_req, timeout=_AUDIO_QUERY_TIMEOUT) as resp:
            query = json.loads(resp.read().decode("utf-8"))

        # Pass the AudioQuery through unmodified except for an optional speed
        # tweak (editing other fields can break AivisSpeech synthesis).
        if isinstance(speed, (int, float)) and speed > 0:
            query["speedScale"] = float(speed)

        # 2) AudioQuery -> WAV bytes
        sy_url = f"{base}/synthesis?speaker={urllib.parse.quote(str(speaker))}"
        sy_req = urllib.request.Request(
            sy_url,
            data=json.dumps(query).encode("utf-8"),
            method="POST",
            headers={"Content-Type": "application/json", "Accept": "audio/wav"},
        )
        with urllib.request.urlopen(sy_req, timeout=_SYNTHESIS_TIMEOUT) as resp:
            audio = resp.read()

        if not audio:
            raise RuntimeError("AivisSpeech /synthesis returned empty audio")

        with open(output_path, "wb") as fh:
            fh.write(audio)
        return output_path


def register(ctx) -> None:
    """Plugin entry point — register the AivisSpeech TTS provider."""
    ctx.register_tts_provider(AivisProvider())
