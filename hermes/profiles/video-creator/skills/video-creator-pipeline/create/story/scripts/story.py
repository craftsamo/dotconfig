#!/usr/bin/env python3
"""create-story helper: storyboard + cast proposal hash and checked local render.

Reuses create-promotion's storyboard parser and HyperFrames render checks
(loaded as a private module instance, so its limits here do not leak) and
adds what a character story needs: a cast whose approved art is bound by
hash, dialogue checked verbatim against the approved script, and Mix
caption markup checked against its sidecar. Stdlib only apart from that.

    story.py propose --storyboard DRAFT.md --cast id=PATH[,id=PATH...] --out NEW_DIR [--script SCRIPT]
    story.py render --approved-plan STORYBOARD.md --approval-sha256 HEX \
        --source DIR --out NEW_DIR --quality draft|final [--inputs JSON] [--captions captions.json]
        [--reference VIDEO]

Every command prints one RESULT JSON object and exits 0 on PASS, 1 on FAIL.
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
CREATE = HERE.parents[1]
KERNEL = HERE.parents[2]

_spec = importlib.util.spec_from_file_location("story_promotion", CREATE / "promotion/scripts/promotion.py")
base = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(base)
base.MIN_S, base.MAX_S = 10, 120
base.MOVIE = "story.mp4"

Fail, require, sha, fresh = base.Fail, base.require, base.sha, base.fresh
IMAGE_SUFFIXES = {".png", ".webp", ".jpg", ".jpeg"}
CAST_ID = re.compile(r"[a-z0-9]+(?:-[a-z0-9]+)*")
MAX_CAST_FILES = 200
QUOTED = re.compile(r"([\w-]*\s*[:：]?)\s*(?:\u300c([^\u300c\u300d]+)\u300d|\u201c([^\u201c\u201d]+)\u201d|\"([^\"]+)\")")
CAST_ART = "## Cast art (bound by propose)"


def section(body: str, name: str) -> str | None:
    match = re.search(rf"^## {name}\s*$(.*?)(?=^## |\Z)", body, re.S | re.M)
    return match.group(1) if match else None


def table(text: str) -> tuple[list[str], list[list[str]]]:
    rows = [r for r in text.splitlines() if r.strip().startswith("|")]
    if len(rows) < 3:
        return [], []
    header = [c.strip().lower() for c in rows[0].strip().strip("|").split("|")]
    return header, [[c.strip() for c in r.strip().strip("|").split("|")] for r in rows[2:]]


def cast_files(value: str) -> dict[str, list[Path]]:
    """`id=PATH` pairs; PATH is one approved image or a directory of them (a pose pack)."""
    cast: dict[str, list[Path]] = {}
    for pair in [p.strip() for p in value.split(",") if p.strip()]:
        require("=" in pair, f"cast entry must be id=PATH: {pair}")
        cid, raw = (part.strip() for part in pair.split("=", 1))
        require(CAST_ID.fullmatch(cid), f"cast id must be a lowercase slug: {cid}")
        require(cid not in cast, f"duplicate cast id: {cid}")
        path = Path(raw).expanduser()
        require(path.is_absolute() and "://" not in raw, f"cast {cid}: absolute local path required")
        if path.is_dir() and (path / "manifest.json").is_file():
            # an image-creator mascot pack: only items its own QA passed are approved art
            manifest = json.loads((path / "manifest.json").read_text(encoding="utf-8"))
            require(isinstance(manifest, list), f"cast {cid}: manifest.json must be a list of items")
            files = sorted(path / item["file"] for item in manifest
                           if isinstance(item, dict) and item.get("passed") is True and "/" not in item.get("file", "/"))
            require(all(f.is_file() for f in files), f"cast {cid}: manifest names a missing file")
        elif path.is_dir():
            files = sorted(p for p in path.iterdir() if p.is_file() and p.suffix.lower() in IMAGE_SUFFIXES
                           and p.stem not in ("sheet", "silhouette"))
        else:
            files = [path] if path.is_file() and path.suffix.lower() in IMAGE_SUFFIXES else []
        require(files, f"cast {cid}: no approved PNG/WebP/JPEG art at {raw}")
        cast[cid] = files
    require(cast, "cast: at least one character")
    require(sum(len(v) for v in cast.values()) <= MAX_CAST_FILES, f"cast: at most {MAX_CAST_FILES} images")
    return cast


def normalize(text: str) -> str:
    return " ".join(text.replace("\u3000", " ").split())


def check_story(path: Path, cast: dict[str, list[Path]] | None, script: Path | None,
                script_bound: bool = False) -> dict:
    info = base.parse_storyboard(path)
    head, body = path.read_text(encoding="utf-8").split("\n---\n", 1)
    require(re.search(r"^aspect\s*:", head, re.M), "front matter needs an explicit aspect (the story default is 9:16)")
    cast_text = section(body, "Cast")
    require(cast_text is not None, "storyboard needs a ## Cast section")
    _, cast_rows = table(cast_text)
    ids = [row[0].strip("` ") for row in cast_rows if row and row[0]]
    require(ids, "## Cast needs a table whose first column is the cast id")
    if cast is not None:
        require(set(ids) == set(cast), f"## Cast ids {sorted(ids)} must match --cast ids {sorted(cast)}")
    header, beats = table(section(body, "Beats") or "")
    require("cast" in header and "dialogue" in header, "## Beats needs cast and dialogue columns")
    ci, di = header.index("cast"), header.index("dialogue")
    require(all(len(row) == len(header) for row in beats),
            "a beats row has more cells than the header; a '|' inside a cell breaks the table")
    lines = []
    for number, row in enumerate(beats, 1):
        on_screen = set()
        for cid in re.split(r"[,\s]+", row[ci] if ci < len(row) else ""):
            cid = cid.strip("` ")
            require(not cid or cid in ("-", "none") or cid in ids, f"beat names unknown cast id: {cid}")
            on_screen.add(cid)
        cell = row[di].strip() if di < len(row) else ""
        if cell in ("", "-", "none"):
            continue
        spoken = QUOTED.findall(cell)
        require(spoken, f"beat {number}: dialogue must quote each line as speaker: 「line」 or \"line\"")
        leftover = QUOTED.sub("", cell)
        require(not re.search(r"[\"\u201c\u201d\u300c\u300d]", leftover), f"beat {number}: unpaired quote in dialogue")
        for speaker, text in ((m[0], next(x for x in m[1:] if x)) for m in spoken):
            speaker = speaker.strip().rstrip(":：").strip("` ")
            require(not speaker or speaker in on_screen or speaker in ("vo", "narrator"),
                    f"beat {number}: speaker {speaker} is not on screen in that beat")
            lines.append(normalize(text))
    if script is not None:
        text = normalize(script.read_text(encoding="utf-8"))
        missing = [line for line in lines if line not in text]
        require(not missing, f"dialogue not verbatim in the approved script: {missing[:3]}")
    elif lines and not script_bound:
        require("script" in info["pending"], "quoted dialogue without --script needs a pending 'script' id")
    info.update(cast_ids=ids, dialogue_lines=len(lines))
    return info


def propose(args) -> dict:
    draft = Path(args.storyboard).expanduser()
    cast = cast_files(args.cast)
    script = None
    if args.script:
        script = Path(args.script).expanduser()
        require(script.is_absolute() and script.is_file(), "script: absolute path to the approved script required")
    info = check_story(draft, cast, script)
    require(CAST_ART not in draft.read_text(encoding="utf-8"), f"the draft must not carry {CAST_ART!r} itself")
    out = fresh(args.out)
    out.mkdir()
    target = out / "storyboard.md"
    bound = {"cast": {cid: {p.name: sha(p) for p in files} for cid, files in cast.items()},
             "script_sha256": sha(script) if script else None}
    # The approval hash covers these bytes, so changed art or script needs a new approval.
    target.write_text(draft.read_text(encoding="utf-8").rstrip("\n") + f"\n\n{CAST_ART}\n\n```json\n"
                      + json.dumps(bound, indent=2, ensure_ascii=False) + "\n```\n", encoding="utf-8")
    info.update(storyboard=str(target), sha256=sha(target),
                status="pending-inputs" if info["pending"] else "awaiting-approval",
                cast={cid: {str(p): sha(p) for p in files} for cid, files in cast.items()},
                script={"path": str(script), "sha256": sha(script)} if script else None)
    (out / "proposal.json").write_text(json.dumps(info, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return info


def bound_art(text: str) -> dict:
    block = re.search(re.escape(CAST_ART) + r"\s*```json\n(.*?)\n```", text, re.S)
    require(block, "approved storyboard has no bound cast art; propose it with story.py")
    return json.loads(block.group(1))


def render(args) -> dict:
    plan_path = Path(args.approved_plan).expanduser()
    require(plan_path.is_file() and sha(plan_path) == (args.approval_sha256 or ""),
            "approved storyboard hash mismatch; changed bytes need a new approval")
    bound = bound_art(plan_path.read_text(encoding="utf-8"))
    info = base.parse_storyboard(plan_path)
    script = None
    if not bound["script_sha256"] and "script" in info["pending"] and args.quality == "final":
        inputs = json.loads(Path(args.inputs).expanduser().read_text(encoding="utf-8")) if args.inputs else {}
        require(inputs.get("script"), "final render needs the approved script in --inputs")
        script = Path(inputs["script"])
        script = script if script.is_absolute() else Path(args.source).expanduser() / script
        require(script.is_file(), "script input not found")
    # Dialogue is checked against the approved script: at propose, or now when it arrived later.
    check_story(plan_path, None, script, script_bound=bool(bound["script_sha256"]) or args.quality == "draft")
    source = Path(args.source).expanduser().resolve()
    require(source.is_dir(), "source directory not found")
    visible = [p for p in source.rglob("*") if p.is_file()
               and not any(part.startswith(".") or part == "node_modules" for part in p.relative_to(source).parts)]
    markup = "\n".join(p.read_text(encoding="utf-8", errors="replace") for p in visible
                       if p.suffix.lower() in base.TEXT_SUFFIXES and p.name != "gsap.min.js")
    referenced = {sha(p) for p in visible if p.suffix.lower() in IMAGE_SUFFIXES
                  and p.relative_to(source).as_posix() in markup}
    used = {cid: [name for name, digest in files.items() if digest in referenced]
            for cid, files in bound["cast"].items()}
    require(all(used.values()), "every cast member must appear from its approved art, byte for byte and "
            "referenced by the source: " + ", ".join(cid for cid, names in used.items() if not names))
    mix_audio = load_mix_audio()
    captions = None
    if args.captions:
        captions = Path(args.captions).expanduser()
        require(captions.is_file(), "captions: Mix captions.json not found")
    try:  # without a sidecar, no mix-caption element may exist either
        mix_audio.check_caption_markup(source / "index.html", captions)
    except (ValueError, KeyError) as exc:
        raise Fail(f"caption markup does not match the Mix sidecar: {exc}") from exc
    result = base.render(args)
    result.update(cast_used={cid: len(names) for cid, names in used.items()},
                  captions_checked=bool(captions), script_checked=bool(bound["script_sha256"] or script))
    (Path(result["movie"]).parent / "render.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    return result


def load_mix_audio():
    sys.path.insert(0, str(KERNEL / "scripts"))
    try:
        import mix_audio  # noqa: PLC0415
    except Exception as exc:  # pragma: no cover - environment dependent
        raise Fail(f"Mix caption check unavailable ({exc}); run with the Hermes venv Python") from exc
    return mix_audio


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("propose")
    p.add_argument("--storyboard", required=True)
    p.add_argument("--cast", required=True)
    p.add_argument("--script")
    p.add_argument("--out", required=True)
    r = sub.add_parser("render")
    r.add_argument("--approved-plan", required=True)
    r.add_argument("--approval-sha256", required=True)
    r.add_argument("--source", required=True)
    r.add_argument("--out", required=True)
    r.add_argument("--quality", choices=["draft", "final"], required=True)
    r.add_argument("--inputs")
    r.add_argument("--captions")
    r.add_argument("--reference")
    args = ap.parse_args(argv)
    try:
        result = propose(args) if args.cmd == "propose" else render(args)
    except (Fail, OSError, ValueError, KeyError, TypeError, subprocess.TimeoutExpired) as exc:
        print("RESULT " + json.dumps({"status": "FAIL", "error": str(exc)}, ensure_ascii=False))
        return 1
    print("RESULT " + json.dumps(result, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
