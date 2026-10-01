# MarketScope v5.11.46 — Calendar return-button fix

Back to Economic Calendar now explicitly selects economic; Show Earnings Calendar explicitly selects earnings. Distinct widget keys replace the shared toggle key, so repeated/queued destination actions do not reverse the intended state.

The calendar renders in a Streamlit fragment. Calendar button and crop-control interactions rerun the calendar independently rather than requiring the market-data and portfolio dashboard to rerun. Economic and earnings frames use separate keyed containers so the selected content replaces the other frame.

The original economic widget URL, U.S./three-star/week configuration and styling are preserved. Earnings crop, scale and popup restrictions remain. Its unverified provider filters and in-page overlays remain existing limitations.

Validation includes repeated earnings-to-economic round trips inside a tab, idempotent back actions, a single remaining iframe with the economic URL after return, and crop settings. The reported production failure was not reproduced directly; these changes address the shared toggle and full-app-rerun dependencies. Live deployment/device verification is still needed. No financial calculations changed. Not deployed.

Regression result: 714 tests passed, 72 warnings.
