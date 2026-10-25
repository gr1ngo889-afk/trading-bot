"""Trend-following, long-only, volatility-sized. Run once a day after the US close.

Rules
- Enter long when price > SMA50 > SMA200 and RSI14 < 70 (uptrend, not overextended).
- Exit when price closes below SMA200 (picked on 2000-2015; the SMA50 exit whipsawed). A stop at entry - 3*ATR14 sits on the exchange as a backstop.
- Size so hitting the stop loses 1% of equity, capped at 20% of equity per position.
- 1x leverage only; total exposure never exceeds equity.
Benchmark: buy-and-hold mkts:US500 from the same start date.

Usage: python3 strategy.py < snapshot.json
snapshot = {"equity": float, "held": [symbol, ...],
            "markets": {symbol: {"price", "sma50", "sma200", "rsi14", "atr14"}}}
"""
import json
import sys

UNIVERSE = ["mkts:US500", "xyz:SMH", "xyz:XLE", "xyz:TLT", "xyz:MSFT", "xyz:GOOGL", "xyz:LLY", "xyz:COST",
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
    a = decide(10_000, [], {"mkts:US500": up})
    assert a[0]["action"] == "buy" and a[0]["notional"] == 1666.67 and a[0]["stop"] == 94
    assert decide(10_000, [], {"mkts:US500": {**up, "rsi14": 75}}) == []          # overextended
    assert decide(10_000, [], {"mkts:US500": {**up, "sma50": 85}}) == []          # not in uptrend
    assert decide(10_000, ["mkts:US500"], {"mkts:US500": up}) == []               # already held, keep
    assert decide(10_000, ["mkts:US500"], {"mkts:US500": {**up, "price": 89}})[0]["action"] == "close"
    assert decide(10_000, [], {"mkts:US500": {**up, "atr14": 0.1}})[0]["notional"] == 2000  # 20% cap
    assert decide(10_000, [], {"mkts:US500": up}, exposure=9_995) == []           # no leverage
    assert decide(10_000, [], {"mkts:US500": {**up, "sma200": None}}) == []       # short history
    dip = {**up, "price": 92}                                                     # below SMA50, above SMA200
    assert decide(10_000, ["mkts:US500"], {"mkts:US500": dip}, exit_rule="sma200") == []
    assert decide(10_000, ["mkts:US500"], {"mkts:US500": dip}, exit_rule="cross") == []
    assert decide(10_000, ["mkts:US500"], {"mkts:US500": {**dip, "sma50": 89}}, exit_rule="cross")[0]["action"] == "close"


if __name__ == "__main__":
    _selftest()
    raw = sys.stdin.read()
    if raw.strip():
        s = json.loads(raw)
        print(json.dumps(decide(s["equity"], s["held"], s["markets"], s.get("exposure", 0.0)), indent=2))
