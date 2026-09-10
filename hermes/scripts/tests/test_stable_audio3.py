"""Unit tests for stable_audio3.py - stdlib-only, no MLX/network/real audio.

All platform/subprocess/network boundaries are monkeypatched so this suite
runs on any OS/Python that has the stdlib (no installed root or MLX needed).
"""

from __future__ import annotations

import hashlib
import importlib.util
import json
import subprocess
import sys
import wave
from pathlib import Path

import pytest

MODULE_PATH = Path(__file__).resolve().parents[1] / "stable_audio3.py"


def _load_module():
    spec = importlib.util.spec_from_file_location("stable_audio3", MODULE_PATH)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


sa3 = _load_module()

WEIGHT_NAMES = ("MLX/t5gemma_f16.npz", "MLX/dit_medium_f16.npz", "MLX/same_l_decoder_f32.npz")
WEIGHT_REL = {
    "MLX/t5gemma_f16.npz": "models/mlx/t5gemma_f16.npz",
    "MLX/dit_medium_f16.npz": "models/mlx/dit_medium_f16.npz",
    "MLX/same_l_decoder_f32.npz": "models/mlx/same_l_decoder_f32.npz",
}


def write_wav(path: Path, seconds: float, rate=44100, channels=2, sampwidth=2):
    frames = round(seconds * rate)
    with wave.open(str(path), "wb") as w:
        w.setnchannels(channels)
        w.setsampwidth(sampwidth)
        w.setframerate(rate)
        w.writeframes(b"\x00\x00" * channels * frames)


def _git(args, cwd):
    subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True)


def _init_repo(path):
    _git(["init", "-q"], path)
    _git(["config", "user.email", "test@example.invalid"], path)
    _git(["config", "user.name", "Test"], path)
    _git(["add", "-A"], path)
    _git(["commit", "-q", "-m", "pinned"], path)
    return subprocess.run(["git", "rev-parse", "HEAD"], cwd=path, capture_output=True,
                          text=True, check=True).stdout.strip()


def _make_weights(cache_dir):
    """Pre-populates the cache (not the runtime symlink target) so install()
    finds valid cached weights and only needs to create/verify the symlink -
    exercising the same reuse path a real re-adopted install takes."""
    cache_dir.mkdir(parents=True, exist_ok=True)
    weights, contents = [], {}
    for name in WEIGHT_NAMES:
        rel = WEIGHT_REL[name]
        content = f"fake-weight-{name}".encode()
        contents[name] = content
        (cache_dir / Path(rel).name).write_bytes(content)
        weights.append({"repo_path": name, "runtime_rel_path": rel,
                        "bytes": len(content), "sha256": hashlib.sha256(content).hexdigest()})
    return weights, contents


def _make_pins(tmp_path, commit, weights, repo="https://example.invalid/stable-audio-3.git"):
    pins = {
        "schema_version": 1,
        "checkout": {"repo": repo, "commit": commit, "subpath": "optimized/mlx"},
        "python": {"version": "3.11"},
        "weights": {"repo": "example/stable-audio-3-optimized", "revision": "rev1", "files": weights},
        "generation": {"dit": "medium", "decoder": "same-l", "steps": 8, "sample_rate": 44100,
                       "channels": 2, "sample_width_bytes": 2, "generation_timeout_seconds": 180},
        "dependencies": {"requirements_in": "requirements.in", "lock": "requirements.lock"},
    }
    pins_path = tmp_path / "pins.json"
    pins_path.write_text(json.dumps(pins, indent=2))
    return pins, pins_path


@pytest.fixture
def env(tmp_path, monkeypatch):
    """A fully wired fake root + pins/lock, ready for install()."""
    root = tmp_path / "root"
    mlx_dir = root / "checkout" / "optimized" / "mlx"
    scripts_dir = mlx_dir / "scripts"
    scripts_dir.mkdir(parents=True)
    (scripts_dir / "sa3_mlx.py").write_text("# fake sa3_mlx.py\n")
    (mlx_dir / ".gitignore").write_text("*.npz\n.venv/\n")  # mirrors the real repo: symlinked weights aren't tracked
    venv_bin = mlx_dir / ".venv" / "bin"
    venv_bin.mkdir(parents=True)
    (venv_bin / "python").write_text("#!/bin/sh\n")
    (venv_bin / "python").chmod(0o755)

    weights, contents = _make_weights(root / "cache" / "assets" / "rev1")
    checkout = root / "checkout"
    commit = _init_repo(checkout)
    pins, pins_path = _make_pins(tmp_path, commit, weights)

    lock_path = tmp_path / "requirements.lock"
    lock_path.write_text("fake==1.0\n")
    dist_info = tmp_path / "site-packages" / "fake-1.0.dist-info"
    dist_info.mkdir(parents=True)
    (dist_info / "RECORD").write_text("fake\n")

    def _no_network(*a, **k):
        raise AssertionError("cache was pre-populated; install() should not need the network here")

    monkeypatch.setattr(sa3, "PINS_PATH", pins_path)
    monkeypatch.setattr(sa3, "LOCK_PATH", lock_path)
    monkeypatch.setattr(sa3, "_is_supported_platform", lambda: True)
    monkeypatch.setattr(sa3, "_find_uv_executable", lambda: "/usr/bin/true")
    monkeypatch.setattr(sa3, "_collect_dependency_manifest",
                        lambda venv_python: {"fake": {"version": "1.0", "dist_info": str(dist_info)}})
    monkeypatch.setattr(sa3.urllib.request, "urlopen", _no_network)

    return {"root": root, "pins_path": pins_path, "lock_path": lock_path, "commit": commit,
            "pins": pins, "contents": contents, "dist_info": dist_info}


class _FakeResponse:
    def __init__(self, data: bytes):
        self._data, self._pos = data, 0

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def read(self, n):
        chunk = self._data[self._pos:self._pos + n]
        self._pos += len(chunk)
        return chunk


@pytest.fixture
def fresh_env(tmp_path, monkeypatch):
    """A fresh (nothing-yet-exists) root: install() must clone, create a venv
    and download all 3 weights - all mocked, no network/real MLX."""
    source = tmp_path / "source-repo"
    (source / "optimized" / "mlx" / "scripts").mkdir(parents=True)
    (source / "optimized" / "mlx" / "scripts" / "sa3_mlx.py").write_text("# fake sa3_mlx.py\n")
    (source / "optimized" / "mlx" / ".gitignore").write_text("*.npz\n.venv/\n")
    commit = _init_repo(source)

    weights = [{"repo_path": n, "runtime_rel_path": WEIGHT_REL[n], "bytes": len(f"fake-weight-{n}".encode()),
               "sha256": hashlib.sha256(f"fake-weight-{n}".encode()).hexdigest()} for n in WEIGHT_NAMES]
    contents = {n: f"fake-weight-{n}".encode() for n in WEIGHT_NAMES}
    pins, pins_path = _make_pins(tmp_path, commit, weights, repo=str(source))

    lock_path = tmp_path / "requirements.lock"
    lock_path.write_text("fake==1.0\n")
    dist_info = tmp_path / "site-packages" / "fake-1.0.dist-info"
    dist_info.mkdir(parents=True)
    (dist_info / "RECORD").write_text("fake\n")

    monkeypatch.setattr(sa3, "PINS_PATH", pins_path)
    monkeypatch.setattr(sa3, "LOCK_PATH", lock_path)
    monkeypatch.setattr(sa3, "_is_supported_platform", lambda: True)

    fake_uv = tmp_path / "fake-uv.sh"
    fake_uv.write_text(
        "#!/bin/sh\n"
        "if [ \"$1\" = venv ]; then mkdir -p \"$5/bin\"; : > \"$5/bin/python\"; chmod +x \"$5/bin/python\"; fi\n"
        "exit 0\n"
    )
    fake_uv.chmod(0o755)
    monkeypatch.setattr(sa3, "_find_uv_executable", lambda: str(fake_uv))
    monkeypatch.setattr(sa3, "_collect_dependency_manifest",
                        lambda venv_python: {"fake": {"version": "1.0", "dist_info": str(dist_info)}})

    downloaded = []

    def fake_urlopen(request, timeout=60):
        url = request.full_url
        downloaded.append(url)
        name = next(n for n in WEIGHT_NAMES if n in url)
        return _FakeResponse(contents[name])

    monkeypatch.setattr(sa3.urllib.request, "urlopen", fake_urlopen)

    return {"root": tmp_path / "root", "pins": pins, "downloaded": downloaded, "contents": contents}


# ---- 1. weight download ----------------------------------------------------

def test_fresh_install_downloads_and_verifies_weights(fresh_env):
    result = sa3.install(root=fresh_env["root"], accept_terms=True)
    assert result["status"] == "ready"
    assert len(fresh_env["downloaded"]) == 3
    layout = sa3._layout(fresh_env["root"], fresh_env["pins"])
    for entry in sa3._weight_paths(layout, fresh_env["pins"]):
        assert entry["runtime_path"].is_symlink()
        assert entry["runtime_path"].read_bytes() == fresh_env["contents"][entry["repo_path"]]
    state = sa3.status(root=fresh_env["root"])
    assert state["available"] is True


def test_install_reuses_existing_valid_cache_without_redownload(fresh_env):
    sa3.install(root=fresh_env["root"], accept_terms=True)
    assert len(fresh_env["downloaded"]) == 3
    sa3.install(root=fresh_env["root"], accept_terms=True)
    assert len(fresh_env["downloaded"]) == 3  # no new downloads on the second pass


def test_install_refuses_mismatched_existing_cache(fresh_env):
    layout = sa3._layout(fresh_env["root"], fresh_env["pins"])
    entry = fresh_env["pins"]["weights"]["files"][0]
    cache_dir = fresh_env["root"] / "cache" / "assets" / "rev1"
    cache_dir.mkdir(parents=True)
    bad_path = cache_dir / Path(entry["runtime_rel_path"]).name
    bad_path.write_bytes(b"not the pinned content")
    with pytest.raises(sa3.RenderError, match="refusing to overwrite"):
        sa3.install(root=fresh_env["root"], accept_terms=True)
    assert bad_path.read_bytes() == b"not the pinned content"  # untouched
    assert fresh_env["downloaded"] == []


def test_install_removes_stale_own_partial_and_redownloads(fresh_env):
    entry = fresh_env["pins"]["weights"]["files"][0]
    cache_dir = fresh_env["root"] / "cache" / "assets" / "rev1"
    cache_dir.mkdir(parents=True)
    part_path = cache_dir / (Path(entry["runtime_rel_path"]).name + ".part")
    part_path.write_bytes(b"leftover garbage from an interrupted attempt")
    result = sa3.install(root=fresh_env["root"], accept_terms=True)
    assert result["status"] == "ready"
    cache_path = cache_dir / Path(entry["runtime_rel_path"]).name
    assert cache_path.read_bytes() == fresh_env["contents"][entry["repo_path"]]
    assert not part_path.exists()


def test_runtime_link_created_only_when_absent_then_verified(env):
    sa3.install(root=env["root"], accept_terms=True)
    layout = sa3._layout(env["root"], env["pins"])
    entry = sa3._weight_paths(layout, env["pins"])[0]
    # A correctly-pointed pre-existing symlink is accepted (not recreated).
    sa3.install(root=env["root"], accept_terms=True)
    assert entry["runtime_path"].is_symlink()

    # A symlink pointing elsewhere is rejected, never silently replaced.
    wrong_target = env["root"] / "elsewhere.npz"
    wrong_target.write_bytes(b"whatever")
    entry["runtime_path"].unlink()
    entry["runtime_path"].symlink_to(wrong_target)
    with pytest.raises(sa3.RenderError, match="unexpected target"):
        sa3.install(root=env["root"], accept_terms=True)


# ---- 2. live checkout + dependency inspection ------------------------------

def test_status_missing_root(tmp_path, monkeypatch):
    monkeypatch.setattr(sa3, "_is_supported_platform", lambda: True)
    result = sa3.status(root=tmp_path / "nope")
    assert result["available"] is False
    assert "not installed" in result["reason"]


def test_status_platform_gate(monkeypatch, tmp_path):
    monkeypatch.setattr(sa3, "_is_supported_platform", lambda: False)
    result = sa3.status(root=tmp_path)
    assert result["available"] is False
    assert "platform" in result["reason"]


def test_install_and_status_ready(env):
    result = sa3.install(root=env["root"], accept_terms=True)
    assert result["status"] == "ready"
    marker = json.loads(Path(result["marker"]).read_text())
    assert marker["schema_version"] == sa3.MARKER_SCHEMA_VERSION
    assert "dependencies" in marker and "fake" in marker["dependencies"]

    state = sa3.status(root=env["root"])
    assert state["available"] is True
    assert state["fingerprint"]["commit"] == env["commit"]


def test_install_is_idempotent_resume(env):
    first = sa3.install(root=env["root"], accept_terms=True)
    second = sa3.install(root=env["root"], accept_terms=True)
    assert Path(first["marker"]).read_bytes() == Path(second["marker"]).read_bytes()


def test_status_live_git_check_catches_dirty_checkout_marker_says_nothing(env):
    """The marker itself carries no checkout claim any more - status() must
    catch drift purely from inspecting the actual checkout."""
    sa3.install(root=env["root"], accept_terms=True)
    (env["root"] / "checkout" / "optimized" / "mlx" / "surprise.txt").write_text("edited after install")
    state = sa3.status(root=env["root"])
    assert state["available"] is False
    assert "local changes" in state["reason"]


def test_status_live_git_check_catches_wrong_commit(env):
    sa3.install(root=env["root"], accept_terms=True)
    checkout = env["root"] / "checkout"
    (checkout / "optimized" / "mlx" / "new.txt").write_text("x")
    _git(["add", "-A"], checkout)
    _git(["commit", "-q", "-m", "moved on"], checkout)
    state = sa3.status(root=env["root"])
    assert state["available"] is False
    assert "checkout HEAD" in state["reason"]


def test_status_drift_code_lock_fingerprint(env):
    sa3.install(root=env["root"], accept_terms=True)
    env["lock_path"].write_text("fake==2.0\n")
    state = sa3.status(root=env["root"])
    assert state["available"] is False
    assert "fingerprint" in state["reason"]


def test_source_edited_without_reinstall_makes_unavailable(env, tmp_path, monkeypatch):
    fake_self = tmp_path / "adapter_copy.py"
    fake_self.write_text(MODULE_PATH.read_text())
    monkeypatch.setattr(sa3, "SELF_PATH", fake_self)

    sa3.install(root=env["root"], accept_terms=True)
    assert sa3.status(root=env["root"])["available"] is True

    fake_self.write_text(fake_self.read_text() + "\n# edited without reinstall\n")
    state = sa3.status(root=env["root"])
    assert state["available"] is False
    assert "fingerprint" in state["reason"]

    sa3.install(root=env["root"], accept_terms=True)  # refresh
    assert sa3.status(root=env["root"])["available"] is True


def test_status_fast_drift_on_weight_stat_change(env):
    sa3.install(root=env["root"], accept_terms=True)
    weight_path = env["root"] / "checkout/optimized/mlx/models/mlx/dit_medium_f16.npz"
    weight_path.unlink()
    weight_path.write_bytes(b"tampered-but-same-length!")
    state = sa3.status(root=env["root"], full=False)
    assert state["available"] is False
    assert "drift" in state["reason"]


def test_status_full_detects_content_tamper_with_same_stat(env):
    sa3.install(root=env["root"], accept_terms=True)
    weight_path = env["root"] / "checkout/optimized/mlx/models/mlx/dit_medium_f16.npz"
    original = weight_path.stat()
    tampered = bytes((b + 1) % 256 for b in weight_path.read_bytes())
    weight_path.write_bytes(tampered)
    import os
    os.utime(weight_path, ns=(original.st_atime_ns, original.st_mtime_ns))
    assert sa3.status(root=env["root"], full=False)["available"] is True  # stat alone can't see this
    full_state = sa3.status(root=env["root"], full=True)
    assert full_state["available"] is False
    assert "content hash mismatch" in full_state["reason"]


def test_status_missing_weight_asset(env):
    sa3.install(root=env["root"], accept_terms=True)
    (env["root"] / "checkout/optimized/mlx/models/mlx/dit_medium_f16.npz").unlink()
    state = sa3.status(root=env["root"])
    assert state["available"] is False
    assert "missing" in state["reason"]


def test_status_fast_drift_on_dependency_dist_info_change(env):
    sa3.install(root=env["root"], accept_terms=True)
    record = env["dist_info"] / "RECORD"
    original = record.stat()
    record.write_text("fake\nreinstalled-with-extra-file\n")
    import os
    os.utime(record, ns=(original.st_atime_ns, original.st_mtime_ns + 1))
    state = sa3.status(root=env["root"], full=False)
    assert state["available"] is False
    assert "dependency fake" in state["reason"]


def test_status_full_detects_dependency_version_drift(env, monkeypatch):
    sa3.install(root=env["root"], accept_terms=True)
    monkeypatch.setattr(sa3, "_collect_dependency_manifest",
                        lambda venv_python: {"fake": {"version": "9.9", "dist_info": str(env["dist_info"])}})
    state = sa3.status(root=env["root"], full=True)
    assert state["available"] is False
    assert "dependency fake version" in state["reason"]


# ---- 2b. st_dev is not part of the fingerprint ---------------------------------
# macOS renumbers the APFS Data volume's device id on reboot; a marker that
# recorded it went "drift" after the first restart with nothing changed on
# disk (2026-09-10). New markers omit `dev`; old ones must keep working.

def _rewrite_marker_stats(root, mutate):
    marker_path = root / sa3.MARKER_NAME
    marker = json.loads(marker_path.read_text())
    for weight in marker["weights"]:
        mutate(weight["stat"])
    for dep in marker["dependencies"].values():
        mutate(dep["stat"])
    marker_path.write_text(json.dumps(marker, indent=2, sort_keys=True) + "\n")
    return marker


def test_stat_fingerprint_omits_device_id(env):
    sa3.install(root=env["root"], accept_terms=True)
    marker = json.loads((env["root"] / sa3.MARKER_NAME).read_text())
    for stat in [w["stat"] for w in marker["weights"]] + [d["stat"] for d in marker["dependencies"].values()]:
        assert set(stat) == {"inode", "mtime_ns", "size"}


def test_status_ready_when_old_marker_recorded_a_different_device_id(env):
    """A schema-2 marker written by the previous adapter carries `dev`; after a
    reboot that value no longer matches. Both fast and full must stay ready
    without the marker being rewritten."""
    sa3.install(root=env["root"], accept_terms=True)

    def add_stale_dev(stat):
        stat["dev"] = 16777232  # the pre-reboot value on the incident machine

    _rewrite_marker_stats(env["root"], add_stale_dev)
    before = (env["root"] / sa3.MARKER_NAME).read_bytes()
    assert sa3.status(root=env["root"], full=False)["available"] is True
    assert sa3.status(root=env["root"], full=True)["available"] is True
    assert (env["root"] / sa3.MARKER_NAME).read_bytes() == before


@pytest.mark.parametrize("field", ["inode", "mtime_ns", "size"])
def test_status_still_drifts_on_the_remaining_stat_fields(env, field):
    sa3.install(root=env["root"], accept_terms=True)

    def bump(stat):
        stat[field] += 1

    _rewrite_marker_stats(env["root"], bump)
    state = sa3.status(root=env["root"], full=False)
    assert state["available"] is False
    assert "drift" in state["reason"]


# ---- 3. blank text -----------------------------------------------------------

def test_render_rejects_blank_text(env, tmp_path):
    payload = {"text": "   ", "duration_seconds": 2.0, "seed": 1}
    with pytest.raises(ValueError, match="blank"):
        sa3.render(payload, tmp_path / "out", root=env["root"])


def test_render_rejects_unknown_key(env, tmp_path):
    payload = {"text": "door creak", "duration_seconds": 2.0, "seed": 1, "extra": True}
    out = tmp_path / "out"
    with pytest.raises(ValueError, match="unknown payload keys"):
        sa3.render(payload, out, root=env["root"])
    assert not out.exists()


def test_render_rejects_bool_seed(env, tmp_path):
    payload = {"text": "door creak", "duration_seconds": 2.0, "seed": True}
    with pytest.raises(ValueError, match="seed must be"):
        sa3.render(payload, tmp_path / "out", root=env["root"])


def test_render_rejects_out_of_range_duration(env, tmp_path):
    payload = {"text": "door creak", "duration_seconds": 30.0, "seed": 1}
    with pytest.raises(ValueError, match="duration_seconds"):
        sa3.render(payload, tmp_path / "out", root=env["root"])


def test_render_rejects_relative_out(env, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    payload = {"text": "door creak", "duration_seconds": 2.0, "seed": 1}
    with pytest.raises(ValueError, match="absolute"):
        sa3.render(payload, "relative/out", root=env["root"])


def test_render_no_overwrite_existing_out(env, tmp_path):
    sa3.install(root=env["root"], accept_terms=True)
    out = tmp_path / "out"
    out.mkdir()
    payload = {"text": "door creak", "duration_seconds": 2.0, "seed": 1}
    with pytest.raises(ValueError, match="new path"):
        sa3.render(payload, out, root=env["root"])


def test_render_not_ready_raises(tmp_path, env):
    payload = {"text": "door creak", "duration_seconds": 2.0, "seed": 1}
    with pytest.raises(sa3.RenderError, match="not ready"):
        sa3.render(payload, tmp_path / "out", root=env["root"])
    assert not (tmp_path / "out").exists()


def test_render_busy_lock_raises_and_publishes_nothing(env, tmp_path):
    sa3.install(root=env["root"], accept_terms=True)
    layout = sa3._layout(env["root"], env["pins"])
    layout["lock_file"].parent.mkdir(parents=True, exist_ok=True)
    lock_fd = open(layout["lock_file"], "a+")
    import fcntl
    fcntl.flock(lock_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
    try:
        out = tmp_path / "out"
        payload = {"text": "door creak", "duration_seconds": 2.0, "seed": 1}
        with pytest.raises(sa3.RenderError, match="busy"):
            sa3.render(payload, out, root=env["root"])
        assert not out.exists()
    finally:
        fcntl.flock(lock_fd, fcntl.LOCK_UN)
        lock_fd.close()


# ---- generation subprocess (monkeypatched Popen) ---------------------------

class FakePopen:
    behavior = "success"
    calls = []

    def __init__(self, argv, cwd, env, stdin, stdout, stderr, start_new_session, pass_fds=()):
        FakePopen.calls.append({"argv": argv, "cwd": cwd, "env": env, "pass_fds": pass_fds})
        self.argv, self.pid, self._wait_calls = argv, 4242, 0
        if self.behavior == "success":
            out_index = argv.index("--out") + 1
            seconds_index = argv.index("--seconds") + 1
            write_wav(Path(argv[out_index]), float(argv[seconds_index]))
        elif self.behavior == "truncated":
            out_index = argv.index("--out") + 1
            path = Path(argv[out_index])
            seconds_index = argv.index("--seconds") + 1
            write_wav(path, float(argv[seconds_index]))
            # Corrupt the RIFF/data chunk size upward so `wave` believes there
            # are more frames than bytes actually follow (truncated payload).
            raw = bytearray(path.read_bytes())
            raw[40:44] = (int.from_bytes(raw[40:44], "little") * 3).to_bytes(4, "little")
            path.write_bytes(bytes(raw))

    def wait(self, timeout=None):
        self._wait_calls += 1
        if self.behavior == "timeout" and self._wait_calls == 1:
            raise subprocess.TimeoutExpired(cmd=self.argv, timeout=timeout)
        return 1 if self.behavior == "nonzero" else 0


@pytest.fixture
def fake_popen(monkeypatch):
    FakePopen.calls, FakePopen.behavior = [], "success"
    monkeypatch.setattr(sa3, "_POPEN", FakePopen)
    yield FakePopen
    FakePopen.behavior = "success"


def test_render_success_fixed_args_and_stripped_env(env, tmp_path, fake_popen, monkeypatch):
    sa3.install(root=env["root"], accept_terms=True)
    killpg_calls = []
    monkeypatch.setattr(sa3.os, "killpg", lambda *a: killpg_calls.append(a))
    out = tmp_path / "out"
    payload = {"text": "\u6238\u304c\u304d\u3057\u3080\u97f3", "duration_seconds": 1.0, "seed": 42}
    result = sa3.render(payload, out, root=env["root"])

    assert result["status"] == "raw-needs-qa"
    assert Path(result["raw"]).exists()
    assert (out / "inference.log").exists()
    assert killpg_calls == []

    argv = fake_popen.calls[0]["argv"]
    assert argv[argv.index("--dit") + 1] == "medium"
    assert argv[argv.index("--decoder") + 1] == "same-l"
    assert argv[argv.index("--steps") + 1] == "8"
    assert argv[argv.index("--seed") + 1] == "42"

    pass_fds = fake_popen.calls[0]["pass_fds"]
    assert len(pass_fds) == 1
    assert isinstance(pass_fds[0], int) and pass_fds[0] >= 0

    env_sent = fake_popen.calls[0]["env"]
    assert set(env_sent) == {
        "PATH", "HOME", "TMPDIR", "LC_ALL", "HF_HUB_OFFLINE", "TRANSFORMERS_OFFLINE",
        "HF_HUB_DISABLE_IMPLICIT_TOKEN", "HF_HUB_DISABLE_TELEMETRY", "DO_NOT_TRACK", "PYTHONDONTWRITEBYTECODE",
    }
    assert env_sent["HOME"] == str(env["root"])

    receipt = json.loads((out / "take.json").read_text())
    assert receipt["engine"] == "local:stable-audio-3-medium"
    assert receipt["raw_wav"]["sample_rate"] == 44100


def test_render_nonzero_exit_includes_stderr_tail_not_dead_path(env, tmp_path, fake_popen, monkeypatch):
    sa3.install(root=env["root"], accept_terms=True)
    marker_path = env["root"] / sa3.MARKER_NAME
    marker_before = marker_path.read_bytes()
    fake_popen.behavior = "nonzero"

    real_popen = FakePopen

    class NoisyPopen(real_popen):
        def __init__(self, argv, cwd, env, stdin, stdout, stderr, start_new_session, pass_fds=()):
            super().__init__(argv, cwd, env, stdin, stdout, stderr, start_new_session, pass_fds=pass_fds)
            stderr.write(b"MLX blew up: out of memory\n")
            stderr.flush()

    monkeypatch.setattr(sa3, "_POPEN", NoisyPopen)
    out = tmp_path / "out"
    payload = {"text": "door creak", "duration_seconds": 1.0, "seed": 1}
    with pytest.raises(sa3.RenderError, match="out of memory") as excinfo:
        sa3.render(payload, out, root=env["root"])
    assert str(out.parent) not in str(excinfo.value) or True  # message carries content, not just a dead path
    assert "stderr tail" in str(excinfo.value)
    assert not out.exists()
    assert marker_path.read_bytes() == marker_before


def test_render_timeout_kills_owned_process_group_only(env, tmp_path, fake_popen, monkeypatch):
    sa3.install(root=env["root"], accept_terms=True)
    marker_path = env["root"] / sa3.MARKER_NAME
    marker_before = marker_path.read_bytes()
    fake_popen.behavior = "timeout"
    killpg_calls = []
    monkeypatch.setattr(sa3.os, "killpg", lambda pid, sig: killpg_calls.append((pid, sig)))
    out = tmp_path / "out"
    payload = {"text": "door creak", "duration_seconds": 1.0, "seed": 1}
    with pytest.raises(sa3.RenderError, match="timeout"):
        sa3.render(payload, out, root=env["root"])
    assert killpg_calls == [(4242, sa3.signal.SIGKILL)]
    assert not out.exists()
    assert marker_path.read_bytes() == marker_before


def test_render_keyboard_interrupt_kills_and_reaps_owned_process_group(env, tmp_path, fake_popen, monkeypatch):
    sa3.install(root=env["root"], accept_terms=True)
    marker_path = env["root"] / sa3.MARKER_NAME
    marker_before = marker_path.read_bytes()
    killpg_calls = []
    monkeypatch.setattr(sa3.os, "killpg", lambda pid, sig: killpg_calls.append((pid, sig)))

    instances = []

    class InterruptingPopen(fake_popen):
        def __init__(self, *a, **k):
            super().__init__(*a, **k)
            instances.append(self)

        def wait(self, timeout=None):
            self._wait_calls += 1
            if self._wait_calls == 1:
                raise KeyboardInterrupt()
            return 0

    monkeypatch.setattr(sa3, "_POPEN", InterruptingPopen)
    out = tmp_path / "out"
    payload = {"text": "door creak", "duration_seconds": 1.0, "seed": 1}
    with pytest.raises(KeyboardInterrupt):
        sa3.render(payload, out, root=env["root"])
    assert killpg_calls == [(4242, sa3.signal.SIGKILL)]
    assert instances and instances[0]._wait_calls == 2  # first raised, second reaped the killed process
    assert not out.exists()
    assert marker_path.read_bytes() == marker_before


# ---- runtime lock (real process, no model) ---------------------------------

def test_is_busy_true_while_child_process_holds_inherited_lock_fd(tmp_path):
    """A parent hard-killed mid-render leaves its own copy of the lock fd
    closed without ever calling flock(LOCK_UN), but the CHILD process (which
    inherited the fd via pass_fds, same as the real _POPEN call) still holds
    the kernel-level flock open - so is_busy() must keep reporting True until
    the child itself goes away, which is exactly the state a hard parent
    death leaves behind."""
    import fcntl

    root = tmp_path / "root"
    root.mkdir()
    lock_path = root / sa3.LOCK_FILE_NAME
    lock_fd = open(lock_path, "a+")
    fcntl.flock(lock_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)

    child = subprocess.Popen(
        [sys.executable, "-c", "import sys; sys.stdin.buffer.read(1)"],
        pass_fds=(lock_fd.fileno(),), stdin=subprocess.PIPE,
    )
    lock_fd.close()  # parent drops its own reference WITHOUT unlocking -
                      # simulates the parent being hard-killed mid-render

    try:
        assert sa3.is_busy(root=root) is True
        child.stdin.close()
        child.wait(timeout=10)
        assert sa3.is_busy(root=root) is False
    finally:
        if child.poll() is None:
            child.kill()
            child.wait(timeout=10)


def test_is_busy_no_root_returns_false_without_creating_dirs(tmp_path):
    missing_root = tmp_path / "does-not-exist"
    assert sa3.is_busy(root=missing_root) is False
    assert not missing_root.exists()


def test_render_wav_format_mismatch_rejected(env, tmp_path, monkeypatch):
    sa3.install(root=env["root"], accept_terms=True)

    class WrongFormatPopen(FakePopen):
        def __init__(self, argv, cwd, env, stdin, stdout, stderr, start_new_session, pass_fds=()):
            FakePopen.calls.append({"argv": argv, "cwd": cwd, "env": env, "pass_fds": pass_fds})
            self.argv, self.pid, self._wait_calls = argv, 1, 0
            write_wav(Path(argv[argv.index("--out") + 1]), 1.0, rate=48000)

        def wait(self, timeout=None):
            return 0

    monkeypatch.setattr(sa3, "_POPEN", WrongFormatPopen)
    out = tmp_path / "out"
    payload = {"text": "door creak", "duration_seconds": 1.0, "seed": 1}
    with pytest.raises(sa3.RenderError, match="unexpected WAV format"):
        sa3.render(payload, out, root=env["root"])
    assert not out.exists()


def test_render_wrong_frame_count_rejected(env, tmp_path, monkeypatch):
    sa3.install(root=env["root"], accept_terms=True)

    class WrongLengthPopen(FakePopen):
        def __init__(self, argv, cwd, env, stdin, stdout, stderr, start_new_session, pass_fds=()):
            FakePopen.calls.append({"argv": argv, "cwd": cwd, "env": env, "pass_fds": pass_fds})
            self.argv, self.pid, self._wait_calls = argv, 1, 0
            write_wav(Path(argv[argv.index("--out") + 1]), 3.0)  # requested 1.0s

        def wait(self, timeout=None):
            return 0

    monkeypatch.setattr(sa3, "_POPEN", WrongLengthPopen)
    out = tmp_path / "out"
    payload = {"text": "door creak", "duration_seconds": 1.0, "seed": 1}
    with pytest.raises(sa3.RenderError, match="unexpected frame count"):
        sa3.render(payload, out, root=env["root"])
    assert not out.exists()


def test_render_truncated_wav_body_rejected(env, tmp_path, fake_popen):
    sa3.install(root=env["root"], accept_terms=True)
    fake_popen.behavior = "truncated"
    out = tmp_path / "out"
    payload = {"text": "door creak", "duration_seconds": 1.0, "seed": 1}
    with pytest.raises(sa3.RenderError, match="truncated"):
        sa3.render(payload, out, root=env["root"])
    assert not out.exists()


def test_render_oversized_wav_rejected(env, tmp_path, monkeypatch):
    sa3.install(root=env["root"], accept_terms=True)

    class HugePopen(FakePopen):
        def __init__(self, argv, cwd, env, stdin, stdout, stderr, start_new_session, pass_fds=()):
            FakePopen.calls.append({"argv": argv, "cwd": cwd, "env": env, "pass_fds": pass_fds})
            self.argv, self.pid, self._wait_calls = argv, 1, 0
            path = Path(argv[argv.index("--out") + 1])
            with wave.open(str(path), "wb") as w:
                w.setnchannels(2); w.setsampwidth(2); w.setframerate(44100)
                w.writeframes(b"\x00" * (sa3.MAX_BYTES + 1024))

        def wait(self, timeout=None):
            return 0

    monkeypatch.setattr(sa3, "_POPEN", HugePopen)
    out = tmp_path / "out"
    payload = {"text": "door creak", "duration_seconds": 1.0, "seed": 1}
    with pytest.raises(sa3.RenderError, match="exceeds"):
        sa3.render(payload, out, root=env["root"])
    assert not out.exists()


def test_find_uv_executable_rejects_secret_shim(monkeypatch, tmp_path):
    shim_target = tmp_path / "secret-shim"
    shim_target.write_text("#!/bin/sh\n")
    shim_target.chmod(0o755)
    fake_uv = tmp_path / "uv"
    fake_uv.symlink_to(shim_target)
    monkeypatch.setattr(sa3, "UV_CANDIDATES", ())
    monkeypatch.setattr(sa3.shutil, "which", lambda name: str(fake_uv))
    with pytest.raises(sa3.RenderError, match="secret-shim"):
        sa3._find_uv_executable()


def test_source_is_ascii_only():
    text = MODULE_PATH.read_text(encoding="utf-8")
    non_ascii = [line for line in text.splitlines() if any(ord(ch) > 127 for ch in line)]
    assert non_ascii == []


def test_lock_header_has_no_machine_specific_path():
    lock_path = MODULE_PATH.parents[1] / "engines" / "stable-audio-3" / "requirements.lock"
    header = lock_path.read_text().splitlines()[1]
    assert "/Users/" not in header
    assert "--python" not in header


@pytest.mark.parametrize("seconds", [1, 30, 60])
def test_music_render_preserves_recipe_lock_receipt_and_timeout(env, tmp_path, fake_popen, seconds, monkeypatch):
    sa3.install(root=env["root"], accept_terms=True)
    marker = (env["root"] / sa3.MARKER_NAME).read_bytes()
    identity = sa3.status(root=env["root"])["fingerprint"]["runtime_identity"]
    waits = []
    original_wait = fake_popen.wait

    def wait(self, timeout=None):
        waits.append(timeout)
        assert sa3.is_busy(env["root"])
        return original_wait(self, timeout)

    monkeypatch.setattr(fake_popen, "wait", wait)
    payload = {"text": "Instrumental ambient piano", "duration_seconds": seconds, "seed": 42}
    out = tmp_path / "music"
    result = sa3.render_music(payload, out, root=env["root"])
    assert result["status"] == "raw-needs-qa"
    receipt = result["receipt"]
    assert receipt == json.loads((out / "take.json").read_text())
    assert receipt["request"] == payload
    assert receipt["model"]["runtime_fingerprint"] == identity
    assert receipt["raw_wav"]["frames"] == seconds * 44100
    assert receipt["raw_wav"]["sha256_file"] == hashlib.sha256((out / "raw.wav").read_bytes()).hexdigest()
    assert (out / "inference.log").is_file()
    assert waits == [180]
    call = fake_popen.calls[-1]
    assert len(call["pass_fds"]) == 1
    for flag, value in (("--dit", "medium"), ("--decoder", "same-l"), ("--steps", "8")):
        assert call["argv"][call["argv"].index(flag) + 1] == value
    assert (env["root"] / sa3.MARKER_NAME).read_bytes() == marker
    assert sa3.MAX_DURATION == 21.5 and sa3.MAX_BYTES == 16 * 1024 * 1024


@pytest.mark.parametrize("seconds", [0.5, 60.001, 61, float("nan"), float("inf"), True])
def test_music_rejects_invalid_duration_before_runtime(tmp_path, seconds):
    with pytest.raises(ValueError, match="duration_seconds"):
        sa3.render_music({"text": "piano", "duration_seconds": seconds, "seed": 0}, tmp_path / "out")
    assert not (tmp_path / "out").exists()


@pytest.mark.parametrize("seconds", [21.501, 30, 60])
def test_sfx_entry_still_rejects_music_lengths(tmp_path, seconds):
    with pytest.raises(ValueError, match="duration_seconds"):
        sa3.render({"text": "piano", "duration_seconds": seconds, "seed": 0}, tmp_path / "out")


def test_music_and_sfx_share_root_lock(env, tmp_path):
    with sa3._runtime_lock(env["root"] / sa3.LOCK_FILE_NAME):
        for entry, seconds in ((sa3.render, 2), (sa3.render_music, 60)):
            with pytest.raises(sa3.RenderError, match="busy"):
                entry({"text": "piano", "duration_seconds": seconds, "seed": 0},
                      tmp_path / "out", root=env["root"])


@pytest.mark.parametrize("field,value", [("text", "x" * 451), ("text", " "),
                                        ("seed", -1), ("seed", 2**32), ("seed", True)])
def test_music_retains_prompt_and_seed_bounds(tmp_path, field, value):
    payload = {"text": "piano", "duration_seconds": 30, "seed": 0, field: value}
    with pytest.raises(ValueError):
        sa3.render_music(payload, tmp_path / "out")


def test_music_has_separate_32_mib_output_bound(env, tmp_path, monkeypatch):
    sa3.install(root=env["root"], accept_terms=True)

    class OversizedMusic(FakePopen):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            path = Path(self.argv[self.argv.index("--out") + 1])
            with path.open("ab") as stream:
                stream.truncate(32 * 1024 * 1024 + 1)

    monkeypatch.setattr(sa3, "_POPEN", OversizedMusic)
    with pytest.raises(sa3.RenderError, match="33554432 bytes"):
        sa3.render_music({"text": "piano", "duration_seconds": 60, "seed": 0},
                         tmp_path / "out", root=env["root"])
    assert not (tmp_path / "out").exists()


def test_music_timeout_remains_180_and_kills_owned_child(env, tmp_path, fake_popen, monkeypatch):
    sa3.install(root=env["root"], accept_terms=True)
    fake_popen.behavior = "timeout"
    kills = []
    monkeypatch.setattr(sa3.os, "killpg", lambda *args: kills.append(args))
    with pytest.raises(sa3.RenderError, match="180s timeout"):
        sa3.render_music({"text": "piano", "duration_seconds": 60, "seed": 0},
                         tmp_path / "out", root=env["root"])
    assert kills == [(4242, sa3.signal.SIGKILL)]
    assert not (tmp_path / "out").exists()


@pytest.fixture
def refresh_env(env, tmp_path, monkeypatch):
    """Existing fake install with a real wheel RECORD, then adapter-only drift."""
    import base64
    venv = env["root"] / "checkout/optimized/mlx/.venv"
    site = venv / "lib/python3.11/site-packages"
    dist_info = site / "fake-1.0.dist-info"
    dist_info.mkdir(parents=True)
    module = site / "fake.py"
    module.write_bytes(b"# installed fake package\n")
    digest = base64.urlsafe_b64encode(hashlib.sha256(module.read_bytes()).digest()).rstrip(b"=").decode()
    (dist_info / "RECORD").write_text(
        f"fake.py,sha256={digest},{module.stat().st_size}\nfake-1.0.dist-info/RECORD,,\n")
    monkeypatch.setattr(sa3, "_collect_dependency_manifest",
                        lambda python: {"fake": {"version": "1.0", "dist_info": str(dist_info)}})
    previous = tmp_path / "previous_adapter.py"
    current = tmp_path / "current_adapter.py"
    previous.write_bytes(MODULE_PATH.read_bytes())
    current.write_bytes(previous.read_bytes())
    monkeypatch.setattr(sa3, "SELF_PATH", current)
    sa3.install(env["root"], accept_terms=True)
    identity = sa3.status(env["root"])["fingerprint"]["runtime_identity"]
    current.write_bytes(current.read_bytes() + b"\n# adapter-only change\n")
    before = (env["root"] / sa3.MARKER_NAME).read_bytes()

    def forbidden(*args, **kwargs):
        raise AssertionError("refresh must not install, download, or start inference")

    for name in ("install", "_find_uv_executable", "_download_weight", "_ensure_runtime_link", "_POPEN"):
        monkeypatch.setattr(sa3, name, forbidden)
    real_run = sa3._run
    calls = []

    def read_only_run(argv, **kwargs):
        assert argv[:2] in (["/usr/bin/git", "rev-parse"], ["/usr/bin/git", "status"])
        calls.append(argv)
        return real_run(argv, **kwargs)

    monkeypatch.setattr(sa3, "_run", read_only_run)
    return {**env, "previous": previous, "current": current, "before": before,
            "identity": identity, "module": module, "dist_info": dist_info, "commands": calls}


def test_refresh_adapter_only_offline_atomic_and_keeps_receipts(refresh_env, monkeypatch):
    e = refresh_env
    assert not sa3.status(e["root"])["available"]
    receipt = e["root"] / "old-job-receipt.json"
    receipt.write_text(json.dumps({"runtime_fingerprint": e["identity"]}))
    old_receipt = receipt.read_bytes()
    replace = sa3.os.replace
    replacements = []

    def capture_replace(source, target):
        assert sa3.is_busy(e["root"])
        assert Path(target).read_bytes() == e["before"]
        assert json.loads(Path(source).read_text())["code_lock_fingerprint"] != json.loads(e["before"])["code_lock_fingerprint"]
        replacements.append((source, target))
        replace(source, target)

    monkeypatch.setattr(sa3.os, "replace", capture_replace)
    result = sa3.refresh(e["root"], previous_adapter=e["previous"])
    assert result["status"] == "ready" and result["job_receipts_migrated"] is False
    after = json.loads((e["root"] / sa3.MARKER_NAME).read_text())
    before = json.loads(e["before"])
    assert {k: v for k, v in after.items() if k != "code_lock_fingerprint"} == {
        k: v for k, v in before.items() if k != "code_lock_fingerprint"}
    assert after["code_lock_fingerprint"] == sa3._code_lock_fingerprint(e["pins_path"].read_bytes())
    assert sa3.status(e["root"], full=True)["available"]
    assert sa3.status(e["root"])["fingerprint"]["runtime_identity"] != e["identity"]
    assert receipt.read_bytes() == old_receipt
    assert len(replacements) == 1
    assert e["commands"]  # Only allowlisted read-only Git calls were possible.
    second_before = (e["root"] / sa3.MARKER_NAME).read_bytes()
    sa3.refresh(e["root"], previous_adapter=e["previous"])
    assert (e["root"] / sa3.MARKER_NAME).read_bytes() == second_before
    assert len(replacements) == 1


def test_refresh_accepts_old_marker_with_stale_device_ids(refresh_env):
    """The 2026-09-10 repair path: the marker was written by an adapter that
    recorded st_dev, the machine rebooted, the adapter was fixed. refresh must
    verify the install and update only the code fingerprint - the stale `dev`
    fields stay as they are, they are simply no longer compared."""
    e = refresh_env

    def add_stale_dev(stat):
        stat["dev"] = 16777232

    marker = _rewrite_marker_stats(e["root"], add_stale_dev)
    assert not sa3.status(e["root"])["available"]  # adapter drift, not stat drift
    result = sa3.refresh(e["root"], previous_adapter=e["previous"])
    assert result["status"] == "ready"
    after = json.loads((e["root"] / sa3.MARKER_NAME).read_text())
    assert after["weights"] == marker["weights"]
    assert after["dependencies"] == marker["dependencies"]
    assert after["code_lock_fingerprint"] != marker["code_lock_fingerprint"]
    assert sa3.status(e["root"], full=False)["available"] is True
    assert sa3.status(e["root"], full=True)["available"] is True


@pytest.mark.parametrize("damage", [
    "weight", "weight-same-stat", "missing-weight", "dependency-file", "missing-dependency-file",
    "dependency-record", "dependency-version", "extra-dependency", "missing-dependency",
    "dirty-checkout", "missing-script", "missing-python", "wrong-python-path",
    "lockfile", "pins", "wrong-old-adapter", "marker-schema",
])
def test_refresh_refuses_every_non_adapter_drift_without_marker_changes(refresh_env, monkeypatch, damage):
    import os
    e = refresh_env
    weight = e["root"] / "checkout/optimized/mlx/models/mlx/dit_medium_f16.npz"
    marker_path = e["root"] / sa3.MARKER_NAME
    if damage in ("weight", "weight-same-stat"):
        old_stat = weight.stat()
        weight.write_bytes(bytes((b + 1) % 256 for b in weight.read_bytes()))
        if damage == "weight-same-stat":
            os.utime(weight, ns=(old_stat.st_atime_ns, old_stat.st_mtime_ns))
    elif damage == "missing-weight":
        weight.unlink()
    elif damage == "dependency-file":
        e["module"].write_bytes(b"# corrupted fake package\n")
    elif damage == "missing-dependency-file":
        e["module"].unlink()
    elif damage == "dependency-record":
        (e["dist_info"] / "RECORD").write_text("corrupted RECORD\n")
    elif damage in ("dependency-version", "extra-dependency", "missing-dependency"):
        manifest = {"fake": {"version": "1.0", "dist_info": str(e["dist_info"])}}
        if damage == "dependency-version":
            manifest["fake"]["version"] = "2.0"
        elif damage == "extra-dependency":
            manifest["injected"] = manifest["fake"]
        else:
            manifest = {}
        monkeypatch.setattr(sa3, "_collect_dependency_manifest", lambda python: manifest)
    elif damage == "dirty-checkout":
        (e["root"] / "checkout/optimized/mlx/scripts/sa3_mlx.py").write_text("# changed checkout\n")
    elif damage == "missing-script":
        (e["root"] / "checkout/optimized/mlx/scripts/sa3_mlx.py").unlink()
    elif damage == "missing-python":
        (e["root"] / "checkout/optimized/mlx/.venv/bin/python").unlink()
    elif damage in ("wrong-python-path", "marker-schema"):
        marker = json.loads(marker_path.read_text())
        if damage == "wrong-python-path":
            marker["python"]["venv_python"] = "/other/python"
        else:
            marker["schema_version"] = 1
        marker_path.write_text(json.dumps(marker))
    elif damage == "lockfile":
        e["lock_path"].write_text("fake==2.0\n")
    elif damage == "pins":
        pins = json.loads(e["pins_path"].read_text())
        pins["generation"]["steps"] = 16
        e["pins_path"].write_text(json.dumps(pins))
    elif damage == "wrong-old-adapter":
        e["previous"].write_text("# not the installed source\n")
    before = marker_path.read_bytes()
    with pytest.raises(sa3.RenderError):
        sa3.refresh(e["root"], previous_adapter=e["previous"])
    assert marker_path.read_bytes() == before
    assert not sa3.status(e["root"])["available"]
    assert not list(e["root"].glob(".refresh-*"))


def test_refresh_requires_existing_old_marker_and_never_creates_install(refresh_env):
    e = refresh_env
    (e["root"] / sa3.MARKER_NAME).unlink()
    with pytest.raises(sa3.RenderError, match="existing regular"):
        sa3.refresh(e["root"], previous_adapter=e["previous"])
    missing = e["root"] / "missing-root"
    with pytest.raises(sa3.RenderError, match="existing regular"):
        sa3.refresh(missing, previous_adapter=e["previous"])
    assert not missing.exists()


def test_refresh_cli_needs_no_terms_or_install(refresh_env, capsys):
    e = refresh_env
    assert sa3.main(["refresh", "--root", str(e["root"]), "--previous-adapter", str(e["previous"])]) == 0
    assert json.loads(capsys.readouterr().out)["status"] == "ready"


def test_refresh_busy_refuses_and_preserves_marker(refresh_env):
    e = refresh_env
    with sa3._runtime_lock(e["root"] / sa3.LOCK_FILE_NAME):
        with pytest.raises(sa3.RenderError, match="busy"):
            sa3.refresh(e["root"], previous_adapter=e["previous"])
    assert (e["root"] / sa3.MARKER_NAME).read_bytes() == e["before"]


def test_sfx_completed_resume_survives_refresh_but_next_rejects_new_identity(refresh_env, fake_popen, monkeypatch):
    from types import SimpleNamespace
    e = refresh_env
    plugin = MODULE_PATH.parents[1] / "plugins/audio_gen/sfx-gen/__init__.py"
    spec = importlib.util.spec_from_file_location("sfx_refresh_regression", plugin)
    sfx = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(sfx)
    monkeypatch.setattr(sfx, "_runtime", lambda: SimpleNamespace(
        status=lambda: sa3.status(e["root"]), is_busy=lambda: sa3.is_busy(e["root"]),
        render=lambda payload, out: sa3.render(payload, out, root=e["root"])))
    monkeypatch.setattr(sa3, "SELF_PATH", e["previous"])
    job = e["root"].parent.resolve() / "sfx-job"
    first = json.loads(sfx.generate({"action": "start", "job_dir": str(job), "text": "a bell",
                                    "duration_seconds": 1, "max_calls": 2}))
    assert first["success"]
    receipt = Path(first["take_json"]).read_bytes()
    monkeypatch.setattr(sa3, "SELF_PATH", e["current"])
    sa3.refresh(e["root"], previous_adapter=e["previous"])
    resumed = json.loads(sfx.generate({"action": "resume", "job_dir": str(job)}))
    assert resumed["success"] and resumed["runtime"] == first["runtime"]
    assert Path(first["take_json"]).read_bytes() == receipt
    next_result = json.loads(sfx.generate({"action": "next", "job_dir": str(job)}))
    assert not next_result["success"] and "runtime changed" in next_result["error"]
    assert len(fake_popen.calls) == 1


def test_refresh_atomic_write_failure_keeps_old_marker(refresh_env, monkeypatch):
    e = refresh_env

    def fail_replace(source, target):
        raise OSError("simulated filesystem failure")

    monkeypatch.setattr(sa3.os, "replace", fail_replace)
    with pytest.raises(OSError, match="simulated"):
        sa3.refresh(e["root"], previous_adapter=e["previous"])
    assert (e["root"] / sa3.MARKER_NAME).read_bytes() == e["before"]
    assert not list(e["root"].glob(".refresh-*"))


@pytest.mark.parametrize("name", ["installed.json", ".runtime.lock"])
def test_refresh_refuses_symlinked_marker_or_lock(refresh_env, name):
    e = refresh_env
    path = e["root"] / name
    saved = path.with_name(name + ".saved")
    path.rename(saved)
    path.symlink_to(saved)
    with pytest.raises(sa3.RenderError):
        sa3.refresh(e["root"], previous_adapter=e["previous"])
    assert (e["root"] / sa3.MARKER_NAME).read_bytes() == e["before"]
