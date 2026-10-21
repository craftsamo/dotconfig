import importlib.util
import json
from pathlib import Path
import subprocess

import pytest

ROOT = Path(__file__).resolve().parents[1]


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


keychain = _load("web3_keychain_test", ROOT / "keychain.py")

def _item(name, kind, scope="", stage="", comment="", env="yes"):
    """One object of `secret ls --json` (the shape zsh/tests/secret-selftest.zsh pins on the CLI)."""
    return {"project": "work", "scope": scope, "stage": stage, "name": name, "kind": kind,
            "comment": comment, "env": env, "meta": {}, "modified": "2026-10-07 10:00"}


LISTING = json.dumps([
    _item("EXCHANGE_API_KEY", "API KEY"),
    _item("HERMES_MAIN", "MNEMONIC", comment="hermes only"),
    _item("DEPLOYER", "PRIVATE KEY", scope="deploy-ops"),
    _item("OLD_SEED", "SEED PHRASE"),
    _item("SOME_TOKEN", "TOKEN"),
])


def test_only_wallet_kinds_are_picked_from_a_listing():
    found = keychain.parse_listing("work", LISTING)
    assert found == [
        {"project": "work", "scope": None, "name": "HERMES_MAIN", "label": "MNEMONIC", "role": "seed",
         "use": "sign", "memo": "hermes only", "env": "yes"},
        {"project": "work", "scope": "deploy-ops", "name": "DEPLOYER", "label": "PRIVATE KEY", "role": "key",
         "use": "watch", "memo": None, "env": "yes"},
        {"project": "work", "scope": None, "name": "OLD_SEED", "label": "SEED PHRASE", "role": "seed",
         "use": "watch", "memo": None, "env": "yes"},
    ]
    assert [keychain.source_id(item) for item in found] == ["work/HERMES_MAIN", "work/deploy-ops/DEPLOYER",
                                                             "work/OLD_SEED"]


def test_env_is_read_from_the_listing():
    listing = json.dumps([_item("HERMES_MAIN", "MNEMONIC PHRASE", comment="wallet memo", env="no"),
                          _item("OTHER_SEED", "MNEMONIC")])
    found = keychain.parse_listing("work", listing)
    assert [(item["name"], item["role"], item["env"], item["memo"]) for item in found] == [
        ("HERMES_MAIN", "seed", "no", "wallet memo"), ("OTHER_SEED", "seed", "yes", None)]
    # no env field: assume it is injected
    bare = [{k: v for k, v in _item("X_SEED", "MNEMONIC").items() if k != "env"}]
    assert [item["env"] for item in keychain.parse_listing("work", json.dumps(bare))] == ["yes"]


def test_items_of_a_stage_are_left_out():
    listing = json.dumps([_item("HERMES_MAIN", "MNEMONIC"), _item("HERMES_MAIN", "MNEMONIC", stage="prod"),
                          _item("HERMES_OPS", "MNEMONIC", scope="ops", stage="test")])
    assert [(item["name"], item["scope"]) for item in keychain.parse_rows("work", listing)] == [
        ("HERMES_MAIN", None)]


def test_the_long_table_is_not_a_listing():
    # the people's table (`ls --long`), in any layout, is never parsed
    table = ("work\n    NAME         KIND      ENV  MODIFIED\n  shared\n"
             "    HERMES_MAIN  MNEMONIC  no   2026-10-07\n")
    old = ("NAME         SCOPE   KIND      MODIFIED          COMMENT\n"
           "HERMES_MAIN  Shared  MNEMONIC  2026-10-07 10:00\n")
    assert keychain.parse_rows("work", table) == [] and keychain.parse_rows("work", old) == []


@pytest.mark.parametrize("label, role", [("MNEMONIC", "seed"), ("mnemonic", "seed"), ("seed phrase", "seed"),
                                         ("MNEMONIC PHRASE", "seed"),
                                         ("PRIVATE_KEY", "key"), ("private-key", "key"), ("Private Key", "key"),
                                         ("api key", None), ("TOKEN", None), ("", None)])
def test_kind_labels_are_matched_however_spelled(label, role):
    assert keychain.kind_of(label) == role


@pytest.mark.parametrize("name, use", [
    ("HERMES", "sign"), ("HERMES_MAIN", "sign"), ("PROJECTX_HERMES", "sign"), ("hermes-deploy", "sign"),
    ("A_HERMES_B", "sign"), ("PROD_MNEMONIC", "watch"), ("THERMES_KEY", "watch"), ("HERMESX", "watch"),
    ("", "watch")])
def test_hermes_in_the_name_as_a_word_marks_a_wallet_it_may_sign_with(name, use):
    assert keychain.use_of(name) == use


def test_an_empty_or_foreign_listing_yields_nothing():
    assert keychain.parse_listing("p", "") == []
    assert keychain.parse_listing("p", "[]\n") == []
    assert keychain.parse_listing("p", "no items\n") == []
    assert keychain.parse_listing("p", '{"name": "HERMES_MAIN"}') == []


def test_without_the_secret_cli_the_wallet_is_unavailable(monkeypatch, tmp_path):
    monkeypatch.setattr(keychain, "SECRET", tmp_path / "missing")
    with pytest.raises(keychain.KeychainError, match="not available on this machine"):
        keychain.discover()


def test_values_are_read_only_for_wallet_items(monkeypatch, tmp_path):
    calls = []
    fake = tmp_path / "secret"
    fake.write_text("")
    monkeypatch.setattr(keychain, "SECRET", fake)

    def run(cmd, **kwargs):
        args = cmd[1:]
        calls.append(args)
        assert kwargs["stdin"] is subprocess.DEVNULL
        out = {"projects": "work\nempty\n"}.get(args[0], "")
        if args[:3] == ["ls", "-p", "work"]:
            out = LISTING
        if args[0] == "get":
            out = "value\n"
        return subprocess.CompletedProcess(cmd, 0, stdout=out, stderr="")

    monkeypatch.setattr(keychain.subprocess, "run", run)
    items = keychain.discover()
    gets = [c for c in calls if c[0] == "get"]
    assert gets == [["get", "HERMES_MAIN", "-p", "work", "--shared"],
                    ["get", "DEPLOYER", "-p", "work", "--scope", "deploy-ops"],
                    ["get", "OLD_SEED", "-p", "work", "--shared"]]
    assert {item["id"] for item in items} == {"work/HERMES_MAIN", "work/deploy-ops/DEPLOYER", "work/OLD_SEED"}
    assert all(item["value"] == "value" for item in items)


def test_sign_only_never_reads_a_watch_only_value(monkeypatch, tmp_path):
    calls = []
    fake = tmp_path / "secret"
    fake.write_text("")
    monkeypatch.setattr(keychain, "SECRET", fake)

    def run(cmd, **kwargs):
        args = cmd[1:]
        calls.append(args)
        out = {"projects": "work\n"}.get(args[0], "")
        if args[:3] == ["ls", "-p", "work"]:
            out = LISTING
        if args[0] == "get":
            out = "value\n"
        return subprocess.CompletedProcess(cmd, 0, stdout=out, stderr="")

    monkeypatch.setattr(keychain.subprocess, "run", run)
    items = keychain.discover(sign_only=True)
    assert [c for c in calls if c[0] == "get"] == [["get", "HERMES_MAIN", "-p", "work", "--shared"]]
    assert [item["id"] for item in items] == ["work/HERMES_MAIN"]
