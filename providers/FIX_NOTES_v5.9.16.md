# MarketScope v5.9.16 — Profit Tile UX Fix

- Removed the `help=` tooltip from every return/profit tile so no floating hover message appears on click or hover.
- Kept the v5.9.7-style Card View organization from v5.9.15.
- Preserved native Streamlit callback/session-state logic for reliable exact-period profit calculations.
- Added performance-aware tile styling:
  - positive return: green font and green-accent border
  - negative return: red font and red-accent border
  - zero/unavailable: neutral font
  - selected tile uses a stronger tint of the same performance color
- No custom JavaScript is used for the calculation; selecting a tile still updates only the card-local fragment.
