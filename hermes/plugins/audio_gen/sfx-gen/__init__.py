"""SFX-only tools. No implicit paid fallback or process-environment credentials."""

from __future__ import annotations

import fcntl
import hashlib
import importlib.util
import json
import math
import os
from pathlib import Path
from urllib.parse import urlparse

ENGINE = "fal:elevenlabs-sfx-v2"
LOCAL_ENGINE = "local:stable-audio-3-medium"
MODEL = "fal-ai/elevenlabs/sound-effects/v2"
PRICE_PER_SECOND = 0.002  # Estimate, not an invoice; checked 2026-09-08.
MAX_BYTES = 16 * 1024 * 1024

CATALOG_SCHEMA = {
    "name": "sfx_engines",
    "description": "List SFX generation capabilities without generating or spending. Prefer local Medium MLX; never automatically fall back to fal.",
    "parameters": {"type": "object", "properties": {}, "additionalProperties": False},
}
GENERATE_SCHEMA = {
    "name": "sfx_generate",
    "description": "Generate SFX with local Medium MLX by default, or explicitly chosen fal with paid approval. start freezes a job budget; next spends another attempt; resume only recovers existing work. Local seed increments per variant; loop/prompt_influence are fal-only, seed is local-only. Raw audio needs sfx-media.py track QA. Approval acknowledgment is not authorization proof.",
    "parameters": {
        "type": "object",
        "properties": {
            "action": {"type": "string", "enum": ["start", "next", "resume"]},
            "job_dir": {"type": "string", "description": "Absolute durable job directory; start requires it not to exist and its parent to exist."},
            "engine": {"type": "string", "description": "Engine ID from sfx_engines; default local:stable-audio-3-medium, never a paid fallback."},
            "text": {"type": "string", "description": "1-450 characters describing one sound. next may supply a corrective prompt."},
            "duration_seconds": {"type": "number", "minimum": 0.5, "maximum": 21.5},
            "loop": {"type": "boolean"},
            "prompt_influence": {"type": "number", "minimum": 0, "maximum": 1},
            "seed": {"type": "integer", "minimum": 0, "maximum": 4294967295, "description": "Local only: base seed (default 0); attempt N uses (base + N - 1) modulo 2^32. Replay a take in a new granted job with its returned seed."},
            "paid_approved": {"type": "boolean", "description": "True only after explicit current-work client approval relayed by Creator."},
            "max_calls": {"type": "integer", "minimum": 1, "maximum": 8},
            "max_usd": {"type": "number", "description": "Approved USD estimate ceiling; actual provider billing may differ."},
        },
        "required": ["action", "job_dir"], "additionalProperties": False,
    },
}


def _key():
    from agent.secret_scope import get_secret
    return (get_secret("FAL_KEY", "") or "").strip()


def _runtime():
    script = Path(__file__).resolve().parents[3] / "scripts" / "stable_audio3.py"
    spec = importlib.util.spec_from_file_location("hermes_stable_audio3", script)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _client():
    from fal_client import SyncClient
    key = _key()
    if not key:
        raise ValueError("FAL_KEY is unavailable in this profile's secret scope")

    class SingleSubmitClient(SyncClient):
        def submit(self, application, arguments):
            import requests
            if application != MODEL:
                raise ValueError("unsupported SFX model")
            # SDK 0.13.1 retries submission on transport/5xx failures. Only
            # retrieval may retry: an ambiguous paid POST must happen once.
            response = requests.post(
                "https://queue.fal.run/" + MODEL,
                json=arguments, headers={"Authorization": "Key " + key},
                timeout=(10, 60), allow_redirects=False,
            )
            if response.status_code not in (200, 201, 202):
                raise RuntimeError(f"SFX submit returned HTTP {response.status_code}")
            request_id = response.json().get("request_id")
            if not isinstance(request_id, str) or not request_id or len(request_id) > 100 or not all(c.isalnum() or c in "-_" for c in request_id):
                raise ValueError("provider returned no usable request ID; submission remains unknown")
            return self.get_handle(MODEL, request_id)

    return SingleSubmitClient(key=key, default_timeout=60)


def catalog(args=None, **kwargs):
    try:
        local = _runtime().status()
    except Exception:
        local = {"available": False, "reason": "local runtime readiness check failed"}
    try:
        available = bool(_key())
    except Exception:
        available = False
    return json.dumps({"engines": [
        {"id": LOCAL_ENGINE, "available": local["available"], "reason": local["reason"],
         "cost": "free", "duration_seconds": [0.5, 21.5], "seed": True, "loop": False,
         "prompt_influence": False, "max_text_chars": 450, "steps": 8,
         "runtime": local.get("fingerprint"), "license": "Community License and Gemma terms; commercial registration is separate from local installation"},
        {"id": ENGINE, "available": available, "cost": "metered", "duration_seconds": [0.5, 21.5],
         "availability_check": "profile credential presence only; no paid call or provider-health probe",
         "duration_note": "API permits 22s; reserve 0.5s for MP3 padding/provider duration drift before the 22s packaging cap",
         "loop": True, "seed": False, "max_text_chars": 450, "estimated_usd_per_second": PRICE_PER_SECOND,
         "model": MODEL, "license_url": "https://fal.ai/models/fal-ai/elevenlabs/sound-effects/v2"},
    ]})


def _number(value, name, low, high):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or not low <= value <= high:
        raise ValueError(f"{name} must be finite and between {low} and {high}")
    return value


def _text(value):
    if not isinstance(value, str) or not value.strip() or len(value) > 450:
        raise ValueError("text must contain 1-450 characters")
    return value


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


def _save(path, state):
    temp = path / ".state.tmp"
    with temp.open("x", encoding="utf-8") as stream:
        json.dump(state, stream, ensure_ascii=False, indent=2, allow_nan=False)
        stream.flush()
        os.fsync(stream.fileno())
    temp.replace(path / "state.json")


def _download(url, output):
    """Only fal's result CDN; no redirects, credentials or arbitrary URL fetches."""
    import requests
    parsed = urlparse(url)
    if parsed.scheme != "https" or not parsed.hostname or not parsed.hostname.endswith(".fal.media") or parsed.port not in (None, 443) or parsed.username or parsed.password:
        raise ValueError("result is not an allowed HTTPS fal.media URL")
    with requests.get(url, stream=True, timeout=(10, 60), allow_redirects=False) as response:
        if response.status_code != 200:
            raise ValueError(f"result download returned HTTP {response.status_code}")
        with output.open("xb") as stream:
            size = 0
            for chunk in response.iter_content(65536):
                size += len(chunk)
                if size > MAX_BYTES:
                    raise ValueError("result exceeds the 16 MiB download cap")
                stream.write(chunk)
            if not size:
                raise ValueError("empty audio result")


def _local_generate(args, path):
    action = args["action"]
    runtime = _runtime()
    if action == "start":
        if "prompt_influence" in args or args.get("loop", False) is not False:
            raise ValueError("local Medium supports neither loop nor prompt_influence; no control is silently dropped")
        if "paid_approved" in args or "max_usd" in args:
            raise ValueError("local generation uses a take cap, not paid_approved/max_usd")
        seed = args.get("seed", 0)
        if type(seed) is not int or not 0 <= seed <= 2**32 - 1:
            raise ValueError("local seed must be an integer in [0, 2^32-1]")
        count = args.get("max_calls", 4)
        if type(count) is not int or not 1 <= count <= 8:
            raise ValueError("max_calls must be an integer from 1 to 8")
        payload = {"text": _text(args.get("text")),
                   "duration_seconds": _number(args.get("duration_seconds"), "duration_seconds", 0.5, 21.5),
                   "seed": seed}
        ready = runtime.status()
        if not ready["available"]:
            raise ValueError(f"local runtime unavailable: {ready['reason']}; no paid fallback")
        path.mkdir()
        _save(path, {"version": 2, "engine": LOCAL_ENGINE, "runtime": ready["fingerprint"]["runtime_identity"],
                     "payload": payload, "max_calls": count, "attempts": []})
    else:
        allowed = {"action", "job_dir", "text"} if action == "next" else {"action", "job_dir"}
        if set(args) - allowed:
            raise ValueError("resume/next cannot change the frozen engine, controls or budget")
    if not path.is_dir():
        raise ValueError("job does not exist")
    if (path / ".lock").is_symlink() or (path / "state.json").is_symlink():
        raise ValueError("symlinked job state is refused")
    with (path / ".lock").open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        state = json.loads((path / "state.json").read_text())
        if state.get("version") != 2 or state.get("engine") != LOCAL_ENGINE:
            raise ValueError("unsupported local job state")
        attempts = state["attempts"]
        if action in ("start", "next"):
            if attempts and attempts[-1]["status"] not in ("downloaded", "failed"):
                raise ValueError("local attempt unresolved; resume existing evidence, never automatically regenerate")
            if len(attempts) >= state["max_calls"]:
                raise ValueError("attempt budget exhausted")
            ready = runtime.status()
            if not ready["available"] or ready["fingerprint"]["runtime_identity"] != state["runtime"]:
                raise ValueError("local runtime changed/unavailable; do not substitute an engine or reset the job")
            payload = dict(state["payload"])
            payload["seed"] = (payload["seed"] + len(attempts)) % 2**32
            if "text" in args:
                payload["text"] = _text(args["text"])
            attempt = {"number": len(attempts) + 1, "payload": payload, "status": "running"}
            attempts.append(attempt)
            _save(path, state)
            try:
                runtime.render(payload, path / f"take-{attempt['number']:02d}")
            except Exception as exc:
                attempt["status"] = "failed"
                _save(path, state)
                raise ValueError(f"local generation failed (attempt counted): {exc}") from exc
        if not attempts:
            raise ValueError("job contains no attempt")
        attempt = attempts[-1]
        bundle = path / f"take-{attempt['number']:02d}"
        raw, take = bundle / "raw.wav", bundle / "take.json"
        if bundle.is_symlink() or raw.is_symlink() or take.is_symlink():
            raise ValueError("symlinked local result is refused")
        if not raw.is_file() or not take.is_file():
            if attempt["status"] == "running":
                if runtime.is_busy():
                    return {"success": True, "status": "pending", "job_dir": str(path), "calls": len(attempts), "max_calls": state["max_calls"]}
                attempt["status"] = "failed"
                _save(path, state)
                raise ValueError("local attempt lost after interruption; still counted. Use next only within the remaining grant")
            raise ValueError("local attempt failed, interrupted or still in flight; no finished evidence to resume, never regenerate on resume")
        if raw.stat().st_size > MAX_BYTES or take.stat().st_size > 1024 * 1024:
            raise ValueError("local result exceeds evidence bounds")
        receipt = json.loads(take.read_text())
        if (receipt.get("engine") != LOCAL_ENGINE or receipt.get("request") != attempt["payload"]
                or receipt.get("model", {}).get("runtime_fingerprint") != state["runtime"]
                or receipt.get("raw_wav", {}).get("sha256_file") != hashlib.sha256(raw.read_bytes()).hexdigest()):
            raise ValueError("local result does not match the frozen attempt")
        attempt["status"] = "downloaded"
        _save(path, state)
        return {"success": True, "status": "raw-needs-qa", "raw": str(raw), "take_json": str(take),
                "job_dir": str(path), "engine": LOCAL_ENGINE, "seed": attempt["payload"]["seed"],
                "calls": len(attempts), "max_calls": state["max_calls"], "estimated_usd": 0,
                "seed_supported": True, "runtime": state["runtime"]}


def generate(args, **kwargs):
    path = None
    try:
        if not isinstance(args, dict) or set(args) - set(GENERATE_SCHEMA["parameters"]["properties"]):
            raise ValueError("unknown controls (seed is not supported by fal SFX v2)")
        action = args.get("action")
        if action not in ("start", "next", "resume"):
            raise ValueError("action must be start, next or resume")
        path = _path(args.get("job_dir"))
        engine = args.get("engine", LOCAL_ENGINE) if action == "start" else None
        if action != "start" and path.is_dir() and not (path / "state.json").is_symlink():
            engine = json.loads((path / "state.json").read_text()).get("engine")
        if engine == LOCAL_ENGINE:
            return json.dumps(_local_generate(args, path))
        if "seed" in args:
            raise ValueError("unknown controls: seed is not supported by fal SFX v2")
        if action == "start":
            if args.get("engine") != ENGINE:
                raise ValueError("unknown engine; use sfx_engines, never substitute a backend")
            if args.get("paid_approved") is not True:
                raise ValueError("explicit current-work paid approval is required")
            count = args.get("max_calls")
            if type(count) is not int or not 1 <= count <= 8:
                raise ValueError("max_calls must be an integer from 1 to 8")
            seconds = _number(args.get("duration_seconds"), "duration_seconds", 0.5, 21.5)
            cap = _number(args.get("max_usd"), "max_usd", 0.001, 10)
            if count * seconds * PRICE_PER_SECOND > cap + 1e-9:
                raise ValueError("approved max_usd does not cover max_calls at the published estimate")
            loop = args.get("loop", False)
            if type(loop) is not bool:
                raise ValueError("loop must be boolean")
            payload = {"text": _text(args.get("text")), "duration_seconds": seconds, "loop": loop,
                       "prompt_influence": _number(args.get("prompt_influence", 0.3), "prompt_influence", 0, 1),
                       "output_format": "mp3_44100_128"}
            client = _client()  # Preflight before creating any artifacts.
            path.mkdir()  # Exclusive: parent must exist. Never replace a prior job.
            state = {"version": 1, "engine": ENGINE, "model": MODEL, "payload": payload,
                     "max_calls": count, "max_usd": cap, "estimated_usd_per_call": seconds * PRICE_PER_SECOND,
                     "attempts": []}
            _save(path, state)
        else:
            allowed = {"action", "job_dir", "text"} if action == "next" else {"action", "job_dir"}
            if set(args) - allowed:
                raise ValueError("resume/next cannot change the frozen engine, controls or budget")
            if not path.is_dir():
                raise ValueError("job does not exist")
            client = _client()

        # Serialize calls for this job across CLI/A2A sessions, not just threads.
        lock_path = path / ".lock"
        if lock_path.is_symlink() or (path / "state.json").is_symlink():
            raise ValueError("symlinked job state is refused")
        with lock_path.open("a") as lock:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            state = json.loads((path / "state.json").read_text())
            if state.get("version") != 1 or state.get("engine") != ENGINE or state.get("model") != MODEL:
                raise ValueError("unsupported job state")
            attempts = state["attempts"]
            if action in ("start", "next"):
                if attempts and attempts[-1]["status"] not in ("downloaded", "failed"):
                    raise ValueError("latest attempt is unresolved; resume it, never submit again")
                if len(attempts) >= state["max_calls"]:
                    raise ValueError("attempt budget exhausted")
                payload = dict(state["payload"])
                if "text" in args:
                    payload["text"] = _text(args["text"])
                attempt = {"number": len(attempts) + 1, "status": "submission-unknown", "payload": payload}
                attempts.append(attempt)
                _save(path, state)  # Count before network; ambiguous submission cannot be retried.
                handle = client.submit(MODEL, arguments=payload)
                attempt.update(request_id=handle.request_id, status="pending")
                _save(path, state)
            if not attempts:
                raise ValueError("job contains no submitted attempt")
            attempt = attempts[-1]
            if attempt["status"] == "failed":
                raise ValueError("provider rejected this attempt; it remains counted, and next may use the remaining approved budget")
            if attempt["status"] == "submission-unknown":
                raise ValueError("submission outcome unknown; inspect provider history, no automatic resubmit")
            raw = path / f"take-{attempt['number']:02d}.mp3"
            if attempt["status"] != "downloaded":
                from fal_client import Completed
                handle = client.get_handle(MODEL, attempt["request_id"])
                if not isinstance(handle.status(with_logs=False), Completed):
                    return json.dumps({"success": True, "status": "pending", "job_dir": str(path), "calls": len(attempts), "max_calls": state["max_calls"]})
                from fal_client.client import FalClientHTTPError
                try:
                    result = handle.get()
                except FalClientHTTPError as exc:
                    # Only a completed request's explicit input/moderation rejection
                    # is terminal here. Network/auth/rate-limit errors remain resumable.
                    if exc.status_code in (400, 422):
                        attempt.update(status="failed", response_status=exc.status_code)
                        _save(path, state)
                    raise
                result_path = path / f"take-{attempt['number']:02d}.tool.json"
                if not result_path.exists():
                    with result_path.open("x") as stream:
                        json.dump(result, stream, indent=2)
                temp = path / f"take-{attempt['number']:02d}.download"
                if temp.exists():
                    raise ValueError("partial download exists; preserve it and request packaging recovery, never regenerate")
                if not raw.exists():
                    try:
                        _download(result["audio"]["url"], temp)
                        os.link(temp, raw)  # Exclusive publication, no overwrite on resume.
                    finally:
                        if temp.exists() and not temp.is_symlink():
                            temp.unlink()
                attempt["status"] = "downloaded"
                _save(path, state)
            return json.dumps({"success": True, "status": "raw-needs-qa", "raw": str(raw), "job_dir": str(path),
                               "engine": ENGINE, "calls": len(attempts), "max_calls": state["max_calls"],
                               "estimated_usd": len(attempts) * state["estimated_usd_per_call"], "seed_supported": False})
    except Exception as exc:
        # Provider errors may contain signed URLs or keys; do not echo arbitrary exceptions.
        message = str(exc) if isinstance(exc, (ValueError, FileExistsError, FileNotFoundError, BlockingIOError)) else f"{type(exc).__name__}: request failed; inspect durable state and resume, never resubmit blindly"
        return json.dumps({"success": False, "error": message, "job_dir": str(path) if path else None})


def register(ctx):
    if ctx.profile_name != "audio-creator":
        return
    for schema, handler in ((CATALOG_SCHEMA, catalog), (GENERATE_SCHEMA, generate)):
        ctx.register_tool(name=schema["name"], toolset="sfx_gen", schema=schema,
                          handler=handler, description=schema["description"])
