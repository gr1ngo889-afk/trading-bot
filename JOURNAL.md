# Paper trading journal (Liquid paper account)

Start: 2026-10-25, equity $10,000.00. Benchmark: hold mkts:US500 from $763.41.
From 2026-10-29 the benchmark is xyz:SP500 from 7642 (its price at the bot's start, 2026-10-25 21:32 UTC):
Liquid delisted mkts:US500 and lists the S&P 500 as xyz:SP500 (about 10x the price). Rows before that use US500.

| Date | Action | Symbol | Notional | Fill | Stop | Order id |
|---|---|---|---|---|---|---|
| 2026-10-25 | buy | xyz:MSFT | $1,811.54 | 522.80 | 493.95 | 144078 |
| 2026-10-25 | buy | xyz:LLY | $1,397.85 | 1274.00 | 1182.86 (exchange: 1182.9) | 144080 |
| 2026-10-25 | buy | xyz:AAPL | $2,000.00 | 346.92 | 330.54 | 144082 |
| 2026-11-02 | stop hit | xyz:AAPL | -$97.64 (+$3.71 fees) | 329.98 | | 144083 |

| Date | Equity | US500 / SP500 | Bot vs hold |
|---|---|---|---|
| 2026-10-25 | $9,994.52 | 763.41 | -0.05% vs 0.00% |
| 2026-10-26 | $10,020.14 | 765.25 | +0.20% vs +0.24% |
| 2026-10-27 | $10,037.15 | 769.37 | +0.37% vs +0.78% |
| 2026-10-28 | $10,121.20 | 770.30 | +1.21% vs +0.90% |
| 2026-10-29 | $10,138.18 | 7683.30 (SP500) | +1.38% vs +0.54% |
| 2026-10-30 | $10,132.02 | 7581.40 (SP500) | +1.32% vs -0.79% |
| 2026-11-02 | $10,037.46 | 7554.90 (SP500) | +0.37% vs -1.14% |
| 2026-11-03 | $10,028.35 | 7577.50 (SP500) | +0.28% vs -0.84% |
| 2026-11-04 | $10,167.05 | 7701.40 (SP500) | +1.67% vs +0.78% |
| 2026-11-09 | $10,121.46 | 7550.70 (SP500) | +1.21% vs -1.19% |
| 2026-11-10 | $10,108.05 | 7534.10 (SP500) | +1.08% vs -1.41% |
| 2026-11-11 | $10,063.33 | 7619.30 (SP500) | +0.63% vs -0.30% |

Nov 3-6: daily runs were cut off by session restarts. Nov 3/4 rows are from data read during those runs;
Nov 4's buy signals (SP500, AAPL) were never shown for approval. Nov 5-6 have no data.
Nov 10: COST and AAPL buys were approved in a pop-up but the request was interrupted before execution; nothing was placed.
