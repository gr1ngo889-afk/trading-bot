# Paper trading journal (Liquid paper account)

Start: 2026-10-25, equity $10,000.00. Benchmark: hold mkts:US500 from $763.41.
From 2026-10-29 the benchmark is xyz:SP500 from 7642 (its price at the bot's start, 2026-10-25 21:32 UTC):
Liquid delisted mkts:US500 and lists the S&P 500 as xyz:SP500 (about 10x the price). Rows before that use US500.

| Date | Action | Symbol | Notional | Fill | Stop | Order id |
|---|---|---|---|---|---|---|
| 2026-10-25 | buy | xyz:MSFT | $1,811.54 | 522.80 | 493.95 | 144078 |
| 2026-10-25 | buy | xyz:LLY | $1,397.85 | 1274.00 | 1182.86 (exchange: 1182.9) | 144080 |
| 2026-10-25 | buy | xyz:AAPL | $2,000.00 | 346.92 | 330.54 | 144082 |

| Date | Equity | US500 / SP500 | Bot vs hold |
|---|---|---|---|
| 2026-10-25 | $9,994.52 | 763.41 | -0.05% vs 0.00% |
| 2026-10-26 | $10,020.14 | 765.25 | +0.20% vs +0.24% |
| 2026-10-27 | $10,037.15 | 769.37 | +0.37% vs +0.78% |
| 2026-10-28 | $10,121.20 | 770.30 | +1.21% vs +0.90% |
| 2026-10-29 | $10,138.18 | 7683.30 (SP500) | +1.38% vs +0.54% |
| 2026-10-30 | $10,132.02 | 7581.40 (SP500) | +1.32% vs -0.79% |
