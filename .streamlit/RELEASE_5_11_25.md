# MarketScope 5.11.25 - YTD period statistics

YTD portfolio cards, saved cards, and each strategy's actual-data area now show:
- Longest positive and negative streaks, with counts and observed date ranges.
- Maximum period investment profit and loss, with observed dates/ranges.

Statistics follow the completed run's Daily, Weekly, or Monthly table period.
Run again after changing inputs. Streak signs use compounded returns before
withdrawals; extremes use summed investment profit within each display period.
Zero-return periods break streaks, weekends are not trading observations, and
equal ties show the earliest period. Partial periods are included and their dates
reflect observed data. No positive/negative result displays None, not a fabricated
extreme. None cadence retains the single Performance label.

Existing saved records derive statistics from their stored daily ledger without
changing the saved cash flows. PDF and Excel downloads include the same metrics.
Previously stored PDF share artifacts remain historical unless regenerated;
fresh PDF downloads contain the new statistics.

Deploy the extracted archive at the repository root while preserving existing
data, histories and generated PDFs. No new environment variables. Version 5.11.24
is preserved. This package does not deploy itself to GitHub or Render.
