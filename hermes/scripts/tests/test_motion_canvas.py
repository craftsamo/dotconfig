"""MC contracts with fake native boundaries by default; no browser or installs.

MOTION_CANVAS_RENDER_TEST=1 opts into four real six-second fixture variants,
bundler confinement and cancellation checks. Synthetic tone/mouth cues are not voice proof.
"""

import importlib.util
import json
import os
import signal
import socket
import subprocess
import time
from pathlib import Path
from types import SimpleNamespace

import pytest
from PIL import Image, ImageChops, ImageStat

FIXTURE = Path(__file__).parent / "fixtures/explainer-video/motion-canvas/example.py"
_spec = importlib.util.spec_from_file_location("motion_canvas_example", FIXTURE)
example = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(example)
ex = example.explainer
mc = ex.mc
native = pytest.mark.skipif(os.environ.get("MOTION_CANVAS_RENDER_TEST") != "1",
                            reason="opt in with MOTION_CANVAS_RENDER_TEST=1; no auto-install")


def forbidden(*args, **kwargs):
    pytest.fail("Ordinary MC tests must not launch a browser, install, or use HyperFrames")


@pytest.fixture(autouse=True)
def native_guard(monkeypatch, request):
    identity = mc.identity
    monkeypatch.setattr(ex, "hf", forbidden)
    if not request.node.name.startswith("test_native_"):
        monkeypatch.setattr(mc, "identity", lambda: {"engine": "motion-canvas", "version": "synthetic-1", "runtime": {"version": "synthetic-1"}})
        # Popen is shared by subprocess.run, so block only the renderer entrypoint.
        popen = subprocess.Popen

        def guarded(args, *a, **kw):
            if str(mc.ENGINE / "render.mjs") in map(str, args) and "--check" not in args:
                forbidden()
            return popen(args, *a, **kw)

        monkeypatch.setattr(subprocess, "Popen", guarded)
    return identity


@pytest.fixture
def job(tmp_path):
    root = tmp_path.resolve() / "job"
    example.fixture(root, audio=False)
    return root


def propose(root, spec=None):
    if spec is not None:
        (root / "spec.json").write_text(json.dumps(spec), encoding="utf-8")
    return ex.propose(SimpleNamespace(spec=str(root / "spec.json"), out=str(root / "proposal-v1")))


def prepare(root):
    proposal = propose(root)
    source = example.author_source(root, proposal)
    return SimpleNamespace(approved_plan=proposal["proposal"], approval_sha256=proposal["approval_sha256"],
                           source=str(source), project=str(root / "project"))


def preview(root):
    ex.freeze(prepare(root))
    return ex.snapshot(SimpleNamespace(project=str(root / "project"), out=str(root / "preview")))


def render(root, receipt):
    return ex.render(SimpleNamespace(project=str(root / "project"), approved_preview=receipt["preview"],
                     approval_sha256=receipt["preview_sha256"], out=str(root / "final")))


@pytest.fixture
def fake_backend(monkeypatch):
    calls = []

    def snapshot(root, plan, out):
        calls.append("snapshot")
        (out / "frames").mkdir()
        for i, _ in enumerate(plan["samples"]):
            Image.new("RGB", ex.SIZES[plan["aspect"]], "#101820").save(out / "frames" / f"{i:02}.png")
        ex.write(out / "check.json", {"ok": True, "renderer": "motion-canvas", "copy": {"checked": 15},
                 "contrast": {"enabled": False, "reason": "Canvas contrast requires visual review"}})

    def encode(root, plan, out, approved):
        calls.append("render")
        assert approved == root.parent / "preview"
        width, height = ex.SIZES[plan["aspect"]]
        cmd = ["ffmpeg", "-nostdin", "-v", "error", "-n", "-f", "lavfi", "-i",
               f"color=c=0x101820:s={width}x{height}:r=30:d=6"]
        if plan["audio"]["master"]:
            cmd += ["-i", str(root / plan["audio"]["master"]), "-c:a", "aac"]
        cmd += ["-c:v", "libx264", "-preset", "ultrafast", "-pix_fmt", "yuv420p",
                "-frames:v", "180", str(out / "explainer.mp4")]
        subprocess.run(cmd, capture_output=True, check=True, timeout=60)
        ex.write(out / "check.json", {"ok": True, "renderer": "motion-canvas",
                 "contrast": {"enabled": False, "reason": "Canvas contrast requires visual review"}})

    monkeypatch.setattr(mc, "snapshot", snapshot)
    monkeypatch.setattr(mc, "render", encode)
    return calls


@pytest.mark.parametrize("renderer,version,ready", [("motion-canvas", 2, True), ("motion-canvas", 1, False),
                                                  ("hyperframes", 1, True)])
def test_version_routing_preserves_plan_and_legacy_approval(job, renderer, version, ready):
    spec = ex.load(job / "spec.json")
    spec.update(renderer=renderer, version=version)
    result = propose(job, spec)
    plan = ex.load(Path(result["proposal"]).parent / "plan.json")
    assert (plan["renderer"], plan["version"]) == (renderer, version)
    assert result["can_render"] is ready and result["media_generation"] == 0
    assert result["status"] == ("awaiting-approval" if ready else "pending-inputs")
    if not ready:
        with pytest.raises(ValueError, match="pending-inputs"):
            ex.approved_proposal(result["proposal"], result["approval_sha256"])
    assert all(("assets/" + name in plan["assets"]) == (renderer == "hyperframes") for name in ex.VENDOR_FILES)


def test_missing_runtime_pending_without_install(job, monkeypatch, native_guard):
    # Restore the actual identity implementation with an absent runtime marker.
    monkeypatch.setattr(mc, "RUNTIME", job / "missing-runtime")
    monkeypatch.setattr(mc, "command", forbidden)
    monkeypatch.setattr(mc, "identity", native_guard)
    with pytest.raises(ValueError, match="no automatic install"):
        mc.identity()
    result = propose(job)
    assert result["status"] == "pending-inputs" and not result["can_render"]
    assert "no automatic install" in " ".join(result["missing"])


def test_cue_assets_preserved_without_gsap_or_generated_mouth_track(tmp_path):
    root = tmp_path.resolve() / "cues"
    spec = example.fixture(root, framing="full", performance="puppet", cue_at_zero=True)
    ex.freeze(prepare(root))
    project, plan = ex.project_model(str(root / "project"))
    assert set(plan["assets"]) == set(spec["assets"])
    for name, original in spec["assets"].items():
        assert (project / name).read_bytes() == Path(original).read_bytes()
    assert ex.MOUTH_TRACK not in plan["assets"]
    assert not any("gsap" in name.lower() for name in mc.source_files(project))
    assert plan["character"] == spec["character"]


@pytest.mark.parametrize("name", ["scene.tsx", "scene.meta"])
def test_frozen_scene_hashes_reject_mutation(job, name):
    args = prepare(job)
    ex.freeze(args)
    path = Path(args.project) / name
    assert ex.load(Path(args.project) / "integrity.json")[name] == ex.digest(path)
    assert path.read_bytes() == (Path(args.source) / name).read_bytes()
    path.write_text(path.read_text() + "\n", encoding="utf-8")
    with pytest.raises(ValueError, match="project changed since freeze"):
        ex.project_model(args.project)


@pytest.mark.parametrize("metadata", [
    '{"version":1,"timeEvents":[]}', '{"version":1,"seed":42}',
    '{"version":1,"seed":42,"seed":43,"timeEvents":[]}',
    '{"version":1,"seed":true,"timeEvents":[]}',
    '{"version":1,"seed":42,"timeEvents":[{"name":"beat","targetTime":1},{"name":"beat","targetTime":2}]}',
])
def test_metadata_requires_unique_seed_and_time_events(job, metadata):
    args = prepare(job)
    (Path(args.source) / "scene.meta").write_text(metadata)
    with pytest.raises(ValueError):
        ex.freeze(args)
    assert not Path(args.project).exists()


@pytest.mark.parametrize("name,code", [
    ("extra.ts", "import item from './scene?scene';"), ("extra.ts", "import item from './scene?raw';"),
    ("extra.ts", "import('./scene');"), ("vite.config.ts", "export default {};"),
    ("node_modules/extra.js", "export default {};"), ("package.json", "{}"),
])
def test_unsupported_query_dynamic_import_and_config_rejected(job, name, code):
    args = prepare(job)
    path = Path(args.source) / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(code)
    with pytest.raises(ValueError, match="query imports|dynamic imports|runtime-owned"):
        ex.freeze(args)
    assert not Path(args.project).exists()


@pytest.mark.parametrize("kind", ["symlink", "traversal"])
def test_source_confinement_preserves_outside_sentinel(job, kind):
    args = prepare(job)
    sentinel = job / "outside.ts"
    sentinel.write_text("export const untouched = true;")
    if kind == "symlink":
        (Path(args.source) / "outside.ts").symlink_to(sentinel)
    else:
        args.source += "/../source"
    with pytest.raises(ValueError, match="symlink|physical"):
        ex.freeze(args)
    assert sentinel.read_text() == "export const untouched = true;"
    assert not Path(args.project).exists()


def test_source_file_count_excludes_root_control_files(tmp_path):
    root = tmp_path.resolve()
    payload = {f"payload-{i:03}.txt" for i in range(200)}
    controls = {"plan.json", "proposal.md", "integrity.json"}
    for name in payload | controls:
        (root / name).write_text("{}", encoding="utf-8")
    assert set(mc.source_files(root)) == payload | controls
    (root / "payload-200.txt").write_text("extra", encoding="utf-8")
    with pytest.raises(ValueError, match="source exceeds 200 files"):
        mc.source_files(root)


@pytest.mark.parametrize("field", ["duration", "sample", "duplicate"])
def test_exact_frame_boundaries_and_distinct_samples(job, field):
    plan = ex.load(job / "spec.json")
    assert mc.sample_frames(plan) == [0, 30, 90, 150, 179]
    if field == "duplicate":
        plan["samples"].insert(1, {"at": .001, "expect": "Same frame"})
        with pytest.raises(ValueError, match="distinct frames"):
            mc.sample_frames(plan)
    else:
        if field == "duration":
            plan["duration"] += .001
        else:
            plan["samples"][1]["at"] += .001
        with pytest.raises(ValueError, match="frame boundary|exact frames"):
            ex.model(plan)


def test_render_routes_to_mc_with_real_final_decode(job, fake_backend):
    result = render(job, preview(job))
    assert fake_backend == ["snapshot", "render"]
    assert result["decoded"] and result["fps"] == 30 and result["duration"] == 6
    assert result["audio"] is None and result["listening"] == "unverified"
    assert result["renderer"] == "motion-canvas" and result["contrast"]["enabled"] is False
    assert "Contrast was not automatically checked" in (job / "final/qa.md").read_text()
    assert len(list((job / "final/review").glob("*.png"))) == 5
    assert Image.open(job / "final/poster.png").size == (1280, 720)


@pytest.mark.parametrize("fault", ["runtime", "frame", "times", "check"])
def test_preview_drift_stops_before_mc_render(job, fake_backend, monkeypatch, fault):
    receipt = preview(job)
    if fault == "runtime":
        monkeypatch.setattr(mc, "identity", lambda: {"engine": "motion-canvas", "version": "changed"})
    elif fault == "frame":
        Image.new("RGB", (1280, 720), "red").save(job / "preview/frames/00.png")
    elif fault == "check":
        (job / "preview/check.json").write_text('{"ok": false}')
    else:
        path = job / "preview/preview.json"
        data = ex.load(path)
        data["times"][1] += 1 / 30
        path.write_text(json.dumps(data), encoding="utf-8")
        receipt["preview_sha256"] = ex.digest(path)
    with pytest.raises(ValueError, match="runtime changed|preview frame changed|preview times changed|preview check changed"):
        render(job, receipt)
    assert fake_backend == ["snapshot"] and not (job / "final").exists()


@pytest.mark.parametrize("stage", ["snapshot", "render"])
def test_runtime_drift_during_execution_never_publishes_approval(job, fake_backend, monkeypatch, stage):
    if stage == "render":
        receipt = preview(job)
    else:
        ex.freeze(prepare(job))
    identities = iter([mc.identity(), {"engine": "motion-canvas", "version": "changed"}])
    monkeypatch.setattr(mc, "identity", lambda: next(identities))
    with pytest.raises(ValueError, match="runtime changed during"):
        if stage == "render":
            render(job, receipt)
        else:
            ex.snapshot(SimpleNamespace(project=str(job / "project"), out=str(job / "preview")))
    assert not (job / ("final/qa.json" if stage == "render" else "preview/preview.json")).exists()


@pytest.fixture
def execution(job, monkeypatch):
    """Fake Node execution output, exercising the actual Python audit consumer."""
    plan = ex.load(job / "spec.json")
    out = job / "execution"
    (out / "canvas/frames").mkdir(parents=True)
    frames = {}
    for frame in mc.sample_frames(plan):
        path = out / "canvas/frames" / f"{frame:06}.png"
        Image.new("RGB", (1280, 720), "#101820").save(path)
        frames[path.name] = ex.digest(path)
    audit = {"ok": True, "count": 180, "frames": frames, "runtime": mc.identity()["runtime"],
             "audits": [{"frame": f, "time": f / 30, "copyChecked": 3} for f in mc.sample_frames(plan)]}

    class Process:
        returncode = 0

        def __init__(self, argv, **kwargs):
            assert argv[1:3] == [str(mc.ENGINE / "render.mjs"), "--job"]
            assert kwargs["start_new_session"] is True
            assert ex.load(Path(argv[3]))["count"] == 180

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def communicate(self, timeout):
            assert timeout == 660
            ex.write(out / "canvas/audit.json", audit)
            return "Synthetic execution, not native rendering\n", ""

    monkeypatch.setattr(mc.subprocess, "Popen", Process)
    return plan, out, audit


@pytest.mark.parametrize("fault", [None, "count", "frame-set", "render-frame-set", "hash", "dimensions", "png",
                                 "audit-frames", "unchecked", "worker-runtime"])
def test_invoke_validates_frame_counts_pngs_hashes_and_sample_audits(job, execution, fault):
    plan, out, audit = execution
    path = out / "canvas/frames/000000.png"
    if fault == "count":
        audit["count"] -= 1
    elif fault == "worker-runtime":
        audit["runtime"] = {"version": "changed-during-execution"}
    elif fault == "frame-set":
        audit["frames"].pop(path.name)
    elif fault == "hash":
        audit["frames"][path.name] = "0" * 64
    elif fault in ("dimensions", "png"):
        if fault == "png":
            path.write_bytes(b"Not a PNG")
        else:
            Image.new("RGB", (32, 32)).save(path)
        audit["frames"][path.name] = ex.digest(path)
    elif fault == "audit-frames":
        audit["audits"].pop()
    elif fault == "unchecked":
        for item in audit["audits"]:
            item["copyChecked"] = 0
    if fault:
        with pytest.raises((ValueError, OSError)):
            mc.invoke(job, plan, out, "render" if fault == "render-frame-set" else "snapshot")
        assert not (out / "check.json").exists()
    else:
        mc.snapshot(job, plan, out)
        assert ex.load(out / "motion-canvas-job.json")["samples"] == [0, 30, 90, 150, 179]
        for i, frame in enumerate(mc.sample_frames(plan)):
            assert ex.digest(out / "frames" / f"{i:02}.png") == audit["frames"][f"{frame:06}.png"]
        assert ex.load(out / "check.json")["copy"]["checked"] == 15


def test_raw_sample_hash_mismatch_stops_before_ffmpeg(job, execution, monkeypatch):
    plan, out, audit = execution
    approved = job / "preview"
    (approved / "frames").mkdir(parents=True)
    for i, _ in enumerate(mc.sample_frames(plan)):
        Image.new("RGB", (1280, 720), "red" if i == 4 else "#101820").save(approved / "frames" / f"{i:02}.png")
    monkeypatch.setattr(mc, "invoke", lambda *args: audit)
    monkeypatch.setattr(mc, "command", forbidden)
    with pytest.raises(ValueError, match="differs from approved preview"):
        mc.render(job, plan, out, approved)
    assert not (out / "explainer.mp4").exists()


def test_node_syntax_and_runtime_exports_without_install(job):
    for name in ("render.mjs", "setup.mjs"):
        subprocess.run(["node", "--check", str(mc.ENGINE / name)], capture_output=True, check=True)
    script = r"""
const {stripTypeScriptTypes} = require('node:module');
const {SourceTextModule, SyntheticModule, createContext} = require('node:vm');
const fs = require('node:fs');
const assert = require('node:assert/strict');
const data = JSON.parse(fs.readFileSync(0, 'utf8'));
const context = createContext({});
let time = 0;
const modules = Object.fromEntries(Object.entries({
  '@motion-canvas/2d': {useScene2D: () => ({getView: () => ({globalTime: () => time})})},
  '@explainer/plan': {default: data.plan}, '@explainer/cues': {default: data.cues},
}).map(([id, values]) => [id, new SyntheticModule(Object.keys(values), function () {
  for (const [key, value] of Object.entries(values)) this.setExport(key, value);
}, {context})]));
new SourceTextModule(stripTypeScriptTypes(fs.readFileSync(data.browser, 'utf8')), {context});
(async () => {
  const mod = new SourceTextModule(stripTypeScriptTypes(fs.readFileSync(data.contract, 'utf8')), {context});
  await mod.link(id => modules[id]); await mod.evaluate();
  const api = mod.namespace;
  assert.deepEqual(Object.keys(api).sort(), ['copy', 'mouthOpacity', 'plan', 'time', 'visible']);
  for (time of [0, .4, .8, 2, 2.4, 2.8, 4, 4.4, 4.8, 179/30, 6, .6, 0]) {
    for (const row of data.plan.copy) {
      assert.equal(api.copy(row.id), row.text);
      assert.equal(api.visible(row.id), +(row.start <= time && time < row.end));
    }
    const local = time - data.cues.offset;
    const mouth = data.cues.events.find(e => e.start <= local && local < e.end)?.mouth ?? 'rest';
    for (const shape of Object.keys(data.plan.character.mouths))
      assert.equal(api.mouthOpacity(shape), +(shape === mouth));
  }
  assert.throws(() => api.copy('unknown'));
  assert.throws(() => api.visible('unknown'));
  assert.throws(() => api.mouthOpacity('unknown'));
})().catch(error => {console.error(error); process.exitCode = 1;});
"""
    root = job / "contract-inputs"
    plan = example.fixture(root, framing="bust", performance="puppet", cue_at_zero=True)
    payload = {"plan": plan, "cues": ex.load(root / "inputs/cues.json"),
               "contract": str(mc.ENGINE / "contract.ts"), "browser": str(mc.ENGINE / "browser.ts")}
    result = subprocess.run(["node", "--experimental-vm-modules", "-e", script], input=json.dumps(payload),
                            capture_output=True, text=True, timeout=30)
    assert result.returncode == 0, result.stderr


def test_fixture_cli_requires_approval_and_defaults_to_source_only(tmp_path, capsys):
    root = tmp_path.resolve() / "cli"
    with pytest.raises(SystemExit) as error:
        example.main(["--root", str(root), "--render"])
    assert error.value.code == 2 and not root.exists()
    assert "--approve-synthetic" in capsys.readouterr().err
    result = example.main(["--root", str(root), "--silent", "--aspect", "portrait", "--japanese"])
    assert result["native_rendered"] is False and result["proposal"]["can_render"]
    plan = ex.load(root / "proposal-v1/plan.json")
    assert plan["aspect"] == "9:16" and any(ord(c) > 127 for c in plan["copy"][0]["text"])
    assert (root / "source/scene.tsx").is_file()
    assert not (root / "project").exists() and not list(root.rglob("*.mp4"))


@native
def test_native_cancellation_closes_browser_and_server(job):
    import psutil

    spec = ex.load(job / "spec.json")
    spec["duration"] = 120
    for row in spec["units"] + spec["copy"]:
        if row["end"] == 6:
            row["end"] = 120
    spec["samples"][-1]["at"] = 120 - 1 / 30
    (job / "spec.json").write_text(json.dumps(spec), encoding="utf-8")
    args = prepare(job)
    scene = Path(args.source) / "scene.tsx"
    source = scene.read_text(encoding="utf-8")
    # Keep the six-second animation, then hold until the approved 120-second end.
    scene.write_text(source.replace("\n});", "\n  yield* waitFor(114);\n});"), encoding="utf-8")
    ex.freeze(args)
    project, plan = ex.project_model(args.project)
    runtime = mc.identity()["runtime"]
    out = job / "cancelled"
    out.mkdir()
    job_path = out / "motion-canvas-job.json"
    ex.write(job_path, {"project": str(project), "out": str(out / "canvas"), "mode": "render",
                       "fps": 30, "width": 1280, "height": 720, "count": 3600,
                       "samples": mc.sample_frames(plan)})
    log_path = out / "motion-canvas.log"
    with log_path.open("w", encoding="utf-8") as log:
        process = subprocess.Popen([runtime["node"], str(mc.ENGINE / "render.mjs"), "--job", str(job_path)],
                                   stdout=log, stderr=subprocess.STDOUT, start_new_session=True)
        passed = False
        try:
            deadline = time.monotonic() + 60
            worker_path = out / "canvas/worker.json"
            first_frame = out / "canvas/frames/000000.png"
            while not (worker_path.is_file() and first_frame.is_file() and first_frame.stat().st_size):
                assert process.poll() is None, log_path.read_text(encoding="utf-8")
                assert time.monotonic() < deadline, "No worker/first frame within 60 seconds"
                time.sleep(.05)
            worker = ex.load(worker_path)
            assert worker["nodePid"] == process.pid
            browser = psutil.Process(worker["browserPid"])
            assert browser.ppid() == process.pid
            assert Path(browser.cmdline()[0]).resolve() == Path(runtime["browser"]).resolve()
            with socket.create_connection(("127.0.0.1", worker["port"]), timeout=1):
                pass
            assert process.poll() is None, "Render finished before cancellation"
            deadline = time.monotonic() + 30
            process.send_signal(signal.SIGTERM)  # Node must close its browser, not the test.
            assert process.wait(timeout=30) != 0, log_path.read_text(encoding="utf-8")
            # psutil retains the creation time, so PID reuse is not mistaken for a leak.
            while browser.is_running() and time.monotonic() < deadline:
                time.sleep(.05)
            assert not browser.is_running(), "Renderer browser survived cancellation"
            with socket.socket() as connection:
                connection.settimeout(1)
                assert connection.connect_ex(("127.0.0.1", worker["port"])) != 0, "Renderer port still open"
            assert not (out / "canvas/audit.json").exists()
            assert not (out / "check.json").exists()
            assert "Render cancelled" in log_path.read_text(encoding="utf-8")
            passed = True
        finally:
            # Never signal a recorded browser PID or a possibly reused, reaped Node PID.
            if not passed and process.poll() is None:
                try:
                    os.killpg(process.pid, signal.SIGTERM)
                except ProcessLookupError:
                    pass
                try:
                    process.wait(timeout=15)
                except subprocess.TimeoutExpired:
                    os.killpg(process.pid, signal.SIGKILL)
                    process.wait(timeout=10)


@native
@pytest.mark.parametrize("framing,performance,aspect,japanese", [
    ("none", "still", "portrait", True), ("bust", "still", "landscape", False),
    ("full", "puppet", "portrait", False), ("full", "animated", "landscape", False),
])
def test_native_four_variants(tmp_path, framing, performance, aspect, japanese):
    root = tmp_path.resolve() / "native"
    try:
        result = example.main(["--root", str(root), "--framing", framing, "--performance", performance,
                               "--aspect", aspect, "--render", "--approve-synthetic"] +
                              (["--japanese"] if japanese else []) +
                              (["--cue-at-zero"] if performance != "animated" and framing != "none" else []))
    except ValueError as error:
        logs = "\n".join(f"{path}: {path.read_text()}" for path in root.glob("*/motion-canvas.log"))
        pytest.fail(f"{error}\n{logs}")
    assert result["native_rendered"] and result["render"]["decoded"]
    assert result["render"]["listening"] == "unverified"
    plan = ex.load(root / "project/plan.json")
    audit = ex.load(root / "final/canvas/audit.json")
    assert audit["count"] == 180 and len(audit["frames"]) == 180
    assert {a["frame"] for a in audit["audits"]} == set(mc.sample_frames(plan))
    for i, frame in enumerate(mc.sample_frames(plan)):
        raw = root / "final/canvas/frames" / f"{frame:06}.png"
        assert ex.digest(raw) == ex.digest(root / "preview/frames" / f"{i:02}.png")
        # Lossy final MP4 copy region must remain close to the approved native PNG.
        width, height = ex.SIZES[plan["aspect"]]
        box = (20, 20, width - 20, int(height * .4))
        with Image.open(raw) as expected, Image.open(root / "final/review" / f"{i:02}.png") as actual:
            delta = ImageChops.difference(expected.convert("RGB").crop(box), actual.convert("RGB").crop(box))
            assert max(ImageStat.Stat(delta).mean) < 4
    assert len(set(audit["frames"].values())) > 20  # Genuine moving geometry, not a static card.


@native
@pytest.mark.parametrize("absolute", [False, True])
def test_native_bundler_rejects_import_outside_frozen_source(job, absolute):
    args = prepare(job)
    sentinel = job / "outside.ts"
    sentinel.write_text("export const outside = 123;")
    scene = Path(args.source) / "scene.tsx"
    target = str(sentinel) if absolute else "../outside.ts"
    scene.write_text(f"import {{outside}} from {json.dumps(target)};\nconsole.log(outside);\n" + scene.read_text())
    # Static source checks are not a JS resolver; the actual bundler owns this boundary.
    ex.freeze(args)
    with pytest.raises(ValueError, match="Motion Canvas failed"):
        ex.snapshot(SimpleNamespace(project=args.project, out=str(job / "preview")))
    assert "Import outside frozen source" in (job / "preview/motion-canvas.log").read_text()
    assert not (job / "preview/preview.json").exists()
    assert sentinel.read_text() == "export const outside = 123;"
