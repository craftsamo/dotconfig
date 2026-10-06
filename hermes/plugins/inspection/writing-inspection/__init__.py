"""Terminal-free transport to the canonical shared inspector, not inspection rules."""

import hashlib
import json
import os
from pathlib import Path
import selectors
import subprocess
import time


ROOT = Path(__file__).resolve().parents[4]
SCRIPT = ROOT / "agents/curated/japanese-writing/scripts/inspect_text.py"
PYTHON = ROOT / "hermes/local/writing-inspection/venv/bin/python"
MODES = ("naturalness", "expression", "notation", "reading-load",
         "outline", "terms", "structure", "revision")
GENRES = ("default", "tech", "business", "essay")
STANCES = ("advice", "rule", "explanation")
FIELDS = {"text", "modes", "genre", "experimental", "stance", "original"}
ARRAYS = ("findings", "outline", "terms")
SCHEMA_VERSION = 2
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


def _error_report(reason, code, digest, original_digest, modes):
    return json.dumps({"schema_version": SCHEMA_VERSION, "status": "error",
                       "error": {"code": code, "message": reason},
                       "input_sha256": digest, "original_sha256": original_digest,
                       "inspector_version": None, "request": {},
                       "executed": [], "unverified": [
                           {"check": mode, "reason": reason} for mode in modes],
                       "findings": [], "score": None, "outline": [], "heading_stats": {},
                       "terms": [], "structure": {}, "revision": {}, "stats": {},
                       "dependencies": {},
                       "truncation": {"applied": False, "counts": {
                           key: {"total": 0, "returned": 0, "omitted": 0} for key in ARRAYS},
                           "excerpt_clipped": 0, "term_clipped": 0,
                           "output_budget_dropped": 0, "section_omitted": 0}}, indent=2)


def _validate_text(value, name):
    if not isinstance(value, str) or len(value) > INPUT_LIMIT:
        return None, f"{name} must be a string of at most 131072 UTF-8 bytes"
    try:
        encoded = value.encode("utf-8")
    except UnicodeEncodeError:
        return None, f"{name} must be valid UTF-8"
    if len(encoded) > INPUT_LIMIT:
        return None, f"{name} exceeds 131072 UTF-8 bytes"
    return hashlib.sha256(encoded).hexdigest(), None


def _valid_report(report, digest, original_digest):
    if (not isinstance(report, dict) or type(report.get("schema_version")) is not int
            or report["schema_version"] != SCHEMA_VERSION
            or report.get("status") not in ("ok", "partial", "error")
            or report.get("input_sha256") != digest
            or report.get("original_sha256") != original_digest
            or not isinstance(report.get("inspector_version"), str)
            or not report["inspector_version"]
            or any(not isinstance(report.get(key), list)
                   for key in ("executed", "unverified", *ARRAYS))
            or any(not isinstance(report.get(key), dict)
                   for key in ("structure", "truncation", "heading_stats", "revision", "stats"))
            or not (report.get("score") is None or isinstance(report["score"], dict))):
        return "Invalid inspector report schema or input hash"
    truncation = report["truncation"]
    counts = truncation.get("counts")
    if (not isinstance(counts, dict)
            or type(truncation.get("applied")) is not bool
            or any(type(truncation.get(key)) is not int or truncation[key] < 0
                   for key in ("output_budget_dropped", "excerpt_clipped", "term_clipped"))):
        return "Invalid inspector report truncation metadata"
    for key in ARRAYS:
        count = counts.get(key)
        if (not isinstance(count, dict)
                or any(type(count.get(field)) is not int or count[field] < 0
                       for field in ("total", "returned", "omitted"))
                or count["returned"] != len(report[key])
                or count["total"] != count["returned"] + count["omitted"]):
            return "Invalid inspector report truncation counts"
    return None


def _detail_lists(node, prefix=""):
    """Non-empty lists inside the revision section, with dotted names."""
    if isinstance(node, dict):
        for key, value in node.items():
            if key == "omitted":
                continue
            name = f"{prefix}.{key}" if prefix else key
            if isinstance(value, list):
                if value:
                    yield name, value
                for item in value:
                    yield from _detail_lists(item, name)
            elif isinstance(value, dict):
                yield from _detail_lists(value, name)


def _drop_one(report):
    """Remove one tail entry for the transport budget and account for it."""
    revision = report["revision"]
    details = list(_detail_lists(revision))
    if details:
        name, values = max(details, key=lambda item: len(json.dumps(item[1], ensure_ascii=False)))
        values.pop()
        omitted = revision.setdefault("omitted", {})
        if isinstance(omitted, dict):
            omitted[name] = omitted.get(name, 0) + 1
    else:
        key = max(ARRAYS, key=lambda name: len(report[name]))
        if not report[key]:
            return False
        report[key].pop()
        counts = report["truncation"]["counts"][key]
        counts["returned"] -= 1
        counts["omitted"] += 1
    report["truncation"]["output_budget_dropped"] += 1
    report["truncation"]["applied"] = True
    if report["status"] != "error":
        report["status"] = "partial"
    return True


def _inspect(args, profile, **kwargs):
    from hermes_constants import get_hermes_home
    from gateway.session_context import get_session_env, session_context_engaged

    digest = original_digest = None
    modes = [mode for mode in MODES if mode != "revision"]

    def error(reason, code="invalid_request"):
        return _error_report(reason, code, digest, original_digest, modes)

    # A gateway (A2A) turn binds its session profile. A resident CLI turn binds
    # none, so the effective home carries the identity and any profile it does
    # see must still be Writer's.
    session_profile = get_session_env("HERMES_SESSION_PROFILE", "")
    if (profile != "writer" or get_hermes_home().name != profile
            or (session_profile != profile
                and (session_context_engaged() or session_profile))
            or not get_session_env("HERMES_SESSION_ID", "")
            or not isinstance(kwargs.get("task_id"), str) or not kwargs["task_id"]):
        return error("Writer profile, originating session and framework task required", "wrong_scope")
    if not isinstance(args, dict) or set(args) - FIELDS:
        return error("Only text, modes, genre, experimental, stance and original are accepted")
    digest, problem = _validate_text(args.get("text"), "text")
    if problem:
        return error(problem)
    if "original" in args:
        original_digest, problem = _validate_text(args["original"], "original")
        if problem:
            return error(problem)
        modes.append("revision")
    selected = args.get("modes", modes)
    if (not isinstance(selected, list) or len(selected) > len(MODES)
            or any(not isinstance(mode, str) or mode not in MODES for mode in selected)
            or len(set(selected)) != len(selected)):
        return error("modes must be a unique list of supported modes")
    if ("revision" in selected) != ("original" in args):
        return error("original is required by, and only allowed with, the revision mode")
    if (args.get("genre", "default") not in GENRES
            or type(args.get("experimental", False)) is not bool
            or args.get("stance", STANCES[0]) not in STANCES):
        return error("genre, experimental or stance has an unsupported value")
    modes = selected
    if not PYTHON.is_file() or not os.access(PYTHON, os.X_OK) or not SCRIPT.is_file():
        return error("Canonical inspector or dedicated Python is not provisioned", "unavailable")
    payload = {key: args[key] for key in ("text", "genre", "experimental", "stance", "original") if key in args}
    payload["modes"] = modes
    request = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    if len(request) > 1048576:
        return error("Serialized request exceeds 1 MiB")
    try:
        report = json.loads(_run(request))
        problem = _valid_report(report, digest, original_digest)
        if problem:
            return error(problem, "invalid_report")
        # Transport budgeting only: keep metadata and ordered prefixes, and add
        # every removal to the shared inspector's omission accounting.
        while True:
            serialized = json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False)
            lines = serialized.splitlines()
            if (len(serialized.encode("utf-8")) <= REPORT_BYTES
                    and len(lines) <= REPORT_LINES
                    and max(map(len, lines), default=0) <= REPORT_LINE_LENGTH):
                return serialized
            if not _drop_one(report):
                return error("Inspector metadata cannot fit the report budget", "report_budget_exceeded")
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
    description = (
        "Inspect supplied Japanese text with the shared japanese-writing inspector. "
        "Returns advisory findings with reference anchors, a mechanical naturalness score, "
        "outline, terms and, with original, a revision diff; never edits. "
        "No file paths, shell, code, network or installation. "
        "Default modes: all except revision; revision runs when original is given."
    )
    text = {"type": "string", "maxLength": INPUT_LIMIT}
    ctx.register_tool(
        name="writing_inspect", toolset="writing-inspection", description=description,
        handler=lambda args, **kwargs: _inspect(args, profile, **kwargs),
        schema={"name": "writing_inspect", "description": description, "parameters": {
            "type": "object", "additionalProperties": False, "required": ["text"],
            "properties": {
                "text": dict(text, description="Text to inspect, at most 131072 UTF-8 bytes."),
                "modes": {"type": "array", "maxItems": len(MODES),
                          "uniqueItems": True, "items": {"type": "string", "enum": list(MODES)}},
                "genre": {"type": "string", "enum": list(GENRES)},
                "experimental": {"type": "boolean"},
                "stance": {"type": "string", "enum": list(STANCES)},
                "original": dict(text, description="Text before editing; enables the revision mode."),
            },
        }},
    )
