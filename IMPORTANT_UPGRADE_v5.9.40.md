# IMPORTANT UPGRADE — MarketScope v5.9.40

## Saved Portfolio PDFs are upgrade-protected

v5.9.40 formalizes the Portfolio Simulation library and generated PDFs as **live user data**, not release files.

Protected live paths:

- `data/saved_portfolio_simulations.json`
- `data/generated_pdfs/`

The v5.9.40 release ZIP intentionally does **not** contain either live path. Therefore uploading the new version **over the existing GitHub repository** will not overwrite the saved simulation library or previously generated PDFs.

### Required Render environment variable

Keep `MARKETSCOPE_GITHUB_TOKEN` configured in Render with GitHub Contents read/write permission. MarketScope saves:

1. the simulation record to `data/saved_portfolio_simulations.json`; and
2. each real PDF to `data/generated_pdfs/<artifact>.pdf`.

On a Render restart/redeploy, MarketScope restores the PDF from GitHub back into the running server automatically.

### Optional second durable copy

If using a Render persistent disk, set `MARKETSCOPE_PDF_PERSIST_DIR` to a directory on that mounted disk. MarketScope will mirror PDFs there in addition to the normal server/GitHub storage.

### Never do this during an upgrade

Do not upload an empty `data/saved_portfolio_simulations.json`.
Do not delete or replace `data/generated_pdfs/`.
Do not use a destructive repository sync that deletes files absent from the release ZIP.
Do not remove `MARKETSCOPE_GITHUB_TOKEN` before or after deployment.
