"""Card contract tests; optional real offline rendering via CARD_SMOKE_DIR."""

import importlib.util
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
HELPER = ROOT / "profiles/image-creator/skills/image-creator-pipeline/scripts/card.py"
MODULE = importlib.util.spec_from_file_location("card", HELPER)
card = importlib.util.module_from_spec(MODULE)
MODULE.loader.exec_module(card)


class CardTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="card-test-")
        self.addCleanup(self.temp.cleanup)
        self.work = Path(self.temp.name)
        self.spec = {"title": "A clear idea", "destination": "og", "style": "paper"}

    def test_all_destinations(self):
        expected = {"og": (1200, 630), "x-post": (1200, 675), "x-article": (1500, 600),
                    "x-header": (1500, 500), "x-pair": (1050, 1200), "x-carousel": (1080, 1350),
                    "instagram": (1080, 1350), "instagram-square": (1080, 1080),
                    "story": (1080, 1920), "youtube-thumb": (1280, 720),
                    "hero": (1920, 1080), "slide-title": (1920, 1080), "note": (1280, 670)}
        for name, size in expected.items():
            with self.subTest(name=name):
                dims = card.destination({"destination": name})
                self.assertEqual((dims["width"], dims["height"]), size)
        dims = card.destination({"destination": "x-carousel", "tile": "square", "tiles": 4})
        self.assertEqual((dims["master_width"], dims["height"]), (4320, 1080))
        self.assertEqual(card.destination({"destination": "720x480"})["width"], 720)
        self.assertEqual(card.destination({"destination": "x-pair"})["status"], "unverified-candidate")

    def test_invalid_conflicting_controls(self):
        for spec in ({"destination": "../../og"}, {"destination": "0x630"},
                     {"destination": "og", "tile": "square"}, {"destination": "og", "gap": 2},
                     {"destination": "x-pair", "tiles": 3}, {"destination": "x-pair", "tile": "portrait"},
                     {"destination": "x-pair", "tile": "tall"},
                     {"destination": "x-pair", "tile": "tall", "tiles": 3},
                     {"destination": "og", "tile": "tall"},
                     {"destination": "x-carousel", "tile": "tall", "tiles": 2},
                     {"destination": "x-carousel", "tiles": 2}, {"destination": "x-carousel", "tiles": True},
                     {"destination": "x-carousel", "tile": "landscape"}, {"destination": "x-pair", "gap": -1}):
            with self.subTest(spec=spec), self.assertRaises(ValueError):
                card.destination(spec)
        with self.assertRaises(ValueError):
            card.validate({**self.spec, "unknown": "ignored?"}, "create")
        with self.assertRaises(ValueError):
            card.validate({**self.spec, "slug": "../escape"}, "create")
        with self.assertRaises(ValueError):
            card.validate({**self.spec, "tile_titles": "1: misplaced"}, "create")

    def test_titles(self):
        self.assertEqual(card.titles("1: Intro\n2: Detail: exact", 3), {1: "Intro", 2: "Detail: exact"})
        self.assertEqual(card.titles([{"tile": 3, "text": "Next"}], 3), {3: "Next"})
        for value in ("0: no", "4: too far", "1: a\n1: b", [{"tile": 1, "text": ""}], {"2": "ambiguous"}):
            with self.subTest(value=value), self.assertRaises(ValueError):
                card.titles(value, 3)

    def test_json_duplicate_and_path_rejection(self):
        path = self.work / "spec.json"
        path.write_text('{"title":"a","title":"b"}')
        with self.assertRaises(ValueError):
            card.load(path)
        for path in ("https://example.com/a.png", "relative.png", "xc:red"):
            with self.subTest(path=path), self.assertRaises(ValueError):
                card.local(path)

    def test_css_separate_and_bounded(self):
        styles = [card.css_style({"style": name}) for name in ("glass", "flat-minimal", "dark-pro", "gradient-glow", "paper", "soft-3d")]
        self.assertEqual(len(set(styles)), 6)
        path = self.work / "custom.css"
        base = ":root {--surface:#fff4bc;--ink:#232330;--accent:#c83538;}"
        path.write_text(base + ".panel {border:4px solid var(--ink);}")
        self.assertIn("4px", card.css_style({"style": "Printed yellow poster", "style_css": str(path)}))
        for css in (base + '.stage{background:url(https://example.com/x)}',
                    base + 'h1{display:none}', base + 'h1{color:red!important}',
                    base + '@import "x";', base + 'h1{color:r\\65 d}', 'h1{color:red}'):
            path.write_text(css)
            with self.subTest(css=css), self.assertRaises(ValueError):
                card.css_style({"style": "Custom", "style_css": str(path)})
        with self.assertRaises(ValueError):
            card.css_style({"style": "glass", "style_css": str(path)})
        with self.assertRaises(ValueError):
            card.css_style({"style": "unknown"})

    def test_escaping_and_separate_tile_text(self):
        # A small stand-in font keeps this pure markup test portable/offline.
        font = self.work / "font.ttf"
        font.write_bytes(b"test font")
        spec = {**self.spec, "destination": "x-carousel", "font": str(font),
                "title": '<script>" & test</script>', "brand": "Brand", "meta": "Meta",
                "tile_titles": "1: Overview\n2: Detail\n3: Next"}
        page = card.page(spec, card.validate(spec, "create"))
        self.assertNotIn('<script>', page)
        self.assertIn('&lt;script&gt;&quot; &amp; test&lt;/script&gt;', page)
        self.assertEqual(page.count('data-copy>Brand'), 1)
        self.assertEqual(page.count('data-copy>Meta'), 1)
        self.assertEqual(page.count('data-copy>Detail'), 1)
        self.assertIn("default-src 'none'", page)

    def test_clobber_existing_and_symlink(self):
        font = self.work / "font.ttf"
        font.write_bytes(b"fake font")
        spec = {**self.spec, "font": str(font)}
        out = self.work / "existing"
        out.mkdir()
        sentinel = out / "keep"
        sentinel.write_text("untouched")
        with self.assertRaises(FileExistsError), patch.object(card, "snapshot") as render:
            card.create(spec, out)
        render.assert_not_called()
        alias = self.work / "alias"
        alias.symlink_to(out, target_is_directory=True)
        with self.assertRaises(FileExistsError):
            card.create(spec, alias)
        self.assertEqual(sentinel.read_text(), "untouched")

    def test_analysis_order_and_conflicts(self):
        files = []
        for n in range(3):
            path = self.work / f"tile-{n}.png"
            card.command(["magick", "-size", "1080x1080", "xc:#334455", path])
            files.append(str(path))
        spec = {"destination": "x-carousel", "tile": "square", "files": files[::-1], "input_kind": "tiles"}
        report = card.analyze(spec)
        self.assertEqual([r["file"] for r in report["ordered_measurements"]], files[::-1])
        self.assertTrue(all(r["dimensions_match"] for r in report["ordered_measurements"]))
        self.assertEqual(report["visual_checks"]["text"], "unverified")
        with self.assertRaises(ValueError):
            card.analyze({**spec, "files": files[:2]})
        with self.assertRaises(ValueError):
            card.analyze({**spec, "input_kind": "single"})
        panorama = card.analyze({**spec, "files": files[:1], "input_kind": "panorama"})
        self.assertFalse(panorama["ordered_measurements"][0]["dimensions_match"])

    def test_exact_reassembly_and_gap(self):
        dims = card.destination({"destination": "x-pair", "gap": 7})
        card.command(["magick", "-size", "2100x1200", "gradient:#193355-#ddbbaa", self.work / "master.png"])
        report = card.finish(self.work, dims)
        self.assertTrue(report["reassembly_rgba_equal"])
        self.assertEqual(card.image_info(self.work / "simulated-gap.png")["width"], 2107)

    def test_carousel_geometry_reassembly_and_display_scale(self):
        for tile, height in (("portrait", 1350), ("square", 1080), ("tall", 2160)):
            for count in (3, 4):
                with self.subTest(tile=tile, count=count):
                    spec = {"destination": "x-carousel", "tile": tile, "tiles": count, "gap": 23}
                    dims = card.destination(spec)
                    self.assertEqual((dims["width"], dims["height"], dims["master_width"]),
                                     (1080, height, 1080 * count))
                    out = self.work / f"{tile}-{count}"
                    out.mkdir()
                    card.command(["magick", "-size", f"{1080*count}x{height}",
                                  "gradient:#193355-#ddbbaa", "-rotate", "180", out / "master.png"])
                    report = card.finish(out, dims)
                    self.assertTrue(report["reassembly_rgba_equal"])
                    pixels = card.command(["magick", *[out / f for f in report["ordered_tiles"]],
                                           "+append", "-depth", "8", "rgba:-"])
                    self.assertEqual(pixels, card.command(["magick", out / "master.png", "-depth", "8", "rgba:-"]))
                    for name in report["ordered_tiles"]:
                        info = card.image_info(out / name)
                        self.assertEqual((info["width"], info["height"]), (1080, height))
                    preview = card.image_info(out / "simulated-display.png")
                    self.assertEqual((preview["width"], preview["height"]),
                                     (360 * count + 6 * (count - 1), height // 3))
                    label = card.load(out / "simulated-display.json")
                    self.assertEqual(label["image_width_css_px"], 360)
                    self.assertEqual(label["effective_image_gap_css_px"], 6)
                    self.assertEqual(label["raster_pixels_per_css_px"], 1)
                    self.assertIn("LOCAL SIMULATION", label["label"])
                    # Check every gap pixel and each image placement, not just total width.
                    for i, name in enumerate(report["ordered_tiles"]):
                        crop = card.command(["magick", out / "simulated-display.png", "-crop",
                                             f"360x{height//3}+{i*366}+0", "+repage", "-depth", "8", "rgba:-"])
                        resized = card.command(["magick", out / name, "-resize", f"360x{height//3}!",
                                                "-depth", "8", "rgba:-"])
                        self.assertEqual(crop, resized)
                        if i < count - 1:
                            gap = card.command(["magick", out / "simulated-display.png", "-crop",
                                                f"6x{height//3}+{i*366+360}+0", "+repage", "-depth", "8", "rgba:-"])
                            self.assertEqual(gap, bytes((119, 119, 119, 255)) * 6 * (height // 3))
                    self.assertEqual(card.image_info(out / "simulated-gap.png")["width"],
                                     1080 * count + 23 * (count - 1))
                    measured = card.analyze({**spec, "input_kind": "panorama", "files": [str(out / "master.png")]})
                    self.assertTrue(measured["ordered_measurements"][0]["dimensions_match"])
        self.assertEqual(card.destination({"destination": "x-carousel"})["gap"], 16)
        self.assertNotIn("display_width_css_px", card.destination({"destination": "x-pair"}))

    def test_protected_edits_and_clobber(self):
        source = self.work / 'source [special] " quote.png'
        card.command(["magick", "-size", "800x400", "xc:#234567", source])
        spec = {"source": str(source), "destination": "400x400", "fit": "cover", "protected": [[0, 0, 100, 100]]}
        with self.assertRaisesRegex(ValueError, "destructive"):
            card.edit(spec, self.work / "unsafe")
        self.assertFalse((self.work / "unsafe").exists())
        report = card.edit({**spec, "fit": "contain"}, self.work / "safe")
        self.assertEqual(report["master"]["width"], 400)
        with self.assertRaises(FileExistsError):
            card.edit({**spec, "fit": "contain"}, self.work / "safe")
        with self.assertRaises(ValueError):
            card.edit({**spec, "fit": "pad"}, self.work / "pad")
        with self.assertRaises(ValueError):
            card.edit({**spec, "fit": "focus"}, self.work / "focus")
        report = card.edit({**spec, "fit": "focus", "focus": [0, .5]}, self.work / "focus-safe")
        self.assertEqual(report["crop_scaled_xy"], [0, 0])

    def test_browser_isolation_and_failure_cleanup(self):
        calls = []

        def fake_command(argv, **kwargs):
            calls.append((argv, kwargs))
            data = {"result": {"ok": False, "checks": []}} if "eval" in argv else {}
            return json.dumps({"success": True, "data": data}).encode()

        bad_environment = {"AGENT_BROWSER_CDP": "shared", "AGENT_BROWSER_PROFILE": "real",
                           "AGENT_BROWSER_PLUGINS": "untrusted", "HTTP_PROXY": "unexpected"}
        with patch.dict(os.environ, bad_environment), patch.object(card, "command", fake_command):
            with self.assertRaisesRegex(ValueError, "overflow"):
                card.snapshot(self.work / "card.html", self.work, card.destination(self.spec))
        self.assertEqual(calls[-1][0][-1], "close")
        sessions = {argv[argv.index("--session") + 1] for argv, _ in calls}
        self.assertEqual(len(sessions), 1)
        self.assertTrue(any(argv[-3:] == ["set", "offline", "on"] for argv, _ in calls))
        for argv, options in calls:
            self.assertIn("--namespace", argv)
            self.assertFalse(set(bad_environment) & options["env"].keys())
            self.assertNotIn("--cdp", argv)
        self.assertFalse((self.work / "master.png").exists())

    def test_card_routing_and_generation_contracts(self):
        # Static contracts, NOT a live LLM handoff or provider-call test.
        for verb in ("create", "generate", "edit", "analyze"):
            name = verb + "-card"
            leaf = card.ROOT / verb / "card/SKILL.md"
            body = leaf.read_text()
            self.assertIn("name: " + name, body)
            for tag in ("<Procedure>", "<QA>", "<Report>"):
                self.assertIn(tag, body)
        generated = (card.ROOT / "generate/card/SKILL.md").read_text()
        for phrase in ("explicit budget approval", "current work conversation", "BEFORE calling",
                       "never reset spent calls", "3 variant", "1 corrective", "No hardcoded 21:9"):
            self.assertIn(phrase, generated)
        for reference in (card.ROOT / "generate/card/references/styles").glob("*.md"):
            self.assertNotIn("```css", reference.read_text())
        self.assertTrue((ROOT / "profiles/creator/skills/technic/creator-text-card/SKILL.md").is_file())


@unittest.skipUnless(os.environ.get("CARD_SMOKE_DIR"), "set CARD_SMOKE_DIR to a NEW directory for real browser smoke")
class CardRenderSmoke(unittest.TestCase):
    def test_render_matrix(self):
        out = Path(os.environ["CARD_SMOKE_DIR"])
        out.mkdir(exist_ok=False)
        copy = {"title": "\u8003\u3048\u3092\u3001\u4f1d\u308f\u308b\u5f62\u306b\u3002",
                "subtitle": "\u8a00\u8449\u3068\u4f59\u767d\u3067\u3064\u304f\u308b\u3001\u6b21\u306e\u4e00\u679a\u3002",
                "brand": "FORM / STUDIO", "meta": "DESIGN NOTES 01", "label": "A CLEAR IDEA"}
        cases = [("og", {"destination": "og", "style": "glass"}),
                 ("carousel-portrait", {"destination": "x-carousel", "style": "paper", "tile_titles": "1: Overview\n2: A closer look\n3: Your next step"}),
                 ("carousel-square", {"destination": "x-carousel", "style": "flat-minimal", "tile": "square", "tile_titles": "2: Details\n3: Next step"}),
                 ("carousel-tall", {"destination": "x-carousel", "style": "paper", "tile": "tall",
                                    "tile_titles": "1: \u8003\u3048\u3092\u6574\u3048\u308b\n2: \u8a00\u8449\u3092\u9078\u3076\n3: \u6b21\u306e\u4e00\u6b69\u3078"}),
                 ("pair-candidate", {"destination": "x-pair", "style": "dark-pro", "tile_titles": "2: A connected idea"}),
                 ("story", {"destination": "story", "style": "soft-3d"}),
                 ("custom-size", {"destination": "840x560", "style": "gradient-glow"})]
        for name, spec in cases:
            with self.subTest(name=name):
                result = card.create({**copy, **spec}, out / name)
                self.assertTrue(result["reassembly_rgba_equal"])
        # All six styles at the same canvas/copy must differ in actual pixels.
        hashes = set()
        for style in ("glass", "flat-minimal", "dark-pro", "gradient-glow", "paper", "soft-3d"):
            result = card.create({**copy, "destination": "og", "style": style}, out / ("style-" + style))
            hashes.add(result["master"]["sha256"])
        self.assertEqual(len(hashes), 6)
        # Same input/environment, fresh output: stable decoded pixels.
        self.assertEqual(card.command(["magick", out / "og/master.png", "rgba:-"]),
                         card.command(["magick", out / "style-glass/master.png", "rgba:-"]))
        custom = out / "custom.css"
        custom.write_text(":root{--surface:#fff4bc;--ink:#232330;--accent:#c83538;} .stage{background:var(--surface);} .panel{border:4px solid var(--ink);box-shadow:12px 12px 0 var(--accent);}")
        card.create({**copy, "destination": "og", "style": "Printed yellow poster", "style_css": str(custom)}, out / "custom-style")
        # Mock generated backdrop finishing: local gradient, zero provider calls.
        backdrop = out / 'background [approved] "local".png'
        card.command(["magick", "-size", "1600x900", "gradient:#204060-#381d52", backdrop])
        card.create({**copy, "destination": "og", "style": "glass", "background": str(backdrop)}, out / "offline-backdrop")
        card.edit({"source": str(backdrop), "destination": "og", "fit": "contain", "title": copy["title"], "text_band": 150}, out / "text-band")
        with self.assertRaisesRegex(ValueError, "overflow"):
            card.create({"title": "Overflow " * 700, "destination": "320x180", "style": "paper"}, out / "overflow-rejected")
        self.assertFalse((out / "overflow-rejected/manifest.json").exists())
        spec = {"destination": "x-carousel", "input_kind": "panorama", "files": [str(out / "carousel-portrait/master.png")]}
        measurements = card.analyze(spec)
        self.assertTrue(measurements["ordered_measurements"][0]["dimensions_match"])
        (out / "analysis.json").write_text(json.dumps(measurements, indent=2))


if __name__ == "__main__":
    unittest.main()
