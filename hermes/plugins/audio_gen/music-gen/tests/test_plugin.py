"""Fake inference and HTTP only. No model, secret lookup, network or payment."""

from __future__ import annotations

import copy
import hashlib
import importlib.util
import inspect
import json
import wave
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import fal_client
import pytest

PLUGIN = Path(__file__).resolve().parents[1] / "__init__.py"
SPEC = importlib.util.spec_from_file_location("music_gen_tests", PLUGIN)
M = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(M)


def wav(path, seconds=1, rate=44100):
    pcm = b"\0" * (round(seconds * rate) * 4)
    with wave.open(str(path), "wb") as stream:
        stream.setnchannels(2)
        stream.setsampwidth(2)
        stream.setframerate(rate)
        stream.writeframes(pcm)
    return pcm


@pytest.fixture(autouse=True)
def offline(monkeypatch):
    import requests
    import httpx
    monkeypatch.setattr(requests, "post", Mock(side_effect=AssertionError("real POST prohibited")))
    monkeypatch.setattr(requests, "get", Mock(side_effect=AssertionError("real GET prohibited")))
    monkeypatch.setattr(httpx.Client, "send", Mock(side_effect=AssertionError("real HTTP prohibited")))
    monkeypatch.setattr(M, "_key", Mock(return_value="fake-scoped-key"))


@pytest.fixture
def rig(tmp_path, monkeypatch):
    root = tmp_path.resolve()
    runtime = SimpleNamespace(
        status=Mock(return_value={"available": True, "reason": "ready", "fingerprint": {"runtime_identity": "fake-runtime"}}),
        is_busy=Mock(return_value=False),
        RenderError=M._load(M.HERMES / "scripts/stable_audio3.py", "music_test_runtime").RenderError,
    )

    def render(payload, bundle):
        state = json.loads((bundle.parent / "state.json").read_text())
        assert state["attempts"][-1]["status"] == "running"
        bundle.mkdir()
        pcm = wav(bundle / "raw.wav", payload["duration_seconds"])
        receipt = {"engine": M.LOCAL_ENGINE, "request": dict(payload),
                   "model": {"runtime_fingerprint": "fake-runtime"},
                   "raw_wav": {"sha256_file": hashlib.sha256((bundle / "raw.wav").read_bytes()).hexdigest(),
                               "sha256_pcm": hashlib.sha256(pcm).hexdigest(), "frames": len(pcm) // 4,
                               "sample_rate": 44100, "channels": 2, "sample_width_bytes": 2}}
        (bundle / "take.json").write_text(json.dumps(receipt))
        (bundle / "inference.log").write_text("fake inference completed\n")
        return {"status": "raw-needs-qa", "receipt": receipt, "raw": str(bundle / "raw.wav")}

    runtime.render_music = Mock(side_effect=render)
    monkeypatch.setattr(M, "_runtime", Mock(return_value=runtime))
    handle = SimpleNamespace(request_id="fake-id", status=Mock(return_value=fal_client.Queued(position=0)), get=Mock())
    client = SimpleNamespace(submit=Mock(return_value=handle), get_handle=Mock(return_value=handle))
    factory = Mock(return_value=client)
    monkeypatch.setattr(M, "_client", factory)
    monkeypatch.setattr(M, "_download", Mock(side_effect=lambda url, out: wav(out)))
    manifests = {}

    def load_approved(path, sha, kind):
        assert kind == "generate"
        manifest = manifests[path]
        if hashlib.sha256(Path(path).read_bytes()).hexdigest() != sha:
            raise ValueError("approved proposal changed")
        return copy.deepcopy(manifest)

    original_load = M._load
    monkeypatch.setattr(M, "_load", lambda path, name: SimpleNamespace(load_approved=load_approved)
                        if path == M.PLAN_SCRIPT else original_load(path, name))

    def approve(text="Instrumental ambient piano", **settings):
        proposal = root / f"proposal-{len(manifests)}.md"
        proposal.write_text(text + json.dumps(settings))
        sha = hashlib.sha256(proposal.read_bytes()).hexdigest()
        manifest = {"version": 1, "kind": "generate", "form": {"theme_detail": text},
                    "settings": {"engine": M.LOCAL_ENGINE, "duration_seconds": 1, "seed": 0, "max_calls": 3, **settings},
                    "artifact_text": text, "artifact_sha256": hashlib.sha256(text.encode()).hexdigest(),
                    "approval_sha256": sha, "approved_plan": str(proposal)}
        manifests[str(proposal)] = manifest
        return {"approved_plan": str(proposal), "approval_sha256": sha}

    return SimpleNamespace(root=root, job=root / "job", runtime=runtime, client=client, handle=handle,
                           factory=factory, approve=approve, manifests=manifests)


def call(rig, action="start", **args):
    return json.loads(M.generate({"action": action, "job_dir": str(rig.job), **args}))


def state(rig):
    return json.loads((rig.job / "state.json").read_text())


def start(rig, paid=False, **settings):
    approval = rig.approve(**({"engine": M.ENGINE, "max_usd": 1} if paid else {}), **settings)
    return call(rig, **approval, **({"paid_approved": True} if paid else {}))


def test_registration_scope_and_exact_dict_signature():
    for profile in ("default", "creator", "audio-creator", "video-creator"):
        ctx = SimpleNamespace(profile_name=profile, register_tool=Mock())
        M.register(ctx)
        assert ctx.register_tool.call_count == (2 if profile == "audio-creator" else 0)
        for record in ctx.register_tool.call_args_list:
            assert record.kwargs["toolset"] == "music_gen"
            handler = record.kwargs["handler"]
            signature = inspect.signature(handler)
            assert list(signature.parameters) == ["args", "kwargs"]
            assert signature.parameters["kwargs"].kind == inspect.Parameter.VAR_KEYWORD
    assert set(M.GENERATE_SCHEMA["parameters"]["properties"]) == {
        "action", "job_dir", "approved_plan", "approval_sha256", "paid_approved"}


def test_catalog_no_spend_and_runtime_follows_readiness(rig):
    result = json.loads(M.catalog({}))
    assert result["default_engine"] == M.LOCAL_ENGINE
    assert result["engines"][1]["estimated_usd_per_audio"] == 0.0376
    assert all(e["seed"] and not e["instrumental_guaranteed"] for e in result["engines"])
    rig.runtime.render_music.assert_not_called()
    rig.client.submit.assert_not_called()
    rig.runtime.status.return_value["available"] = False
    assert not json.loads(M.catalog({}))["engines"][0]["available"]
    assert not json.loads(M.catalog({"text": "piano"}))["success"]


@pytest.mark.parametrize("missing", ["approved_plan", "approval_sha256", "both"])
def test_missing_approval_refused_before_spend(rig, missing):
    args = rig.approve()
    if missing == "both":
        args = {}
    else:
        del args[missing]
    assert not call(rig, **args)["success"]
    assert not rig.job.exists()
    rig.runtime.render_music.assert_not_called()
    rig.factory.assert_not_called()


@pytest.mark.parametrize("settings", [
    {"engine": "fal:elevenlabs-sfx-v2"}, {"engine": "auto"},
    {"duration_seconds": 0.5}, {"duration_seconds": 60.001}, {"duration_seconds": True},
    {"duration_seconds": float("nan")}, {"duration_seconds": float("inf")},
    {"seed": -1}, {"seed": 2**32}, {"seed": True}, {"max_calls": 0}, {"max_calls": 9},
    {"max_calls": 1.5}, {"max_calls": True}, {"loop": False}, {"output_format": "wav"},
    {"prompt_influence": 0.3}, {"enable_prompt_expansion": False}, {"max_usd": 0},
    {"engine": M.ENGINE, "max_usd": None}, {"engine": M.ENGINE, "max_usd": 0.0376},
    {"engine": M.ENGINE, "max_usd": float("nan")}, {"engine": M.ENGINE, "max_usd": float("inf")},
    {"engine": M.ENGINE, "max_usd": True}, {"engine": M.ENGINE, "max_usd": 11},
])
def test_invalid_settings_refused_before_spend(rig, settings):
    assert not call(rig, **rig.approve(**settings))["success"]
    assert not rig.job.exists()
    rig.runtime.render_music.assert_not_called()
    rig.factory.assert_not_called()


@pytest.mark.parametrize("text", ["", "   ", "x" * 451])
def test_invalid_prompt_refused(rig, text):
    assert not call(rig, **rig.approve(text))["success"]
    rig.runtime.render_music.assert_not_called()


@pytest.mark.parametrize("field", ["text", "duration_seconds", "engine", "seed", "loop", "max_calls", "max_usd"])
def test_arbitrary_tool_controls_refused(rig, field):
    assert not call(rig, **rig.approve(), **{field: None})["success"]
    rig.runtime.render_music.assert_not_called()


@pytest.mark.parametrize("value", [True, False, None])
def test_local_rejects_paid_flag_even_false(rig, value):
    assert not call(rig, **rig.approve(), paid_approved=value)["success"]
    assert not rig.job.exists()


@pytest.mark.parametrize("value", [False, None, 1])
def test_fal_requires_explicit_true(rig, value):
    approval = rig.approve(engine=M.ENGINE, max_usd=1)
    assert not call(rig, **approval, paid_approved=value)["success"]
    rig.factory.assert_not_called()


def test_changed_approval_rejected_before_start_and_next(rig):
    approval = rig.approve()
    Path(approval["approved_plan"]).write_text("changed")
    assert not call(rig, **approval)["success"]
    assert not rig.job.exists()
    approval = rig.approve()
    assert call(rig, **approval)["success"]
    Path(approval["approved_plan"]).write_text("changed")
    assert not call(rig, "next")["success"]
    assert len(state(rig)["attempts"]) == 1
    assert rig.runtime.render_music.call_count == 1


def test_local_success_seed_wrap_and_resume_without_approval(rig):
    assert start(rig, seed=2**32 - 1)["seed"] == 2**32 - 1
    result = call(rig, "next")
    assert result["seed"] == 0 and result["calls"] == 2 and result["estimated_usd"] == 0
    assert result["status"] == "raw-needs-qa" and result["perceptual_qa"] == "unverified"
    for path in rig.manifests:
        Path(path).unlink()
    assert call(rig, "resume")["success"]
    assert rig.runtime.render_music.call_count == 2
    rig.factory.assert_not_called()


def test_reapproval_changes_prompt_not_budget_and_default_next_reuses_correction(rig):
    assert start(rig)["success"]
    assert call(rig, "next", **rig.approve("Instrumental quiet strings"))["success"]
    assert call(rig, "next")["success"]
    ledger = state(rig)["attempts"]
    assert [a["payload"]["seed"] for a in ledger] == [0, 1, 2]
    assert ledger[0]["approved"] != ledger[1]["approved"]
    assert ledger[1]["approved"] == ledger[2]["approved"]
    assert ledger[2]["payload"]["text"] == "Instrumental quiet strings"


@pytest.mark.parametrize("settings", [{"engine": M.ENGINE, "max_usd": 1}, {"duration_seconds": 2},
                                      {"seed": 1}, {"max_calls": 8}])
def test_reapproval_cannot_change_settings(rig, settings):
    assert start(rig)["success"]
    assert not call(rig, "next", **rig.approve(**settings))["success"]
    assert len(state(rig)["attempts"]) == 1


def test_paid_reapproval_cannot_change_cap(rig):
    start(rig, paid=True)
    complete(rig)
    assert call(rig, "resume")["success"]
    assert not call(rig, "next", **rig.approve(engine=M.ENGINE, max_usd=2))["success"]
    assert rig.client.submit.call_count == 1


@pytest.mark.parametrize("action", ["next", "resume"])
@pytest.mark.parametrize("args", [{"paid_approved": True}, {"engine": M.ENGINE}, {"max_calls": 8},
                                 {"approved_plan": "/missing"}])
def test_resume_next_reject_direct_changes(rig, action, args):
    assert start(rig)["success"]
    assert not call(rig, action, **args)["success"]
    assert rig.runtime.render_music.call_count == 1


def test_resume_rejects_even_paired_approval(rig):
    assert start(rig)["success"]
    assert not call(rig, "resume", **rig.approve())["success"]


def test_frozen_state_tamper_rejected(rig):
    assert start(rig)["success"]
    data = state(rig)
    data["frozen"]["settings"]["max_calls"] = 8
    (rig.job / "state.json").write_text(json.dumps(data))
    assert not call(rig, "resume")["success"]
    assert not call(rig, "next")["success"]


def test_local_failure_counts_and_cannot_forge_success(rig):
    render = rig.runtime.render_music.side_effect

    def fail(payload, bundle):
        render(payload, bundle)
        raise RuntimeError("secret provider diagnostic")

    rig.runtime.render_music.side_effect = fail
    result = start(rig, max_calls=2)
    assert not result["success"] and "secret provider" not in result["error"]
    assert state(rig)["attempts"][0]["status"] == "failed"
    assert not call(rig, "resume")["success"]
    assert not call(rig, "next")["success"]
    assert len(state(rig)["attempts"]) == 2
    assert not call(rig, "next")["success"]
    assert rig.runtime.render_music.call_count == 2


@pytest.mark.parametrize("file", ["raw.wav", "take.json", "inference.log"])
def test_checkpointed_local_evidence_tamper_rejected(rig, file):
    assert start(rig)["success"]
    output = rig.job / "take-01" / file
    if file == "take.json":
        receipt = json.loads(output.read_text())
        receipt["generated_at"] = "forged"
        output.write_text(json.dumps(receipt))
    else:
        with output.open("ab") as stream:
            stream.write(b"tampered")
    assert not call(rig, "resume")["success"]
    assert rig.runtime.render_music.call_count == 1


def test_local_pending_then_lost_never_reexecutes_or_adopts_unsealed_bundle(rig):
    assert start(rig)["success"]
    data = state(rig)
    data["attempts"][0].update(status="running")
    del data["attempts"][0]["evidence"]
    M._save(rig.job, data)
    rig.runtime.is_busy.return_value = True
    assert call(rig, "resume")["status"] == "pending"
    rig.runtime.is_busy.return_value = False
    assert not call(rig, "resume")["success"]
    assert state(rig)["attempts"][0]["status"] == "failed"
    assert rig.runtime.render_music.call_count == 1


def test_local_runtime_changed_blocks_next_but_resume_recovers(rig):
    assert start(rig)["success"]
    rig.runtime.status.return_value["fingerprint"]["runtime_identity"] = "changed"
    assert not call(rig, "next")["success"]
    assert call(rig, "resume")["success"]


def complete(rig):
    payload = state(rig)["attempts"][-1]["payload"]
    rig.handle.status.return_value = fal_client.Completed(logs=[], metrics={})
    rig.handle.get.return_value = {"prompt": payload["prompt"], "seed": payload["seed"],
                                   "audio": {"url": "https://test.fal.media/audio.wav"}}


def test_paid_counted_before_submit_exact_payload_pending_resume_and_seed(rig):
    def submit(model, arguments):
        ledger = state(rig)["attempts"]
        assert ledger[-1]["status"] == "submission-unknown"
        assert ledger[-1]["payload"] == arguments
        assert model == "fal-ai/stable-audio-3/medium/text-to-audio"
        return rig.handle

    rig.client.submit.side_effect = submit
    result = start(rig, paid=True)
    assert result["status"] == "pending" and result["estimated_usd"] == 0.0376
    payload = state(rig)["attempts"][0]["payload"]
    assert payload == {"prompt": "Instrumental ambient piano", "duration": 1, "seed": 0,
                       "output_format": "wav", "enable_prompt_expansion": False, "enable_safety_checker": True,
                       "sync_mode": False, "num_inference_steps": 8, "guidance_scale": 1, "negative_prompt": ""}
    assert state(rig)["attempts"][0]["request_id"] == "fake-id"
    assert not call(rig, "next")["success"]
    assert call(rig, "resume")["status"] == "pending"
    complete(rig)
    for proposal in rig.manifests:
        Path(proposal).unlink()
    result = call(rig, "resume")
    assert result["status"] == "raw-needs-qa"
    assert Path(result["take_json"]).exists()
    assert call(rig, "resume")["success"]
    assert rig.client.submit.call_count == 1
    assert not call(rig, "next")["success"]
    rig.runtime.render_music.assert_not_called()


def test_paid_unknown_submission_never_retries_or_skips(rig):
    rig.client.submit.side_effect = ValueError("secret signed URL")
    result = start(rig, paid=True)
    assert not result["success"] and "secret signed" not in result["error"]
    assert state(rig)["attempts"][0]["status"] == "submission-unknown"
    assert not call(rig, "resume")["success"]
    assert not call(rig, "next", **rig.approve(engine=M.ENGINE, max_usd=1))["success"]
    assert rig.client.submit.call_count == 1


@pytest.mark.parametrize("status", [400, 422, 401, 429, 500])
def test_paid_rejection_counts_but_transport_failure_stays_pending(rig, status):
    from fal_client.client import FalClientHTTPError
    start(rig, paid=True)
    complete(rig)
    rig.handle.get.side_effect = FalClientHTTPError(
        "private provider message", status_code=status, response_headers={}, response=None)
    result = call(rig, "resume")
    assert not result["success"] and "private provider" not in result["error"]
    assert state(rig)["attempts"][0]["status"] == ("failed" if status in (400, 422) else "pending")
    assert rig.client.submit.call_count == 1


@pytest.mark.parametrize("field,value", [("seed", 1), ("seed", True), ("prompt", "expanded prompt")])
def test_fal_result_must_match_approved_payload(rig, field, value):
    start(rig, paid=True)
    complete(rig)
    rig.handle.get.return_value[field] = value
    result = call(rig, "resume")
    assert not result["success"] and result["failure_reason"] == "invalid-output"
    assert state(rig)["attempts"][0]["status"] == "failed"
    assert call(rig, "resume")["failure_reason"] == "invalid-output"
    M._download.assert_not_called()
    rig.handle.status.return_value = fal_client.Queued(position=0)
    assert call(rig, "next")["calls"] == 2


def test_no_forged_fal_success_from_preexisting_bundle(rig):
    start(rig, paid=True)
    complete(rig)
    bundle = rig.job / "take-01"
    bundle.mkdir()
    wav(bundle / "raw.wav")
    assert not call(rig, "resume")["success"]
    M._download.assert_not_called()
    assert rig.client.submit.call_count == 1


def test_existing_job_and_next_output_protected(rig):
    assert start(rig)["success"]
    before = (rig.job / "state.json").read_bytes()
    assert not start(rig)["success"]
    assert (rig.job / "state.json").read_bytes() == before
    (rig.job / "take-02").mkdir()
    assert not call(rig, "next")["success"]
    assert rig.runtime.render_music.call_count == 1


@pytest.mark.parametrize("target", ["job", "state", "lock", "bundle", "raw", "receipt", "log"])
def test_symlink_paths_refused(rig, target):
    if target == "job":
        rig.job.symlink_to(rig.root, target_is_directory=True)
        assert not start(rig)["success"]
        return
    assert start(rig)["success"]
    paths = {"state": rig.job / "state.json", "lock": rig.job / ".lock", "bundle": rig.job / "take-01",
             "raw": rig.job / "take-01/raw.wav", "receipt": rig.job / "take-01/take.json",
             "log": rig.job / "take-01/inference.log"}
    path = paths[target]
    saved = path.with_name(path.name + ".saved")
    path.rename(saved)
    path.symlink_to(saved, target_is_directory=saved.is_dir())
    assert not call(rig, "resume")["success"]


def test_protected_path_rejected_before_approval(rig, monkeypatch):
    from agent import file_safety
    monkeypatch.setattr(file_safety, "is_write_denied", lambda path: True)
    assert not start(rig)["success"]
    assert not rig.job.exists()


def test_secret_only_from_scope(monkeypatch):
    from agent import secret_scope
    spec = importlib.util.spec_from_file_location("music_secret_test", PLUGIN)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    getter = Mock(return_value=" scoped ")
    monkeypatch.setattr(secret_scope, "get_secret", getter)
    monkeypatch.setenv("FAL_KEY", "must-not-use-process-env")
    assert module._key() == "scoped"
    getter.assert_called_once_with("FAL_KEY", "")
    getter.return_value = ""
    assert module._key() == ""


@pytest.mark.parametrize("status", [500, 429, 302])
def test_actual_client_does_one_post_without_redirect_or_sdk_retry(monkeypatch, status):
    import requests
    spec = importlib.util.spec_from_file_location("music_client_test", PLUGIN)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    monkeypatch.setattr(module, "_key", lambda: "fake-scoped-key")
    post = Mock(return_value=SimpleNamespace(status_code=status))
    monkeypatch.setattr(requests, "post", post)
    with pytest.raises(RuntimeError):
        module._client().submit(module.MODEL, {"prompt": "piano"})
    assert post.call_count == 1
    assert post.call_args.kwargs["allow_redirects"] is False
    assert post.call_args.args == ("https://queue.fal.run/" + module.MODEL,)


@pytest.mark.parametrize("url", ["http://test.fal.media/a", "https://fal.media.evil/a", "https://localhost/a",
                               "https://user@test.fal.media/a", "https://test.fal.media:8443/a"])
def test_download_rejects_arbitrary_urls(tmp_path, url):
    with pytest.raises(ValueError):
        M._download(url, tmp_path / "audio")


def test_download_byte_bound_and_no_redirects(tmp_path, monkeypatch):
    import requests
    response = Mock()
    response.__enter__ = Mock(return_value=response)
    response.__exit__ = Mock(return_value=False)
    response.status_code = 200
    response.iter_content.return_value = [b"x" * (M.MAX_BYTES + 1)]
    get = Mock(return_value=response)
    monkeypatch.setattr(requests, "get", get)
    with pytest.raises(ValueError, match="32 MiB"):
        M._download("https://test.fal.media/a", tmp_path / "audio")
    assert get.call_args.kwargs["allow_redirects"] is False


@pytest.mark.parametrize("method", ["status", "get"])
def test_retrieval_errors_are_redacted_and_never_resubmit(rig, method):
    start(rig, paid=True)
    complete(rig)
    getattr(rig.handle, method).side_effect = ValueError("private signed URL or key")
    result = call(rig, "resume")
    assert not result["success"] and "private signed" not in result["error"]
    assert state(rig)["attempts"][0]["status"] == "pending"
    assert rig.client.submit.call_count == 1


def test_fal_failure_next_keeps_cost_seed_and_grant(rig):
    from fal_client.client import FalClientHTTPError
    start(rig, paid=True, max_calls=2)
    complete(rig)
    rig.handle.get.side_effect = FalClientHTTPError(
        "rejected", status_code=422, response_headers={}, response=None)
    assert not call(rig, "resume")["success"]
    rig.handle.status.return_value = fal_client.Queued(position=0)
    rig.handle.get.side_effect = None
    result = call(rig, "next")
    assert result["calls"] == 2 and result["seed"] == 1
    assert result["estimated_usd"] == 0.0752
    complete(rig)
    assert call(rig, "resume")["success"]
    assert not call(rig, "next")["success"]
    assert rig.client.submit.call_count == 2


@pytest.mark.parametrize("field,value", [("kind", "create"), ("version", 2),
                                        ("artifact_sha256", "a" * 64)])
def test_invalid_approved_manifest_refused_before_spend(rig, field, value):
    approval = rig.approve()
    rig.manifests[approval["approved_plan"]][field] = value
    assert not call(rig, **approval)["success"]
    rig.factory.assert_not_called()
    rig.runtime.render_music.assert_not_called()


def test_approved_artifact_changed_before_next_is_refused(rig):
    assert start(rig)["success"]
    manifest = next(iter(rig.manifests.values()))
    manifest["artifact_text"] = "tampered prompt"
    assert not call(rig, "next")["success"]
    assert len(state(rig)["attempts"]) == 1


def test_local_unavailable_never_falls_back(rig):
    rig.runtime.status.return_value["available"] = False
    assert not start(rig)["success"]
    rig.factory.assert_not_called()
    assert not rig.job.exists()


def test_next_requires_both_approval_fields(rig):
    assert start(rig)["success"]
    approval = rig.approve("Instrumental guitar")
    assert not call(rig, "next", approval_sha256=approval["approval_sha256"])["success"]
    assert not call(rig, "next", approved_plan=approval["approved_plan"])["success"]
    assert rig.runtime.render_music.call_count == 1


@pytest.mark.parametrize("seconds", [30, 60])
def test_local_music_lengths_reach_explicit_runtime_entry(rig, seconds):
    result = start(rig, duration_seconds=seconds)
    assert result["success"]
    assert rig.runtime.render_music.call_args.args[0]["duration_seconds"] == seconds
    assert call(rig, "resume")["success"]


def test_bad_receipt_from_runtime_never_becomes_success(rig):
    render = rig.runtime.render_music.side_effect

    def forged(payload, bundle):
        result = render(payload, bundle)
        result["receipt"]["model"]["runtime_fingerprint"] = "other-runtime"
        (bundle / "take.json").write_text(json.dumps(result["receipt"]))
        return result

    rig.runtime.render_music.side_effect = forged
    assert not start(rig)["success"]
    assert state(rig)["attempts"][0]["status"] == "failed"
    assert not call(rig, "resume")["success"]


def test_fal_checkpoint_tamper_rejected_without_network(rig):
    start(rig, paid=True)
    complete(rig)
    assert call(rig, "resume")["success"]
    response = rig.job / "take-01/response.json"
    response.write_text("{}")
    calls = rig.handle.get.call_count
    assert not call(rig, "resume")["success"]
    assert rig.handle.get.call_count == calls


def test_job_lock_serializes_across_calls(rig):
    import fcntl
    assert start(rig)["success"]
    with (rig.job / ".lock").open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        assert not call(rig, "next")["success"]
    assert rig.runtime.render_music.call_count == 1


@pytest.mark.parametrize("field", ["raw.wav", "take.json", "inference.log"])
def test_nonregular_local_evidence_refused_without_blocking(rig, field):
    import os
    assert start(rig)["success"]
    path = rig.job / "take-01" / field
    path.unlink()
    os.mkfifo(path)
    assert not call(rig, "resume")["success"]


def test_traversal_and_symlink_ancestor_refused(rig):
    rig.job = rig.root / "parent" / ".." / "job"
    assert not start(rig)["success"]
    link = rig.root / "link"
    link.symlink_to(rig.root, target_is_directory=True)
    rig.job = link / "job"
    assert not start(rig)["success"]
    rig.runtime.render_music.assert_not_called()


@pytest.mark.parametrize("request_id", ["", "bad/id", "https://evil", "x" * 101, None])
def test_bad_request_id_keeps_submission_unknown(rig, request_id):
    rig.handle.request_id = request_id
    assert not start(rig, paid=True)["success"]
    assert state(rig)["attempts"][0]["status"] == "submission-unknown"
    assert not call(rig, "next")["success"]
    assert rig.client.submit.call_count == 1


def test_local_default_is_two_plus_one_attempts(rig):
    approval = rig.approve()
    del rig.manifests[approval["approved_plan"]]["settings"]["max_calls"]
    assert call(rig, **approval)["max_calls"] == 3
    assert call(rig, "next")["calls"] == 2
    assert call(rig, "next")["calls"] == 3
    assert not call(rig, "next")["success"]
    assert rig.runtime.render_music.call_count == 3


def test_busy_before_start_does_not_create_job_or_consume_grant(rig):
    approval = rig.approve()
    rig.runtime.is_busy.return_value = True
    result = call(rig, **approval)
    assert not result["success"] and result["error"] == M.BUSY_MESSAGE
    assert not rig.job.exists()
    rig.runtime.render_music.assert_not_called()
    rig.runtime.is_busy.return_value = False
    assert call(rig, **approval)["calls"] == 1


def test_busy_before_next_keeps_exact_ledger_and_grant(rig):
    assert start(rig)["success"]
    before = (rig.job / "state.json").read_bytes()
    rig.runtime.is_busy.return_value = True
    result = call(rig, "next")
    assert not result["success"] and result["error"] == M.BUSY_MESSAGE
    assert (rig.job / "state.json").read_bytes() == before
    assert rig.runtime.render_music.call_count == 1
    rig.runtime.is_busy.return_value = False
    assert call(rig, "next")["calls"] == 2


def test_busy_after_start_directory_creation_leaves_empty_resumable_grant(rig):
    rig.runtime.is_busy.side_effect = [False, True]
    result = start(rig)
    assert result["error"] == M.BUSY_MESSAGE
    assert state(rig)["attempts"] == []
    rig.runtime.render_music.assert_not_called()
    rig.runtime.is_busy.side_effect = None
    assert call(rig, "next")["calls"] == 1


@pytest.mark.parametrize("prefix,reason", [
    ("busy: another install or render holds the runtime lock", "busy"),
    ("runtime not ready: drift detected", "not-ready"),
    ("generation exceeded 180s timeout; killed owned process group; stderr tail:", "timeout"),
    ("generation subprocess exited 1; stderr tail:", "subprocess"),
    ("generation completed but raw.wav was not written", "invalid-output"),
    ("raw.wav exceeds 33554432 bytes", "invalid-output"),
    ("unexpected WAV format: channels=1", "invalid-output"),
    ("WAV truncated: read 4 PCM bytes", "invalid-output"),
    ("unexpected frame count 100", "invalid-output"),
    ("unrecognized runtime error", "runtime-error"),
])
def test_invoked_local_failure_persists_fixed_classification_and_never_stderr(rig, prefix, reason):
    def fail(payload, out):
        assert len(state(rig)["attempts"]) == 1
        assert state(rig)["attempts"][0]["status"] == "running"
        raise rig.runtime.RenderError(prefix + "\nprivate-secret-value")

    rig.runtime.render_music.side_effect = fail
    result = start(rig)
    assert not result["success"] and result["failure_reason"] == reason
    assert "attempt counted" in result["error"] and "private-secret" not in result["error"]
    assert state(rig)["attempts"][0]["failure_reason"] == reason
    assert state(rig)["attempts"][0]["status"] == "failed"
    assert "private-secret" not in (rig.job / "state.json").read_text()
    assert call(rig, "resume")["failure_reason"] == reason
    assert rig.runtime.render_music.call_count == 1
    rig.runtime.render_music.side_effect = RuntimeError("different private diagnostic")
    assert not call(rig, "next")["success"]
    assert len(state(rig)["attempts"]) == 2


def test_real_runtime_timeout_is_classified_and_counted(rig, monkeypatch):
    import subprocess
    runtime = M._load(M.HERMES / "scripts/stable_audio3.py", "music_timeout_runtime")
    root = rig.root / "fake-runtime"
    root.mkdir()
    monkeypatch.setattr(runtime, "DEFAULT_ROOT", root)
    monkeypatch.setattr(runtime, "status", rig.runtime.status)
    process = Mock(pid=4242)
    process.wait.side_effect = [subprocess.TimeoutExpired("fake-generation", 180), 0]
    monkeypatch.setattr(runtime, "_POPEN", Mock(return_value=process))
    kill = Mock()
    monkeypatch.setattr(runtime.os, "killpg", kill)
    monkeypatch.setattr(M, "_runtime", lambda: runtime)
    result = start(rig, duration_seconds=60)
    assert result["failure_reason"] == "timeout"
    assert state(rig)["attempts"][0]["failure_reason"] == "timeout"
    assert len(state(rig)["attempts"]) == 1
    assert call(rig, "resume")["failure_reason"] == "timeout"
    assert runtime._POPEN.call_count == 1
    kill.assert_called_once_with(4242, runtime.signal.SIGKILL)


@pytest.mark.parametrize("seconds,extra,accepted", [(60, 1, True), (60, -1, True), (60, 2, False),
                                                   (30, 1, True), (30, -2, False)])
def test_local_requested_duration_one_frame_tolerance(rig, seconds, extra, accepted):
    render = rig.runtime.render_music.side_effect

    def altered(payload, bundle):
        result = render(payload, bundle)
        pcm = wav(bundle / "raw.wav", seconds + extra / 44100)
        result["receipt"]["raw_wav"].update(
            sha256_file=hashlib.sha256((bundle / "raw.wav").read_bytes()).hexdigest(),
            sha256_pcm=hashlib.sha256(pcm).hexdigest(), frames=len(pcm) // 4)
        (bundle / "take.json").write_text(json.dumps(result["receipt"]))
        return result

    rig.runtime.render_music.side_effect = altered
    result = start(rig, duration_seconds=seconds)
    assert result["success"] is accepted
    assert call(rig, "resume")["success"] is accepted
    if not accepted:
        assert result["failure_reason"] == "invalid-output"
    assert rig.runtime.render_music.call_count == 1


@pytest.mark.parametrize("requested,actual", [(60, 60.25), (60, 59.75), (30, 30.25), (30, 29.75)])
def test_fal_requested_duration_quarter_second_tolerance(rig, requested, actual):
    start(rig, paid=True, duration_seconds=requested)
    complete(rig)
    M._download.side_effect = lambda url, output: wav(output, actual)
    result = call(rig, "resume")
    assert result["success"] and result["status"] == "raw-needs-qa"
    assert call(rig, "resume")["success"]
    assert M._download.call_count == 1
    assert json.loads(M.catalog({}))["engines"][1]["duration_seconds"] == [1, 60]


@pytest.mark.parametrize("requested,actual", [(60, 60.251), (30, 29.749), (30, 30.251), (30, 1), (1, 60)])
def test_invalid_fal_duration_terminal_preserves_candidate_and_next_grant(rig, requested, actual):
    start(rig, paid=True, duration_seconds=requested)
    complete(rig)
    M._download.side_effect = lambda url, output: wav(output, actual)
    result = call(rig, "resume")
    assert not result["success"] and result["failure_reason"] == "invalid-output"
    attempt = state(rig)["attempts"][0]
    assert attempt["status"] == "failed" and attempt["failure_reason"] == "invalid-output"
    assert "evidence" not in attempt
    candidate = Path(attempt["diagnostic_candidate"])
    assert {p.name for p in candidate.iterdir()} == {"raw.wav", "response.json", "take.json"}
    receipt = json.loads((candidate / "take.json").read_text())
    assert receipt["request"] == attempt["payload"] and receipt["validation"] == "unverified"
    assert receipt["raw_wav"]["sha256_file"] == hashlib.sha256((candidate / "raw.wav").read_bytes()).hexdigest()
    assert not (rig.job / "take-01").exists()
    before = {p: p.read_bytes() for p in candidate.iterdir()}
    assert call(rig, "resume")["failure_reason"] == "invalid-output"
    assert call(rig, "resume")["failure_reason"] == "invalid-output"
    assert M._download.call_count == 1 and rig.handle.get.call_count == 1
    rig.handle.status.return_value = fal_client.Queued(position=0)
    result = call(rig, "next")
    assert result["calls"] == 2 and result["estimated_usd"] == 0.0752 and result["seed"] == 1
    assert {p: p.read_bytes() for p in candidate.iterdir()} == before
    complete(rig)
    M._download.side_effect = lambda url, output: wav(output, requested)
    assert call(rig, "resume")["status"] == "raw-needs-qa"


@pytest.mark.parametrize("damage", ["invalid-wav", "truncated", "missing-seed", "missing-prompt"])
def test_invalid_completed_fal_result_is_terminal_not_a_retry_wedge(rig, damage):
    start(rig, paid=True)
    complete(rig)
    if damage.startswith("missing-"):
        del rig.handle.get.return_value[damage.removeprefix("missing-")]
    elif damage == "invalid-wav":
        M._download.side_effect = lambda url, out: out.write_bytes(b"not a WAV")
    else:
        def truncated(url, out):
            wav(out)
            out.write_bytes(out.read_bytes()[:-4])
        M._download.side_effect = truncated
    assert call(rig, "resume")["failure_reason"] == "invalid-output"
    downloads = M._download.call_count
    assert state(rig)["attempts"][0]["status"] == "failed"
    assert call(rig, "resume")["failure_reason"] == "invalid-output"
    assert M._download.call_count == downloads and rig.handle.get.call_count == 1


def test_diagnostic_candidate_cannot_be_adopted_as_success(rig):
    start(rig, paid=True)
    complete(rig)
    M._download.side_effect = lambda url, out: wav(out, 2)
    assert call(rig, "resume")["failure_reason"] == "invalid-output"
    candidate = Path(state(rig)["attempts"][0]["diagnostic_candidate"])
    candidate.rename(rig.job / "take-01")
    assert call(rig, "resume")["failure_reason"] == "invalid-output"
    assert M._download.call_count == 1


def test_real_approval_helper_integration_and_changed_artifact_before_next(rig, monkeypatch):
    """Use the parent's real helper, keeping only the generation boundary fake."""
    spec = importlib.util.spec_from_file_location("music_real_approval_plugin", PLUGIN)
    plugin = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(plugin)
    monkeypatch.setattr(plugin, "_runtime", lambda: rig.runtime)
    monkeypatch.setattr(plugin, "_client", Mock(side_effect=AssertionError("no paid work")))
    plan = plugin._load(plugin.PLAN_SCRIPT, "music_real_approval_plan")
    form = rig.root / "form.json"
    arrangement = rig.root / "arrangement.md"
    prompt = rig.root / "prompt.txt"
    form.write_text(json.dumps({"what_for": "unit test", "theme": "quiet", "style": "ambient", "duration": 1}))
    arrangement.write_text("Quiet instrumental piano throughout, with a resolved ending.")
    prompt.write_text("Instrumental ambient piano, no vocals.")
    proposal = plan.propose("generate", form, arrangement, rig.root / "approved", prompt_file=prompt)
    result = json.loads(plugin.generate({"action": "start", "job_dir": str(rig.job),
                                        "approved_plan": proposal["approved_plan"],
                                        "approval_sha256": proposal["approval_sha256"]}))
    assert result["success"] and result["max_calls"] == 3
    assert rig.runtime.render_music.call_args.args[0]["text"] == prompt.read_text()
    Path(proposal["artifact"]).write_text("Instrumental strings, no vocals.")
    result = json.loads(plugin.generate({"action": "next", "job_dir": str(rig.job)}))
    assert not result["success"] and "changed" in result["error"]
    assert len(state(rig)["attempts"]) == 1
    Path(proposal["approved_plan"]).unlink()
    assert json.loads(plugin.generate({"action": "resume", "job_dir": str(rig.job)}))["success"]
    assert rig.runtime.render_music.call_count == 1
