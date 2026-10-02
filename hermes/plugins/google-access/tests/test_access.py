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
    ("Leads!K3257:L3257", ("Leads", "K3257:L3257")), ("'My ''Tab'''!A1", ("My 'Tab'", "A1")),
    ("Sheet1", ("Sheet1", "")), ("A1:B2", (None, "A1:B2")), ("C:C", (None, "C:C")), ("3:5", (None, "3:5"))])
def test_split_range(rng, expected):
    assert access.split_range(rng) == expected


def test_column_letters_round_trip():
    for index in (0, 25, 26, 51, 701, 702):
        assert access._column_index(access.column_letters(index)) == index
    assert access.column_letters(10) == "K" and access.column_letters(27) == "AB"


def context(monkeypatch, title="Leads sheet", headers=None, names=None):
    calls = []

    def fake(home, sid, tabs):
        calls.append(tabs)
        return title, headers or {}, names if names is not None else list((headers or {}).keys())

    monkeypatch.setattr(access, "_sheet_context", fake)
    return calls


def test_card_shows_title_headers_and_cells(monkeypatch):
    context(monkeypatch, headers={"Leads": ["id"] + [""] * 9 + ["確認メモ", "判定"]})
    reason, _ = access.approval_request("google_sheets", {
        "action": "update", "spreadsheet_id": SID, "range": "Leads!K3257:L3257",
        "values": [["2026-10-02確認: 自社サイト example-shop.com にパッケージ・サービス(トイレ・リビング・寝室・台所)",
                    "【batch 3】見送り_既存機能重複。"]]}, home=Path("/nonexistent"))
    lines = reason.split("\n")
    assert lines[:3] == ["SpreadSheet: Leads sheet", "Sheet: Leads", ""]
    assert lines[3].startswith("K3257 > 確認メモ: 2026-10-02確認") and lines[3].endswith("…")
    assert lines[4] == "L3257 > 判定: 【batch 3】見送り_既存機能重複。"
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

