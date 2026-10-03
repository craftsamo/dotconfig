"""Structural checks of the japanese-writing skill, not a judge of Japanese quality."""

import json
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1].parent
SKILL = ROOT / "agents/curated/japanese-writing"
REFERENCES = SKILL / "references"
ANCHORS = {
    "readability.md": ["A1", "A2", "B1", "B2", "B3", "B4", "B5", "B6", "B7", "C1", "C2", "C3", "C4",
                       "D1", "E1", "F1", "H1", "H2", "H3", "I1", "J1", "J2", "J3"],
    "expression.md": [f"X{n}" for n in range(1, 11)],
    "notation.md": [f"N{n}" for n in range(1, 12)],
    "revision.md": [f"R{n}" for n in range(1, 6)],
}


def skill_text():
    return (SKILL / "SKILL.md").read_text(encoding="utf-8")


def anchors_in(name):
    text = (REFERENCES / name).read_text(encoding="utf-8")
    return re.findall(r"^#{2,3} ([A-Z][0-9]+) ", text, re.MULTILINE)


def test_frontmatter_and_discovery_contract():
    text = skill_text()
    assert text.startswith("---\nname: japanese-writing\n")
    description = text.split("description: >-", 1)[1].split("\n---", 1)[0]
    assert len(" ".join(description.split())) <= 1024
    assert "<" not in description and ">" not in description
    assert len(text.splitlines()) < 500


def test_every_reference_is_linked_and_exists():
    text = skill_text()
    linked = set(re.findall(r"(references/[\w/-]+\.md|assets/[\w-]+\.md)", text))
    on_disk = {p.relative_to(SKILL).as_posix() for p in SKILL.rglob("*.md") if p.name != "SKILL.md"}
    doctypes = {p for p in on_disk if p.startswith("references/doctypes/")}
    assert doctypes and all(Path(p).name in text for p in doctypes)
    assert linked - {"references/doctypes/"} <= on_disk
    assert on_disk - doctypes <= linked
    assert "scripts/inspect_text.py" in text


def test_reference_anchors_are_complete_and_ordered():
    for name, expected in ANCHORS.items():
        assert anchors_in(name) == expected, name


def test_inspector_reasons_cite_existing_anchors():
    cited = set()
    sources = list((SKILL / "scripts/inspector").rglob("*.py")) + list((SKILL / "scripts/inspector/data").glob("*.json"))
    for path in sources:
        cited |= set(re.findall(r"(readability|expression|notation|revision)\.md ([A-Z][0-9]+)", path.read_text(encoding="utf-8")))
    assert cited
    for stem, anchor in cited:
        assert anchor in ANCHORS[f"{stem}.md"], (stem, anchor)


def test_data_files_are_valid_json():
    for path in (SKILL / "scripts/inspector/data").glob("*.json"):
        json.loads(path.read_text(encoding="utf-8"))


def test_only_runtime_resources_are_packaged():
    files = {
        p.relative_to(SKILL).as_posix() for p in SKILL.rglob("*")
        if p.is_file() and not any(part == "__pycache__" or part.startswith(".") for part in p.relative_to(SKILL).parts)
    }
    assert not {f for f in files if Path(f).name in ("README.md", "CHANGELOG.md", "LICENSE")}
    assert not {f for f in files if f.startswith("scripts/") and not re.fullmatch(r"scripts/(inspect_text\.py|requirements\.txt|inspector/[\w/-]+\.(py|json))", f)}
    assert not {f for f in files if "lint.py" in f or "fixtures" in f}


def test_host_router_only_loads_core():
    text = (ROOT / "opencode/AGENTS.md").read_text(encoding="utf-8")
    route = text.split("<JapaneseWritingSkills>", 1)[1].split("</JapaneseWritingSkills>", 1)[0]
    assert "japanese-writing" in route
    assert "references/" not in route
    assert "scripts/" not in route


def test_writer_does_not_call_skill_resources_directly():
    pipeline = ROOT / "hermes/profiles/writer/skills/writer-pipeline"
    for path in pipeline.rglob("*.md"):
        text = path.read_text(encoding="utf-8")
        assert "japanese-writing/scripts/" not in text, path
        assert "references/inspection/" not in text, path
