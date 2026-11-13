"""Trend-following, long-only, volatility-sized. Run once a day after the US close.

Rules
- Enter long when price > SMA50 > SMA200 and RSI14 < 70 (uptrend, not overextended).
- Exit when price closes below SMA200 (picked on 2000-2015; the SMA50 exit whipsawed). A stop at entry - 3*ATR14 sits on the exchange as a backstop.
- Size so hitting the stop loses 1% of equity, capped at 20% of equity per position.
- 1x leverage only; total exposure never exceeds equity.
Benchmark: buy-and-hold xyz:SP500 from the same start date.

Usage: python3 strategy.py < snapshot.json
snapshot = {"equity": float, "held": [symbol, ...],
            "markets": {symbol: {"price", "sma50", "sma200", "rsi14", "atr14"}}}
"""
import json
import sys

UNIVERSE = ["xyz:SP500", "xyz:SMH", "xyz:XLE", "xyz:TLT", "xyz:MSFT", "xyz:GOOGL", "xyz:LLY", "xyz:COST",
            "xyz:AAPL", "xyz:AMZN", "xyz:NVDA", "xyz:META"]
RISK_PER_TRADE = 0.01
STOP_ATR = 3
MAX_POSITION = 0.20
MIN_NOTIONAL = 10


def decide(equity, held, markets, exposure=0.0, exit_rule="sma200"):
    actions = []
    for sym in UNIVERSE:
        m = markets.get(sym)
        if not m:
            continue
        p = m["price"]
        if sym in held:
            # exit rules: "sma50" price < SMA50, "sma200" price < SMA200, "cross" SMA50 < SMA200
            a, b = {"sma50": (p, m["sma50"]), "sma200": (p, m["sma200"]), "cross": (m["sma50"], m["sma200"])}[exit_rule]
            if None not in (a, b) and a < b:
                actions.append({"symbol": sym, "action": "close", "why": f"{exit_rule} exit: {a} < {b}"})
            continue
        if None in (m["sma50"], m["sma200"], m["rsi14"], m["atr14"]):
            continue  # too little history (newly listed market); joins once it has 200 days
        if not (p > m["sma50"] > m["sma200"] and m["rsi14"] < 70):
            continue
        stop = p - STOP_ATR * m["atr14"]
        notional = min(equity * RISK_PER_TRADE * p / (p - stop), equity * MAX_POSITION, equity - exposure)
        if notional < MIN_NOTIONAL:
            continue
        exposure += notional
        actions.append({"symbol": sym, "action": "buy", "notional": round(notional, 2),
                        "stop": round(stop, 2), "why": f"uptrend, RSI {m['rsi14']}"})
    return actions


def _selftest():
    up = {"price": 100, "sma50": 95, "sma200": 90, "rsi14": 55, "atr14": 2}
    # risk $100 over a $6 stop distance on a $100 stock -> ~$1666 notional
    a = decide(10_000, [], {"xyz:SP500": up})
    assert a[0]["action"] == "buy" and a[0]["notional"] == 1666.67 and a[0]["stop"] == 94
    assert decide(10_000, [], {"xyz:SP500": {**up, "rsi14": 75}}) == []          # overextended
    assert decide(10_000, [], {"xyz:SP500": {**up, "sma50": 85}}) == []          # not in uptrend
    assert decide(10_000, ["xyz:SP500"], {"xyz:SP500": up}) == []               # already held, keep
    assert decide(10_000, ["xyz:SP500"], {"xyz:SP500": {**up, "price": 89}})[0]["action"] == "close"
    assert decide(10_000, [], {"xyz:SP500": {**up, "atr14": 0.1}})[0]["notional"] == 2000  # 20% cap
    assert decide(10_000, [], {"xyz:SP500": up}, exposure=9_995) == []           # no leverage
    assert decide(10_000, [], {"xyz:SP500": {**up, "sma200": None}}) == []       # short history
    dip = {**up, "price": 92}                                                     # below SMA50, above SMA200
    assert decide(10_000, ["xyz:SP500"], {"xyz:SP500": dip}, exit_rule="sma200") == []
    assert decide(10_000, ["xyz:SP500"], {"xyz:SP500": dip}, exit_rule="cross") == []
    assert decide(10_000, ["xyz:SP500"], {"xyz:SP500": {**dip, "sma50": 89}}, exit_rule="cross")[0]["action"] == "close"
    # plan(): sleeve stays off unless enabled; when on, it only uses cash left after the trend buys
    snap = {"equity": 10_000, "held": [], "exposure": 0,
            "markets": {"xyz:SP500": {**up, "sma200": 90, "sma5": 99, "close_5d_ago": 105}}}  # -2.5 ATR dip
    assert [a["sleeve"] for a in plan(snap, False)["actions"]] == ["trend"]
    p = plan(snap, True)["actions"]
    assert [(a["sleeve"], a["action"]) for a in p] == [("trend", "buy"), ("pullback", "add")]
    assert p[1]["notional"] == 3300 and p[1]["stop"] is None


def plan(s, pullback_on=None):
    """Trend actions, then (when enabled) pullback-sleeve actions using only the cash the trend sleeve leaves.
    Returns {"actions": [...], "pullback_lots": {...}}; save pullback_lots to pullback_state.json after fills."""
    import pullback
    exposure = s.get("exposure", 0.0)
    actions = [dict(a, sleeve="trend") for a in decide(s["equity"], s["held"], s["markets"], exposure)]
    lots = s.get("pullback", {}).get("lots", {})
    if pullback.PULLBACK_ENABLED if pullback_on is None else pullback_on:
        used = exposure + sum(a["notional"] for a in actions if a["action"] == "buy")  # closes not netted: conservative
        closing = [a["symbol"] for a in actions if a["action"] == "close"]
        buying = [a["symbol"] for a in actions if a["action"] == "buy"]
        trend_held = [h for h in s["held"] if h not in closing] + buying
        pb, lots = pullback.decide_pullback(s["equity"], used, lots, s["markets"], trend_held, closing)
        actions += pb
    return {"actions": actions, "pullback_lots": lots}


if __name__ == "__main__":
    _selftest()
    raw = sys.stdin.read()
    if raw.strip():
        # --pullback previews the sleeve even while PULLBACK_ENABLED is False (nothing is traded from a preview)
        print(json.dumps(plan(json.loads(raw), True if "--pullback" in sys.argv else None), indent=2))
