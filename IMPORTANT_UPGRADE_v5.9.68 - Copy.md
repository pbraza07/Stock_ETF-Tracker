# MarketScope v5.9.68 - PDF Withdrawal Summary + Market Table Target Transcription

## PDF page 1 withdrawal context

When a saved Portfolio Simulation uses recurring withdrawals, the first-page **TOTAL INVESTED** card now also carries the applicable income summary in compact text.

### Yearly Withdrawal

The same card shows:
- Annual Withdrawal
- Rebalanced Remaining
- Not-Rebalanced Remaining
- Rebalance Difference
- Withdrawals Funded: RB x/y and NR x/y

### Monthly Withdrawal

The same card shows:
- Monthly Withdrawal
- Rebalanced Remaining
- Not-Rebalanced Remaining
- Rebalance Difference
- Positive Months: RB x/y and NR x/y

The four primary portfolio KPI cards remain on the first row; no separate oversized withdrawal section is added to page 1.

## Exact Market Table price-target handoff

MarketScope now maintains an in-session price-target registry for **Low / Average / High** values that have already been resolved and displayed in Market Table.

Whenever Market Table has a valid target value, that exact value is remembered. Saving or rebuilding a Portfolio PDF then uses those remembered Market Table values before attempting any additional Yahoo lookup.

This fixes the failure mode where:
1. Market Table correctly displayed Low / Avg / High;
2. the Portfolio PDF performed a separate target lookup;
3. the second lookup was throttled or returned empty;
4. page 1 incorrectly rendered `LOW - AVG/CONS - HIGH -`.

Existing durable snapshot values and Yahoo/yfinance target fallbacks remain in place. The Market Table bridge is an additional deterministic handoff, not a replacement for persistent target data.

## Saved simulations

The v5.9.67 Save / Manage withdrawal summaries remain unchanged and continue to display the full five-card annual or monthly result inside the app.

## PDF contract

The PDF layout contract is **v26**. Opening/rebuilding an older saved simulation forces page 1 through the new withdrawal-summary and target-transcription layout.
