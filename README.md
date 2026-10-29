# Trend bot (Liquid paper trading)

Long-only trend-following bot for Liquid's stock perps (`xyz:` markets on Hyperliquid). **Paper trading only.**

## Rules (`strategy.py`)
- Buy when price > SMA50 > SMA200 and RSI14 < 70 (daily candles).
- Sell when price closes below SMA200. A stop at entry - 3x ATR14 sits on the exchange.
- Size so the stop loses 1% of equity, max 20% of equity per position, 1x leverage, never more than equity in total.
- Markets with fewer than 200 days of history are skipped until they have it.
- `python3 strategy.py < snapshot.json` prints the actions; it self-tests on every run.

## Backtest findings (`backtest.py`)
- Rule picked on 2000-2015 only (SMA200 exit beat SMA50 exit and the 50/200 cross), then run once on 2016-today.
- 2016-today, 12 stocks: +12.9%/yr, worst drop -21%, vs holding US500 +11.5%/yr. The stock list was picked in hindsight
  (holding all 12 equally made +32.5%/yr), so this is not evidence of an edge.
- US500 alone, full size: 2000-today +4.1%/yr (worst drop -19%) vs hold +5.4%/yr (worst drop -56%).
  Expect market-like returns or less, with smaller crashes.
- Funding on Liquid's stock perps costs longs 2-21%/yr (AAPL 2.2%, SP500 2.2%, LLY 16.5%, TLT 21.1%). Biggest drag.
- `python3 backtest.py` (pick period), `python3 backtest.py test sma200` (test period), `python3 backtest.py hl` (Liquid's own data).
  Needs network access to api.hyperliquid.xyz and query1.finance.yahoo.com.

## Daily run (weekdays, 4:37pm New York)
1. Confirm Liquid `paper_trading_status` is ENABLED; if not, stop and tell the user. Never trade live.
2. `get_portfolio` (skipCache): equity, positions, stop coverage. A missing position means its stop probably triggered; check position history.
3. `get_technical_indicators` (1d; sma, rsi, atr) for every symbol in `UNIVERSE`, plus `xyz:SP500` for the benchmark.
4. Build the snapshot (`equity`, `held`, `exposure` = margin used, `markets`) and run `strategy.py`.
5. Add a row to `JOURNAL.md` (equity, SP500 price, bot vs SP500 return since 2026-10-25 21:32 UTC: start equity $10,000, SP500 7642). Commit and push.
6. For each action, preview it (`suggest_trade`, or `close_position` for sells) and show the user the exact terms.
   **Execute only after the user explicitly approves those exact terms in chat.** Log fills in `JOURNAL.md`, commit, push.

See `JOURNAL.md` for positions and performance.
