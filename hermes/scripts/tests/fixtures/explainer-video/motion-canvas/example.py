#!/usr/bin/env python3
"""Six-second native Motion Canvas technical fixture, never speech/viseme proof.

Reuses the adjacent synthetic input factory, not its HTML/GSAP authoring.
Default: propose and author only. Rendering requires --render --approve-synthetic.
Use a new --root for each run; no runtime installation or production approval.
"""

import argparse
import importlib.util
import json
import shutil
import sys
from pathlib import Path
from types import SimpleNamespace

HERE = Path(__file__).resolve().parent
_spec = importlib.util.spec_from_file_location("motion_canvas_input_factory", HERE.parent / "example.py")
inputs = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(inputs)
explainer = inputs.explainer
ASPECTS = {"landscape": "16:9", "portrait": "9:16"}
NOTICE = inputs.NOTICE


def fixture(root, framing="none", performance="still", lip_sync=None, audio=True,
            aspect="landscape", cue_at_zero=False, japanese=False):
    spec = inputs.fixture(root, framing, performance, lip_sync, audio,
                          ASPECTS.get(aspect, aspect), cue_at_zero)
    spec.update(version=2, renderer="motion-canvas")
    if japanese:
        # Only on-screen copy changes; the synthetic tone is not Japanese speech.
        texts = ["\u30ad\u30e3\u30c3\u30b7\u30e5\u306e\u6d41\u308c",
                 "\u5408\u6210\u97f3\u306b\u3088\u308b\u6280\u8853\u691c\u8a3c\u7528\u3067\u3059\u3002",
                 "1. \u30ad\u30e3\u30c3\u30b7\u30e5\u3092\u78ba\u8a8d",
                 "2. \u7d50\u679c\u3092\u4fdd\u5b58", "3. \u7d50\u679c\u3092\u518d\u5229\u7528"]
        for row, value in zip(spec["copy"], texts, strict=True):
            row["text"] = value
        spec["must_keep"] = texts[1]
    (root / "spec.json").write_text(json.dumps(spec, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return spec


def author_source(root, proposal):
    source = root / "source"
    source.mkdir()
    assets = Path(proposal["proposal"]).parent / "assets"
    if assets.exists():
        shutil.copytree(assets, source / "assets")
    for name in ("scene.tsx", "scene.meta"):
        shutil.copyfile(HERE / name, source / name)
    return source


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", required=True)
    parser.add_argument("--framing", choices=("none", "bust", "full"), default="none")
    parser.add_argument("--performance", choices=("still", "puppet", "animated"), default="still")
    parser.add_argument("--lip-sync", choices=("off", "cues", "baked"))
    parser.add_argument("--silent", action="store_true")
    parser.add_argument("--aspect", choices=tuple(ASPECTS), default="landscape")
    parser.add_argument("--cue-at-zero", action="store_true")
    parser.add_argument("--japanese", action="store_true")
    parser.add_argument("--render", action="store_true")
    parser.add_argument("--approve-synthetic", action="store_true")
    args = parser.parse_args(argv)
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
    fixture(root, args.framing, args.performance, args.lip_sync, not args.silent,
            args.aspect, args.cue_at_zero, args.japanese)
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
    return result


if __name__ == "__main__":
    main(sys.argv[1:])
