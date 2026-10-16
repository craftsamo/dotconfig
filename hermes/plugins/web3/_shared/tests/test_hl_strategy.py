"""The rules, the backtest, specs and stances (hl_strategy.py): pure, so tested in Hermes' interpreter."""

from __future__ import annotations

import importlib.util
import math
from pathlib import Path
import random

import pytest

ROOT = Path(__file__).resolve().parents[1]
_spec = importlib.util.spec_from_file_location("web3_hl_strategy_test", ROOT / "hl_strategy.py")
hs = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(hs)

H4 = 4 * hs.HOUR_MS
T0 = 1_700_000_000_000 - 1_700_000_000_000 % H4
BREAKOUT = {"kind": "breakout", "entry": 5, "exit": 3, "atr": 5, "stop_atr": 2, "risk_pct": 1}
NOW = T0 + 400 * H4


def bar(i, o, h, l, c):
    return {"t": T0 + i * H4, "o": o, "h": h, "l": l, "c": c}


def flat(n, price=100.0, start=0):
    return [bar(start + i, price, price + 1, price - 1, price) for i in range(n)]


def walk(n, seed=1, drift=0.002):
    random.seed(seed)
    rows, p = [], 100.0
    for i in range(n):
        d = drift if (i // 300) % 2 == 0 else -drift
        c = max(1.0, p * (1 + d + random.gauss(0, 0.01)))
        rows.append(bar(i, p, max(p, c) * 1.003, min(p, c) * 0.997, c))
        p = c
    return rows


# --- rules and bars -----------------------------------------------------------------------------

def test_rules_are_validated_and_fingerprinted_with_their_interval():
    r = hs.rules(BREAKOUT)
    assert r == {"kind": "breakout", "entry": 5, "exit": 3, "atr": 5, "stop_atr": 2.0, "risk_pct": 1.0}
    assert hs.fingerprint(r, "4h") == hs.fingerprint(hs.rules(dict(BREAKOUT)), "4h")
    assert hs.fingerprint(r, "4h") != hs.fingerprint(r, "1h")
    assert hs.fingerprint(r, "4h") != hs.fingerprint(hs.rules({**BREAKOUT, "entry": 6}), "4h")
    for bad, why in (({**BREAKOUT, "exit": 9}, "exit must not be longer"), ({**BREAKOUT, "risk_pct": 9}, "risk_pct"),
                     ({**BREAKOUT, "x": 1}, "not x"), ({"kind": "rsi"}, "kind is one of"),
                     ({"kind": "ema_cross", "fast": 20, "slow": 10, "atr": 14, "stop_atr": 2, "risk_pct": 1}, "slow")):
        with pytest.raises(hs.StrategyError, match=why):
            hs.rules(bad)


def test_bars_drop_the_bar_still_forming_and_bad_rows():
    rows = [{"t": T0, "o": "1", "h": "2", "l": "0.5", "c": "1.5"}, [T0 + H4, "1", "0.5", "1", "1"],
            {"t": T0 + 2 * H4, "o": "1", "h": "1", "l": "1", "c": "1"}]
    got = hs.bars(rows, "4h", now_ms=T0 + 2 * H4 + 1)
    assert [b["t"] for b in got] == [T0]  # a high below the open is malformed; the last one is forming


def test_channels_match_a_brute_force_reading():
    series = walk(300)
    ind = hs.indicators(series, hs.rules(BREAKOUT))
    for i in range(5, 300):
        assert ind["up_entry"][i] == max(b["h"] for b in series[i - 5:i])
        assert ind["down_exit"][i] == min(b["l"] for b in series[i - 3:i])


def test_decide_closes_what_the_direction_excludes_and_opens_only_allowed_sides():
    sig = {"long": True, "short": False, "exit_long": False, "exit_short": True}
    assert hs.decide(sig, None, "both") == (False, "long")
    assert hs.decide(sig, None, "short") == (False, None)
    assert hs.decide(sig, "long", "flat") == (True, None)
    assert hs.decide(sig, "short", "both") == (True, "long")
    assert hs.decide(sig, "long", "both") == (False, None)
    assert hs.decide(None, "long", "flat") == (False, None)


def test_size_is_the_risk_capped_by_every_limit_and_the_venue_minimum():
    r = hs.rules(BREAKOUT)
    limits = {"exposure_pct": 70, "max_leverage": 2}
    value, bound = hs.size_usd(1000, 100, 99, r, 1.0, 0, limits)  # 1% at a 1% stop wants 1000
    assert bound == "exposure_pct" and value == pytest.approx(700)
    value, bound = hs.size_usd(1000, 100, 90, r, 1.0, 0, limits)
    assert bound == "risk" and value == pytest.approx(100)
    assert hs.size_usd(1000, 100, 90, r, 0.5, 0, limits)[0] == pytest.approx(50)
    value, bound = hs.size_usd(1000, 100, 90, r, 1.0, 0, {**limits, "max_order_usd": 50})
    assert bound == "mandate order" and value == pytest.approx(49)
    value, bound = hs.size_usd(1000, 100, 90, r, 1.0, 20, {**limits, "max_exposure_usd": 80})
    assert bound == "mandate exposure" and value == pytest.approx(58.8)
    none, why = hs.size_usd(1000, 100, 90, r, 1.0, 695, limits)
    assert none is None and "below the venue's 10" in why


# --- the backtest -------------------------------------------------------------------------------

def test_an_entry_fills_at_the_next_open_and_its_stop_inside_a_bar():
    series = flat(10) + [bar(10, 100, 106, 100, 105), bar(11, 110, 111, 109, 110), bar(12, 109, 109, 90, 95)]
    cost = hs.costs({"taker_bps": 0, "slippage_bps": 0, "funding": "none"})
    run = hs.simulate(series, hs.rules(BREAKOUT), "4h", cost, {"exposure_pct": 100, "max_leverage": 10})
    trade = run["trades"][0]
    assert trade["side"] == "long" and trade["entry"] == "110" and trade["reason"] == "stop"
    atr = hs.indicators(series, hs.rules(BREAKOUT))["atr"][10]
    assert float(trade["exit"]) == pytest.approx(105 - 2 * atr, rel=1e-4)


def test_a_trailing_stop_follows_each_close_and_never_loosens():
    plain, trailing = hs.rules(BREAKOUT), hs.rules({**BREAKOUT, "trail_atr": 1})
    assert "trail_atr" not in plain and hs.rules({**BREAKOUT, "trail_atr": 0}) == plain  # 0 is none: same fingerprint
    assert trailing["trail_atr"] == 1.0 and hs.fingerprint(trailing, "4h") != hs.fingerprint(plain, "4h")
    with pytest.raises(hs.StrategyError, match="trail_atr"):
        hs.rules({**BREAKOUT, "trail_atr": 20})
    assert hs.trailed("long", 90.0, 100.0, 2.0, trailing) == 98.0 and hs.trailed("long", 99.0, 100.0, 2.0, trailing) == 99.0
    assert hs.trailed("short", 110.0, 100.0, 2.0, trailing) == 102.0 and hs.trailed("short", 90.0, 100.0, 2.0, plain) == 90.0
    # a run-up, then a pullback that reaches the trailed stop but not the one placed at entry
    series = flat(10) + [bar(10, 100, 106, 100, 105), bar(11, 110, 111, 109, 110), bar(12, 110, 121, 110, 120),
                         bar(13, 120, 121, 114, 115), bar(14, 115, 116, 114, 115)]
    cost = hs.costs({"taker_bps": 0, "slippage_bps": 0, "funding": "none"})
    limits = {"exposure_pct": 100, "max_leverage": 10}
    kept = hs.simulate(series, plain, "4h", cost, limits)
    moved = hs.simulate(series, trailing, "4h", cost, limits)
    assert kept["trades"][0]["reason"] == "end"
    trade = moved["trades"][0]
    atr = hs.indicators(series, trailing)["atr"][12]
    assert trade["reason"] == "stop" and float(trade["exit"]) == pytest.approx(120 - atr, rel=1e-4)
    # evaluate names the level a held position's stop should reach after the newest bar
    ev = hs.evaluate(series[:13], trailing, {"direction": "both"}, "long")
    assert ev["trail"] == pytest.approx(120 - atr, rel=1e-4) and "trail" not in hs.evaluate(series[:13], plain, {"direction": "both"}, "long")
    assert "trail" not in hs.evaluate(series[:13], trailing, {"direction": "both"}, None)


def test_a_regime_ema_withholds_entries_against_it_but_not_exits():
    plain, filtered = hs.rules(BREAKOUT), hs.rules({**BREAKOUT, "regime_ema": 30})
    assert "regime_ema" not in plain and hs.rules({**BREAKOUT, "regime_ema": 0}) == plain
    assert hs.fingerprint(filtered, "4h") != hs.fingerprint(plain, "4h") and hs.warmup(filtered) == 91
    with pytest.raises(hs.StrategyError, match="regime_ema"):
        hs.rules({**BREAKOUT, "regime_ema": 2.5})
    # a long fall, then a bounce that breaks the 5-bar channel while the price is still under the EMA
    series = [bar(i, 500 - 2 * i, 501 - 2 * i, 498 - 2 * i, 499 - 2 * i) for i in range(120)]
    series += [bar(120, 260, 282, 260, 280), bar(121, 280, 281, 279, 280)]
    i = 120
    plain_sig = hs.signal(series, hs.indicators(series, plain), i, plain)
    reg_sig = hs.signal(series, hs.indicators(series, filtered), i, filtered)
    assert plain_sig["long"] and not reg_sig["long"] and "regime" in reg_sig["why"]
    assert reg_sig["exit_short"] == plain_sig["exit_short"] is True  # a short held still exits on the bounce
    assert hs.signal(series, hs.indicators(series, filtered), 50, filtered) is None  # before the EMA has settled
    # a short with the fall is still allowed under the EMA
    down = hs.signal(series, hs.indicators(series, filtered), 119, filtered)
    assert down["short"] and not down["long"]
    # mirrored: a long rise, then a dip through the channel while the price is still above the EMA
    rise = [bar(i, 100 + 2 * i, 102 + 2 * i, 99 + 2 * i, 101 + 2 * i) for i in range(120)]
    rise += [bar(120, 340, 340, 318, 320), bar(121, 320, 321, 319, 320)]
    dip = hs.signal(rise, hs.indicators(rise, filtered), 120, filtered)
    assert dip["exit_long"] and not dip["short"] and hs.signal(rise, hs.indicators(rise, plain), 120, plain)["short"]
    # the filter is the same on an EMA cross, and a close on the EMA withholds nothing
    ema = hs.rules({"kind": "ema_cross", "fast": 3, "slow": 8, "atr": 5, "stop_atr": 2, "risk_pct": 1, "regime_ema": 30})
    assert ema["regime_ema"] == 30 and hs.warmup(ema) == 91
    crossed = hs.signal(series, hs.indicators(series, ema), 120, ema)
    assert crossed is not None and not crossed["long"] and "regime" in crossed["why"]
    flat_on = series[:120] + [bar(120, 260, 282, 260, 280), bar(121, 280, 281, 279, 280)]
    ind = hs.indicators(flat_on, filtered)
    ind["regime"][120] = 280.0  # the close sits exactly on the EMA
    on = hs.signal(flat_on, ind, 120, filtered)
    assert on["long"] == hs.signal(flat_on, hs.indicators(flat_on, plain), 120, plain)["long"] is True


def test_a_walk_forward_grid_may_choose_the_regime_filter():
    series = walk(1200)
    cost = hs.costs({"funding": "none"})
    rates = hs.funding_by_bar(series, "4h", None, 0.0, "none")
    out = hs.walk_forward(series, hs.rules(BREAKOUT), "4h", cost, {"exposure_pct": 70, "max_leverage": 2},
                          {"grid": {"regime_ema": [0, 20], "entry": [5, 8]}, "folds": 2, "min_trades": 0},
                          rates=rates, stance=[], direction="both")
    assert out["candidates"] == 4 and len(out["folds"]) == 2
    assert all(f["chosen"].get("regime_ema", 0) in (0, 20) and f["chosen"]["entry"] in (5, 8) for f in out["folds"])


def test_a_bar_that_gaps_through_the_stop_fills_at_its_open_and_costs_are_charged():
    series = flat(10) + [bar(10, 100, 106, 100, 105), bar(11, 106, 107, 105, 106), bar(12, 80, 81, 79, 80)]
    cost = hs.costs({"taker_bps": 10, "slippage_bps": 0, "funding": "none"})
    run = hs.simulate(series, hs.rules(BREAKOUT), "4h", cost, {"exposure_pct": 100, "max_leverage": 10})
    trade = run["trades"][0]
    assert trade["exit"] == "80" and trade["reason"] == "stop" and trade["r"] < -1
    assert run["totals"]["fees"] > 0 and hs.metrics(run)["fees_pct"] > 0


def test_a_position_that_gaps_out_at_the_open_pays_no_funding_for_that_bar():
    series = flat(10) + [bar(10, 100, 106, 100, 105), bar(11, 106, 107, 105, 106), bar(12, 80, 81, 79, 80)]
    cost = hs.costs({"taker_bps": 0, "slippage_bps": 0})
    rates = [(0.01, 0)] * len(series)
    run = hs.simulate(series, hs.rules(BREAKOUT), "4h", cost, {"exposure_pct": 100, "max_leverage": 10}, rates=rates)
    assert run["trades"][0]["reason"] == "stop" and run["totals"]["bars_held"] == 1
    qty = run["totals"]["funding"] / (106 * 0.01)
    assert qty > 0 and run["totals"]["funding"] == pytest.approx(qty * 106 * 0.01)


def test_funding_follows_the_venue_rate_hour_by_hour_and_says_what_it_assumed():
    series = flat(3)
    funding = {T0 + h * hs.HOUR_MS: 0.001 for h in range(4)}
    rates = hs.funding_by_bar(series, "4h", funding, 0.0, "venue")
    assert rates[0] == (pytest.approx(0.004), 0) and rates[1] == (0.0, 4)
    assert hs.funding_by_bar(series, "4h", funding, 0.0, "none")[0] == (0.0, 0)


def test_metrics_read_drawdown_and_trades():
    run = hs.simulate(walk(2000), hs.rules({**BREAKOUT, "entry": 20, "exit": 10, "atr": 14}), "4h", hs.costs({}),
                      hs.backtest_limits({}))
    m = hs.metrics(run)
    assert m["trades"] > 10 and 0 < m["max_drawdown_pct"] < 100 and m["win_rate"] is not None
    assert len(hs.curve_points(run["curve"])["rows"]) <= hs.CURVE_POINTS + 1


def test_walk_forward_only_ever_trades_rules_chosen_on_earlier_data():
    series = walk(3000)
    base = hs.rules({**BREAKOUT, "entry": 20, "exit": 10, "atr": 14})
    rates = hs.funding_by_bar(series, "4h", None, hs.BASELINE_FUNDING, "venue")
    out = hs.walk_forward(series, base, "4h", hs.costs({}), hs.backtest_limits({}),
                          {"grid": {"entry": [20, 40], "exit": [10, 20]}, "folds": 3},
                          rates=rates, stance=[], direction="both")
    assert len(out["folds"]) == 3 and out["candidates"] == 4
    for fold in out["folds"]:
        assert fold["train"]["end"] < fold["test"]["start"]
        assert fold["chosen_fingerprint"] == hs.fingerprint({"kind": "breakout", **fold["chosen"]}, "4h")
    assert out["window"]["start"] == out["folds"][0]["test"]["start"]
    with pytest.raises(hs.StrategyError, match="at most 48"):
        hs.grid({"entry": [10, 20, 30, 40, 50, 60], "exit": [2, 3, 4, 5, 6, 7], "atr": [5, 6]}, base)


def test_a_stance_window_overrides_the_direction_and_scales_the_risk():
    series = walk(1500)
    r = hs.rules({**BREAKOUT, "entry": 20, "exit": 10, "atr": 14})
    windows = hs.timeline([{"from": T0, "to": T0 + 2000 * H4, "direction": "flat"}])
    run = hs.simulate(series, r, "4h", hs.costs({}), hs.backtest_limits({}), stance=windows)
    assert run["trades"] == []
    with pytest.raises(hs.StrategyError, match="size"):
        hs.timeline([{"from": T0, "to": T0 + H4, "size": 3}])


# --- specs, stances and the live decision -------------------------------------------------------

def spec_raw(**over):
    r = hs.rules(BREAKOUT)
    raw = {"schema": hs.SPEC_SCHEMA, "name": "trend", "network": "testnet", "account": "hermes/HERMES_MAIN#0",
           "address": "0x" + "ab" * 20, "markets": ["BTC", "ETH"], "interval": "4h",
           "variants": {"fast": {"rules": dict(BREAKOUT), "validated": {"fingerprint": hs.fingerprint(r, "4h")}}},
           "advisor": {"max_size": 1.5, "max_age_days": 7, "min_days_between_flips": 7},
           "limits": {"exposure_pct": 70, "max_leverage": 3},
           "mandate": {"id": "m1", "max_order_usd": "100", "max_exposure_usd": "200", "max_leverage": 2,
                       "expires": "2030-01-01T00:00:00+09:00"}}
    raw.update(over)
    return raw


def test_a_spec_runs_only_variants_backtested_as_written():
    s = hs.spec(spec_raw())
    assert s["limits"]["max_leverage"] == 2 and s["mandate"]["max_order_usd"] == 100.0 and s["active"]
    changed = spec_raw()
    changed["variants"]["fast"]["rules"]["entry"] = 6
    with pytest.raises(hs.StrategyError, match="not backtested as written"):
        hs.spec(changed)
    for over, why in (({"markets": ["xyz:GOLD"]}, "main-dex perps"), ({"network": "devnet"}, "network"),
                      ({"default": {"variant": "slow"}}, "default.variant"), ({"schema": "x"}, "schema")):
        with pytest.raises(hs.StrategyError, match=why):
            hs.spec(spec_raw(**over))


def test_a_market_may_have_its_own_default_inside_the_spec():
    ema = hs.rules({"kind": "ema_cross", "fast": 3, "slow": 8, "atr": 5, "stop_atr": 2, "risk_pct": 1})
    raw = spec_raw(default={"variant": "fast", "direction": "both", "size": 1,
                            "markets": {"ETH": {"variant": "slow", "direction": "long", "size": 0.5}}})
    raw["variants"]["slow"] = {"rules": dict(ema), "validated": {"fingerprint": hs.fingerprint(ema, "4h")}}
    s = hs.spec(raw)
    assert s["default"]["markets"]["BTC"] == {"variant": "fast", "direction": "both", "size": 1.0}
    assert s["default"]["markets"]["ETH"] == {"variant": "slow", "direction": "long", "size": 0.5}
    choices, notes, _ = hs.stance(s, None, NOW)
    assert choices["ETH"] == {"variant": "slow", "direction": "long", "size": 0.5, "source": "default"}
    assert choices["BTC"]["variant"] == "fast" and notes == []
    # an advisor's choice without a variant keeps the market's own default variant
    choices, _, _ = hs.stance(s, stance_raw(markets={"ETH": {"direction": "short"}}), NOW)
    assert choices["ETH"]["variant"] == "slow" and choices["ETH"]["source"] == "advisor"
    for over, why in (({"markets": {"SOL": {}}}, "default.markets"), ({"markets": {"ETH": {"variant": "x"}}}, "default.markets.ETH.variant"),
                      ({"markets": {"ETH": {"size": 2}}}, "default.markets.ETH.size"), ({"markets": []}, "default.markets")):
        with pytest.raises(hs.StrategyError, match=why):
            hs.spec(spec_raw(default={"variant": "fast", **over}))


def stance_raw(**over):
    raw = {"schema": hs.STANCE_SCHEMA, "strategy": "trend", "issued": hs.iso(NOW - hs.DAY_MS),
           "expires": hs.iso(NOW + 3 * hs.DAY_MS),
           "markets": {"BTC": {"direction": "short", "size": 1.5}},
           "basis": [{"claim": "payrolls above consensus", "source": "BLS", "as_of": hs.iso(NOW - 2 * hs.DAY_MS)}]}
    raw.update(over)
    return raw


def test_a_valid_stance_chooses_inside_the_bounds_and_the_rest_keeps_the_default():
    s = hs.spec(spec_raw())
    choices, notes, history = hs.stance(s, stance_raw(), NOW)
    assert choices["BTC"] == {"direction": "short", "variant": "fast", "size": 1.5, "source": "advisor"}
    assert choices["ETH"]["source"] == "default" and notes == []
    assert history["BTC"] == {"bias": "short", "since": NOW}


@pytest.mark.parametrize("over, why", [
    ({"expires": hs.iso(NOW - 1000)}, "expired"),
    ({"expires": hs.iso(NOW + 30 * hs.DAY_MS)}, "longer than"),
    ({"strategy": "other"}, "names strategy"),
    ({"basis": []}, "basis lists"),
    ({"basis": [{"claim": "c", "source": "s", "as_of": hs.iso(NOW)}]}, "dated after"),
    ({"markets": {"BTC": {"direction": "long", "size": 1.6}}}, "size must be between"),
    ({"markets": {"SOL": {"direction": "long"}}}, "not one of the strategy's markets"),
])
def test_a_stance_that_does_not_hold_falls_back_to_the_default(over, why):
    choices, notes, _ = hs.stance(hs.spec(spec_raw()), stance_raw(**over), NOW)
    assert choices["BTC"]["source"] == "default" and why in notes[0]


def test_an_early_turn_between_long_and_short_goes_flat_until_the_window_passes():
    s = hs.spec(spec_raw())
    history = {"BTC": {"bias": "long", "since": NOW - 2 * hs.DAY_MS}}
    choices, notes, kept = hs.stance(s, stance_raw(), NOW, history)
    assert choices["BTC"]["direction"] == "flat" and choices["BTC"]["source"] == "held" and "waits until" in notes[0]
    assert kept["BTC"]["bias"] == "long"
    later = NOW + 6 * hs.DAY_MS
    renewed = stance_raw(issued=hs.iso(later - hs.DAY_MS), expires=hs.iso(later + hs.DAY_MS))
    choices, _, kept = hs.stance(s, renewed, later, history)
    assert choices["BTC"]["direction"] == "short" and kept["BTC"]["bias"] == "short"


def test_evaluate_reads_the_newest_completed_bar_with_the_backtests_signal():
    series = flat(10) + [bar(10, 100, 106, 100, 105)]
    ev = hs.evaluate(series, hs.rules(BREAKOUT), {"direction": "both"}, None)
    assert ev["open"] == "long" and ev["bar"] == series[-1]["t"] and ev["stop"] < 105
    assert hs.evaluate(series[:3], hs.rules(BREAKOUT), {"direction": "both"}, None)["open"] is None
    assert hs.evaluate(series, hs.rules(BREAKOUT), {"direction": "flat"}, "long")["close"] is True


def test_prices_are_written_at_five_significant_figures():
    assert hs.sig5(123456.7) == "123457" and hs.sig5(2512.345) == "2512.3" and hs.sig5(0.000123456) == "0.00012346"
    assert hs.usd(12.349) == "12.34"
    assert math.isclose(hs.parse_time("2026-01-01T00:00:00Z", "t"), 1767225600000)
