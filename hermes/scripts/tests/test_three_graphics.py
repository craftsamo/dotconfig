"""Opt-in runtime contracts. Ordinary tests do not install or open a browser."""
import importlib.util
import json
import sys
import subprocess
from pathlib import Path
from types import SimpleNamespace

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[2]
PIPELINE = ROOT / "profiles/video-creator/skills/video-creator-pipeline"
spec = importlib.util.spec_from_file_location("three_graphics_test", PIPELINE / "scripts/three_graphics.py")
graphics = importlib.util.module_from_spec(spec)
spec.loader.exec_module(graphics)
PLAN = {"graphics": graphics.MODE}


@pytest.fixture
def rig(tmp_path, monkeypatch):
    engine, runtime = tmp_path / "engine", tmp_path / "runtime"
    engine.mkdir()
    (runtime / "assets").mkdir(parents=True)
    inputs = ("package.json", "package-lock.json", "setup.mjs", "three-layer.js", "audit.mjs")
    for name in inputs:
        (engine / name).write_text("synthetic " + name)
    for name in graphics.NAMES:
        (runtime / "assets" / name).write_text("synthetic " + name)
    (runtime / "package-lock.json").write_bytes((engine / "package-lock.json").read_bytes())
    data = {"version": 1, "three": "0.185.1", "esbuild": "0.28.2", "hyperframesVersion": "0.8.35",
            "gpu": "software", "inputs": {name: graphics.digest(engine / name) for name in inputs},
            "assets": {name: graphics.digest(runtime / "assets" / name) for name in graphics.NAMES}}
    graphics.write(runtime / "runtime.json", data)
    monkeypatch.setattr(graphics, "ENGINE", engine)
    monkeypatch.setattr(graphics, "RUNTIME", runtime)
    source = tmp_path / "source"
    (source / "assets").mkdir(parents=True)
    return source, runtime, data


def markup(**changes):
    return SimpleNamespace(**{"roots": [{"data-hermes-graphics": graphics.MODE}], "canvases": [{}],
                              "assets": ["assets/three-runtime.js", "assets/three-layer.js"], **changes})


def test_omitted_mode_preserves_old_behavior():
    assert not graphics.enabled({})
    assert graphics.enabled(PLAN)
    with pytest.raises(ValueError, match="HyperFrames"):
        graphics.enabled({**PLAN, "renderer": "motion-canvas"})


@pytest.mark.parametrize("subject", ["tour", "ad", "explainer-video"])
def test_graphics_option_fits_runtime_discovery_prefix(subject):
    prefix = (PIPELINE / "create" / subject / "SKILL.md").read_text()[:4000]
    assert prefix.count("---") >= 2, "frontmatter exceeds Hermes discovery prefix"
    metadata = yaml.safe_load(prefix.split("---", 2)[1])
    assert metadata["metadata"]["hermes"]["form"]["graphics"]["options"] == [graphics.MODE]


@pytest.mark.parametrize("value", [None, True, False, "webgl", "", 1])
def test_unknown_graphics_mode_is_rejected(value):
    with pytest.raises(ValueError, match="graphics must"):
        graphics.enabled({"graphics": value})


def test_stage_is_exact_and_never_overwrites(rig):
    source, runtime, data = rig
    result = graphics.stage(source / "assets")
    assert result["approval"] is False
    for name in graphics.NAMES:
        assert (source / "assets" / name).read_bytes() == (runtime / "assets" / name).read_bytes()
    assert graphics.load(source / graphics.DESCRIPTOR) == graphics.descriptor(data)
    with pytest.raises(ValueError, match="already exist"):
        graphics.stage(source / "assets")
    assert graphics.validate_assets(source, PLAN, markup()) == {"assets/" + name for name in graphics.NAMES}
    with pytest.raises(ValueError, match="explicit graphics selection"):
        graphics.validate_assets(source, {})


def test_stage_rejects_symlink_directory(rig, tmp_path):
    source, _, _ = rig
    alias = tmp_path / "alias"
    alias.symlink_to(source / "assets", target_is_directory=True)
    with pytest.raises(ValueError, match="physical|symlink"):
        graphics.stage(alias)
    assert not list((source / "assets").iterdir())


@pytest.mark.parametrize("change", ["bundle", "descriptor", "installed"])
def test_vendor_exemption_never_accepts_changed_bytes(rig, change):
    source, runtime, _ = rig
    graphics.stage(source / "assets")
    path = {"bundle": source / "assets/three-runtime.js", "descriptor": source / graphics.DESCRIPTOR,
            "installed": runtime / "assets/three-runtime.js"}[change]
    path.write_text('{}' if change == "descriptor" else "tampered")
    with pytest.raises(ValueError, match="hash mismatch|differs|asset drift"):
        graphics.validate_assets(source, PLAN, markup())


def test_adapter_manifest_cannot_relabel_changed_guard_source(rig):
    _, runtime, data = rig
    (runtime / "assets/three-layer.js").write_text("changed guards")
    data["assets"]["three-layer.js"] = graphics.digest(runtime / "assets/three-layer.js")
    (runtime / "runtime.json").write_text(json.dumps(data))
    with pytest.raises(ValueError, match="reviewed engine source"):
        graphics.installed()


@pytest.mark.parametrize("changes", [{"canvases": []}, {"canvases": [{}, {}]}, {"roots": [{}]},
                                    {"assets": []}, {"assets": ["assets/three-runtime.js"]}])
def test_source_requires_actual_single_layer(rig, changes):
    source, _, _ = rig
    graphics.stage(source / "assets")
    with pytest.raises(ValueError):
        graphics.validate_assets(source, PLAN, markup(**changes))


@pytest.mark.parametrize("code", ["r.setAnimationLoop(loop)", "window.__hfThreeRender = fn",
                                 "window.__hermesThreeAudit={}"])
def test_authored_source_cannot_replace_clock_or_evidence(code):
    with pytest.raises(ValueError, match="animation clock|audited hooks"):
        graphics.check_authored_code(code)


def test_old_hf_calls_do_not_consult_installation(tmp_path, monkeypatch):
    monkeypatch.setattr(graphics, "identity", lambda: pytest.fail("old path consulted Three"))
    calls = []
    original = lambda *args: calls.append(args)
    graphics.run_hf(original, tmp_path, {}, ["check"], tmp_path / "check.json")
    assert calls == [(tmp_path, ["check"], tmp_path / "check.json")]
    graphics.bind_preview({}, {}, tmp_path)
    graphics.verify_preview({}, {}, tmp_path)
    graphics.compare_final({}, tmp_path, tmp_path)


def test_new_hf_calls_pin_browser_and_gpu(tmp_path, monkeypatch):
    data = {"node": "/test/node", "browser": "/test/browser", "hyperframes": "/test/hf"}
    monkeypatch.setattr(graphics, "identity", lambda: data)
    calls = []
    monkeypatch.setattr(graphics, "execute", lambda argv, **kw: calls.append((argv, kw)) or "output")
    graphics.run_hf(lambda *a: pytest.fail("wrong path"), tmp_path, PLAN, ["check"], tmp_path / "check.json")
    argv, kwargs = calls[0]
    assert argv == [data["node"], data["hyperframes"], "check"]
    assert kwargs["env"]["HYPERFRAMES_BROWSER_PATH"] == data["browser"]
    assert kwargs["env"]["PRODUCER_BROWSER_GPU_MODE"] == "software"
    assert (tmp_path / "check.json").read_text() == "output"


def test_preview_binds_runtime_and_pixel_proof(tmp_path, monkeypatch):
    monkeypatch.setattr(graphics, "identity", lambda: {"version": "test"})
    before, after = tmp_path / "preview", tmp_path / "final"
    before.mkdir()
    after.mkdir()
    evidence = {"frames": {"0": "a" * 64}, "renderer": "SwiftShader"}
    graphics.write(before / "graphics.json", evidence)
    graphics.write(after / "graphics.json", evidence)
    preview = {}
    graphics.bind_preview(preview, PLAN, before)
    graphics.verify_preview(preview, PLAN, before)
    graphics.compare_final(PLAN, before, after)
    with pytest.raises(ValueError, match="DOM-only"):
        graphics.verify_preview(preview, {}, before)
    with pytest.raises(ValueError, match="runtime changed"):
        graphics.verify_preview({}, PLAN, before)
    (after / "graphics.json").write_text('{"frames":{},"renderer":"SwiftShader"}')
    with pytest.raises(ValueError, match="differs from approved preview"):
        graphics.compare_final(PLAN, before, after)
    (before / "graphics.json").write_text("{}")
    with pytest.raises(ValueError, match="evidence changed"):
        graphics.verify_preview(preview, PLAN, before)


def test_success_exit_with_browser_error_still_fails(tmp_path):
    script = tmp_path / "fake-render.py"
    script.write_text("import sys\nprint('HermesThree: lost context', file=sys.stderr)\n")
    with pytest.raises(ValueError) as error:
        graphics.execute([sys.executable, str(script)], cwd=tmp_path, timeout=5,
                         error_markers=("HermesThree:",), stderr_path=tmp_path / "stderr.log")
    assert "lost context" in error.value.evidence
    assert "lost context" in (tmp_path / "stderr.log").read_text()


def test_timeout_retains_stdout_and_stderr(tmp_path):
    script = tmp_path / "stalled.py"
    script.write_text("import sys,time\nprint('before stall',flush=True)\nprint('shader error',file=sys.stderr,flush=True)\ntime.sleep(30)\n")
    with pytest.raises(subprocess.TimeoutExpired) as error:
        graphics.execute([sys.executable, str(script)], cwd=tmp_path, timeout=.5, stderr_path=tmp_path / "stderr.log")
    assert "before stall" in error.value.evidence and "shader error" in error.value.evidence
    assert "shader error" in (tmp_path / "stderr.log").read_text()


def test_audit_failure_retains_actionable_evidence(tmp_path, monkeypatch):
    monkeypatch.setattr(graphics, "identity", lambda: {"node": "/test/node"})
    def fail(*args, **kwargs):
        error = ValueError("audit failed")
        error.evidence = "Actual WebGL backend must be SwiftShader"
        raise error
    monkeypatch.setattr(graphics, "execute", fail)
    with pytest.raises(ValueError):
        graphics.audit(tmp_path, PLAN, [0, 1], tmp_path)
    assert "SwiftShader" in (tmp_path / "graphics.log").read_text()
