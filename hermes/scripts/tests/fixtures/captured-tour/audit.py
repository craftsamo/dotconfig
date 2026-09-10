#!/usr/bin/env python3
"""Decode source/final pixels, verify timestamp mapping, optionally prove kept audio."""

import argparse
import json
import shutil
import sys
from pathlib import Path
from types import SimpleNamespace

import numpy as np

LEAF = Path(__file__).resolve().parents[4] / "profiles/video-creator/skills/video-creator-pipeline/create/tour"
sys.path.insert(0, str(LEAF / "scripts"))
import authored
import footage


def pixels(path, time, filter):
    data = authored.command(["ffmpeg", "-nostdin", "-v", "error", "-ss", str(time), "-i", str(path),
                             "-frames:v", "1", "-vf", filter, "-pix_fmt", "rgb24", "-f", "rawvideo", "-"], binary=True)
    return np.frombuffer(data, dtype=np.uint8).astype(np.int16)


def audit(project, final, out):
    out = authored.fresh(str(out))
    out.mkdir()
    authored.project_model(str(project))
    mapping = authored.load(project / "assets/footage/media.json")["clips"][0]
    source = project / "assets/footage" / mapping["path"]
    raw_form = authored.load(project / "form.json")
    raw = Path(authored.load(Path(raw_form["source"]))["clips"][0]["path"])
    timestamps = json.loads(authored.command(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_frames",
        "-show_entries", "frame=best_effort_timestamp_time", "-of", "json", str(source)]))
    pts = [float(f["best_effort_timestamp_time"]) for f in timestamps["frames"]]
    records = []
    for time in [3, 5, 7, 10, 12]:
        if time >= mapping["timeline_start"] + mapping["duration"]:
            continue
        source_time = time - mapping["timeline_start"]
        source_pts = min(pts, key=lambda t: abs(t-source_time))
        assert abs(source_pts-source_time) <= 1/30
        expected = pixels(source, source_time, "scale=1120:630")
        actual = pixels(final / "tour.mp4", time, "crop=1120:630:80:80")
        raw_pixels = pixels(raw, source_time + mapping["source_start"], "scale=1120:630")
        delta = np.abs(expected-actual)
        raw_delta = np.abs(expected-raw_pixels)
        metrics = {"timeline": time, "prepared_time": source_time, "prepared_pts": source_pts,
                   "raw_time": source_time + mapping["source_start"], "final_mean_error": float(delta.mean()),
                   "final_channels_within_10": float((delta<=10).mean()), "raw_mean_error": float(raw_delta.mean())}
        records.append(metrics)
        assert delta.mean() < 4 and (delta<=10).mean() > .95, metrics
        assert raw_delta.mean() < 4, metrics
        # A fixed sanitized-fixture badge is evidence of the viewport, NOT a mask.
        authored.command(["ffmpeg", "-nostdin", "-v", "error", "-n", "-ss", str(time), "-i", str(final / "tour.mp4"),
                          "-frames:v", "1", str(out / f"final-{time}.png")])
    authored.write(out / "alignment.json", {"records": records, "privacy_redaction": "not implemented; sanitized fixture only",
        "source_sha256": footage.sha256(raw), "prepared_sha256": footage.sha256(source), "full_decode": True})
    print(json.dumps({"alignment": str(out), "samples": len(records)}))


def supplied_audio(project, out):
    out = authored.fresh(str(out))
    out.mkdir(mode=0o700)
    original_form = authored.load(project / "form.json")
    original = authored.load(Path(original_form["source"]))["clips"][0]
    raw = out / "supplied-tone.mp4"
    authored.command(["ffmpeg", "-nostdin", "-v", "error", "-n", "-i", original["path"],
        "-f", "lavfi", "-i", "sine=frequency=440:sample_rate=48000", "-map", "0:v:0", "-map", "1:a:0",
        "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac", "-t", str(original["duration"]), str(raw)])
    manifest = {"clips": [{**original, "path": str(raw), "sha256": footage.sha256(raw), "audio": "keep"}]}
    authored.write(out / "source.json", manifest)
    source = out / "source"
    (source / "assets").mkdir(parents=True)
    for name in ("gsap.min.js", "GSAP-LICENSE.txt", "gsap-provenance.json"):
        shutil.copyfile(LEAF / "assets" / name, source / "assets" / name)
    footage.prepare(str(out / "source.json"), str(source / "assets/footage"))
    html = (project / "index.html").read_text()
    audio = f'<audio id="demo-audio" src="assets/footage/demo.mp4" data-start="2" data-duration="{original["duration"]}" data-media-start="0"></audio>'
    (source / "index.html").write_text(html.replace('</video>', '</video>' + audio))
    shutil.copyfile(project / "index.motion.json", source / "index.motion.json")
    form = {k:v for k,v in original_form.items() if k not in ("approved_plan", "approval_sha256", "target", "start_state")}
    form.update(screen_mode="supplied", source=str(out / "source.json"), source_sha256=authored.digest(out / "source.json"))
    proposal = out / "proposal-v1.md"
    proposal.write_text('# Supplied Audio Fixture\n\nSynthetic 440 Hz test tone, not recorded browser audio.\n\n```tour\n'+json.dumps({"form":form})+'\n```\n')
    form.update(approved_plan=str(proposal), approval_sha256=authored.digest(proposal))
    authored.write(out / "form.json", form)
    shutil.copyfile(project / "contract.json", out / "contract.json")
    authored.freeze(SimpleNamespace(source=str(source), project=str(out / "project"), form=str(out / "form.json"), contract=str(out / "contract.json")))
    authored.snapshot(SimpleNamespace(project=str(out / "project"), out=str(out / "preview")))
    authored.render(SimpleNamespace(project=str(out / "project"), out=str(out / "final"), approved_preview=str(out / "preview")))
    authored.write(out / "audio-proof.json", audio_check(out / "final"))
    print(json.dumps({"supplied_audio": str(out), "status": "passed"}))


def audio_check(final):
    samples = authored.command(["ffmpeg", "-nostdin", "-v", "error", "-i", str(final / "tour.mp4"),
                               "-vn", "-ac", "1", "-ar", "48000", "-f", "f32le", "-"], binary=True)
    samples = np.frombuffer(samples, dtype="<f4")
    energy = lambda a,b: float(np.sqrt(np.mean(samples[int(a*48000):int(b*48000)]**2)))
    assert energy(3,4) > .01 and energy(0,.5) < .001 and energy(18,19) < .001
    return {"fixture": "synthetic 440 Hz tone added to dummy footage", "policy": "keep",
        "intro_rms": energy(0,.5), "footage_rms": energy(3,4), "outro_rms": energy(18,19), "listening": "not a subjective listening verdict"}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project", required=True)
    parser.add_argument("--final", required=True)
    parser.add_argument("--out", required=True)
    parser.add_argument("--supplied-audio")
    parser.add_argument("--audio-final")
    args = parser.parse_args()
    audit(Path(args.project), Path(args.final), Path(args.out))
    if args.supplied_audio:
        supplied_audio(Path(args.project), Path(args.supplied_audio))
    if args.audio_final:
        authored.write(Path(args.out) / "audio-proof.json", audio_check(Path(args.audio_final)))
