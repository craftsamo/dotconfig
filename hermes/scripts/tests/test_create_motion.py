"""create-motion: storyboard/render helper contract and Creator routing."""

from __future__ import annotations

import hashlib
import importlib.util
import json
import shutil
from pathlib import Path

import pytest
import yaml

HERMES_ROOT = Path(__file__).resolve().parents[2]
VIDEO = HERMES_ROOT / "profiles/video-creator/skills/video-creator-pipeline"
LEAF = VIDEO / "create/motion"
CREATOR = HERMES_ROOT / "profiles/creator"
CAPABILITIES = CREATOR / "skills/creator-pipeline/references/capabilities.md"

spec = importlib.util.spec_from_file_location("motion", LEAF / "scripts/motion.py")
motion = importlib.util.module_from_spec(spec)
spec.loader.exec_module(motion)

STORYBOARD = """---
aspect: 16:9
duration: 4
fps: 30
audio: {audio}
pending: {pending}
---
# Fixture
## Beats
| # | start | end | scene | on-screen copy | motion | audio |
| --- | --- | --- | --- | --- | --- | --- |
| 1 | 0 | 1.5 | title | "One" | blur-in | intro |
| 2 | 1.5 | 4 | logo | "Two" | zoom-through | hit at 1.5 |
## Design
TEST FIXTURE only.
{extra}"""


def write(tmp_path, audio="none", pending="", extra=""):
    path = tmp_path / "draft.md"
    path.write_text(STORYBOARD.format(audio=audio, pending=pending, extra=extra))
    return path


def test_propose_hashes_exact_bytes(tmp_path):
    draft = write(tmp_path)
    result = motion.main(["propose", "--storyboard", str(draft), "--out", str(tmp_path / "proposal-v1")])
    assert result == 0
    stored = tmp_path / "proposal-v1/storyboard.md"
    data = json.loads((tmp_path / "proposal-v1/proposal.json").read_text())
    assert data["sha256"] == hashlib.sha256(stored.read_bytes()).hexdigest()
    assert data["status"] == "awaiting-approval"
    assert (data["width"], data["height"], data["beats"]) == (1920, 1080, 2)


def test_pending_audio_needs_a_described_dependency(tmp_path):
    draft = write(tmp_path, audio="pending", pending="audio")
    with pytest.raises(motion.Fail, match="## Pending"):
        motion.parse_storyboard(draft)
    draft = write(tmp_path, audio="pending", pending="audio",
                  extra="## Pending\naudio: audio-creator Mix master, 4s\n")
    info = motion.parse_storyboard(draft)
    assert info["pending"] == ["audio"]
    with pytest.raises(motion.Fail, match="go together"):
        motion.parse_storyboard(write(tmp_path, audio="none", pending="audio",
                                      extra="## Pending\naudio: x\n"))


@pytest.mark.parametrize("bad, message", [
    ("| 1 | 0 | 1.0 | a | b | c | d |\n| 2 | 1.5 | 4 | a | b | c | d |", "contiguous"),
    ("| 1 | 0 | 1.5 | a | b | c | d |\n| 2 | 1.5 | 3 | a | b | c | d |", "end at the storyboard duration"),
])
def test_beats_must_cover_the_duration(tmp_path, bad, message):
    text = STORYBOARD.format(audio="none", pending="", extra="")
    rows = text.split("| --- | --- | --- | --- | --- | --- | --- |\n")
    body = rows[1].split("## Design")
    draft = tmp_path / "bad.md"
    draft.write_text(rows[0] + "| --- | --- | --- | --- | --- | --- | --- |\n" + bad + "\n## Design" + body[1])
    with pytest.raises(motion.Fail, match=message):
        motion.parse_storyboard(draft)


def test_render_refuses_changed_storyboard_and_remote_source(tmp_path):
    draft = write(tmp_path)
    motion.main(["propose", "--storyboard", str(draft), "--out", str(tmp_path / "p")])
    approved = tmp_path / "p/storyboard.md"
    digest = hashlib.sha256(approved.read_bytes()).hexdigest()
    source = tmp_path / "source"
    (source / "assets").mkdir(parents=True)
    root = ('<div id="root" data-composition-id="motion" data-start="0" data-width="1920" '
            'data-height="1080" data-duration="4" data-fps="30"></div>')
    (source / "index.html").write_text(root + '<img src="https://example.com/x.png">')
    args = ["render", "--approved-plan", str(approved), "--source", str(source), "--quality", "draft"]
    assert motion.main([*args, "--approval-sha256", "0" * 64, "--out", str(tmp_path / "o1")]) == 1
    assert not (tmp_path / "o1").exists()
    plan = motion.parse_storyboard(approved)
    with pytest.raises(motion.Fail, match="remote"):
        motion.check_source(source, plan)
    (source / "index.html").write_text(root.replace('data-width="1920"', 'data-width="1080"'))
    with pytest.raises(motion.Fail, match="canvas"):
        motion.check_source(source, plan)


def test_leaf_form_and_shared_policy():
    leaf = (LEAF / "SKILL.md").read_text()
    meta = yaml.safe_load(leaf.split("---")[1])["metadata"]["hermes"]
    assert meta["hands"] == "video-creator" and meta["cost"] == "free"
    assert {"subject", "what_for", "approved_plan", "approval_sha256", "inputs"} <= set(meta["form"])
    assert len(leaf.split("---")[1]) < 3800
    assert 'file_path="references/hyperframes.md"' in leaf
    assert "dependency request back to Creator" in leaf
    assert "create-motion" in (VIDEO / "references/hyperframes.md").read_text()


def test_creator_routes_authored_motion_to_video_creator():
    table = CAPABILITIES.read_text()
    assert "| video-creator: create-motion |" in table
    legacy = next(line for line in table.splitlines() if "`creator-html-motion` |" in line)
    assert "create-motion first" in legacy
    prompt = yaml.safe_load((CREATOR / "config.yaml").read_text())["agent"]["system_prompt"]
    assert "create-motion on video-creator" in prompt
    assert "you do not author that HTML motion" in prompt
    for phase in ("plan", "build", "qa"):
        entry = CREATOR / f"skills/creator-pipeline/{phase}-creator"
        assert "references/video-creator/motion.md" in (entry / "SKILL.md").read_text()
        assert (entry / "references/video-creator/motion.md").is_file()


@pytest.mark.skipif(not shutil.which("hyperframes"), reason="hyperframes CLI not installed")
@pytest.mark.skipif(not __import__("os").environ.get("MOTION_RENDER_SMOKE"), reason="set MOTION_RENDER_SMOKE=1")
def test_render_smoke(tmp_path):
    draft = write(tmp_path)
    motion.main(["propose", "--storyboard", str(draft), "--out", str(tmp_path / "p")])
    approved = tmp_path / "p/storyboard.md"
    digest = hashlib.sha256(approved.read_bytes()).hexdigest()
    source = tmp_path / "source"
    (source / "assets").mkdir(parents=True)
    for name in ("gsap.min.js", "GSAP-LICENSE.txt", "gsap-provenance.json"):
        shutil.copy(VIDEO / "create/tour/assets" / name, source / "assets" / name)
    (source / "index.html").write_text(
        '<!doctype html><html><body><div id="root" data-composition-id="motion" data-start="0" '
        'data-width="1920" data-height="1080" data-duration="4" data-fps="30" style="background:#fff;'
        'width:1920px;height:1080px"><div id="t">Fixture</div></div><script src="assets/gsap.min.js">'
        '</script><script>const tl=gsap.timeline({paused:true});tl.from("#t",{opacity:0,duration:1},0);'
        'window.__timelines||={};window.__timelines["motion"]=tl;</script></body></html>')
    assert motion.main(["render", "--approved-plan", str(approved), "--approval-sha256", digest,
                        "--source", str(source), "--out", str(tmp_path / "final"), "--quality", "final"]) == 0
    result = json.loads((tmp_path / "final/render.json").read_text())
    assert result["status"] == "PASS" and result["probe"]["duration"] == 4.0
