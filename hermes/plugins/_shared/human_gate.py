"""human_gate: keep a write off the approval card's bypass paths.

An account plugin escalates every write to Hermes' human-approval gate with a ``pre_tool_call``
``approve`` directive. That gate auto-approves, without asking anyone, whenever Hermes runs in a mode
where nobody can answer: ``--yolo``, ``approvals.mode: off``, and ``hermes -z`` (which switches YOLO
on by itself because "an approval prompt would hang forever"). A write the card was meant to guard
would then run unasked. ``no_human`` names that situation so the plugin can refuse the write itself,
before any card is built: the same checks as the web3 tools' ``_no_human``.

Shared by the plugins that return an ``approve`` directive (each loads this file by path; it is not a
plugin and has no manifest). It fails closed: if Hermes' approval context cannot be read, nobody is
assumed present.
"""

from __future__ import annotations

# Programmatic platforms: a session there never has a person who can answer a card.
UNATTENDED = {"webhook", "msgraph_webhook", "api_server"}


def no_human() -> str | None:
    """Why no person can answer an approval card here, or None when one can."""
    try:
        from tools import approval, approval_context
        if approval._yolo_active():
            return "yolo mode is on"
        if approval_context._get_approval_mode() == "off":
            return "approvals are off (approvals.mode: off)"
        if approval_context._is_cron_approval_context():
            return "this is a cron job"
        if approval_context._is_single_query_approval_context():
            return "this is a single-query run"
        if approval_context._get_session_platform() in UNATTENDED:
            return "this platform is unattended"
        _, is_cli, is_gateway, is_ask = approval._presence()
        if not (is_cli or is_gateway or is_ask):
            return "nobody is present to answer"
        return None
    except Exception:  # noqa: BLE001 - fail closed on any doubt
        return "Hermes' approval context could not be read"


def refusal(tool: str, reason: str) -> str:
    """The message a refused write ends with: what did not happen, why, and what to do instead."""
    return (f"{tool}: not done. A write needs an approval card that a person answers, and none can be answered "
            f"here ({reason}). Nothing was sent or changed; ask the user to make this request in a chat with "
            "the Assistant, where the card reaches them.")
