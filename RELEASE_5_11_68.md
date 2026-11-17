# MarketScope 5.11.68 — ranking monthly freshness

The monthly writer and Top 5 ranking reader previously stopped at December of the last completed year. Both now include observed months through the current calendar month. Daily snapshot collection records the last adjusted-price observation date. Rankings reuse already retrieved adjusted daily histories to supplement current-year months without a new per-stock download loop.

The current month is explicitly partial MTD. It participates as observed performance, but is removed from full-month projection risk calibration. Future months, missing prior-month closes and nonfinite returns are not fabricated. Completed-year statistics and withdrawal windows remain unchanged.

Saved ranking details now expose monthly observation date, partial-month basis, coverage count, oldest instrument month and calibration basis. Previously saved rankings keep their original dates until recalculated; the scheduled workflow creates new rankings after refreshing monthly data. Ranking model audit version is 5.11.68.
