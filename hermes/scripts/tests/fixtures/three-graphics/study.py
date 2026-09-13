"""Synthetic maintainer fixture. Hash arguments exercise gates, never user approval."""
import argparse
import importlib.util
from pathlib import Path
import shutil
import sys
from types import SimpleNamespace

HERE = Path(__file__).resolve().parent
HERMES = HERE.parents[3]
PIPELINE = HERMES / "profiles/video-creator/skills/video-creator-pipeline"
sys.path.insert(0, str(PIPELINE / "scripts"))
spec = importlib.util.spec_from_file_location("three_study_ad", PIPELINE / "create/ad/scripts/ad-render.py")
ad = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ad)
graphics = ad.graphics


def prepare(root):
    root = Path(root).resolve()
    ad.require(not root.exists() and root.parent.is_dir(), "new fixture directory required")
    source = root / "source"
    (source / "assets").mkdir(parents=True)
    shutil.copyfile(HERE / "index.html", source / "index.html")
    for name in ("gsap.min.js", "GSAP-LICENSE.txt", "gsap-provenance.json"):
        shutil.copyfile(ad.VENDOR / name, source / "assets" / name)
    graphics.stage(source / "assets")
    copy = {"eyebrow":"FORM / FIELD", "study-label":"INTERFACE MATERIAL STUDY",
        "headline":"Make room for the next move.", "subtitle":"One action. A clearer working set.",
        "volume-label":"01 / VOLUME & SURFACE", "task-title":"Working set", "task-count":"03",
        "task-one":"Review the brief", "rank-one":"01", "task-two":"Shape the sequence", "rank-two":"02",
        "task-three":"Resolve the motion", "rank-three":"03", "rail-label":"Ready to arrange",
        "action-label":"Resolve", "footer":"SYNTHETIC FIXTURE / NOT A PRODUCT CLAIM"}
    plan = {"version":1,"purpose":"study","question":"Do real parallax, a spatial GLSL boundary and bespoke UI states survive seek and encoding?",
        "product":"Fictional interface study","audience":"Maintainer validating graphics and component quality",
        "message":copy["headline"],"theme":"material workbench","style":"editorial interface","direction":"continuous state change",
        "duration":8,"aspect":"16:9","width":1920,"height":1080,"fps":30,"graphics":"three-webgl2",
        "assets":{"assets/" + p.name:ad.digest(p) for p in (source / "assets").iterdir()},
        "copy":[{"id":key,"text":value,"role":"message" if key=="headline" else "support",
                 "start":3.95 if key=="rail-label" else 0,"end":8} for key,value in copy.items()],
        "samples":[{"at":at,"expect":expect} for at,expect in [(0,"First frame without a flash"),(.5,"Typography and UI arrival"),
            (1.5,"Camera travel creates real parallax"),(2.8,"Separated plates retain occlusion"),(3.5,"Pointer contact starts the response"),
            (4.1,"Material boundary crosses the front surface"),(4.6,"Action rail and selection agree"),(5.3,"New surface resolved"),
            (7.966666666666667,"Final components remain still and readable")]]}
    ad.write(root / "plan.json", plan)
    ad.preflight(SimpleNamespace(plan=str(root / "plan.json"), assets=str(source / "assets")))
    ad.freeze(SimpleNamespace(plan=str(root / "plan.json"), approval_sha256=ad.digest(root / "plan.json"),
        source=str(source), project=str(root / "project"), study=True))
    return root


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=("prepare", "snapshot", "render"))
    parser.add_argument("directory")
    args = parser.parse_args()
    root = Path(args.directory).resolve()
    if args.action == "prepare":
        prepare(root)
    elif args.action == "snapshot":
        ad.snapshot(SimpleNamespace(project=str(root / "project"), out=str(root / "preview")))
    else:
        ad.render(SimpleNamespace(project=str(root / "project"), approved_preview=str(root / "preview"),
            approval_sha256=ad.digest(root / "preview/preview.json"), out=str(root / "final"), study=True))
    print(root)
