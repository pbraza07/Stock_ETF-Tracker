# MarketScope v5.11.12 - History Status Correction

The application no longer displays `History Pending`.

The badge describes the independent annual-return cross-check, not whether the
stock has price history. MarketScope now displays only completed outcomes:

- **Verified** - every compared year is within the configured tolerance.
- **Partial** - some available years could be independently compared.
- **Review** - at least one compared year exceeds the tolerance.
- **Unavailable** - no independent comparison result is available.

Blank and older `Pending` values are normalized automatically to `Unavailable`
in cards, comparison tables, saved simulations, and PDF reports. Historical
returns, simulator calculations, and projection calculations are unchanged.
