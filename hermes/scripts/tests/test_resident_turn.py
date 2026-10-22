"""resident-turn.py: one resident turn through the gateway, with a stop the receipt confirms.

The gateway is a fake: scripted RPC answers and an event queue. What is under test is the
client's contract to resident-session.sh — the reply on stdout, ``session_id:`` /
``admission_id:`` on stderr, and the exit codes 0 / 1 / 124 / 125 / 143.
"""
import asyncio
import contextlib
import importlib.util
import os
import signal
import sys
import threading
import time
import unittest
from pathlib import Path
from unittest import mock

SCRIPT = Path(__file__).resolve().parents[2] / "profiles/assistant/scripts/resident-turn.py"
spec = importlib.util.spec_from_file_location("resident_turn", SCRIPT)
rt = importlib.util.module_from_spec(spec)
spec.loader.exec_module(rt)


class GatewayRPCError(ValueError):
    """Like the runtime's: ``str(exc)`` is the gateway's bounded reason code."""


class FakeGateway:
    """``rpc(method, **params)`` answers from ``answers``; ``events`` feeds ``message.complete``."""

    def __init__(self, answers, session_id="local-" + "a" * 64):
        self.answers = dict(answers)
        self.session_id = session_id
        self.calls = []
        self.events = asyncio.Queue()
        self.admission = "adm-1"

    async def rpc(self, method, _timeout=None, **params):
        self.calls.append((method, params))
        answer = self.answers[method]
        if callable(answer):
            answer = answer(params)
        if isinstance(answer, Exception):
            raise answer
        return answer

    def complete(self, status="complete", outcome="completed", text="the reply"):
        self.events.put_nowait({"method": "session.event", "params": {
            "session_id": self.session_id, "type": "message.complete", "admission_id": self.admission,
            "payload": {"status": status, "outcome": outcome, "text": text}}})

    def receipt(self, status, outcome=None, final=""):
        return {"status": status, "outcome": outcome, "result": {"final_response": final}}


def fake_modules(gateway):
    """The hermes_cli modules resident-turn imports, backed by ``gateway``."""
    @contextlib.asynccontextmanager
    async def connect_gateway():
        yield gateway
    client = type(sys)("hermes_cli.gateway_client")
    client.connect_gateway = connect_gateway
    client.GatewayRPCError = GatewayRPCError
    connection = type(sys)("hermes_cli.gateway_connection")
    connection.RESUME_GONE = frozenset({"not_found", "permission_denied", "profile_mismatch"})
    return {"hermes_cli": type(sys)("hermes_cli"), "hermes_cli.gateway_client": client,
            "hermes_cli.gateway_connection": connection}


class ResidentTurnTest(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(self.enterContext(__import__("tempfile").TemporaryDirectory()))
        self.prompt = self.tmp / "prompt.txt"
        self.prompt.write_text("do the thing", encoding="utf-8")
        self.enterContext(mock.patch.object(rt, "STOP_BUDGET", 4.0))  # 2 s of it is the close

    def run_turn(self, gateway, *args):
        out, err = __import__("io").StringIO(), __import__("io").StringIO()
        with mock.patch.dict(sys.modules, fake_modules(gateway)), \
                contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            rc = rt.main(["--profile", "writer", "--prompt-file", str(self.prompt), *args])
        return rc, out.getvalue(), err.getvalue()

    def gateway(self, receipt_status="terminal", receipt_outcome="interrupted", final="", stopped=None):
        """``stopped``: the receipt the admission settles to once the stop (interrupt / cancel) has
        been sent; before that it reads ``started``. Without it the receipt is fixed."""
        gw = FakeGateway({})
        stop_sent = []

        def receipt(params):
            if stopped is not None:
                return gw.receipt(*stopped) if stop_sent else gw.receipt("started")
            return gw.receipt(receipt_status, receipt_outcome, final)
        gw.answers = {
            "session.create": {"session_id": gw.session_id},
            "session.resume": {"session_id": gw.session_id, "execution_generation": 3},
            "prompt.submit": {"admission_id": gw.admission, "execution_generation": 3, "status": "queued"},
            "session.interrupt": lambda params: stop_sent.append("interrupt") or {},
            "prompt.receipt": receipt,
        }
        return gw

    def test_a_completed_turn_prints_its_reply_and_exits_0(self):
        gw = self.gateway()
        gw.complete()
        rc, out, err = self.run_turn(gw)
        self.assertEqual((rc, out), (0, "the reply"))
        self.assertIn(f"session_id: {gw.session_id}", err)
        self.assertIn("admission_id: adm-1", err)
        methods = [m for m, _ in gw.calls]
        self.assertEqual(methods, ["session.create", "prompt.submit"])
        self.assertTrue(gw.calls[1][1]["finite"])

    def test_resume_continues_the_given_session(self):
        gw = self.gateway()
        gw.complete()
        rc, _, _ = self.run_turn(gw, "--resume", gw.session_id)
        self.assertEqual(rc, 0)
        self.assertEqual(gw.calls[0], ("session.resume", {"session_id": gw.session_id, "omit_messages": True}))

    def test_a_gone_session_is_refused_before_anything_runs(self):
        gw = self.gateway()
        gw.answers["session.resume"] = GatewayRPCError("not_found")
        with self.assertRaises(SystemExit) as caught:
            self.run_turn(gw, "--resume", "local-" + "b" * 64)
        self.assertIn("is gone", str(caught.exception))
        self.assertEqual([m for m, _ in gw.calls], ["session.resume"])

    def test_a_turn_the_gateway_interrupted_exits_143(self):
        gw = self.gateway()
        gw.complete(status="interrupted", outcome="cancelled", text="")
        rc, out, _ = self.run_turn(gw)
        self.assertEqual((rc, out), (143, ""))

    def test_a_failed_turn_exits_1(self):
        gw = self.gateway()
        gw.complete(status="error", outcome="failed", text="")
        self.assertEqual(self.run_turn(gw)[0], 1)

    def test_a_signal_interrupts_the_turn_and_the_receipt_confirms_143(self):
        gw = self.gateway(stopped=("terminal", "interrupted", "partial"))
        timer = threading.Timer(0.3, lambda: os.kill(os.getpid(), signal.SIGTERM))
        self.addCleanup(timer.cancel)
        timer.start()
        rc, out, err = self.run_turn(gw)
        self.assertEqual((rc, out), (143, "partial"))
        self.assertIn(("session.interrupt", {"session_id": gw.session_id, "execution_generation": 3}), gw.calls)
        self.assertIn("signal received", err)

    def test_the_deadline_interrupts_the_turn_and_exits_124(self):
        gw = self.gateway(stopped=("terminal", "interrupted"))
        rc, _, err = self.run_turn(gw, "--deadline", str(time.time() + 0.3))
        self.assertEqual(rc, 124)
        self.assertIn("deadline reached", err)
        self.assertIn("session.interrupt", [m for m, _ in gw.calls])

    def test_a_stop_the_receipt_never_confirms_exits_125(self):
        gw = self.gateway(receipt_status="started", receipt_outcome=None)
        rc, _, err = self.run_turn(gw, "--deadline", str(time.time() + 0.2))
        self.assertEqual(rc, 125)
        self.assertIn("not confirmed", err)

    def test_a_turn_that_finished_before_the_stop_exits_0_with_its_reply(self):
        """The receipt is already terminal when the stop begins: nothing is interrupted."""
        gw = self.gateway(receipt_outcome="completed", final="done anyway")
        rc, out, err = self.run_turn(gw, "--deadline", str(time.time() + 0.2))
        self.assertEqual((rc, out), (0, "done anyway"))
        self.assertIn("completed before the stop", err)
        self.assertNotIn("session.interrupt", [m for m, _ in gw.calls])

    def test_a_gateway_lost_mid_turn_exits_125(self):
        gw = self.gateway()
        gw.events.put_nowait(ConnectionError("Gateway disconnected; turn outcome is unknown"))
        rc, _, err = self.run_turn(gw)
        self.assertEqual(rc, 125)
        self.assertIn("unknown", err)

    def test_a_gateway_lost_while_confirming_the_stop_exits_125_not_1(self):
        """Admitted, then the receipt poll dies: the turn may run on, so never "failed"."""
        gw = self.gateway()
        gw.answers["prompt.receipt"] = ConnectionError("Gateway disconnected")
        rc, _, err = self.run_turn(gw, "--deadline", str(time.time() + 0.2))
        self.assertEqual(rc, 125)
        self.assertIn("Gateway disconnected", err)

    def test_a_submit_refused_before_the_write_exits_1_as_nothing_ran(self):
        gw = self.gateway()
        gw.answers["prompt.submit"] = GatewayRPCError("queue_full")
        rc, _, err = self.run_turn(gw)
        self.assertEqual(rc, 1)
        self.assertIn("queue_full", err)

    def test_a_submit_that_failed_after_it_may_have_landed_exits_125(self):
        """storage_unavailable can follow the admission's commit (the owner's own list): unknown."""
        gw = self.gateway()
        gw.answers["prompt.submit"] = GatewayRPCError("storage_unavailable")
        self.assertEqual(self.run_turn(gw)[0], 125)
        gw.answers["prompt.submit"] = ConnectionError("Gateway disconnected")
        self.assertEqual(self.run_turn(gw)[0], 125)

    def test_a_queued_admission_is_retired_without_an_interrupt(self):
        gw = self.gateway()
        state = {"cancelled": False}

        def receipt(params):
            return gw.receipt("terminal", "cancelled") if state["cancelled"] else gw.receipt("queued")
        gw.answers["prompt.receipt"] = receipt
        gw.answers["prompt.cancel"] = lambda params: state.update(cancelled=True) or gw.receipt("terminal", "cancelled")
        rc, _, _ = self.run_turn(gw, "--deadline", str(time.time() + 0.2))
        self.assertEqual(rc, 124)
        methods = [m for m, _ in gw.calls]
        self.assertIn("prompt.cancel", methods)
        self.assertNotIn("session.interrupt", methods)

    def test_the_stop_fits_its_budget(self):
        """Every RPC of the stop is bounded by the budget's end, never by its own full timeout."""
        gw = self.gateway(receipt_status="started", receipt_outcome=None)
        timeouts = []
        real_rpc = gw.rpc

        async def rpc(method, _timeout=None, **params):
            timeouts.append((method, _timeout))
            return await real_rpc(method, _timeout=_timeout, **params)
        gw.rpc = rpc
        with mock.patch.object(rt, "STOP_BUDGET", 2.8):  # 0.8 s for the stop, 2 s kept for the close
            started = time.monotonic()
            rc, _, _ = self.run_turn(gw, "--deadline", str(time.time() + 0.1))
        self.assertEqual(rc, 125)
        self.assertLess(time.monotonic() - started, 3.5)
        self.assertTrue(all(t <= 0.9 for m, t in timeouts if m in {"prompt.receipt", "session.interrupt"}), timeouts)

    def test_a_send_that_blocks_is_cut_at_the_budget(self):
        """The client's ``_timeout`` covers only the answer; a send stuck on backpressure must still
        end within the budget, as an unconfirmed stop."""
        gw = self.gateway(receipt_status="started", receipt_outcome=None)
        real_rpc = gw.rpc

        async def rpc(method, _timeout=None, **params):
            if method == "session.interrupt":
                await asyncio.sleep(30)  # the send never completes, so _timeout never starts
            return await real_rpc(method, _timeout=_timeout, **params)
        gw.rpc = rpc
        with mock.patch.object(rt, "STOP_BUDGET", 3.0):
            started = time.monotonic()
            rc, out, err = self.run_turn(gw, "--deadline", str(time.time() + 0.1))
        self.assertEqual((rc, out), (125, ""))
        self.assertLess(time.monotonic() - started, 4.5)
        self.assertIn("not confirmed", err)

    def test_a_slow_close_never_outlives_the_stop_budget(self):
        """The verdict is in; a gateway that will not hang up must not hold the exit past the budget."""
        gw = self.gateway(stopped=("terminal", "interrupted", "partial"))
        connect = fake_modules(gw)["hermes_cli.gateway_client"].connect_gateway

        @contextlib.asynccontextmanager
        async def slow_connect():
            async with connect() as client:
                try:
                    yield client
                finally:
                    await asyncio.sleep(30)
        modules = fake_modules(gw)
        modules["hermes_cli.gateway_client"].connect_gateway = slow_connect
        out, err = __import__("io").StringIO(), __import__("io").StringIO()
        started = time.monotonic()
        with mock.patch.dict(sys.modules, modules), mock.patch.object(rt, "STOP_BUDGET", 3.0), \
                contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            rc = rt.main(["--profile", "writer", "--prompt-file", str(self.prompt), "--deadline", str(time.time() + 0.1)])
        self.assertEqual((rc, out.getvalue()), (124, "partial"))
        self.assertLess(time.monotonic() - started, 5.0)
        self.assertIn("closing the gateway connection", err.getvalue())

    def test_a_cancel_that_found_the_turn_completed_fetches_its_reply(self):
        """prompt.cancel answers terminal/completed without a result: the reply comes from the receipt."""
        gw = self.gateway()
        state = {"cancelled": False}
        gw.answers["prompt.receipt"] = lambda params: (
            gw.receipt("terminal", "completed", "finished anyway") if state["cancelled"] else gw.receipt("queued"))
        gw.answers["prompt.cancel"] = lambda params: state.update(cancelled=True) or {
            "status": "terminal", "outcome": "completed"}
        rc, out, _ = self.run_turn(gw, "--deadline", str(time.time() + 0.2))
        self.assertEqual((rc, out), (0, "finished anyway"))

    def test_an_image_is_staged_on_the_gateway_and_attached(self):
        gw = self.gateway()
        image = self.tmp / "shot.png"
        image.write_bytes(b"\x89PNG")
        gw.answers["image.attach_bytes"] = {"path": "/staged/shot.png", "mime": "image/png"}
        gw.complete()
        rc, _, _ = self.run_turn(gw, "--image", str(image))
        self.assertEqual(rc, 0)
        submit = dict(gw.calls)["prompt.submit"]
        self.assertEqual(submit["attachments"], [{"path": "/staged/shot.png", "mime": "image/png"}])


if __name__ == "__main__":
    unittest.main()
