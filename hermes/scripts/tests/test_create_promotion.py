"""create-promotion: storyboard/render helper contract and Creator routing."""

from __future__ import annotations

import hashlib
import importlib.util
import json
import shutil
from pathlib import Path

import pytest
import hermes_yaml as yaml

HERMES_ROOT = Path(__file__).resolve().parents[2]
VIDEO = HERMES_ROOT / "profiles/video-creator/skills/video-creator-pipeline"
LEAF = VIDEO / "create/promotion"
CREATOR = HERMES_ROOT / "profiles/creator"
ADVISOR = CREATOR / "skills/creator-pipeline/references/video-creator/promotion.md"
COMMISSION = HERMES_ROOT / "profiles/assistant/skills/assistant-pipeline/execute-assistant-creative/references/promotion.md"

spec = importlib.util.spec_from_file_location("promotion", LEAF / "scripts/promotion.py")
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
    root = ('<div id="root" data-composition-id="promotion" data-start="0" data-width="1920" '
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
    assert "dependency request back to the Assistant" in leaf
    assert "create-promotion" in (VIDEO / "references/hyperframes.md").read_text()


def test_assistant_commissions_authored_motion_and_creator_only_advises():
    commission = COMMISSION.read_text()
    assert "## Leaves" in commission and "| `create-promotion` |" in commission
    assert 'specialist_call(target="video-creator"' in commission and 'kind="work"' in commission
    assert "[commissioning](../SKILL.md)" in commission
    assert ADVISOR.is_file() and "`create-promotion`" in ADVISOR.read_text()
    assert "(references/video-creator/promotion.md)" in (CREATOR / "skills/creator-pipeline/SKILL.md").read_text()
    config = yaml.safe_load((CREATOR / "config.yaml").read_text())
    assert config["specialist_call"]["resident_targets"] == ["researcher", "searcher"]
    assert "video_gen" not in config["toolsets"] and "image_gen" not in config["toolsets"]
    prompt = yaml.safe_load((HERMES_ROOT / "profiles/assistant/config.example.yaml").read_text())
    assert "video-creator" in prompt["specialist_call"]["resident_targets"]


@pytest.mark.skipif(not shutil.which("hyperframes"), reason="hyperframes CLI not installed")
@pytest.mark.skipif(not __import__("os").environ.get("PROMOTION_RENDER_SMOKE"), reason="set PROMOTION_RENDER_SMOKE=1")
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
        '<!doctype html><html><body><div id="root" data-composition-id="promotion" data-start="0" '
        'data-width="1920" data-height="1080" data-duration="4" data-fps="30" style="background:#fff;'
        'width:1920px;height:1080px"><div id="t">Fixture</div></div><script src="assets/gsap.min.js">'
        '</script><script>const tl=gsap.timeline({paused:true});tl.from("#t",{opacity:0,duration:1},0);'
        'window.__timelines||={};window.__timelines["promotion"]=tl;</script></body></html>')
    assert motion.main(["render", "--approved-plan", str(approved), "--approval-sha256", digest,
                        "--source", str(source), "--out", str(tmp_path / "final"), "--quality", "final"]) == 0
    result = json.loads((tmp_path / "final/render.json").read_text())
    assert result["status"] == "PASS" and result["probe"]["duration"] == 4.0


def test_storyboard_approves_structure_not_pixels():
    leaf = (LEAF / "SKILL.md").read_text()
    authoring = (LEAF / "references/authoring.md").read_text()
    assert "never fixes pixel sizes" in leaf and "by redesign, not nudges" in leaf
    assert "up to 8 drafts" in leaf and "<Standard>" in leaf
    assert "never in pixels" in authoring and "## Look" in authoring
    commission = COMMISSION.read_text()
    assert "needs no new approval" in commission and "Small execution fixes" not in commission


@pytest.mark.skipif(not shutil.which("ffmpeg"), reason="ffmpeg not installed")
def test_compare_sheet_stacks_reference_over_draft(tmp_path):
    import subprocess
    for name, colour in (("ref.mp4", "red"), ("draft.mp4", "blue")):
        subprocess.run(["ffmpeg", "-v", "error", "-f", "lavfi", "-i", f"color={colour}:size=640x360:rate=30",
                        "-t", "2", str(tmp_path / name)], check=True)
    motion.compare_sheet(tmp_path / "ref.mp4", tmp_path / "draft.mp4", 2.0, tmp_path / "compare.png")
    out = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "stream=width,height", "-of", "csv=p=0",
                          str(tmp_path / "compare.png")], capture_output=True, text=True).stdout.strip()
    assert out == "3200,452"
    assert not list(tmp_path.glob(".compare-*"))


@pytest.mark.skipif(not shutil.which("ffmpeg"), reason="ffmpeg not installed")
def test_compare_sheet_handles_shorter_reference_of_another_aspect(tmp_path):
    import subprocess
    for name, size, seconds in (("ref.mp4", "640x360", "1"), ("draft.mp4", "360x640", "3")):
        subprocess.run(["ffmpeg", "-v", "error", "-f", "lavfi", "-i", f"color=red:size={size}:rate=30",
                        "-t", seconds, str(tmp_path / name)], check=True)
    motion.compare_sheet(tmp_path / "ref.mp4", tmp_path / "draft.mp4", 3.0, tmp_path / "compare.png")
    out = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "stream=width,height", "-of", "csv=p=0",
                          str(tmp_path / "compare.png")], capture_output=True, text=True).stdout.strip()
    assert out == "3200,938"
    assert not list(tmp_path.glob(".compare-*"))


def test_round_a_names_techniques_from_the_vocabulary():
    leaf = (LEAF / "SKILL.md").read_text()
    vocab = (LEAF.parent.parent / "references/motion-vocabulary.md").read_text()
    assert 'file_path="references/motion-vocabulary.md"' in leaf
    assert "name the" in leaf and 'instead of generic "fade", "slide" or "card"' in " ".join(leaf.split())
    for section in ("## Text animations", "## Transitions", "## Camera", "## Effects", "## Components", "## Compositions"):
        assert section in vocab
    assert "A dictionary, not a rulebook" in vocab


def test_pv_and_series_are_promotion_not_a_new_subject():
    text = (LEAF / "SKILL.md").read_text()
    meta = yaml.safe_load(text.split("---")[1])
    assert meta["metadata"]["hermes"]["form"]["series_of"]["type"] == "path"
    assert "PV/showcase reel" in " ".join(meta["description"].split())
    body = " ".join(text.split())
    assert "never redrawn as stand-ins" in body and "never invented" in body
    authoring = (LEAF / "references/authoring.md").read_text()
    assert "## Showcase and series" in authoring and "the earlier episode is never edited" in authoring
    vocab = (LEAF.parent.parent / "references/motion-vocabulary.md").read_text()
    assert "## Film structures" in vocab and "showcase reel (PV)" in vocab
    assert not (LEAF.parent / "pv").exists()
    row = next(line for line in COMMISSION.read_text().splitlines() if line.endswith("| `create-promotion` | free"
               ) or "| `create-promotion` |" in line)
    assert "PV/showcase reel" in row and "`series_of`" in row
    assert "showcase reel" in ADVISOR.read_text() and "`series_of`" in ADVISOR.read_text()


# ── frame rate ─────────────────────────────────────────────────────────


def with_fps(tmp_path, value, name="draft.md"):
    path = tmp_path / name
    text = STORYBOARD.format(audio="none", pending="", extra="")
    path.write_text(text.replace("fps: 30\n", "" if value is None else f"fps: {value}\n"))
    return path


@pytest.mark.parametrize("value, expected", [(None, 30), ("24", 24), ("25", 25), ("30", 30),
                                             ("50", 50), ("60", 60), ('"60"', 60), ("60  # smooth", 60)])
def test_storyboard_fps_is_one_of_the_allowed_rates(tmp_path, value, expected):
    assert motion.parse_storyboard(with_fps(tmp_path, value))["fps"] == expected


@pytest.mark.parametrize("value", ["29.97", "59.94", "120", "240", "0", "abc", ""])
def test_storyboard_rejects_other_rates(tmp_path, value):
    with pytest.raises(motion.Fail, match="fps must be one of 24/25/30/50/60"):
        motion.parse_storyboard(with_fps(tmp_path, value))


def root_html(fps=None, duration="4"):
    rate = "" if fps is None else f' data-fps="{fps}"'
    return ('<div id="root" data-composition-id="promotion" data-start="0" data-width="1920" '
            f'data-height="1080" data-duration="{duration}"{rate}></div>')


def test_source_data_fps_must_match_the_storyboard(tmp_path):
    plan = motion.parse_storyboard(with_fps(tmp_path, "60"))
    source = tmp_path / "source"
    source.mkdir()
    for ok in (60, None):
        (source / "index.html").write_text(root_html(ok))
        motion.check_source(source, plan)
    (source / "index.html").write_text(root_html(30))
    with pytest.raises(motion.Fail, match="data-fps must be 60"):
        motion.check_source(source, plan)
    (source / "index.html").write_text(root_html(60, duration="4.03"))
    with pytest.raises(motion.Fail, match="data-duration"):
        motion.check_source(source, plan)


@pytest.mark.skipif(not shutil.which("ffmpeg") or not shutil.which("ffprobe"), reason="ffmpeg not installed")
@pytest.mark.parametrize("rate, suggested", [("60", 60), ("60000/1001", 60), ("24000/1001", 24), ("25", 25)])
def test_propose_reports_the_reference_rate_without_rewriting(tmp_path, rate, suggested):
    import subprocess
    reference = tmp_path / "ref.mp4"
    subprocess.run(["ffmpeg", "-v", "error", "-f", "lavfi", "-i", f"color=red:size=320x180:rate={rate}",
                    "-t", "1", str(reference)], check=True)
    draft = with_fps(tmp_path, None)
    original = draft.read_bytes()
    assert motion.main(["propose", "--storyboard", str(draft), "--out", str(tmp_path / "p"),
                        "--reference", str(reference)]) == 0
    data = json.loads((tmp_path / "p/proposal.json").read_text())
    assert data["suggested_fps"] == suggested and abs(data["reference_fps"] - float(eval(rate))) < 0.01
    assert data["fps"] == 30 and (tmp_path / "p/storyboard.md").read_bytes() == original


def test_propose_with_missing_reference_writes_nothing(tmp_path):
    draft = with_fps(tmp_path, None)
    assert motion.main(["propose", "--storyboard", str(draft), "--out", str(tmp_path / "p"),
                        "--reference", str(tmp_path / "missing.mp4")]) == 1
    assert not (tmp_path / "p").exists()


def fake_hyperframes(monkeypatch):
    import subprocess
    seen = []

    def run(cmd, cwd=None, timeout=1800):
        if cmd[1] == "lint":
            return subprocess.CompletedProcess(cmd, 0, json.dumps({"ok": True, "errorCount": 0, "filesScanned": 1}), "")
        if cmd[1] == "render":
            Path(cmd[cmd.index("--output") + 1]).write_bytes(b"fake")
            seen.append(int(cmd[cmd.index("--fps") + 1]))
        return subprocess.CompletedProcess(cmd, 0, "", "")

    monkeypatch.setattr(motion, "run", run)
    monkeypatch.setattr(motion.shutil, "which", lambda name: "/fake/hyperframes")
    monkeypatch.setattr(motion, "contact_sheet", lambda *args: None)
    monkeypatch.setattr(motion, "probe", lambda movie: {"width": 1920, "height": 1080, "fps": float(seen[-1]),
                                                       "duration": 4.0, "audio": False})
    return seen


@pytest.mark.parametrize("value, draft_rate, final_rate", [("60", 30, 60), ("50", 30, 50), ("24", 24, 24), (None, 30, 30)])
def test_drafts_render_at_most_30fps_and_the_final_at_the_approved_rate(tmp_path, monkeypatch, value, draft_rate, final_rate):
    draft = with_fps(tmp_path, value)
    assert motion.main(["propose", "--storyboard", str(draft), "--out", str(tmp_path / "p")]) == 0
    approved = tmp_path / "p/storyboard.md"
    digest = hashlib.sha256(approved.read_bytes()).hexdigest()
    source = tmp_path / "source"
    source.mkdir()
    (source / "index.html").write_text(root_html(None if value is None else final_rate))
    seen = fake_hyperframes(monkeypatch)
    args = ["render", "--approved-plan", str(approved), "--approval-sha256", digest, "--source", str(source)]
    for quality, rate in (("draft", draft_rate), ("final", final_rate)):
        assert motion.main([*args, "--out", str(tmp_path / quality), "--quality", quality]) == 0
        result = json.loads((tmp_path / quality / "render.json").read_text())
        assert result["fps"] == rate and result["approved_fps"] == final_rate and result["checks"]["fps"]
    assert seen == [draft_rate, final_rate]
