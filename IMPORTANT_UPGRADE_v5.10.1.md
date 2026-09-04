# MarketScope v5.10.1 — Future Projection Empty-Portfolio Fix

This patch fixes the `KeyError: ''` traceback that appeared when Future Projection validated its four default empty holding fields.

The history-quality lookup now runs only after all four holdings are nonempty, unique, and present in the currently loaded MarketScope universe. Empty or partially completed portfolios remain on the form and display the normal instruction to select all four holdings. Blank fields are no longer reported as duplicate tickers.

No Monte Carlo formulas, historical simulator calculations, existing tabs, saved simulations, dependencies, environment variables, or data files changed.

Deploy the files over v5.10.0, preserve live saved-simulation JSON/PDF paths, and push to `main`. Render can use the existing configuration without migration.
