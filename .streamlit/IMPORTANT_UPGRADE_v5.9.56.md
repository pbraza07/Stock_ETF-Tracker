# MarketScope v5.9.56 — Historical Data Verification

MarketScope now automatically cross-checks the primary Yahoo/yfinance completed annual returns against an independent Stooq U.S. bulk historical-price dataset.

## Verification rules

- Primary return source remains Yahoo/yfinance adjusted historical data.
- Secondary verification source is Stooq U.S. bulk historical Close data.
- Every available completed annual return from 2025 through 2001 is compared when the same annual anchor exists in Stooq.
- Default tolerance: 0.25 percentage points.
- The secondary source never overwrites the Yahoo return automatically.

Verification states:

- **Verified** — every available Yahoo annual return was independently compared and all differences are within 0.25 percentage points.
- **Partial** — available comparisons agree within tolerance, but the secondary source does not cover every Yahoo year.
- **Review** — at least one compared year differs by more than 0.25 percentage points.
- **Unavailable** — no comparable Stooq annual return is available.
- **Pending** — no successful independent cross-check has been saved yet.

The snapshot stores verification coverage, discrepancy count, maximum difference and the exact exception years.

## Automatic refresh

The normal GitHub refresh now:
1. builds the verified 25-year Yahoo snapshot;
2. validates 2025–2001 coverage;
3. retrieves/caches the Stooq U.S. bulk historical archive;
4. cross-checks the annual returns;
5. persists the Yahoo returns plus verification metadata using the v5.9.55 race-safe persistence mechanism.

The Stooq archive is cached by ISO week because completed historical annual returns do not need a fresh 300+ MB secondary download every day.

A temporary Stooq outage never blocks or deletes the primary Yahoo snapshot. Previously saved verification metadata is preserved until a later successful cross-check.

## UI

Market Card View and Stock/ETF Comparison cards show a compact History verification badge.

Market Table View includes:
- History Check
- Verified Coverage
- Review Years
- Max Δ (percentage points)
- Verification Exceptions

Portfolio PDFs include the verification status in the Portfolio Information Table.

## Interpretation

A Review flag is a data-quality warning, not an instruction to change the stored return. Differences can come from corporate-action adjustment methods, symbol mapping, vendor corrections or different historical records.
