"""Replay strategy.decide() on daily candles, with fees and funding.

Fills at the daily close; a stop fills at the stop price, or at the open if the day gaps below it.
Usage:
  python3 backtest.py        2000-2015 of the real stocks (Yahoo), funding charged at last year's Liquid rates
  python3 backtest.py test R 2016-today, exit rule R only (pick R on 2000-2015 first; look at this once)
  python3 backtest.py hl     the last year on Liquid's own markets (Hyperliquid), actual hourly funding
Candles and funding are cached in data/.
"""
import json
import os
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone

from strategy import UNIVERSE, decide

HL_API = "https://api.hyperliquid.xyz/info"
YAHOO = "https://query1.finance.yahoo.com/v8/finance/chart/{}?period1=946684800&period2={}&interval=1d"
TICKER = {"xyz:SP500": "SPY", "xyz:SMH": "SMH", "xyz:XLE": "XLE", "xyz:TLT": "TLT", "xyz:MSFT": "MSFT",
          "xyz:GOOGL": "GOOGL", "xyz:LLY": "LLY", "xyz:COST": "COST", "xyz:AAPL": "AAPL", "xyz:AMZN": "AMZN",
          "xyz:NVDA": "NVDA", "xyz:META": "META"}
# shortcut: last year's average Liquid funding (APR, longs pay) applied to all 26 years; real funding moves with demand
FUNDING_APR = {"xyz:SP500": 0.022, "xyz:SMH": 0.148, "xyz:XLE": 0.161, "xyz:TLT": 0.211, "xyz:MSFT": 0.073,
               "xyz:GOOGL": 0.106, "xyz:LLY": 0.165, "xyz:COST": 0.081, "xyz:AAPL": 0.022, "xyz:AMZN": 0.087,
               "xyz:NVDA": 0.104, "xyz:META": 0.073}
FEE = 0.0005  # per side; shortcut: flat taker fee, check HIP-3 fee schedule before going live
DAY = 86_400_000
DATA = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")


def get(url, body=None):
    req = urllib.request.Request(url, body and json.dumps(body).encode(),
                                 {"Content-Type": "application/json", "User-Agent": "Mozilla/5.0"})
    for wait in (2, 4, 8, 16, 32, None):
        try:
            return json.load(urllib.request.urlopen(req, timeout=30))
        except urllib.error.HTTPError as e:
            if e.code != 429 or wait is None:
                raise
            time.sleep(wait)


def cached(name, fetch):
    path = os.path.join(DATA, name.replace(":", "_") + ".json")
    if not os.path.exists(path):
        os.makedirs(DATA, exist_ok=True)
        json.dump(fetch(), open(path, "w"))
    return json.load(open(path))


def hl_funding(coin, start):
    out = []
    while True:
        page = get(HL_API, {"type": "fundingHistory", "coin": coin, "startTime": start})
        out += page
        if len(page) < 500:
            return out
        start = page[-1]["time"] + 1
        time.sleep(1)


def load_hl():
    """{symbol: {day_ms: (o, h, l, c)}}, {symbol: {day_ms: funding rate for the day}}"""
    bars, fund = {}, {}
    for s in UNIVERSE:
        candles = cached(s + "_1d", lambda: get(HL_API, {"type": "candleSnapshot",
                         "req": {"coin": s, "interval": "1d", "startTime": 0}}))
        bars[s] = {c["t"]: tuple(float(c[k]) for k in "ohlc") for c in candles[:-1]}  # last candle is unfinished
        fund[s] = {}
        for r in cached(s + "_funding", lambda: hl_funding(s, candles[0]["t"])):
            day = r["time"] // DAY * DAY
            fund[s][day] = fund[s].get(day, 0) + float(r["fundingRate"])
    return bars, fund


def load_yahoo():
    """Split-adjusted, not dividend-adjusted: perps track price only, so dividends are not earned."""
    bars, fund = {}, {}
    now = int(time.time())
    for s in UNIVERSE:
        r = cached("yahoo_" + TICKER[s], lambda: get(YAHOO.format(TICKER[s], now)))["chart"]["result"][0]
        q = r["indicators"]["quote"][0]
        bars[s] = {t * 1000 // DAY * DAY: (o, h, l, c) for t, o, h, l, c
                   in zip(r["timestamp"], q["open"], q["high"], q["low"], q["close"]) if None not in (o, h, l, c)}
        bars[s].pop(max(bars[s]))  # today's bar may still be forming
        daily = FUNDING_APR[s] / 252  # funding accrues every calendar day; charged per trading day here
        fund[s] = {t: daily for t in bars[s]}
    return bars, fund


def wilder(values, n):
    avg = sum(values[:n]) / n
    for v in values[n:]:
        avg = (avg * (n - 1) + v) / n
    return avg


def indicators(closes, highs, lows):
    if len(closes) < 15:
        return None
    # Wilder averages forget their seed quickly; 300 bars keeps a 26-year run fast
    c, h, lo = closes[-300:], highs[-300:], lows[-300:]
    gains = [max(b - a, 0) for a, b in zip(c, c[1:])]
    losses = [max(a - b, 0) for a, b in zip(c, c[1:])]
    g, l = wilder(gains, 14), wilder(losses, 14)
    trs = [max(hh - ll, abs(hh - pc), abs(ll - pc)) for hh, ll, pc in zip(h[1:], lo[1:], c)]
    return {"price": closes[-1],
            "sma50": sum(closes[-50:]) / 50 if len(closes) >= 50 else None,
            "sma200": sum(closes[-200:]) / 200 if len(closes) >= 200 else None,
            "rsi14": 100 if l == 0 else 100 - 100 / (1 + g / l),
            "atr14": wilder(trs, 14)}


def simulate(bars, fund, start, end, exit_rule="sma200"):
    """Trade from start to end (ms, inclusive). Earlier bars only warm up the indicators."""
    cash, pos, last = 10_000.0, {}, {}
    hist = {s: ([], [], []) for s in UNIVERSE}
    curve, trades, fees, funding = [], [], 0.0, 0.0
    for t in sorted({t for s in UNIVERSE for t in bars[s] if t <= end}):
        markets = {}
        for s in UNIVERSE:
            if t not in bars[s]:
                continue
            o, h, lo, c = bars[s][t]
            last[s] = c
            for lst, v in zip(hist[s], (c, h, lo)):
                lst.append(v)
            if t < start:
                continue
            if s in pos:
                p = pos[s]
                f = p["qty"] * c * fund[s].get(t, 0)
                cash -= f
                funding += f
                if lo <= p["stop"]:
                    px = min(o, p["stop"])
                    cash += p["qty"] * px * (1 - FEE)
                    fees += p["qty"] * px * FEE
                    trades.append((s, p["entry"], px))
                    del pos[s]
            m = indicators(*hist[s])
            if m:
                markets[s] = m
        if t < start:
            continue
        equity = cash + sum(p["qty"] * last[s] for s, p in pos.items())
        for a in decide(equity, list(pos), markets, equity - cash, exit_rule):
            s, px = a["symbol"], markets[a["symbol"]]["price"]
            if a["action"] == "close":
                cash += pos[s]["qty"] * px * (1 - FEE)
                fees += pos[s]["qty"] * px * FEE
                trades.append((s, pos[s]["entry"], px))
                del pos[s]
            else:
                cash -= a["notional"] * (1 + FEE)
                fees += a["notional"] * FEE
                pos[s] = {"qty": a["notional"] / px, "entry": px, "stop": a["stop"]}
        curve.append((t, cash + sum(p["qty"] * last[s] for s, p in pos.items())))
    return {"curve": curve, "trades": trades, "fees": fees, "funding": funding, "open": sorted(pos)}


def buy_and_hold(bars, fund, syms, start, end):
    """Equal-weight buy at the first close on/after start, pay funding daily, sell at the last close."""
    total = 0.0
    for s in syms:
        days = [t for t in sorted(bars[s]) if start <= t <= end]
        value = (1 - FEE) / bars[s][days[0]][3]  # units bought with $1
        cost = 0.0
        for t in days:
            cost += value * bars[s][t][3] * fund[s].get(t, 0)
        total += value * bars[s][days[-1]][3] * (1 - FEE) - cost
    return total / len(syms) - 1


def stats(curve):
    years = (curve[-1][0] - curve[0][0]) / DAY / 365.25
    peak, mdd = 0, 0
    for _, v in curve:
        peak = max(peak, v)
        mdd = min(mdd, v / peak - 1)
    total = curve[-1][1] / 10_000 - 1
    return total, (1 + total) ** (1 / years) - 1, mdd


def ms(date):
    return int(datetime.strptime(date, "%Y-%m-%d").replace(tzinfo=timezone.utc).timestamp() * 1000)


def report(label, bars, fund, start, end, exit_rule):
    r = simulate(bars, fund, start, end, exit_rule)
    total, cagr, mdd = stats(r["curve"])
    wins = sum(b > a for _, a, b in r["trades"])
    print(f"  {label:26} total {total:+8.1%}  per year {cagr:+6.1%}  worst drop {mdd:7.1%}  "
          f"trades {len(r['trades']):4} ({wins / max(len(r['trades']), 1):.0%} won)  "
          f"fees ${r['fees']:,.0f}  funding ${r['funding']:,.0f}")
    return r


def benchmarks(bars, fund, start, end):
    years = (end - start) / DAY / 365.25
    spy = buy_and_hold(bars, fund, ["xyz:SP500"], start, end)
    held = [s for s in UNIVERSE if min(bars[s]) <= start + 10 * DAY]
    ew = buy_and_hold(bars, fund, held, start, end)
    print(f"  {'Hold SP500':26} total {spy:+8.1%}  per year {(1 + spy) ** (1 / years) - 1:+6.1%}")
    print(f"  {f'Hold all {len(held)} equally':26} total {ew:+8.1%}  per year {(1 + ew) ** (1 / years) - 1:+6.1%}")


if __name__ == "__main__":
    # self-check: RSI of a straight uptrend is 100, ATR of constant 2-wide bars is 2
    up = [float(i) for i in range(1, 31)]
    m = indicators(up, [x + 1 for x in up], [x - 1 for x in up])
    assert m["rsi14"] == 100 and abs(m["atr14"] - 2) < 1e-9 and m["sma50"] is None
    # self-check: buy-and-hold of a flat market with no funding loses exactly the two fees
    flat = {"xyz:SP500": {t * DAY: (10, 10, 10, 10) for t in range(5)}}
    assert abs(buy_and_hold(flat, {"xyz:SP500": {}}, ["xyz:SP500"], 0, 4 * DAY) - (-2 * FEE + FEE ** 2)) < 1e-12

    if sys.argv[1:] == ["hl"]:
        bars, fund = load_hl()
        start = min(t for s in UNIVERSE for t in bars[s])
        end = max(t for s in UNIVERSE for t in bars[s])
        for rule in ("sma50", "sma200", "cross"):
            report(f"exit {rule}", bars, fund, start, end, rule)
        sys.exit()

    bars, fund = load_yahoo()
    end = max(bars["xyz:SP500"])
    if sys.argv[1:2] == ["test"]:
        print("Test on 2016-today")
        a, rules = ms("2016-01-01"), sys.argv[2:]
    else:
        print("Pick on 2000-2015")
        a, end, rules = ms("2000-01-01"), ms("2015-12-31"), ["sma50", "sma200", "cross"]
    for rule in rules:
        report(f"exit {rule}", bars, fund, a, end, rule)
    benchmarks(bars, fund, a, end)
