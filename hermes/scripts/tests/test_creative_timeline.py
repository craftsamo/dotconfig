"""Planning artifact checks; not artistic acceptance or live Telegram evidence."""

from copy import deepcopy
import hashlib
from html.parser import HTMLParser
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


HERMES = Path(__file__).resolve().parents[2]
SCRIPT = HERMES / "profiles/assistant/scripts/creative-timeline.py"
DOC = SCRIPT.with_suffix(".md")
LOADER = importlib.util.spec_from_file_location("creative_timeline", SCRIPT)
TIMELINE = importlib.util.module_from_spec(LOADER)
LOADER.loader.exec_module(TIMELINE)


def example():
    return json.loads(DOC.read_text().split("```json\n", 1)[1].split("\n```", 1)[0])


def render(spec):
    raw = json.dumps(spec).encode()
    return TIMELINE.render(spec, hashlib.sha256(raw).hexdigest())


class Tags(HTMLParser):
    def __init__(self):
        super().__init__()
        self.tags = []

    def handle_starttag(self, tag, attrs):
        self.tags.append((tag, dict(attrs)))


class TimelineTest(unittest.TestCase):
    def test_documented_example_renders_deterministically_and_exposes_detail(self):
        spec = TIMELINE.validate(example())
        before = deepcopy(spec)
        document = render(spec)
        self.assertEqual(document, render(spec))
        self.assertEqual(spec, before)
        self.assertIn("Discussion only / unresolved", document)
        self.assertIn("not a rendered preview or approval", document)
        for event in spec["scenes"][0]["events"]:
            for key in ("before", "during", "after", "trigger", "trajectory", "pacing"):
                self.assertIn(TIMELINE.esc(event[key]), document)
        for field in ("anatomy", "typography", "surface", "states"):
            self.assertIn(TIMELINE.esc(spec["components"][0][field]), document)

    def test_gaps_and_missing_middle_are_not_renderable(self):
        mutations = [
            lambda s: s["scenes"][0].update(start=0.1),
            lambda s: s.update(duration=3),
            lambda s: s["scenes"][0]["events"][1].update(start=1.1),
            lambda s: s["scenes"][0]["events"][1].update(end=1.9),
            lambda s: s["scenes"][0]["keyframes"].pop(1),
            lambda s: s["scenes"][0]["keyframes"].pop(),
            lambda s: s["scenes"][0]["absent_lanes"].pop("audio"),
            lambda s: s["scenes"][0]["events"][0].update(lane="camera"),
        ]
        for mutation in mutations:
            spec = example()
            mutation(spec)
            with self.subTest(mutation=mutation), self.assertRaises(ValueError):
                TIMELINE.validate(spec)

    def test_unknown_fields_ids_and_invalid_geometry_fail(self):
        mutations = [
            lambda s: s.update(unknown="must not silently drop"),
            lambda s: s["components"][0].update(reference_ids=["invented"]),
            lambda s: s["scenes"][0]["events"][0].update(component_ids=["invented"]),
            lambda s: s["scenes"][0]["events"][1].update(id="expand"),
            lambda s: s["scenes"][0]["keyframes"][0]["nodes"][0].update(fill="missing"),
            lambda s: s["scenes"][0]["keyframes"][0]["nodes"][0].update(w=300),
            lambda s: s["visual_system"]["palette"].update(paper="red; background:url(https://bad.test)"),
            lambda s: s["scenes"][0]["events"][0].update(during=" "),
            lambda s: s["scenes"][0]["events"][0].update(during="a\x00b"),
        ]
        for mutation in mutations:
            spec = example()
            mutation(spec)
            with self.subTest(mutation=mutation), self.assertRaises(ValueError):
                TIMELINE.validate(spec)

    def test_invalid_numbers(self):
        for value in (True, False, float("nan"), float("inf"), -1, 0, 3601, "2"):
            spec = example()
            spec["duration"] = value
            with self.subTest(value=value), self.assertRaises(ValueError):
                TIMELINE.validate(spec)

    def test_injection_is_inert_and_references_are_navigation_only(self):
        spec = example()
        payload = '</style><script>alert(1)</script><img src="https://bad.test" onerror="run()">'
        spec["title"] = payload
        spec["scenes"][0]["events"][0]["during"] = payload
        spec["scenes"][0]["keyframes"][0]["nodes"][0]["label"] = payload
        spec["sources"] = [{"id": "case", "url": "https://example.org/case?x=%22",
                            "observed": payload, "inspection": "Synthetic, not inspected.",
                            "adopt": "Nothing", "avoid": "No reuse"}]
        spec["components"][0]["reference_ids"] = ["case"]
        output = render(TIMELINE.validate(spec))
        tags = Tags()
        tags.feed(output)
        self.assertFalse({"script", "iframe", "img", "video", "audio", "object", "form"} & {t for t, _ in tags.tags})
        self.assertIn(TIMELINE.esc(payload), output)
        self.assertTrue(any(tag == "a" and attrs.get("href", "").startswith("https:") for tag, attrs in tags.tags))
        self.assertTrue(any(attrs.get("http-equiv") == "Content-Security-Policy" for _, attrs in tags.tags))
        for bad in ("javascript:alert(1)", "http://example.org", "https://user:password@example.org", "file:///tmp/file"):
            spec["sources"][0]["url"] = bad
            with self.subTest(url=bad), self.assertRaises(ValueError):
                TIMELINE.validate(spec)

    def run_cli(self, *args):
        return subprocess.run([sys.executable, str(SCRIPT), *map(str, args)], capture_output=True, text=True)

    def test_cli_check_publication_receipt_and_no_overwrite(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            source, output = root / "source.json", root / "timeline-v1"
            raw = json.dumps(example(), ensure_ascii=False).encode()
            source.write_bytes(raw)
            check = self.run_cli("--spec", source, "--check")
            self.assertEqual(check.returncode, 0, check.stderr)
            self.assertEqual(list(root.iterdir()), [source])
            result = self.run_cli("--spec", source, "--out", output)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(json.loads(result.stdout)["html"], str(output / "timeline.html"))
            receipt = json.loads((output / "receipt.json").read_text())
            self.assertEqual(receipt["design_sha256"], hashlib.sha256(raw).hexdigest())
            self.assertEqual(receipt["document_sha256"], hashlib.sha256((output / "timeline.html").read_bytes()).hexdigest())
            self.assertIn("Design ID: sha256:" + receipt["design_sha256"], (output / "timeline.html").read_text())
            self.assertEqual(receipt["approval"], "not-established")
            self.assertEqual((output / "design.json").read_bytes(), raw)
            self.assertEqual(source.read_bytes(), raw)
            again = self.run_cli("--spec", source, "--out", output)
            self.assertNotEqual(again.returncode, 0)
            self.assertEqual((output / "design.json").read_bytes(), raw)

    def test_cli_rejects_invalid_json_and_symlink_paths_without_publication(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            source, out = root / "source.json", root / "out"
            for raw in ('{"version":1,"version":1}', '{"duration":NaN}', '[]'):
                source.write_text(raw)
                result = self.run_cli("--spec", source, "--out", out)
                self.assertNotEqual(result.returncode, 0)
                self.assertNotIn("Traceback", result.stderr)
                self.assertFalse(out.exists())
            source.write_text(json.dumps(example()))
            link = root / "alias"
            link.symlink_to(root, target_is_directory=True)
            for input_path, target in ((link / "source.json", out), (source, link / "out")):
                result = self.run_cli("--spec", input_path, "--out", target)
                self.assertNotEqual(result.returncode, 0)
                self.assertFalse(out.exists())
            out.symlink_to(source)
            self.assertNotEqual(self.run_cli("--spec", source, "--out", out).returncode, 0)

    def test_overlap_scene_and_unused_component(self):
        for change in ("overlap", "unused"):
            spec = example()
            if change == "overlap":
                scene = deepcopy(spec["scenes"][0])
                scene["id"] = "overlapping"
                spec["scenes"].append(scene)
            else:
                component = deepcopy(spec["components"][0])
                component["id"] = "unused"
                spec["components"].append(component)
            with self.subTest(change=change), self.assertRaises(ValueError):
                TIMELINE.validate(spec)

    def test_dense_changes_keep_all_intermediate_states(self):
        spec = example()
        scene = spec["scenes"][0]
        spec["duration"] = scene["end"] = 80
        template = scene["events"][0]
        frame = scene["keyframes"][0]
        scene["events"], scene["keyframes"] = [], []
        for index in range(80):
            event = deepcopy(template)
            event.update(id=f"change-{index}", start=index, end=index + 1)
            scene["events"].append(event)
            for at in (index, index + 0.5):
                state = deepcopy(frame)
                state["at"] = at
                scene["keyframes"].append(state)
        state = deepcopy(frame)
        state["at"] = 80
        scene["keyframes"].append(state)
        TIMELINE.validate(spec)
        self.assertIn("change-79", render(spec))

    def test_offscreen_entry_is_representable_without_clamping(self):
        spec = example()
        node = spec["scenes"][0]["keyframes"][0]["nodes"][0]
        node.update(x=-40)
        output = render(TIMELINE.validate(spec))
        self.assertIn('x="-160"', output)
        self.assertEqual(node["x"], -40)

    def test_render_requires_explicit_source_identity(self):
        with self.assertRaises(TypeError):
            TIMELINE.render(example())
        with self.assertRaisesRegex(ValueError, "identity"):
            TIMELINE.render(example(), "unbound")


if __name__ == "__main__":
    unittest.main()
