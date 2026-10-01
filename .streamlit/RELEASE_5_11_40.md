# MarketScope v5.11.40 — Earnings calendar shortcut

Adds an Earnings Calendar link button immediately above the existing economic iframe in Market Navigator. It opens Investing.com in a new browser tab. The economic calendar remains open in MarketScope, so switching back returns to it.

Investing.com filters must be selected on the provider page: This Week, United States, and importance two and three. No unsupported automatic-filter URL or earnings iframe is used. The interface explicitly explains this limitation. This is the external-link fallback approved by the user.

All simulation, stock ranking, projection and economic calendar calculations/configuration are unchanged. This cumulative source package has not been deployed.

Validation: 708 regression tests passed (72 warnings). Streamlit AppTest verified calendar rendering, earnings-link destination, and explicit manual-filter guidance. External provider filtering is not automated or verified by these tests.
