import importlib.util
from pathlib import Path
import subprocess

import pytest

ROOT = Path(__file__).resolve().parents[1]


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


keychain = _load("web3_wallet_keychain_test", ROOT / "keychain.py")

LISTING = """\
NAME                SCOPE        KIND         MODIFIED          COMMENT
EXCHANGE_API_KEY    Shared       api key      2026-06-13 16:10
HERMES_MAIN         Shared       mnemonic     2026-10-07 10:00  hermes only
DEPLOYER            deploy-ops   private key  2026-10-07 10:01
OLD_SEED            Shared       seed phrase  2026-10-07 10:02
SOME_TOKEN          Shared       token        2026-10-07 10:03
"""


def test_only_wallet_kinds_are_picked_from_a_listing():
    found = keychain.parse_listing("work", LISTING)
    assert found == [
        {"project": "work", "scope": None, "name": "HERMES_MAIN", "label": "mnemonic", "role": "seed",
         "use": "sign", "memo": "hermes only"},
        {"project": "work", "scope": "deploy-ops", "name": "DEPLOYER", "label": "private key", "role": "key",
         "use": "watch", "memo": None},
        {"project": "work", "scope": None, "name": "OLD_SEED", "label": "seed phrase", "role": "seed",
         "use": "watch", "memo": None},
    ]
    assert [keychain.source_id(item) for item in found] == ["work/HERMES_MAIN", "work/deploy-ops/DEPLOYER",
                                                             "work/OLD_SEED"]


@pytest.mark.parametrize("label, role", [("MNEMONIC", "seed"), ("mnemonic", "seed"), ("seed phrase", "seed"),
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
    assert keychain.parse_listing("p", "no items\n") == []


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
