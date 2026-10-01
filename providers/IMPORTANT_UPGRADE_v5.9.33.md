# IMPORTANT UPGRADE — MarketScope v5.9.33

## Sector Performance scalar-return crash fix
- Fixes `AttributeError: numpy.float64 object has no attribute notna` in the Sector Performance top-performers popover.
- Timeframe extraction now always produces an index-aligned numeric pandas Series, including when a metric is missing or duplicate source labels exist.
- Total Profit and Total Profit % continue to recalculate from the selected timeframe.

## Print PDF removal
- MarketScope contains no app-owned Print PDF action.
- The mobile/server PDF viewer now requests the embedded browser PDF with its native toolbar hidden, removing the browser-side print control while preserving MarketScope Share PDF, Download, and Back to MarketScope controls.
