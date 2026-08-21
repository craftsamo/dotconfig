"""Hermes TTS provider for the local Irodori-TTS server.

Irodori-TTS-Server speaks the same OpenAI-compatible ``POST /v1/audio/speech``
contract as the qwen3-tts engine, so the client half mirrors that plugin. What
is specific to this backend is everything around the call.

**Japanese only.** The model has no English pronunciation dictionary. Measured
against qwen3-tts on English-only text it scores 27.0% word error rate versus
8.3%, mangling ``finished`` into "finito" and ``schema`` into "sesame". So this
provider *declines* English-dominant text by raising, which lets the ordinary
``tts-fallback`` chain advance to qwen3-tts. Routing is therefore a property of
this provider rather than a new mechanism, and because the hand-off happens at
message granularity it never splices two engines inside one utterance -- the
same reference voice renders 309 cents apart on the two engines (against 20-40
cents of seed-to-seed variation), so a mid-sentence switch is audible.

**Latin proper nouns** get a katakana substitution pass from ``lexicon.json``.

**Style control is real and measured.** The checkpoint performs an emoji as a
non-verbal vocalisation instead of reading it out, and takes a free-text
``caption`` describing delivery. Both were verified against this server: the
render is byte-identical for a pinned seed, and the predicted duration is
seed-invariant (5.24 s across three seeds) yet moves to 6.92 s when a single
``U+1F92D`` is spliced into the same sentence, while the transcript stays the
same words -- so the extra 1.68 s is added vocalisation, not a re-roll and not
the emoji being spoken. A caption moves it the way its wording implies
("ゆっくり" +0.56 s, "早口で" -0.32 s). None of that is reachable from
``tts.fallback.chain``, which passes no style arguments; it exists for the
explicit character-voice contract, which asks via ``style_features``.

**Three output defects** are repaired before the audio is handed back. All were
measured on this machine, and none can be fixed by changing the reference:

  leading dead air  Both engines reproduce the reference clip's leading
                    silence. Irodori is mild (10-145 ms) where qwen3-tts emits
                    0.72-1.59 s, but the trim is engine-agnostic.

  trailing junk     After the sentence ends the model may append a rustle, or
                    -- when the duration predictor over-allocates -- voiced
                    fragments hallucinated into the slack (1.63 s of them in
                    one measured case). These sit at -33..-48 dB, above any
                    silence gate.

  in-pause rustle   The codec emits a burst of aperiodic high-frequency energy
                    as a vowel decays: ~50 ms at -37 dB against a -77 dB pause,
                    which is plainly audible. Suppressing it without eating
                    fricatives is the subtle part -- see ``_degate``.

Only ``numpy`` and the standard library are used, because the Hermes venv has
numpy but not soundfile or scipy. Adding a dependency here would break the
hash-locked requirements contract.
"""

from __future__ import annotations

import io
import json
import logging
import math
import os
import re
import shutil
import struct
import subprocess
import tempfile
import urllib.error
import urllib.request
import wave
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

from agent.tts_provider import TTSProvider

logger = logging.getLogger(__name__)

_FALLBACK_BASE_URL = "http://127.0.0.1:10103"
_MODEL_ID = "irodori-tts"
_AVAILABILITY_TIMEOUT = 3
_VOICES_TIMEOUT = 5
_SYNTHESIS_TIMEOUT = 900
_FFMPEG_TIMEOUT = 120

# Below this share of Japanese script the text is English-dominant and is
# deferred to the next tier. Kana and kanji only: Latin letters inside an
# otherwise Japanese sentence (product names, code identifiers) must not push it
# over the edge, and those Irodori handles fine.
#
# The bar is deliberately low. This is a Japanese-first environment, and the
# cost of the two mistakes is asymmetric: sending mixed text to Irodori costs
# some mispronounced English inside an otherwise good Japanese render, whereas
# sending it to Qwen costs the Japanese as well. Only text with essentially no
# Japanese in it should leave. A half-and-half sentence ("This is an English
# sentence mixed in. ここから日本語に戻ります。" measures 29%) stays here.
_JA_MIN_RATIO = 0.20
_JA_MIN_CHARS = 2

_JA_CHARS = re.compile(r"[\u3040-\u309F\u30A0-\u30FF\u4E00-\u9FFF\u3005\u30FC]")
_SCRIPT_CHARS = re.compile(r"[^\s\d\W]|[\u3040-\u309F\u30A0-\u30FF\u4E00-\u9FFF]")


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
_LEXICON_ENV = "IRODORI_TTS_LEXICON"
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


def _lexicon_path() -> Path:
    override = os.environ.get(_LEXICON_ENV)
    if override:
        return Path(override).expanduser()
    return _runtime_dir() / "lexicon.json"


def _load_lexicon() -> Tuple[Dict[str, str], Optional[re.Pattern]]:
    global _lexicon_cache
    if _lexicon_cache is not None:
        return _lexicon_cache
    terms: Dict[str, str] = {}
    path = _lexicon_path()
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
        candidate = raw.get("terms") if isinstance(raw, dict) else None
        if isinstance(candidate, dict):
            terms = {
                str(k): str(v)
                for k, v in candidate.items()
                if isinstance(k, str) and isinstance(v, str) and k
            }
        logger.debug("irodori-tts: loaded %d lexicon term(s)", len(terms))
    except FileNotFoundError:
        # Optional: without it, Latin proper nouns are simply read as the model
        # sees them.
        logger.debug("irodori-tts: no lexicon at %s; skipping substitution", path)
    except Exception as exc:  # noqa: BLE001 - the lexicon is an optimisation
        logger.warning("irodori-tts: lexicon at %s unreadable (%s); skipping", path, exc)

    pattern: Optional[re.Pattern] = None
    if terms:
        parts = []
        # Longest first so "Claude Code" beats "Claude". ASCII keys get word
        # boundaries so "Gemini" does not fire inside "GeminiFooBar".
        for key in sorted(terms, key=len, reverse=True):
            esc = re.escape(key)
            if key[0].isascii() and key[0].isalnum():
                esc = r"\b" + esc
            if key[-1].isascii() and key[-1].isalnum():
                esc = esc + r"\b"
            parts.append(esc)
        pattern = re.compile("|".join(parts))
    _lexicon_cache = (terms, pattern)
    return _lexicon_cache


def apply_lexicon(text: str) -> str:
    """Rewrite known Latin proper nouns as katakana."""
    terms, pattern = _load_lexicon()
    if not pattern:
        return text
    return pattern.sub(lambda m: terms.get(m.group(0), m.group(0)), text)


def japanese_ratio(text: str) -> float:
    """Share of script characters that are kana or kanji.

    Digits, punctuation and whitespace are excluded so that "PyTorch 2.10 と
    Python 3.10 が必要です。" is judged on its words, not its numbers.
    """
    script = _SCRIPT_CHARS.findall(text)
    if not script:
        return 0.0
    return len(_JA_CHARS.findall(text)) / len(script)


def is_japanese_enough(text: str) -> bool:
    if len(_JA_CHARS.findall(text)) < _JA_MIN_CHARS:
        return False
    return japanese_ratio(text) >= _JA_MIN_RATIO


# --------------------------------------------------------------------------
# WAV codec (stdlib wave + numpy; soundfile is not available in the venv)
# --------------------------------------------------------------------------


def _decode_wav(data: bytes) -> Tuple[np.ndarray, int]:
    """Decode PCM WAV bytes to mono float64 in [-1, 1]."""
    with wave.open(io.BytesIO(data), "rb") as handle:
        channels = handle.getnchannels()
        width = handle.getsampwidth()
        rate = handle.getframerate()
        raw = handle.readframes(handle.getnframes())

    if width == 1:
        samples = (np.frombuffer(raw, dtype=np.uint8).astype(np.float64) - 128.0) / 128.0
    elif width == 2:
        samples = np.frombuffer(raw, dtype="<i2").astype(np.float64) / 32768.0
    elif width == 3:
        packed = np.frombuffer(raw, dtype=np.uint8).reshape(-1, 3)
        ints = (
            packed[:, 0].astype(np.int32)
            | (packed[:, 1].astype(np.int32) << 8)
            | (packed[:, 2].astype(np.int32) << 16)
        )
        ints = np.where(ints & 0x800000, ints - 0x1000000, ints)
        samples = ints.astype(np.float64) / 8388608.0
    elif width == 4:
        samples = np.frombuffer(raw, dtype="<i4").astype(np.float64) / 2147483648.0
    else:
        raise RuntimeError(f"unsupported WAV sample width: {width} bytes")

    if channels > 1:
        samples = samples.reshape(-1, channels).mean(axis=1)
    return samples, rate


def _encode_wav(samples: np.ndarray, rate: int) -> bytes:
    clipped = np.clip(samples, -1.0, 1.0)
    pcm = np.round(clipped * 32767.0).astype("<i2")
    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as handle:
        handle.setnchannels(1)
        handle.setsampwidth(2)
        handle.setframerate(rate)
        handle.writeframes(pcm.tobytes())
    return buffer.getvalue()


# --------------------------------------------------------------------------
# Frame analysis
# --------------------------------------------------------------------------

_FRAME = 0.010


def _frames(samples: np.ndarray, rate: int, frame: float = _FRAME) -> Tuple[np.ndarray, int]:
    hop = max(1, int(rate * frame))
    count = len(samples) // hop
    if count == 0:
        return np.empty((0, hop)), hop
    return samples[: count * hop].reshape(count, hop), hop


def _rms_db(frames: np.ndarray) -> np.ndarray:
    if frames.size == 0:
        return np.empty(0)
    return 20.0 * np.log10(np.sqrt((frames**2).mean(axis=1)) + 1e-12)


def _hf_share(frames: np.ndarray, rate: int, cutoff: float = 4000.0) -> np.ndarray:
    """Fraction of frame energy above *cutoff*. Vowels sit near 0, sibilants
    and the codec rustle near 1."""
    if frames.size == 0:
        return np.empty(0)
    spectrum = np.abs(np.fft.rfft(frames * np.hanning(frames.shape[1]), axis=1)) ** 2
    freqs = np.fft.rfftfreq(frames.shape[1], 1.0 / rate)
    return spectrum[:, freqs >= cutoff].sum(axis=1) / (spectrum.sum(axis=1) + 1e-20)


def _periodicity(frames: np.ndarray, rate: int) -> np.ndarray:
    """Peak normalised autocorrelation inside the 70-400 Hz pitch range.

    Computed through the FFT for every frame at once; a per-frame ``np.correlate``
    loop would add seconds of latency on a long render.
    """
    if frames.size == 0:
        return np.empty(0)
    hop = frames.shape[1]
    centred = frames - frames.mean(axis=1, keepdims=True)
    size = 1 << int(math.ceil(math.log2(max(2 * hop, 2))))
    spectrum = np.fft.rfft(centred, n=size, axis=1)
    auto = np.fft.irfft(spectrum * np.conj(spectrum), n=size, axis=1)[:, :hop]
    zero = auto[:, :1].copy()
    zero[zero <= 0] = 1.0
    auto = auto / zero
    low, high = int(rate / 400), min(int(rate / 70), hop - 1)
    if high <= low:
        return np.zeros(len(frames))
    return auto[:, low:high].max(axis=1)


# --------------------------------------------------------------------------
# Defect repair
# --------------------------------------------------------------------------

_NOISE_DB = -70.0        # below this there is nothing worth gating
_HF_SHARE = 0.55
_APERIODIC = 0.40
_VOICED_DB = -42.0
_VOICED_PER = 0.45       # pitch structure is what marks a following vowel
_LOOKAHEAD = 0.25
# A phrase-final devoiced vowel (the /u/ of です, the /i/ of しました) is also
# aperiodic high-frequency energy with nothing after it. Measured, the two
# separate cleanly by size: a devoiced vowel carries syllabic energy (130-190 ms
# at -23..-27 dB) while the codec artifact is residue (~50 ms at -37 dB).
_MAX_SPAN_DB = -30.0
_MAX_SPAN_S = 0.12
_ATTEN_DB = -60.0
_SPAN_PAD = 1
_GATE_ATTACK = 0.004
_GATE_RELEASE = 0.040


def _smooth_gain(gain: np.ndarray, attack: float, release: float) -> np.ndarray:
    """One-pole gain smoothing so the suppression cannot itself be heard."""
    out = np.empty_like(gain)
    current = gain[0] if gain.size else 1.0
    per_second = 1.0 / _FRAME
    a_att = math.exp(-1.0 / max(attack * per_second, 1e-9))
    a_rel = math.exp(-1.0 / max(release * per_second, 1e-9))
    for i, target in enumerate(gain):
        coef = a_att if target < current else a_rel
        current = coef * current + (1.0 - coef) * target
        out[i] = current
    return out


def _degate(samples: np.ndarray, rate: int) -> Tuple[np.ndarray, int]:
    """Suppress in-pause codec rustle, leaving fricatives intact.

    Level and spectrum alone cannot tell them apart: the /s/ of 「それ」 measures
    99% high-frequency with periodicity 0.19, identical to the artifact. The
    difference is what follows. A fricative is the leading edge of a syllable,
    so a vowel arrives within tens of milliseconds; the artifact is followed by
    nothing. That test plus the size bounds above is what makes this safe.
    """
    frames, hop = _frames(samples, rate)
    if frames.size == 0:
        return samples, 0
    rms = _rms_db(frames)
    hf = _hf_share(frames, rate)
    period = _periodicity(frames, rate)

    voiced = (rms > _VOICED_DB) & (period > _VOICED_PER)
    look = max(1, int(round(_LOOKAHEAD / _FRAME)))
    voiced_ahead = np.zeros(len(rms), dtype=bool)
    pending = 0
    for i in range(len(rms) - 1, -1, -1):
        pending = look if voiced[i] else max(0, pending - 1)
        voiced_ahead[i] = pending > 0

    candidate = (
        (rms > _NOISE_DB) & (hf > _HF_SHARE) & (period < _APERIODIC) & (~voiced_ahead)
    )

    flagged = np.zeros_like(candidate)
    gated = 0
    index = 0
    while index < len(candidate):
        if not candidate[index]:
            index += 1
            continue
        end = index
        while end < len(candidate) and candidate[end]:
            end += 1
        peak = float(rms[index:end].max())
        duration = (end - index) * _FRAME
        if peak <= _MAX_SPAN_DB and duration <= _MAX_SPAN_S:
            flagged[max(0, index - _SPAN_PAD) : min(len(flagged), end + _SPAN_PAD)] = True
            gated += 1
        index = end

    if not gated:
        return samples, 0

    gain = _smooth_gain(
        np.where(flagged, 10 ** (_ATTEN_DB / 20.0), 1.0), _GATE_ATTACK, _GATE_RELEASE
    )
    envelope = np.interp(
        np.arange(len(samples)),
        np.arange(len(gain)) * hop + hop / 2.0,
        gain,
        left=gain[0],
        right=gain[-1],
    )
    return samples * envelope, gated


_SILENCE_DB = -55.0
_SUSTAIN_DB = -45.0
_SUSTAIN = 0.080
_TAIL_SPEECH_DB = -40.0
_TAIL_SUSTAIN = 0.060
_DECAY_DB = -58.0


def _speech_bounds(samples: np.ndarray, rate: int) -> Tuple[int, int]:
    """Locate the real utterance, ignoring an onset click and trailing junk.

    The head anchor must be *sustained*, because a leading click is loud but
    brief and a plain level gate would mistake it for speech and trim nothing.
    The tail anchor is the last sustained speech followed down its natural
    decay; anything arriving after a gap is discarded whatever it is.
    """
    frames, hop = _frames(samples, rate, _FRAME)
    if frames.size == 0:
        return 0, len(samples)
    rms = _rms_db(frames)

    need = max(1, int(round(_SUSTAIN / _FRAME)))
    start = None
    run = 0
    for i, loud in enumerate(rms > _SUSTAIN_DB):
        run = run + 1 if loud else 0
        if run >= need:
            start = i - need + 1
            break
    audible = np.where(rms > _SILENCE_DB)[0]
    if start is None:
        start = int(audible[0]) if audible.size else 0
    while start > 0 and rms[start - 1] > _SILENCE_DB:
        start -= 1

    need_tail = max(1, int(round(_TAIL_SUSTAIN / _FRAME)))
    end = None
    run = 0
    for i, loud in enumerate(rms > _TAIL_SPEECH_DB):
        run = run + 1 if loud else 0
        if run >= need_tail:
            end = i
    if end is None:
        end = int(audible[-1]) if audible.size else len(rms) - 1
    while end + 1 < len(rms) and rms[end + 1] > _DECAY_DB:
        end += 1

    return start * hop, min(len(samples), (end + 1) * hop)


def _highpass(samples: np.ndarray, rate: int, cutoff: float = 55.0) -> np.ndarray:
    """Zero-phase high pass via FFT.

    Removes the sub-bass step that makes a sample-zero discontinuity audible as
    a thump. Done spectrally because the recursive one-pole form would need a
    Python loop over millions of samples.
    """
    if samples.size < 16:
        return samples
    spectrum = np.fft.rfft(samples)
    freqs = np.fft.rfftfreq(samples.size, 1.0 / rate)
    with np.errstate(divide="ignore", invalid="ignore"):
        ratio = np.where(freqs > 0, freqs / cutoff, 0.0)
    response = ratio**2 / (1.0 + ratio**2)  # 2nd-order-ish smooth rolloff
    response[0] = 0.0                        # kill DC outright
    return np.fft.irfft(spectrum * response, n=samples.size)


_HEAD_PAD = 0.030
_TAIL_PAD = 0.120
_FADE_IN = 0.012      # below the ear's integration window
_FADE_OUT = 0.030
_TARGET_PEAK_DB = -3.0
# What the engine must have actually returned for the result to count as speech.
# Duration alone is not enough: the head/tail padding means even a fully silent
# input comes back longer than any sensible minimum, so the level is checked on
# the decoded audio before normalisation can hide it.
_MIN_AUDIO_S = 0.05
_MIN_PEAK_DB = -50.0


def polish(samples: np.ndarray, rate: int) -> Tuple[np.ndarray, Dict[str, float]]:
    """Repair the measured output defects.

    De-gate first so the boundary search sees clean audio, then bound the real
    speech, then fade, then normalise.
    """
    original = len(samples) / rate if rate else 0.0
    samples, gated = _degate(samples, rate)

    start, end = _speech_bounds(samples, rate)
    lead = start / rate

    pad = int(rate * _HEAD_PAD)
    keep = max(0, start - pad)
    end = min(len(samples), end + int(rate * _TAIL_PAD))
    trailing = (len(samples) - end) / rate
    samples = samples[keep:end]
    missing = pad - (start - keep)
    if missing > 0:
        # Guarantee a lead-in so the fade lands on silence rather than eating
        # the first phoneme.
        samples = np.concatenate([np.zeros(missing), samples])

    samples = _highpass(samples, rate)

    fade_in = int(rate * _FADE_IN)
    fade_out = int(rate * _FADE_OUT)
    if len(samples) > fade_in + fade_out > 0:
        samples[:fade_in] *= np.linspace(0.0, 1.0, fade_in) ** 2
        samples[-fade_out:] *= np.linspace(1.0, 0.0, fade_out) ** 2

    peak = float(np.abs(samples).max()) if samples.size else 0.0
    if peak > 0:
        samples *= (10 ** (_TARGET_PEAK_DB / 20.0)) / peak

    return samples, {
        "rustles_gated": gated,
        "lead_trimmed": lead,
        "tail_trimmed": trailing,
        "duration_before": original,
        "duration_after": len(samples) / rate if rate else 0.0,
    }


# --------------------------------------------------------------------------
# Provider
# --------------------------------------------------------------------------


class IrodoriTTSProvider(TTSProvider):
    @property
    def name(self) -> str:
        return "irodori-tts"

    @property
    def display_name(self) -> str:
        return "Irodori-TTS (local, Japanese)"

    @property
    def voice_compatible(self) -> bool:
        return True

    @property
    def style_features(self) -> frozenset:
        """Style controls this engine honours, for an engine-agnostic caller.

        Advertised rather than hardcoded at the call site: the character-voice
        tools deliberately know no engine names beyond their fixed list, so they
        ask what a provider supports and refuse a control the engine would
        silently drop. A provider that declares nothing supports nothing, which
        is the correct reading of every other TTS plugin.
        """
        return frozenset({"caption", "emoji", "seed"})

    def _config(self) -> Dict[str, Any]:
        try:
            from hermes_cli.config import load_config

            tts = load_config().get("tts", {}) or {}
            block = tts.get("irodori_tts", {})
            return block if isinstance(block, dict) else {}
        except Exception as exc:  # noqa: BLE001 - config is best-effort
            logger.debug("irodori-tts: config load failed (%s); using defaults", exc)
            return {}

    def _base_url(self) -> str:
        return str(self._config().get("base_url") or _FALLBACK_BASE_URL).rstrip("/")

    def _timeout(self) -> int:
        try:
            timeout = int(self._config().get("synthesis_timeout"))
        except (TypeError, ValueError):
            return _SYNTHESIS_TIMEOUT
        return timeout if timeout > 0 else _SYNTHESIS_TIMEOUT

    def _default_voice(self) -> Optional[str]:
        value = self._config().get("voice")
        return str(value).strip() if isinstance(value, str) and value.strip() else None

    def _post_process(self) -> bool:
        return bool(self._config().get("post_process", True))

    def _use_lexicon(self) -> bool:
        return bool(self._config().get("lexicon", True))

    def _min_japanese_ratio(self) -> float:
        try:
            return float(self._config().get("min_japanese_ratio", _JA_MIN_RATIO))
        except (TypeError, ValueError):
            return _JA_MIN_RATIO

    def is_available(self) -> bool:
        try:
            req = urllib.request.Request(self._base_url() + "/health")
            with urllib.request.urlopen(req, timeout=_AVAILABILITY_TIMEOUT) as resp:
                if not 200 <= resp.status < 300:
                    return False
                payload = json.loads(resp.read().decode("utf-8"))
        except Exception:
            return False
        # The server answers /health before the model finishes loading, and a
        # synthesis request during that window blocks or 503s. Report unavailable
        # so the chain moves on instead of stalling the reply.
        runtime = payload.get("runtime", {}) if isinstance(payload, dict) else {}
        return bool(runtime.get("loaded", True))

    def list_voices(self) -> List[Dict[str, Any]]:
        try:
            req = urllib.request.Request(self._base_url() + "/v1/audio/voices")
            with urllib.request.urlopen(req, timeout=_VOICES_TIMEOUT) as resp:
                payload = json.loads(resp.read().decode("utf-8"))
        except Exception as exc:  # noqa: BLE001
            logger.debug("irodori-tts: list_voices failed: %s", exc)
            return []
        # OpenAI-shaped list response, unlike qwen3-tts's {"voices": [...]}.
        data = payload.get("data", []) if isinstance(payload, dict) else []
        return [voice for voice in data if isinstance(voice, dict)]

    def get_setup_schema(self) -> Dict[str, Any]:
        return {
            "name": self.display_name,
            "badge": "local",
            "tag": (
                "Irodori-TTS on a loopback server (no API key). Japanese only; "
                "English-dominant text is deferred to the next tier."
            ),
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
    def _muxer(ext: str) -> Optional[str]:
        """Container to force when the output path carries no extension.

        ffmpeg infers the muxer from the output filename, so an extensionless
        path plus a format hint would otherwise fail outright and push the
        utterance to the next tier for no reason.
        """
        ext = ext.lower().lstrip(".")
        return {
            "mp3": "mp3",
            "ogg": "ogg",
            "oga": "ogg",
            "opus": "opus",
            "m4a": "ipod",
            "aac": "adts",
            "wav": "wav",
        }.get(ext)

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
            raise ValueError("Irodori-TTS speed must be a positive finite number")
        return max(0.25, min(4.0, value))

    def _write_audio(
        self,
        wav_bytes: bytes,
        output_path: str,
        speed: Optional[float],
        fmt_hint: Optional[str],
    ) -> str:
        path_ext = os.path.splitext(output_path)[1].lower()
        ext = path_ext
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
            raise RuntimeError("ffmpeg is required to encode or retime Irodori-TTS audio")

        tmp_wav = None
        try:
            fd, tmp_wav = tempfile.mkstemp(suffix=".wav", prefix="irodori_tts_src_")
            with os.fdopen(fd, "wb") as output:
                output.write(wav_bytes)
            command = [ffmpeg, "-nostdin", "-y", "-loglevel", "error", "-i", tmp_wav]
            if atempo_filter := self._atempo_filter(speed_value):
                command += ["-filter:a", atempo_filter]
            command += self._codec_args(ext)
            if not path_ext:
                if muxer := self._muxer(ext):
                    command += ["-f", muxer]
            command.append(output_path)
            result = subprocess.run(
                command,
                capture_output=True,
                timeout=_FFMPEG_TIMEOUT,
                stdin=subprocess.DEVNULL,
            )
            if result.returncode != 0:
                detail = result.stderr.decode("utf-8", "replace")[:300]
                raise RuntimeError(f"ffmpeg failed to encode Irodori-TTS audio: {detail}")
            if not os.path.exists(output_path) or os.path.getsize(output_path) <= 0:
                raise RuntimeError("ffmpeg produced no Irodori-TTS audio")
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
        caption: Optional[str] = None,
        seed: Optional[int] = None,
        **extra: Any,
    ) -> str:
        if not isinstance(text, str) or not text.strip():
            raise ValueError("Irodori-TTS requires non-empty text")

        ratio = japanese_ratio(text)
        if len(_JA_CHARS.findall(text)) < _JA_MIN_CHARS or ratio < self._min_japanese_ratio():
            # Not an outage: this model is Japanese-only and renders English at
            # 27% WER. Raising hands the utterance to the next chain tier whole,
            # which keeps one voice per utterance.
            raise RuntimeError(
                f"Irodori-TTS is Japanese-only; text is {ratio:.0%} Japanese script "
                "- deferring to the next TTS tier"
            )

        spoken = apply_lexicon(text) if self._use_lexicon() else text

        request_payload: Dict[str, Any] = {"input": spoken, "model": _MODEL_ID}
        if isinstance(model, str) and model.strip():
            request_payload["model"] = model.strip()
        chosen_voice = voice if isinstance(voice, str) and voice.strip() else self._default_voice()
        if chosen_voice:
            request_payload["voice"] = chosen_voice.strip()

        # Style controls travel in the server's own options object. Omitted
        # entirely when unused, so the ordinary chain sends exactly what it sent
        # before and the server keeps its configured defaults.
        options: Dict[str, Any] = {}
        if caption is not None:
            if not isinstance(caption, str) or not caption.strip():
                raise ValueError("Irodori-TTS caption must be a non-empty string")
            options["caption"] = caption.strip()
        if seed is not None:
            try:
                options["seed"] = int(seed)
            except (TypeError, ValueError) as exc:
                raise ValueError(f"Irodori-TTS seed must be an integer, got {seed!r}") from exc
        if options:
            request_payload["irodori"] = options

        req = urllib.request.Request(
            self._base_url() + "/v1/audio/speech",
            data=json.dumps(request_payload).encode("utf-8"),
            method="POST",
            headers={"Content-Type": "application/json", "Accept": "audio/wav"},
        )
        try:
            with urllib.request.urlopen(req, timeout=self._timeout()) as resp:
                audio = resp.read()
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", "replace")[:300]
            raise RuntimeError(
                f"Irodori-TTS synthesis failed: HTTP {exc.code} {exc.reason}. {detail}"
            ) from exc
        except urllib.error.URLError as exc:
            raise RuntimeError(
                f"Irodori-TTS server not reachable at {self._base_url()}: {exc.reason}"
            ) from exc
        if not audio:
            raise RuntimeError("Irodori-TTS server returned empty audio")

        if self._post_process():
            cleaned: Optional[bytes] = None
            try:
                samples, rate = _decode_wav(audio)
                # tts-fallback judges a tier by output file size, and a bare WAV
                # header clears that bar -- silence would be delivered as
                # success instead of falling through. Raised below so it can
                # propagate past the polish guard.
                raw_peak_db = (
                    20.0 * math.log10(float(np.abs(samples).max()) + 1e-12)
                    if samples.size
                    else -120.0
                )
                samples, stats = polish(samples, rate)
                duration = samples.size / rate if rate else 0.0
                usable = duration >= _MIN_AUDIO_S and raw_peak_db >= _MIN_PEAK_DB
                cleaned = _encode_wav(samples, rate) if usable else None
                logger.info(
                    "irodori-tts: polished %.2fs -> %.2fs (lead %.3fs, tail %.3fs, "
                    "%d rustle span(s) gated)",
                    stats["duration_before"],
                    stats["duration_after"],
                    stats["lead_trimmed"],
                    stats["tail_trimmed"],
                    stats["rustles_gated"],
                )
                if cleaned is None:
                    raise RuntimeError(
                        f"Irodori-TTS produced no usable audio "
                        f"({duration:.3f}s, peak {raw_peak_db:.1f} dBFS)"
                    )
            except RuntimeError:
                raise
            except Exception as exc:  # noqa: BLE001 - a polish bug must not lose audio
                logger.warning("irodori-tts: post-processing skipped (%s)", exc)
                cleaned = None
            if cleaned is not None:
                audio = cleaned

        return self._write_audio(audio, output_path, speed, format)


def register(ctx) -> None:
    ctx.register_tts_provider(IrodoriTTSProvider())
