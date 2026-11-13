"""Uptrend-pullback sleeve: buy short, sharp dips in stocks that are still above their 200-day average.

Found in 1989-2026 daily data (Shibui Finance, 35 tickers, see research/RESULTS.md). It runs next to the
trend rules in strategy.py and only uses cash the trend sleeve is not using. Off until PULLBACK_ENABLED is True.

Rules (daily, after the US close, on trading-day data, NOT Liquid's 24/7 candles)
- Signal: close > SMA200 and close - close 5 trading days ago <= -2 * ATR14.
- Size: 33% of equity per lot, never more than the cash left after the trend sleeve (1x in total), max 3 lots.
  When more symbols signal than there is room for, take the deepest drops (in ATR) first.
- Exit: close > SMA5 (the bounce came), or 5 trading days after the last signal, or close below the stop
  (signal close - 3 * ATR14). A new signal while holding restarts the 5-day clock and the stop.
- If the trend sleeve already holds the symbol, the lot is added to that position and later reduced by the
  same number of units; the trend sleeve's exchange stop stays on the position. Otherwise the lot gets its
  own exchange stop at the stop price.
- If the trend sleeve closes a symbol, its pullback lot goes with it.

snapshot["pullback"] = {"lots": {symbol: {"units", "stop", "days_since_signal"}}}
snapshot["markets"][symbol] also needs "sma5" and "close_5d_ago" (trading days).
"""

PULLBACK_ENABLED = False  # flip to True only after the user approves adopting the sleeve
DROP_ATR = 2.0
HOLD_DAYS = 5
STOP_ATR = 3
LOT = 0.33
MAX_LOTS = 3
MIN_NOTIONAL = 10


def signal(m):
    """Depth of the 5-day drop in ATRs when the market signals, else None."""
    need = ("price", "sma200", "atr14", "close_5d_ago")
    if any(m.get(k) is None for k in need) or m["atr14"] <= 0:
        return None
    drop = (m["price"] - m["close_5d_ago"]) / m["atr14"]
    if m["price"] > m["sma200"] and drop <= -DROP_ATR:
        return drop
    return None


def decide_pullback(equity, exposure, lots, markets, trend_held, trend_closing=()):
    """Return (actions, lots_after). exposure = notional already used, including the trend actions planned today."""
    actions, after = [], {}
    for sym, lot in lots.items():
        m = markets.get(sym)
        if sym in trend_closing:
            continue  # the trend close takes the whole position, lot included
        if m is None:
            after[sym] = lot  # no data today: keep, decide tomorrow
            continue
        drop = signal(m)
        if drop is not None:  # fresh signal: restart clock and stop
            after[sym] = {**lot, "stop": round(m["price"] - STOP_ATR * m["atr14"], 2), "days_since_signal": 0}
            continue
        days = lot["days_since_signal"] + 1
        why = None
        if m["price"] < lot["stop"]:
            why = f"stop: close {m['price']} < {lot['stop']}"
        elif m.get("sma5") is not None and m["price"] > m["sma5"]:
            why = f"bounce: close {m['price']} > SMA5 {round(m['sma5'], 2)}"
        elif days >= HOLD_DAYS:
            why = f"time: {days} trading days since signal"
        if why:
            act = "reduce" if sym in trend_held else "close"
            actions.append({"symbol": sym, "action": act, "units": lot["units"], "sleeve": "pullback", "why": why})
        else:
            after[sym] = {**lot, "days_since_signal": days}

    candidates = []
    for sym, m in markets.items():
        if sym in after or sym in lots or sym in trend_closing:
            continue
        drop = signal(m)
        if drop is not None:
            candidates.append((drop, sym))
    for drop, sym in sorted(candidates):  # deepest drop first
        if len(after) >= MAX_LOTS:
            break
        m = markets[sym]
        notional = min(equity * LOT, equity - exposure)
        if notional < MIN_NOTIONAL:
            break
        exposure += notional
        stop = round(m["price"] - STOP_ATR * m["atr14"], 2)
        add = sym in trend_held
        actions.append({"symbol": sym, "action": "add" if add else "buy", "notional": round(notional, 2),
                        "stop": None if add else stop, "sleeve": "pullback",
                        "why": f"pullback {round(drop, 2)} ATR in uptrend"})
        after[sym] = {"units": round(notional / m["price"], 6), "stop": stop, "days_since_signal": 0}
    return actions, after


def _selftest():
    up = {"price": 90, "sma200": 80, "sma5": 95, "atr14": 2, "close_5d_ago": 95}  # -2.5 ATR in 5 days
    assert signal(up) == -2.5
    assert signal({**up, "close_5d_ago": 93}) is None                       # -1.5 ATR: too shallow
    assert signal({**up, "sma200": 91}) is None                             # below SMA200: no uptrend
    assert signal({**up, "atr14": None}) is None

    a, lots = decide_pullback(10_000, 0, {}, {"xyz:A": up}, trend_held=[])
    assert a[0]["action"] == "buy" and a[0]["notional"] == 3300 and a[0]["stop"] == 84
    assert lots["xyz:A"] == {"units": round(3300 / 90, 6), "stop": 84, "days_since_signal": 0}
    a, _ = decide_pullback(10_000, 0, {}, {"xyz:A": up}, trend_held=["xyz:A"])
    assert a[0]["action"] == "add" and a[0]["stop"] is None                  # trend's stop covers it
    a, _ = decide_pullback(10_000, 8_000, {}, {"xyz:A": up}, trend_held=[])
    assert a[0]["notional"] == 2000                                          # only spare cash, 1x total
    assert decide_pullback(10_000, 9_995, {}, {"xyz:A": up}, trend_held=[])[0] == []

    # deepest drop first, at most 3 lots
    mk = {f"xyz:{i}": {**up, "close_5d_ago": 95 + i} for i in range(5)}
    a, lots = decide_pullback(100_000, 0, {}, mk, trend_held=[])
    assert [x["symbol"] for x in a] == ["xyz:4", "xyz:3", "xyz:2"] and len(lots) == 3

    lot = {"units": 10, "stop": 84, "days_since_signal": 0}
    hold = {**up, "close_5d_ago": 91, "price": 89, "sma5": 92}               # no new signal, below SMA5
    a, lots = decide_pullback(10_000, 0, {"xyz:A": lot}, {"xyz:A": hold}, [])
    assert a == [] and lots["xyz:A"]["days_since_signal"] == 1
    a, lots = decide_pullback(10_000, 0, {"xyz:A": lot}, {"xyz:A": {**hold, "price": 93}}, [])
    assert a[0]["action"] == "close" and a[0]["units"] == 10 and lots == {}   # bounce exit
    a, _ = decide_pullback(10_000, 0, {"xyz:A": lot}, {"xyz:A": {**hold, "price": 93}}, ["xyz:A"])
    assert a[0]["action"] == "reduce"                                        # trend keeps its part
    a, _ = decide_pullback(10_000, 0, {"xyz:A": {**lot, "days_since_signal": 4}}, {"xyz:A": hold}, [])
    assert "time" in a[0]["why"]
    a, _ = decide_pullback(10_000, 0, {"xyz:A": lot}, {"xyz:A": {**hold, "price": 83, "sma200": 85}}, [])
    assert "stop" in a[0]["why"]
    a, lots = decide_pullback(10_000, 0, {"xyz:A": {**lot, "days_since_signal": 4}}, {"xyz:A": up}, [])
    assert a == [] and lots["xyz:A"]["days_since_signal"] == 0               # re-signal restarts clock
    a, lots = decide_pullback(10_000, 0, {"xyz:A": lot}, {"xyz:A": hold}, ["xyz:A"], trend_closing=["xyz:A"])
    assert a == [] and lots == {}                                            # gone with the trend close


_selftest()
