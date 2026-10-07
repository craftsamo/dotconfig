"""Tests for the `generate-illustration` leaf: front matter contract and the
procedure's budget and no-text statements."""

from __future__ import annotations

import importlib.util
import re
import sys
from pathlib import Path

HERMES_ROOT = Path(__file__).resolve().parents[2]
PIPELINE = HERMES_ROOT / "profiles" / "image-creator" / "skills" / "image-creator-pipeline"
LEAF = PIPELINE / "generate" / "illustration"
SKILL = LEAF / "SKILL.md"
SIBLINGS = [PIPELINE / "generate" / "card" / "SKILL.md"]

_spec = importlib.util.spec_from_file_location(
    "validate_profile_skills", HERMES_ROOT / "scripts" / "validate-profile-skills.py"
)
VALIDATOR = importlib.util.module_from_spec(_spec)
sys.modules[_spec.name] = VALIDATOR
_spec.loader.exec_module(VALIDATOR)


def test_front_matter_closes_early_and_validates():
    text = SKILL.read_text(encoding="utf-8")
    assert text.startswith("---\n")
    assert "\n---\n" in text[:3800]
    errors: list[str] = []
    VALIDATOR.validate_hands_leaves(PIPELINE, "image-creator", errors)
    assert [e for e in errors if "illustration" in e] == []
    meta = VALIDATOR.hermes_meta(VALIDATOR.frontmatter(SKILL))
    assert meta["cost"] == "metered" and meta["hands"] == "image-creator"
    form = meta["form"]
    assert {"what_for", "subject", "style", "size", "format", "reference", "avoid",
            "variants", "note"} == set(form)
    assert [k for k, v in form.items() if v["required"]] == ["what_for", "subject", "style"]
    assert "options" not in form["style"] and "options" not in form["format"]
    assert form["reference"]["type"] == "image"
    assert form["variants"]["type"] == "int"
    form_errors: list[str] = []
    VALIDATOR.validate_hands_form(form, LEAF, SKILL, form_errors)
    assert form_errors == []
    body = text.split("\n---\n", 1)[1]
    assert re.findall(r"^<(/?\w+)>$", body, re.M) == [
        "Procedure", "/Procedure", "QA", "/QA", "Report", "/Report"]


def test_reference_consent_matches_sibling_convention():
    def label(path: Path) -> str:
        return VALIDATOR.hermes_meta(VALIDATOR.frontmatter(path))["form"]["reference"]["label"]

    for sibling in SIBLINGS:
        assert label(SKILL) == label(sibling)
    assert "explicit upload consent" in label(SKILL)


def test_procedure_states_budget_and_no_text_in_pixels():
    text = SKILL.read_text(encoding="utf-8")
    assert "4 variants + 1 corrective" in text
    assert "attempts.json" in text
    assert "Never put a" in text and "readable word" in text
    assert "no text, no letters" in text
    assert (LEAF / "references" / "craft-notes.md").is_file()
