
# MarketScope v5.9.12 — Card + Table Stock / ETF Search

Added a dedicated **Search stock / ETF** input to **Card View** so both display modes are searchable.

## Behavior

- Card View search filters cards before sorting and pagination.
- Table View search continues to filter the sortable market table.
- Both support partial, case-insensitive matching across:
  - Symbol
  - Name
  - Type
  - Sector
  - Industry
  - Analyst Rating
- Each view shows its current match count while a search is active.
- Clearing the field restores the full active filtered universe for that view.

The previous shared search box above Display Mode was removed to avoid redundant/confusing double filtering.
