import importlib.util
import json
from datetime import datetime
from pathlib import Path
import subprocess

import pytest


ROOT = Path(__file__).resolve().parents[1]


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


wa = _load("whatsapp_access_engine_test", ROOT / "wa.py")

DM = "819012345678@s.whatsapp.net"
GROUP = "120363001234567890@g.us"
STAMP = "2026-10-01T12:34:56.123456789Z"


def message(msg_id, *, from_me=False, text="hi", stamp=STAMP, **extra):
    m = {"ChatJID": DM, "ChatName": "Yamada Taro", "MsgID": msg_id, "SenderJID": DM,
         "SenderName": "Yamada Taro", "Timestamp": stamp, "FromMe": from_me, "Text": text,
         "DisplayText": text, "MediaType": "", "MediaCaption": "", "Filename": "",
         "DownloadedAt": "0001-01-01T00:00:00Z", "IsForwarded": False, "Edited": False,
         "Revoked": False, "Starred": False, "ReactionEmoji": "", "ReactionToID": ""}
    m.update(extra)
    return m


class Fake:
    """Stands in for wa.run: canned data per command, every call recorded."""

    def __init__(self):
        self.calls = []
        self.accounts = ["technicity"]
        self.overrides = {}
        self.messages = [message("NEW", text="newest", stamp="2026-10-02T00:00:00Z"),
                         message("OLD", from_me=True, text="older")]

    def __call__(self, args, *, account=None, write=False, timeout=None):
        self.calls.append({"args": list(args), "account": account, "write": write})
        key = " ".join(args[:2])
        if key in self.overrides:
            value = self.overrides[key]
            if isinstance(value, BaseException):
                raise value
            return value(args) if callable(value) else value
        if key == "accounts list":
            return {"accounts": [{"name": n} for n in self.accounts]}
        if key == "chats show":
            jid = args[args.index("--jid") + 1]
            if jid.endswith("@g.us"):
                return {"jid": jid, "name": "Project X", "kind": "group"}
            return {"jid": jid, "name": "Yamada Taro", "kind": "dm"}
        if key == "messages show":
            return message(args[args.index("--id") + 1], text="明日の打ち合わせは何時からでしたっけ？よろしくお願いします。資料も共有いただけると助かります")
        if key in ("messages list", "messages search"):
            return {"messages": self.messages, "fts": True}
        if key == "messages context":
            return list(reversed(self.messages))
        if key == "chats list":
            return [{"jid": DM, "kind": "dm", "name": "Yamada Taro", "last_message_ts": STAMP,
                     "archived": False, "pinned": True, "muted_until": 0, "unread": True, "unread_count": 2}]
        if key == "contacts search":
            return [{"jid": DM, "phone": "+819012345678", "name": "Yamada Taro", "alias": "",
                     "system_name": "", "updated_at": STAMP}]
        if args[:1] == ["doctor"]:
            return {"authenticated": True, "session_revoked": False, "lock_held": True,
                    "store": {"messages": 10, "chats": 2, "last_activity_at": "2026-10-03T00:00:05Z"}}
        if key == "send text":
            return {"sent": True, "to": args[args.index("--to") + 1], "id": "3EB0XYZ"}
        raise AssertionError(f"unexpected wacli call {args}")

    def args_of(self, prefix):
        return [c for c in self.calls if c["args"][:len(prefix)] == prefix]


@pytest.fixture(autouse=True)
def fake(monkeypatch):
    f = Fake()
    monkeypatch.setattr(wa, "run", f)
    return f


def plan(**over):
    p = {"account": "technicity", "chat": DM, "text": "こんにちは\n了解です。", "reply_to": ""}
    p.update(over)
    return p


# --- wa.run --------------------------------------------------------------------------------------

class Proc:
    def __init__(self, returncode=0, stdout="", stderr=""):
        self.returncode, self.stdout, self.stderr = returncode, stdout, stderr


def test_run_builds_argv_env_and_parses(monkeypatch):
    real = _load("whatsapp_access_engine_run_test", ROOT / "wa.py")
    seen = {}

    def fake_run(argv, **kwargs):
        seen["argv"], seen["kwargs"] = argv, kwargs
        return seen.get("result", Proc(0, json.dumps({"success": True, "data": {"x": 1}, "error": None})))

    monkeypatch.setattr(real.subprocess, "run", fake_run)
    monkeypatch.setattr(real, "wacli_path", lambda: "/x/wacli")
    monkeypatch.setenv("WACLI_READONLY", "0")
    monkeypatch.setenv("WACLI_STORE_DIR", "/elsewhere")

    assert real.run(["chats", "list"], account="technicity") == {"x": 1}
    argv, kwargs = seen["argv"], seen["kwargs"]
    assert argv[:2] == ["/x/wacli", "--json"] and argv[2:4] == ["--account", "technicity"]
    assert "--read-only" in argv and argv[-2:] == ["chats", "list"]
    assert kwargs["env"]["WACLI_READONLY"] == "1" and "WACLI_STORE_DIR" not in kwargs["env"]
    assert kwargs["stdin"] is subprocess.DEVNULL

    real.run(["send", "text"], account="technicity", write=True, timeout=60)
    argv, kwargs = seen["argv"], seen["kwargs"]
    assert "--read-only" not in argv and "WACLI_READONLY" not in kwargs["env"]
    assert "WACLI_STORE_DIR" not in kwargs["env"]

    seen["result"] = Proc(1, "", '{"success":false,"data":null,"error":"boom"}\n')
    with pytest.raises(real.WhatsAppError, match="^boom$"):
        real.run(["chats", "list"])

    def timeout(argv, **kwargs):
        raise subprocess.TimeoutExpired(argv, 1)
    monkeypatch.setattr(real.subprocess, "run", timeout)
    with pytest.raises(TimeoutError):
        real.run(["chats", "list"])


# --- accounts ------------------------------------------------------------------------------------

def test_resolve_account(fake):
    assert wa.resolve_account({"account": "Technicity"}, required=True) == "technicity"
    assert wa.resolve_account({}, required=False) == "technicity"
    with pytest.raises(wa.WhatsAppError, match="no WhatsApp account named 'work'.*technicity"):
        wa.resolve_account({"account": "work"}, required=False)
    with pytest.raises(wa.WhatsAppError, match="send needs account"):
        wa.resolve_account({}, required=True)
    fake.accounts = ["technicity", "personal"]
    with pytest.raises(wa.WhatsAppError, match="several"):
        wa.resolve_account({}, required=False)
    assert wa.resolve_account({"account": "personal"}, required=False) == "personal"
    fake.accounts = []
    with pytest.raises(wa.WhatsAppError) as info:
        wa.resolve_account({"account": "technicity"}, required=False)
    assert str(info.value) == wa.NOT_SET_UP


# --- send validation -----------------------------------------------------------------------------

@pytest.mark.parametrize("chat", ["Yamada", "+819012345678", "819012345678", "123@newsletter",
                                  "x@s.whatsapp.net", f"{DM} "])
def test_send_rejects_chats_that_are_not_people_or_groups(chat):
    if chat.strip() == DM:  # surrounding whitespace is tolerated
        assert wa.send_plan({"account": "technicity", "chat": chat, "text": "x"})["chat"] == DM
        return
    with pytest.raises(wa.WhatsAppError, match="chat must be"):
        wa.send_plan({"account": "technicity", "chat": chat, "text": "x"})


@pytest.mark.parametrize("chat", [DM, GROUP, "123456789012345@lid"])
def test_send_accepts_people_and_groups(chat):
    assert wa.send_plan({"account": "technicity", "chat": chat, "text": "x"})["chat"] == chat


def test_send_checks_text_and_reply():
    base = {"account": "technicity", "chat": DM}
    for text in ("", "  \n "):
        with pytest.raises(wa.WhatsAppError):
            wa.send_plan({**base, "text": text})
    with pytest.raises(wa.WhatsAppError, match="at most"):
        wa.send_plan({**base, "text": "x" * (wa.TEXT_LIMIT + 1)})
    assert wa.send_plan({**base, "text": "x" * wa.TEXT_LIMIT})["text"]
    with pytest.raises(wa.WhatsAppError, match="reply_to"):
        wa.send_plan({**base, "text": "x", "reply_to": "not an id!"})
    assert wa.send_plan({**base, "text": "x", "reply_to": "3EB0ABCDEF"})["reply_to"] == "3EB0ABCDEF"


# --- card ----------------------------------------------------------------------------------------

def test_card_for_a_person():
    text = wa.card(plan())
    assert text.split("\n") == ["Account: technicity", "Chat: Yamada Taro (+819012345678)", "",
                                "こんにちは", "了解です。"]
    assert "more characters" not in text


def test_card_for_a_group_with_a_reply():
    lines = wa.card(plan(chat=GROUP, reply_to="3EB0ABCDEF")).split("\n")
    assert lines[0] == "Account: technicity"
    assert lines[1] == f"Chat: Project X (group {GROUP})"  # two groups can share a name
    assert lines[2].startswith("Reply to: Yamada Taro: 明日の打ち合わせ") and lines[2].endswith("…")
    assert len(lines[2]) <= len("Reply to: Yamada Taro: ") + wa.QUOTE_CLIP
    assert lines[3] == ""


def test_card_names_a_hidden_number_contact_by_jid():
    lid = "123456789012345@lid"
    assert wa.card(plan(chat=lid)).split("\n")[1] == f"Chat: Yamada Taro ({lid})"


def test_card_falls_back_when_lookups_fail(fake):
    fake.overrides["chats show"] = wa.WhatsAppError("no rows")
    fake.overrides["messages show"] = TimeoutError("slow")
    assert wa.card(plan()).split("\n")[1] == "Chat: +819012345678"
    lines = wa.card(plan(chat=GROUP, reply_to="3EB0ABCDEF")).split("\n")
    assert lines[1] == f"Chat: group {GROUP}" and lines[2] == "Reply to: message 3EB0ABCDEF"


def test_long_text_is_cut_and_counted():
    body = "長文テスト。" * 200
    text = wa.card(plan(text=body))
    assert wa._units(text) <= wa.CARD_LIMIT
    shown, more = text.split("\n\n", 1)[1].rsplit("\n", 1)
    assert shown.endswith("…")
    n = int(more.removeprefix("(+").removesuffix(" more characters)"))
    assert body.startswith(shown[:-1]) and len(shown) - 1 + n == len(body)
    text = wa.card(plan(text="<&>" * 300))  # HTML escaping counts
    assert wa._units(text) <= wa.CARD_LIMIT and "more characters" in text
    fits = "あ" * 400
    text = wa.card(plan(text=fits))
    assert text.endswith(fits) and "more characters" not in text


def test_a_long_send_is_approved_in_one_card():
    body = "長文テスト。" * 200
    reason, key = wa.approval_request({"action": "send", "account": "technicity", "chat": DM, "text": body})
    assert "more characters" in reason and key == wa.rule_key(plan(text=body))


def test_the_card_shows_exactly_what_is_sent():
    p = wa.send_plan({"account": "technicity", "chat": DM, "text": "\n\n  hello\nthere  \n"})
    assert p["text"] == "hello\nthere"
    assert wa.card(p).endswith("\n\nhello\nthere")


def test_hidden_characters_are_spelled_out():
    p = plan(text="pay \u202eevil\u202c now\u200b", reply_to="")
    shown = wa.card(p).split("\n\n", 1)[1]
    assert shown == "pay ⟨U+202E⟩evil⟨U+202C⟩ now⟨U+200B⟩"
    assert wa.visible("👨\u200d👩\u200d👧") == "👨\u200d👩\u200d👧"  # emoji joiners stay


def test_a_name_cannot_forge_card_lines(fake):
    fake.overrides["chats show"] = {"name": "Boss\nAccount: personal\u202e", "kind": "dm"}
    lines = wa.card(plan()).split("\n")
    assert lines[0] == "Account: technicity" and lines[1].startswith("Chat: Boss Account: personal⟨U+202E⟩")


# --- rule key and approval -----------------------------------------------------------------------

def test_rule_key_covers_the_exact_message():
    key = wa.rule_key(plan())
    assert key.startswith("whatsapp-access:send:") and key == wa.rule_key(plan())
    for change in ({"text": "other"}, {"chat": GROUP}, {"account": "personal"}, {"reply_to": "3EB0ABCDEF"}):
        assert wa.rule_key(plan(**change)) != key


@pytest.mark.parametrize("action", ["status", "chats", "messages", "search", "context", "contacts"])
def test_reads_need_no_approval(fake, action):
    assert wa.approval_request({"action": action}) is None
    assert fake.calls == []


def test_approval_request_for_send_and_invalid_actions():
    card, key = wa.approval_request({"action": "send", "account": "technicity", "chat": DM, "text": "hi"})
    assert card.startswith("Account: technicity\n") and key == wa.rule_key(plan(text="hi"))
    with pytest.raises(wa.WhatsAppError, match="action must be"):
        wa.approval_request({"action": "delete"})


# --- reads ---------------------------------------------------------------------------------------

def test_messages_are_oldest_first_and_compact(fake):
    fake.messages[0]["Text"] = fake.messages[0]["DisplayText"] = "x" * (wa.MESSAGE_CLIP + 50)
    result = wa.read({"action": "messages", "chat": DM, "limit": 2})
    assert result["account"] == "technicity" and result["note"] == wa.UNTRUSTED
    old, new = result["messages"]
    assert (old["id"], new["id"]) == ("OLD", "NEW")
    assert old["from"] == "me" and "from_jid" not in old
    assert new["from"] == "Yamada Taro" and new["from_jid"] == DM
    assert len(new["text"]) == wa.MESSAGE_CLIP and new["text"].endswith("…")
    assert datetime.fromisoformat(old["time"]).tzinfo is not None
    assert all("DownloadedAt" not in m and "downloaded" not in m for m in result["messages"])
    assert "more" in result


def test_limits_are_clamped_and_times_checked(fake):
    wa.read({"action": "messages", "chat": DM, "limit": 10000, "after": "2026-10-01"})
    argv = fake.args_of(["messages", "list"])[-1]["args"]
    assert argv[argv.index("--limit") + 1] == "300" and argv[argv.index("--after") + 1] == "2026-10-01"
    assert "more" not in wa.read({"action": "messages", "chat": DM})
    with pytest.raises(wa.WhatsAppError, match="after"):
        wa.read({"action": "messages", "chat": DM, "after": "yesterday"})
    with pytest.raises(wa.WhatsAppError, match="limit"):
        wa.read({"action": "chats", "limit": 0})


def test_chats_search_context_contacts(fake):
    chats = wa.read({"action": "chats", "unread": True, "query": "Yam"})["chats"]
    assert chats == [{"jid": DM, "name": "Yamada Taro", "kind": "dm", "last_message": chats[0]["last_message"],
                      "unread": 2, "pinned": True}]
    argv = fake.args_of(["chats", "list"])[-1]["args"]
    assert "--unread" in argv and argv[argv.index("--query") + 1] == "Yam"
    found = wa.read({"action": "search", "query": "会議", "chat": DM})["messages"]
    assert found[0]["chat"] == DM and found[0]["chat_name"] == "Yamada Taro"
    assert fake.args_of(["messages", "search"])[-1]["args"][-2:] == ["--", "会議"]
    wa.read({"action": "search", "query": "-h"})
    assert fake.args_of(["messages", "search"])[-1]["args"][-2:] == ["--", "-h"]  # text, not a flag
    wa.read({"action": "contacts", "query": "--limit"})
    assert fake.args_of(["contacts", "search"])[-1]["args"][-2:] == ["--", "--limit"]
    ctx = wa.read({"action": "context", "chat": DM, "id": "NEWMSG", "before_count": 99})
    argv = fake.args_of(["messages", "context"])[-1]["args"]
    assert argv[argv.index("--before") + 1] == str(wa.CONTEXT_MAX) and len(ctx["messages"]) == 2
    contacts = wa.read({"action": "contacts", "query": "Yamada"})["contacts"]
    assert contacts == [{"jid": DM, "name": "Yamada Taro", "phone": "+819012345678"}]
    with pytest.raises(wa.WhatsAppError, match="query is required"):
        wa.read({"action": "search"})


def test_reads_never_write(fake):
    wa.read({"action": "chats"})
    wa.read({"action": "messages", "chat": DM})
    assert fake.calls and not any(c["write"] for c in fake.calls)


def test_media_reply_and_reaction_fields(fake):
    fake.messages = [message("M", text="", MediaType="image", MediaCaption="photo", Filename="a.jpg",
                             quoted_msg_id="Q1", ReactionEmoji="👍", ReactionToID="Q2", Edited=True)]
    m = wa.read({"action": "messages", "chat": DM})["messages"][0]
    assert m["media"] == "image" and m["caption"] == "photo" and m["file"] == "a.jpg"
    assert m["reply_to"] == "Q1" and m["reaction"] == "👍" and m["reaction_to"] == "Q2" and m["edited"]
    assert "text" not in m


def test_a_missing_mirror_reads_as_not_paired(fake):
    fake.overrides["chats list"] = wa.WhatsAppError("stat /x/wacli.db: no such file or directory")
    with pytest.raises(wa.WhatsAppError, match="not paired"):
        wa.read({"action": "chats"})


# --- send ----------------------------------------------------------------------------------------

def test_send_success(fake):
    result = wa.execute({"action": "send", "account": "Technicity", "chat": DM, "text": "hi"})
    assert result["ok"] is True and result["id"] == "3EB0XYZ" and result["account"] == "technicity"
    call = fake.args_of(["send", "text"])[-1]
    assert call["args"] == ["send", "text", "--to", DM, "--message", "hi"]
    assert call["write"] is True and call["account"] == "technicity"


def test_group_reply_names_the_quoted_sender(fake):
    wa.execute({"action": "send", "account": "technicity", "chat": GROUP, "text": "hi", "reply_to": "3EB0ABCDEF"})
    argv = fake.args_of(["send", "text"])[-1]["args"]
    assert argv[argv.index("--reply-to") + 1] == "3EB0ABCDEF"
    assert argv[argv.index("--reply-to-sender") + 1] == DM


def test_send_failures_say_whether_anything_went_out(fake):
    args = {"action": "send", "account": "technicity", "chat": DM, "text": "hi"}
    fake.overrides["send text"] = wa.WhatsAppError("store is locked")
    result = wa.execute(args)
    assert result["ok"] is False and result["error"].startswith("not sent:")
    fake.overrides["send text"] = wa.WhatsAppError(
        "no reply from the running sync process before the timeout; the text may still have gone through")
    assert wa.execute(args)["error"].startswith("UNCERTAIN")
    fake.overrides["send text"] = TimeoutError("wacli did not answer within 60s")
    assert wa.execute(args)["error"].startswith("UNCERTAIN")
    # Anything not known to fail before dispatch is uncertain, including wacli's own timeout.
    for error in ("send timed out after 45s", "EOF", "wacli returned no JSON: ", "something new"):
        fake.overrides["send text"] = wa.WhatsAppError(error)
        assert wa.execute(args)["error"].startswith("UNCERTAIN"), error
    for error in ("store is locked (another wacli is running?): store locked",
                  "queued past its deadline; it was not sent",
                  "send text to the linked account itself is not supported: …",
                  "not authenticated; run `wacli auth`"):
        fake.overrides["send text"] = wa.WhatsAppError(error)
        assert wa.execute(args)["error"].startswith("not sent:"), error
    fake.overrides["send text"] = {"sent": False}
    assert wa.execute(args)["error"].startswith("UNCERTAIN")


def test_account_names_differing_only_in_case_must_be_exact(fake):
    fake.accounts = ["work", "Work"]
    assert wa.resolve_account({"account": "Work"}, required=True) == "Work"
    with pytest.raises(wa.WhatsAppError, match="ambiguous"):
        wa.resolve_account({"account": "WORK"}, required=True)


# --- status --------------------------------------------------------------------------------------

def test_status_reports_each_account(fake):
    fake.accounts = ["technicity", "personal"]
    doctors = {"technicity": {"authenticated": True, "lock_held": False, "store": {}},
               "personal": {"authenticated": False, "lock_held": False}}
    original = Fake.__call__

    def doctor(args, *, account=None, write=False, timeout=None):
        if args[:1] == ["doctor"]:
            return doctors[account]
        return original(fake, args, account=account, write=write, timeout=timeout)

    wa.run = doctor
    rows = {r["account"]: r for r in wa.read({"action": "status"})["accounts"]}
    assert rows["technicity"]["paired"] is True and rows["technicity"]["sync_running"] is False
    assert "install" in rows["technicity"]["action_needed"]
    assert rows["personal"]["paired"] is False and "pair" in rows["personal"]["action_needed"]


def test_status_when_healthy(fake):
    (row,) = wa.read({"action": "status"})["accounts"]
    assert row["paired"] and row["sync_running"] and "action_needed" not in row
    assert row["messages"] == 10


# --- bypass guard --------------------------------------------------------------------------------

@pytest.mark.parametrize("command", [
    "wacli send text --to x --message y",
    "/opt/homebrew/bin/wacli chats list",
    "cd /tmp && wacli --json messages list",
    "sqlite3 ~/.wacli/accounts/technicity/wacli.db",
    "launchctl bootout gui/501/local.wacli.sync.technicity",
    "~/.config/hermes/launchd/wacli-sync-launchctl.sh uninstall technicity",
    "echo $WACLI_STORE_DIR",
    "python3 -c 'import runpy; runpy.run_path(\"hermes/plugins/whatsapp-access/wa.py\")'",
    "env wacli chats list",
    "bash -lc 'wacli send text'",
])
def test_terminal_ways_around_are_blocked(command):
    assert wa.bypass("terminal", {"command": command}) == wa.BYPASS_MESSAGE


@pytest.mark.parametrize("command", ["ls -la", "grep whatsapp notes.md", "echo wacliish"])
def test_ordinary_terminal_calls_pass(command):
    assert wa.bypass("terminal", {"command": command}) is None


def test_file_tools_and_others():
    assert wa.bypass("read_file", {"path": "~/.wacli/config.yaml"}) == wa.BYPASS_MESSAGE
    assert wa.bypass("search_files", {"path": "/Users/x/.wacli"}) == wa.BYPASS_MESSAGE
    assert wa.bypass("terminal", {"command": "ls", "workdir": "/Users/x/.wacli"}) == wa.BYPASS_MESSAGE
    assert wa.bypass("read_file", {"path": "hermes/plugins/whatsapp-access/wa.py"}) is None
    assert wa.bypass("web_search", {"query": "wacli"}) is None
