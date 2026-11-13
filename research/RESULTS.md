# Pullback sleeve: research and test results (2026-11-13)

Data: Shibui Finance daily trading-day prices and indicators, split-adjusted, not dividend-adjusted (perps earn no
dividends). Bot universe (SPY for xyz:SP500, SMH, XLE, TLT, MSFT, GOOGL, LLY, COST, AAPL, AMZN, NVDA, META) from
1989 or each listing date, plus 23 other tickers (QQQ, IWM, sector ETFs, EFA, EEM, IEF, GLD, JPM, XOM, JNJ, WMT,
AVGO, ORCL, NFLX, AMD, TSLA) used only to check the pattern holds outside the bot's list.
Reproduce the portfolio table with `pullback_backtest.sql`.

## 1. What the data shows
Forward returns by state, 23 tickers NOT in the bot universe, 1985-2026 (167k ticker-days):

| Uptrend (close > SMA200), 5-day move | Days | Next 5 days | Win rate |
|---|---|---|---|
| fell more than 3 ATR | 1,465 | +0.88% | 61% |
| fell 1.5-3 ATR | 10,166 | +0.58% | 59% |
| fell 0-1.5 ATR | 32,198 | +0.36% | 55% |
| rose 0-1.5 ATR | 43,472 | +0.19% | 53% |
| rose more than 1.5 ATR | 24,780 | +0.15% | 53% |
| all days | 167,199 | +0.29% | 54% |

Monotonic: the deeper the short-term drop inside an uptrend, the better the next week. Same picture on the bot's
12 markets before and after 2010 (RSI 30-40 in an uptrend: +0.86% / +0.75% next 5 days vs +0.43% baseline).

## 2. Rule picked on 1990-2009 only
Grid: drop 1.0/1.5/2.0/2.5 ATR x max hold 5/10/20 days x lot 20%/33% x exit on close > SMA5 or time only.
SMA5 exit beat time-only in every cell. Drop 1.5-2.0 ATR was a flat plateau (Sharpe 0.64-0.72).
Picked: drop >= 2 ATR, exit close > SMA5 or 5 days, 33% lots. 3x ATR stop added for safety (costs ~0.7%/yr).

## 3. Results (fees 0.05%/side, funding at last year's Liquid rates)

| | 1990-2009 (picked here) | 2010-2026 (untouched) | All |
|---|---|---|---|
| Pullback sleeve | 6.7%/yr, Sharpe 0.66 | 6.7%/yr, Sharpe 0.64 | 6.7%/yr, worst drop -17% |
| Current trend rules | 4.4%/yr, Sharpe 0.47 | 7.8%/yr, Sharpe 0.61 | 6.0%/yr, worst drop -27% |
| Trend + pullback in spare cash | 10.1%/yr, Sharpe 0.73 | 8.4%/yr, Sharpe 0.60 | 9.3%/yr, worst drop -25% |
| Hold SP500 (price only, minus funding) | 3.3%/yr | 9.6%/yr | 6.5%/yr, worst drop -64% |

**At Liquid's real cost (~0.10% per side, from the Nov 2 AAPL fills):**

| | All years | 2010-2026 | Worst drop |
|---|---|---|---|
| Trend + pullback in spare cash | **8.4%/yr, Sharpe 0.61** | 7.5%/yr, Sharpe 0.55 | -26% |
| Current trend rules | 5.7%/yr, Sharpe 0.52 | 7.5%/yr, Sharpe 0.59 | -27% |
| Pullback alone | 5.3%/yr, Sharpe 0.53 | 4.7%/yr, Sharpe 0.47 | -20% |
| Half trend, half pullback | 5.7%/yr, Sharpe 0.62 | 6.3%/yr, Sharpe 0.62 | -20% |

## 4. Robustness
- **Walk-forward** (each year picks the best grid cell on all earlier years, 2000-2026): +7.4%/yr, 20 of 27 years up.
- **Every ticker made money**: 35 of 35 tickers had a positive average trade (before costs); 4,278 trades, 71% won,
  average +0.70% over 3.6 days. Bot universe +0.91%, other 23 tickers +0.57%.
- **Regimes** (annualised, 1994-2026): pullback did best when markets were stressed (SP500 below its 200-day: +12.9%,
  20-day vol above 22%: +15.7%), exactly where the trend rules made ~0-4%. Correlation with the trend sleeve 0.43.
  Bear years: 2000 +37%, 2001 +4%, 2002 +15%, 2008 -8% (trend -6%, -9%, -11%, -18%).
- **Costs**: pullback trades ~60 times a year, so fees matter. 0.01%/side 7.9%/yr, 0.05% 6.7%, 0.10% 5.3%, 0.15% 3.8%.
  Funding barely matters (13% average exposure). The trend rules are the opposite: doubling funding takes them from
  6.0%/yr to -0.6%/yr; doubling it costs the pullback sleeve ~1.8%/yr.
- **Needs to add to trend positions**: most pullbacks happen in names the trend sleeve already holds. Allowing pullback
  lots only in names the trend sleeve does not hold cut trades from ~1,500 to 93 and the combination fell to 5.5%/yr.
  So `pullback.py` adds to an existing position and later reduces it by the same units.

## 5. Caveats
- Survivor-only data: today's mega-caps were picked in hindsight, so every number is biased up by an unknown amount.
- Best of ~50 grid cells; the out-of-sample and walk-forward checks are the honest numbers.
- Engine simplifications: fills at the close; funding uses one year of rates for all years; the trend sleeve's 3x ATR
  stop is not simulated; when more than 3 pullbacks are live the backtest splits cash equally instead of ranking.
- FMP plan only allows single-symbol quotes (batch quotes need an upgrade), so live prices come from Liquid.
