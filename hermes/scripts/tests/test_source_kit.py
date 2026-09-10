"""Tests for the `source-kit` hands leaf's fetcher: kenney-fetch.py.

All network access is mocked or monkeypatched — nothing here reaches the
internet. A separate, manual live smoke fetch is documented in the leaf's
worker report rather than run from this suite (see AGENTS.md: "Network
tests fixture-based not CI internet").
"""
from __future__ import annotations

import importlib.util
import io
import json
import os
import stat
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest import mock


HERMES_ROOT = Path(__file__).resolve().parents[2]
SCRIPT_PATH = (
    HERMES_ROOT
    / "profiles"
    / "image-creator"
    / "skills"
    / "image-creator-pipeline"
    / "source"
    / "kit"
    / "scripts"
    / "kenney-fetch.py"
)


def load_module():
    spec = importlib.util.spec_from_file_location("kenney_fetch", SCRIPT_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load {SCRIPT_PATH}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


kf = load_module()


# ── fixtures ────────────────────────────────────────────────────────────

SEARCH_PAGE_FIXTURE = """
<html><body>
<div class='results'>
  <div class='asset'>
    <a href='https://kenney.nl/assets/game-icons'><div class='cover'></div></a>
    <h2><a href='https://kenney.nl/assets/game-icons'>Game Icons</a></h2>
  </div>
  <div class='asset'>
    <a href='https://kenney.nl/assets/ui-pack'><div class='cover'></div></a>
    <h2><a href='https://kenney.nl/assets/ui-pack'>UI Pack</a></h2>
  </div>
</div>
<ul class='pagination'>
  <li><a href='https://kenney.nl/assets/page:2?search=x'>2</a></li>
</ul>
</body></html>
"""

PACK_PAGE_FIXTURE_CC0 = """
<html><head><title>Game Icons &middot; Kenney</title></head><body>
<h1 class='mobile-text-center'>Game Icons</h1>
<table>
  <tr><td>License</td>
      <td><a href='https://creativecommons.org/publicdomain/zero/1.0/' target='_blank'>Creative Commons CC0</a></td></tr>
</table>
<p><a id='donate-text' href='https://kenney.nl/media/pages/assets/game-icons/abc123/kenney_game-icons.zip'>Continue without donating...</a></p>
<h1>Consider a donation</h1>
</body></html>
"""

PACK_PAGE_FIXTURE_NO_LICENSE = """
<html><body>
<h1>Mystery Pack</h1>
<p><a href='https://kenney.nl/media/pages/assets/mystery-pack/z/kenney_mystery-pack.zip'>download</a></p>
</body></html>
"""

PACK_PAGE_FIXTURE_OTHER_LICENSE = """
<html><body>
<h1>Other License Pack</h1>
<table><tr><td><a href='https://creativecommons.org/licenses/by/4.0/'>CC BY 4.0</a></td></tr></table>
<p><a href='https://kenney.nl/media/pages/assets/other-license-pack/z/kenney_other.zip'>download</a></p>
</body></html>
"""

PACK_PAGE_FIXTURE_RELATIVE_ZIP = """
<html><body>
<h1>Relative Pack</h1>
<table><tr><td><a href='https://creativecommons.org/publicdomain/zero/1.0/'>CC0</a></td></tr></table>
<p><a href='/media/pages/assets/relative-pack/z/kenney_relative-pack.zip'>download</a></p>
</body></html>
"""

PACK_PAGE_FIXTURE_WRONG_HOST_ZIP = """
<html><body>
<h1>Evil Pack</h1>
<table><tr><td><a href='https://creativecommons.org/publicdomain/zero/1.0/'>CC0</a></td></tr></table>
<p><a href='https://evil.example.com/kenney_evil-pack.zip'>download</a></p>
</body></html>
"""


def build_zip_bytes(entries: dict[str, bytes], *, symlinks: dict[str, str] | None = None) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        for name, data in entries.items():
            zf.writestr(name, data)
        for name, target in (symlinks or {}).items():
            info = zipfile.ZipInfo(name)
            info.external_attr = (stat.S_IFLNK | 0o777) << 16
            zf.writestr(info, target)
    return buf.getvalue()


GAME_ICONS_ZIP = build_zip_bytes(
    {
        "license.txt": b"Kenney assets are CC0 (public domain)...\n",
        "PNG/Black/1x/arrowDown.png": b"\x89PNGfakepng1",
        "PNG/Black/1x/arrowUp.png": b"\x89PNGfakepng2",
        "Vector/arrowDown.svg": b"<svg>fake</svg>",
        "Spritesheet/sheet.xml": b"<xml/>",
        "preview.png": b"\x89PNGfakepreview",
    }
)


# ── HTML parsers ──────────────────────────────────────────────────────────


class SearchResultsParserTest(unittest.TestCase):
    def test_extracts_slug_and_title_from_h2_cards_only(self) -> None:
        parser = kf.SearchResultsParser()
        parser.feed(SEARCH_PAGE_FIXTURE)
        self.assertEqual(
            parser.results,
            [("game-icons", "Game Icons"), ("ui-pack", "UI Pack")],
        )

    def test_pagination_links_outside_h2_are_ignored(self) -> None:
        parser = kf.SearchResultsParser()
        parser.feed(SEARCH_PAGE_FIXTURE)
        slugs = [slug for slug, _ in parser.results]
        self.assertNotIn("page:2", slugs)


class PackPageParserTest(unittest.TestCase):
    def test_finds_title_zip_and_cc0(self) -> None:
        parser = kf.PackPageParser()
        parser.feed(PACK_PAGE_FIXTURE_CC0)
        self.assertEqual(parser.title, "Game Icons")
        self.assertTrue(parser.cc0_seen)
        self.assertEqual(
            parser.zip_hrefs,
            ["https://kenney.nl/media/pages/assets/game-icons/abc123/kenney_game-icons.zip"],
        )

    def test_second_h1_does_not_override_title(self) -> None:
        parser = kf.PackPageParser()
        parser.feed(PACK_PAGE_FIXTURE_CC0)
        self.assertEqual(parser.title, "Game Icons")  # not "Consider a donation"

    def test_flags_non_cc0_creativecommons_link(self) -> None:
        parser = kf.PackPageParser()
        parser.feed(PACK_PAGE_FIXTURE_OTHER_LICENSE)
        self.assertFalse(parser.cc0_seen)
        self.assertEqual(parser.other_cc_hrefs, ["https://creativecommons.org/licenses/by/4.0/"])


# ── license verification ───────────────────────────────────────────────────


class VerifyCc0Test(unittest.TestCase):
    def test_accepts_verified_cc0_page(self) -> None:
        parser = kf.PackPageParser()
        parser.feed(PACK_PAGE_FIXTURE_CC0)
        kf.verify_cc0("https://kenney.nl/assets/game-icons", parser)  # no raise

    def test_rejects_missing_license_link(self) -> None:
        parser = kf.PackPageParser()
        parser.feed(PACK_PAGE_FIXTURE_NO_LICENSE)
        with self.assertRaises(kf.FetchError):
            kf.verify_cc0("https://kenney.nl/assets/mystery-pack", parser)

    def test_rejects_non_cc0_license(self) -> None:
        parser = kf.PackPageParser()
        parser.feed(PACK_PAGE_FIXTURE_OTHER_LICENSE)
        with self.assertRaises(kf.FetchError):
            kf.verify_cc0("https://kenney.nl/assets/other-license-pack", parser)


# ── zip url resolution / host allowlist ────────────────────────────────────


class ResolveZipUrlTest(unittest.TestCase):
    def test_resolves_absolute_media_zip(self) -> None:
        parser = kf.PackPageParser()
        parser.feed(PACK_PAGE_FIXTURE_CC0)
        url = kf.resolve_zip_url("https://kenney.nl/assets/game-icons", parser)
        self.assertEqual(
            url, "https://kenney.nl/media/pages/assets/game-icons/abc123/kenney_game-icons.zip"
        )

    def test_resolves_relative_zip_href_via_urljoin(self) -> None:
        parser = kf.PackPageParser()
        parser.feed(PACK_PAGE_FIXTURE_RELATIVE_ZIP)
        url = kf.resolve_zip_url("https://kenney.nl/assets/relative-pack", parser)
        self.assertEqual(
            url, "https://kenney.nl/media/pages/assets/relative-pack/z/kenney_relative-pack.zip"
        )

    def test_rejects_off_host_zip_link(self) -> None:
        parser = kf.PackPageParser()
        parser.feed(PACK_PAGE_FIXTURE_WRONG_HOST_ZIP)
        with self.assertRaises(kf.FetchError):
            kf.resolve_zip_url("https://kenney.nl/assets/evil-pack", parser)

    def test_rejects_zip_under_a_different_slugs_media_path(self) -> None:
        parser = kf.PackPageParser()
        parser.feed(PACK_PAGE_FIXTURE_CC0)  # zip lives under .../game-icons/...
        with self.assertRaises(kf.FetchError):
            kf.resolve_zip_url("https://kenney.nl/assets/some-other-slug", parser)

    def test_no_zip_link_at_all_raises(self) -> None:
        parser = kf.PackPageParser()
        parser.feed("<html><body><h1>Empty</h1></body></html>")
        with self.assertRaises(kf.FetchError):
            kf.resolve_zip_url("https://kenney.nl/assets/empty", parser)


class HostAllowlistTest(unittest.TestCase):
    def test_https_get_rejects_non_kenney_host(self) -> None:
        with self.assertRaises(kf.FetchError):
            kf._https_get("https://evil.example.com/x", timeout=1, max_bytes=100)

    def test_https_get_rejects_plain_http(self) -> None:
        with self.assertRaises(kf.FetchError):
            kf._https_get("http://kenney.nl/assets", timeout=1, max_bytes=100)

    def test_download_zip_rejects_non_kenney_host(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            with self.assertRaises(kf.FetchError):
                kf._download_zip("https://evil.example.com/x.zip", os.path.join(d, "x.zip"))

    def test_fetch_pack_page_rejects_bad_slug_without_network(self) -> None:
        with mock.patch.object(kf, "_https_get", side_effect=AssertionError("must not fetch")):
            with self.assertRaises(kf.FetchError):
                kf.fetch_pack_page("../etc/passwd")
            with self.assertRaises(kf.FetchError):
                kf.fetch_pack_page("Game_Icons!")


# ── zip member name safety ─────────────────────────────────────────────────


class ValidateMemberNameTest(unittest.TestCase):
    def test_accepts_normal_relative_path(self) -> None:
        self.assertEqual(kf._validate_member_name("PNG/Black/1x/arrowDown.png"), "PNG/Black/1x/arrowDown.png")

    def test_rejects_absolute_path(self) -> None:
        with self.assertRaises(kf.FetchError):
            kf._validate_member_name("/etc/passwd")

    def test_rejects_parent_traversal(self) -> None:
        with self.assertRaises(kf.FetchError):
            kf._validate_member_name("../../etc/passwd")

    def test_rejects_traversal_hidden_after_normal_component(self) -> None:
        with self.assertRaises(kf.FetchError):
            kf._validate_member_name("PNG/../../etc/passwd")

    def test_rejects_backslash_separator(self) -> None:
        with self.assertRaises(kf.FetchError):
            kf._validate_member_name("PNG\\Black\\arrow.png")

    def test_rejects_nul_byte(self) -> None:
        with self.assertRaises(kf.FetchError):
            kf._validate_member_name("PNG/arrow.png\x00.exe")

    def test_rejects_drive_letter(self) -> None:
        with self.assertRaises(kf.FetchError):
            kf._validate_member_name("C:/Windows/System32/evil.dll")


# ── malicious zip fixtures ──────────────────────────────────────────────────


class InspectZipTest(unittest.TestCase):
    def _write(self, tmpdir: str, data: bytes) -> str:
        path = os.path.join(tmpdir, "test.zip")
        with open(path, "wb") as fh:
            fh.write(data)
        return path

    def test_accepts_clean_zip(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            path = self._write(d, GAME_ICONS_ZIP)
            zf = kf.inspect_zip(path)
            try:
                self.assertGreater(len(zf.infolist()), 0)
            finally:
                zf.close()

    def test_rejects_traversal_entry(self) -> None:
        evil = build_zip_bytes({"../evil.txt": b"pwned"})
        with tempfile.TemporaryDirectory() as d:
            path = self._write(d, evil)
            with self.assertRaises(kf.FetchError):
                kf.inspect_zip(path)

    def test_rejects_absolute_entry(self) -> None:
        evil = build_zip_bytes({"/etc/passwd": b"pwned"})
        with tempfile.TemporaryDirectory() as d:
            path = self._write(d, evil)
            with self.assertRaises(kf.FetchError):
                kf.inspect_zip(path)

    def test_rejects_symlink_entry(self) -> None:
        evil = build_zip_bytes({"PNG/a.png": b"ok"}, symlinks={"PNG/evil-link.png": "/etc/passwd"})
        with tempfile.TemporaryDirectory() as d:
            path = self._write(d, evil)
            with self.assertRaises(kf.FetchError):
                kf.inspect_zip(path)

    def test_rejects_too_many_entries(self) -> None:
        many = build_zip_bytes({f"file{i}.png": b"x" for i in range(10)})
        with tempfile.TemporaryDirectory() as d:
            path = self._write(d, many)
            with mock.patch.object(kf, "MAX_ZIP_ENTRIES", 5):
                with self.assertRaises(kf.FetchError):
                    kf.inspect_zip(path)

    def test_corrupt_zip_raises_a_clean_fetch_error(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            path = self._write(d, b"this is not a zip file at all, just garbage bytes")
            with self.assertRaises(kf.FetchError) as ctx:
                kf.inspect_zip(path)
            self.assertIn("corrupt zip", str(ctx.exception))

    def test_truncated_zip_raises_a_clean_fetch_error(self) -> None:
        # A zip with a valid-looking local header but a truncated body/
        # missing central directory — BadZipFile at open(), not a generic
        # traceback.
        with tempfile.TemporaryDirectory() as d:
            path = self._write(d, GAME_ICONS_ZIP[: len(GAME_ICONS_ZIP) // 2])
            with self.assertRaises(kf.FetchError) as ctx:
                kf.inspect_zip(path)
            self.assertIn("corrupt zip", str(ctx.exception))


# ── member selection (--pick) ────────────────────────────────────────────


class SelectMembersTest(unittest.TestCase):
    def _open(self, data: bytes) -> zipfile.ZipFile:
        return zipfile.ZipFile(io.BytesIO(data))

    def test_default_picks_only_png_and_svg(self) -> None:
        zf = self._open(GAME_ICONS_ZIP)
        picked, license_files = kf.select_members(zf, kf.DEFAULT_PICKS, require_each_match=False)
        names = sorted(m.filename for m in picked)
        self.assertEqual(
            names,
            [
                "PNG/Black/1x/arrowDown.png",
                "PNG/Black/1x/arrowUp.png",
                "Vector/arrowDown.svg",
                "preview.png",
            ],
        )
        self.assertEqual([m.filename for m in license_files], ["license.txt"])

    def test_explicit_pick_matches_only_requested_glob(self) -> None:
        zf = self._open(GAME_ICONS_ZIP)
        picked, _ = kf.select_members(zf, ("PNG/*.png",))
        names = sorted(m.filename for m in picked)
        self.assertEqual(names, ["PNG/Black/1x/arrowDown.png", "PNG/Black/1x/arrowUp.png"])

    def test_pick_with_no_matches_raises(self) -> None:
        zf = self._open(GAME_ICONS_ZIP)
        with self.assertRaises(kf.FetchError):
            kf.select_members(zf, ("Audio/*.ogg",))

    def test_default_uppercase_variant_with_no_matches_is_not_an_error(self) -> None:
        # *.PNG / *.SVG (upper-case) match nothing in this fixture, but the
        # default set as a whole still selects the lower-case files.
        zf = self._open(GAME_ICONS_ZIP)
        picked, _ = kf.select_members(zf, kf.DEFAULT_PICKS, require_each_match=False)
        self.assertTrue(any(m.filename.endswith(".png") for m in picked))

    def test_default_picks_raise_if_the_whole_set_matches_nothing(self) -> None:
        data = build_zip_bytes({"Audio/beep.ogg": b"x", "license.txt": b"CC0"})
        zf = self._open(data)
        with self.assertRaises(kf.FetchError):
            kf.select_members(zf, kf.DEFAULT_PICKS, require_each_match=False)

    def test_license_file_is_included_even_when_not_picked(self) -> None:
        zf = self._open(GAME_ICONS_ZIP)
        picked, license_files = kf.select_members(zf, ("Vector/*.svg",))
        self.assertEqual([m.filename for m in picked], ["Vector/arrowDown.svg"])
        self.assertEqual([m.filename for m in license_files], ["license.txt"])

    def test_nested_readme_and_license_files_are_preserved_at_any_depth(self) -> None:
        # A pack's terms can be embedded inside a subdirectory, not only at
        # the archive root — LICENSE_NAME_RE matches on basename, so this
        # must not require a top-level location.
        data = build_zip_bytes(
            {
                "PNG/icon.png": b"x",
                "docs/README.txt": b"how to use this pack",
                "docs/sub/LICENSE": b"CC0 terms",
                "fonts/COPYRIGHT.md": b"font copyright notice",
            }
        )
        zf = self._open(data)
        picked, license_files = kf.select_members(zf, ("PNG/*.png",))
        self.assertEqual([m.filename for m in picked], ["PNG/icon.png"])
        self.assertEqual(
            sorted(m.filename for m in license_files),
            sorted(["docs/README.txt", "docs/sub/LICENSE", "fonts/COPYRIGHT.md"]),
        )

    def test_top_level_license_still_matches(self) -> None:
        data = build_zip_bytes({"PNG/icon.png": b"x", "LICENSE.txt": b"CC0"})
        zf = self._open(data)
        _, license_files = kf.select_members(zf, ("PNG/*.png",))
        self.assertEqual([m.filename for m in license_files], ["LICENSE.txt"])

    def test_unrelated_file_named_licensed_report_is_not_matched(self) -> None:
        # LICENSE_NAME_RE anchors the basename so "licensed-report.pdf"
        # (a real word starting with "licens") is not swept in by accident.
        data = build_zip_bytes({"PNG/icon.png": b"x", "docs/licensed-report.pdf": b"x"})
        zf = self._open(data)
        _, license_files = kf.select_members(zf, ("PNG/*.png",))
        self.assertEqual(license_files, [])

    def test_rejects_case_insensitive_duplicate_destination(self) -> None:
        data = build_zip_bytes(
            {
                "Assets/Icon.png": b"a",
                "assets/icon.png": b"b",
            }
        )
        zf = self._open(data)
        with self.assertRaises(kf.FetchError):
            kf.select_members(zf, ("Assets/Icon.png", "assets/icon.png"))

    def test_rejects_over_member_count_cap(self) -> None:
        zf = self._open(GAME_ICONS_ZIP)
        with mock.patch.object(kf, "MAX_SELECTED_MEMBERS", 1):
            with self.assertRaises(kf.FetchError):
                kf.select_members(zf, kf.DEFAULT_PICKS, require_each_match=False)

    def test_rejects_over_uncompressed_size_cap(self) -> None:
        zf = self._open(GAME_ICONS_ZIP)
        with mock.patch.object(kf, "MAX_SELECTED_UNCOMPRESSED_BYTES", 1):
            with self.assertRaises(kf.FetchError):
                kf.select_members(zf, kf.DEFAULT_PICKS, require_each_match=False)


# ── dedup helper ──────────────────────────────────────────────────────────


class DedupPreserveOrderTest(unittest.TestCase):
    def test_dedups_by_identity_preserving_first_seen_order(self) -> None:
        zf = zipfile.ZipFile(io.BytesIO(GAME_ICONS_ZIP))
        infos = zf.infolist()
        a, b = infos[0], infos[1]
        result = kf._dedup_preserve_order([a, b, a, b, a])
        self.assertEqual(len(result), 2)
        self.assertIs(result[0], a)
        self.assertIs(result[1], b)

    def test_empty_and_no_duplicates_pass_through(self) -> None:
        self.assertEqual(kf._dedup_preserve_order([]), [])
        zf = zipfile.ZipFile(io.BytesIO(GAME_ICONS_ZIP))
        infos = zf.infolist()[:2]
        self.assertEqual(kf._dedup_preserve_order(infos), infos)


# ── license evidence vs. reference documents ────────────────────────────


class ClassifyLicenseFilesTest(unittest.TestCase):
    def _infos(self, data: bytes) -> dict[str, zipfile.ZipInfo]:
        zf = zipfile.ZipFile(io.BytesIO(data))
        return {i.filename: i for i in zf.infolist()}

    def test_single_license_file_is_the_evidence(self) -> None:
        infos = self._infos(build_zip_bytes({"license.txt": b"CC0"}))
        evidence, references = kf.classify_license_files([infos["license.txt"]])
        self.assertIs(evidence, infos["license.txt"])
        self.assertEqual(references, [])

    def test_license_preferred_over_readme_regardless_of_zip_order(self) -> None:
        # README stored BEFORE the license file in the archive's central
        # directory — evidence selection must not take license_files[0].
        data = build_zip_bytes({"README.txt": b"how to use", "LICENSE.txt": b"CC0 terms"})
        infos = self._infos(data)
        license_files = [infos["README.txt"], infos["LICENSE.txt"]]  # central-dir order
        evidence, references = kf.classify_license_files(license_files)
        self.assertIs(evidence, infos["LICENSE.txt"])
        self.assertEqual(references, [infos["README.txt"]])

    def test_readme_only_yields_no_evidence(self) -> None:
        infos = self._infos(build_zip_bytes({"README.md": b"just docs"}))
        evidence, references = kf.classify_license_files([infos["README.md"]])
        self.assertIsNone(evidence)
        self.assertEqual(references, [infos["README.md"]])

    def test_shallower_path_wins_over_deeper_license_file(self) -> None:
        data = build_zip_bytes({"docs/sub/LICENSE": b"nested", "LICENSE.txt": b"root"})
        infos = self._infos(data)
        # Deliberately pass the deeper one first to prove order doesn't matter.
        license_files = [infos["docs/sub/LICENSE"], infos["LICENSE.txt"]]
        evidence, references = kf.classify_license_files(license_files)
        self.assertIs(evidence, infos["LICENSE.txt"])
        self.assertEqual(references, [infos["docs/sub/LICENSE"]])

    def test_same_depth_ties_broken_lexicographically(self) -> None:
        data = build_zip_bytes({"LICENSE": b"l", "COPYRIGHT": b"c"})
        infos = self._infos(data)
        license_files = [infos["LICENSE"], infos["COPYRIGHT"]]
        evidence, references = kf.classify_license_files(license_files)
        self.assertIs(evidence, infos["COPYRIGHT"])  # "COPYRIGHT" < "LICENSE"
        self.assertEqual(references, [infos["LICENSE"]])

    def test_no_license_files_at_all(self) -> None:
        evidence, references = kf.classify_license_files([])
        self.assertIsNone(evidence)
        self.assertEqual(references, [])

    def test_multiple_readmes_are_all_kept_as_references_sorted(self) -> None:
        data = build_zip_bytes({"b/README.txt": b"b", "a/README.txt": b"a"})
        infos = self._infos(data)
        license_files = [infos["b/README.txt"], infos["a/README.txt"]]
        evidence, references = kf.classify_license_files(license_files)
        self.assertIsNone(evidence)
        self.assertEqual(references, [infos["a/README.txt"], infos["b/README.txt"]])


# ── extraction ──────────────────────────────────────────────────────────


class ExtractSelectedTest(unittest.TestCase):
    def test_writes_files_under_assets_preserving_archive_relative_paths(self) -> None:
        zf = zipfile.ZipFile(io.BytesIO(GAME_ICONS_ZIP))
        picked, license_files = kf.select_members(zf, ("PNG/*.png",))
        with tempfile.TemporaryDirectory() as staging:
            written = kf.extract_selected(zf, picked + license_files, staging)
            pairs = dict(written)
            self.assertEqual(pairs["license.txt"], "assets/license.txt")
            self.assertEqual(
                pairs["PNG/Black/1x/arrowDown.png"], "assets/PNG/Black/1x/arrowDown.png"
            )
            for archive_path, output_path in written:
                self.assertTrue(output_path.startswith("assets/"))
                self.assertEqual(output_path, f"assets/{archive_path}")
                full = os.path.join(staging, *output_path.split("/"))
                self.assertTrue(os.path.isfile(full))
            # Nothing is written directly under staging outside assets/.
            self.assertEqual(os.listdir(staging), ["assets"])


# ── output directory guards ──────────────────────────────────────────────


class PrepareStagingTest(unittest.TestCase):
    def test_rejects_symlinked_out_dir(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            real = os.path.join(d, "real")
            os.mkdir(real)
            link = os.path.join(d, "link")
            os.symlink(real, link)
            with self.assertRaises(kf.FetchError):
                kf.prepare_staging(link)

    def test_rejects_nonempty_existing_dir(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            out = os.path.join(d, "out")
            os.mkdir(out)
            Path(out, "already-here.txt").write_text("x")
            with self.assertRaises(kf.FetchError):
                kf.prepare_staging(out)

    def test_accepts_empty_existing_dir_and_publishes_into_it(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            out = os.path.join(d, "out")
            os.mkdir(out)
            staging = kf.prepare_staging(out)
            Path(staging, "a.txt").write_text("hi")
            kf.publish_staging(staging, out)
            self.assertTrue(Path(out, "a.txt").is_file())

    def test_rejects_missing_parent_directory(self) -> None:
        with self.assertRaises(kf.FetchError):
            kf.prepare_staging("/no/such/parent/dir/out")


# ── end-to-end do_pack with a mocked network ────────────────────────────


class DoPackEndToEndTest(unittest.TestCase):
    def _fake_page(self):
        parser = kf.PackPageParser()
        parser.feed(PACK_PAGE_FIXTURE_CC0)
        return "https://kenney.nl/assets/game-icons", parser

    def test_extracts_default_pngs_and_writes_provenance(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            out = os.path.join(d, "deliver")

            def fake_download(url, dest_path):
                with open(dest_path, "wb") as fh:
                    fh.write(GAME_ICONS_ZIP)
                import hashlib

                return hashlib.sha256(GAME_ICONS_ZIP).hexdigest(), len(GAME_ICONS_ZIP)

            with mock.patch.object(kf, "fetch_pack_page", return_value=self._fake_page()), \
                 mock.patch.object(kf, "_download_zip", side_effect=fake_download):
                rc = kf.do_pack("game-icons", out, ())
            self.assertEqual(rc, 0)

            provenance = json.loads(Path(out, "provenance.json").read_text())
            self.assertEqual(provenance["pack"]["slug"], "game-icons")
            self.assertEqual(provenance["license"]["spdx"], "CC0-1.0")
            self.assertTrue(provenance["license"]["verified_on_page"])
            self.assertEqual(provenance["assets_dir"], "assets")
            self.assertEqual(
                provenance["license"]["archive_license_file_output_path"], "assets/license.txt"
            )

            by_archive_path = {e["archive_path"]: e["output_path"] for e in provenance["selected_files"]}
            self.assertEqual(
                by_archive_path["PNG/Black/1x/arrowDown.png"],
                "assets/PNG/Black/1x/arrowDown.png",
            )
            self.assertNotIn("Spritesheet/sheet.xml", by_archive_path)

            # provenance.json and LICENSE.source.txt sit at <out>'s root, next
            # to assets/, never inside it.
            self.assertTrue(Path(out, "LICENSE.source.txt").exists())
            self.assertFalse(Path(out, "assets", "LICENSE.source.txt").exists())
            self.assertFalse(Path(out, "assets", "provenance.json").exists())

            # every selected file actually lands under <out>/assets/...
            self.assertTrue(Path(out, "assets", "PNG/Black/1x/arrowDown.png").exists())
            self.assertTrue(Path(out, "assets", "license.txt").exists())
            self.assertFalse(Path(out, "PNG/Black/1x/arrowDown.png").exists())

    def test_broad_pick_matching_license_file_is_not_double_extracted(self) -> None:
        # --pick '*' matches everything, including license.txt, which is
        # ALSO separately matched by LICENSE_NAME_RE — extraction must not
        # write it twice, and selected_count/selected_files must not
        # double-count it.
        with tempfile.TemporaryDirectory() as d:
            out = os.path.join(d, "deliver")

            def fake_download(url, dest_path):
                with open(dest_path, "wb") as fh:
                    fh.write(GAME_ICONS_ZIP)
                import hashlib

                return hashlib.sha256(GAME_ICONS_ZIP).hexdigest(), len(GAME_ICONS_ZIP)

            with mock.patch.object(kf, "fetch_pack_page", return_value=self._fake_page()), \
                 mock.patch.object(kf, "_download_zip", side_effect=fake_download):
                rc = kf.do_pack("game-icons", out, ("*",))
            self.assertEqual(rc, 0)

            provenance = json.loads(Path(out, "provenance.json").read_text())
            archive_paths = [e["archive_path"] for e in provenance["selected_files"]]
            self.assertEqual(len(archive_paths), len(set(archive_paths)))
            self.assertEqual(provenance["selected_count"], len(archive_paths))

            with zipfile.ZipFile(io.BytesIO(GAME_ICONS_ZIP)) as zf:
                expected = {i.filename for i in zf.infolist() if not i.is_dir()}
            self.assertEqual(set(archive_paths), expected)

            # Written to disk exactly once.
            license_copies = list(Path(out, "assets").rglob("license.txt"))
            self.assertEqual(len(license_copies), 1)

    def test_readme_only_archive_is_not_labeled_as_license(self) -> None:
        readme_only_zip = build_zip_bytes(
            {
                "README.txt": b"Read this before use.",
                "PNG/icon.png": b"\x89PNGdata",
            }
        )

        def fake_download(url, dest_path):
            with open(dest_path, "wb") as fh:
                fh.write(readme_only_zip)
            import hashlib

            return hashlib.sha256(readme_only_zip).hexdigest(), len(readme_only_zip)

        with tempfile.TemporaryDirectory() as d:
            out = os.path.join(d, "deliver")
            with mock.patch.object(kf, "fetch_pack_page", return_value=self._fake_page()), \
                 mock.patch.object(kf, "_download_zip", side_effect=fake_download):
                rc = kf.do_pack("game-icons", out, ())
            self.assertEqual(rc, 0)

            provenance = json.loads(Path(out, "provenance.json").read_text())
            lic = provenance["license"]
            self.assertIsNone(lic["archive_license_file"])
            self.assertIsNone(lic["archive_license_file_output_path"])
            self.assertEqual(
                lic["reference_documents"],
                [{"archive_path": "README.txt", "output_path": "assets/README.txt"}],
            )
            # The page's verified CC0 evidence is untouched by the archive
            # carrying only a README.
            self.assertTrue(lic["verified_on_page"])
            self.assertEqual(lic["spdx"], "CC0-1.0")

            # README is still extracted (preserved), just not quoted as license.
            self.assertTrue(Path(out, "assets", "README.txt").exists())

            license_source = Path(out, "LICENSE.source.txt").read_text()
            self.assertIn("NOT quoted as license text", license_source)
            self.assertIn("README.txt", license_source)
            self.assertNotIn("Read this before use.", license_source)

    def test_nested_readme_before_root_license_still_picks_the_license(self) -> None:
        # README stored FIRST in the zip's central directory, at a deeper
        # path; the root LICENSE.txt must still win as evidence — proving
        # selection does not take license_files[0] in archive order.
        mixed_zip = build_zip_bytes(
            {
                "docs/README.txt": b"read me first",
                "LICENSE.txt": b"CC0 terms, verbatim",
                "PNG/icon.png": b"\x89PNGdata",
            }
        )

        def fake_download(url, dest_path):
            with open(dest_path, "wb") as fh:
                fh.write(mixed_zip)
            import hashlib

            return hashlib.sha256(mixed_zip).hexdigest(), len(mixed_zip)

        with tempfile.TemporaryDirectory() as d:
            out = os.path.join(d, "deliver")
            with mock.patch.object(kf, "fetch_pack_page", return_value=self._fake_page()), \
                 mock.patch.object(kf, "_download_zip", side_effect=fake_download):
                kf.do_pack("game-icons", out, ())

            provenance = json.loads(Path(out, "provenance.json").read_text())
            lic = provenance["license"]
            self.assertEqual(lic["archive_license_file"], "LICENSE.txt")
            self.assertEqual(lic["archive_license_file_output_path"], "assets/LICENSE.txt")
            self.assertEqual(
                lic["reference_documents"],
                [{"archive_path": "docs/README.txt", "output_path": "assets/docs/README.txt"}],
            )

            license_source = Path(out, "LICENSE.source.txt").read_text()
            self.assertIn("CC0 terms, verbatim", license_source)

            # Both files preserved on disk regardless of which is "the" evidence.
            self.assertTrue(Path(out, "assets", "LICENSE.txt").exists())
            self.assertTrue(Path(out, "assets", "docs", "README.txt").exists())

    def test_refuses_to_publish_into_existing_nonempty_output(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            out = os.path.join(d, "deliver")
            os.mkdir(out)
            Path(out, "prior.txt").write_text("already delivered")

            def fake_download(url, dest_path):
                with open(dest_path, "wb") as fh:
                    fh.write(GAME_ICONS_ZIP)
                import hashlib

                return hashlib.sha256(GAME_ICONS_ZIP).hexdigest(), len(GAME_ICONS_ZIP)

            with mock.patch.object(kf, "fetch_pack_page", return_value=self._fake_page()), \
                 mock.patch.object(kf, "_download_zip", side_effect=fake_download):
                with self.assertRaises(kf.FetchError):
                    kf.do_pack("game-icons", out, ())
            # nothing was overwritten
            self.assertEqual(Path(out, "prior.txt").read_text(), "already delivered")

    def test_pick_with_no_match_leaves_output_dir_absent(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            out = os.path.join(d, "deliver")

            def fake_download(url, dest_path):
                with open(dest_path, "wb") as fh:
                    fh.write(GAME_ICONS_ZIP)
                import hashlib

                return hashlib.sha256(GAME_ICONS_ZIP).hexdigest(), len(GAME_ICONS_ZIP)

            with mock.patch.object(kf, "fetch_pack_page", return_value=self._fake_page()), \
                 mock.patch.object(kf, "_download_zip", side_effect=fake_download):
                with self.assertRaises(kf.FetchError):
                    kf.do_pack("game-icons", out, ("Audio/*.ogg",))
            self.assertFalse(os.path.exists(out))

    def test_unverified_license_refuses_before_any_download(self) -> None:
        parser = kf.PackPageParser()
        parser.feed(PACK_PAGE_FIXTURE_NO_LICENSE)
        with tempfile.TemporaryDirectory() as d:
            out = os.path.join(d, "deliver")
            with mock.patch.object(
                kf, "fetch_pack_page", return_value=("https://kenney.nl/assets/mystery-pack", parser)
            ), mock.patch.object(kf, "_download_zip", side_effect=AssertionError("must not download")):
                with self.assertRaises(kf.FetchError):
                    kf.do_pack("mystery-pack", out, ())
            self.assertFalse(os.path.exists(out))

    def test_corrupt_zip_fails_cleanly_with_no_partial_output(self) -> None:
        def fake_download_garbage(url, dest_path):
            with open(dest_path, "wb") as fh:
                fh.write(b"not actually a zip file")
            return "0" * 64, 24

        with tempfile.TemporaryDirectory() as d:
            out = os.path.join(d, "deliver")
            with mock.patch.object(kf, "fetch_pack_page", return_value=self._fake_page()), \
                 mock.patch.object(kf, "_download_zip", side_effect=fake_download_garbage):
                with self.assertRaises(kf.FetchError) as ctx:
                    kf.do_pack("game-icons", out, ())
            self.assertIn("corrupt zip", str(ctx.exception))
            # nothing left behind: neither the final dir nor a stray staging dir
            self.assertFalse(os.path.exists(out))
            self.assertEqual(os.listdir(d), [])


# ── CLI argument handling ──────────────────────────────────────────────────


class MainCliTest(unittest.TestCase):
    def test_requires_search_or_pack(self) -> None:
        self.assertEqual(kf.main([]), 1)

    def test_search_cannot_combine_with_pack(self) -> None:
        self.assertEqual(kf.main(["--search", "icons", "--pack", "game-icons"]), 1)

    def test_pack_requires_out(self) -> None:
        self.assertEqual(kf.main(["--pack", "game-icons"]), 1)

    def test_search_runs_through_https_get(self) -> None:
        with mock.patch.object(kf, "_https_get", return_value=SEARCH_PAGE_FIXTURE.encode("utf-8")):
            self.assertEqual(kf.main(["--search", "game icons"]), 0)


if __name__ == "__main__":
    unittest.main()
