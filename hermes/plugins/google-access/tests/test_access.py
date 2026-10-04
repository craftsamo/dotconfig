import base64
import importlib.util
import json
import os
from email import message_from_bytes
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

import pytest


ROOT = Path(__file__).resolve().parents[1]


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


access = _load("google_access_engine_test", ROOT / "access.py")


def token(home, scopes=access.SCOPES):
    access._write_private(access.token_path(home), json.dumps({
        "type": "authorized_user", "client_id": "c", "client_secret": "s", "refresh_token": "r",
        "token": "t", "scopes": list(scopes)}))


def tree(spec):
    """{"a": {"b": None}} -> gcloud's completion-tree shape; None marks a command (leaf)."""
    return {"commands": {name: tree(child) if child else {"commands": {}, "flags": {}}
                         for name, child in spec.items()}, "flags": {}}


TREE = tree({
    "projects": {"list": None, "get-iam-policy": None, "add-iam-policy-binding": None},
    "run": {"services": {"describe": None, "delete": None, "list": None}, "deploy": None,
            "jobs": {"list": None}},
    "logging": {"read": None},
    "storage": {"ls": None, "cp": None},
    "compute": {"instances": {"list": None, "list-tags": None, "create": None, "delete": None},
                "ssh": None},
    "auth": {"list": None, "login": None, "print-access-token": None},
    "config": {"list": None, "set": None, "get": None, "configurations": {"activate": None}},
    "beta": {"run": {"jobs": {"list": None}}, "auth": {"login": None}},
    "secrets": {"versions": {"access": None}},
    "container": {"clusters": {"get-credentials": None}},
    "services": {"enable": None},
    "domains": {"registrations": {"authorization-code": {"get": None}}},
    "init": None,
    "components": {"install": None},
})


@pytest.fixture(autouse=True)
def fake_tree(monkeypatch):
    monkeypatch.setattr(access, "_command_tree", lambda: TREE)


# --- gcloud planning ------------------------------------------------------------------------------

@pytest.mark.parametrize("command", [["projects", "list"], ["run", "services", "describe"],
                                     ["projects", "get-iam-policy"], ["logging", "read"],
                                     ["storage", "ls"], ["compute", "instances", "list-tags"],
                                     ["auth", "list"], ["config", "list"], ["config", "get"],
                                     ["config", "get-value"],
                                     ["beta", "run", "jobs", "list"]])
def test_read_only_commands_need_no_approval(command):
    argv, read_only = access.gcloud_plan({"command": command, "args": ["--format=json"]})
    assert read_only
    assert argv[:len(command)] == command and argv[-1] == "--format=json"
    assert access.approval_request("gcloud", {"command": command}) is None


@pytest.mark.parametrize("command", [["run", "deploy"], ["compute", "instances", "delete"],
                                     ["compute", "ssh"], ["projects", "add-iam-policy-binding"],
                                     ["secrets", "versions", "access"], ["storage", "cp"],
                                     ["container", "clusters", "get-credentials"], ["services", "enable"],
                                     ["domains", "registrations", "authorization-code", "get"]])
def test_other_commands_need_approval(command):
    _, read_only = access.gcloud_plan({"command": command})
    assert not read_only
    reason, key = access.approval_request("gcloud", {"command": command, "project": "my-proj"})
    assert "gcloud " + " ".join(command) in reason and "--project=my-proj" in reason
    assert key.startswith("google-access:gcloud:")


def test_a_read_verb_in_args_does_not_make_a_write_read_only():
    _, read_only = access.gcloud_plan({"command": ["compute", "instances", "delete"], "args": ["list"]})
    assert not read_only


@pytest.mark.parametrize("command", [["compute", "instances", "create", "list"],
                                     ["run", "services", "delete", "list"], ["projects", "lst"]])
def test_a_positional_inside_the_command_path_is_rejected(command):
    with pytest.raises(access.AccessError, match="not a gcloud command path"):
        access.gcloud_plan({"command": command})
    with pytest.raises(access.AccessError):
        access.approval_request("gcloud", {"command": command})


def test_a_group_is_not_a_command():
    with pytest.raises(access.AccessError, match="command group"):
        access.gcloud_plan({"command": ["compute", "instances"]})


def test_without_the_sdk_tree_everything_asks(monkeypatch):
    monkeypatch.setattr(access, "_command_tree", lambda: None)
    _, read_only = access.gcloud_plan({"command": ["projects", "list"]})
    assert not read_only
    assert access.approval_request("gcloud", {"command": ["projects", "list"]})


def test_the_installed_sdk_tree_parses():
    binary = access.shutil.which("gcloud")
    if not binary:
        pytest.skip("gcloud not installed")
    path = Path(binary).resolve().parent.parent / access.GCLOUD_TREE
    if not path.is_file():
        pytest.skip("no static command tree in this SDK")
    real = access._load_tree(str(path), path.stat().st_mtime_ns)
    instances = real["commands"]["compute"]["commands"]["instances"]["commands"]
    assert instances["create"]["commands"] == {} and instances["list"]["commands"] == {}


@pytest.mark.parametrize("command", [["auth", "login"], ["auth", "print-access-token"], ["config", "set"],
                                     ["beta", "auth", "login"], ["init"], ["components", "install"],
                                     ["config", "configurations", "activate"]])
def test_identity_and_configuration_are_off_limits(command):
    with pytest.raises(access.AccessError, match="gaccess"):
        access.gcloud_plan({"command": command})


@pytest.mark.parametrize("flag", ["--account=x@y", "--configuration", "--project=p", "--flags-file=f.yaml",
                                  "--impersonate-service-account=sa@p.iam", "--log-http"])
def test_forbidden_flags(flag):
    with pytest.raises(access.AccessError, match="not allowed"):
        access.gcloud_plan({"command": ["projects", "list"], "args": [flag]})


@pytest.mark.parametrize("command", [[], ["Projects", "list"], ["projects", "--format=json"], ["a b"], "projects list"])
def test_malformed_commands(command):
    with pytest.raises(access.AccessError):
        access.gcloud_plan({"command": command})


def test_hermes_flags_precede_user_args_so_double_dash_cannot_swallow_them():
    argv, _ = access.gcloud_plan({"command": ["compute", "ssh"], "project": "p-1",
                                  "args": ["vm", "--", "ls", "--quiet"]})
    assert argv == ["compute", "ssh", "--quiet", "--project=p-1", "vm", "--", "ls", "--quiet"]


def test_bad_project_id():
    with pytest.raises(access.AccessError, match="project id"):
        access.gcloud_plan({"command": ["projects", "list"], "project": "x; rm -rf /"})


# --- gcloud execution -----------------------------------------------------------------------------

def test_gcloud_runs_in_the_profile_configuration(tmp_path, monkeypatch):
    access.gcloud_config_dir(tmp_path).mkdir(parents=True)
    monkeypatch.setenv("CLOUDSDK_CORE_PROJECT", "users-own")
    monkeypatch.setenv("CLOUDSDK_CONFIG", "/Users/x/.config/gcloud")
    monkeypatch.setattr(access.shutil, "which", lambda name: "/opt/homebrew/bin/gcloud")
    seen = {}

    def run(argv, **kwargs):
        seen.update(argv=argv, **kwargs)
        return SimpleNamespace(returncode=0, stdout="[]", stderr="")

    monkeypatch.setattr(access.subprocess, "run", run)
    result = access.gcloud(tmp_path, {"command": ["projects", "list"], "args": ["--format=json"]})
    assert result["ok"] and result["stdout"] == "[]"
    assert seen["argv"] == ["/opt/homebrew/bin/gcloud", "projects", "list", "--quiet", "--format=json"]
    env = seen["env"]
    assert env["CLOUDSDK_CONFIG"] == str(access.gcloud_config_dir(tmp_path))
    assert "CLOUDSDK_CORE_PROJECT" not in env
    assert seen["stdin"] is access.subprocess.DEVNULL and seen["timeout"] == access.GCLOUD_TIMEOUT


def test_gcloud_requires_the_profile_login(tmp_path):
    with pytest.raises(access.AccessError, match="gcloud-login"):
        access.gcloud(tmp_path, {"command": ["projects", "list"]})


def test_gcloud_output_is_clipped(tmp_path, monkeypatch):
    access.gcloud_config_dir(tmp_path).mkdir(parents=True)
    monkeypatch.setattr(access.shutil, "which", lambda name: "/bin/gcloud")
    monkeypatch.setattr(access.subprocess, "run", lambda argv, **kw: SimpleNamespace(
        returncode=1, stdout="x" * (access.STDOUT_LIMIT + 5), stderr="boom"))
    result = access.gcloud(tmp_path, {"command": ["projects", "list"]})
    assert not result["ok"] and result["exit_code"] == 1 and result["truncated"]
    assert len(result["stdout"]) == access.STDOUT_LIMIT


# --- approval for Google writes -------------------------------------------------------------------

SID = "1AbCdEfGhIjKlMnOpQrStUvWxYz0123456789_-abcd"
OTHER = "1ZyXwVuTsRqPoNmLkJiHgFeDcBa9876543210_-zyxw"


@pytest.fixture(autouse=True)
def fresh_context():
    access._CONTEXT.clear()
    yield
    access._CONTEXT.clear()


def test_sheets_reads_pass_and_writes_ask():
    for action in ("search", "info", "get"):
        assert access.approval_request("google_sheets", {"action": action, "spreadsheet_id": SID}) is None
    args = {"action": "update", "spreadsheet_id": SID, "range": "Sheet1!A1:B2",
            "values": [["Name", "Score"], ["Alice", 95]]}
    reason, key = access.approval_request("google_sheets", args)
    assert SID in reason and "A2 > Alice" in reason and "B2 > 95" in reason
    assert key == f"google-access:sheets-edit:{SID}"


def test_edits_share_one_key_per_spreadsheet():
    edits = [
        {"action": "update", "spreadsheet_id": SID, "range": "A1", "values": [["x"]]},
        {"action": "update", "spreadsheet_id": SID, "range": "Z9", "values": [["y"]]},
        {"action": "append", "spreadsheet_id": SID, "range": "Log!A:C", "values": [["z"]]},
        {"action": "batch_update", "spreadsheet_id": SID, "data": [{"range": "B2", "values": [["w"]]}]},
        {"action": "add_sheet", "spreadsheet_id": SID, "title": "New"},
    ]
    keys = {access.approval_request("google_sheets", args)[1] for args in edits}
    assert keys == {f"google-access:sheets-edit:{SID}"}
    other = access.approval_request("google_sheets", dict(edits[0], spreadsheet_id=OTHER))[1]
    assert other == f"google-access:sheets-edit:{OTHER}"


def test_clear_and_create_still_ask_per_call():
    clear = {"action": "clear", "spreadsheet_id": SID, "range": "A1:B9"}
    key = access.approval_request("google_sheets", clear)[1]
    assert "sheets-edit" not in key and key.startswith("google-access:google_sheets:")
    assert access.approval_request("google_sheets", dict(clear, range="C1"))[1] != key
    create = access.approval_request("google_sheets", {"action": "create", "title": "Budget"})
    assert create[0] == "Create SpreadSheet: Budget" and "sheets-edit" not in create[1]
    clear_card = access.approval_request("google_sheets", clear)[0]
    assert clear_card == f"SpreadSheet: {SID}\nClear: A1:B9"


@pytest.mark.parametrize("sid", ["s", "abc", "x/../y", "a" * 300, "1AbC dEfGhIjK"])
def test_a_malformed_spreadsheet_id_is_blocked(sid):
    with pytest.raises(access.AccessError, match="spreadsheet id"):
        access.approval_request("google_sheets", {"action": "update", "spreadsheet_id": sid,
                                                  "range": "A1", "values": [["x"]]})


def test_a_write_without_values_is_blocked_before_asking():
    with pytest.raises(access.AccessError, match="values"):
        access.approval_request("google_sheets", {"action": "append", "spreadsheet_id": SID, "range": "A1"})
    with pytest.raises(access.AccessError, match="data"):
        access.approval_request("google_sheets", {"action": "batch_update", "spreadsheet_id": SID})
    with pytest.raises(access.AccessError, match="at most"):
        access.approval_request("google_sheets", {"action": "batch_update", "spreadsheet_id": SID, "data": [
            {"range": f"A{i}", "values": [["x"]]} for i in range(access.BATCH_LIMIT + 1)]})


@pytest.mark.parametrize("rng,expected", [
    ("bp候補!K3257:L3257", ("bp候補", "K3257:L3257")), ("'My ''Tab'''!A1", ("My 'Tab'", "A1")),
    ("Sheet1", ("Sheet1", "")), ("A1:B2", (None, "A1:B2")), ("C:C", (None, "C:C")), ("3:5", (None, "3:5"))])
def test_split_range(rng, expected):
    assert access.split_range(rng) == expected


def test_column_letters_round_trip():
    for index in (0, 25, 26, 51, 701, 702):
        assert access._column_index(access.column_letters(index)) == index
    assert access.column_letters(10) == "K" and access.column_letters(27) == "AB"


def context(monkeypatch, title="BP候補リスト", headers=None, names=None):
    calls = []

    def fake(home, sid, tabs):
        calls.append(tabs)
        return title, headers or {}, names if names is not None else list((headers or {}).keys())

    monkeypatch.setattr(access, "_sheet_context", fake)
    return calls


def test_card_shows_title_headers_and_cells(monkeypatch):
    context(monkeypatch, headers={"bp候補": ["id"] + [""] * 9 + ["確認メモ", "判定"]})
    reason, _ = access.approval_request("google_sheets", {
        "action": "update", "spreadsheet_id": SID, "range": "bp候補!K3257:L3257",
        "values": [["2026-10-02確認: 自社サイト sinarfajarempire.com にパッケージ・サービス(トイレ・リビング・寝室・台所)",
                    "【bp batch23】見送り_既存機能重複。"]]}, home=Path("/nonexistent"))
    lines = reason.split("\n")
    assert lines[:3] == ["SpreadSheet: BP候補リスト", "Sheet: bp候補", ""]
    assert lines[3].startswith("K3257 > 確認メモ: 2026-10-02確認") and lines[3].endswith("…")
    assert lines[4] == "L3257 > 判定: 【bp batch23】見送り_既存機能重複。"
    assert SID not in reason


def test_card_falls_back_to_ids_and_letters():
    reason, _ = access.approval_request("google_sheets", {
        "action": "append", "spreadsheet_id": SID, "range": "Log!B:C", "values": [["a", ""], ["b", None]]})
    assert SID in reason
    assert "B(+1) > a" in reason and "C(+1) > (empty)" in reason and "B(+2) > b" in reason


@pytest.mark.parametrize("fill", ["x", "&", "<", "😀"])
def test_card_stays_within_the_escaped_limit_and_counts_the_rest(fill):
    data = [{"range": f"S!A{i}:C{i}", "values": [[fill * 80, "y" * 80, "z" * 80]]} for i in range(1, 200)]
    reason, _ = access.approval_request("google_sheets", {"action": "batch_update", "spreadsheet_id": SID,
                                                         "data": data})
    assert access._units(reason) <= access.CARD_LIMIT
    shown = sum(1 for line in reason.split("\n") if line.startswith(("A", "B", "C")))
    assert f"(+{3 * 199 - shown} more cells)" in reason


def test_long_titles_and_many_tabs_keep_the_count(monkeypatch):
    context(monkeypatch, title="T" * 400, names=[f"tab{i}" for i in range(6)])
    data = [{"range": f"{'&' * 100}{i}!A1", "values": [["v"] * 40]} for i in range(6)]
    reason, _ = access.approval_request("google_sheets", {"action": "batch_update", "spreadsheet_id": SID,
                                                         "data": data}, home=Path("/x"))
    assert access._units(reason) <= access.CARD_LIMIT
    assert "more cells)" in reason and "\nSheet: " in reason
    assert access._tabs_summary(["a", "b", None, "d", "e"], ["First"]) == "a, b, First +2"
    assert access._tabs_summary([None]) == "(first sheet)"


def test_named_ranges_and_unknown_tabs_show_relative_positions(monkeypatch):
    context(monkeypatch, headers={"Data": ["Name", "Score"]}, names=["Data"])
    reason, _ = access.approval_request("google_sheets", {"action": "batch_update", "spreadsheet_id": SID, "data": [
        {"range": "MyRange", "values": [["a", "b"]]}, {"range": "Data", "values": [["c"]]}]}, home=Path("/x"))
    assert "R1C1 > a" in reason and "R1C2 > b" in reason and "A1 > Name: c" in reason
    reason, _ = access.approval_request("google_sheets", {"action": "update", "spreadsheet_id": SID,
                                                         "range": "Sheet1", "values": [["z"]]})
    assert "R1C1 > z" in reason



def test_sheet_context_is_cached_and_never_raises(tmp_path, monkeypatch):
    api = mock.MagicMock()
    api.spreadsheets().get().execute.return_value = {"properties": {"title": "Book"},
                                                     "sheets": [{"properties": {"title": "Main"}}]}
    api.spreadsheets().values().batchGet().execute.return_value = {"valueRanges": [{"values": [["Name"]]}]}
    calls = services(monkeypatch, sheets=api)
    assert access._sheet_context(tmp_path, SID, {None}) == ("Book", {"Main": ["Name"], None: ["Name"]}, ["Main"])
    assert access._sheet_context(tmp_path, SID, {"Main", "NamedRange"})[0] == "Book"
    assert len(calls) == 1
    assert api.spreadsheets().values().batchGet.call_args.kwargs["ranges"] == ["'Main'!1:1"]

    failures = []

    def broken(*a, **k):
        failures.append(1)
        raise access.AccessError("no token")

    monkeypatch.setattr(access, "_service", broken)
    assert access._sheet_context(tmp_path, OTHER, {"X"}) == (None, {}, None)
    assert access._sheet_context(tmp_path, OTHER, {"X"}) == (None, {}, None)
    assert failures == [1]  # a failure is remembered briefly, not retried on every edit
    assert access._sheet_context(None, OTHER, {"X"}) == (None, {}, None)


def test_a_slow_lookup_does_not_hold_up_the_hook(tmp_path, monkeypatch):
    import threading
    import time
    release = threading.Event()

    def slow(home, sid, tabs):
        release.wait(5)
        return "Late", {}, ["S"]

    monkeypatch.setattr(access, "_fetch_context", slow)
    monkeypatch.setattr(access, "CONTEXT_TIMEOUT", 0.1)
    started = time.monotonic()
    assert access._sheet_context(tmp_path, SID, {"S"}) == (None, {}, None)
    assert time.monotonic() - started < 1
    release.set()
    for _ in range(50):
        if SID in access._CONTEXT:
            break
        time.sleep(0.02)
    assert access._sheet_context(tmp_path, SID, {"S"})[0] == "Late"


def test_gmail_send_shows_recipients_and_body():
    assert access.approval_request("google_gmail", {"action": "search"}) is None
    reason, _ = access.approval_request("google_gmail", {
        "action": "send", "to": ["a@example.com"], "bcc": "b@example.com", "subject": "Hi", "body": "Hello"})
    assert "to: a@example.com" in reason and "bcc: b@example.com" in reason
    assert "subject: Hi" in reason and "body: Hello" in reason
    with pytest.raises(access.AccessError):
        access.approval_request("google_gmail", {"action": "send", "to": ["not-an-address"], "body": "x"})
    with pytest.raises(access.AccessError):
        access.approval_request("google_gmail", {"action": "send", "body": "x"})


def test_drive_upload_asks_and_refuses_credentials(tmp_path):
    assert access.approval_request("google_drive", {"action": "download", "file_id": "f"}) is None
    report = tmp_path / "report.pdf"
    report.write_bytes(b"%PDF")
    reason, _ = access.approval_request("google_drive", {"action": "upload", "path": str(report)})
    assert str(report) in reason and "4 bytes" in reason and "My Drive" in reason
    with pytest.raises(access.AccessError, match="not a file"):
        access.approval_request("google_drive", {"action": "upload", "path": str(tmp_path / "missing")})
    token(tmp_path)
    with pytest.raises(access.AccessError, match="credential"):
        access.approval_request("google_drive", {"action": "upload", "path": str(access.token_path(tmp_path))})


@pytest.mark.parametrize("tool,args", [
    ("google_gmail", {"action": "send ", "to": ["a@example.com"], "subject": "s", "body": "b"}),
    ("google_sheets", {"action": " clear", "spreadsheet_id": "s", "range": "A1"}),
    ("google_drive", {"action": "UPLOAD", "path": "/etc/hosts"}),
    ("google_sheets", {"spreadsheet_id": "s"}),
])
def test_noncanonical_actions_are_blocked_by_the_gate_and_the_engine(tool, args, tmp_path):
    with pytest.raises(access.AccessError, match="unknown action"):
        access.approval_request(tool, args)
    engine = {"google_gmail": access.gmail, "google_sheets": access.sheets, "google_drive": access.drive}[tool]
    with pytest.raises(access.AccessError, match="unknown action"):
        engine(tmp_path, args)


def test_long_reasons_are_capped():
    reason, _ = access.approval_request("google_gmail", {"action": "send", "to": ["a@example.com"],
                                                         "subject": "s" * 5000, "body": "b"})
    assert len(reason) <= access.REASON_LIMIT + 1


# --- bypass guard ---------------------------------------------------------------------------------

@pytest.mark.parametrize("command", [
    "gcloud projects list", "/opt/homebrew/bin/gcloud run deploy", "cd x && gsutil ls gs://b",
    "bq query 'select 1'", "gaccess check", "(gcloud auth print-access-token)",
    "cat ~/.config/gcloud/credentials.db", "CLOUDSDK_CONFIG=/tmp/x foo",
    "python3 ~/ghq/x/skills/productivity/google-workspace/scripts/google_api.py sheets get",
    "cat ~/.hermes/profiles/assistant/google-access/token.json",
    "ls ~/.hermes/profiles/assistant/google-access/gcloud"])
def test_terminal_bypass_is_blocked(command):
    assert access.bypass("terminal", {"command": command}) == access.BYPASS_MESSAGE


@pytest.mark.parametrize("command", ["ls ~/Workspaces", "git log --grep gcloudy", "echo mybq",
                                     "open ~/.hermes/profiles/assistant/google-downloads/a.pdf"])
def test_ordinary_terminal_commands_pass(command):
    assert access.bypass("terminal", {"command": command}) is None


@pytest.mark.parametrize("args", [
    {"command": "cat token.json", "workdir": "~/.hermes/profiles/assistant/google-access"},
    {"command": "cd ~/.hermes/profiles/assistant/google-access && cat token.json"},
    {"command": "cat ../token.json", "workdir": "~/.hermes/profiles/assistant/google-access/downloads"},
    {"command": "cat ~/.hermes/profiles/assistant/plugins/google-access/../../google-access/token.json"},
    {"command": "ls", "workdir": "/Users/me/.config/gcloud"}])
def test_working_directories_and_traversal_count(args):
    assert access.bypass("terminal", args) == access.BYPASS_MESSAGE


def test_the_plugin_source_stays_readable():
    assert access.bypass("read_file", {"path": "~/.config/hermes/plugins/google-access/access.py"}) is None


def test_file_tools_cannot_read_credentials():
    assert access.bypass("read_file", {"path": "~/.hermes/profiles/assistant/google-access/token.json"})
    assert access.bypass("search_files", {"pattern": "x", "path": "/Users/me/.config/gcloud"})
    assert access.bypass("read_file", {"path": "~/.hermes/profiles/assistant/google-access/downloads/../token.json"})
    assert access.bypass("read_file", {"path": "~/.hermes/profiles/assistant/google-downloads/a.csv"}) is None
    assert access.bypass("web_search", {"query": "gcloud run deploy"}) is None


# --- state and credentials ------------------------------------------------------------------------

def test_token_is_private(tmp_path):
    token(tmp_path)
    path = access.token_path(tmp_path)
    assert oct(path.stat().st_mode & 0o777) == "0o600"
    assert oct(path.parent.stat().st_mode & 0o777) == "0o700"


def test_concurrent_writes_never_share_a_temporary_file(tmp_path):
    import threading
    path = access.token_path(tmp_path)
    barrier = threading.Barrier(8)
    errors = []

    def write(n):
        try:
            barrier.wait()
            access._write_private(path, json.dumps({"n": n, "pad": "x" * 50000}))
        except Exception as exc:  # pragma: no cover - the assertion reports it
            errors.append(exc)

    threads = [threading.Thread(target=write, args=(n,)) for n in range(8)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    assert errors == []
    assert json.loads(path.read_text())["n"] in range(8)
    assert oct(path.stat().st_mode & 0o777) == "0o600"
    assert [p.name for p in path.parent.iterdir() if p.suffix == ".tmp"] == []


def test_concurrent_refreshes_are_serialized(tmp_path, monkeypatch):
    import threading
    import time
    credentials_module = pytest.importorskip("google.oauth2.credentials")
    token(tmp_path)
    refreshed = []

    class Fake:
        def __init__(self, info):
            self.info = info
            self.valid = info.get("token") == "fresh"
            self.refresh_token = info.get("refresh_token")

        @classmethod
        def from_authorized_user_info(cls, info, scopes=None):
            return cls(info)

        def refresh(self, request):
            time.sleep(0.05)
            refreshed.append(1)
            self.info = dict(self.info, token="fresh")

        def to_json(self):
            return json.dumps(self.info)

    monkeypatch.setattr(credentials_module, "Credentials", Fake)
    threads = [threading.Thread(target=access.credentials, args=(tmp_path, access.SHEETS)) for _ in range(6)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    assert refreshed == [1]
    stored = json.loads(access.token_path(tmp_path).read_text())
    assert stored["token"] == "fresh" and stored["scopes"] == list(access.SCOPES)


def test_missing_token_explains_setup(tmp_path):
    with pytest.raises(access.AccessError, match="gaccess auth"):
        access.credentials(tmp_path, access.SHEETS)


def test_missing_scope_is_reported(tmp_path):
    token(tmp_path, scopes=[access.SHEETS])
    with pytest.raises(access.AccessError, match="gmail.send"):
        access.credentials(tmp_path, access.GMAIL_SEND)


def test_download_dir_defaults_to_the_state_dir(tmp_path):
    assert access.download_dir(tmp_path) == tmp_path / "google-downloads"
    assert access.bypass("read_file", {"path": str(access.download_dir(tmp_path) / "a.pdf")}) is None


def test_download_dir_from_config(tmp_path):
    pytest.importorskip("yaml")
    (tmp_path / "config.yaml").write_text("google_access:\n  download_dir: ~/Inbox/google\n")
    assert access.download_dir(tmp_path) == Path(os.path.expanduser("~/Inbox/google"))


# --- services (fake Google clients) ---------------------------------------------------------------

def services(monkeypatch, **by_name):
    calls = []

    def service(home, name, version, scope):
        calls.append((name, scope))
        return by_name[name]

    monkeypatch.setattr(access, "_service", service)
    return calls


def test_sheets_update_types_values_like_the_ui(tmp_path, monkeypatch):
    api = mock.MagicMock()
    api.spreadsheets().values().update().execute.return_value = {"updatedRange": "S!A1:B2", "updatedCells": 4}
    calls = services(monkeypatch, sheets=api)
    result = access.sheets(tmp_path, {"action": "update", "spreadsheet_id": SID, "range": "S!A1",
                                      "values": [["=1+1", 2]]})
    assert result == {"ok": True, "spreadsheet_id": SID, "updated_range": "S!A1:B2", "updated_cells": 4}
    kwargs = api.spreadsheets().values().update.call_args.kwargs
    assert kwargs["valueInputOption"] == "USER_ENTERED" and kwargs["body"] == {"values": [["=1+1", 2]]}
    assert calls == [("sheets", access.SHEETS)]


def test_sheets_batch_update_writes_every_range_in_one_call(tmp_path, monkeypatch):
    api = mock.MagicMock()
    api.spreadsheets().values().batchUpdate().execute.return_value = {
        "responses": [{}, {}], "totalUpdatedRows": 2, "totalUpdatedCells": 4}
    services(monkeypatch, sheets=api)
    data = [{"range": "S!K1:L1", "values": [["a", "b"]]}, {"range": "S!K9:L9", "values": [["c", "d"]]}]
    result = access.sheets(tmp_path, {"action": "batch_update", "spreadsheet_id": SID, "data": data, "raw": True})
    assert result == {"ok": True, "spreadsheet_id": SID, "updated_ranges": 2, "updated_rows": 2,
                      "updated_cells": 4}
    kwargs = api.spreadsheets().values().batchUpdate.call_args.kwargs
    assert kwargs == {"spreadsheetId": SID, "body": {"valueInputOption": "RAW", "data": data}}
    with pytest.raises(access.AccessError, match="range, values"):
        access.sheets(tmp_path, {"action": "batch_update", "spreadsheet_id": SID,
                                 "data": [{"range": "A1", "values": [["x"]], "extra": 1}]})


def test_sheets_search_uses_read_only_drive(tmp_path, monkeypatch):
    drive = mock.MagicMock()
    drive.files().list().execute.return_value = {"files": [{"id": "1", "name": "Budget"}]}
    calls = services(monkeypatch, drive=drive)
    result = access.sheets(tmp_path, {"action": "search", "query": "Bud'get"})
    assert result["spreadsheets"][0]["name"] == "Budget"
    q = drive.files().list.call_args.kwargs["q"]
    assert access.SPREADSHEET_MIME in q and "name contains 'Bud\\'get'" in q
    assert calls == [("drive", access.DRIVE_READ)]


def b64(text):
    return base64.urlsafe_b64encode(text.encode()).decode().rstrip("=")


def test_gmail_get_prefers_plain_text_and_lists_attachments(tmp_path, monkeypatch):
    api = mock.MagicMock()
    api.users().messages().get().execute.return_value = {
        "id": "m1", "threadId": "t1", "labelIds": ["INBOX"], "payload": {
            "headers": [{"name": "From", "value": "a@x"}, {"name": "Subject", "value": "Hi"}],
            "mimeType": "multipart/mixed", "parts": [
                {"mimeType": "multipart/alternative", "parts": [
                    {"mimeType": "text/plain", "body": {"data": b64("plain body")}},
                    {"mimeType": "text/html", "body": {"data": b64("<p>html</p>")}}]},
                {"mimeType": "application/pdf", "filename": "a.pdf", "body": {"size": 10}}]}}
    services(monkeypatch, gmail=api)
    result = access.gmail(tmp_path, {"action": "get", "id": "m1"})
    assert result["body"] == "plain body" and result["subject"] == "Hi"
    assert result["attachments"] == [{"filename": "a.pdf", "mime_type": "application/pdf", "size": 10}]
    assert "untrusted" in result["note"]


def test_html_only_mail_is_reduced_to_text():
    text, _ = access._body({"mimeType": "text/html", "body": {"data": b64(
        "<style>p{}</style><p>Hello&amp;bye</p><script>x()</script>")}})
    assert text == "Hello&bye"


def test_gmail_reply_threads(tmp_path, monkeypatch):
    api = mock.MagicMock()
    api.users().messages().get().execute.return_value = {"threadId": "t9", "payload": {"headers": [
        {"name": "Message-ID", "value": "<orig@x>"}, {"name": "Subject", "value": "Plan"}]}}
    api.users().messages().send().execute.return_value = {"id": "new", "threadId": "t9"}
    calls = services(monkeypatch, gmail=api)
    result = access.gmail(tmp_path, {"action": "send", "to": ["b@example.com"], "body": "OK", "reply_to": "m1"})
    assert result == {"ok": True, "status": "sent", "id": "new", "thread_id": "t9"}
    sent = api.users().messages().send.call_args.kwargs["body"]
    assert sent["threadId"] == "t9"
    mail = message_from_bytes(base64.urlsafe_b64decode(sent["raw"]))
    assert mail["Subject"] == "Re: Plan" and mail["In-Reply-To"] == "<orig@x>"
    assert mail["To"] == "b@example.com"
    assert ("gmail", access.GMAIL_SEND) in calls


def test_drive_download_exports_google_docs(tmp_path, monkeypatch):
    http = pytest.importorskip("googleapiclient.http")
    api = mock.MagicMock()
    api.files().get().execute.return_value = {"id": "d1", "name": "Notes/2026",
                                              "mimeType": "application/vnd.google-apps.document"}

    class Downloader:
        def __init__(self, handle, request):
            self.handle = handle

        def next_chunk(self):
            self.handle.write(b"%PDF-1.7")
            return None, True

    monkeypatch.setattr(http, "MediaIoBaseDownload", Downloader)
    services(monkeypatch, drive=api)
    first = access.drive(tmp_path, {"action": "download", "file_id": "d1"})
    second = access.drive(tmp_path, {"action": "download", "file_id": "d1"})
    assert first["path"] == str(access.download_dir(tmp_path) / "Notes_2026.pdf")
    assert second["path"].endswith("Notes_2026 (2).pdf") and first["size"] == 8
    assert api.files().export_media.call_args.kwargs["mimeType"] == "application/pdf"


def test_downloads_reserve_names_and_never_write_through_a_symlink(tmp_path):
    folder = tmp_path / "dl"
    folder.mkdir()
    outside = tmp_path / "outside.txt"
    (folder / "a.txt").symlink_to(outside)            # dangling
    first, fd1 = access._reserve(folder / "a.txt")
    second, fd2 = access._reserve(folder / "a.txt")
    os.close(fd1)
    os.close(fd2)
    assert first.name == "a (2).txt" and second.name == "a (3).txt"
    assert not outside.exists()


def test_drive_upload_uses_the_app_file_scope(tmp_path, monkeypatch):
    http = pytest.importorskip("googleapiclient.http")
    report = tmp_path / "r.csv"
    report.write_text("a,b\n")
    api = mock.MagicMock()
    api.files().create().execute.return_value = {"id": "u1", "name": "r.csv"}
    monkeypatch.setattr(http, "MediaFileUpload", lambda path, mimetype, resumable: (path, mimetype))
    calls = services(monkeypatch, drive=api)
    result = access.drive(tmp_path, {"action": "upload", "path": str(report), "parent": "folder"})
    assert result["status"] == "uploaded"
    kwargs = api.files().create.call_args.kwargs
    assert kwargs["body"] == {"name": "r.csv", "parents": ["folder"]}
    assert kwargs["media_body"] == (str(report.resolve()), "text/csv")
    assert calls == [("drive", access.DRIVE_FILE)]


def test_unknown_actions_are_rejected(tmp_path):
    for engine in (access.sheets, access.gmail, access.drive):
        with pytest.raises(access.AccessError, match="unknown action"):
            engine(tmp_path, {"action": "delete"})



# --- row guards (expect) --------------------------------------------------------------------------

def guarded_api(found):
    """A Sheets client whose guard read returns ``found`` (one displayed value per guard)."""
    api = mock.MagicMock()
    values = api.spreadsheets().values()
    values.batchGet().execute.return_value = {"valueRanges": [
        {"values": [[v]]} if v is not None else {} for v in found]}
    values.batchUpdate().execute.return_value = {"responses": [{}], "totalUpdatedRows": 1, "totalUpdatedCells": 3}
    values.update().execute.return_value = {"updatedRange": "S!F2", "updatedCells": 1}
    values.clear().execute.return_value = {"clearedRange": "S!F2"}
    values.batchUpdate.reset_mock()
    values.update.reset_mock()
    values.clear.reset_mock()
    values.batchGet.reset_mock()
    return api, values


GUARDED = {"action": "batch_update", "spreadsheet_id": SID,
           "expect": [{"range": "bp候補!A2534", "value": "bp-2534"}, {"range": "bp候補!A2535", "value": 2535}],
           "data": [{"range": "bp候補!F2534", "values": [["自動返信"]]},
                    {"range": "bp候補!J2535", "values": [["2026-10-02"]]}]}


def test_matching_guards_let_the_write_through(tmp_path, monkeypatch):
    api, values = guarded_api([" bp-2534 ", "2535"])
    services(monkeypatch, sheets=api)
    result = access.sheets(tmp_path, GUARDED)
    assert result["ok"] and values.batchUpdate.call_count == 1
    kwargs = values.batchGet.call_args.kwargs
    assert kwargs["ranges"] == ["bp候補!A2534", "bp候補!A2535"]
    assert kwargs["valueRenderOption"] == "FORMATTED_VALUE"


@pytest.mark.parametrize("found", [["bp-2535", "2535"], ["bp-2534", None], ["bp-2534", "2536"]])
def test_one_mismatch_writes_nothing(tmp_path, monkeypatch, found):
    api, values = guarded_api(found)
    services(monkeypatch, sheets=api)
    with pytest.raises(access.AccessError, match="nothing written") as error:
        access.sheets(tmp_path, GUARDED)
    assert values.batchUpdate.call_count == 0
    assert "expected" in str(error.value) and "found" in str(error.value)


@pytest.mark.parametrize("action,extra,call", [
    ("update", {"range": "S!F2", "values": [["x"]]}, "update"),
    ("clear", {"range": "S!F2:G2"}, "clear")])
def test_update_and_clear_are_guarded_too(tmp_path, monkeypatch, action, extra, call):
    args = {"action": action, "spreadsheet_id": SID, "expect": [{"range": "S!A2", "value": True}], **extra}
    api, values = guarded_api(["FALSE"])
    services(monkeypatch, sheets=api)
    with pytest.raises(access.AccessError, match="expected 'TRUE', found 'FALSE'"):
        access.sheets(tmp_path, args)
    assert getattr(values, call).call_count == 0
    api, values = guarded_api(["TRUE"])
    services(monkeypatch, sheets=api)
    assert access.sheets(tmp_path, args)["ok"]
    assert getattr(values, call).call_count == 1


def test_without_expect_nothing_is_read_first(tmp_path, monkeypatch):
    api, values = guarded_api([])
    services(monkeypatch, sheets=api)
    access.sheets(tmp_path, {k: v for k, v in GUARDED.items() if k != "expect"})
    assert values.batchGet.call_count == 0 and values.batchUpdate.call_count == 1


@pytest.mark.parametrize("expect,message", [
    ("A1", "array"), ([{"range": "S!A1"}], "range, value"), ([{"range": "S!A1", "value": "x", "x": 1}], "range, value"),
    ([{"range": "S!A1:A2", "value": "x"}], "one cell"), ([{"range": "S!A", "value": "x"}], "one cell"),
    ([{"range": "S!A1", "value": None}], "text, a number"), ([{"range": "S!A1", "value": ["x"]}], "text, a number"),
    ([{"range": f"S!A{i}", "value": "x"} for i in range(1, access.EXPECT_LIMIT + 2)], "at most")])
def test_malformed_guards_are_blocked_before_asking(expect, message, tmp_path):
    args = dict(GUARDED, expect=expect)
    with pytest.raises(access.AccessError, match=message):
        access.approval_request("google_sheets", args)
    with pytest.raises(access.AccessError, match=message):
        access.sheets(tmp_path, args)


@pytest.mark.parametrize("args", [
    {"action": "append", "spreadsheet_id": SID, "range": "S!A:B", "values": [["x"]]},
    {"action": "add_sheet", "spreadsheet_id": SID, "title": "New"},
    {"action": "create", "title": "Budget"}])
def test_expect_is_refused_where_it_guards_nothing(args, tmp_path):
    args = dict(args, expect=[{"range": "S!A1", "value": "x"}])
    with pytest.raises(access.AccessError, match="expect applies to"):
        access.approval_request("google_sheets", args)
    with pytest.raises(access.AccessError, match="expect applies to"):
        access.sheets(tmp_path, args)


def test_the_card_shows_the_checks():
    reason, key = access.approval_request("google_sheets", GUARDED)
    lines = reason.split("\n")
    assert lines[2] == "Check: A2534 = bp-2534, A2535 = 2535" and lines[3] == ""
    assert key == f"google-access:sheets-edit:{SID}"
    many = dict(GUARDED, expect=[{"range": f"bp候補!A{i}", "value": f"id{i}"} for i in range(1, 7)])
    assert "Check: A1 = id1, A2 = id2, A3 = id3 (+3 more)" in access.approval_request("google_sheets", many)[0]
    clear = {"action": "clear", "spreadsheet_id": SID, "range": "S!F2", "expect": [{"range": "S!A2", "value": "k"}]}
    assert access.approval_request("google_sheets", clear)[0].endswith("Clear: S!F2\nCheck: A2 = k")


def test_checks_name_another_tab_and_the_first_sheet():
    args = dict(GUARDED, expect=[{"range": "Control!A2", "value": "on"}, {"range": "A9", "value": "k"},
                                 {"range": "bp候補!A2534", "value": "bp-2534"}])
    line = access.approval_request("google_sheets", args)[0].split("\n")[2]
    assert line == "Check: Control!A2 = on, (first sheet)!A9 = k, A2534 = bp-2534"
    two_tabs = dict(args, data=GUARDED["data"] + [{"range": "Other!B1", "values": [["x"]]}])
    assert "bp候補!A2534 = bp-2534" in access.approval_request("google_sheets", two_tabs)[0]


def test_long_checks_give_way_and_keep_the_count():
    args = dict(GUARDED, expect=[{"range": f"bp候補!A{i}", "value": "&" * 30} for i in range(1, 4)],
                data=[{"range": f"bp候補!B{i}", "values": [["v" * 40] * 3]} for i in range(1, 30)])
    reason = access.approval_request("google_sheets", args)[0]
    assert access._units(reason) <= access.CARD_LIMIT
    assert reason.split("\n")[2].startswith("Check: A1 = ") and "more cells)" in reason.split("\n")[-1]


@pytest.mark.parametrize("action,extra,call", [
    ("batch_update", {"data": GUARDED["data"]}, "batchUpdate"),
    ("update", {"range": "S!F2", "values": [["x"]]}, "update"),
    ("clear", {"range": "S!F2"}, "clear")])
@pytest.mark.parametrize("response", ["error", "short"])
def test_a_failed_guard_read_writes_nothing(tmp_path, monkeypatch, action, extra, call, response):
    args = {"action": action, "spreadsheet_id": SID, "expect": [{"range": "S!A2", "value": "k"}], **extra}
    api, values = guarded_api(["k"])
    if response == "error":
        values.batchGet().execute.side_effect = access.AccessError("Google API error 503: backend")
    else:
        values.batchGet().execute.return_value = {"valueRanges": []}
    services(monkeypatch, sheets=api)
    with pytest.raises(access.AccessError):
        access.sheets(tmp_path, args)
    assert getattr(values, call).call_count == 0


# --- info: tab details ----------------------------------------------------------------------------

@pytest.mark.parametrize("grid,text", [
    ({}, ""), ({"startColumnIndex": 1, "endColumnIndex": 4}, "B:D"), ({"startRowIndex": 2, "endRowIndex": 5}, "3:5"),
    ({"endRowIndex": 1, "endColumnIndex": 3}, "A1:C1"),
    ({"startRowIndex": 1, "startColumnIndex": 0, "endColumnIndex": 3}, "A2:C")])
def test_grid_ranges_read_back_as_a1(grid, text):
    assert access._a1(grid) == text


def test_info_lists_merges_tables_and_rules(tmp_path, monkeypatch):
    api = mock.MagicMock()
    api.spreadsheets().get().execute.return_value = {"properties": {"title": "Plan"}, "sheets": [dict(
        properties={"sheetId": 7, "title": "Tasks", "gridProperties": {
            "rowCount": 100, "columnCount": 8, "frozenRowCount": 1}},
        tables=[{"tableId": "t1", "name": "Todo", "range": {"sheetId": 7, "startRowIndex": 0, "endRowIndex": 5,
                                                            "startColumnIndex": 1, "endColumnIndex": 4},
                 "columnProperties": [
                     {"columnName": "Task"},
                     {"columnIndex": 1, "columnName": "State", "columnType": "DROPDOWN", "dataValidationRule": {
                         "condition": {"type": "ONE_OF_LIST", "values": [{"userEnteredValue": "Open"}]}}},
                     {"columnIndex": 2, "columnName": "Due", "columnType": "DATE"}]}],
        merges=[{"sheetId": 7, "endRowIndex": 1, "endColumnIndex": 2}],
        conditionalFormats=[
            {"ranges": [{"sheetId": 7, "startRowIndex": 1, "startColumnIndex": 3, "endColumnIndex": 4}],
             "booleanRule": {"condition": {"type": "NUMBER_GREATER", "values": [{"userEnteredValue": "10"}]}}},
            {"ranges": [{"sheetId": 7, "startColumnIndex": 1, "endColumnIndex": 2}], "gradientRule": {}}])]}
    services(monkeypatch, sheets=api)
    sheet = access.sheets(tmp_path, {"action": "info", "spreadsheet_id": SID})["sheets"][0]
    assert api.spreadsheets().get.call_args.kwargs["fields"] == access.INFO_FIELDS
    assert sheet["gridProperties"]["frozenRowCount"] == 1 and sheet["merges"] == ["A1:B1"]
    assert sheet["tables"] == [{"table_id": "t1", "name": "Todo", "range": "B1:D5", "columns": [
        {"column": "B", "name": "Task", "type": "TEXT"},
        {"column": "C", "name": "State", "type": "DROPDOWN", "options": ["Open"]},
        {"column": "D", "name": "Due", "type": "DATE"}]}]
    assert sheet["conditional_rules"] == [{"index": 0, "ranges": ["D2:D"], "rule": "NUMBER_GREATER 10"},
                                          {"index": 1, "ranges": ["B:B"], "rule": "colour scale"}]


# --- layout (spreadsheets.batchUpdate) ------------------------------------------------------------

META = {"sheets": [
    {"properties": {"title": "Main"}},  # sheetId 0 is omitted by the API
    {"properties": {"sheetId": 7, "title": "Tasks"}, "tables": [{
        "tableId": "t1", "name": "Todo", "range": {"sheetId": 7, "startRowIndex": 0, "endRowIndex": 5,
                                                   "startColumnIndex": 1, "endColumnIndex": 4},
        "columnProperties": [{"columnName": "Task"},
                             {"columnIndex": 1, "columnName": "State", "columnType": "DROPDOWN",
                              "dataValidationRule": {"condition": {"type": "ONE_OF_LIST", "values": [
                                  {"userEnteredValue": "Open"}]}}},
                             {"columnIndex": 2, "columnName": "Due", "columnType": "DATE"}]}]}]}


def layout(*ops, **extra):
    return {"action": "layout", "spreadsheet_id": SID, "ops": list(ops), **extra}


def requests(*ops):
    return access._layout_requests(access._ops(layout(*ops), "layout"), META)


@pytest.mark.parametrize("ref,grid", [
    ("", {}),
    ("B2", {"startColumnIndex": 1, "endColumnIndex": 2, "startRowIndex": 1, "endRowIndex": 2}),
    ("b2:d9", {"startColumnIndex": 1, "endColumnIndex": 4, "startRowIndex": 1, "endRowIndex": 9}),
    ("D9:B2", {"startColumnIndex": 1, "endColumnIndex": 4, "startRowIndex": 1, "endRowIndex": 9}),
    ("B:D", {"startColumnIndex": 1, "endColumnIndex": 4}),
    ("C", {"startColumnIndex": 2, "endColumnIndex": 3}),
    ("3:5", {"startRowIndex": 2, "endRowIndex": 5}),
    ("4", {"startRowIndex": 3, "endRowIndex": 4}),
    ("A2:C", {"startColumnIndex": 0, "endColumnIndex": 3, "startRowIndex": 1}),
    ("AA1:AB2", {"startColumnIndex": 26, "endColumnIndex": 28, "startRowIndex": 0, "endRowIndex": 2})])
def test_a1_references_become_grid_ranges(ref, grid):
    assert access._grid_ref(ref) == grid


@pytest.mark.parametrize("ref", ["A0", "A1:5", "1:B", "A1:", ":B2", "A1B", "ABCD1", "A1:B2:C3", "03:5"])
def test_malformed_a1_references_are_refused(ref):
    with pytest.raises(access.AccessError, match="not an A1 range"):
        access._grid_ref(ref)


def test_format_borders_and_sizes_become_requests():
    got = requests(
        {"op": "format", "range": "Tasks!A1:E1", "bold": True, "background": "#eee", "align": "center",
         "number_format": "currency", "pattern": "¥#,##0"},
        {"op": "format", "range": "D2:D", "reset": True, "color": "none"},
        {"op": "borders", "range": "Tasks!A1:B2", "sides": ["outer"], "style": "dashed", "color": "#f00"},
        {"op": "size", "range": "Tasks!B:D", "pixels": 140},
        {"op": "size", "range": "Tasks!2:3", "auto": True})
    first = got[0]["repeatCell"]
    assert first["range"] == {"sheetId": 7, "startColumnIndex": 0, "endColumnIndex": 5, "startRowIndex": 0,
                              "endRowIndex": 1}
    fmt = first["cell"]["userEnteredFormat"]
    assert fmt["textFormat"] == {"bold": True} and fmt["horizontalAlignment"] == "CENTER"
    assert fmt["backgroundColorStyle"] == {"rgbColor": {"red": 238 / 255, "green": 238 / 255, "blue": 238 / 255}}
    assert fmt["numberFormat"] == {"type": "CURRENCY", "pattern": "¥#,##0"}
    assert first["fields"].split(",") == [
        "userEnteredFormat.textFormat.bold", "userEnteredFormat.backgroundColor",
        "userEnteredFormat.backgroundColorStyle", "userEnteredFormat.horizontalAlignment",
        "userEnteredFormat.numberFormat"]
    # reset clears everything first; "none" clears the colour (both the legacy and the style field)
    assert got[1]["repeatCell"] == {"range": {"sheetId": 0, "startColumnIndex": 3, "endColumnIndex": 4,
                                              "startRowIndex": 1}, "cell": {}, "fields": "userEnteredFormat"}
    assert got[2]["repeatCell"]["cell"] == {"userEnteredFormat": {}}
    assert got[2]["repeatCell"]["fields"] == ("userEnteredFormat.textFormat.foregroundColor,"
                                              "userEnteredFormat.textFormat.foregroundColorStyle")
    borders = got[3]["updateBorders"]
    assert set(borders) == {"range", "top", "bottom", "left", "right"}
    assert borders["top"] == {"style": "DASHED", "colorStyle": {"rgbColor": {"red": 1.0, "green": 0.0, "blue": 0.0}}}
    assert got[4] == {"updateDimensionProperties": {"range": {"sheetId": 7, "dimension": "COLUMNS", "startIndex": 1,
                                                              "endIndex": 4},
                                                    "properties": {"pixelSize": 140}, "fields": "pixelSize"}}
    assert got[5] == {"autoResizeDimensions": {"dimensions": {"sheetId": 7, "dimension": "ROWS", "startIndex": 1,
                                                              "endIndex": 3}}}


def test_shape_ops_become_requests():
    got = requests(
        {"op": "insert", "range": "Tasks!5:6"}, {"op": "insert", "range": "A:A"},
        {"op": "delete", "range": "Tasks!C"}, {"op": "move", "range": "Tasks!2:3", "to": 10},
        {"op": "move", "range": "B:C", "to": "f"}, {"op": "merge", "range": "A1:C1", "merge": "rows"},
        {"op": "unmerge", "range": "A1:C1"}, {"op": "freeze", "sheet": "Tasks", "rows": 1, "columns": 0})
    assert got[0] == {"insertDimension": {"range": {"sheetId": 7, "dimension": "ROWS", "startIndex": 4, "endIndex": 6},
                                          "inheritFromBefore": True}}
    assert got[1]["insertDimension"]["inheritFromBefore"] is False  # nothing before column A
    assert got[2] == {"deleteDimension": {"range": {"sheetId": 7, "dimension": "COLUMNS", "startIndex": 2,
                                                    "endIndex": 3}}}
    assert got[3]["moveDimension"]["destinationIndex"] == 9 and got[4]["moveDimension"]["destinationIndex"] == 5
    assert got[5]["mergeCells"]["mergeType"] == "MERGE_ROWS" and got[6]["unmergeCells"]["range"]["sheetId"] == 0
    assert got[7] == {"updateSheetProperties": {
        "properties": {"sheetId": 7, "gridProperties": {"frozenRowCount": 1, "frozenColumnCount": 0}},
        "fields": "gridProperties.frozenRowCount,gridProperties.frozenColumnCount"}}


def test_tables_are_made_changed_and_deleted():
    made, changed, renamed, gone = requests(
        {"op": "table", "range": "Tasks!E1:G9", "table_columns": [
            {"column": "F", "type": "DROPDOWN", "values": ["Todo", "Done"]}, {"column": "G", "type": "date"}],
         "header_color": "#1A73E8", "band_colors": ["#FFFFFF", "#F1F3F4"]},
        {"op": "table_update", "table": "todo", "table_columns": [{"column": "C", "type": "TEXT"},
                                                             {"column": "D", "name": "Deadline"}]},
        {"op": "table_update", "table": "t1", "range": "B1:D20", "name": "Backlog"},
        {"op": "table_delete", "table": "t1"})
    table = made["addTable"]["table"]
    assert table["name"] == "Table2" and table["range"]["sheetId"] == 7  # unique default name
    assert table["columnProperties"] == [
        {"columnIndex": 1, "columnType": "DROPDOWN", "dataValidationRule": {"condition": {
            "type": "ONE_OF_LIST", "values": [{"userEnteredValue": "Todo"}, {"userEnteredValue": "Done"}]}}},
        {"columnIndex": 2, "columnType": "DATE"}]
    assert set(table["rowsProperties"]) == {"headerColorStyle", "firstBandColorStyle", "secondBandColorStyle"}
    # A change keeps every other column as it is and drops a dropdown's rule with the type.
    update = changed["updateTable"]
    assert update["fields"] == "columnProperties"
    assert update["table"]["columnProperties"] == [
        {"columnIndex": 0, "columnName": "Task"}, {"columnIndex": 1, "columnName": "State", "columnType": "TEXT"},
        {"columnIndex": 2, "columnName": "Deadline", "columnType": "DATE"}]
    assert renamed["updateTable"]["fields"] == "range,name"
    assert renamed["updateTable"]["table"]["range"]["sheetId"] == 7  # a range without a tab stays on the table's tab
    assert gone == {"deleteTable": {"tableId": "t1"}}


def test_typed_columns_keep_their_header_text(tmp_path, monkeypatch):
    """Sheets renames a typed column without a name to "Column 1", overwriting the header cell."""
    api, book = layout_api()
    book.values().get().execute.side_effect = [{"values": [["Task", "State", "Due"]]},
                                               {"values": [["Task", "State", "Due", "Due"]]}]
    book.values().get.reset_mock()
    services(monkeypatch, sheets=api)
    access.sheets(tmp_path, layout(
        {"op": "table", "range": "Tasks!E1:G9", "table_columns": [
            {"column": "F", "type": "DROPDOWN", "values": ["Open"]}, {"column": "G", "type": "DATE", "name": "When"}]},
        {"op": "table_update", "table": "Todo", "range": "B1:E5", "table_columns": [{"column": "E", "type": "TEXT"}]}))
    made, changed = book.batchUpdate.call_args.kwargs["body"]["requests"]
    assert made["addTable"]["table"]["columnProperties"] == [
        {"columnIndex": 1, "columnName": "State", "columnType": "DROPDOWN", "dataValidationRule": {
            "condition": {"type": "ONE_OF_LIST", "values": [{"userEnteredValue": "Open"}]}}},
        {"columnIndex": 2, "columnType": "DATE", "columnName": "When"}]
    assert changed["updateTable"]["table"]["columnProperties"][3] == {
        "columnIndex": 3, "columnName": "Due", "columnType": "TEXT"}  # the header of the column added to Todo
    reads = [c.kwargs["range"] for c in book.values().get.call_args_list]
    assert reads == ["'Tasks'!E1:G1", "'Tasks'!B1:E1"]


def test_one_op_covers_scattered_ranges():
    bold, widths, rule, check = (access._layout_requests(access._ops(layout(op), "layout"), META) for op in (
        {"op": "format", "ranges": ["Tasks!A1", "Tasks!C5:D6", "Main!F9"], "bold": True},
        {"op": "size", "ranges": ["Tasks!B:B", "Tasks!E:F"], "pixels": 90},
        {"op": "conditional", "ranges": ["Tasks!D2:D9", "Tasks!G2:G9"], "when": "NOT_BLANK", "italic": True},
        {"op": "validate", "ranges": ["B2:B9", "Tasks!C2:C9"], "when": "BOOLEAN"}))
    assert [r["repeatCell"]["range"]["sheetId"] for r in bold] == [7, 7, 0]
    assert bold[1]["repeatCell"]["range"] == {"sheetId": 7, "startColumnIndex": 2, "endColumnIndex": 4,
                                              "startRowIndex": 4, "endRowIndex": 6}
    assert [r["updateDimensionProperties"]["range"]["startIndex"] for r in widths] == [1, 4]
    assert len(rule) == 1 and [g["startColumnIndex"] for g in rule[0]["addConditionalFormatRule"]["rule"]["ranges"]] == [3, 6]
    assert [r["setDataValidation"]["range"]["sheetId"] for r in check] == [0, 7]


def test_scattered_deletions_run_bottom_up():
    got = requests({"op": "delete", "ranges": ["Tasks!5:5", "Tasks!12:13", "Tasks!2:2"]})
    assert [r["deleteDimension"]["range"]["startIndex"] for r in got] == [11, 4, 1]
    reason = access.approval_request("google_sheets", layout(
        {"op": "delete", "ranges": ["Tasks!5:5", "Tasks!12:13", "Tasks!2:2"]}))[0]
    assert reason.split("\n")[-1] == "Delete row 2, row 5, rows 12-13 with their contents"
    assert "sheets-edit" not in access.approval_request("google_sheets", layout(
        {"op": "delete", "ranges": ["Tasks!5:5"]}))[1]


@pytest.mark.parametrize("op,message", [
    ({"op": "delete", "ranges": ["3:5", "5:6"]}, "overlap"),
    ({"op": "delete", "ranges": ["3:3", "B:B"]}, "all rows or all columns"),
    ({"op": "size", "ranges": ["Tasks!B:B", "Main!C:C"], "pixels": 50}, "of one tab"),
    ({"op": "format", "range": "A1", "ranges": ["B2"], "bold": True}, "not both"),
    ({"op": "format", "ranges": [], "bold": True}, "range is required"),
    ({"op": "format", "ranges": ["A1", 3], "bold": True}, "array of A1 ranges"),
    ({"op": "insert", "ranges": ["3:3", "5:5"]}, "unknown field"),
    ({"op": "move", "ranges": ["3:3"], "to": 9}, "unknown field"),
    ({"op": "table", "ranges": ["A1:C9"]}, "unknown field")])
def test_malformed_multi_range_ops_are_blocked(op, message):
    with pytest.raises(access.AccessError, match=message):
        access.approval_request("google_sheets", layout(op))


def test_ranges_are_counted_against_the_batch_limit():
    many = [f"A{i}" for i in range(1, 301)]
    with pytest.raises(access.AccessError, match="at most 500 per call"):
        access.approval_request("google_sheets", layout({"op": "format", "ranges": many, "bold": True},
                                                        {"op": "format", "ranges": many, "italic": True}))


def test_the_card_names_a_shared_tab_once_and_counts_the_rest(monkeypatch):
    context(monkeypatch, title="Plan", names=["Main", "Tasks"])
    lines = access.approval_request("google_sheets", layout(
        {"op": "format", "ranges": [f"Tasks!A{i}" for i in range(1, 8)], "bold": True}), home=Path("/x"))[0].split("\n")
    assert lines == ["SpreadSheet: Plan", "Sheet: Tasks", "", "Format A1, A2, A3, A4 +3: bold"]
    lines = access.approval_request("google_sheets", layout(
        {"op": "format", "ranges": ["Tasks!A1", "Tasks!B2", "Main!C3"], "bold": True}), home=Path("/x"))[0].split("\n")
    assert lines == ["SpreadSheet: Plan", "", "Format Tasks!A1, Tasks!B2, Main!C3: bold"]
    assert access._where_all([{"tab": "T", "ref": "A1"}, {"tab": "T", "ref": "B2"}]) == "T!A1, B2"


def test_later_table_ops_in_a_batch_build_on_earlier_ones():
    first, second, moved, renamed, gone = requests(
        {"op": "table_update", "table": "Todo", "table_columns": [{"column": "C", "type": "TEXT"}]},
        {"op": "table_update", "table": "Todo", "table_columns": [{"column": "D", "name": "Deadline"}]},
        {"op": "table_update", "table": "Todo", "range": "C1:D9", "table_columns": [{"column": "D", "type": "TIME"}]},
        {"op": "table_update", "table": "Todo", "name": "Backlog"},
        {"op": "table_delete", "table": "Backlog"})
    assert second["updateTable"]["table"]["columnProperties"][1] == {
        "columnIndex": 1, "columnName": "State", "columnType": "TEXT"}  # the first change survives
    # The table now starts at C: B's column drops out and the rest shift left.
    assert moved["updateTable"]["table"]["columnProperties"] == [
        {"columnIndex": 0, "columnName": "State", "columnType": "TEXT"},
        {"columnIndex": 1, "columnName": "Deadline", "columnType": "TIME"}]
    assert renamed["updateTable"]["table"] == {"tableId": "t1", "name": "Backlog"}
    assert gone == {"deleteTable": {"tableId": "t1"}}
    with pytest.raises(access.AccessError, match="no single table named 'Todo'"):
        requests({"op": "table_delete", "table": "Todo"}, {"op": "table_update", "table": "Todo", "name": "X"})


def test_conditional_rules_and_input_rules_become_requests():
    rule, scale, drop, check, menu, ranged, cleared = requests(
        {"op": "conditional", "range": "Tasks!D2:D20", "when": "number_greater", "values": [10000],
         "background": "#F4CCCC", "bold": True},
        {"op": "conditional", "range": "B2:B9", "scale": ["#F00", "#FF0", "#0F0"]},
        {"op": "conditional_delete", "sheet": "Tasks", "index": 2},
        {"op": "validate", "range": "F2:F9", "when": "BOOLEAN"},
        {"op": "validate", "range": "C2:C9", "when": "ONE_OF_LIST", "values": ["Yes", "No"], "help": "Pick one"},
        {"op": "validate", "range": "E2:E9", "when": "ONE_OF_RANGE", "values": ["Lists!A1:A5"], "strict": False},
        {"op": "validate_clear", "range": "G2:G9"})
    added = rule["addConditionalFormatRule"]
    assert added["index"] == 0 and added["rule"]["ranges"][0]["sheetId"] == 7
    assert added["rule"]["booleanRule"] == {
        "condition": {"type": "NUMBER_GREATER", "values": [{"userEnteredValue": "10000"}]},
        "format": {"textFormat": {"bold": True}, "backgroundColorStyle": {"rgbColor": {
            "red": 244 / 255, "green": 204 / 255, "blue": 204 / 255}}}}
    gradient = scale["addConditionalFormatRule"]["rule"]["gradientRule"]
    assert [gradient[k]["type"] for k in ("minpoint", "midpoint", "maxpoint")] == ["MIN", "PERCENTILE", "MAX"]
    assert drop == {"deleteConditionalFormatRule": {"sheetId": 7, "index": 2}}
    assert check["setDataValidation"]["rule"] == {"condition": {"type": "BOOLEAN"}, "strict": True,
                                                  "showCustomUi": False}
    assert menu["setDataValidation"]["rule"]["showCustomUi"] is True
    assert menu["setDataValidation"]["rule"]["inputMessage"] == "Pick one"
    assert ranged["setDataValidation"]["rule"]["condition"]["values"] == [{"userEnteredValue": "=Lists!A1:A5"}]
    assert ranged["setDataValidation"]["rule"]["strict"] is False
    assert cleared == {"setDataValidation": {"range": {"sheetId": 0, "startColumnIndex": 6, "endColumnIndex": 7,
                                                       "startRowIndex": 1, "endRowIndex": 9}}}


def test_relative_dates_and_formulas_are_written_as_the_api_wants():
    assert access._condition("DATE_BEFORE", ["today", "2026-10-01"])["values"] == [
        {"relativeDate": "TODAY"}, {"userEnteredValue": "2026-10-01"}]
    assert access._condition("CUSTOM_FORMULA", ["$A2>3"])["values"] == [{"userEnteredValue": "=$A2>3"}]
    # Input rules have no relative dates: refused before asking rather than failing the batch.
    with pytest.raises(access.AccessError, match="only in conditional rules"):
        access.approval_request("google_sheets", layout(
            {"op": "validate", "range": "D2:D9", "when": "DATE_AFTER", "values": ["TODAY"]}))


def test_a_table_range_without_a_tab_is_shown_on_the_tables_own_tab(monkeypatch):
    context(monkeypatch, title="Plan", names=["Main", "Tasks"])
    reason = access.approval_request("google_sheets", layout(
        {"op": "table_update", "table": "Todo", "range": "B1:D20"}), home=Path("/x"))[0]
    assert reason.split("\n") == ["SpreadSheet: Plan", "", 'Change table "Todo": range B1:D20 on its tab']
    reason = access.approval_request("google_sheets", layout(
        {"op": "table_update", "table": "Todo", "range": "Tasks!B1:D20"},
        {"op": "format", "range": "Main!A1", "bold": True}), home=Path("/x"))[0]
    assert 'Change table "Todo": range Tasks!B1:D20' in reason


@pytest.mark.parametrize("op,message", [
    ({"op": "paint", "range": "A1"}, "op must be one of"),
    ({"op": "format", "range": "A1", "colour": "#fff"}, "unknown field"),
    ({"op": "format", "range": "A1"}, "at least one format field"),
    ({"op": "format"}, "range is required"),
    ({"op": "format", "range": "A1", "background": "red"}, "colour like"),
    ({"op": "format", "range": "A1", "bold": "yes"}, "true or false"),
    ({"op": "format", "range": "A1", "pattern": "0.0"}, "pattern needs number_format"),
    ({"op": "format", "range": "A1", "number_format": "MONEY"}, "number_format must be one of"),
    ({"op": "size", "range": "B2:C3", "pixels": 100}, "whole rows"),
    ({"op": "size", "range": "B:C"}, "pixels or auto"),
    ({"op": "size", "range": "B:C", "pixels": 100, "auto": True}, "pixels or auto"),
    ({"op": "delete", "range": "Tasks"}, "whole rows"),
    ({"op": "move", "range": "2:3", "to": "B"}, "row number"),
    ({"op": "move", "range": "B:C", "to": 3}, "column letter"),
    ({"op": "freeze", "sheet": "Tasks"}, "rows and/or columns"),
    ({"op": "table", "range": "A:C"}, "closed block"),
    ({"op": "table", "range": "A1:C9", "table_columns": [{"column": "D", "type": "TEXT"}]}, "outside the table"),
    ({"op": "table", "range": "A1:C9", "table_columns": [{"column": "B", "type": "NUMBER"}]}, "type must be one of"),
    ({"op": "table", "range": "A1:C9", "table_columns": [{"column": "B", "values": ["x"]}]}, "need type DROPDOWN"),
    ({"op": "table", "range": "A1:C9", "table_columns": [{"column": "B"}]}, "needs a type or a name"),
    ({"op": "table_update", "table": "Todo"}, "give range, name"),
    ({"op": "conditional", "range": "A1:A9", "when": "NUMBER_GREATER", "values": [1]}, "style to apply"),
    ({"op": "conditional", "range": "A1:A9", "scale": ["#fff"]}, "two or three"),
    ({"op": "conditional", "range": "A1:A9", "scale": ["#fff", "#000"], "bold": True}, "takes no when"),
    ({"op": "conditional", "range": "A1:A9", "when": "NUMBER_GREATER", "background": "none"}, "colour like"),
    ({"op": "conditional", "range": "A1:A9", "when": "NOT_BLANK", "underline": True}, "unknown field"),
    ({"op": "conditional_delete", "index": -1}, "whole number"),
    ({"op": "validate", "range": "A1:A9", "when": "ONE_OF_LIST"}, "needs values"),
    ({"op": "validate", "range": "A1:A9", "when": "IS_ANYTHING"}, "when must be one of"),
    ({"op": "validate", "range": "A1:A9", "when": "TEXT_EQ", "values": [{"x": 1}]}, "array of at most")])
def test_malformed_ops_are_blocked_before_asking(op, message, tmp_path):
    with pytest.raises(access.AccessError, match=message):
        access.approval_request("google_sheets", layout(op))
    with pytest.raises(access.AccessError, match=message):
        access.sheets(tmp_path, layout(op))


def test_ops_must_be_a_bounded_list():
    for ops in (None, [], "format", [{"op": "unmerge", "range": "A1"}] * (access.LAYOUT_LIMIT + 1)):
        with pytest.raises(access.AccessError, match="ops"):
            access.approval_request("google_sheets", {"action": "layout", "spreadsheet_id": SID, "ops": ops})


@pytest.mark.parametrize("op,message", [
    ({"op": "format", "range": "Nope!A1", "bold": True}, "no tab named 'Nope'"),
    ({"op": "table_delete", "table": "Missing"}, "no single table named"),
    ({"op": "table_update", "table": "Todo", "table_columns": [{"column": "F", "type": "TEXT"}]}, "outside table")])
def test_unknown_tabs_and_tables_are_refused_before_writing(op, message):
    with pytest.raises(access.AccessError, match=message):
        requests(op)


def test_non_destructive_layout_shares_the_spreadsheet_edit_approval():
    safe = layout({"op": "format", "range": "A1:C1", "bold": True}, {"op": "insert", "range": "3:4"},
                  {"op": "table", "range": "A1:C9"}, {"op": "unmerge", "range": "A1:C1"},
                  {"op": "validate", "range": "B2:B9", "when": "BOOLEAN"}, {"op": "freeze", "rows": 1})
    assert access.approval_request("google_sheets", safe)[1] == f"google-access:sheets-edit:{SID}"


@pytest.mark.parametrize("op", [
    {"op": "delete", "range": "3:4"}, {"op": "move", "range": "3:4", "to": 9}, {"op": "merge", "range": "A1:B1"},
    {"op": "table_delete", "table": "Todo"}, {"op": "conditional_delete", "index": 0}])
def test_a_call_that_deletes_or_moves_data_asks_every_time(op):
    args = layout({"op": "format", "range": "A1", "bold": True}, op)
    key = access.approval_request("google_sheets", args)[1]
    assert "sheets-edit" not in key and key.startswith("google-access:google_sheets:")
    assert access.approval_request("google_sheets", dict(args, ops=args["ops"][::-1]))[1] != key


def test_the_layout_card_lists_each_change(monkeypatch):
    context(monkeypatch, title="Plan", names=["Main", "Tasks"])
    args = layout({"op": "format", "range": "Tasks!A1:C1", "bold": True, "background": "#eee"},
                  {"op": "size", "range": "Tasks!B:C", "pixels": 120},
                  {"op": "delete", "range": "Tasks!4:5"},
                  {"op": "validate", "range": "Tasks!C2:C9", "when": "ONE_OF_LIST", "values": ["a", "b", "c", "d"]},
                  expect=[{"range": "Tasks!A4", "value": "k4"}])
    assert access.approval_request("google_sheets", args, home=Path("/x"))[0].split("\n") == [
        "SpreadSheet: Plan", "Sheet: Tasks", "Check: A4 = k4", "",
        "Format A1:C1: bold, background #EEEEEE",
        "Width of columns B-C: 120px",
        "Delete rows 4-5 with their contents",
        "Input rule on C2:C9: dropdown (a, b, c +1), reject other input"]
    mixed = layout({"op": "merge", "range": "A1:B1"}, {"op": "freeze", "sheet": "Tasks", "columns": 1},
                   {"op": "table_delete", "table": "Todo"})
    assert access.approval_request("google_sheets", mixed, home=Path("/x"))[0].split("\n") == [
        "SpreadSheet: Plan", "",
        "Merge (first sheet)!A1:B1 (only each block's top-left value stays)",
        "Freeze on Tasks: 1 column",
        "Delete table \"Todo\" with its contents"]


def test_the_layout_card_stays_within_the_limit():
    ops = [{"op": "format", "range": f"{'&' * 40}!A{i}", "bold": True, "font": "😀" * 30} for i in range(1, 80)]
    reason = access.approval_request("google_sheets", layout(*ops))[0]
    assert access._units(reason) <= access.CARD_LIMIT and "more changes)" in reason


def layout_api(found=()):
    api = mock.MagicMock()
    book = api.spreadsheets()
    book.get().execute.return_value = META
    book.batchUpdate().execute.return_value = {"replies": [{"addTable": {"table": {
        "tableId": "t9", "name": "Table2", "range": {"sheetId": 7, "endRowIndex": 9, "endColumnIndex": 3}}}}, {}]}
    book.values().batchGet().execute.return_value = {"valueRanges": [{"values": [[v]]} for v in found]}
    for call in (book.get, book.batchUpdate, book.values().batchGet):
        call.reset_mock()
    return api, book


def test_layout_runs_every_op_in_one_batch_update(tmp_path, monkeypatch):
    api, book = layout_api()
    calls = services(monkeypatch, sheets=api)
    result = access.sheets(tmp_path, layout({"op": "table", "range": "Tasks!A1:C9"},
                                            {"op": "format", "range": "Tasks!A1:C1", "bold": True}))
    assert result == {"ok": True, "spreadsheet_id": SID, "applied": 2,
                      "tables": [{"table_id": "t9", "name": "Table2", "range": "A1:C9"}]}
    assert book.get.call_args.kwargs == {"spreadsheetId": SID, "fields": access.LAYOUT_FIELDS}
    body = book.batchUpdate.call_args.kwargs["body"]
    assert [list(r) for r in body["requests"]] == [["addTable"], ["repeatCell"]]
    assert book.batchUpdate.call_count == 1 and calls == [("sheets", access.SHEETS)]


def test_layout_is_guarded_by_expect(tmp_path, monkeypatch):
    args = layout({"op": "delete", "range": "Tasks!4:4"}, expect=[{"range": "Tasks!A4", "value": "k4"}])
    api, book = layout_api(["k5"])
    services(monkeypatch, sheets=api)
    with pytest.raises(access.AccessError, match="nothing written"):
        access.sheets(tmp_path, args)
    assert book.batchUpdate.call_count == 0
    api, book = layout_api(["k4"])
    services(monkeypatch, sheets=api)
    assert access.sheets(tmp_path, args)["ok"] and book.batchUpdate.call_count == 1


# --- layout: tabs, visibility, notes, rich text, filters ------------------------------------------

TABS = {"sheets": [
    {"properties": {"title": "Main"}, "rowGroups": [
        {"range": {"dimension": "ROWS", "startIndex": 1, "endIndex": 10}, "depth": 1}]},
    {"properties": {"sheetId": 7, "title": "Tasks"},
     "filterViews": [{"filterViewId": 55, "title": "Open only",
                      "range": {"sheetId": 7, "startRowIndex": 0, "endRowIndex": 20,
                                "startColumnIndex": 0, "endColumnIndex": 4}}]}]}


def tab_requests(*ops, cell=None):
    return access._layout_requests(access._ops(layout(*ops), "layout"), TABS, cell=cell)


def test_hiding_and_grouping_become_requests():
    hide, show, group, fold_req, ungroup = (
        tab_requests({"op": "hide", "ranges": ["Tasks!C:C", "Tasks!E:F"]})[1],
        tab_requests({"op": "unhide", "range": "4:5"})[0],
        *tab_requests({"op": "group", "range": "Main!3:5", "collapsed": True}),
        tab_requests({"op": "ungroup", "range": "Main!3:5"})[0])
    assert hide == {"updateDimensionProperties": {
        "range": {"sheetId": 7, "dimension": "COLUMNS", "startIndex": 4, "endIndex": 6},
        "properties": {"hiddenByUser": True}, "fields": "hiddenByUser"}}
    assert show["updateDimensionProperties"]["properties"] == {"hiddenByUser": False}
    assert group == {"addDimensionGroup": {"range": {"sheetId": 0, "dimension": "ROWS", "startIndex": 2,
                                                     "endIndex": 5}}}
    # Rows 2-10 are already a group, so the new one is one level deeper.
    assert fold_req["updateDimensionGroup"]["dimensionGroup"]["depth"] == 2
    assert fold_req["updateDimensionGroup"]["fields"] == "collapsed"
    assert ungroup == {"deleteDimensionGroup": {"range": group["addDimensionGroup"]["range"]}}
    assert tab_requests({"op": "group", "range": "Tasks!B:C", "collapsed": True})[1][
        "updateDimensionGroup"]["dimensionGroup"]["depth"] == 1


def test_tab_ops_rename_colour_move_and_copy():
    renamed, moved, copied, formatted, titled = tab_requests(
        {"op": "sheet", "sheet": "Tasks", "title": "Done", "tab_color": "#0F0", "hidden": False},
        {"op": "sheet", "sheet": "Main", "position": 2, "tab_color": "none"},
        {"op": "sheet_duplicate", "sheet": "Done", "title": "Done copy", "position": 1},
        {"op": "format", "range": "'Done copy'!A1", "bold": True},
        {"op": "rename_spreadsheet", "title": "Plan 2026"})
    assert renamed["updateSheetProperties"]["properties"] == {
        "sheetId": 7, "title": "Done", "tabColorStyle": {"rgbColor": {"red": 0.0, "green": 1.0, "blue": 0.0}},
        "hidden": False}
    assert renamed["updateSheetProperties"]["fields"] == "title,tabColor,tabColorStyle,hidden"
    # Main moves from first to second: the API counts the target before the move.
    assert moved["updateSheetProperties"] == {"properties": {"sheetId": 0, "index": 2},
                                              "fields": "tabColor,tabColorStyle,index"}
    copy = copied["duplicateSheet"]
    assert copy["sourceSheetId"] == 7 and copy["newSheetName"] == "Done copy" and copy["insertSheetIndex"] == 0
    assert formatted["repeatCell"]["range"]["sheetId"] == copy["newSheetId"] not in (0, 7)
    assert titled == {"updateSpreadsheetProperties": {"properties": {"title": "Plan 2026"}, "fields": "title"}}
    with pytest.raises(access.AccessError, match="no tab named 'Tasks'"):
        tab_requests({"op": "sheet", "sheet": "Tasks", "title": "Done"}, {"op": "hide", "range": "Tasks!A:A"})
    with pytest.raises(access.AccessError, match="already exists"):
        tab_requests({"op": "sheet", "sheet": "Tasks", "title": "Main"})


def test_notes_and_cell_links():
    note, gone, link = tab_requests(
        {"op": "note", "ranges": ["Tasks!A1"], "text": "Owner: Ann"},
        {"op": "note", "range": "Tasks!B2:C3", "text": ""},
        {"op": "format", "range": "Tasks!D2", "link": "https://example.com/x", "rotation": "vertical",
         "padding": 4})
    assert note["repeatCell"]["cell"] == {"note": "Owner: Ann"} and note["repeatCell"]["fields"] == "note"
    assert gone["repeatCell"]["cell"] == {} and gone["repeatCell"]["fields"] == "note"
    fmt = link["repeatCell"]["cell"]["userEnteredFormat"]
    assert fmt["textFormat"] == {"link": {"uri": "https://example.com/x"}}
    assert fmt["textRotation"] == {"vertical": True} and fmt["padding"]["left"] == 4
    assert "userEnteredFormat.textFormat.link" in link["repeatCell"]["fields"]
    with pytest.raises(access.AccessError, match="give text"):
        tab_requests({"op": "note", "range": "A1"})
    with pytest.raises(access.AccessError, match="http"):
        tab_requests({"op": "format", "range": "A1", "link": "javascript:alert(1)"})


def test_rich_text_styles_parts_of_the_cell():
    (got,) = tab_requests({"op": "rich_text", "range": "Tasks!B2", "value": "絵😀 Total: ¥5,000 (see doc)",
                           "runs": [{"text": "doc", "link": "https://example.com"},
                                    {"text": "Total", "bold": True, "color": "#C00"}]})
    cell = got["updateCells"]["rows"][0]["values"][0]
    assert got["updateCells"]["fields"] == "userEnteredValue,textFormatRuns"
    assert cell["userEnteredValue"] == {"stringValue": "絵😀 Total: ¥5,000 (see doc)"}
    # Indices count UTF-16 units (the emoji is two), and each run ends back on the cell format.
    assert [r["startIndex"] for r in cell["textFormatRuns"]] == [4, 9, 23, 26]
    assert cell["textFormatRuns"][0]["format"]["bold"] is True and cell["textFormatRuns"][1]["format"] == {}
    reads = []

    def reader(grid):
        reads.append(grid)
        return "Call Ann today"

    (kept,) = tab_requests({"op": "rich_text", "range": "C3", "runs": [{"text": "Ann", "italic": True}]},
                           cell=reader)
    assert reads == [{"sheetId": 0, "startColumnIndex": 2, "endColumnIndex": 3, "startRowIndex": 2,
                      "endRowIndex": 3}]
    assert kept["updateCells"]["rows"][0]["values"][0]["userEnteredValue"] == {"stringValue": "Call Ann today"}
    for current in ("=A1&B1", 42, None):
        with pytest.raises(access.AccessError, match="no plain text"):
            tab_requests({"op": "rich_text", "range": "C3", "runs": [{"text": "x", "bold": True}]},
                         cell=lambda grid, current=current: current)


@pytest.mark.parametrize("op,message", [
    ({"op": "rich_text", "range": "A1:B2", "runs": [{"text": "x", "bold": True}]}, "one cell"),
    ({"op": "rich_text", "range": "A1", "value": "abc", "runs": [{"text": "z", "bold": True}]}, "not in the cell"),
    ({"op": "rich_text", "range": "A1", "value": "abc", "runs": [{"text": "a"}]}, "needs a style"),
    ({"op": "rich_text", "range": "A1", "value": "abc", "runs": [{"text": "a", "background": "#fff"}]}, "each run"),
    ({"op": "sheet", "sheet": "Tasks"}, "give title"),
    ({"op": "hide", "range": "A1:B2"}, "whole rows"),
    ({"op": "conditional", "ranges": ["Tasks!A1:A9", "Main!A1:A9"], "when": "NOT_BLANK", "bold": True}, "one tab"),
    ({"op": "filter", "range": "Tasks!A1:C9", "filter_columns": [{"column": "D", "hide": ["x"]}]}, "outside"),
    ({"op": "filter", "range": "A1:C9", "filter_columns": [{"column": "B"}]}, "needs hide or when"),
    ({"op": "filter_view_update", "view": "Open only"}, "give name, range"),
    ({"op": "filter_view_delete", "view": "Nope"}, "no single filter view")])
def test_malformed_tab_and_filter_ops_are_refused(op, message):
    with pytest.raises(access.AccessError, match=message):
        tab_requests(op)


def test_filters_and_filter_views_become_requests():
    basic, clear, view, change, drop = tab_requests(
        {"op": "filter", "range": "Tasks!A1:D20", "filter_columns": [
            {"column": "C", "hide": ["Done"]}, {"column": "D", "when": "NUMBER_GREATER", "values": ["10"]}]},
        {"op": "filter_clear", "sheet": "Tasks"},
        {"op": "filter_view", "name": "Mine", "range": "Tasks!A1:D20"},
        {"op": "filter_view_update", "view": "open only", "range": "A1:D40",
         "filter_columns": [{"column": "B", "when": "TEXT_CONTAINS", "values": ["Ann"]}]},
        {"op": "filter_view_delete", "view": "55"})
    specs = basic["setBasicFilter"]["filter"]["filterSpecs"]
    assert specs == [{"columnIndex": 2, "filterCriteria": {"hiddenValues": ["Done"]}},
                     {"columnIndex": 3, "filterCriteria": {"condition": {
                         "type": "NUMBER_GREATER", "values": [{"userEnteredValue": "10"}]}}}]
    assert clear == {"clearBasicFilter": {"sheetId": 7}}
    assert view["addFilterView"]["filter"] == {"title": "Mine", "filterSpecs": [], "range": {
        "sheetId": 7, "startColumnIndex": 0, "endColumnIndex": 4, "startRowIndex": 0, "endRowIndex": 20}}
    update = change["updateFilterView"]
    assert update["fields"] == "range,filterSpecs" and update["filter"]["filterViewId"] == 55
    assert update["filter"]["range"]["sheetId"] == 7  # a range without a tab stays on the view's tab
    assert drop == {"deleteFilterView": {"filterId": 55}}


def test_conditional_rules_can_be_replaced_by_number():
    (got,) = tab_requests({"op": "conditional_update", "index": 2, "range": "Tasks!D2:D9",
                           "when": "NUMBER_LESS", "values": [0], "color": "#C00"})
    assert got["updateConditionalFormatRule"]["sheetId"] == 7 and got["updateConditionalFormatRule"]["index"] == 2
    assert got["updateConditionalFormatRule"]["rule"]["booleanRule"]["condition"]["type"] == "NUMBER_LESS"


@pytest.mark.parametrize("op", [
    {"op": "conditional_update", "index": 0, "range": "A1:A9", "when": "NOT_BLANK", "bold": True},
    {"op": "filter_view_delete", "view": "Open only"},
    {"op": "note", "range": "A1:C9", "text": ""},
    {"op": "filter_view_update", "view": "Open only", "filter_columns": []}])
def test_replacing_a_rule_or_dropping_a_view_asks_every_time(op):
    assert "sheets-edit" not in access.approval_request("google_sheets", layout(op))[1]


def test_new_safe_ops_share_the_spreadsheet_edit_approval():
    args = layout({"op": "hide", "range": "3:4"}, {"op": "group", "range": "B:C"},
                  {"op": "sheet", "sheet": "Tasks", "tab_color": "#F00"},
                  {"op": "sheet_duplicate", "sheet": "Tasks"}, {"op": "rename_spreadsheet", "title": "X"},
                  {"op": "note", "range": "A1", "text": "n"},
                  {"op": "rich_text", "range": "A1", "value": "ab", "runs": [{"text": "a", "bold": True}]},
                  {"op": "filter", "range": "A1:C9"}, {"op": "filter_clear"},
                  {"op": "filter_view", "name": "v", "range": "A1:C9"},
                  {"op": "filter_view_update", "view": "v", "name": "w"},
                  {"op": "format", "range": "A1", "color": "theme:ACCENT1", "padding": {"top": 2}})
    assert access.approval_request("google_sheets", args)[1] == f"google-access:sheets-edit:{SID}"


def test_the_card_words_the_new_ops(monkeypatch):
    context(monkeypatch, title="Plan", names=["Main", "Tasks"])
    lines = access.approval_request("google_sheets", layout(
        {"op": "hide", "ranges": ["Tasks!C:C", "Tasks!E:F"]},
        {"op": "group", "range": "Tasks!3:5", "collapsed": True},
        {"op": "note", "range": "Tasks!A1", "text": "Owner: Ann"},
        {"op": "rich_text", "range": "Tasks!B2", "value": "Total: 5", "runs": [{"text": "Total", "bold": True}]},
        {"op": "filter", "range": "Tasks!A1:D9", "filter_columns": [{"column": "C", "hide": ["Done"]}]}),
        home=Path("/x"))[0].split("\n")
    assert lines == ["SpreadSheet: Plan", "Sheet: Tasks", "",
                     "Hide column C, columns E-F", "Group rows 3-5 (collapsed)", 'Note on A1: "Owner: Ann"',
                     'Replace text in B2 with "Total: 5": "Total" bold',
                     "Set the filter on A1:D9 (replaces any filter on the tab): C hide (Done)"]
    lines = access.approval_request("google_sheets", layout(
        {"op": "sheet", "sheet": "Tasks", "title": "Done", "position": 1},
        {"op": "rename_spreadsheet", "title": "Plan 2026"},
        {"op": "filter_view_update", "view": "Open only", "range": "A1:D9"},
        {"op": "sheet_duplicate", "sheet": "Main"}), home=Path("/x"))[0].split("\n")
    assert lines[2:] == ['Tab Tasks: rename to "Done", move to position 1', 'Rename spreadsheet to "Plan 2026"',
                         'Change filter view "Open only": range A1:D9 on its tab', "Duplicate tab Main next to it"]


def test_layout_reports_new_tabs_and_views(tmp_path, monkeypatch):
    api, book = layout_api()
    book.get().execute.return_value = TABS
    book.batchUpdate().execute.return_value = {"replies": [
        {"duplicateSheet": {"properties": {"sheetId": 99, "title": "Copy"}}},
        {"addFilterView": {"filter": {"filterViewId": 12, "title": "Mine"}}}]}
    services(monkeypatch, sheets=api)
    result = access.sheets(tmp_path, layout({"op": "sheet_duplicate", "sheet": "Tasks", "title": "Copy"},
                                            {"op": "filter_view", "name": "Mine", "range": "Tasks!A1:C9"}))
    assert result["sheets"] == [{"sheet_id": 99, "title": "Copy"}]
    assert result["filter_views"] == [{"view_id": 12, "name": "Mine"}]


def test_rich_text_reads_the_cell_as_entered(tmp_path, monkeypatch):
    api, book = layout_api()
    book.get().execute.return_value = TABS
    book.values().get().execute.return_value = {"values": [["Call Ann"]]}
    book.values().get.reset_mock()
    services(monkeypatch, sheets=api)
    access.sheets(tmp_path, layout({"op": "rich_text", "range": "Tasks!B2", "runs": [{"text": "Ann", "bold": True}]}))
    assert book.values().get.call_args.kwargs["range"] == "'Tasks'!B2"
    assert book.values().get.call_args.kwargs["valueRenderOption"] == "FORMULA"


# --- get_format -----------------------------------------------------------------------------------

def rgb(r, g, b):
    return {"rgbColor": {"red": r / 255, "green": g / 255, "blue": b / 255}}


HEADER = {"textFormat": {"bold": True, "foregroundColorStyle": rgb(255, 255, 255)},
          "backgroundColorStyle": rgb(26, 115, 232), "horizontalAlignment": "CENTER"}


def test_get_format_groups_cells_by_look_in_the_ops_words(tmp_path, monkeypatch):
    api = mock.MagicMock()
    api.spreadsheets().get().execute.return_value = {"sheets": [{"properties": {"title": "Tasks"}, "data": [{
        "startRow": 0, "startColumn": 1,
        "columnMetadata": [{"pixelSize": 100}, {"pixelSize": 180, "hiddenByUser": True}, {"pixelSize": 100}],
        "rowMetadata": [{"pixelSize": 21}, {"pixelSize": 40}, {"pixelSize": 21}],
        "rowData": [
            {"values": [{"userEnteredFormat": HEADER}, {"userEnteredFormat": HEADER}, {"userEnteredFormat": HEADER}]},
            {"values": [{"note": "check", "userEnteredFormat": {"numberFormat": {"type": "CURRENCY",
                                                                                "pattern": "¥#,##0"}}},
                        {"hyperlink": "https://example.com", "formattedValue": "see doc", "textFormatRuns": [
                            {"format": {}}, {"startIndex": 4, "format": {"link": {"uri": "https://example.com"}}}]},
                        {"dataValidation": {"condition": {"type": "BOOLEAN"}, "strict": True}}]},
            {"values": [{"userEnteredFormat": {"numberFormat": {"type": "CURRENCY", "pattern": "¥#,##0"}}}, {},
                        {"dataValidation": {"condition": {"type": "BOOLEAN"}, "strict": True}}]}]}]}]}
    services(monkeypatch, sheets=api)
    result = access.sheets(tmp_path, {"action": "get_format", "spreadsheet_id": SID, "range": "Tasks!B1:D3"})
    kwargs = api.spreadsheets().get.call_args.kwargs
    assert kwargs["ranges"] == ["Tasks!B1:D3"] and kwargs["fields"] == access.FORMAT_FIELDS
    (block,) = result["ranges"]
    assert block["range"] == "Tasks!B1:D3"
    assert block["styles"] == [
        {"bold": True, "color": "#FFFFFF", "background": "#1A73E8", "align": "CENTER", "ranges": ["B1:D1"]},
        {"number_format": "CURRENCY", "pattern": "¥#,##0", "ranges": ["B2:B3"]}]
    assert block["input_rules"] == [{"when": "BOOLEAN", "values": [], "strict": True, "dropdown": False,
                                     "ranges": ["D2:D3"]}]
    assert block["notes"] == {"B2": "check"} and block["links"] == {"C2": "https://example.com"}
    assert block["rich_text"] == {"C2": [{"text": "see "}, {"text": "doc", "link": "https://example.com"}]}
    assert block["hidden_columns"] == ["C"] and block["row_heights"] == {"2": 40}
    assert block["column_widths"] == {"B": 100, "C": 180, "D": 100}


@pytest.mark.parametrize("rng,message", [("Tasks!A:C", "closed blocks"), ("Tasks", "closed blocks"),
                                         ("Tasks!A1:Z100", "at most 2000")])
def test_get_format_reads_bounded_blocks_only(rng, message, tmp_path):
    with pytest.raises(access.AccessError, match=message):
        access.sheets(tmp_path, {"action": "get_format", "spreadsheet_id": SID, "range": rng})


def test_get_format_needs_no_approval():
    assert access.approval_request("google_sheets", {"action": "get_format", "spreadsheet_id": SID,
                                                     "range": "A1:B2"}) is None


def test_info_lists_groups_filters_views_and_tab_colours(tmp_path, monkeypatch):
    api = mock.MagicMock()
    api.spreadsheets().get().execute.return_value = {"sheets": [{
        "properties": {"sheetId": 7, "title": "Tasks", "hidden": True, "tabColorStyle": rgb(255, 0, 0),
                       "gridProperties": {"rowCount": 100, "columnCount": 8}},
        "rowGroups": [{"range": {"dimension": "ROWS", "startIndex": 2, "endIndex": 5}, "depth": 1, "collapsed": True}],
        "columnGroups": [{"range": {"dimension": "COLUMNS", "startIndex": 1, "endIndex": 3}, "depth": 1}],
        "basicFilter": {"range": {"sheetId": 7, "endRowIndex": 20, "endColumnIndex": 4}},
        "filterViews": [{"filterViewId": 55, "title": "Open only", "range": {"sheetId": 7, "endRowIndex": 20,
                                                                           "endColumnIndex": 4}}]}]}
    services(monkeypatch, sheets=api)
    sheet = access.sheets(tmp_path, {"action": "info", "spreadsheet_id": SID})["sheets"][0]
    assert sheet["hidden"] is True and sheet["tab_color"] == "#FF0000" and "tabColorStyle" not in sheet
    assert sheet["row_groups"] == [{"range": "3:5", "depth": 1, "collapsed": True}]
    assert sheet["column_groups"] == [{"range": "B:C", "depth": 1, "collapsed": False}]
    assert sheet["filter"] == {"range": "A1:D20"}
    assert sheet["filter_views"] == [{"view_id": 55, "name": "Open only", "range": "A1:D20"}]


def test_tab_positions_are_where_the_tab_ends_up():
    meta = {"sheets": [{"properties": {"sheetId": i, "title": name, "index": i}}
                       for i, name in enumerate(["A", "B", "C", "D"])]}
    got = access._layout_requests(access._ops(layout(
        {"op": "sheet", "sheet": "A", "position": 3},          # B C A D: API index 3 (before the move)
        {"op": "sheet", "sheet": "D", "position": 1},          # D B C A: API index 0
        {"op": "sheet_duplicate", "sheet": "B", "title": "B2"},  # D B B2 C A: right after B
        {"op": "sheet_duplicate", "sheet": "C", "position": 9}), "layout"), meta)  # clamped to the end
    assert [r["updateSheetProperties"]["properties"]["index"] for r in got[:2]] == [3, 0]
    assert got[2]["duplicateSheet"]["insertSheetIndex"] == 2 and got[3]["duplicateSheet"]["insertSheetIndex"] == 5


@pytest.mark.parametrize("prior", [{"op": "insert", "range": "Tasks!1:1"}, {"op": "delete", "range": "Main!9:9"},
                                   {"op": "move", "range": "B:B", "to": "E"},
                                   {"op": "rich_text", "range": "Tasks!b2", "value": "x", "runs": [{"text": "x", "bold": True}]}])
def test_rich_text_without_value_refuses_cells_an_earlier_op_may_change(prior):
    later = {"op": "rich_text", "range": "Tasks!B2", "runs": [{"text": "Ann", "bold": True}]}
    with pytest.raises(access.AccessError, match="needs value"):
        access.approval_request("google_sheets", layout(prior, later))
    assert access.approval_request("google_sheets", layout(prior, dict(later, value="Ann")))


def test_regrouping_after_ungroup_collapses_the_new_group():
    got = tab_requests({"op": "ungroup", "range": "Main!2:10"},
                       {"op": "group", "range": "Main!2:10", "collapsed": True})
    assert got[2]["updateDimensionGroup"]["dimensionGroup"]["depth"] == 1


def test_theme_colours_and_side_padding_round_trip():
    (got,) = tab_requests({"op": "format", "range": "A1", "background": "theme:accent2",
                           "padding": {"top": 2, "left": 8}})
    fmt = got["repeatCell"]["cell"]["userEnteredFormat"]
    assert fmt["backgroundColorStyle"] == {"themeColor": "ACCENT2"} and fmt["padding"] == {"top": 2, "left": 8}
    assert access._format_words({"textFormat": {"bold": False, "foregroundColorStyle": {"themeColor": "TEXT"}},
                                 "textRotation": {"angle": 0}}) == {"bold": False, "color": "theme:TEXT",
                                                                    "rotation": 0}
    with pytest.raises(access.AccessError, match="colour like"):
        tab_requests({"op": "format", "range": "A1", "color": "theme:PURPLE"})


# --- data (contents that move or change) ----------------------------------------------------------

def data(*ops, **extra):
    return {"action": "data", "spreadsheet_id": SID, "ops": list(ops), **extra}


def data_requests(*ops):
    return access._data_requests(access._ops(data(*ops), "data"), META)


def test_sort_keeps_the_header_row_and_uses_sheet_columns():
    (got,) = data_requests({"op": "sort", "range": "Tasks!A1:D20", "by": [{"column": "C"},
                                                                         {"column": "d", "order": "desc"}]})
    assert got == {"sortRange": {"range": {"sheetId": 7, "startColumnIndex": 0, "endColumnIndex": 4,
                                           "startRowIndex": 1, "endRowIndex": 20},
                                 "sortSpecs": [{"dimensionIndex": 2, "sortOrder": "ASCENDING"},
                                               {"dimensionIndex": 3, "sortOrder": "DESCENDING"}]}}
    (whole,) = data_requests({"op": "sort", "range": "A2:C", "by": [{"column": "B"}], "header": False})
    assert whole["sortRange"]["range"]["startRowIndex"] == 1


def test_find_replace_scopes():
    ranged, tab, everywhere = data_requests(
        {"op": "find_replace", "find": "Todo", "replacement": "Open", "range": "Tasks!C:C", "whole_cell": True},
        {"op": "find_replace", "find": "a+", "replacement": "", "sheet": "Tasks", "regex": True},
        {"op": "find_replace", "find": "2025", "replacement": "2026", "all_sheets": True, "formulas": True})
    assert ranged["findReplace"] == {"find": "Todo", "replacement": "Open", "matchCase": False,
                                     "matchEntireCell": True, "searchByRegex": False, "includeFormulas": False,
                                     "range": {"sheetId": 7, "startColumnIndex": 2, "endColumnIndex": 3}}
    assert tab["findReplace"]["sheetId"] == 7 and tab["findReplace"]["searchByRegex"] is True
    assert everywhere["findReplace"]["allSheets"] is True and everywhere["findReplace"]["includeFormulas"] is True


def test_copy_and_cut_cover_exactly_the_source_size():
    copied, flipped, moved = data_requests(
        {"op": "copy", "range": "Tasks!A1:D5", "to": "Main!F2", "paste": "values"},
        {"op": "copy", "range": "Tasks!A1:D5", "to": "H1", "transpose": True},
        {"op": "cut", "range": "Tasks!A1:B2", "to": "Tasks!J10"})
    assert copied["copyPaste"]["destination"] == {"sheetId": 0, "startRowIndex": 1, "endRowIndex": 6,
                                                  "startColumnIndex": 5, "endColumnIndex": 9}
    assert copied["copyPaste"]["pasteType"] == "PASTE_VALUES"
    # No tab on "to": the source's tab; transposed, 5x4 becomes 4x5.
    assert flipped["copyPaste"]["destination"] == {"sheetId": 7, "startRowIndex": 0, "endRowIndex": 4,
                                                   "startColumnIndex": 7, "endColumnIndex": 12}
    assert flipped["copyPaste"]["pasteOrientation"] == "TRANSPOSE"
    assert moved["cutPaste"]["destination"] == {"sheetId": 7, "rowIndex": 9, "columnIndex": 9}


def test_dedupe_trim_split_and_fill():
    dedupe, trim_a, trim_b, split, custom, fill, up = data_requests(
        {"op": "dedupe", "range": "Tasks!A1:D50", "compare": ["B", "C"]},
        {"op": "trim", "ranges": ["Tasks!A:A", "Main!B2:B9"]},
        {"op": "split_text", "range": "Tasks!E2:E50", "delimiter": "comma"},
        {"op": "split_text", "range": "Tasks!F2:F50", "delimiter": " / "},
        {"op": "autofill", "range": "Tasks!A2:B3", "fill": 10},
        {"op": "autofill", "range": "Tasks!A20:A21", "fill": 5, "direction": "up"})
    assert dedupe["deleteDuplicates"]["range"]["startRowIndex"] == 1  # the header row is never compared
    assert [c["startIndex"] for c in dedupe["deleteDuplicates"]["comparisonColumns"]] == [1, 2]
    assert [r["trimWhitespace"]["range"]["sheetId"] for r in (trim_a, trim_b)] == [7, 0]
    assert split["textToColumns"] == {"source": {"sheetId": 7, "startColumnIndex": 4, "endColumnIndex": 5,
                                                 "startRowIndex": 1, "endRowIndex": 50}, "delimiterType": "COMMA"}
    assert custom["textToColumns"]["delimiterType"] == "CUSTOM" and custom["textToColumns"]["delimiter"] == " / "
    assert fill["autoFill"]["sourceAndDestination"]["fillLength"] == 10
    assert up["autoFill"]["sourceAndDestination"] == {
        "source": {"sheetId": 7, "startColumnIndex": 0, "endColumnIndex": 1, "startRowIndex": 19, "endRowIndex": 21},
        "dimension": "ROWS", "fillLength": -5}


def test_every_data_call_asks_every_time(monkeypatch):
    context(monkeypatch, title="Plan", names=["Main", "Tasks"])
    args = data({"op": "trim", "range": "Tasks!A1:A9"}, expect=[{"range": "Tasks!A2", "value": "t1"}])
    reason, key = access.approval_request("google_sheets", args, home=Path("/x"))
    assert "sheets-edit" not in key and key.startswith("google-access:google_sheets:")
    assert reason.split("\n") == ["SpreadSheet: Plan", "Sheet: Tasks", "Check: A2 = t1", "",
                                  "Trim surrounding and repeated spaces in A1:A9"]


def test_the_data_card_says_what_is_overwritten(monkeypatch):
    context(monkeypatch, title="Plan", names=["Main", "Tasks"])
    ops = [{"op": "sort", "range": "Tasks!A1:D20", "by": [{"column": "C", "order": "DESC"}]},
           {"op": "find_replace", "find": "Todo", "range": "Tasks!C2:C20", "match_case": True},
           {"op": "copy", "range": "Tasks!A1:D5", "to": "Main!F2", "paste": "VALUES"},
           {"op": "cut", "range": "Tasks!A1:B2", "to": "J10"}]
    lines = access.approval_request("google_sheets", data(*ops), home=Path("/x"))[0].split("\n")
    assert lines == [
        "SpreadSheet: Plan", "Sheet: Tasks", "",
        "Sort A1:D20 by C descending, keeping row 1 as the header",
        'Replace "Todo" with nothing (removes it) in C2:C20 (match case)',
        "Copy A1:D5 to Main!F2:I6 (values only), overwriting it",
        "Move A1:B2 to J10:K11, overwriting it; the source is left empty"]
    lines = access.approval_request("google_sheets", data(
        {"op": "dedupe", "range": "Tasks!A1:D50", "compare": ["B"]},
        {"op": "split_text", "range": "Tasks!E2:E9"},
        {"op": "autofill", "range": "Tasks!A2:B3", "fill": 3, "direction": "RIGHT"},
        {"op": "find_replace", "find": "x", "replacement": "y", "all_sheets": True}), home=Path("/x"))[0].split("\n")
    assert lines == [
        "SpreadSheet: Plan", "",
        "Delete duplicate rows in Tasks!A1:D50 by B (the first of each stays), keeping row 1 as the header",
        "Split Tasks!E2:E9 on the detected separator into the columns to its right, overwriting them",
        "Fill right from Tasks!A2:B3 into Tasks!C2:E3, overwriting it",
        'Replace "x" with "y" in every tab']


@pytest.mark.parametrize("op,message", [
    ({"op": "sort", "range": "A1:D9", "by": [{"column": "F"}]}, "outside the range"),
    ({"op": "sort", "range": "A1:D1", "by": [{"column": "A"}]}, "only its header row"),
    ({"op": "sort", "range": "A1:D9", "by": [{"column": "A", "order": "up"}]}, "ASC or DESC"),
    ({"op": "sort", "range": "A1:D9", "by": []}, "by is required"),
    ({"op": "find_replace", "find": "x"}, "exactly one of"),
    ({"op": "find_replace", "find": "x", "range": "A1:B2", "sheet": "Tasks"}, "exactly one of"),
    ({"op": "find_replace", "find": "x", "all_sheets": False}, "exactly one of"),
    ({"op": "find_replace", "find": "", "sheet": "Tasks"}, "find is required"),
    ({"op": "copy", "range": "A:D", "to": "F1"}, "closed block"),
    ({"op": "copy", "range": "A1:D5", "to": "F1:G2"}, "top-left cell"),
    ({"op": "cut", "range": "A1:D5", "to": "F1", "transpose": True}, "unknown field"),
    ({"op": "dedupe", "range": "A1:D9", "compare": ["Z"]}, "outside the range"),
    ({"op": "split_text", "range": "A2:B9"}, "one column"),
    ({"op": "autofill", "range": "A2:A3", "fill": 5, "direction": "UP"}, "past the first row"),
    ({"op": "autofill", "range": "A:A", "fill": 5}, "closed block"),
    ({"op": "format", "range": "A1", "bold": True}, "op must be one of")])
def test_malformed_data_ops_are_refused_before_asking(op, message):
    with pytest.raises(access.AccessError, match=message):
        access.approval_request("google_sheets", data(op))


def test_data_ops_are_not_layout_ops():
    with pytest.raises(access.AccessError, match="op must be one of"):
        access.approval_request("google_sheets", layout({"op": "trim", "range": "A1:A9"}))


def test_data_reports_counts_and_honours_expect(tmp_path, monkeypatch):
    args = data({"op": "find_replace", "find": "a", "replacement": "b", "sheet": "Tasks"},
                {"op": "dedupe", "range": "Tasks!A1:D9"}, {"op": "trim", "range": "Tasks!A1:A9"},
                expect=[{"range": "Tasks!A2", "value": "t1"}])
    api, book = layout_api(["t9"])
    services(monkeypatch, sheets=api)
    with pytest.raises(access.AccessError, match="nothing written"):
        access.sheets(tmp_path, args)
    assert book.batchUpdate.call_count == 0
    api, book = layout_api(["t1"])
    book.batchUpdate().execute.return_value = {"replies": [
        {"findReplace": {"occurrencesChanged": 4, "valuesChanged": 3, "rowsChanged": 3, "sheetsChanged": 1}},
        {"deleteDuplicates": {"duplicatesRemovedCount": 2}}, {"trimWhitespace": {"cellsChangedCount": 5}}]}
    book.batchUpdate.reset_mock()
    services(monkeypatch, sheets=api)
    result = access.sheets(tmp_path, args)
    assert result["results"] == [
        {"op": "find_replace", "occurrences": 4, "cells": 3, "formulas": 0, "rows": 3, "tabs": 1},
        {"op": "dedupe", "rows_removed": 2}, {"op": "trim", "cells_changed": 5}]
    assert [list(r) for r in book.batchUpdate.call_args.kwargs["body"]["requests"]] == [
        ["findReplace"], ["deleteDuplicates"], ["trimWhitespace"]]


def test_deleting_a_tab_asks_every_time_and_later_ops_cannot_use_it():
    args = layout({"op": "format", "range": "Tasks!A1", "bold": True}, {"op": "sheet_delete", "sheet": "Main"})
    reason, key = access.approval_request("google_sheets", args)
    assert "sheets-edit" not in key and reason.endswith("Delete tab Main with all its contents")
    renamed, dropped = tab_requests({"op": "sheet", "sheet": "Main", "title": "Old"},
                                    {"op": "sheet_delete", "sheet": "Old"})
    assert dropped == {"deleteSheet": {"sheetId": 0}}
    for later in ({"op": "hide", "range": "Old!A:A"}, {"op": "hide", "range": "A:A"}):
        with pytest.raises(access.AccessError, match="no tab named|deleted earlier"):
            tab_requests({"op": "sheet_delete", "sheet": "Main"}, later)
    with pytest.raises(access.AccessError, match="at least one tab"):
        tab_requests({"op": "sheet_delete", "sheet": "Main"}, {"op": "sheet_delete", "sheet": "Tasks"})
    with pytest.raises(access.AccessError, match="no single filter view"):
        tab_requests({"op": "sheet_delete", "sheet": "Tasks"}, {"op": "filter_view_delete", "view": "Open only"})


def test_a_copy_without_a_title_keeps_the_last_tab_guard_honest():
    one = {"sheets": [{"properties": {"sheetId": 3, "title": "Main", "index": 0}}]}
    copy, gone = access._layout_requests(access._ops(layout(
        {"op": "sheet_duplicate", "sheet": "Main"}, {"op": "sheet_delete", "sheet": "Main"}), "layout"), one)
    assert gone == {"deleteSheet": {"sheetId": 3}} and copy["duplicateSheet"]["sourceSheetId"] == 3


def test_a_view_moved_to_another_tab_survives_deleting_its_old_tab():
    *_, kept = tab_requests({"op": "filter_view_update", "view": "Open only", "range": "Main!A1:C9"},
                            {"op": "sheet_delete", "sheet": "Tasks"}, {"op": "filter_view_delete", "view": "Open only"})
    assert kept == {"deleteFilterView": {"filterId": 55}}


def test_card_literals_keep_whitespace_and_overlapping_moves_say_so(monkeypatch):
    context(monkeypatch, title="Plan", names=["Main", "Tasks"])
    lines = access.approval_request("google_sheets", data(
        {"op": "find_replace", "find": "a  b\t", "replacement": "\n", "sheet": "Tasks"},
        {"op": "split_text", "range": "Tasks!E2:E9", "delimiter": " / "},
        {"op": "cut", "range": "Tasks!A1:A3", "to": "A2"}), home=Path("/x"))[0].split("\n")
    assert lines[3:] == ['Replace "a  b\\t" with "\\n" in whole tab',
                         'Split E2:E9 on " / " into the columns to its right, overwriting them',
                         "Move A1:A3 to A2:A4, overwriting it; source cells outside it are left empty"]


# --- charts and pivot tables ----------------------------------------------------------------------

CHARTS = {"sheets": [
    {"properties": {"title": "Main"}},
    {"properties": {"sheetId": 7, "title": "Tasks"}, "charts": [{
        "chartId": 31, "spec": {"title": "Sales", "basicChart": {
            "chartType": "COLUMN", "legendPosition": "BOTTOM_LEGEND", "headerCount": 1,
            "domains": [{"domain": {"sourceRange": {"sources": [{"sheetId": 7, "startColumnIndex": 0,
                                                                 "endColumnIndex": 1, "endRowIndex": 7}]}}}],
            "series": [{"series": {"sourceRange": {"sources": [{"sheetId": 7, "startColumnIndex": 1,
                                                                "endColumnIndex": 2, "endRowIndex": 7}]}},
                        "targetAxis": "LEFT_AXIS"}]}},
        "position": {"overlayPosition": {"anchorCell": {"sheetId": 7, "rowIndex": 0, "columnIndex": 5},
                                         "widthPixels": 480, "heightPixels": 300}}}]}]}


def objects(action, *ops, **extra):
    return {"action": action, "spreadsheet_id": SID, "ops": list(ops), **extra}


def object_requests(action, *ops, pivot=None):
    return access._object_requests(access._ops(objects(action, *ops), action), CHARTS, pivot=pivot)


def test_charts_take_labels_then_one_series_per_column():
    column, pie, combo = object_requests(
        "chart", {"op": "chart", "range": "Tasks!A1:C7", "title": "Sales"},
        {"op": "chart", "range": "Tasks!A1:B7", "chart_type": "pie", "at": "Main!H2", "width": 400, "legend": "none"},
        {"op": "chart", "range": "Tasks!A:D", "chart_type": "COMBO", "stacked": True, "new_sheet": True})
    chart = column["addChart"]["chart"]
    basic = chart["spec"]["basicChart"]
    assert chart["spec"]["title"] == "Sales" and basic["chartType"] == "COLUMN" and basic["headerCount"] == 1
    assert basic["domains"][0]["domain"]["sourceRange"]["sources"][0]["endColumnIndex"] == 1
    assert [s["series"]["sourceRange"]["sources"][0]["startColumnIndex"] for s in basic["series"]] == [1, 2]
    # Next to the data: the column after it, level with its top row, at Sheets' default size.
    assert chart["position"] == {"overlayPosition": {"anchorCell": {"sheetId": 7, "rowIndex": 0, "columnIndex": 3},
                                                     "widthPixels": 600, "heightPixels": 371}}
    pie_chart = pie["addChart"]["chart"]
    assert pie_chart["spec"]["pieChart"]["legendPosition"] == "NO_LEGEND"
    assert pie_chart["spec"]["pieChart"]["domain"]["sourceRange"]["sources"][0]["startRowIndex"] == 1  # header out
    assert pie_chart["position"]["overlayPosition"]["anchorCell"] == {"sheetId": 0, "rowIndex": 1, "columnIndex": 7}
    assert pie_chart["position"]["overlayPosition"]["widthPixels"] == 400
    spec = combo["addChart"]["chart"]["spec"]["basicChart"]
    assert [s["type"] for s in spec["series"]] == ["COLUMN", "LINE", "LINE"] and spec["stackedType"] == "STACKED"
    assert combo["addChart"]["chart"]["position"] == {"newSheet": True}


def test_chart_changes_keep_what_they_do_not_name():
    look, data = object_requests(
        "chart", {"op": "chart_update", "chart": "sales", "chart_type": "LINE", "legend": "RIGHT", "title": ""},
        {"op": "chart_update", "chart": "31", "range": "A1:D7"})
    spec = look["updateChartSpec"]["spec"]
    assert look["updateChartSpec"]["chartId"] == 31 and "title" not in spec
    assert spec["basicChart"]["chartType"] == "LINE" and spec["basicChart"]["legendPosition"] == "RIGHT_LEGEND"
    assert len(spec["basicChart"]["series"]) == 1  # a type change keeps the series
    rebuilt = data["updateChartSpec"]["spec"]["basicChart"]
    # A range without a tab stays on the chart's data tab; the later op sees the earlier one's type.
    assert rebuilt["chartType"] == "LINE" and len(rebuilt["series"]) == 3
    assert rebuilt["series"][0]["series"]["sourceRange"]["sources"][0]["sheetId"] == 7


def test_moving_a_chart_keeps_its_size_unless_given():
    to_cell, resized, own_tab = object_requests(
        "chart", {"op": "chart_move", "chart": "Sales", "at": "Main!B2", "height": 200},
        {"op": "chart_move", "chart": "Sales", "width": 640}, {"op": "chart_move", "chart": "Sales", "new_sheet": True})
    move = to_cell["updateEmbeddedObjectPosition"]
    assert move["newPosition"]["overlayPosition"] == {
        "anchorCell": {"sheetId": 0, "rowIndex": 1, "columnIndex": 1}, "widthPixels": 480, "heightPixels": 200,
        "offsetXPixels": 0, "offsetYPixels": 0}
    assert move["fields"] == "anchorCell,offsetXPixels,offsetYPixels,widthPixels,heightPixels"
    assert resized["updateEmbeddedObjectPosition"]["fields"] == "widthPixels"
    assert own_tab["updateEmbeddedObjectPosition"]["newPosition"] == {"newSheet": True}
    assert "fields" not in own_tab["updateEmbeddedObjectPosition"]


def test_pivot_tables_on_a_new_tab_or_at_a_cell():
    tab, table = object_requests("pivot", {"op": "pivot", "range": "Tasks!B1:E50", "pivot_rows": ["D"],
                                           "pivot_values": [{"column": "E"}, {"column": "B", "summarize": "COUNTA"}],
                                           "pivot_filters": [{"column": "D", "show": ["A", "B"]}]})
    assert tab["addSheet"]["properties"]["title"] == "Pivot table 1"
    cells = table["updateCells"]
    assert cells["start"] == {"sheetId": tab["addSheet"]["properties"]["sheetId"], "rowIndex": 0, "columnIndex": 0}
    pivot = cells["rows"][0]["values"][0]["pivotTable"]
    assert pivot["rows"] == [{"sourceColumnOffset": 2, "showTotals": True, "sortOrder": "ASCENDING"}]
    assert pivot["values"] == [{"sourceColumnOffset": 3, "summarizeFunction": "SUM"},
                               {"sourceColumnOffset": 0, "summarizeFunction": "COUNTA"}]
    assert pivot["filterSpecs"] == [{"columnOffsetIndex": 2, "filterCriteria": {"visibleValues": ["A", "B"]}}]
    (at,) = object_requests("pivot", {"op": "pivot", "range": "Tasks!A1:C9", "pivot_columns": ["B"], "at": "Main!K1"})
    assert at["updateCells"]["start"] == {"sheetId": 0, "rowIndex": 0, "columnIndex": 10}


def test_deleting_a_pivot_table_checks_its_anchor():
    seen = []

    def anchored(grid):
        seen.append(grid)
        return grid["startRowIndex"] == 19

    (gone,) = object_requests("pivot", {"op": "pivot_delete", "at": "Tasks!L20"}, pivot=anchored)
    assert gone == {"updateCells": {"range": seen[0], "fields": "pivotTable", "rows": [{"values": [{}]}]}}
    with pytest.raises(access.AccessError, match="no pivot table is anchored at L21"):
        object_requests("pivot", {"op": "pivot_delete", "at": "Tasks!L21"}, pivot=anchored)


@pytest.mark.parametrize("action,op,message", [
    ("chart", {"op": "chart", "range": "A1:A9"}, "label column"),
    ("chart", {"op": "chart", "range": "A1:C9", "chart_type": "PIE"}, "two columns"),
    ("chart", {"op": "chart", "range": "3:9"}, "block or whole columns"),
    ("chart", {"op": "chart", "range": "A1:C9", "chart_type": "LINE", "stacked": True}, "cannot be stacked"),
    ("chart", {"op": "chart", "range": "A1:C9", "at": "B2", "new_sheet": True}, "not both"),
    ("chart", {"op": "chart", "range": "A1:C9", "new_sheet": True, "width": 300}, "no width"),
    ("chart", {"op": "chart", "range": "A1:C9", "at": "B2:C3"}, "one cell"),
    ("chart", {"op": "chart_update", "chart": "Sales"}, "give range"),
    ("chart", {"op": "chart_move", "chart": "Sales"}, "give at"),
    ("chart", {"op": "trim", "range": "A1"}, "op must be one of"),
    ("pivot", {"op": "pivot", "range": "A1:C9"}, "give pivot_rows"),
    ("pivot", {"op": "pivot", "range": "A1:C9", "pivot_rows": ["F"]}, "outside the range"),
    ("pivot", {"op": "pivot", "range": "A1:C9", "pivot_values": [{"column": "B", "summarize": "TOTAL"}]},
     "summarize must be one of"),
    ("pivot", {"op": "pivot", "range": "A1:C9", "pivot_rows": ["A"], "at": "Z1", "title": "x"}, "takes no title")])
def test_malformed_chart_and_pivot_ops_are_refused(action, op, message):
    with pytest.raises(access.AccessError, match=message):
        access.approval_request("google_sheets", objects(action, op))


@pytest.mark.parametrize("op,message", [
    ({"op": "chart_update", "chart": "Nope", "title": "x"}, "no single chart titled"),
    ({"op": "chart_update", "chart": "Sales", "chart_type": "PIE"}, "into or out of a pie")])
def test_unknown_or_impossible_chart_changes_are_refused(op, message):
    with pytest.raises(access.AccessError, match=message):
        object_requests("chart", op)


def test_chart_and_pivot_approval(monkeypatch):
    shared = f"google-access:sheets-edit:{SID}"
    assert access.approval_request("google_sheets", objects(
        "chart", {"op": "chart", "range": "A1:B9"}, {"op": "chart_update", "chart": "S", "title": "T"},
        {"op": "chart_move", "chart": "S", "width": 300}))[1] == shared
    assert access.approval_request("google_sheets", objects(
        "pivot", {"op": "pivot", "range": "A1:C9", "pivot_rows": ["A"]}))[1] == shared
    for action, op in (("chart", {"op": "chart_delete", "chart": "S"}), ("pivot", {"op": "pivot_delete", "at": "A1"}),
                       ("pivot", {"op": "pivot", "range": "A1:C9", "pivot_rows": ["A"], "at": "Z1"})):
        assert "sheets-edit" not in access.approval_request("google_sheets", objects(action, op))[1]
    context(monkeypatch, title="Plan", names=["Main", "Tasks"])
    lines = access.approval_request("google_sheets", objects(
        "chart", {"op": "chart", "range": "Tasks!A1:C7", "title": "Sales", "at": "Main!H2"},
        {"op": "chart_move", "chart": "Sales", "width": 640}), home=Path("/x"))[0].split("\n")
    assert lines == ["SpreadSheet: Plan", "",
                     'Add column chart of Tasks!A1:C7 at Main!H2: title "Sales"',
                     'Move chart "Sales": size 640x…px']
    lines = access.approval_request("google_sheets", objects(
        "pivot", {"op": "pivot", "range": "Tasks!A1:D9", "pivot_rows": ["C"], "pivot_values": [{"column": "D"}],
                  "at": "Tasks!K1"}), home=Path("/x"))[0].split("\n")
    assert lines[1:] == ["Sheet: Tasks", "",
                         "Pivot table of A1:D9 at K1, overwriting the cells it fills: rows C; values SUM of D"]


def test_chart_and_pivot_results_report_ids_and_tabs(tmp_path, monkeypatch):
    api, book = layout_api()
    book.get().execute.return_value = CHARTS
    book.batchUpdate().execute.return_value = {"replies": [
        {"addChart": {"chart": {"chartId": 77, "spec": {"title": "Sales"}}}},
        {"addSheet": {"properties": {"sheetId": 88, "title": "Pivot table 1"}}}, {}]}
    services(monkeypatch, sheets=api)
    result = access.sheets(tmp_path, objects("chart", {"op": "chart", "range": "Tasks!A1:B9"}))
    assert result["charts"] == [{"chart_id": 77, "title": "Sales"}]
    assert result["sheets"] == [{"sheet_id": 88, "title": "Pivot table 1"}]
    assert book.get.call_args.kwargs["fields"] == access.CHART_FIELDS


def test_info_lists_charts_and_get_format_pivot_anchors():
    sheet = access._sheet_info(CHARTS["sheets"][1])
    assert sheet["charts"] == [{"chart_id": 31, "title": "Sales", "type": "COLUMN", "at": "F1", "size": "480x300"}]
    block = access._format_block("Report", {"startRow": 19, "startColumn": 11, "rowData": [{"values": [
        {"pivotTable": {"source": {"sheetId": 7, "endRowIndex": 7, "startColumnIndex": 11, "endColumnIndex": 15}}}]}]})
    assert block["pivot_tables"] == {"L20": {"source": "L1:O7", "source_sheet_id": 7}}


def test_review_fixes_for_chart_and_pivot_addressing():
    # No tab on a pivot's or chart's "at": the data's tab, on the card and in the request.
    (pivot,) = object_requests("pivot", {"op": "pivot", "range": "Tasks!A1:D9", "pivot_rows": ["C"], "at": "K1"})
    assert pivot["updateCells"]["start"]["sheetId"] == 7
    assert access.approval_request("google_sheets", objects(
        "pivot", {"op": "pivot", "range": "Tasks!A1:D9", "pivot_rows": ["C"], "at": "K1"}))[0].endswith(
        "Sheet: Tasks\n\nPivot table of A1:D9 at K1, overwriting the cells it fills: rows C")
    (chart,) = object_requests("chart", {"op": "chart", "range": "Tasks!A1:C7", "at": "H2"})
    assert chart["addChart"]["chart"]["position"]["overlayPosition"]["anchorCell"]["sheetId"] == 7
    # chart_move's "at" without a tab stays on the chart's tab.
    (moved,) = object_requests("chart", {"op": "chart_move", "chart": "Sales", "at": "B2"})
    assert moved["updateEmbeddedObjectPosition"]["newPosition"]["overlayPosition"]["anchorCell"]["sheetId"] == 7
    # A resize before a move in the same call is kept.
    resized, moved = object_requests("chart", {"op": "chart_move", "chart": "Sales", "width": 640},
                                     {"op": "chart_move", "chart": "Sales", "at": "Main!B2"})
    assert moved["updateEmbeddedObjectPosition"]["newPosition"]["overlayPosition"]["widthPixels"] == 640
    assert resized["updateEmbeddedObjectPosition"]["newPosition"]["overlayPosition"] == {"widthPixels": 640}


def test_type_and_header_changes_keep_the_chart_sources():
    gapped = json.loads(json.dumps(CHARTS))
    series = gapped["sheets"][1]["charts"][0]["spec"]["basicChart"]["series"][0]
    series["series"]["sourceRange"]["sources"][0].update(startColumnIndex=3, endColumnIndex=4)
    (got,) = access._object_requests(access._ops(objects(
        "chart", {"op": "chart_update", "chart": "Sales", "chart_type": "BAR", "header": False}), "chart"), gapped)
    basic = got["updateChartSpec"]["spec"]["basicChart"]
    assert basic["chartType"] == "BAR" and basic["headerCount"] == 0
    assert [s["series"]["sourceRange"]["sources"][0]["startColumnIndex"] for s in basic["series"]] == [3]
    assert basic["series"][0]["targetAxis"] == "BOTTOM_AXIS"


# --- protected ranges -----------------------------------------------------------------------------

PROTECTED = {"sheets": [
    {"properties": {"title": "Main"}},
    {"properties": {"sheetId": 7, "title": "Tasks"}, "protectedRanges": [
        {"protectedRangeId": 41, "description": "Header",
         "range": {"sheetId": 7, "startRowIndex": 0, "endRowIndex": 1, "startColumnIndex": 0, "endColumnIndex": 4}}]}]}


def protect(*ops):
    return {"action": "protect", "spreadsheet_id": SID, "ops": list(ops)}


def protect_requests(*ops):
    return access._protect_requests(access._ops(protect(*ops), "protect"), PROTECTED)


def test_protections_become_requests():
    cells, tab, warn = protect_requests(
        {"op": "protect", "range": "Tasks!A1:D1", "label": "Header"},
        {"op": "protect", "range": "Tasks", "except": ["B2:B20"], "editors": ["ann@example.com", "ANN@example.com"]},
        {"op": "protect", "range": "Main!C:C", "warning_only": True})
    assert cells == {"addProtectedRange": {"protectedRange": {
        "range": {"sheetId": 7, "startColumnIndex": 0, "endColumnIndex": 4, "startRowIndex": 0, "endRowIndex": 1},
        "description": "Header", "warningOnly": False}}}
    whole = tab["addProtectedRange"]["protectedRange"]
    assert whole["range"] == {"sheetId": 7} and whole["editors"] == {"users": ["ann@example.com"]}
    assert whole["unprotectedRanges"] == [{"sheetId": 7, "startColumnIndex": 1, "endColumnIndex": 2,
                                           "startRowIndex": 1, "endRowIndex": 20}]
    assert warn["addProtectedRange"]["protectedRange"]["warningOnly"] is True


def test_protection_changes_and_removal():
    moved, warned, gone = protect_requests(
        {"op": "protect_update", "protection": "header", "range": "A1:E1", "editors": []},
        {"op": "protect_update", "protection": "41", "warning_only": True},
        {"op": "protect_delete", "protection": "Header"})
    update = moved["updateProtectedRange"]
    assert update["fields"] == "range,warningOnly,editors" and update["protectedRange"]["protectedRangeId"] == 41
    assert update["protectedRange"]["range"]["sheetId"] == 7  # a range without a tab stays on its tab
    assert update["protectedRange"]["editors"] == {"users": []}
    assert warned["updateProtectedRange"]["fields"] == "warningOnly"
    assert gone == {"deleteProtectedRange": {"protectedRangeId": 41}}
    with pytest.raises(access.AccessError, match="no single protection"):
        protect_requests({"op": "protect_delete", "protection": "Header"}, {"op": "protect_delete", "protection": "41"})
    with pytest.raises(access.AccessError, match="whole tab"):
        protect_requests({"op": "protect_update", "protection": "Header", "except": ["B2"]})


def test_every_protect_call_asks_and_names_every_editor(monkeypatch):
    context(monkeypatch, title="Plan", names=["Main", "Tasks"])
    editors = [f"person{i}@example.com" for i in range(1, 6)]
    reason, key = access.approval_request("google_sheets", protect(
        {"op": "protect", "range": "Tasks", "except": ["B2:B9"], "editors": editors}), home=Path("/x"))
    assert "sheets-edit" not in key
    assert reason.split("\n") == ["SpreadSheet: Plan", "Sheet: Tasks", "",
                                  f"Protect whole tab: editable only by you, the file's owner, {', '.join(editors)}; except B2:B9"]
    lines = access.approval_request("google_sheets", protect(
        {"op": "protect_update", "protection": "Header", "range": "A1:E1", "warning_only": True},
        {"op": "protect_delete", "protection": "Old"}), home=Path("/x"))[0].split("\n")
    assert lines[2:] == ['Change protection "Header": anyone who can edit the file may edit after a warning; '
                         "range A1:E1 on its tab",
                         'Remove protection "Old" (any other protection over those cells still applies)']
    long = [f"someone.with.a.long.name{i}@example-company.com" for i in range(10)]
    with pytest.raises(access.AccessError, match="every editor"):
        access.approval_request("google_sheets", protect({"op": "protect", "range": "Tasks!A1", "editors": long}))


@pytest.mark.parametrize("op,message", [
    ({"op": "protect", "range": "A1:B2", "editors": ["not an address"]}, "not an email"),
    ({"op": "protect", "range": "A1:B2", "editors": [f"p{i}@x.com" for i in range(11)]}, "up to 10"),
    ({"op": "protect", "range": "A1:B2", "warning_only": True, "editors": ["a@x.com"]}, "no editors"),
    ({"op": "protect", "range": "Tasks!A1:B2", "except": ["A1"]}, "whole tab"),
    ({"op": "protect", "range": "Tasks", "except": ["Main!A1"]}, "on the protected tab"),
    ({"op": "protect_update", "protection": "Header"}, "give range"),
    ({"op": "protect_update", "protection": "Header", "warning_only": False}, "needs editors"),
    ({"op": "protect", "range": "A1", "description": "x"}, "unknown field")])
def test_malformed_protect_ops_are_refused(op, message):
    with pytest.raises(access.AccessError, match=message):
        access.approval_request("google_sheets", protect(op))


def test_info_lists_protections():
    sheet = access._sheet_info({"properties": {"sheetId": 7, "title": "Tasks"}, "protectedRanges": [
        {"protectedRangeId": 41, "range": {"sheetId": 7}, "description": "All", "editors": {"users": ["me@x.com"]},
         "unprotectedRanges": [{"sheetId": 7, "startRowIndex": 1, "endRowIndex": 9, "startColumnIndex": 1,
                                "endColumnIndex": 2}]}]})
    assert sheet["protections"] == [{"protection_id": 41, "range": "whole tab", "label": "All", "warning_only": False,
                                     "editors": ["me@x.com"], "except": ["B2:B9"]}]


def test_protection_updates_resolve_exceptions_and_editors():
    tab = {"sheets": [{"properties": {"title": "Main"}}, {"properties": {"sheetId": 7, "title": "Tasks"},
                       "protectedRanges": [{"protectedRangeId": 42, "description": "All", "range": {"sheetId": 7}}]}]}
    qualified, editors = access._protect_requests(access._ops(protect(
        {"op": "protect_update", "protection": "All", "except": ["Tasks!B2:B20"]},
        {"op": "protect_update", "protection": "All", "editors": ["ann@example.com"]}), "protect"), tab)
    assert qualified["updateProtectedRange"]["protectedRange"]["unprotectedRanges"][0]["sheetId"] == 7
    # Editors only count on a blocking protection, so naming them ends a warning-only one.
    assert editors["updateProtectedRange"]["fields"] == "warningOnly,editors"
    with pytest.raises(access.AccessError, match="on the protected tab"):
        access._protect_requests(access._ops(protect(
            {"op": "protect_update", "protection": "All", "except": ["Main!B2"]}), "protect"), tab)


def test_a_card_hermes_would_mask_is_refused(monkeypatch):
    monkeypatch.setattr(access, "_redacted", lambda text: text.replace("sk-alex", "***"))
    with pytest.raises(access.AccessError, match="looks like a secret"):
        access.approval_request("google_sheets", protect(
            {"op": "protect", "range": "A1", "editors": ["sk-alex123@example.com"]}))
