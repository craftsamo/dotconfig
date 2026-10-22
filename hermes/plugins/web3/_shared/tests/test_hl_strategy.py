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


def test_an_entry_order_is_part_of_the_rules_and_market_keeps_the_fingerprint():
    plain = hs.rules(BREAKOUT)
    assert hs.rules({**BREAKOUT, "entry_order": "market"}) == plain == hs.rules({**BREAKOUT, "entry_order": None})
    limit = hs.rules({**BREAKOUT, "entry_order": "limit", "limit_atr": 0.5})
    assert limit == {**plain, "entry_order": "limit", "limit_atr": 0.5}
    assert hs.fingerprint(limit, "4h") != hs.fingerprint(hs.rules({**BREAKOUT, "entry_order": "limit"}), "4h")
    for bad, why in (({**BREAKOUT, "entry_order": "stop"}, "entry_order is one of"),
                     ({**BREAKOUT, "limit_atr": 0.5}, "takes entry_order limit"),
                     ({**BREAKOUT, "entry_order": "limit", "limit_atr": 2}, "less than stop_atr")):
        with pytest.raises(hs.StrategyError, match=why):
            hs.rules(bad)


def test_a_limit_rests_better_than_the_close_and_fills_only_when_traded_through_or_at_once_when_reached():
    sig, rules = {"close": 100.0, "atr": 2.0}, hs.rules({**BREAKOUT, "entry_order": "limit", "limit_atr": 0.5})
    fill = hs.limit_fill
    assert hs.limit_price("long", sig, rules) == 99.0 and hs.limit_price("short", sig, rules) == 101.0
    assert fill("long", sig, bar(0, 100.2, 101, 98.99, 100), rules, 0.0002, 0.0005) is None  # 99 only touched
    assert fill("long", sig, bar(0, 100.2, 101, 98.9, 100), rules, 0.0002, 0.0005) == (99.0, False)
    assert fill("short", sig, bar(0, 99.0, 101.01, 98, 100), rules, 0.0002, 0.0005) is None
    assert fill("short", sig, bar(0, 99.0, 101.1, 98, 100), rules, 0.0002, 0.0005) == (101.0, False)
    assert fill("long", sig, bar(0, 100.2, 101, 99.0, 100), rules, 0.0, 0.0005) == (99.0, False)  # through 0: a touch
    # the market already there: it takes the book at once, with slippage, never past its own price
    assert fill("long", sig, bar(0, 98.0, 99, 97.9, 98), rules, 0.0002, 0.0005) == (pytest.approx(98.049), True)
    assert fill("long", sig, bar(0, 98.99, 99.5, 98.5, 99), rules, 0.0002, 0.0005) == (99.0, True)
    assert fill("short", sig, bar(0, 101.5, 102, 101, 101.5), rules, 0.0002, 0.0005) == (pytest.approx(101.44925), True)


# a breakout closes at 105; the next bar opens above it, only touches 105, closes at 107 and still holds
# the breakout; the one after opens above 107 and trades back through it
TOUCHED = flat(10) + [bar(10, 100, 106, 100, 105), bar(11, 106, 108, 105, 107), bar(12, 107.5, 109, 106.5, 108),
                      bar(13, 108, 109, 107.5, 108)]


def mirrored(series):
    """The same bars upside down around 100: a long's path becomes a short's."""
    return [{"t": b["t"], "o": 200 - b["o"], "h": 200 - b["l"], "l": 200 - b["h"], "c": 200 - b["c"]} for b in series]


@pytest.mark.parametrize("side", ["long", "short"])
def test_an_unfilled_limit_enters_nothing_or_at_market_after_it_as_its_rules_say(side):
    series = TOUCHED if side == "long" else mirrored(TOUCHED)
    price = (lambda p: str(p)) if side == "long" else (lambda p: str(200 - p))
    cost = hs.costs({"taker_bps": 0, "slippage_bps": 0, "maker_bps": 10, "funding": "none"})
    limits = {"exposure_pct": 100, "max_leverage": 10}
    plain = hs.simulate(series, hs.rules(BREAKOUT), "4h", cost, limits)
    assert plain["trades"][0]["entry"] == price(106) and "limit_entries" not in hs.metrics(plain)
    # a limit only: missed at 105, then placed again at the next close, 107, and filled there as a maker
    limit = hs.simulate(series, hs.rules({**BREAKOUT, "entry_order": "limit"}), "4h", cost, limits)
    assert [(t["side"], t["entry"]) for t in limit["trades"]] == [(side, price(107))] and limit["totals"]["fees"] > 0
    assert hs.metrics(limit)["limit_entries"] == {"placed": 2, "filled": 1, "fill_rate": 0.5, "crossed": 0,
                                                  "market_after": 0, "missed": 1}
    # then market: the missed limit enters at the next open, as a taker
    after = hs.simulate(series, hs.rules({**BREAKOUT, "entry_order": "limit_then_market"}), "4h", cost, limits)
    assert [t["entry"] for t in after["trades"]] == [price(107.5)] and after["totals"]["fees"] == 0
    assert hs.metrics(after)["limit_entries"] == {"placed": 1, "filled": 0, "fill_rate": 0.0, "crossed": 0,
                                                  "market_after": 1, "missed": 0}
    # ... unless the close after it no longer holds the side
    flat_from_12 = hs.timeline([{"from": series[12]["t"], "to": series[13]["t"] + H4, "direction": "flat"}])
    held = hs.simulate(series, hs.rules({**BREAKOUT, "entry_order": "limit_then_market"}), "4h", cost, limits,
                       stance=flat_from_12)
    assert held["trades"] == [] and hs.metrics(held)["limit_entries"]["missed"] == 1
    # with no trade-through asked for, the touch fills
    touch = hs.simulate(series, hs.rules({**BREAKOUT, "entry_order": "limit"}), "4h",
                        {**cost, "limit_through_bps": 0}, limits)
    assert [t["entry"] for t in touch["trades"]] == [price(105)]


def test_a_maker_rebate_never_turns_a_stopped_trade_into_a_positive_r():
    # ranges of a cent, so the stop sits closer below the limit than the rebate is worth
    series = [bar(i, 100, 100.005, 99.995, 100) for i in range(10)]
    series += [bar(10, 100, 100.02, 99.995, 100.015), bar(11, 100.0, 100.0, 99.9, 99.9)]
    rules = hs.rules({**BREAKOUT, "entry_order": "limit", "limit_atr": 1.5})
    cost = hs.costs({"slippage_bps": 0, "maker_bps": -1, "funding": "none"})
    trade = hs.simulate(series, rules, "4h", cost, {"exposure_pct": 100, "max_leverage": 10})["trades"][0]
    assert trade["reason"] == "stop" and trade["pnl"] < 0 and trade["r"] < 0


def test_a_limit_the_market_opened_through_fills_at_once_as_a_taker():
    series = flat(10) + [bar(10, 100, 106, 100, 105), bar(11, 104.9, 108, 104.5, 107)]
    cost = hs.costs({"taker_bps": 10, "slippage_bps": 5, "maker_bps": 0, "funding": "none"})
    run = hs.simulate(series, hs.rules({**BREAKOUT, "entry_order": "limit_then_market"}), "4h", cost,
                      {"exposure_pct": 100, "max_leverage": 10})
    assert run["trades"][0]["entry"] == "104.95" and run["totals"]["fees"] > 0  # 104.9 and slippage, as a taker
    assert hs.metrics(run)["limit_entries"]["crossed"] == 1


def test_the_gate_reads_a_limits_price_and_the_market_entry_after_it_as_the_backtest_does():
    rules = hs.rules({**BREAKOUT, "entry_order": "limit_then_market", "limit_atr": 0.5})
    ev = hs.evaluate(TOUCHED[:11], rules, {"direction": "both"}, None)
    atr = hs.indicators(TOUCHED[:11], rules)["atr"][10]
    assert ev["open"] == "long" and ev["limit"] == pytest.approx(105 - 0.5 * atr)
    assert "limit" not in hs.evaluate(TOUCHED[:11], hs.rules(BREAKOUT), {"direction": "both"}, None)
    # the close after the missed limit still holds the long: an entry from that close, its stop from there
    after = hs.market_after_limit(TOUCHED[:12], rules, {"direction": "both"}, "long")
    assert after["open"] == "long" and after["price"] == 107 and after["stop"] < 107
    assert hs.market_after_limit(TOUCHED[:12], rules, {"direction": "flat"}, "long") is None
    assert hs.market_after_limit(mirrored(TOUCHED)[:12], rules, {"direction": "both"}, "long") is None


def test_a_limit_filled_in_a_bar_that_reaches_the_stop_is_stopped_in_it():
    series = flat(10) + [bar(10, 100, 106, 100, 105), bar(11, 105, 106, 80, 85)]
    cost = hs.costs({"taker_bps": 0, "slippage_bps": 0, "maker_bps": 0, "funding": "none"})
    run = hs.simulate(series, hs.rules({**BREAKOUT, "entry_order": "limit"}), "4h", cost,
                      {"exposure_pct": 100, "max_leverage": 10})
    trade = run["trades"][0]
    atr = hs.indicators(series, hs.rules(BREAKOUT))["atr"][10]
    assert trade["entry"] == "105" and trade["reason"] == "stop"
    assert float(trade["exit"]) == pytest.approx(105 - 2 * atr, rel=1e-4)


def test_a_walk_forward_grid_may_choose_the_entry_order():
    series = walk(1200)
    cost = hs.costs({"funding": "none"})
    rates = hs.funding_by_bar(series, "4h", None, 0.0, "none")
    out = hs.walk_forward(series, hs.rules(BREAKOUT), "4h", cost, {"exposure_pct": 70, "max_leverage": 2},
                          {"grid": {"entry_order": ["market", "limit"], "limit_atr": [0, 0.5]}, "folds": 2,
                           "min_trades": 0}, rates=rates, stance=[], direction="both")
    assert out["candidates"] == 3  # a limit_atr with a market entry is no rule set
    chose_limit = any(f["chosen"].get("entry_order") == "limit" for f in out["folds"])
    assert ("limit_entries" in out["out_of_sample"]) == chose_limit
    if chose_limit:  # the unseen windows' counts add up to the stitched one
        for key in ("placed", "filled", "missed"):
            assert out["out_of_sample"]["limit_entries"][key] == sum(
                f["test"].get("limit_entries", {}).get(key, 0) for f in out["folds"])
    for f in out["folds"]:
        assert f["chosen_fingerprint"] == hs.fingerprint(hs.rules({"kind": "breakout", **f["chosen"]}), "4h")


def test_one_market_of_simulate_many_is_simulate():
    series, rules = walk(400), hs.rules({**BREAKOUT, "trail_atr": 2, "entry_order": "limit_then_market"})
    cost, limits = hs.costs({"funding": "none"}), {"exposure_pct": 70, "max_leverage": 2}
    one = hs.simulate(series, rules, "4h", cost, limits, trade_from=20)
    many = hs.simulate_many({"BTC": series}, {"BTC": rules}, "4h", cost, limits, trade_from=20)
    assert many == one and "market" not in one["trades"][0]
    wf = hs.walk_forward(series, rules, "4h", cost, limits, {"grid": {"entry": [5, 8]}, "folds": 2, "min_trades": 0},
                         rates=hs.funding_by_bar(series, "4h", None, 0.0, "none"), stance=[], direction="both")
    wf_many = hs.walk_forward_many({"BTC": series}, rules, "4h", cost, limits,
                                   {"grid": {"entry": [5, 8]}, "folds": 2, "min_trades": 0},
                                   rates_by={"BTC": hs.funding_by_bar(series, "4h", None, 0.0, "none")}, stance=[],
                                   direction="both")
    assert wf_many["out_of_sample"] == wf["out_of_sample"] and wf_many["markets"] == ["BTC"]
    assert [f["chosen"]["BTC"] for f in wf_many["folds"]] == [f["chosen"] for f in wf["folds"]]


def test_markets_traded_together_share_the_cash_and_the_exposure_bound():
    rules, cost = hs.rules(BREAKOUT), hs.costs({"taker_bps": 0, "slippage_bps": 0, "funding": "none"})
    both = {"A": TOUCHED, "B": TOUCHED}  # the same breakout in two markets at once
    wide = hs.simulate_many(both, {"A": rules, "B": rules}, "4h", cost, {"exposure_pct": 100, "max_leverage": 10})
    assert [t["market"] for t in wide["trades"]] == ["A", "B"] and wide["trades"][0]["pnl"] == wide["trades"][1]["pnl"]
    # a bound the first entry fills leaves the second a smaller one, or none
    tight = hs.simulate_many(both, {"A": rules, "B": rules}, "4h", cost, {"exposure_pct": 30, "max_leverage": 10})
    assert [t["market"] for t in tight["trades"]] == ["A", "B"] and tight["trades"][1]["pnl"] < tight["trades"][0]["pnl"]
    none = hs.simulate_many(both, {"A": rules, "B": rules}, "4h", cost, {"exposure_pct": 18, "max_leverage": 10})
    assert [t["market"] for t in none["trades"]] == ["A"]
    # the curve is the account's: one point per shared time, both positions marked
    assert len(wide["curve"]) == len(TOUCHED) and wide["totals"]["bars_held"] == 3
    assert wide["buy_hold_pct"] == pytest.approx((TOUCHED[-1]["c"] / TOUCHED[0]["o"] - 1) * 100)


def test_an_entry_sees_the_other_markets_only_as_they_stood_at_its_open():
    rules, cost = hs.rules(BREAKOUT), hs.costs({"taker_bps": 0, "slippage_bps": 0, "funding": "none"})
    limits = {"exposure_pct": 30, "max_leverage": 10}  # tight: B's size is what A leaves

    def b_pnl(a_series):
        run = hs.simulate_many({"A": a_series, "B": TOUCHED}, {"A": rules, "B": rules}, "4h", cost, limits)
        return [t["pnl"] for t in run["trades"] if t["market"] == "B"]

    plain = b_pnl(TOUCHED)
    # A's bar runs away after the open, or its stop fires inside the bar: B, sized at the open, sees neither
    assert b_pnl(TOUCHED[:11] + [bar(11, 106, 140, 105, 139), bar(12, 139, 141, 138, 140), bar(13, 140, 141, 139, 140)]) == plain
    assert b_pnl(TOUCHED[:11] + [bar(11, 106, 108, 80, 85), bar(12, 85, 86, 84, 85), bar(13, 85, 86, 84, 85)]) == plain


def test_an_entry_is_sized_from_the_accounts_value_with_the_others_unrealized_result():
    rules, cost = hs.rules(BREAKOUT), hs.costs({"taker_bps": 0, "slippage_bps": 0, "funding": "none"})
    limits = {"exposure_pct": 100, "max_leverage": 10}
    later = flat(11) + [bar(11, 100, 106, 100, 105), bar(12, 106, 108, 105, 107), bar(13, 107.5, 109, 106.5, 108)]

    def b_pnl(a_open_12):  # A is held from bar 11; B enters at bar 12's open, where A's mark is a_open_12
        a = TOUCHED[:12] + [bar(12, a_open_12, a_open_12 + 2, a_open_12 - 1, a_open_12 + 1), bar(13, 108, 109, 107.5, 108)]
        run = hs.simulate_many({"A": a, "B": later}, {"A": rules, "B": rules}, "4h", cost, limits)
        return next(t["pnl"] for t in run["trades"] if t["market"] == "B")

    assert b_pnl(150.0) > b_pnl(107.5) > b_pnl(90.0)


def test_a_limit_resting_through_the_bar_reserves_its_value_for_the_other_markets():
    cost, limits = hs.costs({"taker_bps": 0, "slippage_bps": 0, "funding": "none"}), {"exposure_pct": 30, "max_leverage": 10}
    market, limit = hs.rules(BREAKOUT), hs.rules({**BREAKOUT, "entry_order": "limit_then_market"})
    alone = hs.simulate_many({"B": TOUCHED}, {"B": market}, "4h", cost, limits)["trades"][0]["pnl"]
    # A's limit at 105 rests unfilled through bar 11 (only touched): B's entry at that open is sized after it
    beside = hs.simulate_many({"A": TOUCHED, "B": TOUCHED}, {"A": limit, "B": market}, "4h", cost, limits)
    b = next(t for t in beside["trades"] if t["market"] == "B")
    assert b["pnl"] < alone
    # whether the bar then trades through A's limit (a fill the open could not know) changes nothing for B
    traded_through = TOUCHED[:11] + [bar(11, 106, 108, 104.9, 107)] + TOUCHED[12:]
    filled = hs.simulate_many({"A": traded_through, "B": TOUCHED}, {"A": limit, "B": market}, "4h", cost, limits)
    assert [t["market"] for t in filled["trades"]] == ["A", "B"]
    assert next(t for t in filled["trades"] if t["market"] == "B")["pnl"] == b["pnl"]


def test_a_position_held_on_through_a_time_its_market_has_no_bar_at_counts_as_held():
    rules, cost = hs.rules(BREAKOUT), hs.costs({"funding": "none"})
    sparse = TOUCHED[:12] + TOUCHED[13:]  # B has no bar at time 12, while it holds from 11 to 13
    run = hs.simulate_many({"A": flat(14), "B": sparse}, {"A": rules, "B": rules}, "4h", cost,
                           {"exposure_pct": 100, "max_leverage": 10})
    assert [t["market"] for t in run["trades"]] == ["B"] and run["totals"]["bars_held"] == 3


def test_a_market_without_a_bar_at_a_time_sits_it_out():
    a, b = walk(300, seed=1), walk(300, seed=2)[::2]  # B has every other bar
    rules, cost = hs.rules(BREAKOUT), hs.costs({"funding": "none"})
    run = hs.simulate_many({"A": a, "B": b}, {"A": rules, "B": rules}, "4h", cost, {"exposure_pct": 70, "max_leverage": 2})
    assert len(run["curve"]) == 300 and run["bars"] == 300 and {t["market"] for t in run["trades"]} == {"A", "B"}
    wf = hs.walk_forward_many({"A": walk(1200, seed=3), "B": walk(1200, seed=4)}, rules, "4h", cost,
                              {"exposure_pct": 70, "max_leverage": 2},
                              {"grid": {"entry": [5, 8]}, "folds": 2, "min_trades": 0},
                              rates_by={"A": [(0.0, 0)] * 1200, "B": [(0.0, 0)] * 1200}, stance=[], direction="both")
    assert len(wf["folds"]) == 2 and set(wf["folds"][0]["chosen"]) == {"A", "B"}
    assert wf["out_of_sample"]["trades"] == sum(f["test"]["trades"] for f in wf["folds"])


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


def test_each_trade_keeps_its_equity_path_and_their_order_rebuilds_the_drawdown():
    for seed, extra in ((1, {}), (2, {"trail_atr": 2}), (3, {"entry": 40})):
        run = hs.simulate(walk(3000, seed), hs.rules({**BREAKOUT, "entry": 20, "exit": 10, "atr": 14, **extra}), "4h",
                          hs.costs({}), hs.backtest_limits({}))
        m = hs.metrics(run)
        assert len(run["paths"]) == m["trades"] > hs.MC_MIN_TRADES
        assert all(low <= min(1.0, end) and high >= max(1.0, end) and 0 <= dd < 1 for end, low, high, dd in run["paths"])
        dd, end, _ = hs._compose(run["paths"])
        # the composed marks are the curve's, plus an exit at an open the next entry shares
        assert dd * 100 >= m["max_drawdown_pct"] - 0.005 and dd * 100 == pytest.approx(m["max_drawdown_pct"], abs=0.1)
        assert (end - 1) * 100 == pytest.approx(m["return_pct"], abs=0.01)


def test_a_drawdown_inside_a_trade_counts_from_the_peak_it_started_under():
    # +20% then flat; then a trade that dips 15% under its start and ends at -10%; then one that gains 30%
    # at its high and gives back 20% of it
    paths = [(1.2, 1.0, 1.2, 0.0), (0.9, 0.85, 1.0, 0.15), (1.04, 1.0, 1.3, 0.2)]
    dd, end, streak = hs._compose(paths)
    assert dd == pytest.approx(0.2) and end == pytest.approx(1.2 * 0.9 * 1.04) and streak == 1
    # the same dip under an earlier, higher peak is deeper than the trade alone
    dd, _, _ = hs._compose([(1.0, 0.9, 1.5, 0.4), (0.9, 0.85, 1.0, 0.15)])
    assert dd == pytest.approx(1 - 0.85 / 1.5)
    assert hs._compose([(0.9, 0.9, 1.0, 0.1)] * 3 + [(1.1, 1.0, 1.1, 0.0)] + [(0.95, 0.95, 1.0, 0.05)])[2] == 3


def test_a_trade_stopped_in_its_entry_bar_has_only_its_exit_on_its_path():
    series = flat(10) + [bar(10, 100, 106, 100, 105), bar(11, 110, 111, 90, 100), bar(12, 100, 101, 99, 100)]
    cost = hs.costs({"taker_bps": 0, "slippage_bps": 0, "funding": "none"})
    run = hs.simulate(series, hs.rules(BREAKOUT), "4h", cost, {"exposure_pct": 100, "max_leverage": 10})
    assert run["trades"][0]["reason"] == "stop" and run["trades"][0]["open"] == run["trades"][0]["close"]
    (end, low, high, dd), = run["paths"]
    assert end == low < 1 and high == 1.0 and dd == pytest.approx(1 - end)
    assert hs._compose(run["paths"])[0] * 100 == pytest.approx(hs.metrics(run)["max_drawdown_pct"], abs=0.005)


def test_a_trade_that_leaves_no_equity_ends_the_sequence_as_the_backtest_does():
    # a short at full exposure, then a gap through its stop to two and a half times the entry
    series = flat(10) + [bar(10, 100, 100, 94, 95), bar(11, 95, 96, 94, 95), bar(12, 250, 251, 249, 250),
                         bar(13, 250, 251, 249, 250)]
    cost = hs.costs({"taker_bps": 0, "slippage_bps": 0, "funding": "none"})
    run = hs.simulate(series, hs.rules({**BREAKOUT, "risk_pct": 5}), "4h", cost, {"exposure_pct": 100, "max_leverage": 10})
    m = hs.metrics(run)
    assert run["end_equity"] < 0 and len(run["trades"]) == 1  # nothing opens after it
    dd, end, _ = hs._compose(run["paths"])
    assert dd * 100 == pytest.approx(m["max_drawdown_pct"], abs=0.005) and dd > 1
    assert (end - 1) * 100 == pytest.approx(m["return_pct"], abs=0.005)
    # a later trade in a draw is never taken from an account already gone
    assert hs._compose(run["paths"] + [(1.5, 1.0, 1.5, 0.0)])[1] == pytest.approx(end)


def test_percentiles_are_read_by_nearest_rank():
    values = [float(v) for v in range(1, 101)]
    assert [hs._rank(values, s) for s in (0.05, 0.5, 0.95, 0.99, 1.0)] == [5.0, 50.0, 95.0, 99.0, 100.0]
    assert hs._rank([7.0], 0.95) == hs._rank([7.0], 0.05) == 7.0
    assert hs._rank([1.0, 2.0, 3.0], 0.5) == 2.0


def test_a_monte_carlo_redraws_the_trades_the_same_way_for_the_same_request():
    run = hs.simulate(walk(3000), hs.rules({**BREAKOUT, "entry": 20, "exit": 10, "atr": 14}), "4h", hs.costs({}),
                      hs.backtest_limits({}))
    mc = hs.monte_carlo(run, "BTC:abc:1")
    assert mc == hs.monte_carlo(run, "BTC:abc:1") and mc != hs.monte_carlo(run, "BTC:abc:2")
    assert mc["runs"] == hs.MC_RUNS and mc["trades"] == len(run["trades"])
    dd, ret, streak = mc["max_drawdown_pct"], mc["return_pct"], mc["losing_streak"]
    assert 0 < dd["p50"] <= dd["p95"] <= dd["p99"] < 100 and ret["p5"] <= ret["p50"] and streak["p50"] <= streak["p95"]
    assert dd["observed"] == pytest.approx(hs.metrics(run)["max_drawdown_pct"], abs=0.1)
    few = hs.simulate(walk(400), hs.rules(BREAKOUT), "4h", hs.costs({}), hs.backtest_limits({}))
    few["paths"] = few["paths"][:hs.MC_MIN_TRADES - 1]
    assert hs.monte_carlo(few, "x") is None


def test_walk_forward_only_ever_trades_rules_chosen_on_earlier_data():
    series = walk(3000)
    base = hs.rules({**BREAKOUT, "entry": 20, "exit": 10, "atr": 14})
    rates = hs.funding_by_bar(series, "4h", None, hs.BASELINE_FUNDING, "venue")
    out = hs.walk_forward(series, base, "4h", hs.costs({}), hs.backtest_limits({}),
                          {"grid": {"entry": [20, 40], "exit": [10, 20]}, "folds": 3},
                          rates=rates, stance=[], direction="both", seed="BTC:x:1")
    assert len(out["folds"]) == 3 and out["candidates"] == 4
    oos = out["out_of_sample"]
    assert oos["monte_carlo"]["trades"] == oos["trades"]
    assert oos["monte_carlo"]["max_drawdown_pct"]["observed"] == pytest.approx(oos["max_drawdown_pct"], abs=0.1)
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


OOS = {"return_pct": 40.1, "max_drawdown_pct": 18.5, "mar": 0.9, "trades": 64,
       "monte_carlo": {"runs": 1000, "trades": 64, "max_drawdown_pct": {"observed": 18.5, "p50": 17.0, "p95": 27.3,
                                                                          "p99": 33.0}}}


def test_a_variant_keeps_its_recorded_out_of_sample_or_none():
    assert hs.spec(spec_raw())["variants"]["fast"]["out_of_sample"] is None
    raw = spec_raw()
    raw["variants"]["fast"]["validated"]["out_of_sample"] = OOS
    assert hs.spec(raw)["variants"]["fast"]["out_of_sample"] == {
        "max_drawdown_pct": 18.5, "mar": 0.9, "trades": 64, "monte_carlo_p95_drawdown_pct": 27.3}
    before_mc = {k: v for k, v in OOS.items() if k != "monte_carlo"}
    assert hs.out_of_sample({**before_mc, "mar": None})["monte_carlo_p95_drawdown_pct"] is None
    for bad in (None, {}, {**OOS, "trades": 0}, {**OOS, "max_drawdown_pct": "18"}, {**OOS, "max_drawdown_pct": 120},
                {**OOS, "trades": True}, {**OOS, "mar": "high"}):
        assert hs.out_of_sample(bad) is None
    assert hs.out_of_sample({**OOS, "monte_carlo": None})["monte_carlo_p95_drawdown_pct"] is None


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


def test_a_breaker_is_read_from_the_spec_and_a_bad_one_holds_entries_without_failing_the_spec():
    assert hs.spec(spec_raw())["breaker"] is None and hs.spec(spec_raw())["breaker_problem"] is None
    s = hs.spec(spec_raw(breaker={"max_drawdown_pct": 25, "reset": None}))
    assert s["breaker"] == {"max_drawdown_pct": 25.0, "reset": None}
    reset = hs.spec(spec_raw(breaker={"max_drawdown_pct": 25, "reset": "2026-10-21T10:00:00Z"}))["breaker"]["reset"]
    assert reset == hs.parse_time("2026-10-21T10:00:00Z", "t")
    for bad, why in (({"max_drawdown_pct": 0.5}, "between 1 and 90"), ({"max_drawdown_pct": 95}, "between 1 and 90"),
                     ({"max_drawdown_pct": 25, "reset": "yesterday"}, "breaker.reset"), ({"max_drawdown_pct": 25, "x": 1}, "not x"),
                     ([25], "breaker is"), ({}, "max_drawdown_pct must be a number")):
        s = hs.spec(spec_raw(breaker=bad))
        assert s["breaker"] is None and why in s["breaker_problem"], (bad, s["breaker_problem"])


def test_the_breaker_index_follows_the_strategys_result_against_the_account_and_trips_once():
    m, dd = hs.breaker_step(None, 0.0, 1000.0, 20, None, NOW)
    assert m == {"index": 1.0, "peak": 1.0, "tripped": None, "since": NOW} and dd == 0
    m, dd = hs.breaker_step(m, 100.0, 1000.0, 20, None, NOW + 1)  # +10%
    assert m["index"] == pytest.approx(1.1) and m["peak"] == pytest.approx(1.1) and dd == 0
    # a withdrawal halves the account: the same 110 USDC loss now counts as 20% of it
    m, dd = hs.breaker_step(m, -110.0, 550.0, 20, None, NOW + 2)
    assert m["index"] == pytest.approx(0.88) and dd == pytest.approx(20) and m["tripped"] == {"at": NOW + 2, "drawdown_pct": 20.0}
    # a recovery does not untrip it, and the trip keeps its first figures
    m, dd = hs.breaker_step(m, 220.0, 440.0, 20, None, NOW + 3)
    assert m["tripped"]["at"] == NOW + 2 and dd == 0
    # no limit keeps the index without tripping
    free, dd = hs.breaker_step(None, -500.0, 1000.0, None, None, NOW)
    assert free["tripped"] is None and dd == pytest.approx(50)
    # nothing to measure against: the index stays
    assert hs.breaker_step(m, -50.0, 0.0, 20, None, NOW + 4)[0]["index"] == m["index"]
    gone, dd = hs.breaker_step(None, -2000.0, 1000.0, 20, None, NOW)
    assert gone["index"] == 0.0 and dd == 100.0


def test_only_a_reset_written_after_the_trip_resumes_and_it_restarts_the_high():
    m, _ = hs.breaker_step(None, -300.0, 1000.0, 25, None, NOW)
    assert m["tripped"]["at"] == NOW
    for early in (NOW - 1, NOW, NOW + 10 * hs.DAY_MS):  # before or at the trip, or not yet come
        assert hs.breaker_step(m, 0.0, 700.0, 25, early, NOW + hs.HOUR_MS)[0]["tripped"] is not None
    m, dd = hs.breaker_step(m, 0.0, 700.0, 25, NOW + 5, NOW + hs.HOUR_MS)
    assert m["tripped"] is None and dd == 0 and m["index"] == m["peak"] == 1.0 and m["since"] == NOW + 5
    m, dd = hs.breaker_step(m, -70.0, 700.0, 25, NOW + 5, NOW + 2 * hs.HOUR_MS)  # the same reset does nothing more
    assert m["tripped"] is None and dd == pytest.approx(10)
    # an account the strategy emptied resumes too, once refunded and reset
    gone, _ = hs.breaker_step(None, -1200.0, 1000.0, 25, None, NOW)
    back, dd = hs.breaker_step(gone, 0.0, 0.0, 25, NOW + 1, NOW + 2)
    assert back["tripped"] is None and dd == 0
    assert hs.breaker_step(back, 100.0, 1000.0, 25, NOW + 1, NOW + 3)[0]["index"] == pytest.approx(1.1)


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
