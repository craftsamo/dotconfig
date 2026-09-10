#!/usr/bin/env python3
"""Synthetic cache-flow technical fixture, not speech or character-quality proof.

Ordinary use creates inputs, a proposal and manually authored source only.
Native HyperFrames rendering requires --render --approve-synthetic explicitly.
No models, downloads, private inputs, automatic visemes or production approval.
"""
import argparse
import importlib.util
import json
import math
import shutil
import struct
import subprocess
import sys
import wave
from pathlib import Path
from types import SimpleNamespace

from PIL import Image, ImageDraw

LEAF = Path(__file__).resolve().parents[4] / "profiles/video-creator/skills/video-creator-pipeline/create/explainer-video"
SPEC = importlib.util.spec_from_file_location("explainer_fixture_helper", LEAF / "scripts/explainer.py")
explainer = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = explainer
SPEC.loader.exec_module(explainer)

DURATION = 6
SCRIPT = "Check the cache. Store the result. Reuse the result."
NOTICE = "Synthetic timing fixture, not speech proof"


def tone(path, seconds=DURATION, rate=48000):
    with wave.open(str(path), "wb") as out:
        out.setparams((1, 2, rate, 0, "NONE", "not compressed"))
        out.writeframes(b"".join(struct.pack("<h", round(2000 * math.sin(2 * math.pi * 220 * i / rate)))
                                 for i in range(round(seconds * rate))))


def fixture(root, framing="none", performance="still", lip_sync=None, audio=True, aspect="16:9", cue_at_zero=False):
    root = explainer.fresh(str(root))
    root.mkdir()
    inputs = root / "inputs"
    inputs.mkdir()
    lip_sync = lip_sync or ("off" if framing == "none" or not audio else
                            "baked" if performance == "animated" else "cues")
    character = dict(framing=framing, performance=performance, lip_sync=lip_sync,
                     body=None, video=None, mouths={}, cues=None, sync=None)
    assets = {}

    def asset(name):
        path = inputs / name
        assets["assets/" + name] = str(path)
        return path

    if audio:
        tone(asset("tone.wav"))
        asset("script.txt").write_text(SCRIPT, encoding="utf-8")
    if framing != "none":
        if performance == "animated":
            subprocess.run(["ffmpeg", "-nostdin", "-v", "error", "-n", "-f", "lavfi", "-i",
                            f"testsrc2=size=160x240:rate=30:duration={DURATION}", "-an", "-c:v", "libx264",
                            "-pix_fmt", "yuv420p", str(asset("character.mp4"))], check=True, capture_output=True)
            character["video"] = "assets/character.mp4"
            if lip_sync == "baked":
                receipt = {"master_sha256": explainer.digest(inputs / "tone.wav"),
                           "video_sha256": explainer.digest(inputs / "character.mp4")}
                explainer.write(asset("sync.json"), receipt)
                character["sync"] = "assets/sync.json"
        else:
            body = Image.new("RGBA", (160, 240), (0, 0, 0, 0))
            draw = ImageDraw.Draw(body)
            draw.rounded_rectangle((30, 5, 130, 100), 25, fill="#58c8c0")
            draw.rectangle((40, 100, 120, 230 if framing == "full" else 175), fill="#58c8c0")
            draw.ellipse((55, 35, 63, 43), fill="#102030")
            draw.ellipse((97, 35, 105, 43), fill="#102030")
            body.save(asset("body.png"))
            character["body"] = "assets/body.png"
            if lip_sync == "cues":
                for name, box in (("rest", (65, 65, 95, 69)), ("open", (65, 58, 95, 82))):
                    mouth = Image.new("RGBA", body.size, (0, 0, 0, 0))
                    ImageDraw.Draw(mouth).ellipse(box, fill="#102030")
                    mouth.save(asset(name + ".png"))
                    character["mouths"][name] = "assets/" + name + ".png"
                explainer.write(asset("cues.json"), {
                    "version": 1, "master_sha256": explainer.digest(inputs / "tone.wav"),
                    "voice": "assets/tone.wav", "voice_sha256": explainer.digest(inputs / "tone.wav"),
                    "offset": 0, "events": [
                        {"start": 0 if cue_at_zero else 0.4, "end": 0.8, "mouth": "open"},
                        {"start": 2.4, "end": 2.8, "mouth": "open"},
                        {"start": 4.4, "end": 4.8, "mouth": "open"},
                    ],
                })
                character["cues"] = "assets/cues.json"
    spec = {
        "version": 1, "topic": "A simplified cache flow", "audience": "Technical fixture reviewers",
        "learning_goal": "Distinguish lookup, storage and reuse in this simplified model",
        "theme": "Synthetic local diagram", "style": "High-contrast diagram", "direction": NOTICE,
        "renderer": "hyperframes", "duration": DURATION, "aspect": aspect, "character": character,
        "audio": {"mode": "speech" if audio else "none", "master": "assets/tone.wav" if audio else None,
                  "script": "assets/script.txt" if audio else None, "receipt": None, "captions": None, "timing": None},
        "units": [
            {"id": "lookup", "start": 0, "end": 2, "goal": "Find a stored result",
             "narration": "Check the cache." if audio else "", "before": "Request at the left",
             "change": "Request moves toward cache", "after": "Lookup reaches cache"},
            {"id": "store", "start": 2, "end": 4, "goal": "Keep a result",
             "narration": "Store the result." if audio else "", "before": "Cache is empty",
             "change": "Result enters cache", "after": "Cache contains result"},
            {"id": "reuse", "start": 4, "end": 6, "goal": "Use the stored result",
             "narration": "Reuse the result." if audio else "", "before": "Result is cached",
             "change": "Result moves to request", "after": "Stored result has been reused"},
        ],
        "copy": [{"id": name, "text": text, "start": start, "end": end} for name, text, start, end in (
            ("title", "Cache flow", 0, 6), ("notice", NOTICE, 0, 6),
            ("lookup-copy", "1. Check the cache", 0, 2), ("store-copy", "2. Store the result", 2, 4),
            ("reuse-copy", "3. Reuse the result", 4, 6))],
        "samples": [{"at": at, "expect": expect} for at, expect in (
            (0, "Initial diagram"), (1, "Lookup"), (3, "Storage"), (5, "Reuse"),
            (DURATION - 1 / 30, "Last visible frame"))],
        "assets": assets, "pending": [], "must_keep": NOTICE,
    }
    if lip_sync == "cues":
        spec["samples"].extend({"at": at, "expect": "Supplied cue selects the open mouth"} for at in (.6, 2.6, 4.6))
        spec["samples"].sort(key=lambda sample: sample["at"])
    explainer.write(root / "spec.json", spec)
    return spec


def author_source(root, proposal):
    """Fill this test's handwritten HTML, never production helper-generated UI."""
    plan = explainer.load(Path(proposal["proposal"]).parent / "plan.json")
    source = root / "source"
    source.mkdir()
    shutil.copytree(Path(proposal["proposal"]).parent / "assets", source / "assets")
    width, height = explainer.SIZES[plan["aspect"]]
    char = plan["character"]
    media, motion = [], ""
    if char["framing"] != "none":
        if char["video"]:
            media.append(f'<video id="character-body" class="presenter clip" src="{char["video"]}" muted playsinline '
                         f'data-start="0" data-duration="{DURATION}" data-track-index="1"></video>')
        else:
            media.append(f'<div id="presenter"><img id="character-body" src="{char["body"]}">')
            initial = "rest"
            if char["cues"]:
                cues = explainer.load(source / char["cues"])
                if cues["offset"] + cues["events"][0]["start"] == 0:
                    initial = cues["events"][0]["mouth"]
            for name, path in char["mouths"].items():
                media.append(f'<img id="character-mouth-{name}" src="{path}" style="opacity: {1 if name == initial else 0}">')
            media.append('</div>')
            if char["performance"] == "puppet":
                motion = 'tl.to("#presenter", {x: -24, duration: 0.4}, 2).to("#presenter", {x: 0, duration: 0.4}, 4);'
    if plan["audio"]["master"]:
        media.append(f'<audio id="master" class="clip" src="{plan["audio"]["master"]}" '
                     f'data-start="0" data-duration="{DURATION}" data-track-index="2"></audio>')
    code = (Path(__file__).parent / "index.html").read_text(encoding="utf-8")
    for key, value in {"WIDTH": width, "HEIGHT": height, "MEDIA": "\n".join(media), "MOTION": motion,
                       "MOUTH": '<script src="assets/mouth-track.js"></script>' if char["lip_sync"] == "cues" else "",
                       "MOUTH_CALL": 'addExplainerMouthTrack(tl);' if char["lip_sync"] == "cues" else ""}.items():
        code = code.replace("@@" + key + "@@", str(value))
    (source / "index.html").write_text(code, encoding="utf-8")
    return source


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", required=True)
    parser.add_argument("--framing", choices=("none", "bust", "full"), default="none")
    parser.add_argument("--performance", choices=("still", "puppet", "animated"), default="still")
    parser.add_argument("--lip-sync", choices=("off", "cues", "baked"))
    parser.add_argument("--silent", action="store_true")
    parser.add_argument("--aspect", choices=tuple(explainer.SIZES), default="16:9")
    parser.add_argument("--cue-at-zero", action="store_true", help="exercise an approved mouth cue on the first frame")
    parser.add_argument("--render", action="store_true")
    parser.add_argument("--approve-synthetic", action="store_true",
                        help="Approve only this synthetic technical fixture's plan and preview; not production content")
    args = parser.parse_args()
    if args.render and not args.approve_synthetic:
        parser.error("--render requires --approve-synthetic; this is not production approval")
    if args.framing == "none" and (args.performance != "still" or args.lip_sync not in (None, "off")):
        parser.error("no-character fixture requires still/off")
    if args.silent and args.lip_sync not in (None, "off"):
        parser.error("silent fixture requires lip-sync off")
    if args.lip_sync == "baked" and args.performance != "animated":
        parser.error("baked sync requires animated performance")
    if args.lip_sync == "cues" and args.performance == "animated":
        parser.error("animated fixture uses baked sync, not cues")
    root = Path(args.root)
    fixture(root, args.framing, args.performance, args.lip_sync, not args.silent, args.aspect, args.cue_at_zero)
    proposal = explainer.propose(SimpleNamespace(spec=str(root / "spec.json"), out=str(root / "proposal-v1")))
    source = author_source(root, proposal)
    result = {"proposal": proposal, "source": str(source), "proof": NOTICE, "native_rendered": False}
    if args.render:
        project = root / "project"
        explainer.freeze(SimpleNamespace(approved_plan=proposal["proposal"], approval_sha256=proposal["approval_sha256"],
                                         source=str(source), project=str(project)))
        preview = explainer.snapshot(SimpleNamespace(project=str(project), out=str(root / "preview")))
        result["render"] = explainer.render(SimpleNamespace(project=str(project), approved_preview=preview["preview"],
                           approval_sha256=preview["preview_sha256"], out=str(root / "final")))
        result["native_rendered"] = True
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
