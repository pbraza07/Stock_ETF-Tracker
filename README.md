# MarketScope v5.11.56

Performance upgrade preserving the existing portfolio, YTD, Future Projection,
news, economic calendar, recession indicators, and reporting features.

## Start locally

Use Python 3.12, install `requirements.txt`, then run `python start_marketscope.py`.
The local mode starts a separate calculation worker automatically. Keep the
private runtime directory if you want queued jobs and reports to survive restarts.

## Upgrade the existing app

Back up current saved data. Extract the release into your repository root, keeping
Render's Root Directory blank. Existing `render.yaml` remains compatible with the
single-service deployment. This archive contains bootstrap files, not a replacement
live simulation library, and does not include credentials or runtime job data.

## Public deployment

Read **PERFORMANCE_DEPLOYMENT.md** before public launch. **render.public.yaml** adds
an always-on web service, independent worker, PostgreSQL, and scheduled collection.
It requires configuring paid hosting resources and credentials; this release alone
does not provision or deploy them. Public authentication/access control for existing
shared saved-portfolio features remains a deployment requirement.

## Validation

See **RELEASE_5_11_56.md** for changes, verification results, and known validation
boundaries. Tests: `pip install pytest pypdf` then `python -m pytest -q`.
