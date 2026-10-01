# MarketScope v5.11.41 — In-page earnings calendar switch

The button above the calendar now replaces the economic iframe with an Investing.com earnings-page iframe inside MarketScope. Back to Economic Calendar restores the existing weekly U.S. three-star economic widget. Only the selected calendar is rendered. The selector persists across session reruns.

The earnings iframe uses https://www.investing.com/earnings-calendar/ rather than a legacy earnings widget endpoint. Select This Week, United States, and two/three-star importance inside Investing.com. Automatic filtering and control of the provider page's internal colors are not supported by this integration; clear guidance is shown above the iframe. The provider may block embedded access or require consent. The source link is retained as a fallback.

Verification: public earnings URL returned HTTP 200 without an X-Frame-Options header in the checked response. This is not proof of rendering in every browser. The cloud browser blocked the local iframe preview (ERR_BLOCKED_BY_CLIENT), so live embedded rendering could not be verified here. Automated Streamlit tests cover switching to the earnings iframe and back to the original economic iframe, plus filter guidance.

All simulation, projection and ranking calculations are unchanged. This package has not been deployed.

Regression result: 709 passed, 72 warnings.
