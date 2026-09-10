from __future__ import annotations

import hashlib
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import fal_client
import pytest


PLUGIN = Path(__file__).resolve().parents[1] / "__init__.py"
SPEC = importlib.util.spec_from_file_location("sfx_gen", PLUGIN)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class FakeRuntime:
    """Controlled runtime with real evidence files, but no weights or inference."""

    def __init__(self):
        self.status = mock.Mock(return_value={
            "available": True,
            "reason": "ready",
            "fingerprint": {"runtime_identity": "fake-medium-runtime-v1"},
        })
        self.render = mock.Mock(side_effect=self._render)
        self.is_busy = mock.Mock(return_value=False)

    def _render(self, payload, bundle):
        bundle.mkdir()
        raw = bundle / "raw.wav"
        take = bundle / "take.json"
        raw.write_bytes(b"fake-raw-audio:" + str(payload["seed"]).encode("ascii"))
        receipt = {
            "engine": MODULE.LOCAL_ENGINE,
            "request": dict(payload),
            "model": {"runtime_fingerprint": self.status.return_value["fingerprint"]["runtime_identity"]},
            "raw_wav": {"sha256_file": hashlib.sha256(raw.read_bytes()).hexdigest()},
        }
        take.write_text(json.dumps(receipt))
        return {"raw": str(raw), "take_json": str(take)}


@pytest.fixture(autouse=True)
def runtime():
    # Covers catalog/registration tests too: never inspect installed weights.
    fake = FakeRuntime()
    with mock.patch.object(MODULE, "_runtime", return_value=fake):
        yield fake


@pytest.fixture
def local_job(tmp_path):
    with mock.patch.object(MODULE, "_client") as client, mock.patch.object(
        MODULE, "_key"
    ) as key, mock.patch.object(MODULE, "_download") as download:
        yield tmp_path.resolve() / "job"
        client.assert_not_called()
        key.assert_not_called()
        download.assert_not_called()


def _local_start(job_dir, **overrides):
    args = {
        "action": "start", "job_dir": str(job_dir),
        "engine": MODULE.LOCAL_ENGINE,
        "text": "a gentle breeze through dry leaves", "duration_seconds": 2.0,
    }
    args.update(overrides)
    return args


def _valid_start(job_dir, **overrides) -> dict:
    args = {
        "action": "start",
        "job_dir": str(job_dir),
        "engine": MODULE.ENGINE,
        "text": "a gentle breeze through dry leaves",
        "duration_seconds": 2.0,
        "loop": False,
        "prompt_influence": 0.3,
        "paid_approved": True,
        "max_calls": 3,
        "max_usd": 1.0,
    }
    args.update(overrides)
    return args


class CatalogTest(unittest.TestCase):
    """Local availability follows runtime readiness; fal follows key presence only."""

    def _engines(self, payload: dict) -> dict:
        return {e["id"]: e for e in payload["engines"]}

    def test_local_engine_follows_runtime_readiness(self) -> None:
        for available in (False, True):
            with self.subTest(available=available), mock.patch.object(MODULE, "_key", return_value="present"):
                runtime = MODULE._runtime()
                runtime.status.return_value["available"] = available
                runtime.status.return_value["reason"] = "ready" if available else "weights missing"
                engines = self._engines(json.loads(MODULE.catalog()))
                local = engines[MODULE.LOCAL_ENGINE]
                self.assertEqual("local:stable-audio-3-medium", local["id"])
                self.assertEqual(available, local["available"])
                self.assertEqual(runtime.status.return_value["reason"], local["reason"])
                self.assertEqual(runtime.status.return_value["fingerprint"], local["runtime"])
                self.assertEqual("free", local["cost"])
                self.assertTrue(local["seed"])
                self.assertFalse(local["loop"])
                self.assertFalse(local["prompt_influence"])
                runtime.render.assert_not_called()

    def test_runtime_status_failure_is_unavailable(self) -> None:
        MODULE._runtime().status.side_effect = RuntimeError("readiness failed")
        with mock.patch.object(MODULE, "_key", return_value=""):
            engines = self._engines(json.loads(MODULE.catalog()))
        self.assertFalse(engines[MODULE.LOCAL_ENGINE]["available"])
        self.assertIn("readiness check failed", engines[MODULE.LOCAL_ENGINE]["reason"])

    def test_fal_engine_follows_key_presence(self) -> None:
        with mock.patch.object(MODULE, "_key", return_value=""):
            engines = self._engines(json.loads(MODULE.catalog()))
        self.assertFalse(engines[MODULE.ENGINE]["available"])
        with mock.patch.object(MODULE, "_key", return_value="secret"):
            engines = self._engines(json.loads(MODULE.catalog()))
        self.assertTrue(engines[MODULE.ENGINE]["available"])

    def test_key_lookup_failure_reads_as_unavailable_not_a_crash(self) -> None:
        with mock.patch.object(MODULE, "_key", side_effect=RuntimeError("no scope")):
            engines = self._engines(json.loads(MODULE.catalog()))
        self.assertFalse(engines[MODULE.ENGINE]["available"])


class ValidationTest(unittest.TestCase):
    """Every refusal below must happen before any network client is built or job_dir is touched."""

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        # Resolved: on macOS /var (a common TMPDIR ancestor) is itself a
        # symlink to /private/var, which would otherwise trip the plugin's
        # own symlinked-ancestor guard on every job_dir built from it.
        self.parent = Path(self._tmp.name).resolve()
        patcher = mock.patch.object(MODULE, "_client")
        self.client = patcher.start()
        self.addCleanup(patcher.stop)

    def job_dir(self, name: str = "job") -> Path:
        return self.parent / name

    def assert_refused(self, args: dict, expected_snippet: str) -> dict:
        result = json.loads(MODULE.generate(args))
        self.assertFalse(result["success"])
        self.assertIn(expected_snippet, result["error"])
        self.assertFalse(Path(args["job_dir"]).exists())
        self.client.assert_not_called()
        return result

    def test_removed_local_engine_is_unknown(self) -> None:
        self.assert_refused(
            _valid_start(self.job_dir(), engine="local:stable-audio"), "unknown engine",
        )

    def test_omitted_engine_does_not_implicitly_use_fal_controls(self) -> None:
        args = _valid_start(self.job_dir())
        del args["engine"]
        self.assert_refused(args, "prompt_influence")
        del args["prompt_influence"]
        self.assert_refused(args, "paid_approved/max_usd")
        MODULE._runtime().status.assert_not_called()
        MODULE._runtime().render.assert_not_called()

    def test_missing_paid_approval_is_refused(self) -> None:
        args = _valid_start(self.job_dir())
        del args["paid_approved"]
        self.assert_refused(args, "paid approval")

    def test_false_paid_approval_is_refused(self) -> None:
        self.assert_refused(_valid_start(self.job_dir(), paid_approved=False), "paid approval")

    def test_duration_wrong_type_is_refused(self) -> None:
        for bad in ("2", None, [2]):
            with self.subTest(duration=bad):
                self.assert_refused(
                    _valid_start(self.job_dir(f"job-{bad!r}"), duration_seconds=bad),
                    "duration_seconds",
                )

    def test_duration_bool_is_refused(self) -> None:
        """A bool is an int subclass; it must not silently pass as 1.0/0.0 seconds."""
        self.assert_refused(_valid_start(self.job_dir(), duration_seconds=True), "duration_seconds")

    def test_duration_nonfinite_is_refused(self) -> None:
        for bad in (float("nan"), float("inf"), float("-inf")):
            with self.subTest(duration=bad):
                self.assert_refused(
                    _valid_start(self.job_dir(f"job-{bad}"), duration_seconds=bad),
                    "duration_seconds",
                )

    def test_duration_out_of_range_is_refused(self) -> None:
        for bad in (0.1, 22, 30):
            with self.subTest(duration=bad):
                self.assert_refused(
                    _valid_start(self.job_dir(f"job-{bad}"), duration_seconds=bad),
                    "duration_seconds",
                )

    def test_max_usd_wrong_type_bool_nonfinite(self) -> None:
        for bad in ("1", True, float("nan")):
            with self.subTest(max_usd=bad):
                self.assert_refused(
                    _valid_start(self.job_dir(f"job-{bad!r}"), max_usd=bad), "max_usd",
                )

    def test_max_usd_below_the_estimate_is_refused(self) -> None:
        # 3 calls * 2s * $0.002/s = $0.012, well above a $0.001 cap.
        self.assert_refused(_valid_start(self.job_dir(), max_usd=0.001), "max_usd")

    def test_max_calls_wrong_type_bool_or_out_of_range(self) -> None:
        for bad in (1.5, True, "3", 0, 9):
            with self.subTest(max_calls=bad):
                self.assert_refused(
                    _valid_start(self.job_dir(f"job-{bad!r}"), max_calls=bad), "max_calls",
                )

    def test_loop_wrong_type_is_refused(self) -> None:
        self.assert_refused(_valid_start(self.job_dir(), loop="yes"), "loop")

    def test_seed_is_an_unknown_control(self) -> None:
        """fal SFX v2 has no seed; a model that sends one must be refused, not silently dropped."""
        args = _valid_start(self.job_dir())
        args["seed"] = 7
        self.assert_refused(args, "unknown controls")

    def test_unrecognized_key_is_an_unknown_control(self) -> None:
        args = _valid_start(self.job_dir())
        args["bogus"] = 1
        self.assert_refused(args, "unknown controls")

    def test_invalid_action_is_refused(self) -> None:
        self.assert_refused(_valid_start(self.job_dir(), action="cancel"), "action")

    def test_resume_of_a_nonexistent_job_is_refused(self) -> None:
        result = self.assert_refused(
            {"action": "resume", "job_dir": str(self.job_dir())}, "does not exist",
        )
        self.assertFalse(result["success"])


@pytest.mark.parametrize("explicit_engine", [False, True])
def test_local_defaults_to_medium_seed_zero_four_free_takes(local_job, runtime, explicit_engine):
    args = _local_start(local_job)
    if not explicit_engine:
        del args["engine"]
    first = json.loads(MODULE.generate(args))
    assert first["success"], first
    assert first["engine"] == "local:stable-audio-3-medium"
    assert first["seed"] == 0
    assert first["seed_supported"] is True
    assert first["max_calls"] == 4
    assert first["estimated_usd"] == 0
    state = json.loads((local_job / "state.json").read_text())
    assert state["version"] == 2
    assert state["runtime"] == runtime.status.return_value["fingerprint"]["runtime_identity"]
    assert state["payload"] == {
        "text": args["text"], "duration_seconds": 2.0, "seed": 0,
    }
    for seed in range(1, 4):
        result = json.loads(MODULE.generate({"action": "next", "job_dir": str(local_job)}))
        assert result["success"], result
        assert result["seed"] == seed
        assert result["calls"] == seed + 1
        assert result["estimated_usd"] == 0
    exhausted = json.loads(MODULE.generate({"action": "next", "job_dir": str(local_job)}))
    assert exhausted["success"] is False
    assert "budget exhausted" in exhausted["error"]
    assert runtime.render.call_count == 4


@pytest.mark.parametrize("base, next_seed", [(42, 43), (2**32 - 1, 0)])
def test_local_next_increments_seed_and_preserves_frozen_controls(local_job, runtime, base, next_seed):
    first = json.loads(MODULE.generate(_local_start(local_job, seed=base, max_calls=2, loop=False)))
    assert first["success"], first
    assert first["seed"] == base
    raw = Path(first["raw"])
    take = Path(first["take_json"])
    assert raw == local_job / "take-01" / "raw.wav"
    assert take == local_job / "take-01" / "take.json"
    original = (raw.read_bytes(), take.read_bytes())
    receipt = json.loads(take.read_text())
    assert receipt["request"]["seed"] == base
    assert receipt["raw_wav"]["sha256_file"] == hashlib.sha256(original[0]).hexdigest()
    second = json.loads(MODULE.generate({
        "action": "next", "job_dir": str(local_job), "text": "one softer rustle",
    }))
    assert second["success"], second
    assert second["status"] == "raw-needs-qa"
    assert second["seed"] == next_seed
    assert second["calls"] == second["max_calls"] == 2
    assert second["estimated_usd"] == 0
    assert second["runtime"] == first["runtime"]
    assert Path(second["raw"]) == local_job / "take-02" / "raw.wav"
    assert runtime.render.call_args.args == ({
        "text": "one softer rustle", "duration_seconds": 2.0, "seed": next_seed,
    }, local_job / "take-02")
    assert (raw.read_bytes(), take.read_bytes()) == original
    state = json.loads((local_job / "state.json").read_text())
    assert state["payload"]["seed"] == base
    assert [a["status"] for a in state["attempts"]] == ["downloaded", "downloaded"]


@pytest.mark.parametrize("explicit_engine", [False, True])
def test_local_unavailable_never_falls_back_or_creates_job(local_job, runtime, explicit_engine):
    runtime.status.return_value = {"available": False, "reason": "weights missing"}
    args = _local_start(local_job)
    if not explicit_engine:
        del args["engine"]
    result = json.loads(MODULE.generate(args))
    assert result["success"] is False
    assert "weights missing" in result["error"]
    assert "no paid fallback" in result["error"]
    assert not local_job.exists()
    runtime.render.assert_not_called()


@pytest.mark.parametrize("controls, error", [
    ({"loop": True}, "loop"),
    ({"loop": 0}, "loop"),
    ({"loop": "false"}, "loop"),
    ({"loop": None}, "loop"),
    ({"prompt_influence": 0}, "prompt_influence"),
    ({"prompt_influence": None}, "prompt_influence"),
    ({"paid_approved": True}, "paid_approved"),
    ({"paid_approved": False}, "paid_approved"),
    ({"max_usd": 0}, "max_usd"),
    *[({"seed": value}, "seed") for value in (
        -1, 2**32, True, False, 1.0, "42", None, float("nan"), float("inf"),
    )],
    *[({"duration_seconds": value}, "duration_seconds") for value in (
        0, 0.49, 22, True, False, "2", None, float("nan"), float("inf"), float("-inf"),
    )],
    *[({"max_calls": value}, "max_calls") for value in (
        0, 9, True, False, 1.0, "4", None, float("nan"),
    )],
    *[({"text": value}, "text") for value in ("", " ", "x" * 451, None, 42)],
])
def test_local_invalid_controls_refused_before_readiness_or_artifacts(local_job, runtime, controls, error):
    result = json.loads(MODULE.generate(_local_start(local_job, **controls)))
    assert result["success"] is False
    assert error in result["error"]
    assert not local_job.exists()
    runtime.status.assert_not_called()
    runtime.render.assert_not_called()


@pytest.mark.parametrize("duration", [0.5, 21.5])
def test_local_duration_boundaries_are_supported(local_job, runtime, duration):
    result = json.loads(MODULE.generate(_local_start(local_job, duration_seconds=duration)))
    assert result["success"], result
    assert runtime.render.call_args.args[0]["duration_seconds"] == duration


@pytest.mark.parametrize("engine", ["local:stable-audio", "local:unknown", "local:stable-audio-3-large"])
def test_unknown_local_engine_is_rejected_without_fallback(local_job, runtime, engine):
    result = json.loads(MODULE.generate(_local_start(local_job, engine=engine)))
    assert result["success"] is False
    assert "unknown engine" in result["error"]
    assert not local_job.exists()
    runtime.status.assert_not_called()
    runtime.render.assert_not_called()


@pytest.mark.parametrize("error", [TimeoutError("local timeout after 300s"), RuntimeError("MLX OOM: out of memory")])
def test_runtime_failure_diagnostics_not_redacted_and_failed_next_is_bounded(local_job, runtime, error):
    runtime.render.side_effect = error
    first = json.loads(MODULE.generate(_local_start(local_job, seed=42, max_calls=2)))
    assert first["success"] is False
    assert str(error) in first["error"]
    assert "attempt counted" in first["error"]
    state = json.loads((local_job / "state.json").read_text())
    assert len(state["attempts"]) == 1
    assert state["attempts"][0]["status"] == "failed"
    resume = json.loads(MODULE.generate({"action": "resume", "job_dir": str(local_job)}))
    assert resume["success"] is False
    assert runtime.render.call_count == 1
    runtime.render.side_effect = runtime._render
    second = json.loads(MODULE.generate({"action": "next", "job_dir": str(local_job)}))
    assert second["success"], second
    assert second["seed"] == 43
    assert second["calls"] == 2
    exhausted = json.loads(MODULE.generate({"action": "next", "job_dir": str(local_job)}))
    assert exhausted["success"] is False
    assert "budget exhausted" in exhausted["error"]
    assert runtime.render.call_count == 2


@pytest.mark.parametrize("action", ["resume", "next"])
@pytest.mark.parametrize("controls", [
    {"engine": MODULE.LOCAL_ENGINE}, {"engine": MODULE.ENGINE}, {"duration_seconds": 3},
    {"seed": 7}, {"max_calls": 8}, {"loop": False}, {"prompt_influence": 0.3},
    {"paid_approved": True}, {"max_usd": 1},
])
def test_local_frozen_controls_cannot_be_overridden(local_job, runtime, action, controls):
    first = json.loads(MODULE.generate(_local_start(local_job)))
    assert first["success"], first
    before = (local_job / "state.json").read_bytes()
    runtime.status.reset_mock()
    result = json.loads(MODULE.generate({"action": action, "job_dir": str(local_job), **controls}))
    assert result["success"] is False
    assert "frozen" in result["error"]
    assert (local_job / "state.json").read_bytes() == before
    assert runtime.render.call_count == 1
    runtime.status.assert_not_called()


def test_local_resume_reuses_identical_evidence_without_status_or_render(local_job, runtime):
    first = json.loads(MODULE.generate(_local_start(local_job)))
    assert first["success"], first
    before = {p: p.read_bytes() for p in (Path(first["raw"]), Path(first["take_json"]))}
    runtime.status.reset_mock()
    runtime.status.side_effect = AssertionError("resume must not check readiness")
    runtime.render.reset_mock()
    runtime.render.side_effect = AssertionError("resume must not generate")
    for _ in range(2):
        result = json.loads(MODULE.generate({"action": "resume", "job_dir": str(local_job)}))
        assert result == first
        assert {p: p.read_bytes() for p in before} == before
    runtime.status.assert_not_called()
    runtime.render.assert_not_called()
    runtime.is_busy.assert_not_called()


def test_local_start_never_overwrites_an_existing_job(local_job, runtime):
    first = json.loads(MODULE.generate(_local_start(local_job)))
    assert first["success"], first
    before = {p: p.read_bytes() for p in local_job.rglob("*") if p.is_file()}
    result = json.loads(MODULE.generate(_local_start(local_job, seed=99)))
    assert result["success"] is False
    assert {p: p.read_bytes() for p in local_job.rglob("*") if p.is_file()} == before
    assert runtime.render.call_count == 1


@pytest.mark.parametrize("change", ["identity", "unavailable"])
def test_local_runtime_change_refused_before_another_attempt(local_job, runtime, change):
    first = json.loads(MODULE.generate(_local_start(local_job)))
    assert first["success"], first
    before = (local_job / "state.json").read_bytes()
    if change == "identity":
        runtime.status.return_value["fingerprint"]["runtime_identity"] = "different-runtime"
    else:
        runtime.status.return_value = {"available": False, "reason": "not ready"}
    result = json.loads(MODULE.generate({"action": "next", "job_dir": str(local_job)}))
    assert result["success"] is False
    assert "runtime changed/unavailable" in result["error"]
    assert (local_job / "state.json").read_bytes() == before
    assert runtime.render.call_count == 1
    assert not (local_job / "take-02").exists()


@pytest.mark.parametrize("damage", [
    "raw", "engine", "request", "runtime", "hash", "invalid-json",
    "missing-raw", "missing-receipt", "symlink-raw", "symlink-receipt", "symlink-bundle",
    "oversized-raw", "oversized-receipt",
])
def test_local_resume_refuses_invalid_evidence_without_generation(local_job, runtime, damage):
    first = json.loads(MODULE.generate(_local_start(local_job)))
    assert first["success"], first
    raw, take = Path(first["raw"]), Path(first["take_json"])
    if damage == "raw":
        raw.write_bytes(b"tampered")
    elif damage in ("engine", "request", "runtime", "hash"):
        receipt = json.loads(take.read_text())
        if damage == "engine":
            receipt["engine"] = MODULE.ENGINE
        elif damage == "request":
            receipt["request"]["seed"] += 1
        elif damage == "runtime":
            receipt["model"]["runtime_fingerprint"] = "other-runtime"
        else:
            receipt["raw_wav"]["sha256_file"] = "0" * 64
        take.write_text(json.dumps(receipt))
    elif damage == "invalid-json":
        take.write_text("{invalid")
    elif damage.startswith("missing-"):
        (raw if damage == "missing-raw" else take).unlink()
    elif damage.startswith("symlink-"):
        target = {"symlink-raw": raw, "symlink-receipt": take, "symlink-bundle": raw.parent}[damage]
        outside = local_job.parent / "outside-evidence"
        target.rename(outside)
        target.symlink_to(outside)
    else:
        target, limit = (raw, MODULE.MAX_BYTES) if damage == "oversized-raw" else (take, 1024 * 1024)
        with target.open("r+b") as stream:
            stream.truncate(limit + 1)
    before = (local_job / "state.json").read_bytes()
    runtime.status.reset_mock()
    result = json.loads(MODULE.generate({"action": "resume", "job_dir": str(local_job)}))
    assert result["success"] is False
    if damage.startswith("symlink-"):
        assert "symlinked local result" in result["error"]
    elif damage.startswith("oversized-"):
        assert "evidence bounds" in result["error"]
    elif damage in ("raw", "engine", "request", "runtime", "hash"):
        assert "does not match the frozen attempt" in result["error"]
    assert (local_job / "state.json").read_bytes() == before
    assert runtime.render.call_count == 1
    runtime.status.assert_not_called()
    runtime.is_busy.assert_not_called()


def test_local_interruption_busy_pending_then_failed_then_next_counts_two(local_job, runtime):
    runtime.render.side_effect = KeyboardInterrupt
    with pytest.raises(KeyboardInterrupt):
        MODULE.generate(_local_start(local_job, max_calls=2))
    state = json.loads((local_job / "state.json").read_text())
    assert len(state["attempts"]) == 1
    assert state["attempts"][0]["status"] == "running"
    assert not (local_job / "take-01").exists()
    runtime.status.reset_mock()
    runtime.is_busy.return_value = True
    pending = json.loads(MODULE.generate({"action": "resume", "job_dir": str(local_job)}))
    assert pending["success"], pending
    assert pending["status"] == "pending"
    assert pending["calls"] == 1
    assert pending["max_calls"] == 2
    blocked = json.loads(MODULE.generate({"action": "next", "job_dir": str(local_job)}))
    assert blocked["success"] is False
    assert "unresolved" in blocked["error"]
    runtime.is_busy.return_value = False
    lost = json.loads(MODULE.generate({"action": "resume", "job_dir": str(local_job)}))
    assert lost["success"] is False
    assert "lost after interruption; still counted" in lost["error"]
    state = json.loads((local_job / "state.json").read_text())
    assert len(state["attempts"]) == 1
    assert state["attempts"][0]["status"] == "failed"
    assert runtime.render.call_count == 1
    assert runtime.is_busy.call_count == 2
    runtime.status.assert_not_called()
    runtime.render.side_effect = runtime._render
    second = json.loads(MODULE.generate({"action": "next", "job_dir": str(local_job)}))
    assert second["success"], second
    assert second["calls"] == 2
    assert second["seed"] == 1
    assert runtime.render.call_count == 2


def test_local_interruption_with_completed_receipt_resumes_without_runtime_work(local_job, runtime):
    def render_then_interrupt(payload, bundle):
        runtime._render(payload, bundle)
        raise KeyboardInterrupt

    runtime.render.side_effect = render_then_interrupt
    with pytest.raises(KeyboardInterrupt):
        MODULE.generate(_local_start(local_job, seed=42))
    state = json.loads((local_job / "state.json").read_text())
    assert state["attempts"][0]["status"] == "running"
    before = {p: p.read_bytes() for p in (local_job / "take-01").iterdir()}
    runtime.status.reset_mock()
    runtime.status.side_effect = AssertionError("resume needs no readiness")
    result = json.loads(MODULE.generate({"action": "resume", "job_dir": str(local_job)}))
    assert result["success"], result
    assert result["status"] == "raw-needs-qa"
    assert result["calls"] == 1
    assert result["seed"] == 42
    assert {p: p.read_bytes() for p in before} == before
    state = json.loads((local_job / "state.json").read_text())
    assert state["attempts"][0]["status"] == "downloaded"
    assert runtime.render.call_count == 1
    runtime.status.assert_not_called()
    runtime.is_busy.assert_not_called()


class _StubHandle:
    """A duck-typed stand-in for fal_client.SyncRequestHandle."""

    def __init__(self, request_id: str, status_sequence, result=None) -> None:
        self.request_id = request_id
        self._status_sequence = list(status_sequence)
        self.result = result
        self.status_calls = 0

    def status(self, with_logs: bool = False):
        self.status_calls += 1
        return self._status_sequence.pop(0)

    def get(self):
        return self.result


class _StubClient:
    """Records submit/get_handle calls; a queued outcome may be a handle or an exception."""

    def __init__(self) -> None:
        self.submit_calls: list[dict] = []
        self.get_handle_calls: list[tuple] = []
        self._handles: dict[str, _StubHandle] = {}
        self._next = None

    def queue_submit(self, outcome) -> None:
        self._next = outcome

    def submit(self, model, arguments):
        self.submit_calls.append({"model": model, "arguments": arguments})
        outcome = self._next
        self._next = None
        if isinstance(outcome, Exception):
            raise outcome
        self._handles[outcome.request_id] = outcome
        return outcome

    def get_handle(self, model, request_id):
        self.get_handle_calls.append((model, request_id))
        return self._handles[request_id]


class HappyPathTest(unittest.TestCase):
    """start/next/resume lifecycle against a stubbed fal client, real temp job_dir."""

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.parent = Path(self._tmp.name).resolve()
        self.client = _StubClient()
        self.downloads: list[str] = []

        def fake_download(url, output):
            self.downloads.append(url)
            output.write_bytes(b"fake-mp3-bytes")

        client_patcher = mock.patch.object(MODULE, "_client", lambda: self.client)
        download_patcher = mock.patch.object(MODULE, "_download", fake_download)
        client_patcher.start()
        download_patcher.start()
        self.addCleanup(client_patcher.stop)
        self.addCleanup(download_patcher.stop)

    def job_dir(self) -> Path:
        return self.parent / "job"

    def state(self) -> dict:
        return json.loads((self.job_dir() / "state.json").read_text())

    def test_completed_rejection_counts_and_allows_corrective(self):
        from fal_client.client import FalClientHTTPError
        handle = _StubHandle("rejected", [fal_client.Completed(logs=[], metrics={})])
        self.client.queue_submit(handle)
        error = FalClientHTTPError("rejected", 422, {}, None)
        with mock.patch.object(handle, "get", side_effect=error):
            result = json.loads(MODULE.generate(_valid_start(self.job_dir())))
        self.assertFalse(result["success"])
        self.assertEqual("failed", self.state()["attempts"][0]["status"])
        retry = _StubHandle("corrective", [fal_client.Queued(position=0)])
        self.client.queue_submit(retry)
        result = json.loads(MODULE.generate({"action": "next", "job_dir": str(self.job_dir()), "text": "one gentle click"}))
        self.assertEqual("pending", result["status"])
        self.assertEqual(2, result["calls"])

    def test_completed_transport_error_stays_resumable(self):
        handle = _StubHandle("transport", [fal_client.Completed(logs=[], metrics={})])
        self.client.queue_submit(handle)
        with mock.patch.object(handle, "get", side_effect=TimeoutError):
            json.loads(MODULE.generate(_valid_start(self.job_dir())))
        self.assertEqual("pending", self.state()["attempts"][0]["status"])
        result = json.loads(MODULE.generate({"action": "next", "job_dir": str(self.job_dir())}))
        self.assertFalse(result["success"])
        self.assertEqual(1, len(self.client.submit_calls))

    def resolve(self, request_id: str = "req-1") -> dict:
        """Advance the named attempt's handle to Completed and resume it."""
        handle = self.client._handles[request_id]
        handle._status_sequence.append(fal_client.Completed(logs=[], metrics={}))
        handle.result = {"audio": {"url": "https://v3.fal.media/files/take.mp3"}}
        return json.loads(MODULE.generate({"action": "resume", "job_dir": str(self.job_dir())}))

    def test_start_returns_pending_without_downloading(self) -> None:
        self.client.queue_submit(_StubHandle("req-1", [fal_client.Queued(position=0)]))
        result = json.loads(MODULE.generate(_valid_start(self.job_dir())))
        self.assertTrue(result["success"])
        self.assertEqual("pending", result["status"])
        self.assertEqual(1, len(self.client.submit_calls))
        self.assertEqual([], self.downloads)
        self.assertEqual("pending", self.state()["attempts"][-1]["status"])

    def test_resume_downloads_once_then_repeats_without_resubmitting(self) -> None:
        self.client.queue_submit(_StubHandle("req-1", [fal_client.Queued(position=0)]))
        json.loads(MODULE.generate(_valid_start(self.job_dir())))

        result = self.resolve()
        self.assertTrue(result["success"])
        self.assertEqual("raw-needs-qa", result["status"])
        self.assertTrue(Path(result["raw"]).exists())
        self.assertEqual(1, len(self.downloads))
        get_handle_calls_after_resolve = len(self.client.get_handle_calls)

        repeat = json.loads(MODULE.generate({"action": "resume", "job_dir": str(self.job_dir())}))
        self.assertTrue(repeat["success"])
        self.assertEqual(result["raw"], repeat["raw"])
        self.assertEqual(1, len(self.downloads))
        self.assertEqual(1, len(self.client.submit_calls))
        self.assertEqual(get_handle_calls_after_resolve, len(self.client.get_handle_calls))

    def test_next_preserves_frozen_duration_and_budget_with_corrective_text(self) -> None:
        self.client.queue_submit(_StubHandle("req-1", [fal_client.Queued(position=0)]))
        json.loads(MODULE.generate(_valid_start(self.job_dir())))
        self.resolve()

        self.client.queue_submit(_StubHandle("req-2", [fal_client.Queued(position=0)]))
        result = json.loads(MODULE.generate({
            "action": "next", "job_dir": str(self.job_dir()), "text": "now with rustling leaves",
        }))
        self.assertTrue(result["success"])
        second_payload = self.client.submit_calls[-1]["arguments"]
        self.assertEqual("now with rustling leaves", second_payload["text"])
        self.assertEqual(2.0, second_payload["duration_seconds"])
        self.assertEqual(False, second_payload["loop"])
        self.assertEqual(0.3, second_payload["prompt_influence"])

    def test_next_cannot_change_frozen_controls(self) -> None:
        self.client.queue_submit(_StubHandle("req-1", [fal_client.Queued(position=0)]))
        json.loads(MODULE.generate(_valid_start(self.job_dir())))
        self.resolve()

        result = json.loads(MODULE.generate({
            "action": "next", "job_dir": str(self.job_dir()), "duration_seconds": 5,
        }))
        self.assertFalse(result["success"])
        self.assertIn("frozen", result["error"])
        self.assertEqual(1, len(self.client.submit_calls))

    def test_max_calls_bounds_attempts(self) -> None:
        self.client.queue_submit(_StubHandle("req-1", [fal_client.Queued(position=0)]))
        json.loads(MODULE.generate(_valid_start(self.job_dir(), max_calls=1)))
        self.resolve()

        result = json.loads(MODULE.generate({
            "action": "next", "job_dir": str(self.job_dir()), "text": "again",
        }))
        self.assertFalse(result["success"])
        self.assertIn("budget exhausted", result["error"])
        self.assertEqual(1, len(self.client.submit_calls))

    def test_start_never_overwrites_an_existing_job(self) -> None:
        self.client.queue_submit(_StubHandle("req-1", [fal_client.Queued(position=0)]))
        json.loads(MODULE.generate(_valid_start(self.job_dir())))
        before = self.state()

        self.client.queue_submit(_StubHandle("req-2", [fal_client.Queued(position=0)]))
        result = json.loads(MODULE.generate(_valid_start(self.job_dir())))
        self.assertFalse(result["success"])
        self.assertEqual(1, len(self.client.submit_calls))
        self.assertEqual(before, self.state())

    def test_ambiguous_submit_consumes_one_attempt_and_blocks_resubmission(self) -> None:
        self.client.queue_submit(RuntimeError("connection reset mid-flight"))
        result = json.loads(MODULE.generate(_valid_start(self.job_dir())))
        self.assertFalse(result["success"])
        state = self.state()
        self.assertEqual(1, len(state["attempts"]))
        self.assertEqual("submission-unknown", state["attempts"][-1]["status"])
        self.assertEqual(1, len(self.client.submit_calls))

        resumed = json.loads(MODULE.generate({"action": "resume", "job_dir": str(self.job_dir())}))
        self.assertFalse(resumed["success"])
        self.assertIn("no automatic resubmit", resumed["error"])
        self.assertEqual(1, len(self.client.submit_calls))

        nexted = json.loads(MODULE.generate({
            "action": "next", "job_dir": str(self.job_dir()), "text": "retry",
        }))
        self.assertFalse(nexted["success"])
        self.assertIn("resume it", nexted["error"])
        self.assertEqual(1, len(self.client.submit_calls))


class SubmissionTest(unittest.TestCase):
    def test_paid_post_does_not_use_sdk_retry_loop(self):
        import requests
        with mock.patch.object(MODULE, "_key", return_value="test-scoped-key"), mock.patch("requests.post", side_effect=requests.Timeout) as post:
            client = MODULE._client()
            with self.assertRaises(requests.Timeout):
                client.submit(MODULE.MODEL, {"text": "one click"})
        self.assertEqual(1, post.call_count)
        self.assertEqual(False, post.call_args.kwargs["allow_redirects"])
        self.assertEqual("Key test-scoped-key", post.call_args.kwargs["headers"]["Authorization"])

    def test_submit_uses_returned_id_for_retrieval(self):
        response = mock.Mock(status_code=200)
        response.json.return_value = {"request_id": "request-123"}
        with mock.patch.object(MODULE, "_key", return_value="test-scoped-key"), mock.patch("requests.post", return_value=response) as post:
            client = MODULE._client()
            handle = client.submit(MODULE.MODEL, {"text": "one click"})
        self.assertEqual("request-123", handle.request_id)
        self.assertEqual(1, post.call_count)

    def test_http_failure_does_not_retry_or_follow_redirects(self):
        for status in (302, 429, 500, 503):
            with self.subTest(status=status), mock.patch.object(MODULE, "_key", return_value="test-scoped-key"), mock.patch("requests.post", return_value=mock.Mock(status_code=status)) as post:
                with self.assertRaises(RuntimeError):
                    MODULE._client().submit(MODULE.MODEL, {})
                self.assertEqual(1, post.call_count)


class SecretScopeTest(unittest.TestCase):
    """No process-environment fallback: a raising scope must read as unavailable/refused, not crash."""

    def test_catalog_treats_a_raising_scope_as_unavailable(self) -> None:
        with mock.patch("agent.secret_scope.get_secret", side_effect=RuntimeError("no scope")):
            payload = json.loads(MODULE.catalog())
        engines = {e["id"]: e for e in payload["engines"]}
        self.assertFalse(engines[MODULE.ENGINE]["available"])

    def test_generate_creates_no_job_when_the_secret_scope_raises(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            job_dir = Path(tmp).resolve() / "job"
            with mock.patch("agent.secret_scope.get_secret", side_effect=RuntimeError("no scope")):
                result = json.loads(MODULE.generate(_valid_start(job_dir, max_calls=1)))
            self.assertFalse(result["success"])
            self.assertFalse(job_dir.exists())


class PathSafetyTest(unittest.TestCase):
    """job_dir validation: absolute, no traversal, not protected, no symlinked ancestor."""

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.parent = Path(self._tmp.name).resolve()

    def test_relative_path_is_refused(self) -> None:
        with self.assertRaises(ValueError):
            MODULE._path("relative/job")

    def test_traversal_is_refused(self) -> None:
        with self.assertRaises(ValueError):
            MODULE._path(str(self.parent / ".." / "job"))

    def test_protected_path_is_refused(self) -> None:
        job_dir = self.parent / "job"
        with mock.patch("agent.file_safety.is_write_denied", return_value=True):
            with self.assertRaises(ValueError):
                MODULE._path(str(job_dir))

    def test_symlinked_ancestor_is_refused(self) -> None:
        real_dir = self.parent / "real"
        real_dir.mkdir()
        link = self.parent / "link"
        link.symlink_to(real_dir)
        with self.assertRaises(ValueError):
            MODULE._path(str(link / "job"))

    def test_ordinary_real_path_is_accepted(self) -> None:
        job_dir = self.parent / "job"
        self.assertEqual(job_dir.resolve(), MODULE._path(str(job_dir)).resolve())


class DownloadTest(unittest.TestCase):
    """Only fal's result CDN, over plain HTTPS, no redirects, no embedded credentials."""

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.output = Path(self._tmp.name) / "take.mp3"

    def _response(self, status_code: int = 200, chunks=(b"abc",)):
        response = mock.MagicMock()
        response.__enter__.return_value = response
        response.__exit__.return_value = False
        response.status_code = status_code
        response.iter_content.return_value = list(chunks)
        return response

    def test_non_https_scheme_is_refused(self) -> None:
        with mock.patch("requests.get") as get:
            with self.assertRaises(ValueError):
                MODULE._download("http://v3.fal.media/x.mp3", self.output)
            get.assert_not_called()

    def test_disallowed_host_is_refused(self) -> None:
        with mock.patch("requests.get") as get:
            with self.assertRaises(ValueError):
                MODULE._download("https://evil.example.com/x.mp3", self.output)
            get.assert_not_called()

    def test_non_default_port_is_refused(self) -> None:
        with mock.patch("requests.get") as get:
            with self.assertRaises(ValueError):
                MODULE._download("https://v3.fal.media:8443/x.mp3", self.output)
            get.assert_not_called()

    def test_embedded_credentials_are_refused(self) -> None:
        with mock.patch("requests.get") as get:
            with self.assertRaises(ValueError):
                MODULE._download("https://user:pass@v3.fal.media/x.mp3", self.output)
            get.assert_not_called()

    def test_redirects_are_disabled_for_the_result_fetch(self) -> None:
        response = self._response()
        with mock.patch("requests.get", return_value=response) as get:
            MODULE._download("https://v3.fal.media/x.mp3", self.output)
        self.assertEqual(False, get.call_args.kwargs["allow_redirects"])
        self.assertTrue(self.output.exists())

    def test_non_200_status_is_refused(self) -> None:
        response = self._response(status_code=302)
        with mock.patch("requests.get", return_value=response):
            with self.assertRaises(ValueError) as ctx:
                MODULE._download("https://v3.fal.media/x.mp3", self.output)
        self.assertIn("302", str(ctx.exception))
        self.assertFalse(self.output.exists())

    def test_oversized_result_is_refused(self) -> None:
        response = self._response(chunks=(b"x" * 8,))
        with mock.patch.object(MODULE, "MAX_BYTES", 4):
            with mock.patch("requests.get", return_value=response):
                with self.assertRaises(ValueError) as ctx:
                    MODULE._download("https://v3.fal.media/x.mp3", self.output)
        self.assertIn("16 MiB", str(ctx.exception))

    def test_empty_result_is_refused(self) -> None:
        response = self._response(chunks=())
        with mock.patch("requests.get", return_value=response):
            with self.assertRaises(ValueError) as ctx:
                MODULE._download("https://v3.fal.media/x.mp3", self.output)
        self.assertIn("empty audio", str(ctx.exception))


class RegistrationTest(unittest.TestCase):
    """audio-creator only; handlers dispatch on a single positional dict, per Hermes' calling convention."""

    class FakeContext:
        def __init__(self, profile_name: str) -> None:
            self.profile_name = profile_name
            self.tools: list[str] = []
            self.toolsets: list[str] = []
            self.handlers: dict[str, object] = {}

        def register_tool(self, *, name: str, toolset: str, handler, **kwargs) -> None:
            self.tools.append(name)
            self.toolsets.append(toolset)
            self.handlers[name] = handler

    def test_registered_only_for_audio_creator(self) -> None:
        audio_creator = self.FakeContext("audio-creator")
        creator = self.FakeContext("creator")
        MODULE.register(audio_creator)
        MODULE.register(creator)
        self.assertEqual(["sfx_engines", "sfx_generate"], audio_creator.tools)
        self.assertEqual(["sfx_gen", "sfx_gen"], audio_creator.toolsets)
        self.assertEqual([], creator.tools)

    def test_unrelated_profile_is_denied(self) -> None:
        video_creator = self.FakeContext("video-creator")
        MODULE.register(video_creator)
        self.assertEqual([], video_creator.tools)

    def test_registered_handlers_dispatch_with_a_single_dict_argument(self) -> None:
        ctx = self.FakeContext("audio-creator")
        MODULE.register(ctx)
        catalog_payload = json.loads(ctx.handlers["sfx_engines"]({}))
        self.assertIn("engines", catalog_payload)
        generate_payload = json.loads(
            ctx.handlers["sfx_generate"]({"action": "bogus", "job_dir": "/tmp/does-not-matter"})
        )
        self.assertFalse(generate_payload["success"])


if __name__ == "__main__":
    unittest.main()
