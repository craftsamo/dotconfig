#!/usr/bin/env python3
"""create-promotion helper: storyboard proposal hash + checked local render.

Stdlib only. Never generates media, installs anything or touches the network.

    promotion.py propose --storyboard DRAFT.md --out NEW_DIR
    promotion.py render --approved-plan STORYBOARD.md --approval-sha256 HEX \
        --source DIR --out NEW_DIR --quality draft|final [--reference VIDEO] [--inputs JSON]

Every command prints one RESULT JSON object and exits 0 on PASS, 1 on FAIL.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import re
import shutil
import subprocess
import sys
from fractions import Fraction
from pathlib import Path

FPS = 30
DIMS = {"16:9": (1920, 1080), "9:16": (1080, 1920), "1:1": (1080, 1080), "4:5": (1080, 1350)}
AUDIO = {"none", "supplied", "pending"}
MIN_S, MAX_S = 3, 60
TOL = 0.05
REMOTE = re.compile(r"""(?:src|href)\s*=\s*["']\s*(?:https?:)?//|url\(\s*["']?\s*(?:https?:)?//|@import\s+["']?(?:https?:)?//|\bfetch\s*\(|XMLHttpRequest|WebSocket\s*\(""", re.I)
TEXT_SUFFIXES = {".html", ".htm", ".css", ".js", ".mjs", ".svg", ".json"}


class Fail(Exception):
    pass


def require(cond, msg):
    if not cond:
        raise Fail(msg)


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def fresh(value: str) -> Path:
    out = Path(value).expanduser()
    require(out.is_absolute(), "output path must be absolute")
    require(not out.exists() and not out.is_symlink(), f"output must be a new path: {out}")
    require(out.parent.is_dir(), f"output parent must exist: {out.parent}")
    return out


# ── storyboard ─────────────────────────────────────────────────────────


def parse_storyboard(path: Path) -> dict:
    require(path.is_file(), f"storyboard not found: {path}")
    text = path.read_text(encoding="utf-8")
    m = re.match(r"^---\n(.*?)\n---\n(.*)$", text, re.S)
    require(m, "storyboard needs a --- front matter block at the top")
    meta = {}
    for line in m.group(1).splitlines():
        line = line.split("#", 1)[0].strip()
        if not line:
            continue
        require(":" in line, f"front matter line is not key: value: {line!r}")
        key, value = (part.strip() for part in line.split(":", 1))
        meta[key] = value
    body = m.group(2)
    aspect = meta.get("aspect", "16:9").strip("\"'")
    require(aspect in DIMS, f"aspect must be one of {sorted(DIMS)}")
    try:
        duration = float(meta.get("duration", ""))
    except ValueError:
        raise Fail("duration must be a number") from None
    require(math.isfinite(duration) and MIN_S <= duration <= MAX_S, f"duration must be {MIN_S}..{MAX_S}s")
    require(meta.get("fps", str(FPS)) == str(FPS), "fps must be 30")
    audio = meta.get("audio", "")
    require(audio in AUDIO, f"audio must be one of {sorted(AUDIO)}")
    pending = [p.strip() for p in meta.get("pending", "").split(",") if p.strip()]
    for pid in pending:
        require(re.fullmatch(r"[a-z0-9][a-z0-9:_-]*", pid), f"invalid pending id: {pid}")
    require((audio == "pending") == ("audio" in pending), "audio: pending and a pending 'audio' id go together")

    beats = parse_beats(body)
    require(beats, "storyboard needs a ## Beats table with start/end columns")
    require(abs(beats[0][0]) <= TOL, "beats must start at 0")
    for (s0, e0), (s1, _) in zip(beats, beats[1:]):
        require(abs(s1 - e0) <= TOL, f"beats must be contiguous (gap/overlap at {e0}s)")
    for s, e in beats:
        require(e > s, f"beat end must be after start ({s}..{e})")
    require(abs(beats[-1][1] - duration) <= TOL, "beats must end at the storyboard duration")
    if pending:
        section = re.search(r"^## Pending\s*$(.*?)(?=^## |\Z)", body, re.S | re.M)
        require(section, "pending ids need a ## Pending section")
        for pid in pending:
            require(pid in section.group(1), f"pending id {pid} is not described under ## Pending")
    w, h = DIMS[aspect]
    return {"aspect": aspect, "width": w, "height": h, "duration": duration, "fps": FPS,
            "audio": audio, "pending": pending, "beats": len(beats)}


def parse_beats(body: str) -> list[tuple[float, float]]:
    section = re.search(r"^## Beats\s*$(.*?)(?=^## |\Z)", body, re.S | re.M)
    if not section:
        return []
    rows = [r for r in section.group(1).splitlines() if r.strip().startswith("|")]
    if len(rows) < 3:
        return []
    header = [c.strip().lower() for c in rows[0].strip().strip("|").split("|")]
    if "start" not in header or "end" not in header:
        return []
    si, ei = header.index("start"), header.index("end")
    beats = []
    for row in rows[2:]:
        cells = [c.strip() for c in row.strip().strip("|").split("|")]
        try:
            beats.append((float(cells[si]), float(cells[ei])))
        except (ValueError, IndexError):
            raise Fail(f"beat row needs numeric start/end: {row.strip()}") from None
    return beats


def propose(args) -> dict:
    draft = Path(args.storyboard).expanduser()
    info = parse_storyboard(draft)
    out = fresh(args.out)
    out.mkdir()
    target = out / "storyboard.md"
    shutil.copyfile(draft, target)
    digest = sha(target)
    info.update(storyboard=str(target), sha256=digest,
                status="pending-inputs" if info["pending"] else "awaiting-approval")
    (out / "proposal.json").write_text(json.dumps(info, indent=2) + "\n", encoding="utf-8")
    return info


# ── render ─────────────────────────────────────────────────────────────


def tree_hash(root: Path) -> str:
    h = hashlib.sha256()
    for p in sorted(root.rglob("*")):
        rel = p.relative_to(root)
        if any(part.startswith(".") or part == "node_modules" for part in rel.parts) or not p.is_file():
            continue
        h.update(str(rel).encode() + b"\0" + sha(p).encode() + b"\n")
    return h.hexdigest()


def check_source(source: Path, plan: dict) -> None:
    index = source / "index.html"
    require(index.is_file(), "source needs index.html")
    html = index.read_text(encoding="utf-8", errors="replace")
    root = re.search(r"<[^>]*\bid\s*=\s*[\"']root[\"'][^>]*>", html)
    require(root, "index.html needs an element with id=\"root\"")
    tag = root.group(0)

    def attr(name):
        m = re.search(rf"\b{name}\s*=\s*[\"']([^\"']*)[\"']", tag)
        return m.group(1) if m else None

    require(attr("data-composition-id") is not None, "#root needs data-composition-id")
    require(attr("data-width") == str(plan["width"]) and attr("data-height") == str(plan["height"]),
            f"#root canvas must be {plan['width']}x{plan['height']}")
    try:
        dur = float(attr("data-duration") or "nan")
    except ValueError:
        dur = float("nan")
    require(abs(dur - plan["duration"]) <= 1 / FPS, f"#root data-duration must be {plan['duration']}")
    for p in source.rglob("*"):
        rel = p.relative_to(source)
        if any(part.startswith(".") or part == "node_modules" for part in rel.parts):
            continue
        if p.is_symlink():
            raise Fail(f"symlinks are not allowed in source: {rel}")
        if p.is_file() and p.suffix.lower() in TEXT_SUFFIXES and p.name != "gsap.min.js":
            text = p.read_text(encoding="utf-8", errors="replace")
            require(not REMOTE.search(text), f"remote reference/network call in source: {rel}")


def run(cmd, cwd=None, timeout=1800):
    env = {**os.environ, "DO_NOT_TRACK": "1", "HYPERFRAMES_TELEMETRY_DISABLED": "1"}
    return subprocess.run(cmd, cwd=cwd, env=env, capture_output=True, text=True, timeout=timeout)


def probe(movie: Path) -> dict:
    proc = run(["ffprobe", "-v", "error", "-show_streams", "-show_format", "-of", "json", str(movie)], timeout=120)
    require(proc.returncode == 0, "ffprobe failed on the render")
    info = json.loads(proc.stdout)
    video = next((s for s in info["streams"] if s["codec_type"] == "video"), None)
    require(video, "render has no video stream")
    return {"width": video["width"], "height": video["height"],
            "fps": float(Fraction(video.get("avg_frame_rate", "0/1") or "0/1")),
            "duration": round(float(info["format"]["duration"]), 3),
            "audio": any(s["codec_type"] == "audio" for s in info["streams"])}


def loudness(movie: Path) -> dict:
    proc = run(["ffmpeg", "-nostdin", "-hide_banner", "-i", str(movie), "-map", "0:a:0",
                "-af", "ebur128=peak=true", "-f", "null", "-"], timeout=300)
    text = proc.stdout + proc.stderr
    summary = text.split("Summary:")[-1]
    i = re.search(r"I:\s*(-?[\d.]+|-inf)\s*LUFS", summary)
    tp = re.search(r"True peak:\s*Peak:\s*(-?[\d.]+|-inf)\s*dBFS", summary, re.S)
    to_f = lambda m: None if not m or m.group(1) == "-inf" else float(m.group(1))  # noqa: E731
    return {"integrated_lufs": to_f(i), "true_peak_dbtp": to_f(tp)}


def contact_sheet(movie: Path, duration: float, target: Path) -> None:
    rate = min(4.0, 64.0 / duration)
    rows = math.ceil(duration * rate / 8)
    run(["ffmpeg", "-nostdin", "-v", "error", "-y", "-i", str(movie), "-vf",
         f"fps={rate:.4f},scale=320:-1,tile=8x{rows}:padding=4:color=red", "-frames:v", "1", str(target)],
        timeout=300)


def compare_sheet(reference: Path, movie: Path, duration: float, target: Path) -> None:
    """Reference frames on the top row, draft frames on the bottom, 8 matching positions.

    Each row samples its own film at the same relative positions, so a
    reference shorter or longer than the draft still yields 8 frames (seeking
    the draft's absolute times past a shorter reference's end wrote nothing).
    """
    rows = []
    for index, source in enumerate((reference, movie)):
        length = duration if source == movie else probe(source)["duration"]
        times = [round(length * (i + 0.5) / 8, 3) for i in range(8)]
        frames = []
        for n, at in enumerate(times):
            frame = target.parent / f".compare-{index}-{n}.png"
            run(["ffmpeg", "-nostdin", "-v", "error", "-y", "-ss", str(at), "-i", str(source), "-frames:v", "1",
                 "-vf", "scale=400:-2", str(frame)], timeout=120)
            frames.append(frame)
        row = target.parent / f".compare-row-{index}.png"
        inputs = [arg for f in frames for arg in ("-i", str(f))]
        run(["ffmpeg", "-nostdin", "-v", "error", "-y", *inputs, "-filter_complex",
             "".join(f"[{i}:v]" for i in range(len(frames))) + f"hstack=inputs={len(frames)}", str(row)], timeout=120)
        rows.append(row)
        for f in frames:
            f.unlink(missing_ok=True)
    run(["ffmpeg", "-nostdin", "-v", "error", "-y", "-i", str(rows[0]), "-i", str(rows[1]), "-filter_complex",
         "[0:v]scale=iw:-2[a];[1:v]scale=iw:-2[b];[a][b]vstack=inputs=2", str(target)], timeout=120)
    for r in rows:
        r.unlink(missing_ok=True)
    require(target.is_file(), "reference comparison sheet was not written")


def render(args) -> dict:
    plan_path = Path(args.approved_plan).expanduser()
    require(re.fullmatch(r"[0-9a-f]{64}", args.approval_sha256 or ""), "approval sha256 required")
    require(plan_path.is_file() and sha(plan_path) == args.approval_sha256,
            "approved storyboard hash mismatch; changed bytes need a new approval")
    plan = parse_storyboard(plan_path)
    source = Path(args.source).expanduser().resolve()
    require(source.is_dir(), "source directory not found")
    out = fresh(args.out)
    require(not out.resolve().is_relative_to(source), "output must be outside the source")
    check_source(source, plan)
    final = args.quality == "final"
    inputs = {}
    if final:
        if plan["pending"]:
            require(args.inputs, f"final render needs --inputs resolving: {', '.join(plan['pending'])}")
        if args.inputs:
            inputs = json.loads(Path(args.inputs).expanduser().read_text(encoding="utf-8"))
            require(isinstance(inputs, dict), "--inputs must be a JSON object {pending id: path}")
        for pid in plan["pending"]:
            p = inputs.get(pid)
            require(p, f"pending input unresolved: {pid}")
            p = (source / p) if not Path(p).is_absolute() else Path(p)
            require(p.is_file() and p.resolve().is_relative_to(source), f"input {pid} must be a file under source: {p}")
    binary = shutil.which("hyperframes")
    require(binary, "hyperframes CLI missing; ask maintainer to provision it")
    out.mkdir()
    source_hash = tree_hash(source)
    lint = run([binary, "lint", "--json"], cwd=source, timeout=300)
    (out / "lint.json").write_text(lint.stdout, encoding="utf-8")
    try:
        lint_data = json.loads(lint.stdout)
    except ValueError:
        lint_data = {"ok": False, "errorCount": None}
    require(lint_data.get("ok") and lint_data.get("errorCount") == 0 and lint_data.get("filesScanned", 1) > 0,
            "hyperframes lint failed; see lint.json")
    movie = out / "promotion.mp4"
    cmd = [binary, "render", "--output", str(movie), "--fps", str(FPS),
           "--quality", "delivery" if final else "draft", "--quiet"]
    if final:
        cmd += ["--strict", "--no-best-effort"]
    proc = run(cmd, cwd=source)
    (out / "render.log").write_text(proc.stdout + proc.stderr, encoding="utf-8")
    require(proc.returncode == 0 and movie.is_file(), "hyperframes render failed; see render.log")
    require(tree_hash(source) == source_hash, "source changed during render")
    facts = probe(movie)
    contact_sheet(movie, plan["duration"], out / "sheet.png")
    compare = None
    if args.reference:
        reference = Path(args.reference).expanduser()
        require(reference.is_file(), f"reference not found: {reference}")
        compare_sheet(reference, movie, plan["duration"], out / "compare.png")
        compare = str(out / "compare.png")
    checks = {
        "canvas": (facts["width"], facts["height"]) == (plan["width"], plan["height"]),
        "fps": abs(facts["fps"] - FPS) < 0.01,
        "duration": abs(facts["duration"] - plan["duration"]) <= 0.1,
    }
    level = None
    if facts["audio"]:
        level = loudness(movie)
    if final:
        checks["audio_present"] = facts["audio"] == (plan["audio"] != "none")
        tp = (level or {}).get("true_peak_dbtp")
        checks["true_peak_below_0"] = (not facts["audio"]) or (tp is not None and tp < 0)
    status = "PASS" if all(checks.values()) else "FAIL"
    result = {"status": status, "quality": args.quality, "movie": str(movie), "sheet": str(out / "sheet.png"), "compare": compare,
              "approved_plan": str(plan_path), "approval_sha256": args.approval_sha256,
              "source": str(source), "source_tree_sha256": source_hash, "movie_sha256": sha(movie),
              "probe": facts, "loudness": level, "checks": checks, "inputs": inputs,
              "lint": {"errors": lint_data.get("errorCount"), "warnings": lint_data.get("warningCount")},
              "unverified": ["temporal review beyond sampled sheet", "listening"],
              "media_generation": 0}
    (out / "render.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    if status != "PASS":
        raise Fail(f"render checks failed: {[k for k, v in checks.items() if not v]}; see {out / 'render.json'}")
    return result


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("propose")
    p.add_argument("--storyboard", required=True)
    p.add_argument("--out", required=True)
    r = sub.add_parser("render")
    r.add_argument("--approved-plan", required=True)
    r.add_argument("--approval-sha256", required=True)
    r.add_argument("--source", required=True)
    r.add_argument("--out", required=True)
    r.add_argument("--quality", choices=["draft", "final"], required=True)
    r.add_argument("--inputs")
    r.add_argument("--reference")
    args = ap.parse_args(argv)
    try:
        result = propose(args) if args.cmd == "propose" else render(args)
    except (Fail, OSError, ValueError, subprocess.TimeoutExpired) as exc:
        print("RESULT " + json.dumps({"status": "FAIL", "error": str(exc)}))
        return 1
    print("RESULT " + json.dumps(result))
    return 0


if __name__ == "__main__":
    sys.exit(main())
