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


ledger = _load("web3_wallet_ledger_test", ROOT / "ledger.py")


def test_the_last_row_per_quote_wins(tmp_path):
    now = time.time()
    ledger.append(tmp_path, {"time": now, "quote": "q1", "outcome": "unknown"})
    ledger.append(tmp_path, {"time": now, "quote": "q1", "outcome": "rejected"})
    assert [r["outcome"] for r in ledger.entries(tmp_path, now - 1)] == ["rejected"]


def test_the_hourly_cap_counts_sent_and_unknown_but_not_rejected(tmp_path):
    now = time.time()
    for n in range(ledger.MAX_PER_HOUR - 1):
        ledger.append(tmp_path, {"time": now - 60, "quote": f"q{n}", "outcome": "unknown"})
        ledger.append(tmp_path, {"time": now - 60, "quote": f"q{n}", "outcome": "sent" if n % 2 else "unknown"})
    ledger.append(tmp_path, {"time": now - 60, "quote": "qr", "outcome": "rejected"})
    ledger.check_rate(tmp_path, now)
    ledger.append(tmp_path, {"time": now - 30, "quote": "qlast", "outcome": "sent"})
    with pytest.raises(ledger.CapReached, match="in the last hour"):
        ledger.check_rate(tmp_path, now)
    ledger.check_rate(tmp_path, now + ledger.HOUR)
