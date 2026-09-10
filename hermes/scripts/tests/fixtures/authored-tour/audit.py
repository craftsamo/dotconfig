#!/usr/bin/env python3
"""Pixel evidence for already rendered illustrative fixtures; no new rendering."""
import argparse
import hashlib
import json
from pathlib import Path

from PIL import Image, ImageChops, ImageStat


def audit(root):
    out = root / "pixel-audit.json"
    if out.exists():
        raise ValueError("pixel audit exists; preserve prior evidence")
    qa = json.loads((root / "final/qa.json").read_text())
    preview = sorted((root / "preview/frames").glob("*.png"))
    review = sorted((root / "final/review").glob("*.png"))
    assert len(preview) == len(review) == len(qa["samples"])
    hashes = []
    errors = []
    for before, after in zip(preview, review):
        with Image.open(before) as a, Image.open(after) as b:
            a, b = a.convert("RGB"), b.convert("RGB")
            assert a.size == b.size == (1280, 720)
            hashes.append(hashlib.sha256(b.tobytes()).hexdigest())
            errors.append(sum(ImageStat.Stat(ImageChops.difference(a, b)).mean)/3)
    # Same settled camera: these changes cannot be explained by a screenshot pan.
    assert hashes[3] != hashes[4], "Light/Dark state never changes"
    assert hashes[6] != hashes[7], "typing never advances"
    with Image.open(review[6]) as a, Image.open(review[7]) as b:
        assert ImageChops.difference(a.crop((470, 390, 620, 430)), b.crop((470, 390, 620, 430))).getbbox(), "input text pixels never change"
    assert hashes[7] != hashes[9], "modal never closes to saved UI"
    assert len(set(hashes)) >= 8, "insufficient motion/state evidence"
    assert max(errors) < 15, "preview/final mean pixel error exceeds compression/seek tolerance"
    sheet = Image.new("RGB", (1280, 1080), "white")
    for i, j in enumerate((0, 1, 4, 6, 10, 12)):
        with Image.open(review[j]) as im:
            sheet.paste(im.resize((640, 360)), ((i % 2)*640, (i // 2)*360))
    sheet.save(root / "review-sheet.png")
    report = {"evidence": "direct local illustrative fixture only", "samples": len(hashes),
              "unique_decoded_rgb_hashes": len(set(hashes)), "decoded_rgb_sha256": hashes,
              "preview_final_mean_absolute_pixel_error": errors,
              "state_and_typing_pixel_checks": "passed", "full_decode": qa["decoded"],
              "duration": qa["duration"], "bytes": qa["bytes"],
              "intro": qa["intro"]["direction"], "outro": qa["outro"]["direction"]}
    with out.open("x") as f: json.dump(report, f, indent=2)
    print(json.dumps({"root": str(root), "unique_frames": len(set(hashes)), "max_pixel_error": max(errors)}))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("roots", nargs="+")
    for value in parser.parse_args().roots:
        audit(Path(value))
