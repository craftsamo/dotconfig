"""Measure the synthetic study's encoded frames and extract native review material."""
import argparse
import json
import math
from pathlib import Path
import subprocess

from PIL import Image, ImageChops, ImageDraw, ImageFont, ImageStat


def review(root):
    out = root / "quality-review"
    out.mkdir()
    times = json.loads((root / "preview/preview.json").read_text())["times"]
    previews = sorted((root / "preview/frames").glob("*.png"))
    decoded = sorted((root / "final/review").glob("*.png"))
    assert len(previews) == len(decoded) == len(times)
    rows = []
    regions = {"full": (0, 0, 1920, 1080), "volume": (0, 450, 960, 1080), "ui": (1130, 195, 1802, 939)}
    for at, before, after in zip(times, previews, decoded):
        a, b = Image.open(before).convert("RGB"), Image.open(after).convert("RGB")
        measures = {}
        for name, box in regions.items():
            stat = ImageStat.Stat(ImageChops.difference(a.crop(box), b.crop(box)))
            rms = math.sqrt(sum(v * v for v in stat.rms) / 3)
            psnr = 20 * math.log10(255 / rms) if rms else 100
            measures[name] = {"mae": sum(stat.mean) / 3, "psnr_db": psnr}
            assert psnr >= 35, (at, name, psnr)
        rows.append({"at": at, "regions": measures})
    final = Image.open(decoded[-1])
    final.crop(regions["ui"]).save(out / "ui-native.png")
    final.crop((1145, 585, 1785, 710)).save(out / "selected-row-native.png")
    final.crop((1164, 780, 1768, 930)).save(out / "action-rail-native.png")
    dense = out / "dense"
    dense.mkdir()
    # Source is a verified constant-30fps synthetic fixture. n=99..165 in steps
    # of three gives exact decoded-frame sampling of 3.3..5.5 seconds.
    subprocess.run(["ffmpeg", "-nostdin", "-v", "error", "-i", str(root / "final/study.mp4"),
                    "-vf", "select='between(n,99,165)*not(mod(n-99,3))',crop=960:630:0:450",
                    "-fps_mode", "vfr", str(dense / "%03d.png")], check=True, timeout=90)
    frames = sorted(dense.glob("*.png"))
    assert len(frames) == 23
    def finish_pixels(path):
        pixels = Image.open(path).convert("RGB").tobytes()
        return sum(g > 150 and r > 110 and g > r * 1.1 for r, g, b in zip(pixels[0::3], pixels[1::3], pixels[2::3]))
    onset_pixels = finish_pixels(frames[3]) - finish_pixels(frames[0])
    assert onset_pixels > 100, "Material response is not visible by 3.6 s after the 3.5 s contact"
    width, height, cols = 320, 240, 4
    sheet = Image.new("RGB", (width * cols, height * math.ceil(len(frames) / cols)), "#f1f1eb")
    draw, font = ImageDraw.Draw(sheet), ImageFont.load_default(size=18)
    for index, path in enumerate(frames):
        x, y = index % cols * width, index // cols * height
        image = Image.open(path).convert("RGB")
        image.thumbnail((width, height - 28))
        sheet.paste(image, (x, y + 28))
        draw.text((x + 8, y + 4), f"{3.3 + index / 10:.1f}s", fill="#182330", font=font)
    sheet.save(out / "shader-sequence.png")
    report = {"fixture": "synthetic study", "encoded_sample_pairs": rows, "dense_frames": len(frames), "onset_changed_pixels": onset_pixels,
              "normal_speed_viewing": "unverified", "artistic_acceptance": "not-established",
              "scope": "PSNR detects gross encoded drift, not aesthetic quality or whole-film semantic fidelity"}
    (out / "metrics.json").write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps({"review": str(out), "sample_pairs": len(rows), "dense_frames": len(frames), "psnr_floor_db": 35}))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("directory", type=Path)
    review(parser.parse_args().directory.resolve())
