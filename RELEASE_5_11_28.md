# MarketScope 5.11.28 — Historical recession shading

All three native recession graphs now shade historical U.S. recessions in translucent red, behind the indicator line. A shared legend explains the meaning and each graph lists the recession date ranges visible in its selected history window. Existing indicator values, colors, missing-data gaps and the Sahm 0.50 threshold are preserved.

Dates use NBER chronology with FRED USREC's convention: the month following the business-cycle peak through the last day of the trough month. Bundled periods cover the three indicators' available histories from 1959 onward. The reference is dated September 15, 2026. These retrospective dates are not model signals, and new official recession declarations require a chronology update. No additional API request or secret is required for shading.

Source: https://fred.stlouisfed.org/series/USREC

Validation: 630 tests passed, including all three indicators, clipping to the selected history, preserving the Sahm threshold, and ensuring a high modeled probability alone does not create recession shading. Production browser appearance has not been verified.

Deploy the extracted repository-root files while preserving existing data. Include recession_shading.py and recession_indicators.py. This package retains the v5.11.27 macro snapshot publishing fix. GitHub and Render have not been updated by this delivery.
