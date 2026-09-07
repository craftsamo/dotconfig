#!/usr/bin/env python3
"""Opt-in local dummy capture, media preparation and real HyperFrames render."""

import argparse
import functools
import http.server
import json
import shutil
import sys
import threading
from pathlib import Path
from types import SimpleNamespace

LEAF = Path(__file__).resolve().parents[4] / "profiles/video-creator/skills/video-creator-pipeline/create/tour"
sys.path.insert(0, str(LEAF / "scripts"))
import authored
import capture
import footage


def proof(root, render):
    root = authored.fresh(str(root))
    root.mkdir(mode=0o700)
    site = root / "site"
    site.mkdir()
    shutil.copyfile(Path(__file__).with_name("site.html"), site / "index.html")
    handler = functools.partial(http.server.SimpleHTTPRequestHandler, directory=str(site))
    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    target = f"http://127.0.0.1:{server.server_port}/"
    job = root / "acquisition"
    job.mkdir(mode=0o700)
    form = authored.form_model({"what_for": "Name a demo workspace", "audience": "New users",
        "screen_mode": "capture", "source": str(job / "source.json"), "target": target,
        "start_state": "Local Settings, no name selected", "duration": 20, "preview": "yes"})
    scope = {"platform": "web", "target": target, "origins": [target[:-1]], "start_state": form["start_state"],
             "allowed_actions": {"click": ["#open", "#save"], "type": ["#name"], "scroll": ["down"]},
             "demo_data": ["Studio Demo"], "forbidden": ["credentials", "purchases", "send", "delete", "uploads", "private-regions"],
             "privacy": "sanitized-demo-only", "max_seconds": 120, "max_attempts": 2, "max_actions": 12, "read_only_recon": True}
    proposal = job / "proposal-v1.md"
    proposal.write_text("# Local Fixture Approval\n\nUser authorized isolated dummy capture/render testing, not a production target.\n\n```tour\n" + json.dumps({"form": form, "scope": scope}, indent=2) + "\n```\n")
    approval = authored.digest(proposal)
    commands = [["wait", "1000"], ["click", "#open"], ["wait", "1000"], ["type", "#name", "Studio Demo"],
                ["wait", "1000"], ["click", "#save"], ["wait", "1000"], ["scroll", "down", "800"], ["wait", "1500"]]
    try:
        capture.acquire(str(job), str(proposal), approval, [], recon=True)
        result = capture.acquire(str(job), str(proposal), approval, commands)
    finally:
        server.shutdown()
        server.server_close()
        thread.join()
    raw = Path(result["raw"])
    info = footage.probe(raw, decode=True)
    # Never truncate the demonstrated result just to fit this fixture's form.
    authored.require(info["duration"] < 16, "fixture take too long; retain raw and approve a longer edit")
    duration = info["duration"] - .1
    manifest = {"capture_receipt": result["receipt"], "clips": [{"id": "demo", "path": str(raw), "sha256": footage.sha256(raw),
        "source_start": 0, "duration": duration, "timeline_start": 2, "audio": "mute"}]}
    authored.write(job / "source.json", manifest)
    source = root / "source"
    (source / "assets").mkdir(parents=True)
    footage.prepare(str(job / "source.json"), str(source / "assets/footage"))
    for name in ("gsap.min.js", "GSAP-LICENSE.txt", "gsap-provenance.json"):
        shutil.copyfile(LEAF / "assets" / name, source / "assets" / name)
    source.joinpath("index.html").write_text(f'''<!doctype html><html><head><meta charset="utf-8">
<script src="assets/gsap.min.js"></script><style>
*{{box-sizing:border-box}}body{{margin:0}}#root{{position:relative;width:1280px;height:720px;background:#132b3e;color:white;overflow:hidden;font:24px Arial}}
#title{{position:absolute;top:12px;left:60px;font-size:32px}}#window{{position:absolute;left:80px;top:80px;width:1120px;height:630px}}
video{{width:1120px;height:630px;object-fit:contain}}#end{{position:absolute;inset:80px 0 0;background:#132b3e;padding:200px 120px;font-size:48px;opacity:0}}
#label{{position:absolute;right:20px;top:25px;font-size:20px;color:#b8eadb}}
</style></head><body><div id="root" data-composition-id="tour" data-start="0" data-duration="20" data-width="1280" data-height="720" data-fps="30">
<div id="title">Name Your Workspace</div><div id="window"><video id="demo" class="clip" src="assets/footage/demo.mp4" muted playsinline data-start="2" data-duration="{duration}" data-media-start="0"></video></div>
<div id="label">LOCAL DEMO</div><div id="end">Your Workspace, Named.<p style="font-size:28px">Local fixture / no real account changed</p></div></div>
<script>const tl=gsap.timeline({{paused:true}});tl.fromTo('#title',{{x:100}},{{x:0,duration:1}},0);
tl.set('#end',{{opacity:1}}, {2+duration});window.__timelines||={{}};window.__timelines.tour=tl;</script></body></html>''')
    form.update(approved_plan=str(proposal), approval_sha256=approval)
    authored.write(source / "index.motion.json", {"duration": 20, "assertions": [{"kind": "staysInFrame", "selector": "#window"}]})
    authored.write(root / "form.json", form)
    contract = {"duration": 20,
        "intro": {"direction": form["intro"], "start": 0, "end": 2, "description": "Title arrives before continuous local footage"},
        "outro": {"direction": form["outro"], "start": 2 + duration, "end": 20, "description": "Hold completion title after recorded result"},
        "fidelity_note": "Actual local dummy browser recording at 1x; no reconstructed action timings, no cursor overlay",
        "samples": [{"at": t, "expect": e} for t, e in [(0, "First title"), (1, "Title arrival"), (3, "Recorded UI"),
                      (7, "Continuous UI state"), (12, "Recorded result or action"), (19, "Completion"), (20 - 1/30, "Last completion frame")]]}
    authored.write(root / "contract.json", contract)
    authored.freeze(SimpleNamespace(form=str(root / "form.json"), contract=str(root / "contract.json"), source=str(source), project=str(root / "project")))
    if render:
        authored.snapshot(SimpleNamespace(project=str(root / "project"), out=str(root / "preview")))
        authored.render(SimpleNamespace(project=str(root / "project"), out=str(root / "final"), approved_preview=str(root / "preview")))
    authored.write(root / "proof.json", {"root": str(root), "raw": str(raw), "raw_duration": info["duration"], "clip_duration": duration,
                   "capture": result, "fixture_only": True, "rendered": render, "live_handoff": False})
    print(json.dumps({"root": str(root), "rendered": render}))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", required=True)
    parser.add_argument("--render", action="store_true")
    args = parser.parse_args()
    proof(Path(args.root), args.render)
