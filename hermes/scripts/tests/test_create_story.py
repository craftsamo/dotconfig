"""create-story: storyboard/cast/script helper contract and Creator routing.

Fixture art and lines are synthetic; they prove the checks, not a story.
"""

from __future__ import annotations

import hashlib
import importlib.util
import json
import os
import shutil
from pathlib import Path

import pytest
import yaml
from PIL import Image

HERMES_ROOT = Path(__file__).resolve().parents[2]
VIDEO = HERMES_ROOT / "profiles/video-creator/skills/video-creator-pipeline"
LEAF = VIDEO / "create/story"
CREATOR = HERMES_ROOT / "profiles/creator"
CAPABILITIES = CREATOR / "skills/creator-pipeline/references/capabilities.md"

spec = importlib.util.spec_from_file_location("create_story", LEAF / "scripts/story.py")
story = importlib.util.module_from_spec(spec)
spec.loader.exec_module(story)

STORYBOARD = """---
aspect: 9:16
duration: 12
fps: 30
audio: none
pending: {pending}
---
# Fixture

## Intent
TEST FIXTURE only.

## Cast
| id | who | art on hand | needed |
| --- | --- | --- | --- |
| mika | lead | front | - |
| tobi | friend | front | - |

## Beats
| # | start | end | scene | cast | dialogue | camera / acting / transition | audio |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | 0 | 5 | roof, wide | mika | - | pull-back reveal | wind |
| 2 | 5 | 12 | roof, two-shot | {cast2} | mika: 「{line}」 | push-in; pose swap | line 1 |
{extra}"""

SCRIPT = "mika: 今日で最後なんだね\ntobi: うん。\n"


def art(path: Path, colour: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    Image.new("RGBA", (64, 96), colour).save(path)
    return path


def fixture(tmp_path, line="今日で最後なんだね", cast2="mika, tobi", pending="", extra=""):
    draft = tmp_path / "draft.md"
    draft.write_text(STORYBOARD.format(line=line, cast2=cast2, pending=pending, extra=extra), encoding="utf-8")
    mika = art(tmp_path / "cast/mika/front.png", "red")
    art(tmp_path / "cast/mika/happy.png", "orange")
    tobi = art(tmp_path / "tobi.png", "blue")
    script = tmp_path / "script.txt"
    script.write_text(SCRIPT, encoding="utf-8")
    return draft, f"mika={mika.parent},tobi={tobi}", script


def propose(tmp_path, draft, cast, script=None, out="proposal-v1"):
    args = ["propose", "--storyboard", str(draft), "--cast", cast, "--out", str(tmp_path / out)]
    if script:
        args += ["--script", str(script)]
    return story.main(args)


def test_propose_binds_storyboard_cast_and_script(tmp_path):
    draft, cast, script = fixture(tmp_path)
    assert propose(tmp_path, draft, cast, script) == 0
    data = json.loads((tmp_path / "proposal-v1/proposal.json").read_text())
    stored = tmp_path / "proposal-v1/storyboard.md"
    assert data["sha256"] == hashlib.sha256(stored.read_bytes()).hexdigest()
    assert data["status"] == "awaiting-approval"
    assert (data["width"], data["height"], data["duration"]) == (1080, 1920, 12.0)
    assert set(data["cast"]) == {"mika", "tobi"} and len(data["cast"]["mika"]) == 2
    assert data["script"]["sha256"] == hashlib.sha256(script.read_bytes()).hexdigest()
    assert data["dialogue_lines"] == 1
    bound = story.bound_art(stored.read_text(encoding="utf-8"))
    assert set(bound["cast"]["mika"]) == {"front.png", "happy.png"}
    assert bound["script_sha256"] == data["script"]["sha256"]


def test_a_mascot_pack_counts_only_passed_items(tmp_path):
    pack = tmp_path / "pack"
    art(pack / "m_wave.png", "red")
    art(pack / "m_sad.png", "red")
    art(pack / "sheet.png", "grey")
    (pack / "manifest.json").write_text(json.dumps([{"item": "wave", "file": "m_wave.png", "passed": True},
                                                    {"item": "sad", "file": "m_sad.png", "passed": False}]))
    assert [p.name for p in story.cast_files(f"m={pack}")["m"]] == ["m_wave.png"]


def test_speaker_quotes_and_table_shape(tmp_path, capsys):
    for line, message in (("mika: 今日で最後なんだね", "must quote"), ("tobi: 「今日で最後なんだね」", "not on screen"),
                          ("mika: 「今日で最後なんだね\"", "quote"), ("mika: 「今日」と\"最後\"「", "unpaired")):
        draft, cast, script = fixture(tmp_path, cast2="mika")
        text = draft.read_text(encoding="utf-8").replace("mika: 「今日で最後なんだね」", line)
        draft.write_text(text, encoding="utf-8")
        shutil.rmtree(tmp_path / "proposal-v1", ignore_errors=True)
        assert propose(tmp_path, draft, cast, script) == 1
        assert message in capsys.readouterr().out, line


def test_dialogue_must_be_verbatim_and_cast_must_match(tmp_path, capsys):
    draft, cast, script = fixture(tmp_path, line="今日が最後なんだね")
    assert propose(tmp_path, draft, cast, script) == 1
    assert "verbatim" in capsys.readouterr().out
    draft, cast, script = fixture(tmp_path, cast2="mika, rin")
    assert propose(tmp_path, draft, cast, script, out="p2") == 1
    assert "unknown cast id: rin" in capsys.readouterr().out
    draft, _, script = fixture(tmp_path)
    assert propose(tmp_path, draft, f"mika={tmp_path / 'cast/mika'}", script, out="p3") == 1
    assert "must match --cast" in capsys.readouterr().out
    assert propose(tmp_path, draft, f"mika={tmp_path / 'missing.png'},tobi={tmp_path / 'tobi.png'}",
                   script, out="p4") == 1


def test_lines_without_a_script_are_pending(tmp_path, capsys):
    draft, cast, _ = fixture(tmp_path)
    assert propose(tmp_path, draft, cast) == 1
    assert "pending 'script'" in capsys.readouterr().out
    draft, cast, _ = fixture(tmp_path, pending="script", extra="## Pending\nscript: Writer write-script\n")
    assert propose(tmp_path, draft, cast, out="p2") == 0
    assert json.loads((tmp_path / "p2/proposal.json").read_text())["status"] == "pending-inputs"


def test_duration_limits_are_the_story_s_own(tmp_path):
    draft, cast, script = fixture(tmp_path)
    assert story.base.MIN_S == 10 and story.base.MAX_S == 120 and story.base.MOVIE == "story.mp4"
    promo = importlib.util.spec_from_file_location("promo_check", VIDEO / "create/promotion/scripts/promotion.py")
    module = importlib.util.module_from_spec(promo)
    promo.loader.exec_module(module)
    assert (module.MIN_S, module.MAX_S, module.MOVIE) == (3, 60, "promotion.mp4")
    short = draft.read_text(encoding="utf-8").replace("duration: 12", "duration: 8").replace("| 12 |", "| 8 |")
    draft.write_text(short, encoding="utf-8")
    assert propose(tmp_path, draft, cast, script) == 1


def test_render_requires_the_approved_cast_bytes(tmp_path, capsys):
    draft, cast, script = fixture(tmp_path)
    propose(tmp_path, draft, cast, script)
    approved = tmp_path / "proposal-v1/storyboard.md"
    digest = hashlib.sha256(approved.read_bytes()).hexdigest()
    source = tmp_path / "source"
    (source / "assets/cast/mika").mkdir(parents=True)
    shutil.copy(tmp_path / "cast/mika/front.png", source / "assets/cast/mika/front.png")
    art(source / "assets/cast/tobi/redrawn.png", "navy")  # a redrawn stand-in, not the approved bytes
    (source / ".cache").mkdir()
    shutil.copy(tmp_path / "tobi.png", source / ".cache/tobi.png")  # present but hidden and unreferenced
    (source / "index.html").write_text('<div id="root" data-composition-id="story" data-width="1080" '
                                       'data-height="1920" data-duration="12" data-fps="30">'
                                       '<img src="assets/cast/mika/front.png"><img src="assets/cast/tobi/redrawn.png">'
                                       '<img src=".cache/tobi.png"></div>')
    code = story.main(["render", "--approved-plan", str(approved), "--approval-sha256", digest,
                       "--source", str(source), "--out", str(tmp_path / "d1"), "--quality", "draft"])
    error = json.loads(capsys.readouterr().out.strip().splitlines()[-1][len("RESULT "):])["error"]
    assert code == 1 and error.endswith("referenced by the source: tobi")
    assert not (tmp_path / "d1").exists()
    code = story.main(["render", "--approved-plan", str(approved), "--approval-sha256", "0" * 64,
                       "--source", str(source), "--out", str(tmp_path / "d2"), "--quality", "draft"])
    assert code == 1 and "hash mismatch" in capsys.readouterr().out
    stray = source / "index.html"
    stray.write_text(stray.read_text().replace("redrawn.png", "tobi.png"), encoding="utf-8")
    shutil.copy(tmp_path / "tobi.png", source / "assets/cast/tobi/tobi.png")
    stray.write_text(stray.read_text() + '<div id="mix-caption-1" class="clip">x</div>', encoding="utf-8")
    code = story.main(["render", "--approved-plan", str(approved), "--approval-sha256", digest,
                       "--source", str(source), "--out", str(tmp_path / "d3"), "--quality", "draft"])
    assert code == 1 and "caption markup" in capsys.readouterr().out


def test_a_late_script_is_checked_at_the_final_render(tmp_path, capsys):
    draft, cast, _ = fixture(tmp_path, pending="script", extra="## Pending\nscript: Writer write-script\n")
    assert propose(tmp_path, draft, cast) == 0
    approved = tmp_path / "proposal-v1/storyboard.md"
    digest = hashlib.sha256(approved.read_bytes()).hexdigest()
    source = tmp_path / "source"
    source.mkdir()
    (source / "script.txt").write_text("mika: 別の台詞\n", encoding="utf-8")
    (tmp_path / "inputs.json").write_text(json.dumps({"script": "script.txt"}))
    code = story.main(["render", "--approved-plan", str(approved), "--approval-sha256", digest, "--source",
                       str(source), "--out", str(tmp_path / "f"), "--quality", "final", "--inputs", str(tmp_path / "inputs.json")])
    assert code == 1 and "verbatim" in capsys.readouterr().out


def test_leaf_form_and_routing():
    text = (LEAF / "SKILL.md").read_text(encoding="utf-8")
    end = text.index("\n---\n", 3) + len("\n---\n")
    assert end <= 3800
    meta = yaml.safe_load(text[3:end - 5])
    assert meta["name"] == "create-story"
    form = meta["metadata"]["hermes"]["form"]
    assert {k for k, v in form.items() if v.get("required")} == {"premise", "what_for", "cast"}
    for option in form["style"]["options"]:
        assert (LEAF / "references/styles" / f"{option}.md").is_file()
    body = " ".join(text[end:].split())
    assert "never redraw, restyle, trace or generate a character" in body
    assert "local-authoring fallback" in text.split("<Report>")[1]
    assert 'file_path="references/motion-vocabulary.md"' in text
    assert "create-story" in (VIDEO / "references/hyperframes.md").read_text()
    row = next(line for line in CAPABILITIES.read_text().splitlines() if "| video-creator: create-story |" in line)
    assert "no lip sync" in row
    prompt = yaml.safe_load((CREATOR / "config.yaml").read_text())["agent"]["system_prompt"]
    assert "is create-story on video-creator" in prompt
    for phase in ("plan", "build", "qa"):
        entry = CREATOR / f"skills/creator-pipeline/{phase}-creator"
        assert "[story](references/video-creator/story.md)" in (entry / "SKILL.md").read_text()


@pytest.mark.skipif(not shutil.which("hyperframes"), reason="hyperframes CLI not installed")
@pytest.mark.skipif(not os.environ.get("STORY_RENDER_SMOKE"), reason="set STORY_RENDER_SMOKE=1")
def test_render_smoke(tmp_path):
    draft, cast, script = fixture(tmp_path)
    propose(tmp_path, draft, cast, script)
    approved = tmp_path / "proposal-v1/storyboard.md"
    digest = hashlib.sha256(approved.read_bytes()).hexdigest()
    source = tmp_path / "source"
    (source / "assets/cast").mkdir(parents=True)
    for name in ("gsap.min.js", "GSAP-LICENSE.txt", "gsap-provenance.json"):
        shutil.copy(VIDEO / "create/tour/assets" / name, source / "assets" / name)
    shutil.copy(tmp_path / "cast/mika/happy.png", source / "assets/cast/mika.png")
    shutil.copy(tmp_path / "tobi.png", source / "assets/cast/tobi.png")
    (source / "index.html").write_text(
        '<!doctype html><html><body><div id="root" data-composition-id="story" data-start="0" '
        'data-width="1080" data-height="1920" data-duration="12" data-fps="30" style="background:#fff;'
        'width:1080px;height:1920px"><img id="mika" src="assets/cast/mika.png"><img id="tobi" '
        'src="assets/cast/tobi.png"></div><script src="assets/gsap.min.js"></script><script>'
        'const tl=gsap.timeline({paused:true});tl.from("#tobi",{x:400,duration:1},5);'
        'window.__timelines||={};window.__timelines["story"]=tl;</script></body></html>')
    assert story.main(["render", "--approved-plan", str(approved), "--approval-sha256", digest,
                       "--source", str(source), "--out", str(tmp_path / "final"), "--quality", "final"]) == 0
    result = json.loads((tmp_path / "final/render.json").read_text())
    assert result["status"] == "PASS" and result["cast_used"] == {"mika": 1, "tobi": 1}
    assert Path(result["movie"]).name == "story.mp4"
