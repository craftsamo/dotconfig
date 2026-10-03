#!/usr/bin/env python3
"""Read-only inspection of Japanese prose (UTF-8 plain text or limited Markdown).

    python3 -B inspect_text.py --request < request.json
    python3 -B inspect_text.py --file draft.md [--original before.md]
        [--modes naturalness,reading-load] [--genre tech] [--stance advice] [--experimental]

Request fields: ``text`` (required), ``modes``, ``genre``, ``experimental``,
``stance`` and ``original`` (only with the ``revision`` mode). The report is one JSON
document (schema version 2) on stdout; exit status is 0 for ``ok`` and
``partial`` and 1 for ``error``. Nothing is written, installed or fetched.
"""

import json
from pathlib import Path
import sys

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parent))

from inspector import report as reporting  # noqa: E402
from inspector import score  # noqa: E402
from inspector.document import Document  # noqa: E402
from inspector.morphology import load as load_morphology  # noqa: E402
from inspector.rules import BY_MODE, MODES  # noqa: E402
from inspector.rules import naturalness  # noqa: E402

GENRES = ("default", "tech", "business", "essay")
STANCES = ("advice", "rule", "explanation")
MAX_TEXT = 131072
MAX_REQUEST = 1048576
MAX_OUTPUT = reporting.MAX_OUTPUT
FIELDS = {"text", "modes", "genre", "experimental", "original", "stance"}


def _check_text(value, name):
    if type(value) is not str:
        raise ValueError(f"{name} must be a string")
    try:
        size = len(value.encode("utf-8"))
    except UnicodeEncodeError as exc:
        raise ValueError(f"{name} must contain valid Unicode scalars") from exc
    if size > MAX_TEXT:
        raise ValueError(f"{name} exceeds {MAX_TEXT} UTF-8 bytes")


def _resolve_modes(modes, original):
    if modes is None:
        return [m for m in MODES if m != "revision" or original is not None]
    if type(modes) is not list or any(type(m) is not str or m not in MODES for m in modes):
        raise ValueError("modes must be a list of supported mode names")
    if len(set(modes)) != len(modes):
        raise ValueError("modes must not contain duplicates")
    if ("revision" in modes) != (original is not None):
        raise ValueError("original is required by, and only allowed with, the revision mode")
    return modes


def inspect_text(text, modes=None, genre="default", experimental=False, original=None, stance=None):
    """Return a schema v2 report; invalid arguments raise ValueError."""
    _check_text(text, "text")
    if original is not None:
        _check_text(original, "original")
    if genre not in GENRES:
        raise ValueError("unsupported genre")
    if type(experimental) is not bool:
        raise ValueError("experimental must be a boolean")
    if stance is not None and stance not in STANCES:
        raise ValueError("unsupported stance")
    modes = _resolve_modes(modes, original)
    selected = [module for module in BY_MODE.values() if module.MODE in modes]
    morphology = load_morphology(any(module.MORPHOLOGY for module in selected))
    inspection = reporting.Inspection(
        Document(text), morphology, genre, experimental,
        Document(original) if original is not None else None, stance,
    )
    inspection.report["request"] = {"modes": [m.MODE for m in selected], "genre": genre, "experimental": experimental, "stance": stance}
    inspection.report["dependencies"] = morphology.info
    for module in selected:
        module.run(inspection)
    report = inspection.report
    report["findings"].sort(key=lambda f: (f["line"], f["column"], MODES.index(f["mode"]), f["rule_id"]))
    if naturalness in selected:
        complete = not any(note["check"] in naturalness.SCORED_RULES for note in report["unverified"])
        report["score"] = score.compute(report["findings"], len(text), naturalness.SCORED_RULES, complete)
    return reporting.finish(report)


def _unique_object(pairs):
    obj = {}
    for key, value in pairs:
        if key in obj:
            raise ValueError("duplicate JSON field")
        obj[key] = value
    return obj


def _reject_constant(_):
    raise ValueError("non-finite JSON number")


def _read_request():
    data = sys.stdin.buffer.read(MAX_REQUEST + 1)
    if len(data) > MAX_REQUEST:
        raise ValueError("request too large")
    request = json.loads(data.decode("utf-8"), object_pairs_hook=_unique_object, parse_constant=_reject_constant)
    if type(request) is not dict or set(request) - FIELDS or "text" not in request:
        raise ValueError("request must contain text and only known fields")
    if any(value is None for value in request.values()):
        raise ValueError("request fields must not be null")
    return request


def _parse_file_args(args):
    options = {}
    names = {"--file": "text", "--original": "original", "--modes": "modes", "--genre": "genre", "--stance": "stance"}
    i = 0
    while i < len(args):
        flag = args[i]
        if flag == "--experimental":
            options["experimental"] = True
            i += 1
            continue
        if flag not in names or i + 1 >= len(args) or names[flag] in options:
            raise ValueError("usage")
        value = args[i + 1]
        if flag in ("--file", "--original"):
            value = Path(value).read_text(encoding="utf-8")
        elif flag == "--modes":
            value = [m.strip() for m in value.split(",") if m.strip()]
        options[names[flag]] = value
        i += 2
    if "text" not in options:
        raise ValueError("usage")
    return options


def main(argv=None):
    args = sys.argv[1:] if argv is None else argv
    request = {}
    pretty = False
    try:
        if args == ["--request"]:
            request = _read_request()
        elif args[:1] == ["--file"]:
            request = _parse_file_args(args)
            pretty = True
        else:
            raise ValueError("usage")
        report = inspect_text(
            request["text"], request.get("modes"), request.get("genre", "default"),
            request.get("experimental", False), request.get("original"), request.get("stance"),
        )
        code = 0
    except (ValueError, UnicodeError, RecursionError, OSError):
        report = _error_report(request, "invalid_request", "Invalid request, arguments, file or input size; see the module docstring.")
        code = 1
    except Exception:
        report = _error_report(request, "runtime_failure", "Inspector execution failed; no complete result is available.")
        code = 1
    if pretty:
        sys.stdout.write(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    else:
        sys.stdout.buffer.write(reporting.serialize(report))
    return code


def _error_report(request, code, message):
    def valid(value):
        if type(value) is not str:
            return None
        try:
            value.encode("utf-8")
        except UnicodeEncodeError:
            return None
        return value
    report = reporting.base(valid(request.get("text")), valid(request.get("original")))
    report["error"] = {"code": code, "message": message}
    return reporting.finish(report)


if __name__ == "__main__":
    sys.exit(main())
