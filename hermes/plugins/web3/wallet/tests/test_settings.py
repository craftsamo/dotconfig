import importlib.util
from pathlib import Path
import time

import pytest

ROOT = Path(__file__).resolve().parents[1]


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


conf = _load("web3_wallet_settings_test", ROOT / "settings.py")

RAW = {"mainnet": False, "seeds": ["main", "work-x"], "accounts": {"ops": "main/0", "proj": "work-x/3"}}


def test_settings_normalize_and_reparse():
    settings = conf.parse(RAW)
    assert settings["accounts"] == {"ops": {"seed": "main", "index": 0}, "proj": {"seed": "work-x", "index": 3}}
    assert conf.parse(settings) == settings  # the signer re-parses what the plugin passes
    assert conf.seed_item("work-x") == "WEB3_SEED_WORK_X"
    assert conf.parse({k: v for k, v in RAW.items() if k != "mainnet"})["mainnet"] is False


@pytest.mark.parametrize("raw, message", [
    (None, "missing or empty"),
    ({**RAW, "mainnet": "yes"}, "true or false"),
    ({**RAW, "seeds": []}, "at least one seed"),
    ({**RAW, "seeds": ["Main"]}, "lowercase"),
    ({**RAW, "seeds": ["main", "main"]}, "listed twice"),
    ({**RAW, "accounts": {}}, "at least one account"),
    ({**RAW, "accounts": {"ops": "main"}}, "<seed>/<index>"),
    ({**RAW, "accounts": {"ops": "other/0"}}, "not in seeds"),
    ({**RAW, "accounts": {"Ops": "main/0"}}, "lowercase"),
    ({**RAW, "accounts": {"a": "main/0", "b": "main/0"}}, "same seed and index"),
])
def test_bad_settings_name_their_problem(raw, message):
    with pytest.raises(conf.SettingsError, match=message):
        conf.parse(raw)


def test_mainnet_opens_only_mainnets():
    closed, opened = conf.parse(RAW), conf.parse({**RAW, "mainnet": True})
    assert conf.chain_allowed(closed, testnet=True) and not conf.chain_allowed(closed, testnet=False)
    assert conf.chain_allowed(opened, testnet=False)


def test_the_hourly_cap_counts_sent_and_unknown_but_not_rejected(tmp_path):
    now = time.time()
    for n in range(conf.MAX_PER_HOUR - 1):
        conf.append(tmp_path, {"time": now - 60, "quote": f"q{n}", "outcome": "unknown"})
        conf.append(tmp_path, {"time": now - 60, "quote": f"q{n}", "outcome": "sent" if n % 2 else "unknown"})
    conf.append(tmp_path, {"time": now - 60, "quote": "qr", "outcome": "rejected"})
    conf.check_rate(tmp_path, now)
    conf.append(tmp_path, {"time": now - 30, "quote": "qlast", "outcome": "sent"})
    with pytest.raises(conf.SettingsError, match="in the last hour"):
        conf.check_rate(tmp_path, now)
    conf.check_rate(tmp_path, now + conf.HOUR)
