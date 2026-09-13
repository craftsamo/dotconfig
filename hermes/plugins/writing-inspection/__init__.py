"""Terminal-free transport to the canonical shared inspector, not inspection rules."""

import hashlib
import json
import os
from pathlib import Path
import selectors
import subprocess
import time


ROOT = Path(__file__).resolve().parents[3]
SCRIPT = ROOT / "agents/curated/japanese-writing/scripts/inspect_text.py"
PYTHON = ROOT / "hermes/local/writing-inspection/venv/bin/python"
MODES = ("reading-load", "outline", "terms", "structure")
INPUT_LIMIT = 131072
OUTPUT_LIMIT = 256 * 1024
REPORT_BYTES = 40000
REPORT_LINES = 1800
REPORT_LINE_LENGTH = 1900
STDERR_LIMIT = 16 * 1024
TIMEOUT = 20


def _run(request):
    # Multiplex stdin and both outputs: neither a full input pipe nor noisy stderr
    # can bypass the deadline. No text is placed in argv, logs or temporary files.
    deadline = time.monotonic() + TIMEOUT
    child = subprocess.Popen(
        [str(PYTHON), "-I", "-B", str(SCRIPT), "--request"],
        stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        shell=False, bufsize=0, cwd=str(ROOT), env={},
    )
    output = bytearray()
    stderr_size = 0
    sent = 0
    try:
        with selectors.DefaultSelector() as selector:
            for pipe, event in ((child.stdin, selectors.EVENT_WRITE),
                                (child.stdout, selectors.EVENT_READ),
                                (child.stderr, selectors.EVENT_READ)):
                os.set_blocking(pipe.fileno(), False)
                selector.register(pipe, event)
            while selector.get_map():
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    raise TimeoutError
                for key, _ in selector.select(remaining):
                    pipe = key.fileobj
                    if pipe is child.stdin:
                        try:
                            sent += os.write(pipe.fileno(), request[sent:sent + 4096])
                        except BrokenPipeError:
                            sent = len(request)
                        if sent == len(request):
                            selector.unregister(pipe)
                            pipe.close()
                    else:
                        limit = OUTPUT_LIMIT if pipe is child.stdout else STDERR_LIMIT
                        size = len(output) if pipe is child.stdout else stderr_size
                        chunk = os.read(pipe.fileno(), min(4096, limit - size + 1))
                        if not chunk:
                            selector.unregister(pipe)
                            pipe.close()
                        elif size + len(chunk) > limit:
                            raise OverflowError
                        elif pipe is child.stdout:
                            output.extend(chunk)
                        else:
                            stderr_size += len(chunk)
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise TimeoutError
            code = child.wait(timeout=remaining)
        if code != 0:
            raise RuntimeError
        return bytes(output)
    finally:
        if child.poll() is None:
            child.terminate()
            try:
                child.wait(timeout=0.5)
            except subprocess.TimeoutExpired:
                child.kill()
                child.wait()
        for pipe in (child.stdin, child.stdout, child.stderr):
            pipe.close()


def _inspect(args, profile, **kwargs):
    from hermes_constants import get_hermes_home
    from gateway.session_context import get_session_env, session_context_engaged

    digest = None
    modes = list(MODES)

    def error(reason, code="invalid_request"):
        return json.dumps({"schema_version": 1, "status": "error",
                           "error": {"code": code, "message": reason},
                           "input_sha256": digest, "inspector_version": None,
                           "executed": [], "unverified": [
                               {"check": mode, "reason": reason} for mode in modes],
                           "findings": [], "outline": [], "terms": [],
                           "structure": {}, "dependencies": {},
                           "truncation": {"applied": False, "counts": {
                               key: {"total": 0, "returned": 0, "omitted": 0}
                               for key in ("findings", "outline", "terms")},
                               "excerpt_clipped": 0, "term_clipped": 0,
                               "output_budget_dropped": 0}}, indent=2)

    if (profile != "writer" or get_hermes_home().name != profile
            or not session_context_engaged()
            or get_session_env("HERMES_SESSION_PROFILE", "") != profile
            or not get_session_env("HERMES_SESSION_ID", "")
            or not isinstance(kwargs.get("task_id"), str) or not kwargs["task_id"]):
        return error("Writer profile, originating session and framework task required", "wrong_scope")
    if not isinstance(args, dict) or set(args) - {"text", "modes"}:
        return error("Only text and modes are accepted")
    text = args.get("text")
    if not isinstance(text, str) or len(text) > INPUT_LIMIT:
        return error("text must be a string of at most 131072 UTF-8 bytes")
    try:
        encoded = text.encode("utf-8")
    except UnicodeEncodeError:
        return error("text must be valid UTF-8")
    if len(encoded) > INPUT_LIMIT:
        return error("text exceeds 131072 UTF-8 bytes")
    digest = hashlib.sha256(encoded).hexdigest()
    selected = args.get("modes", modes)
    if (not isinstance(selected, list) or len(selected) > len(MODES)
            or any(not isinstance(mode, str) or mode not in MODES for mode in selected)
            or len(set(selected)) != len(selected)):
        return error("modes must be a unique list of supported modes")
    modes = selected
    if not PYTHON.is_file() or not os.access(PYTHON, os.X_OK) or not SCRIPT.is_file():
        return error("Canonical inspector or dedicated Python is not provisioned", "unavailable")
    request = json.dumps({"text": text, "modes": modes}, ensure_ascii=False).encode("utf-8")
    if len(request) > 1048576:
        return error("Serialized request exceeds 1 MiB")
    try:
        report = json.loads(_run(request))
        if (not isinstance(report, dict) or type(report.get("schema_version")) is not int
                or report["schema_version"] != 1
                or report.get("status") not in ("ok", "partial", "error")
                or report.get("input_sha256") != digest
                or not isinstance(report.get("inspector_version"), str)
                or not report["inspector_version"]
                or any(not isinstance(report.get(key), list)
                       for key in ("executed", "unverified", "findings", "outline", "terms"))
                or not isinstance(report.get("structure"), dict)
                or not isinstance(report.get("truncation"), dict)):
            return error("Invalid inspector report schema or input hash", "invalid_report")
        truncation = report["truncation"]
        arrays = ("findings", "outline", "terms")
        counts = truncation.get("counts")
        if (not isinstance(counts, dict)
                or type(truncation.get("applied")) is not bool
                or any(type(truncation.get(key)) is not int or truncation[key] < 0
                       for key in ("output_budget_dropped", "excerpt_clipped", "term_clipped"))):
            return error("Invalid inspector report truncation metadata", "invalid_report")
        for key in arrays:
            count = counts.get(key)
            if (not isinstance(count, dict)
                    or any(type(count.get(field)) is not int or count[field] < 0
                           for field in ("total", "returned", "omitted"))
                    or count["returned"] != len(report[key])
                    or count["total"] != count["returned"] + count["omitted"]):
                return error("Invalid inspector report truncation counts", "invalid_report")
        # Transport budgeting only: retain metadata and ordered prefixes, and add
        # every removal to the shared inspector's existing omission accounting.
        while True:
            serialized = json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False)
            lines = serialized.splitlines()
            if (len(serialized.encode("utf-8")) <= REPORT_BYTES
                    and len(lines) <= REPORT_LINES
                    and max(map(len, lines), default=0) <= REPORT_LINE_LENGTH):
                return serialized
            key = max(arrays, key=lambda name: len(report[name]))
            if not report[key]:
                return error("Inspector metadata cannot fit the report budget", "report_budget_exceeded")
            report[key].pop()
            counts[key]["returned"] -= 1
            counts[key]["omitted"] += 1
            truncation["output_budget_dropped"] += 1
            truncation["applied"] = True
            if report["status"] != "error":
                report["status"] = "partial"
    except (TimeoutError, subprocess.TimeoutExpired):
        return error("Inspector exceeded its 20-second deadline", "timeout")
    except OverflowError:
        return error("Inspector output exceeded its bounded pipe limit", "output_limit")
    except (ValueError, UnicodeError, RecursionError):
        return error("Invalid inspector JSON report", "invalid_report")
    except (OSError, RuntimeError):
        return error("Inspector unavailable or failed; diagnostics withheld", "unavailable")


def register(ctx):
    if ctx.profile_name != "writer":
        return
    profile = ctx.profile_name
    description = ("Inspect supplied text with the shared Japanese-writing inspector. "
                   "Returns findings and explicit unverified checks, not edits or a quality score. "
                   "No file paths, shell, code, network or installation. All modes run by default.")
    ctx.register_tool(
        name="writing_inspect", toolset="writing-inspection", description=description,
        handler=lambda args, **kwargs: _inspect(args, profile, **kwargs),
        schema={"name": "writing_inspect", "description": description, "parameters": {
            "type": "object", "additionalProperties": False, "required": ["text"],
            "properties": {
                "text": {"type": "string", "maxLength": INPUT_LIMIT,
                         "description": "Text only, at most 131072 UTF-8 bytes."},
                "modes": {"type": "array", "maxItems": 4,
                          "uniqueItems": True, "items": {"type": "string", "enum": list(MODES)}},
            },
        }},
    )
