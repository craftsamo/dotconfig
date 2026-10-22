"""resident-turn: one turn of a resident specialist session, run through the gateway.

Where ``hermes chat -q`` is a gateway client, the turn runs inside the gateway and the
CLI's exit says nothing about it. This client submits the turn itself and keeps the
gateway's receipt for it, so a stop can be confirmed: on SIGTERM / SIGINT, or at
``--deadline``, it stops the admission (``prompt.cancel`` while queued,
``session.interrupt`` once running) and waits for the admission's receipt to go
terminal. Run on the runtime's own interpreter (``hermes-python``) with HERMES_HOME
set to the target profile's home.

    resident-turn.py --profile <name> --prompt-file <path> [--resume <session_id>]
                     [--image <path>] [--deadline <epoch seconds>]

stdout: the reply. stderr: ``session_id: <id>`` once the session is known (the shell
re-captures it every turn) and ``admission_id: <id>`` once the turn is admitted.

Exit codes
  0    the turn completed (its reply is on stdout), even if a stop came too late
  1    the turn failed, or the gateway refused it before admitting it; nothing of it is running
  2    usage
  124  the deadline passed; the stop was confirmed by the receipt
  125  the turn was admitted but its outcome is unknown: a stop was sent and the
       receipt never confirmed it, or the gateway went away after the submit
  143  stopped on a signal; the stop was confirmed by the receipt

The whole stop (cancel or interrupt, the receipt polls, closing the connection) fits
STOP_BUDGET, so the shell's KILL_GRACE (20 s) always hears the verdict.
"""

from __future__ import annotations

import argparse
import asyncio
import base64
import mimetypes
import os
import signal
import sys
import time
import uuid
from pathlib import Path

STOP_BUDGET = 15.0  # from the stop decision to the exit: every RPC and poll of the stop, and the close, fit in it
EXIT_DEADLINE, EXIT_UNCONFIRMED, EXIT_INTERRUPTED = 124, 125, 143


def say(line: str) -> None:
    print(line, file=sys.stderr, flush=True)


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(prog="resident-turn", description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--profile", required=True)
    parser.add_argument("--prompt-file", required=True, type=Path)
    parser.add_argument("--resume", default="")
    parser.add_argument("--image", type=Path)
    parser.add_argument("--deadline", type=float, help="absolute epoch seconds; the turn is stopped there")
    args = parser.parse_args(argv)
    if args.image and not args.image.is_file():
        parser.error(f"image not found: {args.image}")
    return args


class SessionGone(SystemExit):
    """The session to resume no longer exists for this caller; nothing was run."""


async def attach_image(client, session_id: str, path: Path) -> list[dict]:
    mime = mimetypes.guess_type(str(path))[0] or "application/octet-stream"
    staged = await client.rpc("image.attach_bytes", session_id=session_id,
                              content_base64=base64.b64encode(path.read_bytes()).decode("ascii"),
                              filename=path.name, _timeout=60)
    return [{"path": staged["path"], "mime": staged.get("mime") or mime}]


async def open_session(client, resume: str) -> str:
    from hermes_cli.gateway_client import GatewayRPCError
    from hermes_cli.gateway_connection import RESUME_GONE
    if resume:
        try:
            snapshot = await client.rpc("session.resume", session_id=resume, omit_messages=True, _timeout=60)
        except GatewayRPCError as exc:
            if str(exc) in RESUME_GONE:  # str(exc) is the gateway's bounded reason code
                raise SessionGone(f"resident-turn: session {resume} is gone ({exc}); start the key again") from exc
            raise
        return snapshot["session_id"]
    snapshot = await client.rpc("session.create", request_id=uuid.uuid4().hex, source="oneshot",
                                cwd=os.getcwd(), row_cwd="", _timeout=60)
    return snapshot["session_id"]


async def complete_event(client, session_id: str, admission: str) -> dict:
    """The admission's ``message.complete`` payload; a transport error ends the wait."""
    while True:
        frame = await client.events.get()
        if isinstance(frame, Exception):
            raise frame
        params = frame.get("params") if isinstance(frame, dict) else None
        if not isinstance(params, dict) or params.get("session_id") != session_id:
            continue
        if params.get("type") == "message.complete" and params.get("admission_id", admission) == admission:
            return params.get("payload") or {}


async def rpc_within(client, until: float, method: str, **params):
    """``client.rpc`` bounded by the stop budget's absolute end ``until`` (monotonic). The client's
    own ``_timeout`` covers only the answer; the outer timeout covers the send as well."""
    left = max(until - time.monotonic(), 0.1)
    async with asyncio.timeout(left):
        return await client.rpc(method, _timeout=left, **params)


async def stop_turn(client, session_id: str, admission: str, generation, until: float) -> dict | None:
    """Stop the admission and return its terminal receipt, or None when it has not settled by
    ``until``. A queued admission is retired with ``prompt.cancel``; a started one is interrupted."""
    receipt = await rpc_within(client, until, "prompt.receipt", session_id=session_id, admission_id=admission,
                               include_result=True)
    if receipt.get("status") == "queued":
        try:
            receipt = await rpc_within(client, until, "prompt.cancel", session_id=session_id, admission_id=admission)
        except Exception as exc:  # it may have started meanwhile; the interrupt below covers that
            say(f"resident-turn: prompt.cancel failed: {exc}")
    if receipt.get("status") != "terminal":
        if generation is None:
            generation = receipt.get("execution_generation")
        if generation is None:
            snapshot = await rpc_within(client, until, "session.resume", session_id=session_id, omit_messages=True)
            generation = snapshot.get("execution_generation")
        try:
            await rpc_within(client, until, "session.interrupt", session_id=session_id,
                             execution_generation=generation)
        except Exception as exc:  # the receipt below decides; a failed interrupt is just unconfirmed
            say(f"resident-turn: session.interrupt failed: {exc}")
    while receipt.get("status") != "terminal":
        if time.monotonic() >= until:
            return None
        await asyncio.sleep(0.5)
        receipt = await rpc_within(client, until, "prompt.receipt", session_id=session_id, admission_id=admission,
                                   include_result=True)
    return receipt


def reply_of(complete: dict | None, receipt: dict | None) -> str:
    text = (complete or {}).get("text")
    if isinstance(text, str) and text:
        return text
    result = (receipt or {}).get("result") or {}
    final = result.get("final_response") if isinstance(result, dict) else None
    return final if isinstance(final, str) else ""


def emit(text: str) -> None:
    sys.stdout.write(text)
    sys.stdout.flush()


# ``prompt.submit`` refusals the gateway raises before its durable write, so nothing of the turn
# will run (the owner's own list, tui_gateway/owner_forward.py); any other failure of the submit
# can follow the commit, so the turn may be running.
REFUSED_BEFORE_COMMIT = frozenset({
    "invalid_params", "runtime_draining", "runtime_retired", "profile_mismatch", "permission_denied",
    "not_found", "session_superseded", "stale_epoch", "admission_conflict", "queue_full"})


async def submit(client, session_id: str, params: dict, outcome: dict) -> dict:
    """``prompt.submit``; ``outcome["submitted"]`` says whether the turn may exist afterwards."""
    from hermes_cli.gateway_client import GatewayRPCError
    try:
        receipt = await client.rpc("prompt.submit", session_id=session_id, **params, _timeout=60)
    except GatewayRPCError as exc:
        outcome["submitted"] = str(exc) not in REFUSED_BEFORE_COMMIT
        raise
    except BaseException:
        outcome["submitted"] = True  # the submit may have landed: an unknown outcome, never "failed"
        raise
    outcome["submitted"] = True
    return receipt


async def turn(client, args: argparse.Namespace, stop: asyncio.Event, outcome: dict) -> None:
    """Run the turn and fill ``outcome`` (``code``, ``reply``); a stop runs within ``outcome["until"]``."""
    session_id = await open_session(client, args.resume)
    say(f"session_id: {session_id}")
    params = {"submission_id": uuid.uuid4().hex, "text": args.prompt_file.read_text(encoding="utf-8"),
              "finite": True}
    if args.image:
        params["attachments"] = await attach_image(client, session_id, args.image)
    receipt = await submit(client, session_id, params, outcome)
    admission, generation = receipt["admission_id"], receipt.get("execution_generation")
    say(f"admission_id: {admission}")

    waiting = asyncio.ensure_future(complete_event(client, session_id, admission))
    stopping = asyncio.ensure_future(stop.wait())
    remaining = None if args.deadline is None else max(args.deadline - time.time(), 0.0)
    done, _ = await asyncio.wait({waiting, stopping}, timeout=remaining, return_when=asyncio.FIRST_COMPLETED)
    stopping.cancel()
    if waiting in done:
        complete = waiting.result()  # a transport error raises here: admitted, outcome unknown
        status = complete.get("status")
        outcome.update(reply=reply_of(complete, None),
                       code=0 if status == "complete" else EXIT_INTERRUPTED if status == "interrupted" else 1)
        return

    # A signal or the deadline: stop the admission and wait for its receipt, all within the budget,
    # which also covers closing the connection afterwards.
    waiting.cancel()
    by_deadline = not stop.is_set()
    say("resident-turn: " + ("deadline reached" if by_deadline else "signal received") + "; stopping the turn")
    outcome["until"] = time.monotonic() + STOP_BUDGET
    final = await stop_turn(client, session_id, admission, generation, outcome["until"] - 2.0)
    if final is None:
        say("resident-turn: the stop was not confirmed within the budget; the turn may still be running")
        return
    if final.get("outcome") == "completed" and "result" not in final:
        # ``prompt.cancel`` answered for a turn that completed meanwhile; it carries no result.
        final = await rpc_within(client, outcome["until"] - 2.0, "prompt.receipt", session_id=session_id,
                                 admission_id=admission, include_result=True)
    outcome["reply"] = reply_of(None, final)
    if final.get("outcome") == "completed":
        say("resident-turn: the turn completed before the stop reached it")
        outcome["code"] = 0
    else:
        outcome["code"] = EXIT_DEADLINE if by_deadline else EXIT_INTERRUPTED


async def run(args: argparse.Namespace, outcome: dict) -> None:
    """``turn`` on a gateway connection, then close it; a stop's budget bounds the close as well, so the
    shell always hears the verdict within its grace."""
    from hermes_cli.gateway_client import connect_gateway
    stop = asyncio.Event()
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGTERM, signal.SIGINT, signal.SIGHUP):
        loop.add_signal_handler(sig, stop.set)
    connection = connect_gateway()
    client = await connection.__aenter__()
    try:
        await turn(client, args, stop, outcome)
    finally:
        budget = outcome.get("until")
        try:
            if budget is None:
                await connection.__aexit__(None, None, None)
            else:
                async with asyncio.timeout(max(budget - time.monotonic(), 0.1)):
                    await connection.__aexit__(None, None, None)
        except (TimeoutError, Exception) as exc:  # the verdict is in; a slow close must not outlive the grace
            say(f"resident-turn: closing the gateway connection: {exc}")


def main(argv: list[str] | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    outcome = {"submitted": False, "code": EXIT_UNCONFIRMED, "reply": ""}
    try:
        asyncio.run(run(args, outcome))
    except SessionGone:
        raise
    except Exception as exc:
        say(f"resident-turn: {exc}")
        # Before the submit nothing of the turn exists (a refusal, a lost gateway); after it the turn
        # may be running, and only the gateway knows.
        return EXIT_UNCONFIRMED if outcome["submitted"] else 1
    emit(outcome["reply"])
    return outcome["code"]


if __name__ == "__main__":
    sys.exit(main())
