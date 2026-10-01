# MarketScope v5.11.43 — Compact earnings frame, importance 3

Earnings now requests importance=3 instead of 2,3. Headings and filter guidance reflect three stars only. The earnings page is scaled to 80% to make text and controls smaller. A compensated 125%-wide, 650px-high iframe yields the same full-width, 520px visible area as the economic calendar, with the existing dark filter and return button preserved.

This is whole-page scaling, not control over Investing.com's internal fonts or layout. It does not turn the full earnings webpage into an economic-style compact widget. Provider support for earnings query filters remains unverified; select/check U.S., This Week, and three-star importance inside Investing.com. No claim of exact layout matching, verified live rendering, or automatic filter enforcement is made.

No simulation or financial calculations changed. This cumulative package has not been deployed.

Validation: 711 automated regression tests passed (72 warnings), including earnings parameters, compensated iframe sizing, and switching back to the economic calendar. External live appearance/filter enforcement is not verified by these tests.
