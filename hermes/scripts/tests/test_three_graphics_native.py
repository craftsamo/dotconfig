"""Opt-in real local browser/MP4 tests, not client approval or artistic acceptance."""
import importlib.util
import json
import os
from pathlib import Path
import shutil
import signal
import socket
import subprocess
import time
from types import SimpleNamespace

import pytest

pytestmark = pytest.mark.skipif(os.environ.get("THREE_GRAPHICS_NATIVE_TEST") != "1", reason="opt-in native graphics test")
HERE = Path(__file__).resolve().parent
PIPELINE = HERE.parents[1] / "profiles/video-creator/skills/video-creator-pipeline"


def module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    loaded = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(loaded)
    return loaded


study = module("native_three_study", HERE / "fixtures/three-graphics/study.py")
g = study.graphics


def minimal(root, composition):
    source = root / "source"
    (source / "assets").mkdir(parents=True)
    for name in ("gsap.min.js", "GSAP-LICENSE.txt", "gsap-provenance.json"):
        shutil.copyfile(study.ad.VENDOR / name, source / "assets" / name)
    g.stage(source / "assets")
    html = '''<!doctype html><html><head><meta charset="utf-8"><title>Fixture</title><style>
@font-face{font-family:Fixture;src:local("Arial")}*{box-sizing:border-box}body{margin:0}
#root{width:1280px;height:720px;background:#10191a;position:relative;overflow:hidden}
canvas{position:absolute;inset:0;width:1280px;height:720px}
#message{position:absolute;left:40px;top:30px;width:900px;height:80px;color:#fff;font:32px/1.5 Fixture;opacity:0}
</style></head><body><div id="root" data-composition-id="COMPOSITION" data-start="0" data-duration="2"
data-width="1280" data-height="720" data-fps="30" data-hermes-graphics="three-webgl2">
<canvas id="canvas" data-layout-ignore></canvas><div id="message">Synthetic graphics test</div></div>
<script src="assets/gsap.min.js"></script><script src="assets/three-runtime.js"></script><script src="assets/three-layer.js"></script>
<script>const tl=gsap.timeline({paused:true});window.__timelines||={};window.__timelines.COMPOSITION=tl;
tl.to('#message',{opacity:1,duration:.6},0);tl.set({}, {},2);
const scene=new THREE.Scene(),camera=new THREE.PerspectiveCamera(40,1280/720,.1,30);
const uniforms={progress:{value:0}};
const mat=new THREE.ShaderMaterial({uniforms,vertexShader:`varying vec2 v;void main(){v=uv;gl_Position=projectionMatrix*modelViewMatrix*vec4(position,1.);}`,
fragmentShader:`varying vec2 v;uniform float progress;void main(){float p=smoothstep(progress-.05,progress+.05,v.x);gl_FragColor=vec4(mix(vec3(.2,.7,.3),vec3(.1,.3,.5),p),1.);
#include <colorspace_fragment>
}`});const mesh=new THREE.Mesh(new THREE.PlaneGeometry(2,1.4),mat);mesh.rotation.y=.3;scene.add(mesh);
const back=new THREE.Mesh(new THREE.BoxGeometry(2.1,1.5,.15),new THREE.MeshBasicMaterial({color:'#d5e1cc'}));back.position.set(-.3,.2,-.4);scene.add(back);
HermesThree.mount({canvas:document.querySelector('#canvas'),scene,camera,timeline:tl,
update(t){camera.position.set(-.3+t*.3,.1,4);camera.lookAt(0,0,0);uniforms.progress.value=t/2;}});
</script></body></html>'''.replace("COMPOSITION", composition)
    (source / "index.html").write_text(html)
    return source


def test_native_ad_study_and_approval_gates(tmp_path):
    root = study.prepare(tmp_path.resolve() / "study")
    ad = study.ad
    preview = ad.snapshot(SimpleNamespace(project=str(root / "project"), out=str(root / "preview")))
    with pytest.raises(ValueError, match="preview hash"):
        ad.render(SimpleNamespace(project=str(root / "project"), approved_preview=preview["preview"], approval_sha256="0" * 64,
                                  out=str(root / "not-released"), study=True))
    result = ad.render(SimpleNamespace(project=str(root / "project"), approved_preview=preview["preview"],
        approval_sha256=preview["preview_sha256"], out=str(root / "final"), study=True))
    assert result["decoded"] and result["graphics"]["reverseSeek"] == "byte-identical"
    assert result["artifact_role"] == "diagnostic-study" and not result["final_eligible"]


@pytest.mark.parametrize("kind", ["tour", "explainer"])
def test_native_other_html_leaves(tmp_path, kind):
    root = tmp_path.resolve() / kind
    source = minimal(root, kind)
    samples = [{"at": at, "expect": "Synthetic time and graphics state"} for at in (0, .5, 1, 2 - 1 / 30)]
    if kind == "tour":
        leaf = module("native_three_tour", PIPELINE / "create/tour/scripts/authored.py")
        form = leaf.form_model({"what_for": "Synthetic walkthrough", "audience": "Maintainer", "duration": 2,
            "graphics": g.MODE, "screen_mode": "recreate", "fidelity": "simplified", "intro": "none", "outro": "none", "preview": "no"})
        proposal = root / "proposal-v1.md"
        proposal.write_text("Synthetic test, not a user approval\n```tour\n" + json.dumps({"form": form}) + "\n```\n")
        form.update(approved_plan=str(proposal), approval_sha256=g.digest(proposal))
        g.write(root / "form.json", form)
        contract = {"duration": 2, "fidelity_note": "Synthetic illustrative UI", "samples": samples,
            "intro": {"direction": "none", "start": 0, "end": 0, "description": ""},
            "outro": {"direction": "none", "start": 2, "end": 2, "description": ""}}
        g.write(root / "contract.json", contract)
        leaf.freeze(SimpleNamespace(source=str(source), form=str(root / "form.json"), contract=str(root / "contract.json"), project=str(root / "project")))
        with pytest.raises(ValueError, match="approved preview"):
            leaf.render(SimpleNamespace(project=str(root / "project"), approved_preview=None, out=str(root / "not-released")))
        leaf.snapshot(SimpleNamespace(project=str(root / "project"), out=str(root / "preview")))
        result = leaf.render(SimpleNamespace(project=str(root / "project"), approved_preview=str(root / "preview"), out=str(root / "final")))
    else:
        leaf = module("native_three_explainer", PIPELINE / "create/explainer-video/scripts/explainer.py")
        spec = {"version": 1, "renderer": "hyperframes", "graphics": g.MODE, "topic": "Synthetic spatial change",
            "audience": "Maintainer", "learning_goal": "See a surface boundary", "theme": "workbench", "style": "flat-vector",
            "direction": "mechanism", "duration": 2, "aspect": "16:9", "must_keep": "Synthetic check", "pending": [],
            "character": {"framing": "none", "performance": "still", "lip_sync": "off", "mouths": {},
                          "body": None, "video": None, "cues": None, "sync": None},
            "audio": {"mode": "none", "master": None, "script": None, "receipt": None, "captions": None, "timing": None},
            "units": [{"id": "unit", "start": 0, "end": 2, "goal": "Spatial change", "narration": "",
                       "before": "Initial surface", "change": "A moving boundary", "after": "Changed surface"}],
            "copy": [{"id": "message", "text": "Synthetic graphics test", "start": 0, "end": 2}], "samples": samples,
            "assets": {"assets/" + name: str(source / "assets" / name) for name in (*g.NAMES, "three-runtime.json")}}
        g.write(root / "spec.json", spec)
        proposal = leaf.propose(SimpleNamespace(spec=str(root / "spec.json"), out=str(root / "proposal-v1")))
        leaf.freeze(SimpleNamespace(source=str(source), approved_plan=proposal["proposal"], approval_sha256=proposal["approval_sha256"], project=str(root / "project")))
        preview = leaf.snapshot(SimpleNamespace(project=str(root / "project"), out=str(root / "preview")))
        result = leaf.render(SimpleNamespace(project=str(root / "project"), approved_preview=preview["preview"], approval_sha256=preview["preview_sha256"], out=str(root / "final")))
    assert result["decoded"] and result["graphics"]["reverseSeek"] == "byte-identical"


@pytest.mark.parametrize("stop_delay", [0, .005, .05, .15])
def test_native_audit_cancellation_closes_owned_browser(tmp_path, stop_delay):
    root = tmp_path.resolve() / "cancel"
    source = minimal(root, "ad")
    out = root / "audit"
    out.mkdir()
    data = g.identity()
    process = subprocess.Popen([data["node"], str(g.ENGINE / "audit.mjs"), str(source), "[0,0.5,1]", str(out / "graphics.json")],
                               stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, start_new_session=True)
    try:
        deadline = time.monotonic() + 15
        while not (out / "graphics-worker.json").exists() and time.monotonic() < deadline:
            assert process.poll() is None, process.communicate()
            time.sleep(.05)
        worker = json.loads((out / "graphics-worker.json").read_text())
        time.sleep(stop_delay)
        process.send_signal(signal.SIGTERM)
        stdout, stderr = process.communicate(timeout=5)
        status = subprocess.run(["ps", "-p", str(worker["browserPid"]), "-o", "pid=,ppid=,pgid=,stat=,command="], capture_output=True, text=True)
        (out / "cancel.log").write_text(f"Node exit: {process.returncode}\n{stdout}\n{stderr}\nBrowser: {status.stdout}")
        assert process.returncode != 0
        with pytest.raises(ProcessLookupError):
            os.kill(worker["browserPid"], 0)
        with socket.socket() as connection:
            assert connection.connect_ex(("127.0.0.1", worker["port"])) != 0
        assert not (out / "graphics.json").exists()
    finally:
        if process.poll() is None:
            os.killpg(process.pid, signal.SIGKILL)
            process.communicate()


def test_native_mid_movie_error_is_not_a_successful_render(tmp_path):
    root = tmp_path.resolve() / "fault"
    source = minimal(root, "ad")
    index = source / "index.html"
    index.write_text(index.read_text().replace("update(t){", "update(t){if(t>1.1&&t<1.2)throw new Error('intentional fixture fault');"))
    # Deliberate fault injection, not a production/approval path. The full
    # renderer must expose a failed frame even if its own process exits zero.
    with pytest.raises(ValueError) as error:
        g.run_hf(None, source, {"graphics": g.MODE}, ["render", "--output", str(root / "fault.mp4"),
            "--fps", "30", "--workers", "1", "--strict", "--no-best-effort", "--quiet"], root / "render.log")
    assert "HermesThree:" in getattr(error.value, "evidence", "")
    assert "intentional fixture fault" in (root / "render.log").read_text()
