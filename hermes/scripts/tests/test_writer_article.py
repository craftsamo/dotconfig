"""Article contract checks; source syntax is not a rendered-platform test."""

from pathlib import Path

import pytest
import yaml


HERMES = Path(__file__).resolve().parents[2]
PIPELINE = HERMES / "profiles/writer/skills/writer-pipeline"


@pytest.mark.parametrize("verb", ["write", "edit", "analyze"])
def test_article_form_and_platform_references(verb):
    path = PIPELINE / verb / "article/SKILL.md"
    text = path.read_text()
    assert text.index("---", 3) + 3 < 4000
    data = yaml.safe_load(text.split("---", 2)[1])
    assert data["name"] == f"{verb}-article"
    meta = data["metadata"]["hermes"]
    assert meta["category"] == "writing"
    assert meta["output"]
    form = meta["form"]
    assert form["platform"]["options"] == ["x-article", "note", "zenn", "blog"]
    assert form["platform"]["other"] is True
    assert form["humanizer"]["options"] == ["yes", "no"]
    for platform in form["platform"]["options"]:
        assert (path.parent / "references" / f"{platform}.md").is_file()
    for section in ("Procedure", "QA", "Report"):
        assert f"<{section}>" in text and f"</{section}>" in text
    assert "scripts/lint.py" not in text


def test_article_routes_and_approaches_exist():
    kernel = (PIPELINE / "SKILL.md").read_text()
    for verb in ("write", "edit", "analyze"):
        assert f"]({verb}/article/SKILL.md)" in kernel
    root = PIPELINE / "write/article"
    data = yaml.safe_load((root / "SKILL.md").read_text().split("---", 2)[1])
    for approach in data["metadata"]["hermes"]["form"]["approach"]["options"]:
        assert (root / "references/approach" / f"{approach}.md").is_file()


def test_asset_requirements_remain_separate_from_published_text():
    assets = " ".join((PIPELINE / "write/article/references/production/assets.md").read_text().split())
    for kind in ("image", "embed", "table"):
        assert f"[[{kind}:id]]" in assets
    assert "<draft-stem>.production.md" in assets
    assert "not generation, capture, upload" in assets
    assert "never delete one merely" in assets
    assert "Text acceptance does not verify the final render" in assets


@pytest.mark.parametrize("verb", ["write", "edit", "analyze"])
def test_production_record_contract_agrees_across_operations(verb):
    root = PIPELINE / verb / "article"
    assets = (root / "references/production/assets.md").read_text()
    for field in ("ID", "Kind", "Placement", "Purpose", "Source", "Requirements", "State"):
        assert f"`{field}`" in assets
    for kind in ("image", "embed", "table"):
        assert f"[[{kind}:id]]" in assets
    assert "](references/production/assets.md)" in (root / "SKILL.md").read_text()


def test_platform_input_models_are_not_conflated():
    refs = PIPELINE / "write/article/references"
    zenn = (refs / "zenn.md").read_text()
    note = " ".join((refs / "note.md").read_text().split())
    x = " ".join((refs / "x-article.md").read_text().split())
    assert "Input is Markdown source" in zenn
    assert "not a general Markdown-file import contract" in note
    assert "dedicated rich-text editor" in x
    assert "not a long post or a thread" in x
    assert "do not promise raw Markdown import" in x
