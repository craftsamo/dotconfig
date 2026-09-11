"""Authored-layout (layout_html) contract tests for card.CREATE.

Pure unit tests exercise `card.validate`/`card.page`/`card.create` against
authored HTML fragments (tile structure, copy/asset bindings, CSS rules,
literal text output). `CardAuthoredRenderSmoke` is a live, opt-in suite (set
CARD_AUTHORED_SMOKE_DIR to a new directory) that renders through the real
offline agent-browser; it is skipped unless that variable is set.
"""

import hashlib
import html
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


def tile(n, **binds):
    """Build a `<section data-card-tile="n">...</section>` with one
    `<div data-card-copy="field">text</div>` per keyword arg (skip a field to
    leave it unbound)."""
    inner = "".join(f'<div data-card-copy="{field}">{text}</div>' for field, text in binds.items())
    return f'<section data-card-tile="{n}">{inner}</section>'


def layout(sections, style=""):
    style_html = f"<style>{style}</style>" if style else ""
    return style_html + "".join(sections)


class CardAuthoredTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="card-authored-test-")
        self.addCleanup(self.temp.cleanup)
        self.work = Path(self.temp.name)
        self.font = self.work / "font.ttf"
        self.font.write_bytes(b"test font")
        self.spec = {"title": "A clear idea", "destination": "og", "style": "paper", "font": str(self.font)}

    def write_layout(self, content, name="layout.html"):
        path = self.work / name
        path.write_text(content)
        return path

    def test_real_runtime_discovery_preserves_distinct_card_leaves(self):
        from tools import skills_tool

        for verb in ("create", "generate", "edit", "analyze"):
            body = (card.ROOT / verb / "card/SKILL.md").read_text()
            self.assertLess(body.index("\n---", 4) + 4, 3800)
        with patch.object(skills_tool, "_SKILLS_CACHE", {}), \
             patch.object(skills_tool, "_skill_search_dirs", return_value=([], [card.ROOT], card.ROOT)), \
             patch.object(skills_tool, "_skills_dir", return_value=card.ROOT), \
             patch("agent.skill_utils.get_external_skills_dirs", return_value=[]):
            names = {row["name"] for row in skills_tool._find_all_skills(skip_disabled=True)}
        self.assertTrue({"create-card", "generate-card", "edit-card", "analyze-card"} <= names)
        self.assertNotIn("card", names)

    # -- old behavior is preserved when layout_html is absent -------------

    def test_no_layout_html_preserves_named_template_behavior(self):
        page = card.page(self.spec, card.validate(self.spec, "create"))
        self.assertNotIn("data-card-tile", page)
        self.assertNotIn("data-card-copy", page)

    def test_no_layout_html_style_css_still_rejects_font_size(self):
        css = self.work / "custom.css"
        css.write_text(":root{--surface:#fff4bc;--ink:#232330;--accent:#c83538;}h1{font-size:10px}")
        with self.assertRaises(ValueError):
            card.css_style({"style": "Custom", "style_css": str(css)})

    # -- layout_html field: presence, type, conflicts ----------------------

    def test_layout_html_requires_absolute_existing_file(self):
        for bad in ("relative.html", str(self.work / "missing.html")):
            spec = {**self.spec, "layout_html": bad}
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                card.validate(spec, "create")

    def test_layout_html_conflicts_with_style_css(self):
        frag = self.write_layout(layout([tile(1, title=self.spec["title"])]))
        css = self.work / "custom.css"
        css.write_text(":root{--surface:#fff4bc;--ink:#232330;--accent:#c83538;}")
        spec = {**self.spec, "layout_html": str(frag), "style_css": str(css)}
        with self.assertRaises(ValueError):
            card.validate(spec, "create")

    def test_layout_html_conflicts_with_palette(self):
        frag = self.write_layout(layout([tile(1, title=self.spec["title"])]))
        spec = {**self.spec, "layout_html": str(frag), "palette": "#ffffff,#000000,#ff0000"}
        with self.assertRaises(ValueError):
            card.validate(spec, "create")

    def test_layout_html_style_is_kept_as_free_text(self):
        # Without layout_html, an unrecognized style name with no style_css is rejected.
        with self.assertRaises(ValueError):
            card.css_style({"style": "My hand-authored layout"})
        # With layout_html, the same free-text style string is accepted as-is.
        frag = self.write_layout(layout([tile(1, title=self.spec["title"])]))
        spec = {**self.spec, "layout_html": str(frag), "style": "My hand-authored layout"}
        card.validate(spec, "create")  # must not raise

    # -- tile section structure --------------------------------------------

    def test_layout_html_missing_tile_section_rejected(self):
        frag = self.write_layout("<style>.x{color:red}</style>")
        spec = {**self.spec, "layout_html": str(frag)}
        with self.assertRaises(ValueError):
            card.validate(spec, "create")

    def test_layout_html_duplicate_tile_section_rejected(self):
        frag = self.write_layout(layout([tile(1, title=self.spec["title"]), tile(1, title=self.spec["title"])]))
        spec = {**self.spec, "layout_html": str(frag)}
        with self.assertRaises(ValueError):
            card.validate(spec, "create")

    def test_layout_html_nested_tile_section_rejected(self):
        frag = self.write_layout(
            f'<section data-card-tile="1"><section data-card-tile="1">'
            f'<div data-card-copy="title">{self.spec["title"]}</div></section></section>'
        )
        spec = {**self.spec, "layout_html": str(frag)}
        with self.assertRaises(ValueError):
            card.validate(spec, "create")

    def test_layout_html_unrequested_tile_section_rejected(self):
        # destination is "og" -> tiles == 1; a tile-2 section is unrequested.
        frag = self.write_layout(layout([tile(1, title=self.spec["title"]), tile(2)]))
        spec = {**self.spec, "layout_html": str(frag)}
        with self.assertRaises(ValueError):
            card.validate(spec, "create")

    def test_layout_html_missing_tile_section_for_multi_tile_rejected(self):
        frag = self.write_layout(layout([tile(1, title=self.spec["title"])]))
        spec = {**self.spec, "layout_html": str(frag), "destination": "x-carousel", "tile": "square", "tiles": 3}
        with self.assertRaises(ValueError):
            card.validate(spec, "create")

    # -- copy bindings --------------------------------------------------------

    def test_layout_html_empty_binding_element_rejected(self):
        frag = self.write_layout(layout([tile(1, title="")]))
        spec = {**self.spec, "layout_html": str(frag)}
        with self.assertRaises(ValueError):
            card.validate(spec, "create")

    def test_layout_html_unrequested_binding_rejected(self):
        # subtitle is not supplied in the spec (empty/absent), so binding it is rejected.
        frag = self.write_layout(layout([tile(1, title=self.spec["title"], subtitle="Unrequested text")]))
        spec = {**self.spec, "layout_html": str(frag)}
        with self.assertRaises(ValueError):
            card.validate(spec, "create")

    def test_layout_html_missing_binding_rejected(self):
        frag = self.write_layout(layout([tile(1, title=self.spec["title"])]))
        spec = {**self.spec, "layout_html": str(frag), "subtitle": "Needs a home"}
        with self.assertRaises(ValueError):
            card.validate(spec, "create")

    def test_layout_html_duplicate_binding_rejected(self):
        frag = self.write_layout(
            f'<section data-card-tile="1"><div data-card-copy="title">{self.spec["title"]}</div>'
            f'<div data-card-copy="title">{self.spec["title"]}</div></section>'
        )
        spec = {**self.spec, "layout_html": str(frag)}
        with self.assertRaises(ValueError):
            card.validate(spec, "create")

    def test_layout_html_nested_binding_rejected(self):
        frag = self.write_layout(
            f'<section data-card-tile="1"><div data-card-copy="title">{self.spec["title"]}'
            f'<span data-card-copy="label">Nested</span></div></section>'
        )
        spec = {**self.spec, "layout_html": str(frag), "label": "Nested"}
        with self.assertRaises(ValueError):
            card.validate(spec, "create")

    def test_layout_html_unbound_text_rejected(self):
        frag = self.write_layout(
            f'<section data-card-tile="1"><div data-card-copy="title">{self.spec["title"]}</div>'
            f'Stray unbound text</section>'
        )
        spec = {**self.spec, "layout_html": str(frag)}
        with self.assertRaises(ValueError):
            card.validate(spec, "create")

    def test_layout_html_tile_title_bindings(self):
        frag = self.write_layout(layout([
            tile(1, title=self.spec["title"], **{"tile-title-1": "Overview"}),
            tile(2, **{"tile-title-2": "Detail"}),
            tile(3, **{"tile-title-3": "Next"}),
        ]))
        spec = {**self.spec, "layout_html": str(frag), "destination": "x-carousel", "tile": "square", "tiles": 3,
                "tile_titles": "1: Overview\n2: Detail\n3: Next"}
        card.validate(spec, "create")  # must not raise

    # -- copy_blocks: explicit additional per-tile copy -----------------------

    def test_copy_blocks_repeated_branding_and_extra_body(self):
        brand = "Acme Co"
        frag = self.write_layout(layout([
            tile(1, title=self.spec["title"], brand=brand),
            tile(2, **{"brand-2": brand, "body-2": "Extra body copy for tile two."}),
            tile(3, **{"brand-3": brand}),
        ]))
        spec = {**self.spec, "layout_html": str(frag), "destination": "x-carousel", "tile": "square", "tiles": 3,
                "brand": brand, "copy_blocks": [
                    {"id": "brand-2", "tile": 2, "text": brand},
                    {"id": "brand-3", "tile": 3, "text": brand},
                    {"id": "body-2", "tile": 2, "text": "Extra body copy for tile two."},
                ]}
        dims = card.validate(spec, "create")  # must not raise
        page = card.page(spec, dims)
        self.assertEqual(page.count(f">{brand}<"), 3)
        self.assertEqual(page.count(">Extra body copy for tile two.<"), 1)
        self.assertIn('data-card-copy="brand-2"', page)
        self.assertIn('data-card-copy="brand-3"', page)
        self.assertIn('data-card-copy="body-2"', page)

    def test_copy_blocks_missing_or_extra_field_rejected(self):
        base_frag = self.write_layout(layout([tile(1, title=self.spec["title"])]))
        bad_blocks = (
            [{"id": "notes", "tile": 1}],  # missing text
            [{"id": "notes", "text": "x"}],  # missing tile
            [{"tile": 1, "text": "x"}],  # missing id
            [{"id": "notes", "tile": 1, "text": "x", "extra": "y"}],  # extra field
        )
        for blocks in bad_blocks:
            spec = {**self.spec, "layout_html": str(base_frag), "copy_blocks": blocks}
            with self.subTest(blocks=blocks), self.assertRaises(ValueError):
                card.validate(spec, "create")

    def test_copy_blocks_wrong_tile_rejected(self):
        frag = self.write_layout(layout([tile(1, title=self.spec["title"])]))
        for bad_tile in (0, 2, 1.5, "1"):
            spec = {**self.spec, "layout_html": str(frag),
                    "copy_blocks": [{"id": "notes", "tile": bad_tile, "text": "x"}]}
            with self.subTest(tile=bad_tile), self.assertRaises(ValueError):
                card.validate(spec, "create")

    def test_copy_blocks_duplicate_id_rejected(self):
        frag = self.write_layout(layout([tile(1, title=self.spec["title"])]))
        spec = {**self.spec, "layout_html": str(frag), "copy_blocks": [
            {"id": "notes", "tile": 1, "text": "x"}, {"id": "notes", "tile": 1, "text": "y"},
        ]}
        with self.assertRaises(ValueError):
            card.validate(spec, "create")

    def test_copy_blocks_reserved_or_invalid_id_rejected(self):
        frag = self.write_layout(layout([tile(1, title=self.spec["title"])]))
        for bad_id in ("brand", "slug", "note", "tile-title-1", "Title", "2abc", "has_underscore", ""):
            spec = {**self.spec, "layout_html": str(frag),
                    "copy_blocks": [{"id": bad_id, "tile": 1, "text": "x"}]}
            with self.subTest(id=bad_id), self.assertRaises(ValueError):
                card.validate(spec, "create")

    def test_copy_blocks_without_layout_html_rejected(self):
        spec = {**self.spec, "copy_blocks": [{"id": "notes", "tile": 1, "text": "x"}]}
        with self.assertRaises(ValueError):
            card.validate(spec, "create")

    # -- parser rejects browser-implicit tree repair -------------------------

    def test_layout_html_p_containing_block_content_rejected(self):
        frag = self.write_layout(
            f'<section data-card-tile="1"><div data-card-copy="title">{self.spec["title"]}</div>'
            '<p data-card-copy="notes">Intro<span><div>Nested block</div></span></p></section>'
        )
        spec = {**self.spec, "layout_html": str(frag),
                "copy_blocks": [{"id": "notes", "tile": 1, "text": "Intro"}]}
        with self.assertRaises(ValueError):
            card.validate(spec, "create")

    def test_layout_html_heading_in_heading_rejected(self):
        frag = self.write_layout(
            f'<section data-card-tile="1"><div data-card-copy="title">{self.spec["title"]}</div>'
            '<h1 data-card-copy="notes">Outer<h2>Inner</h2></h1></section>'
        )
        spec = {**self.spec, "layout_html": str(frag),
                "copy_blocks": [{"id": "notes", "tile": 1, "text": "Outer"}]}
        with self.assertRaises(ValueError):
            card.validate(spec, "create")

    def test_layout_html_li_without_intervening_list_rejected(self):
        frag = self.write_layout(
            f'<section data-card-tile="1"><div data-card-copy="title">{self.spec["title"]}</div>'
            '<ul data-card-copy="notes"><li>One<li>Two</li></li></ul></section>'
        )
        spec = {**self.spec, "layout_html": str(frag),
                "copy_blocks": [{"id": "notes", "tile": 1, "text": "OneTwo"}]}
        with self.assertRaises(ValueError):
            card.validate(spec, "create")

    def test_layout_html_valid_nested_list(self):
        list_text = "OneNestedTwo"
        list_html = ('<ul data-card-copy="notes"><li>One<ul><li>Nested</li></ul></li>'
                     '<li>Two</li></ul>')
        frag = self.write_layout(
            f'<section data-card-tile="1"><div data-card-copy="title">{self.spec["title"]}</div>'
            f'{list_html}</section>'
        )
        spec = {**self.spec, "layout_html": str(frag),
                "copy_blocks": [{"id": "notes", "tile": 1, "text": list_text}]}
        card.validate(spec, "create")  # must not raise: ul breaks the li chain before the next li

    # -- disallowed tags/attributes/assets --------------------------------

    def test_layout_html_html_body_tags_rejected(self):
        for wrapper in ("<html>{0}</html>", "<body>{0}</body>"):
            frag = self.write_layout(wrapper.format(tile(1, title=self.spec["title"])))
            spec = {**self.spec, "layout_html": str(frag)}
            with self.subTest(wrapper=wrapper), self.assertRaises(ValueError):
                card.validate(spec, "create")

    def test_layout_html_disallowed_tags_rejected(self):
        for bad_tag in ("script", "svg", "iframe", "meta", "link", "base", "input"):
            frag = self.write_layout(
                f'<section data-card-tile="1"><div data-card-copy="title">{self.spec["title"]}</div>'
                f'<{bad_tag}></{bad_tag}></section>'
            )
            spec = {**self.spec, "layout_html": str(frag)}
            with self.subTest(tag=bad_tag), self.assertRaises(ValueError):
                card.validate(spec, "create")

    def test_layout_html_disallowed_attributes_rejected(self):
        bad_markup = (
            f'<section data-card-tile="1"><div data-card-copy="title" onclick="x()">{self.spec["title"]}</div></section>',
            f'<section data-card-tile="1"><div data-card-copy="title" src="x">{self.spec["title"]}</div></section>',
            f'<section data-card-tile="1"><div data-card-copy="title" contenteditable="true">{self.spec["title"]}</div></section>',
            f'<section data-card-tile="1" data-unknown="x"><div data-card-copy="title">{self.spec["title"]}</div></section>',
        )
        for markup in bad_markup:
            frag = self.write_layout(markup)
            spec = {**self.spec, "layout_html": str(frag)}
            with self.subTest(markup=markup), self.assertRaises(ValueError):
                card.validate(spec, "create")

    def test_layout_html_allowed_attributes_permitted(self):
        frag = self.write_layout(
            f'<section data-card-tile="1" class="tile-a" id="t1" style="color:red" lang="en" dir="ltr" title="a tile">'
            f'<div data-card-copy="title" class="h" id="ti" style="font-weight:700" lang="en" dir="ltr" title="ti">'
            f'{self.spec["title"]}</div></section>'
        )
        spec = {**self.spec, "layout_html": str(frag)}
        card.validate(spec, "create")  # must not raise

    def test_layout_html_allowed_static_tags_and_inline_spans(self):
        frag = self.write_layout(
            f'<section data-card-tile="1"><header></header><main>'
            f'<h1 data-card-copy="title"><strong>{self.spec["title"][:7]}</strong> '
            f'<em>{self.spec["title"][8:]}</em></h1></main>'
            f'<footer><small></small></footer><aside></aside></section>'
        )
        spec = {**self.spec, "layout_html": str(frag)}
        card.validate(spec, "create")  # must not raise

    def test_layout_html_img_requires_asset_attribute(self):
        frag = self.write_layout(
            f'<section data-card-tile="1"><div data-card-copy="title">{self.spec["title"]}</div>'
            f'<img src="x.png"></section>'
        )
        spec = {**self.spec, "layout_html": str(frag)}
        with self.assertRaises(ValueError):
            card.validate(spec, "create")

    def test_layout_html_img_unknown_asset_value_rejected(self):
        frag = self.write_layout(
            f'<section data-card-tile="1"><div data-card-copy="title">{self.spec["title"]}</div>'
            f'<img data-card-asset="icon"></section>'
        )
        spec = {**self.spec, "layout_html": str(frag)}
        with self.assertRaises(ValueError):
            card.validate(spec, "create")

    def test_layout_html_supplied_asset_must_be_referenced(self):
        asset = self.work / "bg.png"
        card.command(["magick", "-size", "10x10", "xc:#334455", asset])
        frag = self.write_layout(layout([tile(1, title=self.spec["title"])]))  # no <img data-card-asset="background">
        spec = {**self.spec, "layout_html": str(frag), "background": str(asset)}
        with self.assertRaises(ValueError):
            card.validate(spec, "create")

    # -- style block CSS rules ----------------------------------------------

    def test_layout_html_style_forbids_url(self):
        frag = self.write_layout(layout([tile(1, title=self.spec["title"])], style=".x{background:url(evil.png)}"))
        spec = {**self.spec, "layout_html": str(frag)}
        with self.assertRaises(ValueError):
            card.validate(spec, "create")

    def test_layout_html_style_forbids_backslash(self):
        frag = self.write_layout(layout([tile(1, title=self.spec["title"])], style=".x{content:'\\65'}"))
        spec = {**self.spec, "layout_html": str(frag)}
        with self.assertRaises(ValueError):
            card.validate(spec, "create")

    def test_layout_html_style_forbids_import(self):
        frag = self.write_layout(layout([tile(1, title=self.spec["title"])], style="@import 'x.css';"))
        spec = {**self.spec, "layout_html": str(frag)}
        with self.assertRaises(ValueError):
            card.validate(spec, "create")

    def test_layout_html_style_forbids_font_face(self):
        frag = self.write_layout(layout([tile(1, title=self.spec["title"])], style="@font-face{font-family:X}"))
        spec = {**self.spec, "layout_html": str(frag)}
        with self.assertRaises(ValueError):
            card.validate(spec, "create")

    def test_layout_html_style_forbids_markup(self):
        frag = self.write_layout(layout([tile(1, title=self.spec["title"])], style=".x{color:red}<script>1</script>"))
        spec = {**self.spec, "layout_html": str(frag)}
        with self.assertRaises(ValueError):
            card.validate(spec, "create")

    def test_layout_html_style_allows_ordinary_layout_css(self):
        css = (
            ".copy-area{display:flex;flex-direction:column;position:absolute;text-align:center;font-size:72px}"
            "@media (min-width:100px){.copy-area{font-size:80px}}"
            "@supports (display:grid){.copy-area{display:grid}}"
        )
        frag = self.write_layout(layout([tile(1, title=self.spec["title"])], style=css))
        spec = {**self.spec, "layout_html": str(frag)}
        card.validate(spec, "create")  # must not raise

    # -- output: literal text, entity decode, no browser call on failure ----

    def test_layout_html_valid_fragment_produces_exact_page(self):
        title = '<script>" & test</script>'
        # Source-side entity encoding only needs to decode back to `title`;
        # any valid encoding works since HTMLParser decodes character refs.
        source_title = "&lt;script&gt;&quot; &amp; test&lt;/script&gt;"
        frag = self.write_layout(layout([
            tile(1, title=source_title, subtitle="Meta line", brand="Brand", meta="Meta", label="Label"),
        ], style=".copy-area{display:flex}"))
        spec = {**self.spec, "layout_html": str(frag), "title": title, "subtitle": "Meta line",
                "brand": "Brand", "meta": "Meta", "label": "Label"}
        dims = card.validate(spec, "create")
        page = card.page(spec, dims)
        self.assertNotIn("<script>", page)
        # The bound copy element re-serializes body text with quote=False,
        # which differs from the quote=True escaping used for <title> and
        # the data-card-expected attribute; check the exact visible bound
        # occurrence, not a page-wide count of one particular escaping.
        bound_title = html.escape(title, quote=False)
        self.assertEqual(page.count(f'>{bound_title}</div>'), 1)
        self.assertEqual(page.count(">Brand<"), 1)
        self.assertEqual(page.count(">Meta<"), 1)
        self.assertEqual(page.count(">Label<"), 1)
        self.assertIn("default-src 'none'", page)
        self.assertIn("script-src 'none'", page)
        self.assertIn("@font-face", page)
        self.assertIn('data-card-tile="1"', page)
        self.assertIn('data-card-copy="title"', page)
        self.assertIn(".copy-area{display:flex}", page)

    def test_layout_html_br_newline_preserved(self):
        frag = self.write_layout(layout([tile(1, title="Line1<br>Line2")]))
        spec = {**self.spec, "layout_html": str(frag), "title": "Line1\nLine2"}
        dims = card.validate(spec, "create")  # must not raise
        page = card.page(spec, dims)
        self.assertIn("Line1<br>Line2</div>", page)

    def test_layout_html_referenced_asset_embeds_data_uri(self):
        asset = self.work / "bg.png"
        card.command(["magick", "-size", "10x10", "xc:#334455", asset])
        frag = self.write_layout(
            f'<section data-card-tile="1"><div data-card-copy="title">{self.spec["title"]}</div>'
            f'<img data-card-asset="background"></section>'
        )
        spec = {**self.spec, "layout_html": str(frag), "background": str(asset)}
        dims = card.validate(spec, "create")  # must not raise
        page = card.page(spec, dims)
        expected_uri = card.data_uri(asset)
        self.assertEqual(page.count(f'<img data-card-asset="background" src="{html.escape(expected_uri, quote=True)}" alt="">'), 1)

    def test_authored_fragment_dedupes_repeated_asset_lookup(self):
        # Direct authored_fragment call with a mocked data_uri and synthetic
        # bytes source: no real image or full validate()/page() round trip.
        source = (b'<section data-card-tile="1"><img data-card-asset="background"></section>'
                  b'<section data-card-tile="2"><img data-card-asset="background"></section>')
        spec = {"background": "/fake/background.png"}
        dims = {"tiles": 2}
        with patch.object(card, "data_uri", return_value="data:image/png;base64,FAKE") as mock_uri:
            result = card.authored_fragment(spec, dims, source)
        mock_uri.assert_called_once_with(spec["background"])
        self.assertEqual(result.count('src="data:image/png;base64,FAKE"'), 2)

    def test_layout_html_snapshot_overlap_findings_reported_and_no_manifest(self):
        frag = self.write_layout(layout([tile(1, title=self.spec["title"])]))
        spec = {**self.spec, "layout_html": str(frag)}
        out = self.work / "out"

        def fake_command(argv, **kwargs):
            data = ({"result": {"authored": True, "ok": False, "font": True, "checks": [],
                                 "findings": ["copy overlap"]}}
                    if "eval" in argv else {})
            return json.dumps({"success": True, "data": data}).encode()

        with patch.object(card, "command", fake_command):
            with self.assertRaisesRegex(ValueError, "copy overlap"):
                card.create(spec, out)
        self.assertFalse((out / "manifest.json").exists())

    def test_layout_html_invalid_fragment_rejected_before_browser_call(self):
        frag = self.write_layout(layout([]))  # no tile section at all
        spec = {**self.spec, "layout_html": str(frag)}
        out = self.work / "out"
        with self.assertRaises(ValueError), patch.object(card, "snapshot") as render:
            card.create(spec, out)
        render.assert_not_called()
        self.assertFalse(out.exists())

    def test_layout_html_source_freeze_and_hash(self):
        frag = self.write_layout(layout([tile(1, title=self.spec["title"])]))
        spec = {**self.spec, "layout_html": str(frag)}
        out = self.work / "out"
        expected_hash = hashlib.sha256(frag.read_bytes()).hexdigest()
        fake_report = {"dimensions": card.validate(spec, "create"), "master": {"sha256": "x"},
                        "ordered_tiles": [], "reassembly_rgba_equal": True, "spend": "free",
                        "visual_verdict": "unverified"}
        with patch.object(card, "snapshot", return_value={"ok": True}), \
             patch.object(card, "finish", return_value=fake_report):
            report = card.create(spec, out)
        self.assertTrue((out / "source-layout.html").is_file())
        self.assertEqual((out / "source-layout.html").read_bytes(), frag.read_bytes())
        self.assertEqual(report.get("layout_source_sha256"), expected_hash)
        manifest = json.loads((out / "manifest.json").read_text())
        self.assertEqual(manifest.get("layout_source_sha256"), expected_hash)


@unittest.skipUnless(os.environ.get("CARD_AUTHORED_SMOKE_DIR"),
                      "set CARD_AUTHORED_SMOKE_DIR to a NEW directory for real authored-layout browser smoke")
class CardAuthoredRenderSmoke(unittest.TestCase):
    """Live offline agent-browser smoke matrix. No external resources, no paid calls."""

    @classmethod
    def setUpClass(cls):
        cls.root = Path(os.environ["CARD_AUTHORED_SMOKE_DIR"])
        cls.root.mkdir(exist_ok=False)
        font_source = Path("/System/Library/Fonts/\u30d2\u30e9\u30ae\u30ce\u89d2\u30b4\u30b7\u30c3\u30af W6.ttc")
        cls.font = str(font_source) if font_source.is_file() else None

    def setUp(self):
        # Every test gets its own exclusive subdirectory under the single
        # setUpClass-created root; no test recreates the root itself.
        self.out = self.root / self._testMethodName
        self.out.mkdir(exist_ok=False)

    def _spec(self, layout_html, **extra):
        spec = {"title": "Think it through, say it clean.", "subtitle": "One clear next step.",
                "destination": "og", "style": "authored layout", "layout_html": str(layout_html)}
        if self.font:
            spec["font"] = self.font
        spec.update(extra)
        return spec

    def test_centered_cover_layout(self):
        frag = self.out / "cover.html"
        frag.write_text(
            '<style>.copy-area{position:absolute;inset:0;display:flex;flex-direction:column;'
            'justify-content:center;align-items:center;text-align:center}'
            '.copy-area h1{font-size:108px;margin:0}.copy-area p{font-size:72px;margin:24px 0 0}</style>'
            '<section data-card-tile="1"><div class="copy-area">'
            '<h1 data-card-copy="title">Think it through, say it clean.</h1>'
            '<p data-card-copy="subtitle">One clear next step.</p></div></section>'
        )
        spec = self._spec(frag, destination="1500x600")
        report = card.create(spec, self.out / "cover")
        self.assertTrue(report["reassembly_rgba_equal"])
        layout_check = json.loads((self.out / "cover/layout.json").read_text())
        self.assertTrue(layout_check["ok"])
        rows = {c["text"]: c for c in layout_check["checks"]}
        title_row = rows["Think it through, say it clean."]
        subtitle_row = rows["One clear next step."]
        self.assertEqual(title_row["font"], "108px")
        self.assertEqual(subtitle_row["font"], "72px")
        # Centered layout: both boxes' horizontal centers sit on the canvas
        # midline (1500px wide -> x=750), within 1px.
        self.assertAlmostEqual(title_row["x"] + title_row["width"] / 2, 750, delta=1)
        self.assertAlmostEqual(subtitle_row["x"] + subtitle_row["width"] / 2, 750, delta=1)
        # display_font_px scales the rendered font size to the 360px-wide
        # preview: 108*360/1500=25.92, 72*360/1500=17.28.
        self.assertAlmostEqual(title_row["display_font_px"], 25.92, places=2)
        self.assertAlmostEqual(subtitle_row["display_font_px"], 17.28, places=2)

    def test_asymmetrical_editorial_layout(self):
        # A short title/subtitle genuinely fit a 50%-wide (600px) column at
        # 100px/60px; the original longer sentence overflowed the column and
        # made this "should pass" case fail for real, not just illustratively.
        short_title = "A clear idea"
        frag = self.out / "editorial.html"
        frag.write_text(
            '<style>.copy-area{position:absolute;left:8%;top:12%;width:50%}'
            '.copy-area h1{font-size:100px;margin:0}.copy-area p{font-size:60px;margin:20px 0 0}</style>'
            '<section data-card-tile="1"><div class="copy-area">'
            f'<h1 data-card-copy="title">{short_title}</h1>'
            '<p data-card-copy="subtitle">One clear next step.</p></div></section>'
        )
        spec = self._spec(frag, destination="1200x630", title=short_title)
        report = card.create(spec, self.out / "editorial")
        self.assertTrue(report["reassembly_rgba_equal"])
        layout_check = json.loads((self.out / "editorial/layout.json").read_text())
        self.assertTrue(layout_check["ok"])
        rows = {c["text"]: c["font"] for c in layout_check["checks"]}
        self.assertEqual(rows.get(short_title), "100px")
        self.assertEqual(rows.get("One clear next step."), "60px")

    def test_display_none_title_fails_at_runtime_not_parse(self):
        frag = self.out / "hidden.html"
        frag.write_text(
            '<style>h1{display:none}</style>'
            '<section data-card-tile="1"><h1 data-card-copy="title">Think it through, say it clean.</h1></section>'
        )
        # subtitle="" -> not "requested", so no binding is expected for it and
        # this spec really reaches the browser runtime instead of failing
        # validate() on a missing subtitle binding.
        spec = self._spec(frag, subtitle="")
        card.validate(spec, "create")  # parses fine; the defect is runtime-only
        with self.assertRaises(ValueError):
            card.create(spec, self.out / "hidden")
        self.assertFalse((self.out / "hidden/manifest.json").exists())

    def test_unbound_pseudo_content_fails_at_runtime_not_parse(self):
        frag = self.out / "before.html"
        frag.write_text(
            '<style>.title::before{content:"Extra"}</style>'
            '<section data-card-tile="1"><h1 class="title" data-card-copy="title">'
            'Think it through, say it clean.</h1></section>'
        )
        spec = self._spec(frag, subtitle="")
        card.validate(spec, "create")  # parses fine; the defect is runtime-only
        with self.assertRaises(ValueError):
            card.create(spec, self.out / "before")
        self.assertFalse((self.out / "before/manifest.json").exists())

    def test_overlapping_bound_text_rejected_at_runtime(self):
        frag = self.out / "overlap.html"
        frag.write_text(
            # Same position, same font size, zero margin: title and
            # subtitle boxes are forced to genuinely coincide, not just
            # nominally share a CSS position that box-model/margins undo.
            '<style>.a,.b{position:absolute;left:10px;top:10px;margin:0;font-size:40px}</style>'
            '<section data-card-tile="1">'
            '<h1 class="a" data-card-copy="title">Think it through, say it clean.</h1>'
            '<p class="b" data-card-copy="subtitle">One clear next step.</p></section>'
        )
        spec = self._spec(frag)
        card.validate(spec, "create")  # parses fine; the defect is runtime-only
        with self.assertRaises(ValueError):
            card.create(spec, self.out / "overlap")
        self.assertFalse((self.out / "overlap/manifest.json").exists())

    def test_text_outside_canvas_rejected_at_runtime(self):
        frag = self.out / "offcanvas.html"
        frag.write_text(
            '<style>.copy-area{position:absolute;left:120%;top:0}</style>'
            '<section data-card-tile="1"><div class="copy-area">'
            '<h1 data-card-copy="title">Think it through, say it clean.</h1></div></section>'
        )
        spec = self._spec(frag, subtitle="")
        card.validate(spec, "create")  # parses fine; the defect is runtime-only
        with self.assertRaises(ValueError):
            card.create(spec, self.out / "offcanvas")
        self.assertFalse((self.out / "offcanvas/manifest.json").exists())

    def test_marker_generated_content_rejected_at_runtime(self):
        frag = self.out / "marker.html"
        frag.write_text(
            '<style>li::marker{content:"-"}</style>'
            '<section data-card-tile="1"><ul><li data-card-copy="title">'
            'Think it through, say it clean.</li></ul></section>'
        )
        spec = self._spec(frag, subtitle="")
        card.validate(spec, "create")  # parses fine; the defect is runtime-only
        with self.assertRaises(ValueError):
            card.create(spec, self.out / "marker")
        self.assertFalse((self.out / "marker/manifest.json").exists())

    def test_compact_two_letter_title_readable_at_80px(self):
        # Uses the same font resolution as every other smoke case (system
        # default via self.font); not a new "Arial" or other private asset.
        frag = self.out / "compact.html"
        frag.write_text(
            '<style>.copy-area{position:absolute;inset:0;display:flex;align-items:center;'
            'justify-content:center}.copy-area h1{font-size:80px;margin:0}</style>'
            '<section data-card-tile="1"><div class="copy-area">'
            '<h1 data-card-copy="title">AB</h1></div></section>'
        )
        spec = self._spec(frag, title="AB", subtitle="")
        report = card.create(spec, self.out / "compact")
        self.assertTrue(report["reassembly_rgba_equal"])
        layout_check = json.loads((self.out / "compact/layout.json").read_text())
        self.assertTrue(layout_check["ok"])
        rows = {c["text"]: c["font"] for c in layout_check["checks"]}
        self.assertEqual(rows.get("AB"), "80px")

    def test_scaled_to_zero_text_rejected_at_runtime(self):
        frag = self.out / "scale-zero.html"
        frag.write_text(
            '<style>.hidden-scale{display:inline-block;transform:scale(0)}</style>'
            '<section data-card-tile="1"><h1 data-card-copy="title">'
            'Visible <span class="hidden-scale">hidden text</span></h1></section>'
        )
        spec = self._spec(frag, title="Visible hidden text", subtitle="")
        card.validate(spec, "create")  # parses fine; the defect is runtime-only
        with self.assertRaises(ValueError):
            card.create(spec, self.out / "scale-zero")
        self.assertFalse((self.out / "scale-zero/manifest.json").exists())

    def test_clipped_overflow_hidden_text_rejected_at_runtime(self):
        frag = self.out / "clip.html"
        frag.write_text(
            '<style>.clip{display:inline-block;width:1px;overflow:hidden;white-space:nowrap;'
            'font-size:40px}</style>'
            '<section data-card-tile="1"><h1 data-card-copy="title">'
            '<span class="clip">Think it through, say it clean.</span></h1></section>'
        )
        spec = self._spec(frag, subtitle="")
        card.validate(spec, "create")  # parses fine; the defect is runtime-only
        with self.assertRaises(ValueError):
            card.create(spec, self.out / "clip")
        self.assertFalse((self.out / "clip/manifest.json").exists())

    def test_decorative_hidden_span_does_not_fail(self):
        frag = self.out / "decorative.html"
        frag.write_text(
            '<style>.deco{display:none}</style>'
            '<section data-card-tile="1"><h1 data-card-copy="title">'
            'Think it through, say it clean.<span class="deco"></span></h1></section>'
        )
        spec = self._spec(frag, subtitle="")
        report = card.create(spec, self.out / "decorative")
        self.assertTrue(report["reassembly_rgba_equal"])
        layout_check = json.loads((self.out / "decorative/layout.json").read_text())
        self.assertTrue(layout_check["ok"])

    def test_text_transform_uppercase_rejected_by_innertext_exactness(self):
        # Empirical: innerText reflects rendered text-transform, so the
        # visible text no longer equals the literal bound spec value. If a
        # real browser run disagrees, report it -- do not change production
        # to paper over the discrepancy.
        frag = self.out / "uppercase.html"
        frag.write_text(
            '<style>.title{text-transform:uppercase}</style>'
            '<section data-card-tile="1"><h1 class="title" data-card-copy="title">'
            'Think it through, say it clean.</h1></section>'
        )
        spec = self._spec(frag, subtitle="")
        card.validate(spec, "create")  # parses fine; the defect is runtime-only
        with self.assertRaises(ValueError):
            card.create(spec, self.out / "uppercase")
        self.assertFalse((self.out / "uppercase/manifest.json").exists())


if __name__ == "__main__":
    unittest.main()

