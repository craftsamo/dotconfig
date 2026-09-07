"""Local-only v3 media and acquisition contracts; no model sessions or uploads."""

import json
import os
import shutil
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parents[2]
LEAF = ROOT / "profiles/video-creator/skills/video-creator-pipeline/create/tour"
sys.path.insert(0, str(LEAF / "scripts"))
import approval
import authored
import capture
import footage


def proposal(job, form, scope=None, version=1):
    path = job / f"proposal-v{version}.md"
    data = {"form": form}
    if scope is not None:
        data["scope"] = scope
    path.write_text("# Approved local dummy test\n\n```tour\n" + json.dumps(data) + "\n```\n")
    return str(path), authored.digest(path)


@pytest.fixture
def scope_job(tmp_path):
    job = tmp_path.resolve()
    target = "http://127.0.0.1:8000/"
    form = authored.form_model({"what_for": "Show demo", "audience": "Beginners", "screen_mode": "capture",
        "target": target, "source": str(job / "source.json"), "start_state": "Demo"})
    scope = {"platform": "web", "target": target, "origins": [target[:-1]], "start_state": "Demo",
        "allowed_actions": {"click": ["#open"], "type": ["#name"], "scroll": ["down"]}, "demo_data": ["Demo"],
        "forbidden": ["credentials", "purchases", "send", "delete", "uploads", "private-regions"],
        "privacy": "sanitized-demo-only", "max_seconds": 30, "max_attempts": 2, "max_actions": 5, "read_only_recon": True}
    return job, form, scope


@pytest.mark.parametrize("command", [["eval", "document.body.innerHTML"], ["open", "https://other.test"],
    ["type", "#name", "not approved"], ["type", "#password", "Demo"], ["click", "@e1"],
    ["click", "#delete"], ["scroll", "down", "9999"], ["wait", "6000"], ["press", "Enter"],
    ["upload", "#file", "/private/file"], ["record", "start", "/tmp/x"], ["click", "#open", "extra"]])
def test_capture_command_surface(scope_job, command):
    with pytest.raises(ValueError):
        capture.commands_model([command], scope_job[2])


@pytest.mark.parametrize("key,value", [("platform", "macos"), ("privacy", "mask later"),
    ("read_only_recon", False), ("max_attempts", 3), ("max_seconds", 181), ("forbidden", []),
    ("origins", ["https://other.test"]), ("target", "http://127.0.0.1:9999/")])
def test_capture_scope_fails_closed(scope_job, key, value):
    _, form, scope = scope_job
    scope[key] = value
    with pytest.raises(ValueError):
        capture.scope_model({"form": form, "scope": scope})


def test_approval_and_mode_gates_before_browser(scope_job, monkeypatch):
    job, form, scope = scope_job
    def forbidden(*args, **kwargs):
        pytest.fail("browser must not be acquired")
    monkeypatch.setattr(capture, "Browser", forbidden)
    path, sha = proposal(job, form, scope)
    with pytest.raises(ValueError, match="changed"):
        capture.acquire(str(job), path, "0" * 64, [], recon=True)
    for mode in ("recreate", "supplied"):
        other = {**form, "screen_mode": mode}
        path, sha = proposal(job, other, scope, 2 if mode == "recreate" else 3)
        with pytest.raises(ValueError, match="only capture"):
            capture.acquire(str(job), path, sha, [], recon=True)


def test_proposal_binds_form_not_just_path(scope_job):
    job, form, _ = scope_job
    path, sha = proposal(job, form)
    full = {**form, "approved_plan": path, "approval_sha256": sha}
    approval.form_approval(full)
    full["style"] = "glass"
    with pytest.raises(ValueError, match="differs"):
        approval.form_approval(full)


class FakeBrowser:
    calls = []
    fail = None
    field_type = "text"

    def __init__(self, run, scope, session):
        self.run, self.scope = run, scope
        self.calls.append(("session", session))

    def call(self, *args, **kwargs):
        self.calls.append(args)
        if args[0] == self.fail:
            raise KeyboardInterrupt()
        if args == ("tab", "list"):
            return {"tabs": [{"tabId": "t1", "url": self.scope["target"], "active": True}]}
        if args[:2] == ("get", "attr"):
            return {"value": self.field_type}
        if args[:2] == ("record", "stop"):
            (self.run / "raw.webm").write_bytes(b"dummy raw")
        return {"text": "Demo"}

    def state(self):
        return {"snapshot": "Demo"}


@pytest.fixture
def fake_browser(monkeypatch):
    FakeBrowser.calls, FakeBrowser.fail, FakeBrowser.field_type = [], None, "text"
    monkeypatch.setattr(capture, "Browser", FakeBrowser)
    monkeypatch.setattr(capture, "probe", lambda *a, **k: {"duration": 2, "kind": "video"})
    return FakeBrowser


def test_cancel_preserves_raw_and_blocks_blind_restart(scope_job, fake_browser):
    job, form, scope = scope_job
    path, sha = proposal(job, form, scope)
    capture.acquire(str(job), path, sha, [], recon=True)
    fake_browser.fail = "click"
    with pytest.raises(KeyboardInterrupt):
        capture.acquire(str(job), path, sha, [["click", "#open"]])
    journal = next(job.glob("take-*/actions.jsonl"))
    assert '"pending"' in journal.read_text() and '"complete"' not in journal.read_text()
    assert (journal.parent / "raw.webm").exists()
    assert authored.load(journal.parent / "closed.json")["status"] == "interrupted"
    assert ("record", "stop") in fake_browser.calls and ("close",) in fake_browser.calls
    with pytest.raises(ValueError, match="cannot be replayed"):
        capture.acquire(str(job), path, sha, [["click", "#open"]])


def test_password_rejected_and_logs_redact_dummy_values(scope_job, fake_browser):
    job, form, scope = scope_job
    path, sha = proposal(job, form, scope)
    capture.acquire(str(job), path, sha, [], recon=True)
    fake_browser.field_type = "password"
    with pytest.raises(ValueError, match="secret/non-text"):
        capture.acquire(str(job), path, sha, [["type", "#name", "Demo"]])
    assert not any(c[0] == "type" for c in fake_browser.calls)


def test_recon_then_record_bound_attempts_and_redaction(scope_job, fake_browser):
    job, form, scope = scope_job
    path, sha = proposal(job, form, scope)
    with pytest.raises(ValueError, match="reconnaissance"):
        capture.acquire(str(job), path, sha, [])
    capture.acquire(str(job), path, sha, [], recon=True)
    for _ in range(2):
        result = capture.acquire(str(job), path, sha, [["type", "#name", "Demo"]])
        journal = (Path(result["capture"]) / "actions.jsonl").read_text()
        assert '"Demo"' not in journal and "[approved dummy value]" in journal
    with pytest.raises(ValueError, match="ceiling"):
        capture.acquire(str(job), path, sha, [])


def test_unknown_selectors_interrupted_take_and_reapproval_keep_second_take(scope_job, fake_browser):
    job, form, scope = scope_job
    first, first_sha = proposal(job, form, {**scope, "allowed_actions": {}})
    capture.acquire(str(job), first, first_sha, [], recon=True)
    second, second_sha = proposal(job, form, scope, 2)
    commands = [["click", "#open"]]
    with pytest.raises(ValueError, match="reconnaissance"):
        capture.acquire(str(job), second, second_sha, commands)
    capture.acquire(str(job), second, second_sha, [], recon=True)
    fake_browser.fail = "click"
    with pytest.raises(KeyboardInterrupt):
        capture.acquire(str(job), second, second_sha, commands)
    fake_browser.fail = None
    journal = next(job.glob("take-*/actions.jsonl"))
    assert '"pending"' in journal.read_text() and '"complete"' not in journal.read_text()
    assert (journal.parent / "raw.webm").is_file()
    for recon in (False, True):
        with pytest.raises(ValueError, match="cannot be replayed"):
            capture.acquire(str(job), second, second_sha, [] if recon else commands, recon=recon)
    previous = {p: authored.digest(p) for p in job.rglob("*") if p.is_file()}
    third, third_sha = proposal(job, {**form, "note": "Unknown action reconciled; approve the second take"}, scope, 3)
    with pytest.raises(ValueError, match="reconnaissance"):
        capture.acquire(str(job), third, third_sha, commands)
    capture.acquire(str(job), third, third_sha, [], recon=True)
    result = capture.acquire(str(job), third, third_sha, commands)
    assert authored.load(Path(result["receipt"]))["approval_sha256"] == third_sha
    assert all(authored.digest(p) == sha for p, sha in previous.items())
    leases = [authored.load(p) for p in job.glob("take-*/lease.json")]
    assert len(leases) == 5 and sum(not lease["recon"] for lease in leases) == 2
    fourth, fourth_sha = proposal(job, {**form, "note": "A new proposal cannot reset the global take count"}, scope, 4)
    capture.acquire(str(job), fourth, fourth_sha, [], recon=True)
    with pytest.raises(ValueError, match="attempt ceiling"):
        capture.acquire(str(job), fourth, fourth_sha, commands)


def test_recon_budget_is_bounded_and_does_not_consume_takes(scope_job, fake_browser):
    job, form, scope = scope_job
    path, sha = proposal(job, form, scope)
    for _ in range(4):
        capture.acquire(str(job), path, sha, [], recon=True)
    calls = list(fake_browser.calls)
    another, another_sha = proposal(job, {**form, "note": "New proposal, same job budget"}, scope, 2)
    with pytest.raises(ValueError, match="reconnaissance ceiling"):
        capture.acquire(str(job), another, another_sha, [], recon=True)
    assert fake_browser.calls == calls
    for _ in range(2):
        capture.acquire(str(job), path, sha, [])
    with pytest.raises(ValueError, match="attempt ceiling"):
        capture.acquire(str(job), path, sha, [])


@pytest.mark.parametrize("interruption", ["timeout", "termination"])
def test_browser_closed_before_decode_and_failed_decode_retains_evidence(scope_job, fake_browser, monkeypatch, interruption):
    import subprocess
    job, form, scope = scope_job
    path, sha = proposal(job, form, scope)
    capture.acquire(str(job), path, sha, [], recon=True)
    def fail_probe(*args, **kwargs):
        assert fake_browser.calls[-1] == ("close",)
        if interruption == "timeout":
            raise subprocess.TimeoutExpired("ffmpeg", 360)
        raise KeyboardInterrupt()
    monkeypatch.setattr(capture, "probe", fail_probe)
    with pytest.raises((subprocess.TimeoutExpired, KeyboardInterrupt)):
        capture.acquire(str(job), path, sha, [])
    raw = next(job.glob("take-*/raw.webm"))
    assert authored.load(raw.parent / "closed.json")["status"] == "interrupted"
    assert not (raw.parent / "receipt.json").exists()
    assert fake_browser.calls.count(("close",)) == 2
    with pytest.raises(ValueError, match="cannot be replayed"):
        capture.acquire(str(job), path, sha, [])


def test_browser_subprocess_timeouts_respect_session_and_cleanup_bounds(scope_job, monkeypatch):
    job, _, scope = scope_job
    scope["max_seconds"] = 180
    now = [1000]
    monkeypatch.setattr(capture.time, "monotonic", lambda: now[0])
    timeouts = []
    def run(*args, **kwargs):
        timeouts.append(kwargs["timeout"])
        return SimpleNamespace(returncode=0, stdout='{"success":true,"data":{}}')
    monkeypatch.setattr(capture.subprocess, "run", run)
    browser = capture.Browser(job, scope, "tour-0123456789abcdef")
    assert browser.deadline == 1180
    browser.call("snapshot", "-i")
    now[0] = 1175
    browser.call("snapshot", "-i")
    now[0] = 1181
    with pytest.raises(ValueError, match="lease expired"):
        browser.call("snapshot", "-i")
    browser.call("close", cleanup=True)
    assert timeouts == [20, 5, 20]


def test_unclosed_lease_blocks_capture(scope_job, fake_browser):
    job, form, scope = scope_job
    path, sha = proposal(job, form, scope)
    stale = job / "take-stale"
    stale.mkdir()
    authored.write(stale / "lease.json", {"session": "tour-0123456789abcdef", "approval_sha256": sha})
    with pytest.raises(ValueError, match="interrupted lease"):
        capture.acquire(str(job), path, sha, [], recon=True)
    assert fake_browser.calls == []


def test_job_lease_concurrency(scope_job, fake_browser):
    import fcntl
    job, form, scope = scope_job
    path, sha = proposal(job, form, scope)
    with (job / "capture.lock").open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        with pytest.raises(ValueError, match="already leased"):
            capture.acquire(str(job), path, sha, [], recon=True)
    assert fake_browser.calls == []


def test_recover_closes_owned_session_without_replay(scope_job, fake_browser):
    job, form, scope = scope_job
    path, sha = proposal(job, form, scope)
    stale = job / "take-stale"
    stale.mkdir()
    authored.write(stale / "lease.json", {"session": "tour-0123456789abcdef", "approval_sha256": sha})
    authored.write(stale / "browser.json", {})
    result = capture.acquire(str(job), path, sha, [], recover=True)
    assert result["status"] == "recovered" and fake_browser.calls == [("close",)]
    with pytest.raises(ValueError, match="cannot be replayed"):
        capture.acquire(str(job), path, sha, [], recon=True)


def test_isolated_environment_and_expiry(scope_job, monkeypatch):
    job, _, scope = scope_job
    monkeypatch.setenv("AGENT_BROWSER_PROFILE", "/daily")
    monkeypatch.setenv("AGENT_BROWSER_CDP", "9333")
    monkeypatch.setenv("HTTPS_PROXY", "http://proxy.invalid")
    monkeypatch.setenv("AGENT_BROWSER_INIT_SCRIPTS", "/script.js")
    browser = capture.Browser(job, scope, "tour-0123456789abcdef")
    assert not {"AGENT_BROWSER_PROFILE", "AGENT_BROWSER_CDP", "HTTPS_PROXY", "AGENT_BROWSER_INIT_SCRIPTS"} & browser.env.keys()
    assert "--namespace" in browser.argv and "--config" in browser.argv
    browser.deadline = 0
    with pytest.raises(ValueError, match="lease expired"):
        browser.call("click", "#open")


@pytest.mark.parametrize("url,tabs", [("https://other.test/", []), ("http://127.0.0.1:8000/", [
    {"url": "http://127.0.0.1:8000/"}, {"url": "http://127.0.0.1:8000/popup"}]),
    ("http://127.0.0.1:9999/", [])])
def test_redirect_popup_and_port_drift(scope_job, url, tabs):
    job, _, scope = scope_job
    browser = capture.Browser(job, scope, "tour-0123456789abcdef")
    browser.call = lambda *args: {"url": url} if args == ("get", "url") else {"tabs": tabs}
    with pytest.raises(ValueError):
        browser.state()


@pytest.fixture
def video(tmp_path):
    path = tmp_path.resolve() / "raw.mp4"
    authored.command(["ffmpeg", "-nostdin", "-v", "error", "-n", "-f", "lavfi", "-i", "testsrc2=size=320x180:rate=30",
        "-f", "lavfi", "-i", "sine=frequency=440:sample_rate=48000", "-t", "3", "-c:v", "libx264", "-pix_fmt", "yuv420p",
        "-c:a", "aac", str(path)])
    return path


def manifest_for(video, audio="mute"):
    return {"clips": [{"id": "demo", "path": str(video), "sha256": footage.sha256(video),
                      "source_start": .5, "duration": 2, "timeline_start": 2, "audio": audio}]}


@pytest.mark.parametrize("audio", ["keep", "mute"])
def test_real_video_trim_decode_and_audio_policy(video, audio):
    manifest = video.parent / "source.json"
    authored.write(manifest, manifest_for(video, audio))
    out = video.parent / "prepared"
    footage.prepare(str(manifest), str(out))
    result = footage.probe(out / "demo.mp4", decode=True)
    assert result["audio"] == (audio == "keep")
    assert abs(result["duration"] - 2) < .1
    record = authored.load(out / "media.json")["clips"][0]
    assert record["source_start"] == .5 and record["media_start"] == 0
    assert record["raw_sha256"] == footage.sha256(video)
    with pytest.raises(ValueError, match="must not exist"):
        footage.prepare(str(manifest), str(out))


def test_probe_and_decode_have_separate_bounded_subprocesses(video, monkeypatch):
    run = footage.command
    timeouts = []
    def checked(args, **kwargs):
        timeouts.append((args[0], kwargs["timeout"]))
        return run(args, **kwargs)
    monkeypatch.setattr(footage, "command", checked)
    footage.probe(video, decode=True)
    assert timeouts == [("ffprobe", 180), ("ffmpeg", 360)]


@pytest.mark.parametrize("key,value", [("source_start", 2), ("duration", 61), ("audio", "auto"),
    ("sha256", "0"*64), ("timeline_start", 59), ("path", "https://example.test/video.mp4")])
def test_invalid_sources_before_publication(video, key, value):
    manifest = manifest_for(video)
    manifest["clips"][0][key] = value
    path = video.parent / "source.json"
    authored.write(path, manifest)
    with pytest.raises(ValueError):
        footage.prepare(str(path), str(video.parent / "prepared"))
    assert not (video.parent / "prepared").exists()


def test_raw_bounds_independent_of_final_and_no_symlinks(tmp_path):
    path = tmp_path.resolve() / "big.mp4"
    with path.open("wb") as stream:
        stream.truncate(512_000_001)
    with pytest.raises(ValueError, match="512 MB"):
        footage.media_path(str(path))
    link = path.with_name("link.mp4")
    link.symlink_to(path)
    with pytest.raises(ValueError, match="symlink"):
        footage.media_path(str(link))


def test_supplied_freeze_actual_video_and_standalone_resume(video):
    root = video.parent
    source = root / "source"
    (source / "assets").mkdir(parents=True)
    manifest = root / "source.json"
    authored.write(manifest, manifest_for(video, "keep"))
    footage.prepare(str(manifest), str(source / "assets/footage"))
    for name in ("gsap.min.js", "GSAP-LICENSE.txt", "gsap-provenance.json"):
        shutil.copyfile(LEAF / "assets" / name, source / "assets" / name)
    source.joinpath("index.html").write_text('''<script src="assets/gsap.min.js"></script>
<div data-composition-id="tour" data-start="0" data-width="1280" data-height="720" data-fps="30" data-duration="6">
<video id="demo" src="assets/footage/demo.mp4" data-start="2" data-duration="2" data-media-start="0" muted playsinline></video>
<audio id="sound" src="assets/footage/demo.mp4" data-start="2" data-duration="2" data-media-start="0"></audio>
</div><script>window.__timelines={tour:gsap.timeline({paused:true})};</script>''')
    form = authored.form_model({"what_for": "Demo", "audience": "New users", "screen_mode": "supplied", "duration": 6,
        "source": str(manifest), "source_sha256": authored.digest(manifest)})
    path, sha = proposal(root, form)
    form.update(approved_plan=path, approval_sha256=sha)
    authored.write(root / "form.json", form)
    authored.write(root / "contract.json", {"duration": 6, "fidelity_note": "Real dummy footage",
        "intro": {"direction": "title-reveal", "start": 0, "end": 2, "description": "Title"},
        "outro": {"direction": "result-hold", "start": 4, "end": 6, "description": "Result"},
        "samples": [{"at": t, "expect": "Demo"} for t in (0, 1, 3, 5, 6-1/30)]})
    args = SimpleNamespace(form=str(root / "form.json"), contract=str(root / "contract.json"), source=str(source), project=str(root / "project"))
    authored.freeze(args)
    assert authored.load(root / "project/integrity.json")["version"] == 3
    video.rename(root / "moved.mp4")
    Path(path).rename(root / "archived-proposal.md")
    authored.project_model(str(root / "project"))
    media = source / "index.html"
    original = media.read_text()
    for faulty in (original.replace("<video", "<img").replace("</video>", ""),
                   original.replace('<video id=', '<video data-playback-rate="2" id='),
                   original.replace('<audio id=', '<audio data-volume="0" id='),
                   original.replace('window.__timelines=', 'gsap.set("#sound",{volume:0});window.__timelines='),
                   original.replace('data-media-start="0"', 'data-media-start="1"'),
                   original.replace('id="sound"', 'id="demo"'),
                   original.replace("<audio", "<div").replace("</audio>", "</div>")):
        media.write_text(faulty)
        with pytest.raises(ValueError):
            authored.markup_check(source, form)
    media.write_text(original)
    with pytest.raises(ValueError, match="recreate cannot"):
        authored.markup_check(source, {**form, "screen_mode": "recreate"})


def test_raw_video_can_be_longer_than_sixty_seconds(tmp_path):
    path = tmp_path.resolve() / "long.mp4"
    authored.command(["ffmpeg", "-nostdin", "-v", "error", "-n", "-f", "lavfi", "-i", "color=blue:size=64x64:rate=1",
                      "-t", "65", "-c:v", "libx264", str(path)])
    assert footage.probe(path, decode=True)["duration"] == 65


def test_supplied_static_image_is_not_a_video_substitute(tmp_path):
    from PIL import Image
    path = tmp_path.resolve() / "still.png"
    Image.new("RGB", (320, 180), "blue").save(path)
    manifest = manifest_for(path)
    manifest["clips"][0]["source_start"] = 0
    file = path.parent / "source.json"
    authored.write(file, manifest)
    footage.prepare(str(file), str(path.parent / "prepared"))
    clip = authored.load(path.parent / "prepared/media.json")["clips"][0]
    assert clip["kind"] == "image" and clip["path"] == "demo.png"


def test_video_range_not_container_audio_duration(tmp_path):
    path = tmp_path.resolve() / "unequal.mp4"
    authored.command(["ffmpeg", "-nostdin", "-v", "error", "-n", "-f", "lavfi", "-i", "color=blue:size=64x64:rate=1:duration=1",
        "-f", "lavfi", "-i", "sine=frequency=440:duration=3", "-c:v", "libx264", "-c:a", "aac", str(path)])
    assert footage.probe(path)["duration"] == 1
    manifest = path.parent / "source.json"
    authored.write(manifest, manifest_for(path))
    with pytest.raises(ValueError, match="source range"):
        footage.prepare(str(manifest), str(path.parent / "prepared"))


def test_effective_toolsets_not_widened():
    import yaml
    config = yaml.safe_load((ROOT / "profiles/video-creator/config.yaml").read_text())
    for platform in ("cli", "a2a"):
        tools = config["platform_toolsets"][platform]
        assert "terminal" in tools and not {"browser", "computer_use", "hermes-cli"} & set(tools)
    assert config["skills"]["external_dirs"] == []


@pytest.mark.skipif(os.environ.get("TOUR_LIVE_CAPTURE") != "1", reason="opt-in isolated local browser proof")
@pytest.mark.parametrize("variant", ["password", "popup", "redirect", "cancel"])
def test_live_boundary_and_interruption(scope_job, variant):
    import http.server
    import subprocess
    import threading
    import time
    job, form, scope = scope_job
    effects = []
    class Handler(http.server.BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass
        def do_GET(self):
            if variant == "redirect" and self.server == server:
                self.send_response(302)
                self.send_header("Location", f"http://127.0.0.1:{other.server_port}/effect")
                self.end_headers()
                return
            if self.path == "/effect":
                effects.append("dummy GET side effect")
            self.send_response(200)
            self.send_header("Content-Type", "text/html")
            self.end_headers()
            self.wfile.write(('''<!doctype html><title>Demo</title><h1>Demo</h1>
<input id="name" type="password"><button id="open" onclick="window.open('/popup')">Open</button>''').encode())
    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    other = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    threads = [threading.Thread(target=s.serve_forever, daemon=True) for s in (server, other)]
    for thread in threads:
        thread.start()
    target = f"http://127.0.0.1:{server.server_port}/"
    form["target"] = scope["target"] = target
    scope["origins"] = [target[:-1]]
    path, sha = proposal(job, form, scope)
    try:
        if variant == "redirect":
            with pytest.raises(ValueError, match="origin"):
                capture.acquire(str(job), path, sha, [], recon=True)
            # Exact-origin checks detect after navigation; GET is NOT inherently safe.
            assert effects
            assert not list(job.glob("take-*/raw.webm"))
            return
        capture.acquire(str(job), path, sha, [], recon=True)
        if variant == "cancel":
            commands = job / "commands.json"
            authored.write(commands, [["wait", "5000"], ["click", "#open"]])
            process = subprocess.Popen([sys.executable, str(LEAF / "scripts/capture.py"), "--job", str(job),
                "--proposal", path, "--approval-sha256", sha, "--commands", str(commands)],
                stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            try:
                deadline = time.monotonic() + 25
                while time.monotonic() < deadline:
                    journals = list(job.glob("take-*/actions.jsonl"))
                    if journals and '"pending"' in journals[0].read_text():
                        break
                    assert process.poll() is None, process.communicate()
                    time.sleep(.05)
                else:
                    pytest.fail("capture never reached pending action")
                process.terminate()
                process.communicate(timeout=45)
                assert process.returncode != 0
                assert list(job.glob("take-*/raw.webm"))
                with pytest.raises(ValueError, match="cannot be replayed"):
                    capture.acquire(str(job), path, sha, [])
            finally:
                if process.poll() is None:
                    process.terminate()
                    process.communicate(timeout=45)
        else:
            commands = [["type", "#name", "Demo"]] if variant == "password" else [["click", "#open"]]
            with pytest.raises(ValueError, match="secret/non-text|popup or tab drift"):
                capture.acquire(str(job), path, sha, commands)
            assert list(job.glob("take-*/raw.webm"))
        assert all(authored.load(p)["status"] in ("complete", "interrupted") for p in job.glob("take-*/closed.json"))
    finally:
        for s in (server, other):
            s.shutdown()
            s.server_close()
        for thread in threads:
            thread.join()
