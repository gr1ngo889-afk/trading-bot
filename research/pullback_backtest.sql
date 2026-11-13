-- Portfolio backtest of the trend rules, the pullback sleeve, and both together, 1990-2026.
-- Run in Shibui Finance (DuckDB) through its stock_data_query tool; it returns one row per strategy, fee level and period.
-- Engine notes: fills at the daily close; position decided at the prior close; funding = last year's Liquid APR
-- charged per trading day while held; fee charged on every entry and exit; pullback stop is intraday (fills at the
-- stop or the open if it gapped through). Trend sleeve: 1% risk sizing capped at 20%, no 3x ATR stop modelled.
WITH fund(ticker, apr) AS (VALUES ('SPY',0.022),('SMH',0.148),('XLE',0.161),('TLT',0.211),('MSFT',0.073),('GOOGL',0.106),('LLY',0.165),('COST',0.081),('AAPL',0.022),('AMZN',0.087),('NVDA',0.104),('META',0.073)),
fees(fee) AS (VALUES (0.0005),(0.0010)),
raw AS (
  SELECT sq.ticker, sq.date, sq.open, sq.low, sq.close, ti.sma_200, ti.sma_50, ti.rsi_14, ti.atr_14,
    ROW_NUMBER() OVER w AS rn, LAG(sq.close,5) OVER w AS cm5, LAG(sq.close) OVER w AS pc,
    AVG(sq.close) OVER (PARTITION BY sq.symbol ORDER BY sq.date ROWS BETWEEN 4 PRECEDING AND CURRENT ROW) AS sma5
  FROM shibui.stock_quotes sq JOIN shibui.technical_indicators ti ON sq.symbol=ti.symbol AND sq.date=ti.date
  WHERE sq.ticker IN (SELECT ticker FROM fund) AND sq.date >= DATE '1989-01-01'
  WINDOW w AS (PARTITION BY sq.symbol ORDER BY sq.date)
), sig AS (SELECT *, (close > sma_200 AND atr_14 > 0 AND close - cm5 <= -2.0*atr_14) AS s, (close > sma5) AS x FROM raw WHERE rn > 200),
st AS (SELECT *, MAX(CASE WHEN s THEN rn END) OVER v AS ls, MAX(CASE WHEN x AND NOT s THEN rn END) OVER v AS lx,
   LAST_VALUE(CASE WHEN s THEN close - 3*atr_14 END IGNORE NULLS) OVER v AS stop_lvl FROM sig WINDOW v AS (PARTITION BY ticker ORDER BY date ROWS UNBOUNDED PRECEDING)),
pos AS (SELECT *, CASE WHEN ls IS NOT NULL AND ls > COALESCE(lx,0) AND rn - ls < 5 THEN 1 ELSE 0 END AS p FROM st),
pr AS (SELECT ticker, date, open, low, pc, close/pc-1 AS r, LAG(p) OVER q AS hp, LAG(stop_lvl) OVER q AS hstop, p FROM pos WINDOW q AS (PARTITION BY ticker ORDER BY date)),
tid AS (SELECT *, SUM(CASE WHEN p=1 AND COALESCE(hp,0)=0 THEN 1 ELSE 0 END) OVER (PARTITION BY ticker ORDER BY date ROWS UNBOUNDED PRECEDING) AS t FROM pr),
stp AS (SELECT *, CASE WHEN hp=1 AND low < hstop THEN 1 ELSE 0 END AS hit FROM tid),
stp2 AS (SELECT *, SUM(hit) OVER (PARTITION BY ticker, t ORDER BY date ROWS UNBOUNDED PRECEDING) - hit AS prior_hits FROM stp),
act AS (SELECT s.*, f.apr, SUM(hp) OVER (PARTITION BY date) AS nact,
   CASE WHEN prior_hits > 0 THEN 0 WHEN hit=1 THEN LEAST(open, hstop)/pc - 1 ELSE r END AS r_stop FROM stp2 s JOIN fund f USING (ticker) WHERE hp IS NOT NULL),
mrd AS (SELECT date, COALESCE(SUM(hp*LEAST(0.33,1.0/NULLIF(nact,0))*(r_stop-apr/252)),0) g, SUM(ABS(p-hp)*0.33) tov, COALESCE(SUM(hp*LEAST(0.33,1.0/NULLIF(nact,0))),0) ex FROM act GROUP BY date),
tsig AS (SELECT *, (close > sma_50 AND sma_50 > sma_200 AND rsi_14 < 70) AS s, (close < sma_200) AS x, LEAST(0.2, 0.01*close/NULLIF(3*atr_14,0)) AS w FROM raw WHERE rn > 200),
tst AS (SELECT *, MAX(CASE WHEN s THEN rn END) OVER v AS ls, MAX(CASE WHEN x THEN rn END) OVER v AS lx FROM tsig WINDOW v AS (PARTITION BY ticker ORDER BY date ROWS UNBOUNDED PRECEDING)),
tpos AS (SELECT *, CASE WHEN ls IS NOT NULL AND ls > COALESCE(lx,0) THEN 1 ELSE 0 END AS p FROM tst),
tpr AS (SELECT ticker, date, close/pc-1 AS r, LAG(p) OVER q AS hp, LAG(w) OVER q AS hw, p FROM tpos WINDOW q AS (PARTITION BY ticker ORDER BY date)),
tact AS (SELECT tpr.*, SUM(hp*hw) OVER (PARTITION BY date) AS tw, f.apr FROM tpr JOIN fund f USING (ticker) WHERE hp IS NOT NULL),
trd AS (SELECT date, SUM(hp*hw/GREATEST(1,tw)*(r-apr/252)) g, SUM(ABS(p-hp)*hw) tov, SUM(hp*hw/GREATEST(1,tw)) ex FROM tact GROUP BY date),
s AS (
  SELECT 'pullback' sid, f.fee, m.date, m.g - m.tov*f.fee AS ret FROM mrd m CROSS JOIN fees f
  UNION ALL SELECT 'trend', f.fee, t.date, t.g - t.tov*f.fee FROM trd t CROSS JOIN fees f
  UNION ALL SELECT 'half/half', f.fee, t.date, 0.5*(t.g - t.tov*f.fee) + 0.5*(m.g - m.tov*f.fee) FROM trd t JOIN mrd m USING (date) CROSS JOIN fees f
  UNION ALL SELECT 'trend+pullback_in_spare_cash', f.fee, t.date, (t.g - t.tov*f.fee) + (m.g - m.tov*f.fee)*LEAST(1, GREATEST(0,1-t.ex)/NULLIF(m.ex,0)) FROM trd t JOIN mrd m USING (date) CROSS JOIN fees f),
c AS (SELECT *, EXP(SUM(LN(1+COALESCE(ret,0))) OVER (PARTITION BY sid, fee ORDER BY date)) cv FROM s WHERE date >= DATE '1990-01-01'),
d AS (SELECT *, COALESCE(ret,0) rr, cv/MAX(cv) OVER (PARTITION BY sid, fee ORDER BY date ROWS UNBOUNDED PRECEDING)-1 dd, CASE WHEN date < DATE '2010-01-01' THEN 'IS' ELSE 'OOS' END per FROM c)
SELECT sid, fee*100 fee_pct, per, ROUND((POWER(EXP(SUM(LN(1+rr))),252.0/COUNT(*))-1)*100,2) cagr, ROUND(AVG(rr)/STDDEV(rr)*SQRT(252),2) sharpe, ROUND(MIN(dd)*100,1) mdd FROM d GROUP BY sid, fee, per
UNION ALL SELECT sid, fee*100, 'ALL', ROUND((POWER(EXP(SUM(LN(1+rr))),252.0/COUNT(*))-1)*100,2), ROUND(AVG(rr)/STDDEV(rr)*SQRT(252),2), ROUND(MIN(dd)*100,1) FROM d GROUP BY sid, fee
ORDER BY sid, fee_pct, per LIMIT 40
