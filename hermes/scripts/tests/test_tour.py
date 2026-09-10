"""Local synthetic tour tests, including an opt-in actual Chrome/MP4 render.

TOUR_RENDER_TEST=1 enables rendering tests, whose evidence is retained.
Ordinary fixtures are cleaned up. TOUR_TEST_ROOT overrides the system temp directory.
No real product, model, gateway, upload or two-client handoff is exercised.
"""

from __future__ import annotations

import array
import hashlib
import importlib.util
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
import wave
from pathlib import Path
from unittest.mock import patch

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "profiles/video-creator/skills/video-creator-pipeline/create/tour/scripts/tour.py"
spec = importlib.util.spec_from_file_location("tour", SCRIPT)
tour = importlib.util.module_from_spec(spec)
spec.loader.exec_module(tour)
TEMP = Path(os.environ.get("TOUR_TEST_ROOT", tempfile.gettempdir())).resolve()


def run(*args):
    return subprocess.run([sys.executable, str(SCRIPT), *map(str, args)],
                          capture_output=True, text=True, timeout=1800)


def save(path, value):
    path.write_text(json.dumps(value), encoding="utf-8")


def fixture(root, portrait=False):
    size = (480, 800) if portrait else (960, 600)
    font = ImageFont.truetype("/System/Library/Fonts/Supplemental/Arial.ttf", 28)
    for name, done in (("screen", False), ("done", True)):
        im = Image.new("RGB", size, "#edf2f7")
        draw = ImageDraw.Draw(im)
        draw.rectangle((0, 0, size[0], 65), fill="#13263d")
        draw.text((24, 18), "SYNTHETIC SETTINGS", fill="white", font=font)
        draw.text((40, 110), "Name", fill="#13263d", font=font)
        draw.rectangle((40, 160, 400, 215), fill="white", outline="#375782", width=2)
        draw.text((52, 170), "Example" if done else "", fill="#13263d", font=font)
        draw.rounded_rectangle((40, 270, 230, 330), radius=8, fill="#265ee8")
        draw.text((65, 281), "Saved" if done else "Save", fill="white", font=font)
        im.save(root / f"{name}.png")
    Image.new("RGB", (700, 300), "#b5caff").save(root / "backdrop.png")
    steps = {"steps": [
        {"id": "name", "image": str(root / "screen.png"), "target": [40, 160, 360, 55],
         "action": "type", "typed": "Example", "label": "Enter a name", "duration": 2.5},
        {"id": "save", "image": str(root / "screen.png"), "target": [40, 270, 190, 60],
         "action": "click", "label": "Save settings", "duration": 2},
        {"id": "done", "role": "done", "image": str(root / "done.png"),
         "label": "Settings saved", "duration": 2},
    ]}
    form = {"task": "Save a profile", "app": "Synthetic App", "steps": str(root / "steps.json"),
            "style": "glass", "frame": "ios" if portrait else "browser", "background": "light",
            "backdrop": str(root / "backdrop.png"), "destination": "portrait" if portrait else "landscape"}
    save(root / "steps.json", steps)
    save(root / "form.json", form)
    return form, steps


class TourTest(unittest.TestCase):
    def setUp(self):
        self.root = Path(tempfile.mkdtemp(prefix="create-tour-test-", dir=TEMP))
        self.retain_evidence = False
        self.addCleanup(lambda: None if self.retain_evidence else shutil.rmtree(self.root))
        self.form, self.manifest = fixture(self.root)

    def scaffold(self, name="project"):
        save(self.root / "form.json", self.form)
        save(self.root / "steps.json", self.manifest)
        return run("scaffold", "--form", self.root / "form.json", "--project", self.root / name)

    def success(self, proc):
        self.assertEqual(proc.returncode, 0, proc.stderr + proc.stdout)

    def assert_timeline_ran(self, root):
        preview = json.loads((root / "preview/preview.json").read_text())
        goal, step = list(preview["frames"])[:2]
        evidence = {}
        for kind, paths in (("preview", (Path(goal), Path(step))),
                            ("mp4", (root / "final/review/goal-proof.png", root / "final/review/name.png"))):
            if kind == "mp4":
                tour.command(["ffmpeg", "-nostdin", "-v", "error", "-n", "-ss", "0.75",
                              "-i", str(root / "final/tour_tour.mp4"), "-frames:v", "1", str(paths[0])])
            records = []
            for path in paths:
                with Image.open(path) as im:
                    pixels = hashlib.sha256(im.convert("RGB").tobytes()).hexdigest()
                records.append({"path": str(path), "sha256": tour.digest(path), "rgb_sha256": pixels})
            # Goal versus first step proves advancement; duplicate step states are valid.
            self.assertNotEqual(records[0]["rgb_sha256"], records[1]["rgb_sha256"])
            evidence[kind] = dict(zip(("goal", "step"), records))
        save(root / "timeline-evidence.json", evidence)

    def test_ordinary_fixture_cleanup(self):
        case = TourTest("test_scaffold_sources_backdrop_and_repeated_clicks")
        case.setUp()
        root = case.root
        self.assertTrue(root.is_dir())
        case.doCleanups()
        self.assertFalse(root.exists())

    def test_synchronous_timeline_registration(self):
        self.success(self.scaffold())
        code = (self.root / "project/index.html").read_text()
        self.assertIn('data-composition-id="tour" data-start="0"', code)
        seed = code.index("window.__timelines ||= {};")
        build = code.index("const tl=gsap.timeline({paused:true});")
        registration = code.index('window.__timelines["tour"]=tl;')
        ready = code.index("document.fonts.ready.then")
        self.assertTrue(seed < build < registration < ready)
        self.assertNotIn("tl.", code[ready:])
        self.assertIn("Tour text exceeds rendering bounds", code[ready:])

    def test_scaffold_sources_backdrop_and_repeated_clicks(self):
        self.manifest["steps"][0].pop("typed")
        self.manifest["steps"][0]["action"] = "click"
        before = (self.root / "screen.png").read_bytes()
        self.success(self.scaffold())
        p = self.root / "project"
        self.assertEqual(before, (self.root / "screen.png").read_bytes())
        self.assertEqual(before, (p / "sources/screen-name.png").read_bytes())
        self.assertIn("object-fit:cover", (p / "index.html").read_text())
        self.assertIn("blur(16px)", (p / "index.html").read_text())
        self.assertFalse(any(p.glob("*.mp4")))
        self.assertEqual(9, json.loads((p / "tour.json").read_text())["total"])
        self.assertNotEqual(self.scaffold().returncode, 0)

    def test_typing_survives_same_screenshot_and_asset_names_do_not_collide(self):
        self.manifest["steps"][0]["id"] = "backdrop"
        self.success(self.scaffold())
        code = (self.root / "project/index.html").read_text()
        self.assertIn('assets/screen-backdrop.png', code)
        self.assertIn('assets/backdrop.png', code)
        save_screen = code.split('id="screen-save"')[1].split('id="label-save"')[0]
        self.assertIn('>Example</div>', save_screen)

    def test_background_color_without_backdrop_is_not_dimmed(self):
        self.form.pop("backdrop")
        for color, ink in (("light", "black"), ("dark", "white"), ("#ffcc00", "black")):
            self.form["background"] = color
            self.success(self.scaffold(ink + color.replace("#", "")))
            code = (self.root / (ink + color.replace("#", "")) / "index.html").read_text()
            self.assertIn("background:rgba(0,0,0,0)", code)
            self.assertIn(f"color:{ink};font-size:24px", code)

    def test_duplicate_json_keys_and_ids(self):
        (self.root / "form.json").write_text('{"task":"one","task":"two"}')
        self.assertIn("duplicate JSON key", run("scaffold", "--form", self.root / "form.json", "--project", self.root / "project").stderr)
        self.manifest["steps"][1]["id"] = "name"
        self.assertIn("duplicate step id", self.scaffold().stderr)

    def test_source_output_and_existing_preview_preserved(self):
        proc = run("scaffold", "--form", self.root / "form.json", "--project", self.root)
        self.assertNotEqual(proc.returncode, 0)
        self.success(self.scaffold())
        original = (self.root / "screen.png").read_bytes()
        self.assertNotEqual(run("snapshot", "--project", self.root / "project", "--out", self.root / "screen.png").returncode, 0)
        self.assertEqual(original, (self.root / "screen.png").read_bytes())

    def test_routing_contract(self):
        import yaml
        video = yaml.safe_load((ROOT / "profiles/video-creator/config.yaml").read_text())
        self.assertNotIn("tts", video["toolsets"])
        for path in ("references/build/video-creator/tour.md", "references/plan/video-creator/tour.md",
                     "references/capabilities.md"):
            contents = (ROOT / "profiles/creator/skills/creator-pipeline" / path).read_text()
            self.assertIn("create-tour", contents)
            self.assertIn('kind="work"', contents)
        self.assertTrue((ROOT / "profiles/creator/skills/technic/creator-html-motion/SKILL.md").is_file())

    def test_form_and_manifest_boundaries(self):
        for field, value in (("style", "bad"), ("accent", "red;"), ("frame", "card"),
                             ("slug", "../escape"), ("slug", "X"), ("task", ""),
                             ("preview", True), ("destination", "square"),
                             ("max_zoom", True), ("max_zoom", 0.99), ("max_zoom", 2.01),
                             ("max_zoom", float("nan"))):
            with self.subTest(field=field):
                original = self.form.copy()
                self.form[field] = value
                self.assertNotEqual(self.scaffold().returncode, 0)
                self.assertFalse((self.root / "project").exists())
                self.form = original
        self.manifest["task"] = "duplicate"
        self.assertNotEqual(self.scaffold().returncode, 0)

    def test_nonfinite_and_target_bounds(self):
        for rect in ([0, 0, 0, 1], [-1, 0, 1, 1], [950, 0, 20, 20],
                     [0, 0, float("nan"), 20], [0, True, 20, 20], [1, 2, 3]):
            with self.subTest(rect=rect):
                self.manifest["steps"][0]["target"] = rect
                self.assertNotEqual(self.scaffold().returncode, 0)
        self.manifest["steps"][0]["target"] = [0, 0, 20, 20]
        for duration in (float("inf"), -1, 0, 61, True):
            self.manifest["steps"][0]["duration"] = duration
            self.assertNotEqual(self.scaffold().returncode, 0)

    def test_steps_and_render_duration_bounds(self):
        self.manifest["steps"][-1]["role"] = "step"
        self.assertNotEqual(self.scaffold().returncode, 0)
        self.manifest["steps"][-1]["role"] = "done"
        self.manifest["steps"][0]["duration"] = 58
        self.assertNotEqual(self.scaffold().returncode, 0)
        self.manifest["steps"] *= 6
        self.assertNotEqual(self.scaffold().returncode, 0)

    def test_path_validation(self):
        for path in ("https://example.com/a.png", "relative.png", str(self.root / "missing.png"), "/dev/zero"):
            self.manifest["steps"][0]["image"] = path
            self.assertNotEqual(self.scaffold().returncode, 0)
        link = self.root / "linked.png"
        link.symlink_to(self.root / "screen.png")
        self.manifest["steps"][0]["image"] = str(link)
        self.assertNotEqual(self.scaffold().returncode, 0)

    def test_image_format_pixels_and_mismatched_screens(self):
        p = self.root / "bad.png"
        p.write_text("<svg onload='alert(1)'/>")
        self.manifest["steps"][0]["image"] = str(p)
        self.assertNotEqual(self.scaffold().returncode, 0)
        Image.new("RGB", (8193, 32)).save(p)
        self.assertNotEqual(self.scaffold().returncode, 0)
        Image.new("RGB", (500, 500)).save(p)
        self.assertNotEqual(self.scaffold().returncode, 0)

    def test_html_and_js_escaping(self):
        payload = '</script><img src=x onerror="bad()">&'
        self.form["task"] = payload
        self.form["app"] = payload
        self.manifest["steps"][0]["label"] = payload
        self.manifest["steps"][0]["typed"] = payload
        self.manifest["steps"][0]["duration"] = 5
        self.success(self.scaffold())
        code = (self.root / "project/index.html").read_text()
        self.assertNotIn(payload, code)
        self.assertIn("&lt;/script&gt;", code)
        self.assertIn("\\u003c/script\\u003e", code)

    def test_frame_variants_and_geometry(self):
        for frame in tour.FRAMES:
            self.form["frame"] = frame
            self.success(self.scaffold(frame))
            model = json.loads((self.root / frame / "tour.json").read_text())
            self.assertEqual("browser" if frame == "auto" else frame, model["frame"])
            for s in model["steps"][:-1]:
                g = s["geometry"]
                x, y, w, h = g["target_root"]
                cx, cy = g["cursor"]
                self.assertTrue(x <= cx <= x+w and y <= cy <= y+h)
                self.assertTrue(0 <= x < x+w <= model["width"])
                self.assertTrue(0 <= y < y+h <= model["height"])
            if frame in ("ios", "android"):
                self.assertNotIn('tl.to("#cursor"', (self.root / frame / "index.html").read_text())

    def test_zoom_cap_and_goal_done_presentation(self):
        self.form["max_zoom"] = 1.02
        self.success(self.scaffold())
        model = json.loads((self.root / "project/tour.json").read_text())
        self.assertEqual(2.5, model["steps"][0]["start"])
        code = (self.root / "project/index.html").read_text()
        self.assertIn('id="goal-support">Synthetic App</div>', code)
        self.assertIn('tl.set("#goal",{opacity:0},2.5)', code)
        self.assertIn('id="label-done" class="label">Settings saved</div>', code)
        for raw, step in zip(self.manifest["steps"][:-1], model["steps"][:-1]):
            self.assertEqual(raw["target"], step["target"])
            geo = step["geometry"]
            self.assertLessEqual(geo["punch"][0], 1.02)
            x, y, w, h = geo["target_root"]
            self.assertAlmostEqual(x+w/2, geo["cursor"][0])
            self.assertAlmostEqual(y+h/2, geo["cursor"][1])
        geo = tour.geometry(960, 600, 1280, 720, "none", [40, 270, 190, 60], 1)
        self.assertEqual([1, 0, 0], geo["punch"])

    def test_ocr_unique_ambiguous_missing_and_language(self):
        header = "level\tpage_num\tblock_num\tpar_num\tline_num\tword_num\tleft\ttop\twidth\theight\tconf\ttext\n"
        row = "5\t1\t1\t1\t1\t1\t20\t30\t50\t20\t95\tSave\n"
        self.assertEqual([[20, 30, 50, 20]], tour.ocr_candidates(header+row, "Save")[0])
        self.assertEqual(2, len(tour.ocr_candidates(header+row+row.replace("\t1\t1\t20", "\t2\t1\t20"), "Save")[0]))
        with patch.object(tour.shutil, "which", return_value="tesseract"):
            with patch.object(tour, "command", return_value="eng\n"):
                with self.assertRaisesRegex(ValueError, "language missing"):
                    tour.resolve_target({"text": "Save", "language": "jpn"}, self.root / "screen.png", 960, 600)
            for tsv in (header, header+row+row):
                with patch.object(tour, "command", side_effect=["eng\n", tsv]):
                    with self.assertRaisesRegex(ValueError, "candidates="):
                        tour.resolve_target({"text": "Save"}, self.root / "screen.png", 960, 600)

    def test_ocr_literal_quote_and_missing_text_column(self):
        header = "level\tpage_num\tblock_num\tpar_num\tline_num\tword_num\tleft\ttop\twidth\theight\tconf\ttext\n"
        quote = '5\t1\t1\t1\t1\t1\t20\t30\t8\t20\t95\t"\n'
        malformed = "5\t1\t1\t1\t2\t1\t20\t60\t50\t20\t95\n"
        save_row = "5\t1\t1\t1\t3\t1\t20\t90\t50\t20\t95\tSave\n"
        tsv = header + quote + malformed + save_row
        self.assertEqual(([[20, 30, 8, 20]], ['"', "Save"]), tour.ocr_candidates(tsv, '"'))
        self.assertEqual([[20, 90, 50, 20]], tour.ocr_candidates(tsv, "Save")[0])

    @unittest.skipUnless(shutil.which("tesseract"), "tesseract missing")
    def test_real_english_ocr(self):
        rect, evidence = tour.resolve_target({"text": "Save"}, self.root / "screen.png", 960, 600)
        self.assertTrue(40 <= rect[0] < 230)
        self.assertIn("Save", evidence)

    def test_integrity_rejects_runtime_edits(self):
        self.success(self.scaffold())
        with (self.root / "project/index.html").open("a") as f:
            f.write("changed")
        proc = run("render", "--project", self.root / "project", "--out", self.root / "final")
        self.assertIn("project changed", proc.stderr)
        self.assertFalse((self.root / "final").exists())

    def test_render_bounds_are_rechecked_and_frozen_sources_survive(self):
        self.success(self.scaffold())
        (self.root / "screen.png").rename(self.root / "original-retained.png")
        tour.project_model(str(self.root / "project"))
        model_path = self.root / "project/tour.json"
        model = json.loads(model_path.read_text())
        model["total"] = 61
        save(model_path, model)
        integrity_path = self.root / "project/integrity.json"
        integrity = json.loads(integrity_path.read_text())
        integrity["tour.json"] = tour.digest(model_path)
        save(integrity_path, integrity)
        with self.assertRaisesRegex(ValueError, "render duration"):
            tour.project_model(str(self.root / "project"))

    @unittest.skipUnless(shutil.which("ffmpeg"), "ffmpeg missing")
    def test_current_narration_sidecar(self):
        wav = self.root / "speech_test.wav"
        subprocess.run(["ffmpeg", "-v", "error", "-f", "lavfi", "-i", "sine=frequency=440:duration=1",
                        "-ar", "48000", "-ac", "1", "-c:a", "pcm_s16le", str(wav)], check=True)
        pcm = tour.command(["ffmpeg", "-v", "error", "-i", str(wav), "-f", "s16le", "-"], binary=True)
        data = {"file": wav.name, "duration": 1, "pcm_sha256": hashlib.sha256(pcm).hexdigest(),
                "words": [{"word": "Test", "start": 0, "end": 1}],
                "captions": [{"text": "Test", "start": 0, "end": 1}]}
        side = wav.with_suffix(".words.json")
        save(side, data)
        self.assertEqual(1, tour.narration(wav)[0])
        self.manifest["steps"][0].pop("duration")
        self.manifest["steps"][0]["track"] = str(wav)
        self.success(self.scaffold())
        for field, value in (("duration", 5), ("pcm_sha256", "0"*64), ("file", "other.wav"),
                             ("captions", [{"text": "x", "start": 0, "end": float("nan") }])):
            changed = {**data, field: value}
            save(side, changed)
            with self.assertRaises(ValueError):
                tour.narration(wav)

    def test_renamed_playlist_is_not_opened_by_ffmpeg(self):
        p = self.root / "remote.wav"
        p.write_text("#EXTM3U\nhttps://example.com/track.ts\n")
        with patch.object(tour, "command") as cmd:
            with self.assertRaises(wave.Error):
                tour.narration(p)
            cmd.assert_not_called()

    @unittest.skipUnless(os.environ.get("TOUR_RENDER_TEST") == "1", "set TOUR_RENDER_TEST=1 for real render")
    def test_actual_preview_render_lifecycle(self):
        self.retain_evidence = True
        for portrait in (False, True):
            root = self.root / ("mobile" if portrait else "desktop")
            root.mkdir()
            fixture(root, portrait)
            self.success(run("scaffold", "--form", root / "form.json", "--project", root / "project"))
            self.success(run("snapshot", "--project", root / "project", "--out", root / "preview"))
            preview = json.loads((root / "preview/preview.json").read_text())
            self.assertEqual(4, len(preview["frames"]))
            proc = run("render", "--project", root / "project", "--out", root / "final")
            self.assertNotEqual(proc.returncode, 0)
            self.assertFalse((root / "final").exists())
            self.success(run("render", "--project", root / "project", "--approved-preview", root / "preview", "--out", root / "final"))
            qa = json.loads((root / "final/qa.json").read_text())
            self.assertTrue(qa["decoded"])
            self.assertGreater(qa["bytes"], 1000)
            self.assertFalse(qa["audio"])
            self.assertEqual(9, qa["duration"])
            self.assertGreater(qa["contrast"]["checked"], 0)
            self.assertEqual(qa["contrast"]["passed"], qa["contrast"]["checked"])
            self.assert_timeline_ran(root)
            self.assertNotEqual(run("render", "--project", root / "project", "--approved-preview", root / "preview", "--out", root / "final").returncode, 0)
            self.assertNotEqual(run("snapshot", "--project", root / "project", "--out", root / "preview").returncode, 0)
            print(f"Synthetic tour evidence: {root}")

    @unittest.skipUnless(os.environ.get("TOUR_RENDER_TEST") == "1", "set TOUR_RENDER_TEST=1 for real render")
    def test_actual_narrated_render_without_preview_gate(self):
        self.retain_evidence = True
        self.form["preview"] = "no"
        self.form["style"] = "outline"
        self.form["frame"] = "macos"
        self.form.pop("backdrop")
        wav = self.root / "speech_test.wav"
        subprocess.run(["ffmpeg", "-v", "error", "-f", "lavfi", "-i", "sine=frequency=440:duration=1",
                        "-ar", "48000", "-ac", "1", "-c:a", "pcm_s16le", str(wav)], check=True)
        pcm = tour.command(["ffmpeg", "-v", "error", "-i", str(wav), "-f", "s16le", "-"], binary=True)
        save(wav.with_suffix(".words.json"), {"file": wav.name, "duration": 1,
             "pcm_sha256": hashlib.sha256(pcm).hexdigest(), "words": [{"word": "Synthetic", "start": 0, "end": 1}],
             "captions": [{"text": "Synthetic", "start": 0, "end": 1}]})
        self.manifest["steps"][0].pop("duration")
        self.manifest["steps"][0]["track"] = str(wav)
        self.success(self.scaffold())
        self.success(run("snapshot", "--project", self.root / "project", "--out", self.root / "preview"))
        self.success(run("render", "--project", self.root / "project", "--out", self.root / "final"))
        self.assert_timeline_ran(self.root)
        qa = json.loads((self.root / "final/qa.json").read_text())
        self.assertTrue(qa["audio"])
        self.assertIn("00:00:02,800 --> 00:00:03,800", (self.root / "final/tour.srt").read_text())
        decoded = tour.command(["ffmpeg", "-v", "error", "-i", str(self.root / "final/tour_tour.mp4"),
                                "-ac", "1", "-ar", "48000", "-f", "s16le", "-"], binary=True)
        samples = array.array("h", decoded)
        levels = {}
        for name, start, end in (("before", 0, 2.5), ("during", 2.9, 3.5), ("after", 4.2, 5)):
            window = samples[round(start*48000):round(end*48000)]
            levels[name] = sum(abs(v) for v in window) / len(window)
        self.assertLess(levels["before"], 2)
        self.assertGreater(levels["during"], 100)
        self.assertLess(levels["after"], 2)
        save(self.root / "synthetic-audio-placement.json", levels)
        print(f"Synthetic narrated tour evidence: {self.root}")

    @unittest.skipUnless(os.environ.get("TOUR_RENDER_TEST") == "1", "set TOUR_RENDER_TEST=1 for real render")
    def test_other_frames_preview_tampering_and_rendered_text_bounds(self):
        self.retain_evidence = True
        for frame in ("android", "none"):
            root = self.root / frame
            root.mkdir()
            form, steps = fixture(root, portrait=frame == "android")
            form.update(frame=frame, style="flat")
            save(root / "form.json", form)
            self.success(run("scaffold", "--form", root / "form.json", "--project", root / "project"))
            self.success(run("snapshot", "--project", root / "project", "--out", root / "preview"))
            other = run("render", "--project", root / "project", "--approved-preview", self.root / "android/preview", "--out", root / "final") if frame == "none" else None
            if other:
                self.assertIn("another project", other.stderr)
            preview = json.loads((root / "preview/preview.json").read_text())
            first = Path(next(iter(preview["frames"])))
            with first.open("ab") as f:
                f.write(b"test tamper")
            self.assertIn("preview frame changed", run("render", "--project", root / "project", "--approved-preview", root / "preview", "--out", root / "final").stderr)
            self.assertFalse((root / "final").exists())
        self.manifest["steps"][0]["typed"] = "W" * 80
        self.manifest["steps"][0]["duration"] = 8
        self.success(self.scaffold())
        proc = run("snapshot", "--project", self.root / "project", "--out", self.root / "overflow-preview")
        self.assertNotEqual(proc.returncode, 0)
        self.assertIn("Tour text exceeds rendering bounds", (self.root / "overflow-preview/check.json").read_text())


if __name__ == "__main__":
    unittest.main()
