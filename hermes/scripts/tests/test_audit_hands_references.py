"""audit-hands-references.py: option-backed reference catalog audit."""

from __future__ import annotations

import importlib.util
import json
import shutil
import subprocess
import sys
import textwrap
import unittest
from pathlib import Path


SCRIPT = Path(__file__).resolve().parents[1] / "audit-hands-references.py"
HERMES_ROOT = SCRIPT.parents[1]
REPO_ROOT = HERMES_ROOT.parent
REAL_CARD_ROOT = (
    HERMES_ROOT / "profiles" / "image-creator" / "skills" / "image-creator-pipeline"
)

SPEC = importlib.util.spec_from_file_location("audit_hands_references", SCRIPT)
assert SPEC and SPEC.loader
AUDIT = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(AUDIT)

# Independent import of the canonical validator for a regression check that
# this tool's option-backing gate still agrees with validate_hands_form's.
# No source is extracted and no API is shared; each is called separately.
VALIDATOR_SCRIPT = HERMES_ROOT / "scripts" / "validate-profile-skills.py"
VALIDATOR_SPEC = importlib.util.spec_from_file_location(
    "validate_profile_skills_for_audit_regression", VALIDATOR_SCRIPT
)
assert VALIDATOR_SPEC and VALIDATOR_SPEC.loader
VALIDATOR = importlib.util.module_from_spec(VALIDATOR_SPEC)
VALIDATOR_SPEC.loader.exec_module(VALIDATOR)


def write(path: Path, text: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(textwrap.dedent(text).lstrip("\n"), encoding="utf-8")
    return path


def skill_frontmatter(name: str, form_yaml: str) -> str:
    return (
        "---\n"
        f"name: {name}\n"
        "description: fixture leaf\n"
        "version: 1.0.0\n"
        "metadata:\n"
        "  hermes:\n"
        "    category: hands\n"
        "    hands: image-creator\n"
        "    cost: free\n"
        "    output: fixture\n"
        "    form:\n"
        f"{form_yaml}\n"
        "---\n\n"
        "<Procedure>\nfixture\n</Procedure>\n"
        "<QA>\nfixture\n</QA>\n"
        "<Report>\nfixture\n</Report>\n"
    )


def run_cli(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(SCRIPT), *args],
        capture_output=True,
        text=True,
        check=False,
    )


class FixtureTreeCase(unittest.TestCase):
    """Base: builds a scratch <root>/hermes/profiles/... hands tree."""

    def setUp(self) -> None:
        import tempfile

        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def profile_pipeline(self, profile: str = "image-creator") -> Path:
        return self.root / "hermes" / "profiles" / profile / "skills" / f"{profile}-pipeline"

    def write_leaf(
        self, verb: str, subject: str, form_yaml: str, profile: str = "image-creator",
        name: str | None = None,
    ) -> Path:
        leaf_dir = self.profile_pipeline(profile) / verb / subject
        skill = leaf_dir / "SKILL.md"
        write(skill, skill_frontmatter(name or f"{verb}-{subject}", form_yaml))
        return leaf_dir


# generic reference-catalog checks


class ReferenceCatalogTest(FixtureTreeCase):
    def test_missing_backed_option_is_error(self) -> None:
        self.write_leaf(
            "create", "widget",
            "      style:\n        required: true\n        options: [alpha, beta]\n",
        )
        write(
            self.profile_pipeline() / "create/widget/references/styles/alpha.md",
            "# alpha\ncontent\n",
        )
        # beta.md intentionally absent.
        findings = AUDIT.audit(self.root, None)
        codes = {(f["severity"], f["code"]) for f in findings.items}
        self.assertIn(("error", "missing-backed-option"), codes)

    def test_fully_backed_and_linked_leaf_has_no_findings(self) -> None:
        self.write_leaf(
            "create", "widget",
            "      style:\n        required: true\n        options: [alpha]\n",
        )
        write(
            self.profile_pipeline() / "create/widget/references/styles/alpha.md",
            "# alpha\ncontent\n",
        )
        skill = self.profile_pipeline() / "create/widget/SKILL.md"
        skill.write_text(
            skill.read_text().replace(
                "<Procedure>\nfixture",
                "<Procedure>\nSee [alpha](references/styles/alpha.md)",
            ),
            encoding="utf-8",
        )
        findings = AUDIT.audit(self.root, None)
        self.assertEqual([], findings.items)

    def test_orphan_catalog_candidate_is_warning(self) -> None:
        self.write_leaf(
            "create", "widget",
            "      style:\n        required: true\n        options: [alpha]\n",
        )
        base = self.profile_pipeline() / "create/widget/references/styles"
        write(base / "alpha.md", "# alpha\ncontent\n")
        write(base / "unused.md", "# unused\ncontent\n")
        skill = self.profile_pipeline() / "create/widget/SKILL.md"
        skill.write_text(
            skill.read_text().replace(
                "<Procedure>\nfixture",
                "<Procedure>\nSee [alpha](references/styles/alpha.md)",
            ),
            encoding="utf-8",
        )
        findings = AUDIT.audit(self.root, None)
        self.assertEqual(
            [("warning", "orphan-catalog-candidate")],
            [(f["severity"], f["code"]) for f in findings.items],
        )
        self.assertIn("unused.md", findings.items[0]["path"])

    def test_non_catalog_reference_file_is_not_an_orphan(self) -> None:
        self.write_leaf(
            "create", "widget",
            "      style:\n        required: true\n        options: [alpha]\n",
        )
        base = self.profile_pipeline() / "create/widget/references"
        write(base / "styles/alpha.md", "# alpha\ncontent\n")
        write(base / "spec.md", "# spec\nshared bounded contract, not a catalog file\n")
        skill = self.profile_pipeline() / "create/widget/SKILL.md"
        skill.write_text(
            skill.read_text().replace(
                "<Procedure>\nfixture",
                "<Procedure>\nSee [alpha](references/styles/alpha.md)",
            ),
            encoding="utf-8",
        )
        findings = AUDIT.audit(self.root, None)
        self.assertFalse(
            any("spec.md" in f["path"] for f in findings.items), findings.items
        )

    def test_style_field_always_backed_even_without_directory(self) -> None:
        self.write_leaf(
            "create", "widget",
            "      style:\n        required: true\n        options: [alpha]\n",
        )
        # No references/styles/ directory at all.
        findings = AUDIT.audit(self.root, None)
        codes = {(f["severity"], f["code"]) for f in findings.items}
        self.assertIn(("error", "missing-backed-option"), codes)

    def test_non_style_field_without_directory_or_references_marker_is_skipped(
        self,
    ) -> None:
        self.write_leaf(
            "create", "widget",
            "      finish:\n        required: false\n        options: [matte, gloss]\n",
        )
        # No references/finish/ directory, and no `references:` marker key.
        findings = AUDIT.audit(self.root, None)
        self.assertEqual([], findings.items)

    def test_explicit_references_marker_forces_backing_even_without_directory(
        self,
    ) -> None:
        self.write_leaf(
            "create", "widget",
            "      finish:\n        required: false\n"
            "        options: [matte, gloss]\n        references: true\n",
        )
        findings = AUDIT.audit(self.root, None)
        matches = [
            f for f in findings.items
            if f["severity"] == "error" and f["code"] == "missing-backed-option"
        ]
        self.assertEqual(2, len(matches), findings.items)

    def test_theme_option_backs_against_themes_directory(self) -> None:
        self.write_leaf(
            "create", "widget",
            "      theme:\n        required: true\n        options: [dawn]\n",
        )
        write(
            self.profile_pipeline() / "create/widget/references/themes/dawn.md", "# dawn\n"
        )
        skill = self.profile_pipeline() / "create/widget/SKILL.md"
        skill.write_text(
            skill.read_text().replace(
                "<Procedure>\nfixture",
                "<Procedure>\nSee [dawn](references/themes/dawn.md)",
            ),
            encoding="utf-8",
        )
        findings = AUDIT.audit(self.root, None)
        self.assertEqual([], findings.items)

    def test_empty_catalog_file_is_error(self) -> None:
        self.write_leaf(
            "create", "widget",
            "      style:\n        required: true\n        options: [alpha]\n",
        )
        write(self.profile_pipeline() / "create/widget/references/styles/alpha.md", "   \n")
        findings = AUDIT.audit(self.root, None)
        codes = {(f["severity"], f["code"]) for f in findings.items}
        self.assertIn(("error", "empty-catalog-file"), codes)

    def test_missing_body_link_is_warning_without_templated_pointer(self) -> None:
        self.write_leaf(
            "create", "widget",
            "      style:\n        required: true\n        options: [alpha]\n",
        )
        write(self.profile_pipeline() / "create/widget/references/styles/alpha.md", "# alpha\n")
        findings = AUDIT.audit(self.root, None)
        codes = {(f["severity"], f["code"]) for f in findings.items}
        self.assertIn(("warning", "missing-body-link"), codes)

    def test_templated_pointer_satisfies_body_link(self) -> None:
        self.write_leaf(
            "create", "widget",
            "      style:\n        required: true\n        options: [alpha]\n",
        )
        write(self.profile_pipeline() / "create/widget/references/styles/alpha.md", "# alpha\n")
        skill = self.profile_pipeline() / "create/widget/SKILL.md"
        skill.write_text(
            skill.read_text().replace(
                "<Procedure>\nfixture",
                "<Procedure>\nLoad references/styles/<style>.md",
            ),
            encoding="utf-8",
        )
        findings = AUDIT.audit(self.root, None)
        self.assertEqual([], findings.items)

    def test_malformed_yaml_frontmatter_is_error_not_crash(self) -> None:
        leaf_dir = self.profile_pipeline() / "create/widget"
        write(
            leaf_dir / "SKILL.md",
            "---\nname: create-widget\nmetadata: [broken\n---\n<Procedure>\n</Procedure>\n",
        )
        findings = AUDIT.audit(self.root, None)
        self.assertEqual(
            [("error", "invalid-frontmatter")],
            [(f["severity"], f["code"]) for f in findings.items],
        )

    def test_missing_frontmatter_fence_is_error_not_crash(self) -> None:
        leaf_dir = self.profile_pipeline() / "create/widget"
        write(leaf_dir / "SKILL.md", "no frontmatter here at all\n")
        findings = AUDIT.audit(self.root, None)
        self.assertEqual(
            [("error", "invalid-frontmatter")],
            [(f["severity"], f["code"]) for f in findings.items],
        )

    def test_malformed_form_is_error_not_crash(self) -> None:
        self.write_leaf("create", "widget", "      style: not-a-mapping\n")
        findings = AUDIT.audit(self.root, None)
        codes = {(f["severity"], f["code"]) for f in findings.items}
        self.assertIn(("error", "invalid-field"), codes)

    def test_unreadable_binary_backing_file_is_error_not_crash(self) -> None:
        self.write_leaf(
            "create", "widget",
            "      style:\n        required: true\n        options: [alpha]\n",
        )
        backing = self.profile_pipeline() / "create/widget/references/styles/alpha.md"
        backing.parent.mkdir(parents=True, exist_ok=True)
        backing.write_bytes(b"\xff\xfe\x00invalid utf-8 for testing decode failure\xff")
        findings = AUDIT.audit(self.root, None)
        codes = {(f["severity"], f["code"]) for f in findings.items}
        self.assertIn(("error", "unreadable-backing-file"), codes)

    def test_leaf_with_undecodable_frontmatter_is_error_not_crash(self) -> None:
        leaf_dir = self.profile_pipeline() / "create/widget"
        skill = leaf_dir / "SKILL.md"
        skill.parent.mkdir(parents=True, exist_ok=True)
        skill.write_bytes(b"---\nname: create-widget\n\xff\xfe---\n")
        findings = AUDIT.audit(self.root, None)
        self.assertEqual(
            [("error", "invalid-frontmatter")],
            [(f["severity"], f["code"]) for f in findings.items],
        )

    def test_field_key_with_path_traversal_is_rejected_before_path_use(self) -> None:
        self.write_leaf(
            "create", "widget",
            "      ../../evil:\n        required: true\n        options: [alpha]\n",
        )
        findings = AUDIT.audit(self.root, None)
        self.assertEqual(
            [("error", "invalid-field-key")],
            [(f["severity"], f["code"]) for f in findings.items],
        )
        # No traversal outside the leaf's own references/ directory happened.
        self.assertFalse((self.root / "hermes" / "profiles" / "evil").exists())
        self.assertFalse((self.profile_pipeline().parent / "evil").exists())

    def test_prose_only_leaf_needs_no_card_tree(self) -> None:
        """A hands leaf that is not the `card` subject never touches
        scripts/card.py, so a tree with no card adapter at all still
        audits fine."""
        self.write_leaf(
            "create", "icon",
            "      style:\n        required: true\n        options: [flat]\n",
        )
        write(
            self.profile_pipeline() / "create/icon/references/styles/flat.md", "# flat\n"
        )
        skill = self.profile_pipeline() / "create/icon/SKILL.md"
        skill.write_text(
            skill.read_text().replace(
                "<Procedure>\nfixture",
                "<Procedure>\nSee [flat](references/styles/flat.md)",
            ),
            encoding="utf-8",
        )
        findings = AUDIT.audit(self.root, None)
        self.assertEqual([], findings.items)
        self.assertFalse(
            (self.profile_pipeline() / "scripts" / "card.py").exists()
        )


# --leaf scoping


class LeafFlagTest(FixtureTreeCase):
    def test_rejects_missing_directory(self) -> None:
        with self.assertRaises(AUDIT.InvalidInvocation):
            AUDIT.audit(self.root, "hermes/profiles/image-creator/skills/image-creator-pipeline/create/nope")

    def test_rejects_directory_outside_root(self) -> None:
        outside = Path(self._tmp.name).parent
        with self.assertRaises(AUDIT.InvalidInvocation):
            AUDIT.audit(self.root, str(outside))

    def test_rejects_non_hands_directory(self) -> None:
        self.write_leaf(
            "create", "widget", "      style:\n        required: true\n        options: [alpha]\n"
        )
        # A dir one level too shallow (verb only, no subject/SKILL.md).
        with self.assertRaises(AUDIT.InvalidInvocation):
            AUDIT.audit(self.root, "hermes/profiles/image-creator/skills/image-creator-pipeline/create")

    def test_scopes_to_one_leaf(self) -> None:
        self.write_leaf(
            "create", "widget", "      style:\n        required: true\n        options: [alpha]\n"
        )
        self.write_leaf(
            "create", "gadget", "      style:\n        required: true\n        options: [alpha]\n"
        )
        findings = AUDIT.audit(
            self.root, "hermes/profiles/image-creator/skills/image-creator-pipeline/create/widget"
        )
        # Only widget's missing-backed-option is reported, not gadget's.
        self.assertTrue(
            all("create/widget" in f["path"] for f in findings.items), findings.items
        )


# CLI-level checks (real subprocess: exit codes, --json)


class CliTest(FixtureTreeCase):
    def test_json_output_is_stable_and_exit_zero_on_warnings_only(self) -> None:
        self.write_leaf(
            "create", "widget", "      style:\n        required: true\n        options: [alpha]\n"
        )
        write(self.profile_pipeline() / "create/widget/references/styles/alpha.md", "# alpha\n")
        result = run_cli("--root", str(self.root), "--json")
        self.assertEqual(0, result.returncode, result.stderr)
        payload = json.loads(result.stdout)
        self.assertEqual(0, payload["totals"]["error"])
        self.assertGreaterEqual(payload["totals"]["warning"], 1)
        self.assertEqual(
            payload["totals"]["count"],
            payload["totals"]["error"] + payload["totals"]["warning"],
        )

    def test_exit_one_on_errors(self) -> None:
        self.write_leaf(
            "create", "widget", "      style:\n        required: true\n        options: [alpha]\n"
        )
        # alpha.md missing -> error.
        result = run_cli("--root", str(self.root), "--json")
        self.assertEqual(1, result.returncode, result.stdout)
        payload = json.loads(result.stdout)
        self.assertGreaterEqual(payload["totals"]["error"], 1)

    def test_exit_two_on_invalid_leaf(self) -> None:
        result = run_cli("--root", str(self.root), "--leaf", "hermes/profiles/does-not-exist")
        self.assertEqual(2, result.returncode)
        self.assertIn("does not exist", result.stderr)

    def test_exit_two_on_missing_root(self) -> None:
        result = run_cli("--root", str(self.root / "nope"))
        self.assertEqual(2, result.returncode)

    def test_exit_two_on_root_with_no_hands_leaves(self) -> None:
        # self.root exists but has no hermes/profiles/... tree at all (e.g.
        # --root pointing one level too deep, already inside hermes/): a
        # whole-tree scan must not silently report zero findings and pass.
        with self.assertRaises(AUDIT.InvalidInvocation):
            AUDIT.audit(self.root, None)
        result = run_cli("--root", str(self.root))
        self.assertEqual(2, result.returncode)
        self.assertIn("no managed hands leaf targets", result.stderr)

    def test_root_with_actual_targets_is_unaffected(self) -> None:
        self.write_leaf(
            "create", "widget", "      style:\n        required: true\n        options: [alpha]\n"
        )
        write(self.profile_pipeline() / "create/widget/references/styles/alpha.md", "# alpha\n")
        result = run_cli("--root", str(self.root))
        self.assertEqual(0, result.returncode, result.stdout)

    def test_default_root_is_derived_from_script_location(self) -> None:
        self.assertEqual(REPO_ROOT, AUDIT.DEFAULT_ROOT)


# card adapter (real card.py bytes + real destination/style fixtures)


class CardAdapterTest(FixtureTreeCase):
    """Reuses the real, checked-in card.py bytes rather than imitating its
    contract, per hermes/AGENTS.md's card adapter rules."""

    def build_card_pipeline(self) -> Path:
        pipeline = self.profile_pipeline()
        (pipeline / "scripts").mkdir(parents=True, exist_ok=True)
        shutil.copyfile(REAL_CARD_ROOT / "scripts" / "card.py", pipeline / "scripts" / "card.py")
        return pipeline

    def test_prose_only_leaf_without_card_py_still_audits(self) -> None:
        # No scripts/card.py copied at all; a non-card leaf must not need it.
        self.write_leaf(
            "create", "icon", "      style:\n        required: true\n        options: [flat]\n"
        )
        write(self.profile_pipeline() / "create/icon/references/styles/flat.md", "# flat\n")
        skill = self.profile_pipeline() / "create/icon/SKILL.md"
        skill.write_text(
            skill.read_text().replace(
                "<Procedure>\nfixture",
                "<Procedure>\nSee [flat](references/styles/flat.md)",
            ),
            encoding="utf-8",
        )
        findings = AUDIT.audit(self.root, None)
        self.assertEqual([], findings.items)

    def test_card_leaf_without_card_py_is_error(self) -> None:
        self.write_leaf(
            "create", "card",
            "      destination:\n        required: true\n        options: [og]\n",
            name="create-card",
        )
        write(
            self.profile_pipeline() / "create/card/references/destination/og.md",
            "---\nwidth: 1200\nheight: 630\nstatus: authoring-default\n---\n# og\n",
        )
        findings = AUDIT.audit(self.root, None)
        codes = {(f["severity"], f["code"]) for f in findings.items}
        self.assertIn(("error", "card-adapter-missing"), codes)

    def test_card_destination_metadata_and_adapter_pass_on_real_reference(self) -> None:
        self.build_card_pipeline()
        self.write_leaf(
            "create", "card",
            "      destination:\n        required: true\n        options: [og]\n",
            name="create-card",
        )
        shutil.copyfile(
            REAL_CARD_ROOT / "create/card/references/destination/og.md",
            write(self.profile_pipeline() / "create/card/references/destination/og.md", ""),
        )
        findings = AUDIT.audit(self.root, None)
        self.assertEqual(
            [], [f for f in findings.items if f["severity"] == "error"], findings.items
        )

    def test_card_destination_missing_field_is_error(self) -> None:
        self.build_card_pipeline()
        self.write_leaf(
            "create", "card",
            "      destination:\n        required: true\n        options: [og]\n",
            name="create-card",
        )
        write(
            self.profile_pipeline() / "create/card/references/destination/og.md",
            "---\nwidth: 1200\nstatus: authoring-default\n---\n# og missing height\n",
        )
        findings = AUDIT.audit(self.root, None)
        errors = {(f["code"], f["message"]) for f in findings.items if f["severity"] == "error"}
        self.assertTrue(any(code == "destination-missing-field" for code, _ in errors))

    def test_card_destination_duplicate_scalar_key_is_error(self) -> None:
        self.build_card_pipeline()
        self.write_leaf(
            "create", "card",
            "      destination:\n        required: true\n        options: [og]\n",
            name="create-card",
        )
        write(
            self.profile_pipeline() / "create/card/references/destination/og.md",
            "---\nwidth: 1200\nwidth: 1201\nheight: 630\nstatus: authoring-default\n---\n# og\n",
        )
        findings = AUDIT.audit(self.root, None)
        codes = {f["code"] for f in findings.items if f["severity"] == "error"}
        self.assertIn("destination-duplicate-scalar-key", codes)

    def test_card_destination_unpaired_display_dims_is_error(self) -> None:
        self.build_card_pipeline()
        self.write_leaf(
            "create", "card",
            "      destination:\n        required: true\n        options: [x-post]\n",
            name="create-card",
        )
        write(
            self.profile_pipeline() / "create/card/references/destination/x-post.md",
            "---\nwidth: 1200\nheight: 675\nstatus: authoring-default\n"
            "display_width_css_px: 360\n---\n# missing display_gap_css_px\n",
        )
        findings = AUDIT.audit(self.root, None)
        codes = {f["code"] for f in findings.items if f["severity"] == "error"}
        self.assertIn("destination-unpaired-display-dims", codes)

    def test_carousel_range_descending_is_error_and_default_spec_still_checked(self) -> None:
        self.build_card_pipeline()
        self.write_leaf(
            "create", "card",
            "      destination:\n        required: true\n        options: [x-carousel]\n",
            name="create-card",
        )
        write(
            self.profile_pipeline() / "create/card/references/destination/x-carousel.md",
            # tiles > max_tiles: descending, invalid range.
            "---\nwidth: 900\nheight: 1125\nstatus: authoring-default\n"
            "tiles: 4\nmax_tiles: 3\ntile: portrait\ntile_options: portrait|square\n---\n# bad\n",
        )
        findings = AUDIT.audit(self.root, None)
        codes = [f["code"] for f in findings.items if f["severity"] == "error"]
        self.assertIn("destination-carousel-range-invalid", codes)
        # The default spec {"destination": "x-carousel"} is still exercised
        # even though the declared range itself is rejected: this
        # reference's own default (tiles=4) is inconsistent with its own
        # max_tiles=3, so the real destination() call on the default spec
        # correctly fails too. A bad default must not hide behind the range
        # check by being skipped once the range is flagged.
        self.assertIn("destination-adapter-failed", codes)

    def test_carousel_range_excess_over_card_max_tiles_is_error(self) -> None:
        self.build_card_pipeline()
        self.write_leaf(
            "create", "card",
            "      destination:\n        required: true\n        options: [x-carousel]\n",
            name="create-card",
        )
        write(
            self.profile_pipeline() / "create/card/references/destination/x-carousel.md",
            "---\nwidth: 900\nheight: 1125\nstatus: authoring-default\n"
            "tiles: 3\nmax_tiles: 9\ntile: portrait\ntile_options: portrait|square\n---\n# bad\n",
        )
        findings = AUDIT.audit(self.root, None)
        codes = [f["code"] for f in findings.items if f["severity"] == "error"]
        self.assertIn("destination-carousel-range-excess", codes)
        # A range this large must never be materialized: no per-combo
        # adapter-failure noise, since the loop is never entered.
        self.assertNotIn("destination-adapter-failed", codes)

    def test_carousel_valid_range_is_capped_at_card_max_tiles(self) -> None:
        combos = AUDIT.destination_combinations(
            "x-carousel",
            {"tiles": 3, "max_tiles": AUDIT.CARD_MAX_TILES, "tile_options": "portrait|square"},
            Path("/dev/null"),
            AUDIT.Findings(self.root),
        )
        # Default spec first, then every tiles x tile combo up to the cap.
        self.assertEqual({"destination": "x-carousel"}, combos[0])
        self.assertTrue(
            all(c.get("tiles", 0) <= AUDIT.CARD_MAX_TILES for c in combos), combos
        )

    def test_card_style_css_fence_pass_on_real_reference(self) -> None:
        self.build_card_pipeline()
        self.write_leaf(
            "create", "card",
            "      style:\n        required: true\n        options: [glass]\n",
            name="create-card",
        )
        shutil.copyfile(
            REAL_CARD_ROOT / "create/card/references/styles/glass.md",
            write(self.profile_pipeline() / "create/card/references/styles/glass.md", ""),
        )
        findings = AUDIT.audit(self.root, None)
        self.assertEqual(
            [], [f for f in findings.items if f["severity"] == "error"], findings.items
        )

    def test_card_bad_css_is_error(self) -> None:
        self.build_card_pipeline()
        self.write_leaf(
            "create", "card",
            "      style:\n        required: true\n        options: [broken]\n",
            name="create-card",
        )
        write(
            self.profile_pipeline() / "create/card/references/styles/broken.md",
            "# broken\n\n```css\n.unsupported-selector { color: red; }\n```\n",
        )
        findings = AUDIT.audit(self.root, None)
        codes = {f["code"] for f in findings.items if f["severity"] == "error"}
        self.assertIn("style-css-adapter-failed", codes)

    def test_generate_card_style_prose_is_not_validated_as_css(self) -> None:
        self.build_card_pipeline()
        self.write_leaf(
            "generate", "card",
            "      style:\n        required: true\n        options: [broken]\n",
            name="generate-card",
        )
        # Prose, not a CSS fence at all: must not be run through css_style().
        write(
            self.profile_pipeline() / "generate/card/references/styles/broken.md",
            "# broken\n\nJust backdrop prompt direction, no CSS block here.\n",
        )
        findings = AUDIT.audit(self.root, None)
        codes = {f["code"] for f in findings.items if f["severity"] == "error"}
        self.assertNotIn("style-css-adapter-failed", codes)

    def test_card_style_parity_mismatch_is_error(self) -> None:
        self.build_card_pipeline()
        create = self.write_leaf(
            "create", "card",
            "      style:\n        required: true\n        options: [glass]\n",
            name="create-card",
        )
        self.write_leaf(
            "generate", "card",
            "      style:\n        required: true\n        options: [other]\n",
            name="generate-card",
        )
        shutil.copyfile(
            REAL_CARD_ROOT / "create/card/references/styles/glass.md",
            write(create / "references/styles/glass.md", ""),
        )
        write(
            self.profile_pipeline() / "generate/card/references/styles/other.md", "# other\n"
        )
        findings = AUDIT.audit(self.root, None)
        codes = {f["code"] for f in findings.items if f["severity"] == "error"}
        self.assertIn("card-style-parity", codes)

    def test_whole_tree_deleted_generate_leaf_reports_parity_unverified(self) -> None:
        self.build_card_pipeline()
        create = self.write_leaf(
            "create", "card",
            "      style:\n        required: true\n        options: [glass]\n",
            name="create-card",
        )
        shutil.copyfile(
            REAL_CARD_ROOT / "create/card/references/styles/glass.md",
            write(create / "references/styles/glass.md", ""),
        )
        # No generate-card leaf at all: a whole-tree scan must not stay
        # silent about the missing counterpart (that would read the same as
        # a checked, passing parity comparison).
        findings = AUDIT.audit(self.root, None)
        codes = {(f["severity"], f["code"]) for f in findings.items}
        self.assertIn(("warning", "card-style-parity-unverified"), codes)
        self.assertNotIn(("error", "card-style-parity"), codes)

    def test_whole_tree_absent_style_options_reports_parity_unverified(self) -> None:
        self.build_card_pipeline()
        create = self.write_leaf(
            "create", "card",
            "      style:\n        required: true\n        options: [glass]\n",
            name="create-card",
        )
        shutil.copyfile(
            REAL_CARD_ROOT / "create/card/references/styles/glass.md",
            write(create / "references/styles/glass.md", ""),
        )
        # generate-card exists but its form carries no style field at all
        # (malformed/absent, not just missing options) - still one-sided.
        self.write_leaf(
            "generate", "card",
            "      art:\n        required: true\n",
            name="generate-card",
        )
        findings = AUDIT.audit(self.root, None)
        codes = {(f["severity"], f["code"]) for f in findings.items}
        self.assertIn(("warning", "card-style-parity-unverified"), codes)
        self.assertNotIn(("error", "card-style-parity"), codes)

    def test_no_card_family_present_has_no_parity_findings(self) -> None:
        # No card subject anywhere in the tree: parity must never fire.
        self.write_leaf(
            "create", "icon", "      style:\n        required: true\n        options: [flat]\n"
        )
        write(self.profile_pipeline() / "create/icon/references/styles/flat.md", "# flat\n")
        skill = self.profile_pipeline() / "create/icon/SKILL.md"
        skill.write_text(
            skill.read_text().replace(
                "<Procedure>\nfixture",
                "<Procedure>\nSee [flat](references/styles/flat.md)",
            ),
            encoding="utf-8",
        )
        findings = AUDIT.audit(self.root, None)
        codes = {f["code"] for f in findings.items}
        self.assertNotIn("card-style-parity", codes)
        self.assertNotIn("card-style-parity-unverified", codes)

    def test_leaf_scoped_style_leaf_reports_parity_unverified_not_silence(self) -> None:
        self.build_card_pipeline()
        create = self.write_leaf(
            "create", "card",
            "      style:\n        required: true\n        options: [glass]\n",
            name="create-card",
        )
        shutil.copyfile(
            REAL_CARD_ROOT / "create/card/references/styles/glass.md",
            write(create / "references/styles/glass.md", ""),
        )
        # No generate-card leaf at all in this tree: parity cannot be
        # checked from one selected leaf, and the report must say so
        # explicitly rather than stay silent (which would read as "passed").
        findings = AUDIT.audit(
            self.root,
            "hermes/profiles/image-creator/skills/image-creator-pipeline/create/card",
        )
        codes = {(f["severity"], f["code"]) for f in findings.items}
        self.assertIn(("warning", "card-style-parity-unverified"), codes)
        self.assertNotIn(("error", "card-style-parity"), codes)

    def test_no_bytecode_written_for_candidate_adapter(self) -> None:
        pipeline = self.build_card_pipeline()
        self.write_leaf(
            "create", "card",
            "      style:\n        required: true\n        options: [glass]\n",
            name="create-card",
        )
        shutil.copyfile(
            REAL_CARD_ROOT / "create/card/references/styles/glass.md",
            write(self.profile_pipeline() / "create/card/references/styles/glass.md", ""),
        )
        AUDIT.audit(self.root, None)
        self.assertFalse((pipeline / "scripts" / "__pycache__").exists())
        self.assertTrue(sys.dont_write_bytecode)


class CanonicalGateAgreementTest(FixtureTreeCase):
    """Inexpensive regression: this tool's missing-backed-option gate must
    keep agreeing with validate_hands_form's canonical mapping/gate across
    style/theme/plain-field/explicit-references-marker fields. Each tool is
    called independently on the same fixture; no source is extracted from
    the validator, no API is shared, and the validator is not modified."""

    def test_missing_option_agreement_across_field_kinds(self) -> None:
        form_yaml = (
            "      note:\n        required: false\n"
            "      style:\n        required: true\n        options: [a, b]\n"
            "      theme:\n        required: true\n        options: [c, d]\n"
            "      kind:\n        required: false\n        options: [e, f]\n"
            "      extra:\n        required: false\n"
            "        options: [g]\n        references: true\n"
        )
        leaf_dir = self.write_leaf("create", "widget", form_yaml, name="create-widget")
        write(leaf_dir / "references/styles/a.md", "# a\n")
        write(leaf_dir / "references/themes/c.md", "# c\n")
        # kind: no directory, no `references` marker -> both tools skip it.
        # extra: `references` marker, no directory, g.md absent -> flagged.
        # style: b.md absent -> flagged. theme: directory exists, d.md
        # absent -> flagged.

        audit_findings = AUDIT.Findings(self.root)
        AUDIT.audit_leaf(
            "image-creator", self.profile_pipeline(), leaf_dir / "SKILL.md",
            AUDIT.CardAdapters(audit_findings), {}, audit_findings,
        )
        audit_missing = {
            f["message"].split(" option ", 1)[0]
            for f in audit_findings.items
            if f["code"] == "missing-backed-option"
        }

        form = {
            "note": {"required": False},
            "style": {"required": True, "options": ["a", "b"]},
            "theme": {"required": True, "options": ["c", "d"]},
            "kind": {"required": False, "options": ["e", "f"]},
            "extra": {"required": False, "options": ["g"], "references": True},
        }
        validator_errors: list[str] = []
        VALIDATOR.validate_hands_form(form, leaf_dir, leaf_dir / "SKILL.md", validator_errors)
        validator_missing = {
            err.split(" option ", 1)[0] for err in validator_errors if " option " in err
        }

        expected = {"style", "theme", "extra"}
        self.assertEqual(expected, audit_missing)
        self.assertEqual(expected, validator_missing)
        self.assertNotIn("kind", audit_missing)
        self.assertNotIn("kind", validator_missing)


class RealTreeTest(unittest.TestCase):
    """Baseline pass against the actual checked-in repository tree."""

    def test_real_tree_has_no_errors(self) -> None:
        findings = AUDIT.audit(REPO_ROOT, None)
        errors = [f for f in findings.items if f["severity"] == "error"]
        self.assertEqual([], errors)

    def test_real_tree_cli_exit_zero(self) -> None:
        result = run_cli("--root", str(REPO_ROOT))
        self.assertEqual(0, result.returncode, result.stdout)

    def test_real_card_leaf_scoped(self) -> None:
        findings = AUDIT.audit(
            REPO_ROOT,
            "hermes/profiles/image-creator/skills/image-creator-pipeline/create/card",
        )
        errors = [f for f in findings.items if f["severity"] == "error"]
        self.assertEqual([], errors)


if __name__ == "__main__":
    unittest.main()
