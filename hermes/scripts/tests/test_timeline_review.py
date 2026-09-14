"""Bound, complete review disclosure; not a test of artistic appeal."""
from copy import deepcopy
import hashlib
from html.parser import HTMLParser
import importlib.util
import json
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import unittest

SCRIPT = Path(__file__).resolve().parents[2] / "profiles/assistant/scripts/creative-timeline.py"
LOADER = importlib.util.spec_from_file_location("timeline_review", SCRIPT)
MODULE = importlib.util.module_from_spec(LOADER)
LOADER.loader.exec_module(MODULE)


def encoded(value):
    return json.dumps(value, ensure_ascii=False, indent=2).encode()


def digest(value):
    return hashlib.sha256(encoded(value)).hexdigest()


def fixture():
    spec = json.loads(SCRIPT.with_suffix(".md").read_text().split("```json\n", 1)[1].split("\n```", 1)[0])
    review = {"version": 1, "design_sha256": digest(spec), "language": "en", "title": "One panel, one result",
              "summary": "The task expands without losing its identity, then holds for reading.",
              "issues": [{"index": 0, "summary": "First row: before or after half height?"}],
              "sections": [{"id": "expand-and-read", "scene": "result", "title": "Expand, then read", "summary": "Keep the heading anchored while the result opens beneath it.",
                            "start": 0, "end": 2, "event_ids": ["expand", "read-result"],
                            "previews": [{"at": 0, "caption": "Before"}, {"at": 0.5, "caption": "Middle"}, {"at": 2, "caption": "After"}]}]}
    return spec, review


def fixture_v2():
    spec, review = fixture()
    spec["version"] = 2
    spec["frame"] = {"aspect": "9:16", "background": "ink"}
    for scene in spec["scenes"]:
        for frame in scene["keyframes"]:
            node = frame["nodes"][0]
            frame["nodes"] = [{
                "component": "result-panel", "kind": "surface", "key": "panel",
                "x": node["x"], "y": node["y"], "w": node["w"], "h": node["h"], "label": node["label"],
                "fill": "paper", "opacity": 1, "shape": "notch-top-right", "pattern": "vertical", "pattern_ink": "ink",
            }, {
                "component": "result-panel", "kind": "text", "key": "heading",
                "x": 12, "y": 17, "w": 36, "h": 4, "label": "Heading text",
                "fill": "ink", "opacity": 1, "content": "Today's tasks", "weight": "medium",
            }]
            if frame["at"] == 2:
                frame["nodes"].append({
                    "component": "result-panel", "kind": "text", "key": "done",
                    "x": 12, "y": 60, "w": 36, "h": 5, "label": "Result line",
                    "fill": "accent", "opacity": 0.5, "content": "Done", "weight": "bold",
                })
    review["design_sha256"] = digest(spec)
    return spec, review


class DisclosureParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.depth = 0
        self.nested = False
        self.panels = []
        self.summary_count = 0
        self.tags = []

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        self.tags.append((tag, attrs))
        if tag == "details":
            self.nested |= self.depth > 0
            self.depth += 1
            self.panels.append(attrs)
        if tag == "summary":
            self.summary_count += 1

    def handle_endtag(self, tag):
        if tag == "details":
            self.depth -= 1


class TimelineReviewTest(unittest.TestCase):
    def output(self, spec, review):
        MODULE.validate(spec)
        MODULE.validate_review(review, spec, digest(spec))
        return MODULE.render_review(spec, review, digest(spec), digest(review))

    def test_independent_native_disclosures_and_complete_retained_detail(self):
        spec, review = fixture()
        original = deepcopy((spec, review))
        output = self.output(spec, review)
        self.assertEqual((spec, review), original)
        self.assertEqual(output, self.output(spec, review))
        parser = DisclosureParser()
        parser.feed(output)
        self.assertFalse(parser.nested)
        self.assertEqual(parser.summary_count, len(parser.panels))
        self.assertTrue(all("name" not in panel and "open" not in panel for panel in parser.panels))
        self.assertFalse({"script", "dialog", "iframe", "form", "img", "video", "audio"} & {tag for tag, _ in parser.tags})
        section = review["sections"][0]
        scene = next(s for s in spec["scenes"] if s["id"] == section["scene"])
        events = [event for event in scene["events"] if event["id"] in section["event_ids"]]
        self.assertEqual(output.count('<li class="row'), len(events))
        for event in events:
            self.assertIn(f'<span class="title">{MODULE.esc(event["subject"])}</span>', output)
        for summary_html in re.findall(r'<summary class="line">(.*?)</summary>', output, re.S):
            self.assertIn('<span class="title">', summary_html)
            self.assertIn('<span class="thumb">', summary_html)
            self.assertNotRegex(summary_html, r'<p |<div |<figure|<h2')
        self.assertEqual(output.count('id="issues"'), 1)
        self.assertLess(output.index(review["issues"][0]["summary"]), output.index('<details'))
        self.assertIn('class="chip time"', output)
        self.assertIn('class="chip change"', output)
        self.assertIn('<ol class="strip">', output)
        self.assertIn('id="lane-all"', output)
        self.assertIn('<label for="lane-visual">', output)
        self.assertIn(f'<li class="section" id="beat-{section["id"]}"', output)
        full_spec = MODULE.render(spec, digest(spec))
        for scene in spec["scenes"]:
            for event in scene["events"]:
                for key in ("before", "during", "after", "trigger", "trajectory", "pacing"):
                    self.assertNotIn(MODULE.esc(event[key]), output)
                    self.assertIn(MODULE.esc(event[key]), full_spec)
            for frame in scene["keyframes"]:
                self.assertIn(MODULE.esc(frame["label"]), output)
        for component in spec["components"]:
            self.assertIn(MODULE.esc(component["name"]), output)
        self.assertIn(spec["open_items"][0], output)
        self.assertIn("Design ID: sha256:" + digest(spec), output)
        self.assertIn("Review ID: sha256:" + digest(review), output)
        self.assertIn(MODULE.REVIEW_LABELS["en"]["spec"], output)
        self.assertNotIn('<article class="event"', output)
        self.assertNotIn("<dl>", output)

    def test_unknown_fields_and_stale_or_incomplete_review_fail(self):
        mutations = [
            lambda r: r.update(design_sha256="0" * 64),
            lambda r: r.update(extra="do not drop me"),
            lambda r: r.update(language="unknown"),
            lambda r: r.update(issues=[]),
            lambda r: r["issues"][0].update(index=True),
            lambda r: r["sections"][0].update(start=0.2),
            lambda r: r["sections"][0].update(start=0.0000001),
            lambda r: r["sections"][0].update(end=1),
            lambda r: r["sections"][0].update(scene="missing"),
            lambda r: r["sections"][0].update(event_ids=["expand"]),
            lambda r: r["sections"][0].update(event_ids=["unknown"]),
            lambda r: r["sections"][0]["previews"].pop(1),
            lambda r: r["sections"][0]["previews"][1].update(at=0.25),
            lambda r: r["sections"][0]["previews"][0].update(at=False),
            lambda r: r["sections"][0].update(summary="x" * 161),
        ]
        for mutation in mutations:
            spec, review = fixture()
            mutation(review)
            with self.subTest(mutation=mutation), self.assertRaises(ValueError):
                MODULE.validate_review(review, spec, digest(spec))

    def test_cross_section_event_coverage_is_not_silently_clipped(self):
        spec, review = fixture()
        camera = deepcopy(spec["scenes"][0]["events"][0])
        camera.update(id="camera", lane="camera", end=2)
        spec["scenes"][0]["events"].insert(1, camera)
        spec["scenes"][0]["absent_lanes"].pop("camera")
        review["design_sha256"] = digest(spec)
        first = review["sections"][0]
        first.update(end=1, event_ids=["expand", "camera"])
        first["previews"][-1]["at"] = 1
        second = deepcopy(first)
        second.update(id="read", start=1, end=2, event_ids=["read-result", "camera"],
                      previews=[{"at": 1, "caption": "Continue"}, {"at": 2, "caption": "End"}])
        review["sections"].append(second)
        output = self.output(spec, review)
        parser = DisclosureParser()
        parser.feed(output)
        ids = [attrs["id"] for _, attrs in parser.tags if "id" in attrs]
        self.assertEqual(len(ids), len(set(ids)))
        self.assertIn("beat-expand-and-read", ids)
        self.assertIn("beat-read", ids)
        # An event reviewed in two sections gets one row per section with a section-qualified id.
        self.assertIn("event-camera_expand-and-read", ids)
        self.assertIn("event-camera_read", ids)
        self.assertNotIn("event-camera", ids)
        second["event_ids"].remove("camera")
        with self.assertRaisesRegex(ValueError, "omits event camera"):
            MODULE.validate_review(review, spec, digest(spec))

    def test_scene_order_and_all_open_items_are_required(self):
        spec, review = fixture()
        second = deepcopy(spec["scenes"][0])
        second.update(id="second", start=2, end=4)
        for event in second["events"]:
            event.update(id=event["id"] + "-second", start=event["start"] + 2, end=event["end"] + 2)
        for frame in second["keyframes"]:
            frame["at"] += 2
        spec["scenes"].append(second)
        spec["duration"] = 4
        review["design_sha256"] = digest(spec)
        section = deepcopy(review["sections"][0])
        section.update(id="second", scene="second", start=2, end=4, event_ids=["expand-second", "read-result-second"])
        for preview in section["previews"]:
            preview["at"] += 2
        review["sections"].append(section)
        self.output(spec, review)
        review["sections"].reverse()
        with self.assertRaisesRegex(ValueError, "scene in order"):
            MODULE.validate_review(review, spec, digest(spec))

    def test_localized_status_and_state_labels(self):
        spec, review = fixture()
        review["language"] = "ja"
        output = self.output(spec, review)
        before_details = output.split('<details', 1)[0]
        self.assertIn("判断してほしいこと", before_details)
        self.assertIn(review["issues"][0]["summary"], before_details)
        self.assertIn("この区間のコマ", output)
        self.assertIn('<span class="chip">画面</span>', output)
        self.assertIn('<label for="lane-all">すべて</label>', output)
        self.assertIn("0.5秒", output)
        self.assertIn("文章の仕様は同じ束の spec.html にあります。", output)
        for boilerplate in ("完成映像ではありません", "検討用・未解決あり", "配置と変化の図解", "Structural checks",
                            "not a finished video", "時点 /", "Document identity", "文書の識別情報"):
            self.assertNotIn(boilerplate, output)
        for identity in (None, "not-a-hash", '<script>bad</script>'):
            with self.assertRaisesRegex(ValueError, "identity"):
                MODULE.render_review(spec, review, identity, digest(review))

    def test_hyphenated_ids_cannot_collide(self):
        spec, review = fixture()
        spec["scenes"][0]["events"][0]["id"] = "hold-copy"
        spec["scenes"][0]["events"][1]["id"] = "copy"
        review["design_sha256"] = digest(spec)
        first = review["sections"][0]
        first.update(id="result", end=1, event_ids=["hold-copy"])
        first["previews"][-1]["at"] = 1
        second = deepcopy(first)
        second.update(id="result-hold", start=1, end=2, event_ids=["copy"],
                      previews=[{"at": 1, "caption": "Hold"}, {"at": 2, "caption": "End"}])
        review["sections"].append(second)
        output = self.output(spec, review)
        parser = DisclosureParser()
        parser.feed(output)
        ids = [attrs["id"] for _, attrs in parser.tags if "id" in attrs]
        self.assertEqual(len(ids), len(set(ids)))
        self.assertIn("beat-result", ids)
        self.assertIn("beat-result-hold", ids)

    def test_review_strings_are_escaped_and_no_fragment_links_required(self):
        spec, review = fixture()
        payload = '<script>alert(1)</script>'
        review["title"] = payload
        review["sections"][0]["summary"] = payload
        review["sections"][0]["previews"][0]["caption"] = payload
        spec["sources"] = [{"id": "source", "url": "https://example.org/", "inspection": "Synthetic, not inspected.",
                            "observed": payload, "adopt": "Nothing", "avoid": "Do not reuse"}]
        spec["components"][0]["reference_ids"] = ["source"]
        spec["scenes"][0]["events"][1]["reference_ids"] = ["source"]
        review["design_sha256"] = digest(spec)
        output = self.output(spec, review)
        parser = DisclosureParser()
        parser.feed(output)
        self.assertNotIn("script", [tag for tag, _ in parser.tags])
        self.assertIn(MODULE.esc(payload), output)
        self.assertNotIn("https://example.org/", output)
        self.assertIn("https://example.org/", MODULE.render(spec, digest(spec)))
        panels = {panel["id"] for panel in parser.panels}
        beats = {f'beat-{section["id"]}' for section in review["sections"]}
        allowed = panels | beats
        for tag, attrs in parser.tags:
            if tag == "a" and attrs.get("href", "").startswith("#"):
                href = attrs["href"][1:]
                self.assertIn(href, allowed)
        self.assertNotIn('href="#', output)

    def test_plain_row_when_single_frame_and_no_new_parts(self):
        spec, review = fixture()
        scene = spec["scenes"][0]
        scene["keyframes"] = [frame for frame in scene["keyframes"] if frame["at"] != 1]
        review["design_sha256"] = digest(spec)
        output = self.output(spec, review)
        self.assertIn('<details id="event-expand"', output)
        self.assertIn('<li class="row last plain" data-lane="visual" id="event-read-result">', output)

    def test_lane_filter_inputs_precede_list(self):
        spec, review = fixture()
        output = self.output(spec, review)
        inputs_index = output.index('<input class="lane-input"')
        wrap_index = output.index('<div class="wrap"><div class="filters"')
        self.assertLess(inputs_index, wrap_index)
        self.assertIn('<input class="lane-input" type="radio" name="lane" id="lane-all" checked>', output)
        self.assertIn('<input class="lane-input" type="radio" name="lane" id="lane-visual">', output)
        self.assertNotIn('id="lane-text"', output)
        self.assertNotIn('id="lane-camera"', output)
        self.assertNotIn('id="lane-audio"', output)
        self.assertEqual(output.count(' checked>'), 1)

    def test_cli_preserves_both_inputs_and_records_both_identities(self):
        spec, review = fixture()
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp).resolve()
            source, sidecar = root / "design.json", root / "review.json"
            source.write_bytes(encoded(spec))
            sidecar.write_bytes(encoded(review))
            command = [sys.executable, str(SCRIPT), "--spec", str(source), "--review", str(sidecar)]
            checked = subprocess.run(command + ["--check"], capture_output=True, text=True)
            self.assertEqual(checked.returncode, 0, checked.stderr)
            self.assertEqual(set(root.iterdir()), {source, sidecar})
            output = root / "v1"
            built = subprocess.run(command + ["--out", str(output)], capture_output=True, text=True)
            self.assertEqual(built.returncode, 0, built.stderr)
            receipt = json.loads((output / "receipt.json").read_text())
            self.assertEqual((output / "design.json").read_bytes(), source.read_bytes())
            self.assertEqual((output / "review.json").read_bytes(), sidecar.read_bytes())
            self.assertEqual(receipt["design_sha256"], digest(spec))
            self.assertEqual(receipt["review_sha256"], digest(review))
            self.assertEqual(receipt["document_sha256"], hashlib.sha256((output / "timeline.html").read_bytes()).hexdigest())
            self.assertEqual(receipt["approval"], "not-established")
            self.assertEqual(receipt["status"], "discussion-only")
            self.assertEqual(json.loads(built.stdout)["review"], str(output / "review.json"))
            self.assertTrue((output / "spec.html").exists())
            self.assertEqual(receipt["spec_sha256"], hashlib.sha256((output / "spec.html").read_bytes()).hexdigest())
            self.assertEqual(json.loads(built.stdout)["spec"], str(output / "spec.html"))
            self.assertIn(b"<dl>", (output / "spec.html").read_bytes())
            self.assertNotIn(b"<dl>", (output / "timeline.html").read_bytes())
            review["summary"] = "A revised review sentence, not a changed source design."
            sidecar.write_bytes(encoded(review))
            newer = root / "v2"
            built = subprocess.run(command + ["--out", str(newer)], capture_output=True, text=True)
            self.assertEqual(built.returncode, 0, built.stderr)
            next_receipt = json.loads((newer / "receipt.json").read_text())
            self.assertEqual(receipt["design_sha256"], next_receipt["design_sha256"])
            self.assertNotEqual(receipt["review_sha256"], next_receipt["review_sha256"])
            self.assertNotEqual(receipt["document_sha256"], next_receipt["document_sha256"])
            repeated = subprocess.run(command + ["--out", str(output)], capture_output=True, text=True)
            self.assertNotEqual(repeated.returncode, 0)
            review["design_sha256"] = "0" * 64
            sidecar.write_bytes(encoded(review))
            failed = subprocess.run(command + ["--out", str(root / "invalid")], capture_output=True, text=True)
            self.assertNotEqual(failed.returncode, 0)
            self.assertFalse((root / "invalid").exists())

    def test_v2_boards_draw_real_frame_text_and_derived_motion_marks(self):
        spec, review = fixture_v2()
        output = self.output(spec, review)
        self.assertIn('viewBox="0 0 90 160"', output)
        self.assertIn('fill="#182330"', output)
        self.assertTrue(MODULE.esc("Today's tasks") in output or "Today&#x27;s tasks" in output)
        self.assertIn('font-weight="500"', output)
        self.assertIn('font-weight="700"', output)
        self.assertIn('opacity="0.5"', output)
        self.assertIn('<polygon', output)
        self.assertIn('stroke="#182330"', output)
        self.assertIn('<line', output)
        self.assertIn('stroke-dasharray="2.4 1.6"', output)
        self.assertIn('fill="#ff7a1a"', output)
        strip_split = output.split('<ol class="strip">', 1)[1]
        first_frame_start = strip_split.index('<li class="frame">')
        first_svg_start = strip_split.index('<svg', first_frame_start)
        first_svg_end = strip_split.index('</svg>', first_svg_start) + len('</svg>')
        first_svg = strip_split[first_svg_start:first_svg_end]
        self.assertNotIn('#ff7a1a', first_svg)
        self.assertIn('stroke-width="1.3"', output)
        self.assertIn('<span class="chip change">Appears</span>', output)
        self.assertIn(MODULE.REVIEW_LABELS["en"]["legend"], output.split('<details', 1)[0])
        for scene in spec["scenes"]:
            for frame in scene["keyframes"]:
                self.assertIn(MODULE.esc(frame["label"]), output)
                for node in frame["nodes"]:
                    self.assertIn(MODULE.esc(node["label"]), output)
        self.assertIn("Design ID: sha256:" + digest(spec), output)
        self.assertNotIn('class="landscape"', output)
        self.assertIn('<main class="portrait">', output)
        self.assertIn('class="part"', output)
        self.assertIn("Task and result panel", output)

    def test_v2_validation_rejects_bad_frames_and_nodes(self):
        mutations = [
            lambda s: s["frame"].update(aspect="9x16"),
            lambda s: s["frame"].update(aspect="0:16"),
            lambda s: s["frame"].update(aspect="65:1"),
            lambda s: s["frame"].update(background="missing"),
            lambda s: s.pop("frame"),
            lambda s: s["scenes"][0]["keyframes"][0]["nodes"][0].update(kind="image"),
            lambda s: s["scenes"][0]["keyframes"][0]["nodes"][0].update(opacity=1.5),
            lambda s: s["scenes"][0]["keyframes"][0]["nodes"][0].update(shape="blob"),
            lambda s: s["scenes"][0]["keyframes"][0]["nodes"][0].update(pattern="stripes"),
            lambda s: s["scenes"][0]["keyframes"][0]["nodes"][0].update(pattern_ink="nope"),
            lambda s: s["scenes"][0]["keyframes"][0]["nodes"][1].update(weight="heavy"),
            lambda s: s["scenes"][0]["keyframes"][0]["nodes"][1].update(content="x" * 81),
            lambda s: s["scenes"][0]["keyframes"][0]["nodes"][1].update(key="panel"),
            lambda s: s["scenes"][0]["keyframes"][0]["nodes"][0].update(extra=1),
            lambda s: s["scenes"][0]["keyframes"][0]["nodes"][0].pop("key"),
        ]
        for mutation in mutations:
            spec, _ = fixture_v2()
            mutation(spec)
            with self.subTest(mutation=mutation):
                with self.assertRaises(ValueError):
                    MODULE.validate(spec)
        spec, _ = fixture()
        spec["frame"] = {"aspect": "9:16", "background": "ink"}
        with self.assertRaises(ValueError):
            MODULE.validate(spec)
        spec, _ = fixture_v2()
        MODULE.validate(spec)

    def test_v2_full_document_without_review_still_renders_boards(self):
        spec, _ = fixture_v2()
        MODULE.validate(spec)
        output = MODULE.render(spec, digest(spec))
        self.assertIn('viewBox="0 0 90 160"', output)


if __name__ == "__main__":
    unittest.main()
