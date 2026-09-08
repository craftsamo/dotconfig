#!/usr/bin/env python3
"""Freeze music direction and exact score/prompt bytes before any audio work.

Hashes bind content, not approver identity. Creator must relay the actual
client's approval in the same work conversation; a file is not that approval.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import math
import os
from pathlib import Path
import re
import stat
import sys
import tempfile

MAX_DOCUMENT = 1024 * 1024
MAX_REFERENCE = 128 * 1024 * 1024
LOCAL = "local:stable-audio-3-medium"
FAL = "fal:stable-audio-3-medium"
START = "<!-- MUSIC_MANIFEST\n"
END = "\nMUSIC_MANIFEST -->"
COMMON = {"what_for", "theme", "theme_detail", "style", "instrumentation", "direction",
          "tempo", "duration", "ending", "must_keep", "reference_audio", "reference_focus",
          "slug", "note"}
CREATE = {"key", "meter", "melody", "harmony", "score"}
GENERATE = {"engine", "seed", "max_calls", "max_usd"}


def digest(data):
    return hashlib.sha256(data).hexdigest()


def read_bytes(path, limit=MAX_DOCUMENT):
    path = Path(path).expanduser()
    with os.fdopen(os.open(path, os.O_RDONLY | os.O_NONBLOCK | os.O_NOFOLLOW), "rb") as stream:
        info = os.fstat(stream.fileno())
        if not stat.S_ISREG(info.st_mode) or info.st_size > limit:
            raise ValueError("input must be a bounded regular local file")
        raw = stream.read(limit + 1)
    if len(raw) > limit:
        raise ValueError("input exceeds byte bound")
    return raw


def reject_constant(value):
    raise ValueError(f"nonfinite JSON: {value}")


def unique_pairs(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def parse_json(raw):
    def finite_float(value):
        result = float(value)
        if not math.isfinite(result):
            raise ValueError("nonfinite JSON number")
        return result
    return json.loads(raw, parse_constant=reject_constant, parse_float=finite_float,
                      object_pairs_hook=unique_pairs)


def numeric(value, name, low, high):
    if isinstance(value, bool):
        raise ValueError(f"{name} must be a finite number")
    try:
        value = float(value)
    except (ValueError, TypeError):
        raise ValueError(f"{name} must be a finite number") from None
    if not math.isfinite(value) or not low <= value <= high:
        raise ValueError(f"{name} must be in [{low}, {high}]")
    return value


def media_module():
    path = Path(__file__).with_name("music-media.py")
    spec = importlib.util.spec_from_file_location("music_plan_media", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def validate_form(kind, form, artifact):
    if kind not in ("create", "generate") or not isinstance(form, dict):
        raise ValueError("kind must be create/generate and form must be an object")
    allowed = COMMON | (CREATE if kind == "create" else GENERATE)
    if set(form) - allowed:
        raise ValueError(f"unknown form fields: {sorted(set(form) - allowed)}")
    form = dict(form)
    for key in ("what_for", "theme", "style"):
        if not isinstance(form.get(key), str) or not form[key].strip():
            raise ValueError(f"{key} is required")
    for key in allowed - {"duration", "seed", "max_calls", "max_usd"}:
        if key in form and (not isinstance(form[key], str) or len(form[key]) > 8000):
            raise ValueError(f"{key} must be text of at most 8000 characters")
    form["duration"] = numeric(form.get("duration"), "duration", 1, 60)
    for key, default in (("direction", "steady"), ("ending", "resolve")):
        form.setdefault(key, default)
        if not form[key].strip():
            raise ValueError(f"{key} cannot be blank")
    if form["ending"] not in ("resolve", "fade", "loop"):
        raise ValueError("ending must be resolve, fade or loop")
    if "reference_audio" in form and not form.get("reference_focus", "").strip():
        raise ValueError("reference_audio requires reference_focus; a path is not upload consent")
    if kind == "create":
        score = parse_json(artifact)
        media_module().validate_score(score)
        if abs(score["duration_seconds"] - form["duration"]) > 1e-9:
            raise ValueError("score duration differs from the form")
        for key in ("key", "meter"):
            if key in form and form[key] != score[key]:
                raise ValueError(f"score {key} differs from the form")
            form.setdefault(key, score[key])
        tempo = re.fullmatch(r"\s*(\d+(?:\.\d+)?)\s*(?:BPM)?\s*", form.get("tempo", ""), re.I)
        if tempo and abs(float(tempo[1]) - score["bpm"]) > 1e-9:
            raise ValueError("score BPM differs from explicit form tempo")
        form.setdefault("tempo", f"{score['bpm']} BPM")
        settings = {"duration_seconds": form["duration"], "bpm": score["bpm"],
                    "meter": score["meter"], "key": score["key"]}
    else:
        if not artifact.strip() or len(artifact) > 450:
            raise ValueError("generation prompt must contain 1..450 characters including newline")
        if "instrumental" not in artifact.lower() or "no vocals" not in artifact.lower():
            raise ValueError("prompt must explicitly request instrumental music and no vocals (not a guarantee)")
        engine = form.setdefault("engine", LOCAL)
        if engine not in (LOCAL, FAL):
            raise ValueError("unknown engine; never substitute or fall back")
        seed = form.setdefault("seed", 0)
        if type(seed) is not int or not 0 <= seed < 2**32:
            raise ValueError("seed must be uint32")
        if engine == FAL and "max_calls" not in form:
            raise ValueError("fal requires an explicit max_calls grant")
        count = form.setdefault("max_calls", 3)
        if type(count) is not int or not 1 <= count <= 8:
            raise ValueError("max_calls must be an integer in [1, 8]")
        cap = form.get("max_usd")
        if engine == LOCAL and "max_usd" in form:
            raise ValueError("local generation uses a take grant, not a dollar cap")
        if engine == FAL:
            cap = numeric(cap, "max_usd", .0376, 10)
            if cap + 1e-9 < count * .0376:
                raise ValueError("max_usd does not cover the approved call count estimate")
            form["max_usd"] = cap
        settings = {"engine": engine, "duration_seconds": form["duration"], "seed": seed,
                    "max_calls": count, "max_usd": cap}
    return form, settings


def propose(kind, form_file, arrangement_file, out, score_file=None, prompt_file=None):
    if kind == "create" and (not score_file or prompt_file):
        raise ValueError("create requires score-file only")
    if kind == "generate" and (not prompt_file or score_file):
        raise ValueError("generate requires prompt-file only")
    artifact = read_bytes(score_file if kind == "create" else prompt_file)
    text = artifact.decode("utf-8")
    form, settings = validate_form(kind, parse_json(read_bytes(form_file)), text)
    arrangement = read_bytes(arrangement_file).decode("utf-8")
    if not arrangement.strip() or "MUSIC_MANIFEST" in arrangement:
        raise ValueError("arrangement must be nonblank prose without manifest markers")
    inputs = []
    for key in ("reference_audio", "score"):
        if key in form:
            path = Path(form[key]).expanduser().absolute()
            raw = read_bytes(path, MAX_REFERENCE if key == "reference_audio" else MAX_DOCUMENT)
            if key == "score" and parse_json(raw) != parse_json(artifact):
                raise ValueError("supplied score must match the approved score; do not silently rewrite it")
            inputs.append({"role": key, "path": str(path), "sha256": digest(raw), "bytes": len(raw)})
            form[key] = str(path)
    out = Path(out).expanduser().absolute()
    if out.exists() or out.is_symlink() or not out.parent.is_dir():
        raise ValueError("out must be a new directory with an existing parent")
    out = out.parent.resolve() / out.name
    name = "score.json" if kind == "create" else "generation-prompt.txt"
    manifest = {"version": 1, "kind": kind, "form": form, "settings": settings,
                "artifact": {"file": name, "sha256": digest(artifact)}, "inputs": inputs}
    payload = json.dumps(manifest, ensure_ascii=False, indent=2, allow_nan=False)
    document = (f"# Music {kind} Proposal\n\n" + arrangement.rstrip() +
                "\n\n## Effective Form And Execution Settings\n\n```json\n" + payload +
                "\n```\n\nApprove this exact proposal through Creator before audio work. "
                "The hash binds content, not approver identity. No reference audio is uploaded. "
                "Auditory quality and generated vocal absence remain unverified.\n\n" + START + payload + END + "\n")
    raw = document.encode("utf-8")
    if len(raw) > MAX_DOCUMENT:
        raise ValueError("proposal exceeds document bound")
    with tempfile.TemporaryDirectory(prefix=".music-proposal-", dir=out.parent) as work:
        bundle = Path(work) / "bundle"
        bundle.mkdir()
        (bundle / name).write_bytes(artifact)
        (bundle / "proposal.md").write_bytes(raw)
        media_module().publish(bundle, out)
    return {"status": "proposal-only", "approved_plan": str(out / "proposal.md"),
            "approval_sha256": digest(raw), "kind": kind, "settings": settings,
            "artifact": str(out / name), "spend": 0, "audio_created": False}


def load_approved(path, sha256, kind):
    if not isinstance(sha256, str) or not re.fullmatch(r"[0-9a-f]{64}", sha256):
        raise ValueError("approval_sha256 must be an exact lowercase SHA-256 digest")
    path = Path(path).expanduser().absolute()
    raw = read_bytes(path)
    if digest(raw) != sha256:
        raise ValueError("proposal hash differs from the Creator-relayed approval")
    document = raw.decode("utf-8")
    if document.count(START) != 1 or document.count(END) != 1:
        raise ValueError("proposal must contain one frozen music manifest")
    manifest = parse_json(document.split(START, 1)[1].split(END, 1)[0])
    if (not isinstance(manifest, dict) or set(manifest) != {"version", "kind", "form", "settings", "artifact", "inputs"}
            or type(manifest["version"]) is not int or manifest["version"] != 1 or manifest["kind"] != kind):
        raise ValueError("unsupported proposal or wrong music leaf")
    name = "score.json" if kind == "create" else "generation-prompt.txt"
    if not isinstance(manifest["artifact"], dict) or manifest["artifact"].get("file") != name:
        raise ValueError("unexpected proposal artifact path")
    artifact = read_bytes(path.parent / name)
    if digest(artifact) != manifest["artifact"].get("sha256"):
        raise ValueError("approved score/prompt has changed")
    text = artifact.decode("utf-8")
    form, settings = validate_form(kind, manifest["form"], text)
    if form != manifest["form"] or settings != manifest["settings"]:
        raise ValueError("effective form/settings differ from frozen proposal")
    expected_roles = {key for key in ("reference_audio", "score") if key in form}
    inputs = manifest["inputs"]
    if not isinstance(inputs, list) or len(inputs) != len(expected_roles):
        raise ValueError("reference evidence differs from the effective form")
    seen = set()
    for item in inputs:
        if not isinstance(item, dict) or set(item) != {"role", "path", "sha256", "bytes"}:
            raise ValueError("invalid frozen input evidence")
        role = item["role"]
        if role not in expected_roles or role in seen or item["path"] != form[role]:
            raise ValueError("reference role/path mismatch")
        seen.add(role)
        ref = read_bytes(item["path"], MAX_REFERENCE if role == "reference_audio" else MAX_DOCUMENT)
        if len(ref) != item["bytes"] or digest(ref) != item["sha256"]:
            raise ValueError("reference input changed; obtain a new proposal approval")
    return {**manifest, "artifact_text": text, "artifact_sha256": digest(artifact),
            "approved_plan": str(path), "approval_sha256": sha256}


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__, allow_abbrev=False)
    sub = p.add_subparsers(dest="command", required=True)
    new = sub.add_parser("propose", allow_abbrev=False)
    new.add_argument("--kind", choices=("create", "generate"), required=True)
    for field in ("form-file", "arrangement-file", "out"):
        new.add_argument("--" + field, required=True)
    new.add_argument("--score-file")
    new.add_argument("--prompt-file")
    check = sub.add_parser("check", allow_abbrev=False)
    check.add_argument("--kind", choices=("create", "generate"), required=True)
    check.add_argument("--approved-plan", required=True)
    check.add_argument("--approval-sha256", required=True)
    try:
        args = vars(p.parse_args(argv))
        if args.pop("command") == "propose":
            result = propose(**args)
        else:
            value = load_approved(args["approved_plan"], args["approval_sha256"], args["kind"])
            result = {"status": "PASS", "kind": value["kind"], "settings": value["settings"]}
        code = 0
    except (OSError, ValueError, TypeError, RecursionError) as exc:
        result, code = {"status": "FAIL", "error": str(exc)}, 2
    print("RESULT: " + json.dumps(result, ensure_ascii=False, allow_nan=False))
    return code


if __name__ == "__main__":
    sys.exit(main())
