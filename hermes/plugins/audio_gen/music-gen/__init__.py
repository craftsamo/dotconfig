"""Music-only approved generation. Resume retrieves evidence, never generates.

Approval hashes bind files, not approver identity. Durable state is trusted
local bookkeeping, not a sandbox against an operator rewriting all evidence.
Busy preflight refusals consume no grant. Every invoked render counts,
including a runtime-lock race after preflight; counted failures are never erased.
"""

from __future__ import annotations

import fcntl
import hashlib
import importlib.util
import json
import math
import os
import re
import stat
import tempfile
import wave
from pathlib import Path
from urllib.parse import urlparse

LOCAL_ENGINE = "local:stable-audio-3-medium"
ENGINE = "fal:stable-audio-3-medium"
MODEL = "fal-ai/stable-audio-3/medium/text-to-audio"
PRICE_PER_AUDIO = 0.0376  # Published estimate, not an invoice; 2026-09-08.
MAX_BYTES = 32 * 1024 * 1024
HERMES = Path(__file__).resolve().parents[3]
PLAN_SCRIPT = HERMES / "profiles/audio-creator/skills/audio-creator-pipeline/scripts/music_plan.py"
BUSY_MESSAGE = "local runtime busy; retry later; no new attempt was recorded"


class AttemptFailed(ValueError):
    """Only fixed classifications/messages may leave an inference boundary."""

    def __init__(self, reason):
        messages = {
            "busy": "runtime became busy after preflight",
            "not-ready": "runtime became unavailable after preflight",
            "timeout": "local generation exceeded its timeout",
            "subprocess": "local generation subprocess exited unsuccessfully",
            "invalid-output": "generated output did not match the approved request or evidence requirements",
            "runtime-error": "local generation failed unexpectedly",
            "interrupted": "interrupted attempt has no checkpointed successful evidence",
            "provider-rejected": "provider rejected the completed request",
        }
        self.failure_reason = reason if reason in messages else "runtime-error"
        super().__init__(f"attempt failed ({self.failure_reason}): {messages[self.failure_reason]}; "
                         "attempt counted. Resume never regenerates; next may use the remaining grant")

CATALOG_SCHEMA = {
    "name": "music_engines",
    "description": "List music engines without generation or payment. Local Medium is the default; no automatic fallback.",
    "parameters": {"type": "object", "properties": {}, "additionalProperties": False},
}
GENERATE_SCHEMA = {
    "name": "music_generate",
    "description": "Generate only from a hash-approved music proposal. start freezes settings and budget; next uses another counted attempt and may reapprove creative fields only; resume never generates. Raw music is not perceptually verified. Approval acknowledgment is not authorization proof.",
    "parameters": {
        "type": "object",
        "properties": {
            "action": {"type": "string", "enum": ["start", "next", "resume"]},
            "job_dir": {"type": "string", "description": "Absolute durable directory; start requires a new path with an existing parent."},
            "approved_plan": {"type": "string", "description": "Approved Markdown proposal path. Required with approval_sha256 on start; optional paired correction on next."},
            "approval_sha256": {"type": "string", "pattern": "^[0-9a-f]{64}$"},
            "paid_approved": {"type": "boolean", "description": "start only, true after explicit current-work paid approval for fal. Omit entirely for local."},
        },
        "required": ["action", "job_dir"], "additionalProperties": False,
    },
}


def _load(script, name):
    spec = importlib.util.spec_from_file_location(name, script)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _runtime():
    return _load(HERMES / "scripts/stable_audio3.py", "hermes_music_runtime")


def _key():
    from agent.secret_scope import get_secret
    return (get_secret("FAL_KEY", "") or "").strip()


def _request_id(value):
    if not isinstance(value, str) or not re.fullmatch(r"[A-Za-z0-9_-]{1,100}", value):
        raise ValueError("no usable request ID; submission remains unknown")
    return value


def _client():
    from fal_client import SyncClient
    key = _key()
    if not key:
        raise ValueError("FAL_KEY unavailable in this profile's secret scope")

    class SingleSubmitClient(SyncClient):
        def submit(self, application, arguments):
            import requests
            if application != MODEL:
                raise ValueError("unsupported music model")
            # Do not use the SDK's automatic paid POST retries.
            response = requests.post(
                "https://queue.fal.run/" + MODEL, json=arguments,
                headers={"Authorization": "Key " + key}, timeout=(10, 60),
                allow_redirects=False,
            )
            if response.status_code not in (200, 201, 202):
                raise RuntimeError("submission failed; outcome remains unknown")
            return self.get_handle(MODEL, _request_id(response.json().get("request_id")))

    return SingleSubmitClient(key=key, default_timeout=60)


def catalog(args, **kwargs):
    if not isinstance(args, dict) or args:
        return json.dumps({"success": False, "error": "music_engines accepts an empty object"})
    try:
        local = _runtime().status()
    except Exception:
        local = {"available": False, "reason": "local runtime readiness check failed"}
    try:
        paid = bool(_key())
    except Exception:
        paid = False
    common = {"duration_seconds": [1, 60], "seed": True, "max_text_chars": 450,
              "output_format": "wav", "prompt_expansion": False,
              "instrumental_guaranteed": False, "perceptual_qa": "unverified"}
    return json.dumps({"default_engine": LOCAL_ENGINE, "engines": [
        {**common, "id": LOCAL_ENGINE, "cost": "free", **local,
         "license": "Community License and Gemma terms; commercial registration is separate"},
        {**common, "id": ENGINE, "cost": "metered", "available": paid,
         "model": MODEL, "estimated_usd_per_audio": PRICE_PER_AUDIO,
         "availability_check": "profile credential presence only, not provider health",
         "license_url": "https://fal.ai/models/" + MODEL},
    ]})


def _number(value, name, low, high):
    if (isinstance(value, bool) or not isinstance(value, (int, float))
            or not math.isfinite(value) or not low <= value <= high):
        raise ValueError(f"{name} must be finite and between {low} and {high}")
    return value


def _hash(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, allow_nan=False,
                                     ensure_ascii=False).encode()).hexdigest()


def _settings(value):
    if not isinstance(value, dict) or set(value) - {
        "engine", "duration_seconds", "seed", "max_calls", "max_usd"
    }:
        raise ValueError("unsupported approved settings; no controls are silently dropped")
    settings = dict(value)
    settings.setdefault("engine", LOCAL_ENGINE)
    settings.setdefault("seed", 0)
    settings.setdefault("max_calls", 3)
    if settings["engine"] not in (LOCAL_ENGINE, ENGINE):
        raise ValueError("unsupported engine; no backend substitution")
    _number(settings.get("duration_seconds"), "duration_seconds", 1, 60)
    if type(settings["seed"]) is not int or not 0 <= settings["seed"] < 2**32:
        raise ValueError("seed must be an integer in [0, 2^32-1]")
    if type(settings["max_calls"]) is not int or not 1 <= settings["max_calls"] <= 8:
        raise ValueError("max_calls must be an integer from 1 to 8")
    if settings["engine"] == LOCAL_ENGINE:
        if settings.get("max_usd") is not None:
            raise ValueError("local generation does not accept max_usd")
    else:
        if "max_calls" not in value:
            raise ValueError("fal requires an explicitly approved max_calls")
        cap = _number(settings.get("max_usd"), "max_usd", PRICE_PER_AUDIO, 10)
        if settings["max_calls"] * PRICE_PER_AUDIO > cap + 1e-9:
            raise ValueError("max_usd does not cover max_calls at the published estimate")
    settings.setdefault("max_usd", None)
    return settings


def _manifest(value):
    if (not isinstance(value, dict) or value.get("version") != 1
            or value.get("kind") != "generate" or not isinstance(value.get("form"), dict)):
        raise ValueError("approved manifest must be version 1, kind generate")
    text = value.get("artifact_text")
    if not isinstance(text, str) or not text.strip() or len(text) > 450:
        raise ValueError("approved prompt must contain 1-450 characters")
    if hashlib.sha256(text.encode()).hexdigest() != value.get("artifact_sha256"):
        raise ValueError("approved artifact hash mismatch")
    if (not isinstance(value.get("approved_plan"), str)
            or not isinstance(value.get("approval_sha256"), str)
            or not re.fullmatch(r"[0-9a-f]{64}", value["approval_sha256"])):
        raise ValueError("approved proposal identity is missing")
    _settings(value.get("settings"))
    return value


def _approved(path, sha256):
    if not isinstance(path, str) or not isinstance(sha256, str) or not re.fullmatch(r"[0-9a-f]{64}", sha256):
        raise ValueError("approved_plan and approval_sha256 are required together")
    manifest = _manifest(_load(PLAN_SCRIPT, "hermes_music_plan").load_approved(path, sha256, "generate"))
    if manifest["approval_sha256"] != sha256 or Path(manifest["approved_plan"]).resolve() != Path(path).expanduser().resolve():
        raise ValueError("approval helper returned a different proposal")
    return manifest


def _path(value):
    if not isinstance(value, str) or ".." in Path(value).parts:
        raise ValueError("job_dir must be an absolute path without traversal")
    path = Path(value).expanduser()
    if not path.is_absolute():
        raise ValueError("job_dir must be absolute")
    from agent.file_safety import is_write_denied
    if is_write_denied(str(path)) or is_write_denied(str(path.resolve())):
        raise ValueError("job_dir is a protected path")
    if any(p.is_symlink() for p in (path, *path.parents)):
        raise ValueError("job_dir and ancestors must not be symlinks")
    return path


def _read(path, limit=1024 * 1024):
    with os.fdopen(os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK), "rb") as stream:
        info = os.fstat(stream.fileno())
        if not stat.S_ISREG(info.st_mode) or info.st_size > limit:
            raise ValueError("evidence must be a bounded regular file")
        data = stream.read(limit + 1)
    if len(data) > limit:
        raise ValueError("evidence exceeds its byte bound")
    return data


def _save(path, state):
    fd, name = tempfile.mkstemp(prefix=".state-", dir=path)
    try:
        with os.fdopen(fd, "w") as stream:
            json.dump(state, stream, indent=2, allow_nan=False)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(name, path / "state.json")
        directory = os.open(path, os.O_RDONLY)
        try:
            os.fsync(directory)
        finally:
            os.close(directory)
    finally:
        Path(name).unlink(missing_ok=True)


def _payload(manifest, index):
    settings = _settings(manifest["settings"])
    seed = (settings["seed"] + index) % 2**32
    if settings["engine"] == LOCAL_ENGINE:
        return {"text": manifest["artifact_text"], "duration_seconds": settings["duration_seconds"], "seed": seed}
    return {"prompt": manifest["artifact_text"], "duration": settings["duration_seconds"], "seed": seed,
            "output_format": "wav", "enable_prompt_expansion": False, "enable_safety_checker": True,
            "sync_mode": False, "num_inference_steps": 8, "guidance_scale": 1, "negative_prompt": ""}


def _state(path):
    state = json.loads(_read(path / "state.json"))
    frozen = state["frozen"]
    if state.get("version") != 1 or _hash(frozen) != state.get("frozen_sha256"):
        raise ValueError("frozen job settings changed")
    settings = _settings(frozen["settings"])
    if settings != frozen["settings"] or (settings["engine"] == ENGINE and frozen.get("paid_approved") is not True):
        raise ValueError("invalid frozen settings or paid approval")
    current = _manifest(state["approved"])
    if _settings(current["settings"]) != settings or _hash(current) != state["approved_sha256"]:
        raise ValueError("approved manifest changed")
    attempts = state["attempts"]
    if not isinstance(attempts, list) or len(attempts) > settings["max_calls"]:
        raise ValueError("invalid attempt ledger")
    for index, attempt in enumerate(attempts):
        manifest = _manifest(attempt["approved"])
        if (attempt["number"] != index + 1 or _settings(manifest["settings"]) != settings
                or _hash(manifest) != attempt["approved_sha256"]
                or attempt["payload"] != _payload(manifest, index)
                or _hash(attempt["payload"]) != attempt["payload_sha256"]):
            raise ValueError("attempt differs from frozen approved inputs")
        if "request_id" in attempt:
            _request_id(attempt["request_id"])
    return state


def _download(url, output):
    import requests
    parsed = urlparse(url)
    if (parsed.scheme != "https" or not parsed.hostname or not parsed.hostname.endswith(".fal.media")
            or parsed.port not in (None, 443) or parsed.username or parsed.password):
        raise ValueError("result must be an HTTPS fal.media URL")
    with requests.get(url, stream=True, timeout=(10, 60), allow_redirects=False) as response:
        if response.status_code != 200:
            raise RuntimeError("result download failed")
        with output.open("xb") as stream:
            size = 0
            for chunk in response.iter_content(65536):
                size += len(chunk)
                if size > MAX_BYTES:
                    raise ValueError("result exceeds the 32 MiB cap")
                stream.write(chunk)
            if not size:
                raise ValueError("empty audio result")


def _evidence(bundle, attempt, frozen):
    if bundle.is_symlink() or not bundle.is_dir():
        raise ValueError("result bundle must be a regular directory")
    receipt_raw = _read(bundle / "take.json")
    receipt = json.loads(receipt_raw)
    raw = _read(bundle / "raw.wav", MAX_BYTES)
    raw_hash = hashlib.sha256(raw).hexdigest()
    settings = frozen["settings"]
    if (receipt.get("engine") != settings["engine"] or receipt.get("request") != attempt["payload"]
            or receipt.get("raw_wav", {}).get("sha256_file") != raw_hash):
        raise ValueError("receipt does not match the frozen payload or raw hash")
    import io
    with wave.open(io.BytesIO(raw), "rb") as wav:
        frames, rate = wav.getnframes(), wav.getframerate()
        channels, width = wav.getnchannels(), wav.getsampwidth()
        if (channels not in (1, 2) or width not in (2, 3, 4) or not 8000 <= rate <= 192000
                or frames <= 0 or frames * channels * width > MAX_BYTES):
            raise ValueError("result WAV exceeds music format/duration bounds")
        local = settings["engine"] == LOCAL_ENGINE
        tolerance = 1 if local else 0.25 * rate
        requested = round(settings["duration_seconds"] * rate) if local else settings["duration_seconds"] * rate
        if frames > 60 * rate + tolerance or abs(frames - requested) > tolerance:
            raise ValueError("result WAV duration does not match the approved request")
        pcm = wav.readframes(frames)
        if len(pcm) != frames * channels * width:
            raise ValueError("truncated result WAV")
    hashes = {"raw.wav": raw_hash, "take.json": hashlib.sha256(receipt_raw).hexdigest()}
    if settings["engine"] == LOCAL_ENGINE:
        metadata = receipt["raw_wav"]
        if (receipt.get("model", {}).get("runtime_fingerprint") != frozen["runtime"]
                or (channels, width, rate) != (2, 2, 44100)
                or metadata.get("sha256_pcm") != hashlib.sha256(pcm).hexdigest()
                or metadata.get("frames") != frames or metadata.get("sample_rate") != rate
                or metadata.get("channels") != channels or metadata.get("sample_width_bytes") != width):
            raise ValueError("local receipt does not match frozen runtime or PCM")
        hashes["inference.log"] = hashlib.sha256(_read(bundle / "inference.log", MAX_BYTES)).hexdigest()
    else:
        if receipt.get("model") != MODEL or receipt.get("request_id") != attempt["request_id"]:
            raise ValueError("fal receipt request identity mismatch")
        response_raw = _read(bundle / "response.json")
        response = json.loads(response_raw)
        # The verified OpenAPI marks both prompt and seed as required outputs.
        if (not isinstance(response, dict) or response.get("prompt") != attempt["payload"]["prompt"]
                or type(response.get("seed")) is not int or response["seed"] != attempt["payload"]["seed"]):
            raise ValueError("fal response does not match the frozen prompt/seed")
        hashes["response.json"] = hashlib.sha256(response_raw).hexdigest()
    return hashes


def _recover(path, state, runtime=None, client=None):
    attempts, frozen = state["attempts"], state["frozen"]
    attempt = attempts[-1]
    bundle = path / f"take-{attempt['number']:02d}"
    base = {"success": True, "job_dir": str(path), "calls": len(attempts),
            "max_calls": frozen["settings"]["max_calls"], "engine": frozen["settings"]["engine"],
            "seed": attempt["payload"]["seed"], "seed_supported": True,
            "estimated_usd": len(attempts) * PRICE_PER_AUDIO if frozen["settings"]["engine"] == ENGINE else 0}
    if attempt["status"] == "submission-unknown":
        raise ValueError("submission outcome unknown; stop and inspect provider history, never resubmit")
    if attempt["status"] == "failed":
        raise AttemptFailed(attempt.get("failure_reason"))
    if attempt["status"] == "running":
        if (runtime or _runtime()).is_busy():
            return {**base, "status": "pending"}
        # An uncheckpointed receipt cannot prove that generation returned
        # successfully. Preserve it for manual recovery; never adopt a forgery.
        attempt.update(status="failed", failure_reason="interrupted")
        _save(path, state)
        raise AttemptFailed("interrupted")
    if attempt["status"] == "pending":
        from fal_client import Completed
        from fal_client.client import FalClientHTTPError
        client = client or _client()
        try:
            handle = client.get_handle(MODEL, attempt["request_id"])
            completed = isinstance(handle.status(with_logs=False), Completed)
        except Exception:
            raise RuntimeError("provider status failed; existing request remains resumable") from None
        if not completed:
            return {**base, "status": "pending"}
        try:
            result = handle.get()
        except FalClientHTTPError as exc:
            if exc.status_code in (400, 422):
                attempt.update(status="failed", response_status=exc.status_code, failure_reason="provider-rejected")
                _save(path, state)
                raise AttemptFailed("provider-rejected") from None
            raise RuntimeError("provider retrieval failed; attempt remains counted") from None
        except Exception:
            raise RuntimeError("provider retrieval failed; existing request remains resumable") from None
        if bundle.exists() or bundle.is_symlink():
            raise ValueError("uncheckpointed result bundle exists; preserve for manual recovery, never overwrite")
        with tempfile.TemporaryDirectory(prefix=".music-download-", dir=path) as work:
            work = Path(work)
            receipt = {"engine": ENGINE, "model": MODEL, "request_id": attempt["request_id"],
                       "request": attempt["payload"], "payload_sha256": attempt["payload_sha256"],
                       "approval_sha256": attempt["approved"]["approval_sha256"],
                       "raw_wav": {}, "validation": "unverified"}
            try:
                (work / "response.json").write_text(json.dumps(result, allow_nan=False))
                (work / "take.json").write_text(json.dumps(receipt, allow_nan=False))
                if (not isinstance(result, dict) or result.get("prompt") != attempt["payload"]["prompt"]
                        or type(result.get("seed")) is not int or result["seed"] != attempt["payload"]["seed"]):
                    raise ValueError("provider result differs from frozen prompt/seed")
                audio = result.get("audio")
                if not isinstance(audio, dict) or not isinstance(audio.get("url"), str):
                    raise ValueError("provider returned no audio URL")
                _download(audio["url"], work / "raw.wav")
                receipt["raw_wav"]["sha256_file"] = hashlib.sha256(_read(work / "raw.wav", MAX_BYTES)).hexdigest()
                (work / "take.json").write_text(json.dumps(receipt, allow_nan=False))
                hashes = _evidence(work, attempt, frozen)
            except (ValueError, wave.Error, EOFError):
                # Preserve rejected evidence separately. No successful checkpoint
                # is written, and resume cannot adopt this diagnostic candidate.
                candidate = Path(tempfile.mkdtemp(prefix=f"take-{attempt['number']:02d}-candidate-", dir=path))
                for name in ("raw.wav", "response.json", "take.json"):
                    if (work / name).is_file():
                        os.link(work / name, candidate / name)
                attempt.update(status="failed", failure_reason="invalid-output", diagnostic_candidate=str(candidate))
                _save(path, state)
                raise AttemptFailed("invalid-output") from None
            bundle.mkdir()
            for name in hashes:
                os.link(work / name, bundle / name)
            attempt.update(status="downloaded", evidence=hashes)
            _save(path, state)
    if attempt["status"] != "downloaded" or not attempt.get("evidence"):
        raise ValueError("no checkpointed successful result")
    if _evidence(bundle, attempt, frozen) != attempt["evidence"]:
        raise ValueError("result evidence changed since generation")
    return {**base, "status": "raw-needs-qa", "raw": str(bundle / "raw.wav"),
            "take_json": str(bundle / "take.json"), "runtime": frozen.get("runtime"),
            "approval_sha256": attempt["approved"]["approval_sha256"], "perceptual_qa": "unverified"}


def generate(args, **kwargs):
    path = None
    try:
        if not isinstance(args, dict) or set(args) - set(GENERATE_SCHEMA["parameters"]["properties"]):
            raise ValueError("unsupported tool controls; use the approved proposal")
        action = args.get("action")
        if action not in ("start", "next", "resume"):
            raise ValueError("action must be start, next or resume")
        allowed = {"action", "job_dir"}
        if action != "resume":
            allowed |= {"approved_plan", "approval_sha256"}
        if action == "start":
            allowed.add("paid_approved")
        if set(args) - allowed:
            raise ValueError("resume/next cannot change frozen controls or budget")
        if ("approved_plan" in args) != ("approval_sha256" in args):
            raise ValueError("approved_plan and approval_sha256 are required together")
        path = _path(args.get("job_dir"))
        runtime = client = None
        if action == "start":
            if path.exists():
                raise ValueError("start requires a new job directory; existing jobs are never overwritten")
            manifest = _approved(args.get("approved_plan"), args.get("approval_sha256"))
            settings = _settings(manifest["settings"])
            frozen = {"settings": settings}
            if settings["engine"] == LOCAL_ENGINE:
                if "paid_approved" in args:
                    raise ValueError("local generation rejects paid_approved, even false")
                runtime = _runtime()
                if runtime.is_busy():
                    raise ValueError(BUSY_MESSAGE)
                ready = runtime.status()
                if not ready["available"]:
                    raise ValueError("local runtime unavailable; no paid fallback")
                frozen["runtime"] = ready["fingerprint"]["runtime_identity"]
            else:
                if args.get("paid_approved") is not True:
                    raise ValueError("explicit current-work paid approval is required")
                frozen["paid_approved"] = True
                client = _client()
            path.mkdir()
            _save(path, {"version": 1, "frozen": frozen, "frozen_sha256": _hash(frozen),
                         "approved": manifest, "approved_sha256": _hash(manifest), "attempts": []})
        if not path.is_dir():
            raise ValueError("job does not exist")
        with os.fdopen(os.open(path / ".lock", os.O_WRONLY | os.O_CREAT | os.O_NOFOLLOW | os.O_NONBLOCK, 0o600), "w") as lock:
            if not stat.S_ISREG(os.fstat(lock.fileno()).st_mode):
                raise ValueError("job lock must be a regular file")
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            state = _state(path)
            attempts, frozen = state["attempts"], state["frozen"]
            if action != "resume":
                if attempts and attempts[-1]["status"] not in ("downloaded", "failed"):
                    raise ValueError("latest attempt unresolved; resume, never submit again")
                if len(attempts) >= frozen["settings"]["max_calls"]:
                    raise ValueError("attempt budget exhausted")
                old = state["approved"]
                manifest = _approved(args.get("approved_plan", old["approved_plan"]),
                                     args.get("approval_sha256", old["approval_sha256"]))
                if _settings(manifest["settings"]) != frozen["settings"]:
                    raise ValueError("reapproval cannot change frozen engine, duration, seed or budget")
                if "approved_plan" not in args and manifest != old:
                    raise ValueError("approved files changed before a new attempt")
                local = frozen["settings"]["engine"] == LOCAL_ENGINE
                if local:
                    runtime = runtime or _runtime()
                    if runtime.is_busy():
                        raise ValueError(BUSY_MESSAGE)
                    ready = runtime.status()
                    if not ready["available"] or ready["fingerprint"]["runtime_identity"] != frozen["runtime"]:
                        raise ValueError("local runtime changed/unavailable; no substitution")
                else:
                    client = client or _client()
                number = len(attempts) + 1
                bundle = path / f"take-{number:02d}"
                if bundle.exists() or bundle.is_symlink():
                    raise ValueError("attempt output already exists; never overwrite")
                payload = _payload(manifest, len(attempts))
                attempt = {"number": number, "status": "running" if local else "submission-unknown",
                           "payload": payload, "payload_sha256": _hash(payload),
                           "approved": manifest, "approved_sha256": _hash(manifest)}
                attempts.append(attempt)
                state.update(approved=manifest, approved_sha256=_hash(manifest))
                _save(path, state)  # Count every attempt before generation or paid submission.
                if local:
                    failure_reason = "runtime-error"
                    try:
                        result = runtime.render_music(payload, bundle)
                        failure_reason = "invalid-output"
                        if result.get("status") != "raw-needs-qa" or result.get("receipt") != json.loads(_read(bundle / "take.json")):
                            raise ValueError("runtime returned no matching successful receipt")
                        attempt.update(evidence=_evidence(bundle, attempt, frozen), status="downloaded")
                    except Exception as exc:
                        if isinstance(exc, getattr(runtime, "RenderError", ())):
                            # Inspect fixed runtime prefixes, never persist/relay
                            # arbitrary exception text (which may include stderr).
                            for reason, prefixes in (
                                ("busy", ("busy:",)),
                                ("not-ready", ("runtime not ready:",)),
                                ("timeout", ("generation exceeded ",)),
                                ("subprocess", ("generation subprocess exited ",)),
                                ("invalid-output", ("generation completed but raw.wav was not written",
                                                    "raw.wav exceeds ", "unexpected WAV format:",
                                                    "WAV truncated:", "unexpected frame count ")),
                            ):
                                if str(exc).startswith(prefixes):
                                    failure_reason = reason
                                    break
                        elif isinstance(exc, (wave.Error, EOFError)):
                            failure_reason = "invalid-output"
                        attempt.update(status="failed", failure_reason=failure_reason)
                        _save(path, state)
                        raise AttemptFailed(failure_reason) from None
                    _save(path, state)
                else:
                    try:
                        handle = client.submit(MODEL, arguments=payload)
                        request_id = _request_id(handle.request_id)
                    except Exception:
                        raise RuntimeError("submission outcome unknown; never resubmit") from None
                    attempt.update(request_id=request_id, status="pending")
                    _save(path, state)
            if not attempts:
                raise ValueError("job has no attempted generation; resume never generates")
            return json.dumps(_recover(path, state, runtime, client))
    except Exception as exc:
        # Provider exceptions may include keys or signed URLs. Never relay them.
        safe = isinstance(exc, (ValueError, FileExistsError, FileNotFoundError, BlockingIOError))
        message = str(exc) if safe else "request failed; inspect durable state and resume, never resubmit blindly"
        failure = {"failure_reason": exc.failure_reason} if isinstance(exc, AttemptFailed) else {}
        return json.dumps({"success": False, "error": message, "job_dir": str(path) if path else None, **failure})


def register(ctx):
    if ctx.profile_name != "audio-creator":
        return
    for schema, handler in ((CATALOG_SCHEMA, catalog), (GENERATE_SCHEMA, generate)):
        ctx.register_tool(name=schema["name"], toolset="music_gen", schema=schema,
                          handler=handler, description=schema["description"])
