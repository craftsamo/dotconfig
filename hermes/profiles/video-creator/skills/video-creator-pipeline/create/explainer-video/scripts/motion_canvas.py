"""Pinned local Motion Canvas adapter; no installs, editor, network assets or TTS."""
from __future__ import annotations

import json
import os
import re
import shutil
import signal
import subprocess
from pathlib import Path

from tour import command, digest, image, load, local, number, require, text, write

HERE = Path(__file__).resolve().parent
ENGINE = HERE.parents[6] / "engines/motion-canvas"
RUNTIME = HERE.parents[6] / "local/motion-canvas"
SUFFIXES = {".ts", ".tsx", ".js", ".json", ".meta", ".css", ".png", ".jpg", ".jpeg",
            ".webp", ".svg", ".mp4", ".wav", ".woff2", ".md", ".txt"}
CONTROL_FILES = {"plan.json", "proposal.md", "approved-proposal.md", "integrity.json"}


def identity():
    node = shutil.which("node")
    require(node and (RUNTIME / "runtime.json").is_file(),
            "Motion Canvas runtime missing; maintainer setup required, no automatic install")
    result = json.loads(command([node, str(ENGINE / "render.mjs"), "--identity"], timeout=30))
    return {"engine": "motion-canvas", "runtime": result, "adapter": digest(Path(__file__)),
            "ffmpeg": command(["ffmpeg", "-version"]).splitlines()[0]}


def source_files(root):
    require(root.is_absolute() and root.is_dir() and ".." not in root.parts, "source must be an absolute physical directory")
    require(not any(path.is_symlink() for path in (root, *root.parents)), "symlink source forbidden")
    files, total = {}, 0
    for path in root.rglob("*"):
        require(not path.is_symlink(), "symlink in source forbidden")
        require(path.name not in ("node_modules", "package.json", "package-lock.json", "vite.config.ts", "vite.config.js"),
                "Project dependencies/config are runtime-owned, not source inputs")
        if path.is_dir():
            continue
        local(str(path), SUFFIXES)
        name = path.relative_to(root).as_posix()
        files[name] = digest(path)
        if name not in CONTROL_FILES:
            total += path.stat().st_size
        payload = set(files) - CONTROL_FILES
        require(len(payload) <= 200 and total <= 128_000_000, "source exceeds 200 files / 128 MB")
    return files


def source_check(root, plan):
    files = source_files(root)
    require("scene.tsx" in files and "scene.meta" in files, "Motion Canvas requires scene.tsx and frozen scene.meta")
    meta = load(root / "scene.meta")
    require(isinstance(meta, dict) and set(meta) == {"version", "seed", "timeEvents"}, "invalid scene metadata")
    require(type(meta["version"]) is int and meta["version"] == 1, "scene metadata version must be 1")
    require(type(meta["seed"]) is int and 0 <= meta["seed"] <= 2**32 - 1, "explicit deterministic scene seed required")
    require(isinstance(meta["timeEvents"], list) and len(meta["timeEvents"]) <= 256, "bounded timeEvents required")
    names = set()
    for event in meta["timeEvents"]:
        require(isinstance(event, dict) and set(event) == {"name", "targetTime"}, "time event needs name/targetTime")
        text(event["name"], "time event name", 80)
        require(event["name"] not in names, "duplicate time event name")
        names.add(event["name"])
        number(event["targetTime"], 0, plan["duration"], "time event target")
    for name in files:
        if Path(name).suffix not in (".ts", ".tsx", ".js", ".css"):
            continue
        source = (root / name).read_text(encoding="utf-8")
        require(not re.search(r"\b(fetch|XMLHttpRequest|WebSocket|EventSource|setTimeout|setInterval|requestAnimationFrame|Date)\s*\("
                              r"|Math\.random|Date\.now|performance\.now|\bimport\s*\(", source),
                f"{name}: network/clocks/dynamic imports forbidden")
        require(not re.search(r"['\"][^'\"]+\?(?:scene|project|raw|url)['\"]", source),
                "Vite query imports are not supported; use ordinary frozen modules/assets")


def sample_frames(plan):
    frames = [round(sample["at"] * 30) for sample in plan["samples"]]
    require(len(set(frames)) == len(frames), "Motion Canvas samples must identify distinct frames")
    return frames


def invoke(root, plan, out, mode):
    expected_runtime = identity()["runtime"]
    width, height = (1280, 720) if plan["aspect"] == "16:9" else (720, 1280)
    job = {"project": str(root), "out": str(out / "canvas"), "mode": mode, "fps": 30,
           "width": width, "height": height, "count": round(plan["duration"] * 30), "samples": sample_frames(plan)}
    write(out / "motion-canvas-job.json", job)
    node = shutil.which("node")
    require(node, "Node missing; no automatic install")
    with subprocess.Popen([node, str(ENGINE / "render.mjs"), "--job", str(out / "motion-canvas-job.json")],
                          stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, start_new_session=True) as process:
        try:
            stdout, stderr = process.communicate(timeout=660)
        except (subprocess.TimeoutExpired, KeyboardInterrupt):
            os.killpg(process.pid, signal.SIGTERM)
            try:
                stdout, stderr = process.communicate(timeout=15)
            except subprocess.TimeoutExpired:
                os.killpg(process.pid, signal.SIGKILL)
                stdout, stderr = process.communicate()
            (out / "motion-canvas.log").write_text(stdout + stderr, encoding="utf-8")
            raise ValueError("Motion Canvas render interrupted/timed out; partial output retained")
    (out / "motion-canvas.log").write_text(stdout + stderr, encoding="utf-8")
    require(process.returncode == 0, "Motion Canvas failed; see motion-canvas.log")
    audit = load(local(str(out / "canvas/audit.json"), {".json"}))
    require(audit.get("runtime") == expected_runtime, "Motion Canvas worker runtime differs from expected identity")
    expected = set(range(job["count"])) if mode == "render" else set(job["samples"])
    require(audit.get("ok") is True and audit.get("count") == job["count"], "incomplete Motion Canvas render")
    require(set(audit["frames"]) == {f"{frame:06}.png" for frame in expected}, "Motion Canvas frame set mismatch")
    for name, sha in audit["frames"].items():
        path = local(str(out / "canvas/frames" / name), {".png"})
        require(digest(path) == sha and image(path) == (width, height), "Motion Canvas frame integrity mismatch")
    require({item["frame"] for item in audit["audits"]} == set(job["samples"]), "missing Motion Canvas sample audit")
    checked = sum(item["copyChecked"] for item in audit["audits"])
    require(checked > 0, "no Motion Canvas copy/layout checks ran")
    write(out / "check.json", {"ok": True, "renderer": "motion-canvas", "copy": {"checked": checked},
        "layout": {"checked": checked}, "contrast": {"enabled": False, "reason": "Canvas contrast requires visual review"},
        "samples": audit["audits"]})
    return audit


def snapshot(root, plan, out):
    audit = invoke(root, plan, out, "snapshot")
    (out / "frames").mkdir()
    for index, frame in enumerate(sample_frames(plan)):
        shutil.copyfile(out / "canvas/frames" / f"{frame:06}.png", out / "frames" / f"{index:02}.png")
    return audit


def render(root, plan, out, preview):
    audit = invoke(root, plan, out, "render")
    for index, frame in enumerate(sample_frames(plan)):
        require(digest(out / "canvas/frames" / f"{frame:06}.png") == digest(preview / "frames" / f"{index:02}.png"),
                "Motion Canvas render differs from approved preview; new preview approval required")
    movie = out / "explainer.mp4"
    args = ["ffmpeg", "-nostdin", "-v", "error", "-n", "-framerate", "30", "-start_number", "0",
            "-i", str(out / "canvas/frames/%06d.png")]
    if plan["audio"]["master"]:
        args += ["-f", "wav", "-i", str(root / plan["audio"]["master"]), "-map", "0:v:0", "-map", "1:a:0",
                 "-c:a", "aac", "-b:a", "192k"]
    else:
        args += ["-an"]
    args += ["-c:v", "libx264", "-pix_fmt", "yuv420p", "-frames:v", str(audit["count"]),
             "-t", str(plan["duration"]), "-movflags", "+faststart", str(movie)]
    (out / "render.log").write_text(command(args, timeout=600), encoding="utf-8")
