#!/usr/bin/env python3
"""Task-owned illustrative ad fixture, not a production layout/preset engine."""
import argparse
import importlib.util
import json
import shutil
import sys
from pathlib import Path

LEAF = Path(__file__).resolve().parents[4] / "profiles/video-creator/skills/video-creator-pipeline/create/ad"
TOUR_LEAF = LEAF.parent / "tour"


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


ad = _load("ad_render", LEAF / "scripts" / "ad-render.py")

DURATION = 15

# This fixture is solely local automated test evidence for the create-ad
# pipeline: a fictional, nonnumeric demo product, never a real, client-
# approved or live ad. No survey, count or "No.1"-style claim is invented;
# the claim row says exactly what it is.
PRODUCT = "Solstice Focus Timer (fictional demo product)"
AUDIENCE = "Automated test suite reviewers; not a real advertising audience"
MESSAGE = "A quiet cue to help you pause and refocus"
CLAIM = ("Assumed demo function: a soft screen dim after 25 minutes of focus "
         "(TEST FIXTURE, fictional, not a verified or client ad)*")
CTA = "See the illustrative demo"
CLAIMS_EVIDENCE = ("This is solely local automated test evidence for the create-ad pipeline. "
                    "The product, message, claim and CTA are fictional; nothing here is a "
                    "verified, client-approved or live ad.")


def _layout(width, height):
    """Test-only proportional layout: scales the original 1080x1920 fixture's
    margins/type/vertical beats to any approved canvas, never a production
    template. Font sizes scale off the shorter side so a landscape canvas
    does not inherit portrait-sized type; vertical beats keep their original
    fractional position down the canvas."""
    base = min(width, height)
    margin = round(width * 60 / 1080)
    return {
        "margin": margin,
        "content_width": width - 2 * margin,
        "message_size": round(base * 60 / 1080),
        "claim_size": round(base * 34 / 1080),
        "cta_size": round(base * 56 / 1080),
        "message_top": round(height * 400 / 1920),
        "claim_top": round(height * 900 / 1920),
        "cta_top": round(height * 1600 / 1920),
    }


def base_plan(source, aspect=ad.DEFAULT_ASPECT):
    width, height = ad.ASPECT_SIZES[aspect]
    return {
        "version": 1,
        "product": PRODUCT,
        "audience": AUDIENCE,
        "message": MESSAGE,
        "cta": CTA,
        "theme": "office",
        "style": "bold-graphic",
        "direction": "claim-led",
        "theme_detail": "Warm wood desk, soft daylight through a window",
        "claims": CLAIMS_EVIDENCE,
        "note": "",
        "duration": DURATION,
        "aspect": aspect,
        "width": width, "height": height, "fps": 30,
        "assets": {f"assets/{name}": ad.digest(source / "assets" / name)
                   for name in ("gsap.min.js", "GSAP-LICENSE.txt", "gsap-provenance.json")},
        "copy": [
            {"id": "message", "text": MESSAGE, "role": "message", "start": 1, "end": 6},
            {"id": "claim", "text": CLAIM, "role": "claim", "start": 6, "end": 10},
            {"id": "cta", "text": CTA, "role": "cta", "start": 10, "end": 15},
        ],
        "samples": [
            {"at": 0, "expect": "Opening solid stage background"},
            {"at": 3, "expect": "Message readable"},
            {"at": 8, "expect": "Claim readable with its footnote marker"},
            {"at": 12, "expect": "CTA readable"},
            {"at": DURATION - 1 / 30, "expect": "Final visible frame retains the CTA"},
        ],
    }


def fixture(root, aspect=ad.DEFAULT_ASPECT):
    """Write a fresh job scratch: source/ (with vendored GSAP + index.html) and plan.json."""
    root = ad.fresh(str(root))
    root.mkdir()
    source = root / "source"
    (source / "assets").mkdir(parents=True)
    for name in ("gsap.min.js", "GSAP-LICENSE.txt", "gsap-provenance.json"):
        shutil.copyfile(TOUR_LEAF / "assets" / name, source / "assets" / name)
    width, height = ad.ASPECT_SIZES[aspect]
    layout = _layout(width, height)
    code = (Path(__file__).parent / "index.html").read_text(encoding="utf-8")
    code = code.replace("@@DURATION@@", str(DURATION))
    code = code.replace("@@WIDTH@@", str(width))
    code = code.replace("@@HEIGHT@@", str(height))
    code = code.replace("@@MARGIN@@", str(layout["margin"]))
    code = code.replace("@@CONTENT_WIDTH@@", str(layout["content_width"]))
    code = code.replace("@@MESSAGE_SIZE@@", str(layout["message_size"]))
    code = code.replace("@@CLAIM_SIZE@@", str(layout["claim_size"]))
    code = code.replace("@@CTA_SIZE@@", str(layout["cta_size"]))
    code = code.replace("@@MESSAGE_TOP@@", str(layout["message_top"]))
    code = code.replace("@@CLAIM_TOP@@", str(layout["claim_top"]))
    code = code.replace("@@CTA_TOP@@", str(layout["cta_top"]))
    (source / "index.html").write_text(code, encoding="utf-8")
    plan = base_plan(source, aspect)
    ad.write(root / "plan.json", plan)
    return plan


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", required=True)
    parser.add_argument("--aspect", choices=sorted(ad.ASPECT_SIZES), default=ad.DEFAULT_ASPECT)
    args = parser.parse_args()
    plan = fixture(Path(args.root), args.aspect)
    print(json.dumps({"root": args.root, "plan": plan["product"], "aspect": args.aspect}))
